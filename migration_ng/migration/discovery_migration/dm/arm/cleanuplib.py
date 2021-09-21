import logging
from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.switchlib import SwitchTraffic as sw

class CleanUp:
    DryRun = False

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def lookupOrgRouteTable(cls,cred,vnet,rtb_target_rtb_map):
        logger = logging.getLogger(__name__)
        
        network_client = sw.getAzureNetworkManagmentClient(cred)
        if network_client == None:
            return

        rt_iter = network_client.route_tables.list_all()
        rts = list(rt_iter)
        stagedUdrLst = []
        for rtb in rts:
            # all route tables within the same subscription will be seen
            # only consider the ones in the given vnet.
            if rtb.subnets == None or len(rtb.subnets) == 0:
                continue
            elif dl.isRouteTableUsedInVnet(rtb,vnet) == False:
                continue
            elif rtb.tags == None:
                continue

            # check if it is a new table by checking if there is an Org_rt tag
            tags = [value for key, value in rtb.tags.items() if key == 'Org_RT']
            # rtb is the new route table created in staging if it has an Org_RT tag
            if (len(tags) > 0):
                orgRouteTableIdStr = tags[0]
                orgRouteTableId = ""
                if orgRouteTableIdStr.startswith("org_"):
                    orgRouteTableId = orgRouteTableIdStr[4:]
                    rtb_target_rtb_map[orgRouteTableId] = rtb.name
                else:
                    logger.warning(f'  **Alert** cannot find org_<routeTableId> in the Org_RT tag of new route table {rtb.id}')
        # End of RTB iteration

    @classmethod
    def deleteRouteTable(cls,network_client,rg,rtbName):
        logger = logging.getLogger(__name__)
        logger.info(
            f'  Delete route table {rg}:{rtbName}')
        if cls.DryRun:
            return
        try:
            response = network_client.route_tables.delete(rg,rtbName)
        except Exception as e:
            logger.warning(f'  **Alert** Failed to delete {rg}:{rtbName} {e}')
