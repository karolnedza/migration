import logging
import ipaddress
from dm.arm.commonlib import Common as common
from dm.aws import Aws as aws
import dm.discoverylib
import re
from dm.arm.alert import Alert as alert
from dm.arm.terraform import Terraform as tf
import adal
import requests
from dm.arm.lib.arm_utils import _check_cred_id
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from dm.arm.routetable import RouteTable as AvxRouteTable
from dm.arm.route import Route as AvxRoute
from dm.arm.subnet import Subnet
from dm.arm.subnets import Subnets
from dm.aviatrix import Aviatrix as av
from dm.arm.routetables import RouteTables as AvxRouteTables
import azure.mgmt.resourcegraph as arg
from azure.identity import ClientSecretCredential

class DiscoveryLib(dm.discoverylib.DiscoveryLib):
    
    @classmethod
    def getResources(cls, strQuery, cred ):
        credentials = ClientSecretCredential(
            tenant_id=cred['arm_tenant_id'],
            client_id=cred['arm_client_id'],
            client_secret=cred['arm_client_secret']
        )
        argClient = arg.ResourceGraphClient(credentials)
        
        argQueryOptions = arg.models.QueryRequestOptions(result_format="objectArray")

        # Create query
        subsList = [ cred['subscription_id'] ]
        argQuery = arg.models.QueryRequest(subscriptions=subsList, query=strQuery, options=argQueryOptions)

        # Run query
        argResults = argClient.resources(argQuery)

        # Show Python object
        return argResults

    @classmethod
    def discoverSpokeGw(cls, cred, vnet):
        logger = logging.getLogger(__name__)
        logger.info(f'- check if {vnet.name} has been migrated')
        # 1) look for network interface in the vnet's resource group and subnet aviatrix-spoke-gw
        query_nic_template = "Resources | where type =~ 'Microsoft.Network/networkInterfaces' and tags contains 'Aviatrix-Created-Resource' | mvexpand ipconfig=properties.ipConfigurations | where ipconfig.properties.subnet.id =~ '/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Network/virtualNetworks/%s/subnets/%s'"
        resource_group = vnet.id.split('/')[cls.RG_I]
        query_str = query_nic_template % (cred['subscription_id'], resource_group, vnet.name, 'aviatrix-spoke-gw')
        res = cls.getResources(query_str, cred)
        if res.total_records == 0:
            logger.info(f'  no spoke gateway found')
            return False
        # 2) If found network interface, check if there is an Aviatrix-Created-Resource VM that used it.
        query_spoke_template = "Resources | where type =~ 'microsoft.compute/virtualMachines' and tags contains 'Aviatrix-Created-Resource' | mvexpand nics=properties.networkProfile | mvexpand nic=nics.networkInterfaces | where nic.id =~ '%s'"
        query_spoke_str = query_spoke_template % (res.data[0]['id'])
        res = cls.getResources(query_spoke_str, cred)
        if res.total_records == 0:
            logger.info(f'  no spoke gateway found')
            return False
        logger.warning(f'  **Alert** Vnet {vnet.name} already migrated, found an aviatrix gateway {res.data[0]["name"]}')
        return True

    SUB_I = 2
    RG_I = 4
    NSG_I = 8
    RT_I = 8
    PEER_I = -1
    VNET_I = 8
    SUBNET_I = 10

    @classmethod
    def discoverSubnets(cls, vnet, yamlObj):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover subnet: {len(vnet.subnets)} subnet(s)')

        subnetsObj = Subnets(vnet.name)
        for sn in vnet.subnets:
            rg = sn.id.split('/')[cls.RG_I]
            name = sn.name

            # Skip Azure special subnet
            if name == 'GatewaySubnet':
                logger.info(f'  Found Azure {name} ({rg}) -- skipped ')
                continue

            subObj = Subnet(sn)
            subObj.setProvider(yamlObj['provider'])
            subnetsObj.add(subObj)
            # logger.info(f'  {sn.address_prefix.ljust(25)} {name} ({rg})')
            logger.info(f'  {name} ({rg})')
            logger.info(f'    address_prefix: {sn.address_prefix}')
            if sn.network_security_group == None:
                logger.info(f'    network_security_group: None')
            else:
                id = sn.network_security_group.id.split("/")
                logger.info(f'    network_security_group: {id[cls.NSG_I]} ({id[cls.RG_I]})')

            if sn.route_table == None:
                logger.info(f'    route_table: None')
            else:
                id = sn.route_table.id.split("/")
                logger.info(f'    route_table: {id[cls.RT_I]} ({id[cls.RG_I]})')


            if len(sn.delegations) == 0:
                logger.info(f'    delegations: []')
            else:
                for d in sn.delegations:
                    logger.info(f'    delegation: {d.name}')

            if sn.service_endpoints == None:
                logger.info(f'    service_endpoints: None')
            else:
                for se in sn.service_endpoints:
                    logger.info(f'    service_endpoint: {se.service}')

        return subnetsObj

    @classmethod
    def getAllResourceGroup(cls, subscription_id, credentials):
        client = ResourceManagementClient(credentials, subscription_id)
        rg_iter = client.resource_groups.list()
        rgs = list(rg_iter)
        rgList = [ rg.name for rg in rgs ]
        return rgList

    @classmethod
    def getAllNetworkInterface(cls, subscription_id, credentials):
        '''
        Build effective routes per subnet
        '''
        logger = logging.getLogger(__name__)
        # 1) get all network interface and note down the interface name and resource group
        network_client = NetworkManagementClient(credentials, subscription_id)
        iter = network_client.network_interfaces.list_all()
        nics = list(iter)
        # 2) Deduce a vnet/subnet to nic map
        #    Pick the nic in a subent that has endpoint service
        # 3) This map can then be used later to print route table per subnet
        for nic in nics:
            nicName = nic.name
            rg = nic.id.split('/')[cls.RG_I]
            # 2) get effective route table for the given resource group and interface name
            logger.info(f'  route table: {nicName}')
            poller = network_client.network_interfaces.get_effective_route_table(rg, nicName)
            effectiveRouteTable = poller.result()
            for route in effectiveRouteTable.value:
                logger.info(f'    {route.source} {route.state} {route.address_prefix[0]} {route.next_hop_type} {route.next_hop_ip_address}')

        # 3) build vpc/subnet to interface map, provided the interface with an endpoint
        # 4) 
        # rg_iter = client.resource_groups.list()
        # rgs = list(rg_iter)
        # rgList = [ rg.name for rg in rgs ]
        # return rgList

    @classmethod
    def deduceVnet2VngMap(cls, subscription_id, credentials, rgList):
        '''
        Return vnet name to vngObj map
        1) For each resource group, list all Vng(s) in it
        2) For each Vng, deduce the vnet name from its subnet id
        :param rgList: list of resource group name
        :return: vnet name to vngObj map
        '''
        logger = logging.getLogger(__name__)
        if not _check_cred_id(subscription_id, credentials):
            return None

        vnet2VngMap = {}
        network_client = NetworkManagementClient(credentials, subscription_id)
        for rg in rgList:
            vng_iter = network_client.virtual_network_gateways.list(rg)
            vngs = list(vng_iter)
            for vng in vngs:
                for ipConfig in vng.ip_configurations:
                    vnetName = ipConfig.subnet.id.split('/')[cls.VNET_I]
                    vnet2VngMap[vnetName] = vng
        return vnet2VngMap

    @classmethod
    def list_vnet(cls, cred, vnetsInYaml):
        logger = logging.getLogger(__name__)
        subscription_id = cred['subscription_id']
        credentials = cred['credentials']
        # accessToken = cred['accessToken']

        if not _check_cred_id(subscription_id, credentials):
            return None

        network_client = NetworkManagementClient(credentials, subscription_id)

        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)

        logger.info(f'- Discover vnets: {len(vnets)} vnets')
        logger.info("  " + "".rjust(63, "."))
        logger.info("  " + "Vnet cidr".ljust(25) +
                    "Vnet name (rg)".ljust(25))
        logger.info("  " + "".rjust(63, "."))

        # rgList = cls.getAllResourceGroup(subscription_id, credentials)
        # vNet2VngMap = cls.deduceVnet2VngMap(subscription_id, credentials, rgList)

        for vnet in vnets:
            if not vnet.name in vnetsInYaml:
                continue
            # info = 'vnet_name: ' + vnet.name + \
            #        ' vnet_cidr: ' + vnet.address_space.address_prefixes[0]
            logger.info(
                f'  {vnet.address_space.address_prefixes[0].ljust(25)}{vnet.name}  ({vnet.id.split("/")[cls.RG_I]})')
            alert.alertVnetNameLength(vnet)
            

        # for vnet in vnets:
        #     if not vnet.name in vnetsInYaml:
        #         continue
        #     common.logVnetHeader(vnet)
        #     # list peering in vnet
        #     logger.info(f'- Discover peerings')
        #     if len(vnet.virtual_network_peerings) == 0:
        #         logger.info(f'  peerings: None')
        #     else:
        #         alert.alertVnetPeering(vnet)
        #         for peering in vnet.virtual_network_peerings:
        #             id = peering.id.split('/')
        #             peerId = peering.remote_virtual_network.id.split('/')
        #             logger.info(f'  {id[cls.PEER_I]} {peerId[cls.VNET_I]} ({peerId[cls.SUB_I]}/{peerId[cls.RG_I]})')

        #     # list vng in vnet
        #     logger.info(f'- Discover VNG')
        #     if vnet.name in vNet2VngMap:
        #         vngName = vNet2VngMap[vnet.name].name
        #         vngType = vNet2VngMap[vnet.name].gateway_type
        #         rg = vNet2VngMap[vnet.name].id.split('/')[cls.RG_I]
        #         logger.info(f'  {vngName} {vngType} ({rg})')
        #         # cls.getVngLearnedRoutes(cred,rg,vngName)
        #     else:
        #         logger.info(f'  VNG not found')

            # list subnet in vnet
            # cls.list_subnets(vnet)

    @classmethod
    def discoverVnet(cls, vnet, cred):
        logger = logging.getLogger(__name__)
        common.logVnetHeader(vnet)

        subscription_id = cred['subscription_id']
        credentials = cred['credentials']
        rgList = cls.getAllResourceGroup(subscription_id, credentials)
        vNet2VngMap = cls.deduceVnet2VngMap(subscription_id, credentials, rgList)
        # list peering in vnet
        logger.info(f'- Discover peerings')
        if len(vnet.virtual_network_peerings) == 0:
            logger.info(f'  peerings: None')
        else:
            alert.alertVnetPeering(vnet)
            for peering in vnet.virtual_network_peerings:
                id = peering.id.split('/')
                peerId = peering.remote_virtual_network.id.split('/')
                logger.info(f'  {id[cls.PEER_I]} {peerId[cls.VNET_I]} ({peerId[cls.SUB_I]}/{peerId[cls.RG_I]})')

        # list vng in vnet
        logger.info(f'- Discover VNG')
        if vnet.name in vNet2VngMap:
            vngName = vNet2VngMap[vnet.name].name
            vngType = vNet2VngMap[vnet.name].gateway_type
            rg = vNet2VngMap[vnet.name].id.split('/')[cls.RG_I]
            logger.info(f'  {vngName} {vngType} ({rg})')
            # cls.getVngLearnedRoutes(cred,rg,vngName)
        else:
            logger.info(f'  VNG not found')

    @classmethod
    def getVnet(cls, vnetName, network_client):
        vnets = network_client.virtual_networks.list_all()
        for vnet in vnets:
            if vnet.name == vnetName:
                return vnet
        return None

    @classmethod
    def isRouteTableUsedInVnet(cls,rt,vnet):
        if rt.subnets == None or len(rt.subnets) == 0:
            return False
        for sn in rt.subnets:
            idComponent = sn.id.split('/')
            rgName = idComponent[cls.RG_I]
            vnetName = idComponent[cls.VNET_I]
            if vnet.name == vnetName:
                return True
        return False

    @classmethod
    def discover_route_table_without_subnet(cls, cred, yamlObj):
        logger = logging.getLogger(__name__)
        subscription_id = cred['subscription_id']
        credentials = cred['credentials']
        # accessToken = cred['accessToken']
        if not _check_cred_id(subscription_id, credentials):
            return None

        logger.info(f'- Discover route table without subnet association')
        network_client = NetworkManagementClient(credentials, subscription_id)
        rt_iter = network_client.route_tables.list_all()
        rts = list(rt_iter)

        for rt in rts:
            if rt.subnets == None or len(rt.subnets) == 0:
                logger.warning(
                    f'  **Alert** {rt.location} {rt.name} has no subnet association')

    @classmethod
    def discover_route_tables(cls, cred, yamlObj, vnet=None):
        logger = logging.getLogger(__name__)
        subscription_id = cred['subscription_id']
        credentials = cred['credentials']
        # accessToken = cred['accessToken']
        if not _check_cred_id(subscription_id, credentials):
            return None

        network_client = NetworkManagementClient(credentials, subscription_id)
        rt_iter = network_client.route_tables.list_all()
        rts = list(rt_iter)

        common.logRouteTableHeader()
        logger.info(f'- Discover route table(s):')
        # logger.info(f'- Discover route table(s): {len(rts)} route tables')
        # logger.info("  " + "".rjust(63, "."))
        # logger.info("  " + "Region".ljust(25) +
        #             "Route table name".ljust(30))
        # logger.info("  " + "".rjust(63, "."))
        # for rt in rts:
        #     logger.info(f'  {rt.location.ljust(25)}{rt.name}')

        # vnet2RTableMap = {
        #   vnet.name : {
        #      rt1.id : rt1,
        #      rt2.id : rt2 
        #   }
        # }
        # 
        vnet2RTableMap = {}

        for rt in rts:
            if rt.subnets == None or len(rt.subnets) == 0:
                continue
            elif cls.isRouteTableUsedInVnet(rt,vnet) == False:
                continue            
            elif rt.name.startswith("org_") or rt.name.find("aviatrix") != -1:
                logger.info(f'  skip aviatrix created {rt.name}')
                continue
            elif yamlObj['default_route_table'] != None:
                rtName = f'{vnet.name}-{yamlObj["default_route_table"]}'
                if rt.name == rtName:
                    logger.info(f'  skip aviatrix created default {rt.name}')
                    continue

            logger.info(f'  route table: {rt.name}')
            rtable = AvxRouteTable(rt.name, rt.tags)
            rtable.setRegion(rt.location)
            rtable.setDisableBgpPropagation(rt.disable_bgp_route_propagation)
            rtable.addAdditonalTags(yamlObj['route_table_tags'])

            key = f'{vnet.name}'
            # key = f'{rgName}_{vnetName}'            
            if not key in vnet2RTableMap:
                vnet2RTableMap[key] = AvxRouteTables(key)
            if vnet2RTableMap[key].get(rt.id) == None:
                vnet2RTableMap[key].add(rtable)

            for sn in rt.subnets:
                # todo: add subnet assocations here as well?
                idComponent = sn.id.split('/')
                # rgName = idComponent[cls.RG_I]
                vnetName = idComponent[cls.VNET_I]
                snName = sn.id.split('/')[cls.SUBNET_I]
                if vnetName != vnet.name:
                    logger.warning(f'    **Alert** route table used by other vnet {vnetName} {snName}')
                else:
                    logger.info(f'    subnet: {vnetName}/{snName}')

            if len(rt.routes) == 0:
                logger.warning(f'    **Alert** empty UDR route table {rt.name}')
            else:
                logger.info(f'    route(s):')
                logger.info("    " + "".rjust(63, "."))
                logger.info("    " + "Prefix".ljust(25) +
                            "Next hop type".ljust(30) + "Next hop IP")
                logger.info("    " + "".rjust(63, "."))

                for route in rt.routes:
                    logger.info(
                        f'    {route.address_prefix.ljust(25)}{route.next_hop_type.ljust(30)}{route.next_hop_ip_address}')
                    routeObj = AvxRoute(route)
                    rtable.add(routeObj)

        # end for rt in rt
        return vnet2RTableMap

    @classmethod
    def addDefaultRouteTable(cls, vnet, rtName, yamlObj, vnet2RTableMap):
        # Generate a default route table for all subnets without route table association
        # todo: what will be the proper defaultRT id to use
        defaultRT = AvxRouteTable(rtName, {})
        defaultRT.addAdditonalTags(yamlObj['route_table_tags'])
        rg = vnet.id.split("/")[cls.RG_I]
        defaultRT.setRegion(vnet.location)
        defaultRT.setDisableBgpPropagation(True)
        key = f'{vnet.name}'
        if not key in vnet2RTableMap:
            vnet2RTableMap[key] = AvxRouteTables(vnet.name)
        vnet2RTableMap[key].add(defaultRT)

    API_VERSION = '2020-11-01'
    @classmethod
    def getSubscriptions(cls,accessToken):
        logger = logging.getLogger(__name__)
        endpoint = 'https://management.azure.com/subscriptions/?api-version=2015-01-01'
        headers = {"Authorization": 'Bearer ' + accessToken}
        json_output = requests.get(endpoint,headers=headers).json()
        for sub in json_output["value"]:
            logger.info(f'{sub["displayName"]}:{sub["subscriptionId"]}')

    @classmethod
    def getVngLearnedRoutes(cls,cred,rgName,vngName):
        logger = logging.getLogger(__name__)
        endpoint = f'https://management.azure.com/subscriptions/{cred["subscription_id"]}/resourceGroups/{rgName}/providers/Microsoft.Network/virtualNetworkGateways/{vngName}/getLearnedRoutes?api-version={cls.API_VERSION}'
        headers = {"Authorization": 'Bearer ' + cred['accessToken']}
        json_output = requests.post(endpoint,headers=headers).json()


    @classmethod
    def getAccessToken(cls,tenant_id,application_id,application_secret):
        logger = logging.getLogger(__name__)
        authentication_endpoint = 'https://login.microsoftonline.com/'
        resource  = 'https://management.core.windows.net/'

        # get an Azure access token using the adal library
        try:
            context = adal.AuthenticationContext(authentication_endpoint + tenant_id)
            token_response = context.acquire_token_with_client_credentials(resource, application_id, application_secret)
            access_token = token_response.get('accessToken')
        except Exception as e:
            logger.error(f'{e}')
            return None
        return access_token
        