#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import argparse
import getpass
import json

from azure.mgmt import subscription
from dm.arm.terraform import Terraform as tf
from dm.arm.routetables import RouteTables as AvxRouteTables
import dm.logconf as logconf
from dm.arm.commonlib import Common as common
from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.lib.arm_utils import get_ad_sp_credential, list_subscriptions
from dm.arm.io import ArmIO as avxio
from dm.arm.subs import Subscriptions as AvxSubscriptions
from dm.arm.alert import Alert as alert
from azure.mgmt.network import NetworkManagementClient
from dm.aws import Aws as aws
import pdb

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='Get VPC info from account(s)')
    args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    args_parser.add_argument(
        '--s3backup', help='At the end of discovery, backup all generated files into S3', action='store_true', default=False)
    args_parser.add_argument(
        '--tfvars_json', help='Output route table in tfvars.json', action='store_true', default=False)
    args = args_parser.parse_args()
    input_file = args.file_path
    if not os.path.isfile(input_file):
        print('YAML File does not exist')
        sys.exit()

    ## setup logging
    accounts_data = common.convert_yaml_to_json(input_file)
    common.expectYamlType(accounts_data,'AZURE')

    logconf = common.initLogLocation(accounts_data)
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')
    
    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.arm.discovery {iargs}')
    
    ## create bucket if needed
    if aws.createBucketIfneeded(accounts_data) == False:
        sys.exit()

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
    ##
    target_folder = accounts_data['terraform']['terraform_output']
    YAML = {
        'subnet_tags' : common.getSubnetTags(accounts_data),
        'route_table_tags' : common.getRouteTableTags(accounts_data),
        'tfVersion': accounts_data['terraform']['terraform_version'],
        'avxProvider': accounts_data['terraform']['aviatrix_provider'],
        'awsProvider': accounts_data['terraform']['aws_provider'],
        'armProvider': accounts_data['terraform']['arm_provider'],
        'armAccountName': common.getArmAccountName(accounts_data),
        'subscriptionMap': common.getAzurermSubscriptionInfo(accounts_data),
        'default_route_table': common.getPreStageDefaultRouteTable(accounts_data)
    }

    alert.setupAlerts(accounts_data)

    tf.generateModuleFolder(target_folder)
    tf.generateModuleVersionsTf(target_folder, {
        'terraform_version': f'{YAML["tfVersion"]}',
        'aviatrix_provider': f'{YAML["avxProvider"]}',
        'aws_provider': f'{YAML["awsProvider"]}',
        'arm_provider': f'{YAML["armProvider"]}'
    })
    subsInYaml = [x['subscription_id'] for x in accounts_data['account_info']]
    allSubscriptions = AvxSubscriptions()
    for account in accounts_data['account_info']:
        if not account['subscription_id'] in subsInYaml:
            continue
        common.logSubscription(account['subscription_id'])
        subscriptionId = account['subscription_id']
        subscriptionInfo = YAML['subscriptionMap'][subscriptionId]
        arm_tenant_id = subscriptionInfo['dir_id']
        arm_client_id = subscriptionInfo['app_id']
        arm_client_secret =  os.getenv(subscriptionInfo['secret_env'])
        YAML['provider'] = subscriptionInfo['alias']
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
        tf.setupAccountFolder(target_location, accounts_data)
        tf.generateProviderTf(accounts_data)

        tf.generateVersionTf({
            'terraform_version': f'{YAML["tfVersion"]}',
            'aviatrix_provider': f'{YAML["avxProvider"]}',
            'aws_provider': f'{YAML["awsProvider"]}',
            'arm_provider': f'{YAML["armProvider"]}'
        })
        tf.copyYaml(f'{target_location}/tmp', input_file)
        tf.generateTfVars({
            'account_name': f'{YAML["armAccountName"]}',
            'controller_ip': accounts_data['aviatrix']['controller_ip']
        })

        tf.deleteTfImport()
        tf.deleteUndoSubnetsTfImport()

        dl.discover_route_table_without_subnet(cred,YAML)

        network_client = NetworkManagementClient(cred['credentials'], cred['subscription_id'])
        vnetsInYaml = {x['vnet_name']: x for x in account['vnets']}
        dl.list_vnet(cred,vnetsInYaml)
        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)
        for vnet in vnets:
            if not vnet.name in vnetsInYaml:
                continue
            
            if dl.discoverSpokeGw(cred, vnet) == True:
                sys.exit(1)

            dl.discoverVnet(vnet, cred)
            subnetsObj = dl.discoverSubnets(vnet, YAML)
            vnet2RTableMap = dl.discover_route_tables(cred,YAML,vnet)

            # dl.getAllNetworkInterface(account['subscription_id'],credential)
            rgName = vnet.id.split('/')[dl.RG_I]
            prefixLst = [f'"{x}"' for x in vnet.address_space.address_prefixes]
            prefixLst = ",".join(prefixLst)
            subId = account['subscription_id']
            
            var_route_tables = ''
            route_tables = {}
            if vnet.name in vnet2RTableMap:
                routeTables = vnet2RTableMap[vnet.name]
                if routeTables.getRouteTableCount() > 0:
                    var_route_tables = f'variable "route_tables_{vnet.name}" {{}}'
                    route_tables = f'var.route_tables_{vnet.name}'
            tags = {}
            if vnet.tags != None:
                tags = vnet.tags
            vnetTfData = {
                'account_name': f'{YAML["armAccountName"]}',
                'vnet_name': vnet.name,
                'vnet_cidr': f'[{prefixLst}]',
                'avtx_cidr': vnetsInYaml[vnet.name]['avtx_cidr'],
                'hpe': str(account['hpe']).lower(),
                'avtx_gw_size': account['spoke_gw_size'],
                'region': common.REGION[vnet.location],
                'resource_group': rgName,
                'var_route_tables': var_route_tables,
                'route_tables': route_tables,
                'use_azs': str(vnetsInYaml[vnet.name]['use_azs']).lower(),
                'provider': subscriptionInfo['alias'],
                'tags': tags
            }
            tf.generateVnetTf(vnetTfData)
            tf.generateVnetResourceTf(vnetTfData)

            # dl.addDefaultRouteTable(vnet, f'rt_default_1_{vnet.name}', YAML, vnet2RTableMap)
            # dl.addDefaultRouteTable(vnet, f'rt_default_2_{vnet.name}', YAML, vnet2RTableMap)

            # key = f'{rgName}_{vnet.name}'
            key = f'{vnet.name}'
            if key in vnet2RTableMap:
                tf.routeTablesToHcl(vnet.name, vnet2RTableMap[key])
            tf.subnetsToHcl(vnet.name, subnetsObj)
            tf.subnetsToTfImport(vnet, subnetsObj)
            tf.undoSubnetsToTfImport(vnet, subnetsObj)
            # { 
            #   subscription1: [ {vnet1: routeTables1} ],
            #   subscription2: [ {vnet2: routeTables2} ],            
            # }
            # allSubscriptions.add(account['subscription_id'],vnet.name,vnet2RTableMap[key])
        # END for vnet
        if args.s3backup:
            aws.uploadAllFiles('discovery',accounts_data, target_location)
    # END for account
    # avxio.storeJsonInfo(f"rt.json",allSubscriptions.toDict())
