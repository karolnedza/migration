#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import argparse
from dm.arm.terraform import Terraform as tf
import dm.logconf as logconf
from dm.arm.commonlib import Common as common
from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.lib.arm_utils import get_ad_sp_credential
from dm.arm.io import ArmIO as avxio
from dm.aws import Aws as aws
from dm.aviatrix import Aviatrix as av
from azure.mgmt.network import NetworkManagementClient
from dm.arm.switchlib import SwitchTraffic as sw

# 
# AVX-13563 [Azure] Allow Advanced attachment of route tables without subnet association
#
# Problem: 
# 1) Controller does not program the staged <vnetName>-main-1, <vnetname>-main-2 rt in
# staging because it is not associated to a subnet.
# 2) Controller creates and associates a default route table to subnet without UDR.  However, the default RT
# does not have Propagate Route enabled, disrupting onprem traffic.
#
# Workaround: 
# 1) Use prestage to create and associate a default RT with Propagate Route enabled to all subnets without UDR.
# 2) Detach spoke, switch subnet route table and then re-attach spoke at switch_traffic so RFC1918 are added to
# the <vnetName>-main-1, <vnetname>-main-2 and all pre-existing UDRs.
#
# switch_traffic logic:
# 1) Detach spoke
# 2) For subnet without an UDR or subnet associated to controller default RT, re-associate it to Main-1 
#    and Main-2 RT created in staging.
# 3) For subnet with an UDR, re-associate it to the UDR copy created in staging.
# 4) Update spoke gw customized cidr
# 5) Attach spoke
#
# switch_traffic --revert logic:
# 1) Detach spoke
# 2) For subnet associated to Main-1 and Main-2 RT, re-associate it to None
# 3) For subnet associated to an UDR created in staging, re-associate it back to the original UDR.
# 4) Revert spoke gw customized cidr.  
# 5) Attach spoke
# 6) For subnet associated to controller created RT (because of step 4 re-attach spoke), 
#    set subnet association to None.
#
if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='Switch subnet traffic to use new route tables')
    # args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    args_parser.add_argument(
        '--ctrl_user', help='Aviatrix Controller username')
    args_parser.add_argument(
        '--s3_yaml_download', help='a list of comma separated strings in the form: <s3_account>,<s3_role>,<s3_bucket>,<spoke_account>')
    args_parser.add_argument(
        '--s3backup', help='At the end of switch_traffic, upload the generated account folder into S3', action='store_true', default=False)
    args_parser.add_argument(
        '--s3download', help='At the beginning of switch_traffic, download the archived account folder from S3', action='store_true', default=False)
    args_parser.add_argument(
        '--yaml_file', help='specify input <yaml_file>')
    args_parser.add_argument(
        '--revert', help='revert route table migration', action='store_true', default=False)
    args_parser.add_argument(
        '--dry_run', help='Dry run traffic_switch logic and show what will be done', action='store_true', default=False)
    args = args_parser.parse_args()

    input_file = ''
    if args.s3_yaml_download != None:
        if not aws.downloadS3Yaml(args.s3_yaml_download):
            print(f'Failed to download YAML File from S3 using the yaml info: {args.s3_yaml_download}')
            sys.exit()
        input_file = '/tmp/discovery.yaml'
    elif args.yaml_file:
        input_file = args.yaml_file
    else:
        print('Missing input yaml! Please use --s3_yaml_download to download from S3  or --yaml_file to specify the local filename')

    if not os.path.isfile(input_file):
        print(f'YAML File {input_file} does not exist')
        sys.exit()

    ## setup logging
    accounts_data = common.convert_yaml_to_json(input_file)
    common.expectYamlType(accounts_data,'AZURE')

    logconf = common.initLogLocation(accounts_data)
    logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO    
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.arm.switch_traffic {iargs}')

    # subscription_id = os.getenv('ARM_SUBSCRIPTION_ID')
    # arm_tenant_id = os.getenv('ARM_TENANT_ID')
    # arm_client_id = os.getenv('ARM_CLIENT_ID')
    # arm_client_secret = os.getenv('ARM_CLIENT_SECRET')

    # at = dl.getAccessToken(arm_tenant_id, arm_client_id, arm_client_secret)
    # credential = get_ad_sp_credential(arm_tenant_id, arm_client_id, arm_client_secret)
    # if credential == None:
    #     logger.error(f'Failed to get Azure account credential from environment variables')
    #     sys.exit()

    # cred = {
    #     'subscription_id': subscription_id,
    #     'credentials': credential,
    #     'accessToken': at
    # }
    
    if args.dry_run:
        aws.setDryRun()
        sw.setDryRun()
        tf.setDryRun()

    ctrl_user, ctrl_pwd = common.getCtrlCredential(args)

    ##
    target_folder = accounts_data['terraform']['terraform_output']
    api_ep_url = "https://" + \
        accounts_data['aviatrix']['controller_ip'] + "/v1/"
    CID = av.getCid(api_ep_url, ctrl_user, ctrl_pwd)

    YAML = {
       'allow_vnet_cidrs': common.getAllowVpcCidr(accounts_data),
       'subscriptionMap': common.getAzurermSubscriptionInfo(accounts_data),
       'ctrl_private_ip': common.getControllerPrivateIp(accounts_data),
       'default_route_table': common.getPreStageDefaultRouteTable(accounts_data)
    #    'subscriptionMap': common.getAzurermSubscriptionInfo(accounts_data)
    }

    # allsubs = avxio.readJsonInfo(f"rt.json")

    # subs = list_subscriptions(credential)
    # for sub in subs:
    #     common.logSubscription(sub['subscription_id'])

    #     list_vnet(sub['subscription_id'],credential)

    spoke_gw_adv_cidr = None

    subsInYaml = [x['subscription_id'] for x in accounts_data['account_info']]
    for account in accounts_data['account_info']:
        if not account['subscription_id'] in subsInYaml:
            continue
        common.logSubscription(account['subscription_id'])
        subscriptionId = account['subscription_id']
        subscriptionInfo = YAML['subscriptionMap'][subscriptionId]

        # pass subscriptionId into sw.updateSubnetAssociation for populating the provider
        YAML['subscriptionId'] = subscriptionId
        
        arm_tenant_id = subscriptionInfo['dir_id']
        arm_client_id = subscriptionInfo['app_id']
        arm_client_secret =  os.getenv(subscriptionInfo['secret_env'])
        credential = get_ad_sp_credential(arm_tenant_id, arm_client_id, arm_client_secret)
        if credential == None:
            logger.error(f'Failed to get Azure account credential for {subscriptionId}')
            continue
        
        cred = {
            'subscription_id': subscriptionId,
            'credentials': credential,
            'arm_tenant_id': arm_tenant_id,
            'arm_client_id': arm_client_id,
            'arm_client_secret': arm_client_secret
        }

        target_location = f"{target_folder}/{account['subscription_id']}"
        tf.setSwitchTrafficTargetFolder(target_location)

        # If s3Bucket is used, download from S3 the terraform files
        if args.s3download:
            aws.downloadAllFiles(accounts_data, target_location)

        if args.revert == False:
            if tf.isRevertInfoExist():
                logger.warning(
                    f'**Alert** revert.json found for account {account["subscription_id"]}. Please revert first (switch_traffic --revert) before rerunning switch_traffic for this account.')
                continue
        else:
            if not tf.isRevertInfoExist():
                logger.warning(
                    f'**Alert** revert.json NOT found for account {account["subscription_id"]}, nothing to revert for this account.')
                continue

        if spoke_gw_adv_cidr == None:
            # read all spoke_gw once, since controller returns all gw(s) it managed for all
            # accounts
            spoke_gw_adv_cidr = av.get_spoke_gw_adv_cidr(api_endpoint_url=api_ep_url+"api", CID=CID)

        revertInfo = {
            "vnetid-tf-size": {},
            "gw_adv_cidr": {},
            "route_table_prop": {},
            "peering_prop": {}
        }

        tf.deleteSubnetAssociationTf()
        if args.revert == True:
            revertInfo = tf.readRevertInfo()
        else:
            # only delete the undo script at the begining of switch_traffic
            # so user can use it after --revert
            tf.deleteUndoSubnetAssociationTf()

        network_client = NetworkManagementClient(cred['credentials'], cred['subscription_id'])
        vnetsInYaml = {x['vnet_name']: x for x in account['vnets']}
        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)
        for vnet in vnets:
            if not vnet.name in vnetsInYaml:
                continue
            gw_name = sw.deduceGwNameWithSubnetCidr(vnet.location,vnetsInYaml[vnet.name]['avtx_cidr'])

            # - Detach spoke from transit attachment
            transit_name = sw.deduceTransitNameWithRegion(vnet.location)
            logger.info(f'- Detach {gw_name} from {transit_name}')
            if not args.dry_run:
                av.detach_spoke_from_transit_gw(api_endpoint_url=api_ep_url+"api", CID=CID, spoke_gw=gw_name, transit_gw=transit_name)

            if args.revert == False:
                # update switch_traffic attribute in vpc_id.tf file
                tf.updateSwitchTraffic({
                    'vnet_name': vnet.name,
                    'switch_traffic': True
                })
                # record file size after substitution and
                # make sure revert file first before subsitution when reverting
                tf.storeFileSize(
                    f'{vnet.name}.tf', revertInfo)
            else:
                tf.revertFile(
                    f'{vnet.name}.tf', revertInfo)
                # revert substitution after reverting file
                tf.updateSwitchTraffic({
                    'vnet_name': vnet.name,
                    'switch_traffic': False
                })

                # restore route table propagation flag
                sub_vnet_key = f'{subscriptionId}:{vnet.name}'
                if sub_vnet_key in revertInfo['route_table_prop']:
                    sw.restoreRouteTablePropagationInVnet(network_client, revertInfo['route_table_prop'][sub_vnet_key])

                # restore use_remote_gateway flag in peering.
                if sub_vnet_key in revertInfo['peering_prop']:                
                    sw.restoreUseRemoteGwInPeering(network_client, revertInfo['peering_prop'][sub_vnet_key])

            # - Re-associate subnets to route tables created in staging
            rtb_target_rtb_map = {}
            stagedUdrLst = sw.discoverRouteTable(cred,
                    args.revert, vnet, rtb_target_rtb_map)
            resourceGroup = vnet.id.split('/')[dl.RG_I]
            stagedUdrLst.append(f'{vnet.name}-main-1:{resourceGroup}')
            stagedUdrLst.append(f'{vnet.name}-main-2:{resourceGroup}')            
            sw.updateSubnetAssociation(YAML,
                    args.revert, cred, vnet, rtb_target_rtb_map)

            # - update gw advertised cidr
            vnet_cidrs = []
            separator = ","                
            if args.revert == False:
                # lookup the vpc cidrs
                vnet_cidrs = sw.discoverVpcCidr(vnet, YAML)
                avtx_cidr = vnetsInYaml[vnet.name]['avtx_cidr']
                if avtx_cidr != "" and not avtx_cidr in vnet_cidrs:
                    vnet_cidrs.append(avtx_cidr)
                if not gw_name in spoke_gw_adv_cidr:
                    logger.warning(f'  **Alert** {gw_name} not found in controller')
                else:
                    org_vnet_cidrs = spoke_gw_adv_cidr[gw_name]
                    if len(org_vnet_cidrs) > 0:
                        revertInfo['gw_adv_cidr'][gw_name] = org_vnet_cidrs
                    vnet_cidrs_str = f"{separator.join(vnet_cidrs)}"
                    logger.info(
                        f'- Configure {gw_name} with advertized cidrs {vnet_cidrs_str}')
                    if not args.dry_run:
                        try:
                            av.edit_gw_adv_cidr(
                                api_endpoint_url=api_ep_url+"api", CID=CID, gw_name=gw_name, cidrs=vnet_cidrs_str)
                        except Exception as e:
                            logger.error(f'  **Error** Failed to configure {gw_name} with advertized cidrs -{e}')
            else:
                # - revert gw advertised cidr
                if gw_name in revertInfo['gw_adv_cidr']:
                    vnet_cidrs = revertInfo['gw_adv_cidr'][gw_name]
                vnet_cidrs_str = f"{separator.join(vnet_cidrs)}"
                if len(vnet_cidrs_str) == 0:
                    logger.info(
                        f'- Revert {gw_name} advertized cidrs to NO advertized cidr')
                else:
                    logger.info(
                        f'- Revert {gw_name} advertized cidrs to {vnet_cidrs_str}')
                if not args.dry_run:
                    try:
                        av.edit_gw_adv_cidr(
                            api_endpoint_url=api_ep_url+"api", CID=CID, gw_name=gw_name, cidrs=vnet_cidrs_str)
                    except Exception as e:
                        logger.error(f'  **Error** Failed to configure {gw_name} with advertized cidrs -{e}')

            # - attach spoke to transit gateway
            logger.info(f'- Attach {gw_name} to {transit_name}')
            if not args.dry_run:
                av.attach_spoke_to_transit_gw(api_endpoint_url=api_ep_url+"api", CID=CID, spoke_gw=gw_name, transit_gw=transit_name, route_table_list=','.join(stagedUdrLst))

            if args.revert == False:
                # disable UDR route table propagation flag
                sub_vnet_key = f'{subscriptionId}:{vnet.name}'                
                rtb_prop = sw.disableAllRouteTablePropagationInVnet(network_client, args.revert, vnet, rtb_target_rtb_map)
                revertInfo['route_table_prop'] = {
                    sub_vnet_key: rtb_prop
                }
                # disable use_remote_gateway flag in peering for spoke vnet
                if not sw.isVnetWithVng(cred,vnet,sw.ER):
                    revertInfo['peering_prop'] = {
                        sub_vnet_key: sw.disableUseRemoteGwInPeering(subscriptionId, network_client, vnet, exclude='av-peer-')
                    }

            # if args.revert == True:
            #     logger.info(
            #         f'- Disassociate subnet(s) from controller created default route table')
            #     if not args.dry_run:
            #         sw.disassociateSubnetFromControllerRT(YAML, cred, vnet)
                
            # delete peering
            # if args.revert == False:
            #     peeringPairList = sw.deletePeerings(YAML, subscriptionId, vnet)
            #     revertInfo['peering'][vnet.id] = peeringPairList 
            # else:
            #     peeringPairList = sw.addPeerings(YAML, subscriptionId, vnet, revertInfo['peering'][vnet.id])

        # End of VNET iteration

        if args.revert == False:
            tf.storeRevertInfo(revertInfo)
        else:
            tf.deleteRevertInfo() 

        if args.s3backup:
            aws.uploadAllFiles('switch',accounts_data, target_location)

        if args.revert == True:
            aws.deleteBucketObj(accounts_data, target_location, 'terraform-import-associations.sh')
            aws.deleteBucketObj(accounts_data, target_location, 'tmp/revert.json')

