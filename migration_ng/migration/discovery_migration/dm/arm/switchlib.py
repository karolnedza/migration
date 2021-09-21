import logging
import ipaddress
from azure.mgmt.network import NetworkManagementClient
from dm.arm.lib.arm_utils import _check_cred_id
from dm.arm.terraform import Terraform as tf
from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.commonlib import Common as common
import azure.mgmt.resourcegraph as arg
from azure.identity import ClientSecretCredential

class SwitchTraffic:

    DryRun = False

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def isExpectedVpcPrefix(self,ip,prefixes):
        ipn = ipaddress.ip_network(ip)
        for n in prefixes:
            if ipn.subnet_of(n):
                return True
        return False

    @classmethod
    def discoverVpcCidr(cls,vnet,yaml):
        logger = logging.getLogger(__name__)
        allowVnetCidr = yaml['allow_vnet_cidrs']

        vnetCidrs = []
        # retain vnet Cidrs that are within allow_vnet_cidrs list
        for x in vnet.address_space.address_prefixes:
            if cls.isExpectedVpcPrefix(x,allowVnetCidr):
                vnetCidrs.append(x)
        return vnetCidrs

    @classmethod
    def discoverSubnetAssociation(cls,rtb,assocs):
        if rtb.subnets == None:
            return
        for subnet in rtb.subnets:
            try:
                assocs.append(subnet)
            except KeyError:
                pass

    @classmethod
    def getAzureNetworkManagmentClient(cls, cred):
        logger = logging.getLogger(__name__)
    
        subscription_id = cred['subscription_id']
        credentials = cred['credentials']
        # accessToken = cred['accessToken']
        if not _check_cred_id(subscription_id, credentials):
            logger.error(f'**Error** failed to create NetworkManagementClient')
            return None

        network_client = NetworkManagementClient(credentials, subscription_id)
        return network_client

    @classmethod
    def discoverRouteTable(cls,cred,revert,vnet,rtb_target_rtb_map):
        logger = logging.getLogger(__name__)
        network_client = cls.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        rt_iter = network_client.route_tables.list_all()
        rts = list(rt_iter)

        # Build rtbMap - rtb name to rtb object map
        rtbMap = { rtb.name: rtb for rtb in rts }

        stagedUdrLst = []
        for rtb in rts:
            # all route tables within the same subscription will be seen
            # only consider the ones in the given vnet.
            if rtb.tags == None:
                continue

            # check if it is a new table by checking if there is an Org_rt tag
            tags = [value for key, value in rtb.tags.items() if key == 'Org_RT']
            # rtb is the new route table created in staging if it has an Org_RT tag
            if (len(tags) > 0):
                orgRouteTableIdStr = tags[0]
                orgRouteTableId = ""
                if orgRouteTableIdStr.startswith("org_"):
                    orgRouteTableId = orgRouteTableIdStr[4:]

                    # 1) current rtb is new rtb created by staging.
                    # 2) For switch_traffic, lookup subnets association in original rtb.
                    # 3) rtb_target_rtb_map stores: original rtb id => new rtb id
                    if revert == False:
                        # given org_<rtb.name> is not yet associated with a subnet.
                        # <rtb.name> is associated with a subnet
                        # check if <rtb.name> is in this vnet
                        if dl.isRouteTableUsedInVnet(rtbMap[orgRouteTableId],vnet) == False:
                            continue
                        rtb_target_rtb_map[orgRouteTableId] = rtb.name
                        rg = rtb.id.split('/')[dl.RG_I]
                        stagedUdrLst.append(f'{rtb.name}:{rg}')
                    # 1) current rtb is new rtb created by staging.
                    # 2) For switch_traffic --revert, lookup subnet association in new rtb
                    # 3) rtb_target_rtb_map stores: new rtb id => original rtb id
                    else:
                        # for revert, org_<rtb.name> is associated with a subnet
                        # check if org_<rtb.nam> is in this vnet.
                        if dl.isRouteTableUsedInVnet(rtb,vnet) == False:
                            continue
                        rtb_target_rtb_map[rtb.name] = orgRouteTableId
                        rg = rtb.id.split('/')[dl.RG_I]
                        stagedUdrLst.append(f'{rtb.name}:{rg}')                        
                else:
                    logger.warning(f'  **Alert** cannot find org_<routeTableId> in the Org_RT tag of new route table {rtb.id}')

        return stagedUdrLst
        # End of RTB iteration

    @classmethod
    def disassociateSubnetFromControllerRT(cls, yaml, cred, vnet):
        """Workaround for AVX-13563:
        Disassociate subnet from controller created route table '<vnetId>---<controller-private-ip>-public'
        by setting subnet association to None.
        """
        logger = logging.getLogger(__name__)

        rgName = vnet.id.split('/')[dl.RG_I]
        network_client = cls.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        # Workaround for AVX-13563:
        # - compose controller created route table name '<vnetId>---<controller-private-ip>-public'
        controller_created_rt = None
        if yaml['ctrl_private_ip'] != None:
            cpipStr = yaml['ctrl_private_ip'].replace('.','-')
            controller_created_rt_name = f'{vnet.name}---{cpipStr}-public'
            try:
                controller_created_rt = network_client.route_tables.get(rgName,controller_created_rt_name)
            except Exception as e:
                logger.info(f'  **Alert** {controller_created_rt_name} not found')
                logger.debug(f'  **Alert** {e}')
                return

        subnets_iter = network_client.subnets.list(rgName,vnet.name)
        subnets = list(subnets_iter)
        for subnet in subnets:
            # skip Netapp delegated subnet because route table cannot be reassociated for this type of subnet
            if any([ delegation.service_name == 'Microsoft.Netapp/volumes' for delegation in subnet.delegations]) == True:
                logger.info(f'- {subnet.name} delegated to Microsoft.Netapp/volumes -- skipped')
                continue

            # For subnet associated to controller created default route table
            # associate subnet to None
            if subnet.route_table != None and subnet.route_table.id.split('/')[-1] == controller_created_rt_name:
                newRtbObj = None
                logger.info(f'  Associate {subnet.name} to None')
            else:
                continue

            subnet.route_table = newRtbObj

            if cls.DryRun:
                continue

            poller = network_client.subnets.create_or_update(rgName,vnet.name,subnet.name,subnet)
            response = poller.result()

    @classmethod
    def updateSubnetAssociation(cls, yaml, revert, cred, vnet, rtb_target_rtb_map):
        logger = logging.getLogger(__name__)

        rgName = vnet.id.split('/')[dl.RG_I]
        network_client = cls.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        logger.info(f'- Switch subnet to route-table association')
        subnets_iter = network_client.subnets.list(rgName,vnet.name)
        subnets = list(subnets_iter)
        num = 0

        # controller_created_rt = None
        # if revert == False:
        #     # Workaround for AVX-13563:
        #     # - find default route table with name '<vnetId>---<controller-private-ip>-public'
        #     if yaml['ctrl_private_ip'] != None:
        #         cpipStr = yaml['ctrl_private_ip'].replace('.','-')
        #         controller_created_rt_name = f'{vnet.name}---{cpipStr}-public'
        #         try:
        #             controller_created_rt = network_client.route_tables.get(rgName,controller_created_rt_name)
        #         except Exception as e:
        #             logger.info(f'**Alert** {controller_created_rt_name} not found')
        #             logger.debug(f'**Alert** {e}')

        defaultRtbName = None
        if yaml["default_route_table"] != None:
            defaultRtbName = f'{vnet.name}-{yaml["default_route_table"]}'
            try:
                defaultRtbObj = network_client.route_tables.get(rgName, defaultRtbName)
            except Exception as e:
                logger.info(f'  **Alert** {defaultRtbName} not found')
                logger.debug(f'  **Alert** {e}')
        
        subscriptionId = yaml['subscriptionId']
        subscriptionInfo = yaml['subscriptionMap'][subscriptionId]

        for subnet in subnets:
            # Skip Azure special subnet
            if subnet.name == 'GatewaySubnet':
                logger.info(f'  found Azure {subnet.name} -- skipped ')
                continue
            # skip Netapp delegated subnet because route table cannot be reassociated for this type of subnet
            if any([ delegation.service_name == 'Microsoft.Netapp/volumes' for delegation in subnet.delegations]) == True:
                logger.info(f'  {subnet.name} delegated to Microsoft.Netapp/volumes -- skipped')
                continue
            # 1) For subnet without UDR route table initially,
            # associate subnet to default UDR route table in a round robin fashion
            if revert == False:
                if subnet.route_table == None or \
                    (defaultRtbName != None and subnet.route_table.id.split('/')[-1] == defaultRtbName):                    
                    # (controller_created_rt != None and subnet.route_table.id.split('/')[-1] == controller_created_rt_name) or \
                    newRtbName = f'{vnet.name}-main-{(num % 2)+1}'
                    num = num + 1
                    newRtbObj = network_client.route_tables.get(rgName,newRtbName)
                    logger.info(f'  associate {subnet.name} to {newRtbName}')
                    resourceName = f'{vnet.name}_{subnet.name}_{newRtbObj.name}'.replace('.','_')
                    tf.createSubnetAssociationTf({
                        'vnet_name': vnet.name,
                        'subnet_id': subnet.id,
                        'route_table_id': newRtbObj.id,
                        'rname': f'{resourceName}',
                        'provider': subscriptionInfo['alias']
                    })
                else:
                    # this is aviatrix created spoke subnet, named aviatrix-spoke-gw and aviatrix-spoke-hagw
                    if subnet.name.find("aviatrix-spoke") != -1:
                        logger.info(f'  spoke gw subnet {subnet.name} -- skipped')
                        continue

                    # switch UDR to UDR route table & generate resource for import
                    rtbName = subnet.route_table.id.split('/')[-1]
                    if not rtbName in rtb_target_rtb_map:
                        logger.warning(f'  **Alert** {subnet.name} associated to {rtbName} not copied -- skipped')
                        continue
                    newRtbName = rtb_target_rtb_map[rtbName]
                    newRtbObj = network_client.route_tables.get(rgName,newRtbName)
                    logger.info(f'  switch {subnet.name} from {rtbName} to {newRtbName}')

                    resourceName = f'{vnet.name}_{subnet.name}_{newRtbObj.name}'.replace('.','_')                         
                    tf.createSubnetAssociationTf({
                        'vnet_name': vnet.name,
                        'subnet_id': subnet.id,
                        'route_table_id': newRtbObj.id,
                        'rname': f'{resourceName}',
                        'provider': subscriptionInfo['alias']
                    })
            # revert traffic
            else:
                # Some subnets without route table in revert traffic.
                # This is not possible for revert traffic. 
                if subnet.route_table == None:
                    logger.warning(f'  **Alert** Subnet {subnet.name} without route table detected during revert traffic -- skipped')
                    continue

                # this is aviatrix created spoke subnet, named aviatrix-spoke-gw and aviatrix-spoke-hagw
                if subnet.name.find("aviatrix-spoke") != -1:
                    logger.info(f'  spoke gw subnet {subnet.name} -- skipped')
                    continue

                rtbName = subnet.route_table.id.split('/')[-1]
                # revert traffic, unassociate subnet from the <vnetName>-main-1 and <vnetName>-main-2 route tables we created in staging
                # set subnet association to None, no need to go back to controller created rt (e.g., vnetId---10-240-68-141-public)
                if rtbName.startswith(f'{vnet.name}-main-'):
                    if defaultRtbName != None:
                        newRtbObj = defaultRtbObj
                        logger.info(f'  re-associate {subnet.name} from {rtbName} to {defaultRtbName}')
                    else:
                        newRtbObj = None
                        logger.info(f'  re-associate {subnet.name} from {rtbName} to None')
                elif not rtbName in rtb_target_rtb_map:
                    logger.warning(f'  **Alert** {subnet.name} is using a route table {rtbName} that has not been copied -- skipped')
                    continue
                else:
                    # switch UDR to UDR route table
                    newRtbName = rtb_target_rtb_map[rtbName]
                    newRtbObj = network_client.route_tables.get(rgName,newRtbName)
                    logger.info(f'  switch {subnet.name} from {rtbName} to {newRtbName}')

            subnet.route_table = newRtbObj

            if cls.DryRun:
                continue

            poller = network_client.subnets.create_or_update(rgName,vnet.name,subnet.name,subnet)
            response = poller.result()

    @classmethod
    def disableAllRouteTablePropagationInVnet(cls, network_client, revert, vnet, rtb_target_rtb_map):
        logger = logging.getLogger(__name__)
        logger.info(f'- Disable propagate-gateway-route in UDR route table')
        route_table_prop = []
        # Disable propagation on the two default created in staging
        for rtbName in [f'{vnet.name}-main-1', f'{vnet.name}-main-2']:
            rtProp = cls.disableRouteTablePropagation(network_client,vnet,rtbName)
            if rtProp != None:
                route_table_prop.append(rtProp)

        # Disable propagation on other UDR route tables copied
        for key in rtb_target_rtb_map:
            rtProp = cls.disableRouteTablePropagation(network_client,vnet,rtb_target_rtb_map[key])
            if rtProp != None:
                route_table_prop.append(rtProp)

        return route_table_prop

    @classmethod
    def disableRouteTablePropagation(cls, network_client, vnet, rtbName):
        logger = logging.getLogger(__name__)
        rgName = vnet.id.split('/')[dl.RG_I]        
        try:
            rtbObj = network_client.route_tables.get(rgName, rtbName)
            if rtbObj.disable_bgp_route_propagation == False:
                rtbObj.disable_bgp_route_propagation = True
                logger.info(f'  disable propagate-gateway-route in {rtbName}')
                if not cls.DryRun:
                    res = network_client.route_tables.create_or_update(rgName, rtbName, rtbObj)
                return {
                    'vnet': vnet.name,
                    'resource_group': rgName,
                    'route_table_name': rtbName,
                    'disable_bgp_route_propagation': False
                }
        except Exception as e:
            logger.info(f'  **Alert** {rtbName} not found')
            logger.debug(f'  **Alert** {e}')
        return None

    @classmethod
    def restoreRouteTablePropagationInVnet(cls, network_client, rtbPropList):
        logger = logging.getLogger(__name__)
        logger.info(f'- Restore propagate-gateway-route in UDR route table')
        for prop in rtbPropList:
            rgName = prop['resource_group']
            rtbName = prop['route_table_name']
            try:
                rtbObj = network_client.route_tables.get(rgName, rtbName)
                rtbObj.disable_bgp_route_propagation = False
                logger.info(f'  enable propagate-gateway-route in {rtbName}')
                if not cls.DryRun:                
                    res = network_client.route_tables.create_or_update(rgName, rtbName, rtbObj)
            except Exception as e:
                logger.info(f'  **Alert** {rtbName} not found')
                logger.debug(f'  **Alert** {e}')

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

    VPN = 'Vpn'
    ER = 'ExpressRoute'

    @classmethod
    def isVnetWithVng(cls, cred, vnet, vngType):
        logger = logging.getLogger(__name__)
        #
        # assumption: vnet and VNG are in the same resource group
        #
        rgName = vnet.id.split('/')[dl.RG_I]
        gs = f'{vnet.id}/subnets/GatewaySubnet'
        query_vng_template = "Resources | where type =~ 'Microsoft.Network/virtualNetworkGateways' | mvexpand nics=properties.networkProfile | mvexpand ipconfig=properties.ipConfigurations | where ipconfig.properties.subnet.id =~ '%s' | project properties.gatewayType"
        query_vng_str = query_vng_template % gs
        res = cls.getResources(query_vng_str, cred)

        if res.total_records == 0:
            logger.info(f'- vnet {vnet.name} has no VNG')
            return False
        
        for rec in res.data:
            if 'properties_gatewayType' in rec and rec['properties_gatewayType'] == vngType:
                logger.info(f'- vnet {vnet.name} has VNG - {vntType}')
                return True

        logger.info(f'- vnet {vnet.name} has VNG but NOT type {vntType}')
        return False
        # vngs = network_vnet.virtual_network_gateways.list(rgName)
        # for vng in vngs:
        #     pass
        #     ## vng.ip_configurations[0].subnet
        #     ## Microsoft.Network/virtualNetworkGateways



    @classmethod
    def deduceGwName(cls,vpcAid2GwNameMap,vpcId,vpcName,accountId):
        # Deduce the spoke gw_name for advertising the customized cidrs
        gw_name_suffix = ""
        vpcAid = f'{vpcId}-{accountId}'
        if vpcAid in vpcAid2GwNameMap:
            return vpcAid2GwNameMap[vpcAid]
        else:
            return f"{vpcName}-{accountId}-gw"

    region = {
        'eastus'        : 'use',
        'centralus'     : 'usc',
        'westus'        : 'usw',
        'westus2'       : 'usw2',
        'northeurope'   : 'eun',
        'westeurope'    : 'euw',
        'southeastasia' : 'asse',
        'japaneast'     : 'jae',
        'chinaeast2'    : 'che2',
        'chinanorth2'   : 'chn2'
    }

    @classmethod
    def deduceGwNameWithSubnetCidr(cls,regionId,cidr):
        # Deduce the spoke gw_name for advertising the customized cidrs
        ip = cidr.split('/')[0]
        octal = ip.split('.')
        gw_name = f'azu-{cls.region[regionId]}-{int(octal[0]):02x}{int(octal[1]):02x}{int(octal[2]):02x}{int(octal[3]):02x}-gw'
        return gw_name

    @classmethod
    def deduceTransitNameWithRegion(cls,regionId):
        # Deduce the spoke gw_name for advertising the customized cidrs
        gw_name = f'azu-{cls.region[regionId]}-transit-gw'
        return gw_name

    @classmethod
    def getRemotePeering(cls, cred, remotePeeringVnetId, localPeerId):
        logger = logging.getLogger(__name__)

        localVnetIdList = localPeerId.split("/")
        localSubscriptionId = localVnetIdList[dl.SUB_I]
        localRgName = localVnetIdList[dl.RG_I]
        localVnetName = localVnetIdList[dl.VNET_I]
        localPeeringName = localVnetIdList[dl.PEER_I]
        
        logger.debug (f'  local subscription id: {localSubscriptionId}')
        logger.debug (f'  local resource group: {localRgName}')
        logger.debug (f'  local vnet name: {localVnetName}')
        logger.info (f'  local peering name: {localPeeringName}')

        remoteVnetIdList = remotePeeringVnetId.split("/")
        remoteRgName = remoteVnetIdList[dl.RG_I]
        remoteVnetName = remoteVnetIdList[dl.VNET_I]
        remoteSubscriptionId = remoteVnetIdList[dl.SUB_I]
        logger.debug (f'  expected remote subscription id: {remoteSubscriptionId}')
        logger.debug (f'  expected remote resource group: {remoteRgName}')
        logger.debug (f'  expected remote vnet name: {remoteVnetName}')
        network_client = NetworkManagementClient(cred['credentials'], remoteSubscriptionId)
        peering_iter = network_client.virtual_network_peerings.list(remoteRgName, remoteVnetName)
        remotePeeringList = list(peering_iter)
        for peering in remotePeeringList:
            peeringRemoteVnetList = peering.remote_virtual_network.id.split("/")
            peeringRemoteRgName = peeringRemoteVnetList[dl.RG_I]
            peeringRemoteVnetName = peeringRemoteVnetList[dl.VNET_I]
            if peeringRemoteRgName == localRgName and peeringRemoteVnetName == localVnetName:
                logger.info (f'  remote peering name: {peering.name}')
                return remoteRgName, remoteVnetName, peering.name, peering
        logger.info(f'  failed to found remote peering info')
        return None, None, None, None

    @classmethod
    def deletePeerings(cls, YAML, subscriptionId, vnet, local_network_client=None, exclude=None):
        logger = logging.getLogger(__name__)

        if local_network_client == None:
            cred = common.getAzureSubscriptionCred(YAML,subscriptionId)
            local_network_client = NetworkManagementClient(cred['credentials'], subscriptionId)
        peeringPairList = []
        rgName = vnet.id.split('/')[dl.RG_I]
        logger.info(f'- Delete peerings')
        if len(vnet.virtual_network_peerings) == 0:
            logger.info(f'  No peering found')
            return peeringPairList
        for peeringObj in vnet.virtual_network_peerings:
            peeringName = peeringObj.name
            if exclude != None and peeringName.startswith(exclude):
                logger.info(f'  controller created peering {peeringName} -- skipped')
                continue
            try:
                peering = local_network_client.virtual_network_peerings.get(rgName, vnet.name, peeringName)
                remoteSubscriptionId = peering.remote_virtual_network.id.split('/')[dl.SUB_I]                
                cred = common.getAzureSubscriptionCred(YAML,remoteSubscriptionId)
                if cred == None:
                    logger.warning(f'  **Alert** Cannot delete peering. Missing credential for remote subscription {remoteSubscriptionId}')
                    continue

                remote_network_client = NetworkManagementClient(cred['credentials'], remoteSubscriptionId)
                remoteRgName, remoteVnetName, remotePeeringName, remotePeering = cls.getRemotePeering(cred,peering.remote_virtual_network.id, peering.id)
                peeringProperties = {
                    "id": peering.id,
                    "name": peering.name,
                    "allow_virtual_network_access": peering.allow_virtual_network_access,
                    "allow_forwarded_traffic": peering.allow_forwarded_traffic,
                    "allow_gateway_transit": peering.allow_gateway_transit,
                    "use_remote_gateways": peering.use_remote_gateways,
                    "remote_virtual_network": {
                        "id": peering.remote_virtual_network.id
                    }

                }
                remotePeeringProperties = {
                    "id": remotePeering.id,
                    "name": remotePeering.name,
                    "allow_virtual_network_access": remotePeering.allow_virtual_network_access,
                    "allow_forwarded_traffic": remotePeering.allow_forwarded_traffic,
                    "allow_gateway_transit": remotePeering.allow_gateway_transit,
                    "use_remote_gateways": remotePeering.use_remote_gateways,
                    "remote_virtual_network": {
                        "id": remotePeering.remote_virtual_network.id
                    }

                }
                peeringPairList.append({
                    'localSubscriptionId': subscriptionId,
                    'localRgName': rgName,
                    'localVnetName': vnet.name,
                    'localPeeringName': peeringName,
                    'localPeering': peeringProperties,
                    'remoteSubscriptionId': remoteSubscriptionId,
                    'remoteRgName': remoteRgName,
                    'remoteVnetName': remoteVnetName,
                    'remotePeeringName': remotePeeringName,
                    'remotePeering': remotePeeringProperties
                })
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
                continue

            # 1) delete peerings
            logger.info(f'  delete peering {peeringName}')
            if not cls.DryRun:
                res = local_network_client.virtual_network_peerings.delete(rgName, vnet.name, peeringName).result()

            logger.info(f'  delete peering {remotePeeringName}')
            if not cls.DryRun:            
                res = remote_network_client.virtual_network_peerings.delete(remoteRgName, remoteVnetName, remotePeeringName).result()
        return peeringPairList

    @classmethod
    def addPeerings(cls, YAML, peeringPairList):
        logger = logging.getLogger(__name__)

        for pp in peeringPairList:
            cred = common.getAzureSubscriptionCred(YAML,pp['localSubscriptionId'])

            logger.info(f'- add peering {pp["localPeeringName"]}')
            local_network_client = NetworkManagementClient(cred['credentials'], pp['localSubscriptionId'])
            if not cls.DryRun:            
                res = local_network_client.virtual_network_peerings.create_or_update(pp['localRgName'], pp['localVnetName'], pp['localPeeringName'], pp['localPeering']).result()

            logger.info(f'- add peering {pp["remotePeeringName"]}')
            cred = common.getAzureSubscriptionCred(YAML,pp['remoteSubscriptionId'])
            remote_network_client = NetworkManagementClient(cred['credentials'], pp['remoteSubscriptionId'])
            if not cls.DryRun:            
                res = remote_network_client.virtual_network_peerings.create_or_update(pp['remoteRgName'], pp['remoteVnetName'], pp['remotePeeringName'], pp['remotePeering']).result()

    @classmethod
    def disableUseRemoteGwInPeering(cls, subscriptionId, local_network_client, vnet, exclude=None):
        logger = logging.getLogger(__name__)

        peeringPropList = []
        rgName = vnet.id.split('/')[dl.RG_I]
        logger.info(f'- Disable use_remote_gateways in peerings')
        if len(vnet.virtual_network_peerings) == 0:
            logger.info(f'  No peering found')
            return peeringPropList
        for peeringObj in vnet.virtual_network_peerings:
            peeringName = peeringObj.name
            if exclude != None and peeringName.startswith(exclude):
                logger.info(f'  controller created peering {peeringName} -- skipped')
                continue
            try:
                peering = local_network_client.virtual_network_peerings.get(rgName, vnet.name, peeringName)
                if peering.use_remote_gateways == True:
                    logger.info(f'  disable use_remote_gateways in peering {peeringName}')
                    peering.use_remote_gateways = False
                    peeringProperties = {
                        "id": peering.id,
                        "name": peering.name,
                        "allow_virtual_network_access": peering.allow_virtual_network_access,
                        "allow_forwarded_traffic": peering.allow_forwarded_traffic,
                        "allow_gateway_transit": peering.allow_gateway_transit,
                        "use_remote_gateways": peering.use_remote_gateways,
                        "remote_virtual_network": {
                            "id": peering.remote_virtual_network.id
                        }
                    }
                    if not cls.DryRun:                    
                        local_network_client.virtual_network_peerings.create_or_update(rgName, vnet.name, peeringName, peering)
                    peeringPropList.append({
                        'localSubscriptionId': subscriptionId,
                        'localRgName': rgName,
                        'localVnetName': vnet.name,
                        'localPeeringName': peeringName,
                        'localPeering': peeringProperties, 
                    })
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
                continue
        return peeringPropList

    @classmethod
    def restoreUseRemoteGwInPeering(cls, local_network_client, peeringPropList):
        logger = logging.getLogger(__name__)

        logger.info(f'- Restore use_remote_gateways in peering')
        if len(peeringPropList) == 0:
            logger.info(f'  no peering needs to be restored')
            return
        for peeringProp in peeringPropList:
            rgName = peeringProp['localRgName']
            peeringName = peeringProp['localPeeringName']
            vnetName = peeringProp['localVnetName']
            try:
                peering = local_network_client.virtual_network_peerings.get(rgName, vnetName, peeringName)
                logger.info(f'  set use_remote_gateways to True in {peeringName}')
                peering.use_remote_gateways = True
                if not cls.DryRun:                    
                    local_network_client.virtual_network_peerings.create_or_update(rgName, vnetName, peeringName, peering)
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
                continue

    @classmethod
    def updateVnetCidr(cls, args, cidrStrList, YAML, vnet):
        logger = logging.getLogger(__name__)

        rgName = vnet.id.split('/')[dl.RG_I]
        subscriptionId = vnet.id.split('/')[dl.SUB_I]
        cred = common.getAzureSubscriptionCred(YAML,subscriptionId)
        local_network_client = NetworkManagementClient(cred['credentials'], subscriptionId)

        vnetAddressSpace = [ipaddress.ip_network(ip) for ip in vnet.address_space.address_prefixes]
        cidrList = cidrStrList.split(',')
        needUpdate = False
        for aCidr in cidrList:

            aNetworkCidr = ipaddress.ip_network(aCidr)
        
            isCidrInVnet = any([aNetworkCidr.subnet_of(x) for x in vnetAddressSpace])
            if args.delete == False and isCidrInVnet:
                logger.info(f'  {aCidr} already existed in {vnet.name}')
                continue
            elif args.delete == True and not isCidrInVnet:
                logger.info(f'  {aCidr} not found in {vnet.name}')
                continue

            # todo: handle aCidr which is a superset of the existing vnet cidr?
            # 2) update vnet cidr
            if args.delete == True:
                logger.info(f'- to remove cidr {aCidr}')
                vnet.address_space.address_prefixes.remove(aCidr)
            else:
                logger.info(f'- to add cidr {aCidr}')
                vnet.address_space.address_prefixes.append(aCidr)
            needUpdate = True

        peeringPairList = []
        if needUpdate == False:
            return peeringPairList   
        if len(vnet.virtual_network_peerings) > 0:
            peeringPairList = cls.deletePeerings(YAML, subscriptionId, vnet, local_network_client)
        logger.info(f'- update cidr(s) in vnet')
        if not cls.DryRun:
            res = local_network_client.virtual_networks.create_or_update(rgName,vnet.name,vnet).result()
        return peeringPairList        
