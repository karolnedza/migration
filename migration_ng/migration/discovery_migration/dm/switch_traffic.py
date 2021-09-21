#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import argparse
import getpass

from dm.commonlib import Common as common
from dm.aviatrix import Aviatrix as av
from dm.terraform import Terraform as tf
import dm.logconf as logconf
from dm.aws import Aws as aws
from dm.switchlib import SwitchTraffic as sw
import time

if __name__ == "__main__":
    # logging.config.fileConfig(fname='dm/log.conf')

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
    args_parser.add_argument(
        '--rm_static_route', help='remote static route to VPC attachment in tgw route table', action='store_true', default=False)
    args_parser.add_argument(
        '--rm_propagated_route', help='remote propagated route to VPC attachment in tgw route table', action='store_true', default=False)
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
    logconf = common.initLogLocation(accounts_data)
    logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO    
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.switch_traffic {iargs}')

    if args.dry_run:
        aws.setDryRun()
        tf.setDryRun()

    ctrl_user, ctrl_pwd = common.getCtrlCredential(args)

    ##
    target_folder = accounts_data['terraform']['terraform_output']
    api_ep_url = "https://" + \
        accounts_data['aviatrix']['controller_ip'] + "/v1/"
    CID = av.getCid(api_ep_url, ctrl_user, ctrl_pwd)

    YAML = {
       'allow_vpc_cidrs': common.getAllowVpcCidr(accounts_data),
       'tgwDeleteRouteDelay': common.getTgwDeleteRouteDelay(accounts_data)
    }
    GW_NAME_FORMAT = common.getGwNameFormat(accounts_data)
    
    vpcAid2GwNameMap = {}
    if GW_NAME_FORMAT == common.VPC_NAME:
        vpcAid2GwNameMap = tf.readJsonInfo("gw-name.json")

    spoke_gw_adv_cidr = None

    # Start iterating over the input yaml
    for account in accounts_data['account_info']:
        common.logAccountHeader(account)
        role_arn = common.get_role_arn(account)
        creds = common.get_temp_creds_for_account(role_arn)

        target_location = f"{target_folder}/{account['account_id']}"

        tf.setSwitchTrafficTargetFolder(target_location)

        # 1) if s3Bucket is used, download from S3 the terraform files
        if args.s3download:
            aws.downloadAllFiles(accounts_data, target_location)

        if args.revert == False:
            if tf.isRevertInfoExist():
                logger.warning(
                    f'**Alert** revert.json found for account {account["account_id"]}. Please revert first (switch_traffic --revert) before rerunning switch_traffic for this account.')
                continue
        else:
            if not tf.isRevertInfoExist():
                logger.warning(
                    f'**Alert** revert.json NOT found for account {account["account_id"]}, nothing to revert for this account.')
                continue

        if spoke_gw_adv_cidr == None:
            # read all spoke_gw once, since controller returns all gw(s) it managed for all
            # accounts
            spoke_gw_adv_cidr = av.get_spoke_gw_adv_cidr(api_endpoint_url=api_ep_url+"api", CID=CID)

        #
        # store revert info, e.g.:
        # {
        #   "vpcid-tf-size": {
        #     "/Users/<somepath>/tfoutput/115988878633/terraform-import-associations.sh": 139,
        #     "/Users/<somepath>/tfoutput/115988878633/aws-us-east-1-vpc-04de3d319307cc5e9.tf": 681
        #   },
        #   "static": {
        #     "205987878622-us-east-1-tgw-attach-0964a134061260f15": [
        #       "10.90.0.0/16"
        #     ]
        #   },
        #   "propagated": {
        #     "205987878622-us-east-1-vpc-04de3d319307cc5e9": [
        #       {
        #         "TransitGatewayRouteTableId": "tgw-rtb-030cfa359103b1679",
        #         "State": "enabled"
        #       }
        #     ]
        #   },
        #   "gw_adv_cidr": {
        #     "test-pc-115988878633-gw": [
        #       "10.90.0.0/16"
        #     ]
        #   }
        # }
        #
        revertInfo = {
            "vpcid-tf-size": {},
            "static": {},
            "propagated": {},
            "gw_adv_cidr": {}
        }

        tf.deleteSubnetAssociationTf()
        if args.revert == True:
            revertInfo = tf.readRevertInfo()
        else:
            # only delete the undo script at the begining of switch_traffic
            # so user can use it after --revert
            tf.deleteUndoSubnetAssociationTf()

        for regionObj in account['regions']:
            common.logRegionHeader(regionObj)
            ec2_resource = common.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client = ec2_resource.meta.client
            tgwInRegion = common.getTgwInGivenRegion(regionObj, accounts_data, account['account_id'])
            vpcs = ec2_resource.vpcs.all()

            # deduce provider alias for the current region
            regionAlias = regionObj['region']
            regionAlias = regionAlias.replace("-", "_")
            regionAlias = f'spoke_{regionAlias}'

            vpcsInRegionObj = common.getVpcsInRegion(regionObj)

            for vpc in vpcs:
                # If subset of VPCs specified
                if len(vpcsInRegionObj) > 0 and vpc.id not in vpcsInRegionObj:
                    continue
                vpcName = common.logVpcHeader(vpc)
                rtb_target_rtb_map = {}
                rtb_assocs_map = {}

                # 2) update switch_traffic attribute in vpc_id.tf file
                if args.revert == False:
                    tf.updateSwitchTraffic({
                        'vpc_id': vpc.id,
                        'region': regionObj['region'],
                        'switch_traffic': True
                    })
                    # record file size after substitution and
                    # make sure revert file first before subsitution when reverting
                    tf.storeFileSize(
                        f'aws-{regionObj["region"]}-{vpc.id}.tf', revertInfo)
                else:
                    tf.revertFile(
                        f'aws-{regionObj["region"]}-{vpc.id}.tf', revertInfo)
                    # revert substitution after reverting file
                    tf.updateSwitchTraffic({
                        'vpc_id': vpc.id,
                        'region': regionObj['region'],
                        'switch_traffic': False
                    })

                sw.discoverRouteTable(
                    args.revert, vpc, rtb_target_rtb_map, rtb_assocs_map)

                aws.updateSubnetAssociation(
                    args.revert, ec2_client, regionObj["region"], regionAlias, vpc.id, rtb_target_rtb_map, rtb_assocs_map)

                # 3) get gw_name
                if GW_NAME_FORMAT == common.VPC_NAME:
                    gw_name = sw.deduceGwName(
                        vpcAid2GwNameMap, vpc.id, vpcName, account['account_id'])
                else:
                    gw_name = sw.deduceGwNameWithSubnetCidr(regionObj["region"],vpcsInRegionObj[vpc.id]['avtx_cidr'])

                # 4) edit gw advertised cidr
                vpc_cidrs = []
                separator = ","                
                if args.revert == False:
                    # lookup the vpc cidrs
                    vpc_cidrs = sw.discoverVpcCidr(ec2_client, vpc, YAML)
                    avtx_cidr = common.getAvtxCidr(vpcsInRegionObj,vpc.id)
                    if avtx_cidr != "" and not avtx_cidr in vpc_cidrs:
                        vpc_cidrs.append(avtx_cidr)
                    if not gw_name in spoke_gw_adv_cidr:
                        logger.warning(f'  **Alert** {gw_name} not found in controller')
                    else:
                        org_vpc_cidrs = spoke_gw_adv_cidr[gw_name]
                        if len(org_vpc_cidrs) > 0:
                            revertInfo['gw_adv_cidr'][gw_name] = org_vpc_cidrs
                        vpc_cidrs_str = f"{separator.join(vpc_cidrs)}"
                        logger.info(
                            f'- Configure {gw_name} with advertized cidrs {vpc_cidrs_str}')
                        if not args.dry_run:
                            av.edit_gw_adv_cidr(
                                api_endpoint_url=api_ep_url+"api", CID=CID, gw_name=gw_name, cidrs=vpc_cidrs_str)
                else:
                    key = f"{account['account_id']}-{regionObj['region']}-{vpc.id}"
                    if any([ iKey.startswith(key) for iKey, iVal in revertInfo['static'].items() ]) == True:
                        ec2_client_diy = common.getDiyEc2Client(ec2_client, regionObj, accounts_data)
                        aws.mgmtTgwAttachmentStaticRoute(
                            args.revert, revertInfo["static"], key, ec2_client_diy, vpc, tgwInRegion)

                    if any([ iKey.startswith(key) for iKey, iVal in revertInfo['propagated'].items() ]) == True:
                        ec2_client_diy = common.getDiyEc2Client(ec2_client, regionObj, accounts_data)
                        aws.mgmtTgwAttachementPropagatedRoute(
                            args.revert, revertInfo["propagated"], key, ec2_client_diy, vpc, tgwInRegion)

                # Insert a delay, 5 sec by default
                logger.info(f'- sleep {YAML["tgwDeleteRouteDelay"]} sec')
                if not args.dry_run:
                    time.sleep(YAML['tgwDeleteRouteDelay'])

                if args.revert == False:
                    if args.rm_static_route == True or args.rm_propagated_route == True:
                        # check if VPC has any tgw attachment - reusing the same getTgwAttachementSubnets for this purpose.
                        # Empty subnet list implies no VPC attachment found.
                        vpcAttachmentSubnets = aws.getTgwAttachementSubnets(ec2_client, vpc, tgwInRegion)
                        if len(vpcAttachmentSubnets) > 0:
                            key = f"{account['account_id']}-{regionObj['region']}-{vpc.id}"
                            ec2_client_diy = common.getDiyEc2Client(ec2_client, regionObj, accounts_data)
                            if args.rm_static_route == True:                            
                                aws.mgmtTgwAttachmentStaticRoute(
                                    args.revert, revertInfo["static"], key, ec2_client_diy, vpc, tgwInRegion)
                            if args.rm_propagated_route == True:
                                aws.mgmtTgwAttachementPropagatedRoute(
                                    args.revert, revertInfo["propagated"], key, ec2_client_diy, vpc, tgwInRegion)
                else:
                    # lookup orginal cidr
                    if gw_name in revertInfo['gw_adv_cidr']:
                        vpc_cidrs = revertInfo['gw_adv_cidr'][gw_name]
                    vpc_cidrs_str = f"{separator.join(vpc_cidrs)}"
                    logger.info(
                        f'- Revert {gw_name} advertized cidrs to {vpc_cidrs_str}')
                    if args.dry_run:
                        continue
                    av.edit_gw_adv_cidr(
                        api_endpoint_url=api_ep_url+"api", CID=CID, gw_name=gw_name, cidrs=vpc_cidrs_str)

            # End of VPC iteration

            if args.revert == False:
                tf.storeRevertInfo(revertInfo)

        # End of region iteration

        if args.revert == True:
            tf.deleteRevertInfo()

        if args.s3backup:
            aws.uploadAllFiles('switch',accounts_data, target_location)

        if args.revert == True:
            aws.deleteBucketObj(accounts_data, target_location, 'terraform-import-associations.sh')
            aws.deleteBucketObj(accounts_data, target_location, 'tmp/revert.json')
