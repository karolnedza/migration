#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import argparse

import dm.logconf as logconf
from dm.arm.commonlib import Common as common
from dm.arm.lib.arm_utils import get_ad_sp_credential
from dm.aws import Aws as aws
from dm.aviatrix import Aviatrix as av
from azure.mgmt.network import NetworkManagementClient
from dm.arm.prestagelib import PreStage as ps
from dm.arm.discoverylib import DiscoveryLib as dl

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
if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='Associate subnet without UDR to a default route table with route propagation enable')
    args_parser.add_argument(
        '--s3_yaml_download', help='a list of comma separated strings in the form: <s3_account>,<s3_role>,<s3_bucket>,<spoke_account>')
    args_parser.add_argument(
        '--yaml_file', help='specify input <yaml_file>')
    args_parser.add_argument(
        '--revert', help='revert subnet to default route table association', action='store_true', default=False)
    args_parser.add_argument(
        '--dry_run', help='Dry run prestaging logic and show what will be done', action='store_true', default=False)
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
    common.logCommandOptions(f'dm.arm.prestage {iargs}')
    common.expectYamlType(accounts_data,'AZURE')

    if args.dry_run:
        ps.setDryRun()

    YAML = {
       'allow_vnet_cidrs': common.getAllowVpcCidr(accounts_data),
       'subscriptionMap': common.getAzurermSubscriptionInfo(accounts_data),
       'ctrl_private_ip': common.getControllerPrivateIp(accounts_data),
       'default_route_table': common.getPreStageDefaultRouteTable(accounts_data)
    }

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


        network_client = NetworkManagementClient(cred['credentials'], cred['subscription_id'])
        vnetsInYaml = {x['vnet_name']: x for x in account['vnets']}
        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)
        for vnet in vnets:
            if not vnet.name in vnetsInYaml:
                continue

            if dl.discoverSpokeGw(cred, vnet) == True:
                sys.exit(1)

            # - Re-associate subnets to route tables created in staging
            rtName = f'{vnet.name}-{YAML["default_route_table"]}'
            if args.revert == False:
                ps.createRouteTable(YAML,args.revert,cred,vnet,rtName)
                ps.updateSubnetAssociation(YAML, args.revert, cred, vnet, rtName)
            else:
                ps.updateSubnetAssociation(YAML, args.revert, cred, vnet, rtName)
                ps.createRouteTable(YAML,args.revert,cred,vnet,rtName)

