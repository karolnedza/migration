#!/usr/bin/python3

import logging
import logging.config
import argparse
import botocore
import dm.logconf as logconf
from dm.commonlib import Common as common
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import VirtualNetworkPeering

from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.lib.arm_utils import get_ad_sp_credential, list_subscriptions

import sys
import os
import pdb

def getRemotePeering(cred, remotePeeringVnetId, localPeerId):
    localVnetIdList = localPeerId.split("/")
    localSubscriptionId = localVnetIdList[dl.SUB_I]
    localRgName = localVnetIdList[dl.RG_I]
    localVnetName = localVnetIdList[dl.VNET_I]
    localPeeringName = localVnetIdList[dl.PEER_I]
    
    print (f'- getRemotePeering:')
    print (f'  local subscription id: {localSubscriptionId}')
    print (f'  local resource group: {localRgName}')
    print (f'  local vnet name: {localVnetName}')
    print (f'  local peering name: {localPeeringName}')

    remoteVnetIdList = remotePeeringVnetId.split("/")
    remoteRgName = remoteVnetIdList[dl.RG_I]
    remoteVnetName = remoteVnetIdList[dl.VNET_I]
    remoteSubscriptionId = remoteVnetIdList[dl.SUB_I]
    print (f'  expected remote subscription id: {remoteSubscriptionId}')
    print (f'  expected remote resource group: {remoteRgName}')
    print (f'  expected remote vnet name: {remoteVnetName}')
    network_client = NetworkManagementClient(cred['credentials'], remoteSubscriptionId)
    peering_iter = network_client.virtual_network_peerings.list(remoteRgName, remoteVnetName)
    remotePeeringList = list(peering_iter)
    for peering in remotePeeringList:
        peeringRemoteVnetList = peering.remote_virtual_network.id.split("/")
        peeringRemoteRgName = peeringRemoteVnetList[dl.RG_I]
        peeringRemoteVnetName = peeringRemoteVnetList[dl.VNET_I]
        if peeringRemoteRgName == localRgName and peeringRemoteVnetName == localVnetName:
            print (f'  found remote peering name: {peering.name}')
            return remoteRgName, remoteVnetName, peering.name, peering
    print(f'  failed to found remote peering info')
    return None, None, None, None


if __name__ == "__main__":
    # logging.config.fileConfig(fname='log.conf')
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger("dm")

    args_parser = argparse.ArgumentParser(
        description='add avtx_cidr to vnet')

    args_parser.add_argument('subscriptionId', metavar='subscriptionId', type=str)
    args_parser.add_argument('vnetName', metavar='vnetName', type=str)
    args_parser.add_argument('cidr', metavar='cidr', type=str)
    args_parser.add_argument(
        '--delete', help='remote given cidr', action='store_true', default=False)      
    args = args_parser.parse_args()

    ## setup logging
    # accounts_data = common.convert_yaml_to_json(input_file)
    # logconf = common.initLogLocation(accounts_data)
    # logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO    
    # logging.config.dictConfig(logconf.logging_config)
    # logger = logging.getLogger('dm')

    subscription_id = os.getenv('ARM_SUBSCRIPTION_ID')
    arm_tenant_id = os.getenv('ARM_TENANT_ID')
    arm_client_id = os.getenv('ARM_CLIENT_ID')
    arm_client_secret = os.getenv('ARM_CLIENT_SECRET')

    at = dl.getAccessToken(arm_tenant_id, arm_client_id, arm_client_secret)
    credential = get_ad_sp_credential(arm_tenant_id, arm_client_id, arm_client_secret)
    if credential == None:
        logger.error(f'Failed to get Azure account credential from environment variables')
        sys.exit()

    cred = {
        'subscription_id': subscription_id,
        'credentials': credential,
        'accessToken': at
    }

    network_client = NetworkManagementClient(cred['credentials'], args.subscriptionId)
    vnet_iter = network_client.virtual_networks.list_all()
    vnets = list(vnet_iter)
    for vnet in vnets:
        if vnet.name == args.vnetName:
            print(f'- found {args.vnetName}')
            if args.delete == False and args.cidr in vnet.address_space.address_prefixes:
                print(f'  {args.cidr} already existed in {args.vnetName}')
                sys.exit(0)
            elif args.delete == True and not args.cidr in vnet.address_space.address_prefixes:
                print(f'  {args.cidr} not found in {args.vnetName}')
                sys.exit(0)
            rgName = vnet.id.split('/')[dl.RG_I]
            if len(vnet.virtual_network_peerings) > 0:
                peeringName = vnet.virtual_network_peerings[0].name
                peering = network_client.virtual_network_peerings.get(rgName, vnet.name, peeringName)
                remoteSubscriptionId = peering.remote_virtual_network.id.split('/')[dl.SUB_I]
                remote_network_client = NetworkManagementClient(cred['credentials'], remoteSubscriptionId)
                remoteRgName, remoteVnetName, remotePeeringName, remotePeering = getRemotePeering(cred,peering.remote_virtual_network.id, peering.id)

                # 1) delete peerings
                print(f'- delete peering {peeringName}')
                res = network_client.virtual_network_peerings.delete(rgName, vnet.name, peeringName).result()

                print(f'- delete peering {remotePeeringName}')
                res = remote_network_client.virtual_network_peerings.delete(remoteRgName, remoteVnetName, remotePeeringName).result()

                # 2) update vnet cidr
                if args.delete == True:
                    print(f'- remove cidr {args.cidr}')
                    vnet.address_space.address_prefixes.remove(args.cidr)
                else:
                    print(f'- add cidr {args.cidr}')
                    vnet.address_space.address_prefixes.append(args.cidr)
                res = network_client.virtual_networks.create_or_update(rgName,vnet.name,vnet).result()

                # 3) re-establish peerings
                print(f'- add peering {peeringName}')                
                res = network_client.virtual_network_peerings.create_or_update(rgName, vnet.name, peeringName, peering).result()

                print(f'- add peering {remotePeeringName}')
                res = remote_network_client.virtual_network_peerings.create_or_update(remoteRgName, remoteVnetName, remotePeeringName, remotePeering).result()
            else:
                if args.delete == True:
                    print(f'- remove cidr {args.cidr}')
                    vnet.address_space.address_prefixes.remove(args.cidr)
                else:
                    print(f'- add cidr {args.cidr}')
                    vnet.address_space.address_prefixes.append(args.cidr)
                res = network_client.virtual_networks.create_or_update(rgName,vnet.name,vnet).result()
            sys.exit(0)



