import logging
from dm.arm.switchlib import SwitchTraffic as sw
from dm.arm.discoverylib import DiscoveryLib as dl

class PreStage:

    DryRun = False

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def createRouteTable(cls, yaml, revert, cred, vnet, defaultRtbName):
        logger = logging.getLogger(__name__)
        network_client = sw.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        rgName = vnet.id.split('/')[dl.RG_I]
        if revert == False:
            defaultRtObj = None
            try:
                defaultRtObj = network_client.route_tables.get(rgName, defaultRtbName)
            except:
                pass
            if defaultRtObj != None:
                logger.info(f'- Found {defaultRtbName}')                
                return
            logger.info(f'- Create {defaultRtbName}')
            prop = {
                "location": vnet.location,
                "disable_bgp_route_propagation": False,
                "tags": {
                    "name": defaultRtbName,
                    "Aviatrix-Created-Resource": "Do-Not-Delete-Aviatrix-Created-Resource"
                }
            }
            if cls.DryRun:
                return
            poller = network_client.route_tables.create_or_update(
                rgName, defaultRtbName, prop)
            response = poller.result()
        else:
            logger.info(f'- Delete {defaultRtbName}')            
            if cls.DryRun:
                return
            poller = network_client.route_tables.delete(rgName, defaultRtbName)
            response = poller.result()

    @classmethod
    def updateSubnetAssociation(cls, yaml, revert, cred, vnet, defaultRtbName):
        logger = logging.getLogger(__name__)

        rgName = vnet.id.split('/')[dl.RG_I]
        network_client = sw.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        if revert == False:
            logger.info(f'- Associate subnet without UDR to default route table {defaultRtbName}')
        else:
            logger.info(f'- Re-associate subnet without UDR to None')
        subnets_iter = network_client.subnets.list(rgName, vnet.name)
        subnets = list(subnets_iter)

        defaultRtbObj = None
        try:
            defaultRtbObj = network_client.route_tables.get(rgName, defaultRtbName)
        except:
            pass
        if defaultRtbObj == None:
            logger.warning(f'  **Alert** failed to locate route table {defaultRtbName}')

        for subnet in subnets:
            # exclude azure special subnet
            if subnet.name == 'GatewaySubnet':
                logger.info(f'  Found Azure {subnet.name} -- skipped')
                continue
            # skip Netapp delegated subnet because route table cannot be reassociated for this type of subnet
            if any([delegation.service_name == 'Microsoft.Netapp/volumes' for delegation in subnet.delegations]) == True:
                logger.info(
                    f'  {subnet.name} delegated to Microsoft.Netapp/volumes -- skipped')
                continue
            # 1) For subnet without UDR route table initially,
            # associate subnet to default UDR route table in a round robin fashion
            newRtbObj = subnet.route_table
            if revert == False:
                if subnet.route_table == None:
                    newRtbObj = defaultRtbObj
                    logger.info(f'  Associate {subnet.name} to {defaultRtbName}')
            # revert
            else:
                # Some subnets without route table in revert traffic.
                # This is not possible for revert traffic.
                if subnet.route_table == None:
                    logger.warning(
                        f'  **Alert** Subnet {subnet.name} without route table detected during revert -- skipped')
                    continue

                # this is aviatrix created spoke subnet, named aviatrix-spoke-gw and aviatrix-spoke-hagw
                if subnet.name.find("aviatrix-spoke") != -1:
                    logger.info(f'  Spoke gw subnet {subnet.name} -- skipped')
                    continue

                rtbName = subnet.route_table.id.split('/')[-1]
                # revert traffic, unassociate subnet from the <vnetName>-main-1 and <vnetName>-main-2 route tables we created in staging
                # set subnet association to None, no need to go back to controller created rt (e.g., vnetId---10-240-68-141-public)
                if rtbName == defaultRtbName:
                    newRtbObj = None
                    logger.info(
                        f'  Re-associate {subnet.name} from {rtbName} to None')

            if subnet.route_table != newRtbObj:
                subnet.route_table = newRtbObj

                if cls.DryRun:
                    continue

                poller = network_client.subnets.create_or_update(
                    rgName, vnet.name, subnet.name, subnet)
                response = poller.result()
