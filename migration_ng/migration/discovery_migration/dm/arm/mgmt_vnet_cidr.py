#!/usr/bin/python3

import logging
import logging.config
import argparse
import botocore
import dm.logconf as logconf
from dm.arm.commonlib import Common as common
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import VirtualNetworkPeering

from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.lib.arm_utils import get_ad_sp_credential, list_subscriptions
from dm.arm.switchlib import SwitchTraffic as sw
from dm.arm.terraform import Terraform as tf
from dm.arm.inf.VnetCidrMgmtInf import VnetCidrMgmtInf as vnetCidrMgmt
from dm.arm.imp.VnetCidrMgmtImp import ClusterVnetCidrMgmt
from dm.arm.imp.VnetCidrMgmtImp import MigrateVnetCidrMgmt

import sys
import os

#
# mgmt_vnet_cidr.py is helper script for adding cidr into vnet that might have peering.
#
# Problem: As of today (Aug 26, 2021), Azure does not allow cidr to be added to a vnet that has peering.
#
# Solution:
# For each vnet with cidr defined in yaml, this script will
# first 1) delete the peering and 2) add the cidr(s).
# This script will re-construct all the vnet peerings at the end.
#
# Usages:
# 1. To add cidrs specified in yaml: python -m dm.arm.mgmt_vnet_cidr cidr.yaml
# 2. To delete cidrs:  python -m dm.arm.mgmt_vnet_cidr cidr.yaml --delete
# 3. To add cidrs without restoring peering: python -m dm.arm.mgmt_vnet_cidr cidr.yaml --deletePeering
# 4. To delete cidrs without restoring peering: python -m dm.arm.mgmt_vnet_cidr cidr.yaml --delete --deletePeering
# 
# This script is capable of consuming a MGMT_VNET_CIDR yaml or a regular discovery AZURE yaml.
#
# MGMT_VNET_CIDR yaml can be used to describe all vnets that are inter-connected with peerings so
# cidrs can be added to the listed vnets in one shot while all the peerings are removed,
# avoiding multiple outages.  That is, not all vnets need to be in the next migration plan.
#
# The following example shows the structure of a MGMT_VNET_CIDR yaml file with 
# two different subscriptions.  The vnets attribute is an 
# object of multiple vnet_name to cidrs pairs.  Only one is shown in this case.
#
# MGMT_VNET_CIDR yaml example:
#
# label: "MGMT_VNET_CIDR"
# log_output: "/home/<userId>/migration/output"
# vnet_cidr:
#   - arm_subscription_id: "23241dsae-16d2-4d23-8635-1edd1289473ec9"
#     arm_directory_id: "ab46df99a-9006-4ee8-bffb-abcc616faed8e"
#     arm_application_id: "8de8519d-04cc-4e33-b435-79e9e478d8dd"
#     arm_application_secret_env: "ARM_CLIENT_SECRET"
#     vnets:
#       vn_firenet-test_VPC1-US-East: "12.1.1.0/24,14.1.1.0/24"
#   - arm_subscription_id: "23241dsae-16d2-4d23-8635-1edd1289473ec9"
#     arm_directory_id: "ab46df99a-9006-4ee8-bffb-abcc616faed8e"
#     arm_application_id: "8de8519d-04cc-4e33-b435-79e9e478d8dd"
#     arm_application_secret_env: "ARM_CLIENT_SECRET"
#     vnets:
#       vn_firenet-test_VPC2-US-East: "13.1.1.0/24"

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='add avtx_cidr to vnet')
    args_parser.add_argument(
        '--delete', help='remove given cidrs', action='store_true', default=False)
    args_parser.add_argument(
        '--deletePeering', help='do not restore peerings', action='store_true', default=False)
    args_parser.add_argument(
        '--dry_run', help='Dry run mgmt_vnet_cidr logic and show what will be done', action='store_true', default=False)
    args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    args = args_parser.parse_args()
    input_file = args.file_path
    if not os.path.isfile(input_file):
        print('YAML File does not exist')
        sys.exit()

    accounts_data = common.convert_yaml_to_json(input_file)
    yamlType = common.getLabel(accounts_data)
    vnetCidrMgmt = None
    if yamlType == None:
        print(f'**Alert** expecting MGMT_VNET_CIDR or AZURE type yaml')
        sys.exit(1)
    elif yamlType == 'MGMT_VNET_CIDR':
        vnetCidrMgmt = ClusterVnetCidrMgmt()
    elif yamlType == 'AZURE':
        vnetCidrMgmt = MigrateVnetCidrMgmt()
    else:
        print(f'**Alert** expecting MGMT_VNET_CIDR or AZURE type yaml')
        sys.exit(1)

    ## setup logging
    logconf = vnetCidrMgmt.intLogLocation(accounts_data)
    logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO    
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.arm.mgmt_vnet_cidr {iargs}')
    logFolder = common.getLogFolder(accounts_data)
    tf.setOutputBase(logFolder)
    if args.dry_run:
        sw.setDryRun()
        tf.setDryRun()
    
    YAML = {
       'subscriptionMap': common.getVnetCidrSubscriptionInfo(accounts_data)
    }

    vnetPeeringInfo = []

    for account in vnetCidrMgmt.getAccountList(accounts_data):
        # vnetsInYaml is a dict of vnetName and cidr string map
        # {
        #   vnetName1: "cidr1,cidr3",
        #   vnetName2: "cidr2",
        # }
        vnetsInYaml = common.getSubscriptionVnets(account)
        if len(vnetsInYaml) == 0:
            continue

        common.logSubscription(account['arm_subscription_id'])
        subscriptionId = account['arm_subscription_id']
        cred = common.getAzureSubscriptionCred(YAML, subscriptionId)

        network_client = NetworkManagementClient(cred['credentials'], subscriptionId)
        for vnetName, cidr in vnetsInYaml.items():
            # read vnet again since its peering might have been deleted
            vnet = dl.getVnet(vnetName, network_client)

            if vnet == None:
                logger.warning(f'**Alert** vnet {vnetName} not found')
                continue

            common.logVnetHeader(vnet)
            peeringInfo = sw.updateVnetCidr(args, cidr, YAML, vnet)
            if len(peeringInfo) > 0:
                vnetPeeringInfo.append(peeringInfo)
                
    tf.storeJsonInfo('peeringInfo.json', vnetPeeringInfo)
   
    # re-establish peerings
    if not args.deletePeering:
        if len(vnetPeeringInfo) > 0:
            logger.info("")
            logger.info("".ljust(45, "-"))
            logger.info("")
            logger.info(f"    Restore all peerings")
            logger.info("")
            logger.info("".ljust(45, "-"))
            logger.info("")

            for peeringInfo in vnetPeeringInfo:
                sw.addPeerings(YAML, peeringInfo)




