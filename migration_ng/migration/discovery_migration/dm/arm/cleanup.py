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
from dm.aws import Aws as aws
from azure.mgmt.network import NetworkManagementClient
from dm.arm.switchlib import SwitchTraffic as sw
from dm.arm.cleanuplib import CleanUp as cu

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='Delete origin UDRs, and Peerings')
    # args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    args_parser.add_argument(
        '--s3_yaml_download', help='a list of comma separated strings in the form: <s3_account>,<s3_role>,<s3_bucket>,<spoke_account>')
    args_parser.add_argument(
        '--yaml_file', help='specify input <yaml_file>')
    args_parser.add_argument(
        '--dry_run', help='Dry run cleanup logic and show what will be done', action='store_true', default=False)
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
    common.logCommandOptions(f'dm.arm.cleanup {iargs}')

    if 'cleanup' not in accounts_data:
        logger.error('Cleanup section in YAML File does not exist')
        sys.exit()

    if args.dry_run:
        cu.setDryRun()
        sw.setDryRun()
        tf.setDryRun()
        aws.setDryRun()

    ##
    target_folder = accounts_data['terraform']['terraform_output']

    YAML = {
       'allow_vnet_cidrs': common.getAllowVpcCidr(accounts_data),
       'subscriptionMap': common.getAzurermSubscriptionInfo(accounts_data),
       'ctrl_private_ip': common.getControllerPrivateIp(accounts_data),
       'default_route_table': common.getPreStageDefaultRouteTable(accounts_data),
       'cleanup_resources': common.getCleanupResources(accounts_data)
    }

    subsInYaml = [x['subscription_id'] for x in accounts_data['account_info']]
    for account in accounts_data['account_info']:
        if not account['subscription_id'] in subsInYaml:
            continue
        common.logSubscription(account['subscription_id'])

        target_location = f"{target_folder}/{account['subscription_id']}"
        tf.setSwitchTrafficTargetFolder(target_location)

        # 1) Delete revert.json
        if not tf.isRevertInfoExist():
            logger.warning(
                f'**Alert** revert.json NOT found for account {account["subscription_id"]}')
        else:
            tf.deleteRevertInfo() 
            aws.deleteBucketObj(accounts_data, target_location, 'tmp/revert.json')

        # Deduce cred for spoke account (subscription_id)
        subscriptionId = account['subscription_id']
        subscriptionInfo = YAML['subscriptionMap'][subscriptionId]

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
        }

        network_client = NetworkManagementClient(cred['credentials'], cred['subscription_id'])
        vnetsInYaml = {x['vnet_name']: x for x in account['vnets']}
        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)
        for vnet in vnets:
            if not vnet.name in vnetsInYaml:
                continue

            # 2) Delete UDR with previous subnet association
            rtb_target_rtb_map = {}
            cu.lookupOrgRouteTable(cred, vnet, rtb_target_rtb_map)
            logger.info(f'- Delete original route tables')
            rgName = vnet.id.split('/')[dl.RG_I]
            for rtbName in rtb_target_rtb_map.keys():
                cu.deleteRouteTable(network_client, rgName, rtbName)

            # 3) Delete UDR without any subnet association
            # Do we need to do this ??

            # 4) Delete default route table creating at pre-staging.
            if YAML['default_route_table'] != None:
                rtbName = f'{vnet.name}-{YAML["default_route_table"]}'
                cu.deleteRouteTable(network_client, rgName, rtbName)

            # 5) delete peering
            if YAML['cleanup_resources'] == None or \
                (YAML['cleanup_resources'] != None and 'PEERING' in YAML['cleanup_resources']):
                # Do not delete the native peering (av-peer) created by our controller between
                # transit and spoke in HPE mode
                peeringPairList = sw.deletePeerings(YAML, subscriptionId, vnet, network_client, exclude='av-peer-')

        # End of VNET iteration
