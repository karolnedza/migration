import logging
import ipaddress
from dm.routetable import RouteTable
from dm.route import Route
from dm.subnet import Subnet
from dm.subnets import Subnets
from dm.commonlib import Common as common
from dm.aws import Aws as aws
import re
from dm.aviatrix import Aviatrix as av

class DiscoveryLib:

    VPC_NAME_MAX_LENGTH = 29
    vpcWithNoNameAlert = {}
    vpcWithDuplicateNameAlert = {}
    vpcWithNoIgwAlert = {}
    vpcRouteTableALert = {}

    @classmethod
    def setRegion(cls, region):
        logger = logging.getLogger(__name__)
        logger.debug('')
        logger.debug('Region {region}:')
        cls.region = region

    @classmethod
    def checkVpcForIgw(cls, ec2_client, vpc):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check {vpc.id} for IGW')
        response = ec2_client.describe_internet_gateways(
            Filters=[
                {
                    'Name': 'attachment.vpc-id',
                    'Values': [
                        vpc.id
                    ]
                }
            ]
        )

        if 'InternetGateways' in response:
            if len(response['InternetGateways']) > 0:
                logger.info(
                    f"  {vpc.id} has {response['InternetGateways'][0]['InternetGatewayId']}")
                return response['InternetGateways'][0]['InternetGatewayId']
        # alert (c) VPC has no IGW
        logger.warning(f'  **Alert** {vpc.id} has no IGW')
        return ""

    @classmethod
    def checkVpcForPeerings(cls, vpc):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check {vpc.id} for peerings')
        hasPeering = False
        for apc in vpc.accepted_vpc_peering_connections.all():
            if apc.status['Code'] == "deleted":
                continue

            hasPeering = True
            acidrs = []
            if 'CidrBlockSet' in apc.requester_vpc_info:
                acidrs = [cidr['CidrBlock']
                          for cidr in apc.requester_vpc_info['CidrBlockSet']]
            logger.warning(
                f"  **Alert** {apc.id} - {apc.requester_vpc_info['VpcId']} - {apc.requester_vpc_info['OwnerId']} - {acidrs}")

        for rpc in vpc.requested_vpc_peering_connections.all():
            if rpc.status['Code'] == "deleted":
                continue

            hasPeering = True
            rcidrs = []
            if 'CidrBlockSet' in rpc.accepter_vpc_info:
                rcidrs = [cidr['CidrBlock']
                          for cidr in rpc.accepter_vpc_info['CidrBlockSet']]
            logger.warning(
                f"  **Alert** {rpc.id} - {rpc.accepter_vpc_info['VpcId']} - {rpc.accepter_vpc_info['OwnerId']} - {rcidrs}")

        if not hasPeering:
            logger.info('  No peering found')

    @classmethod
    def checkAz(cls, ec2_client, region, zones):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check if az {zones} exists in {region}')
        response = ec2_client.describe_availability_zones()

        zoneNames = [f'{region}{x}' for x in zones]
        azList = [x['ZoneName'] for x in response['AvailabilityZones']]

        availableZone = []
        for n in zoneNames:
            if not n in azList:
                logger.error(f'  **Alert** {n} is not available in {region}')
                continue
            availableZone.append(n)
            logger.info(f'  found {n}')
        return availableZone

    @classmethod
    def checkOnboardAccount(cls, api_ep_url, CID, accountId):
        """Check if an account aws-{accountId} alread exists in the controller

        Return:
        None: controller already got an account under an unexpected account name - alert and skip all terraform file generation for this account.
        True: okay to onboard the account name aws-{accountId}
        False: account already exists, no need to onboard again.

        """
        logger = logging.getLogger(__name__)
        response = av.list_accounts(api_endpoint_url=api_ep_url+"api", CID=CID)
        responseJson = response.json()
        accountNames = [ x['account_name'] for x in responseJson['results']['account_list'] if x['account_number'] == accountId ]
        if len(accountNames) == 0:
            return True
        if len(accountNames) > 0:
            if not f'aws-{accountId}' in accountNames:
                logger.warning(f'  **Error** account {accountId} already onboarded with an unexpected account name {accountNames}')
                return None
            else:
                return False

    @classmethod
    def getAnyAzList(cls, ec2_client, number, exclude=[]):
        logger = logging.getLogger(__name__)
        logger.debug(f'- Get Availability Zones:')
        response = ec2_client.describe_availability_zones()
        logger.debug(f'  exclude - {exclude}')
        azList = [x['ZoneName'] for x in response['AvailabilityZones']
                  if not x['ZoneName'] in exclude]
        sortedAzList = sorted(azList)
        # assume there is at least two AZ in a region
        return sortedAzList[:number]

    @classmethod
    def discoverAz(cls, ec2_client, routeTables, vpc, exclude=[], attachmentSubnet=[]):
        logger = logging.getLogger(__name__)
        logger.info(f'- Suggest AZ with largest number of private subnets')

        response = ec2_client.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [
                        vpc.id
                    ]
                }
            ]
        )

        # zMap stores the number of private subnets in each zone
        zMap = {}
        for x in response['Subnets']:
            subnetId = x['SubnetId']
            if subnetId in attachmentSubnet:
                continue
            rtbId = routeTables.getRtbIdFromAssociation(subnetId)

            # For subnet without a route table, check the main route table
            if rtbId == None:
                rtbId = routeTables.getMainRouteTable()

            rtb = routeTables.get(rtbId)
            if not rtb == None and not rtb.isPublic():
                az = x['AvailabilityZone']
                if az in exclude:
                    continue
                if az in zMap:
                    zMap[az] = zMap[az] + 1
                else:
                    zMap[az] = 1
        if len(zMap) > 0:
            logger.info(f'  Available zones with private subnet count:')
            for k, v in zMap.items():
                logger.info(f'    {k}: {v}')
        else:
            logger.info(f'  no AZ has private subnet')
        zList = list(zMap.keys())

        zListSize = len(zList)

        if len(exclude) + zListSize == 1:
            # get any one zone from AZ list
            lst = cls.getAnyAzList(ec2_client, 1, zList)
            zList.append(lst[0])
            logger.info(f'  Suggested AZ: {zList}')
            return zList
        elif len(exclude) + zListSize == 0:
            # return two zones from AZ list
            lst = cls.getAnyAzList(ec2_client, 2)
            logger.info(f'  Suggested AZ: {lst}')
            return lst
        else:
            # sample output [('us-east-1b', 3), ('us-east-1d', 2)] of the following reverse sorted map:
            # sorted descending order by <numberOfPrivateSubnets> and then ascending order by
            # <regionId>. Achieved by using the key tuple (-1 * <numberOfPrivateSubnets>,<regionId>)
            zTuple = sorted(zMap.items(), key=lambda x: (-1 * x[1], x[0]))[:2]
            lst = list(dict(zTuple).keys())
            numElementReturn = 2 - len(exclude)
            logger.info(f'  Suggested AZ: {lst[:numElementReturn]}')
            return lst[:numElementReturn]

    @classmethod
    def checkVpcsDuplicateName(cls, account, creds):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check VPC for duplicate name')

        vpcDupNameCount = {}

        for regionObj in account['regions']:
            ec2_resource = common.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client = ec2_resource.meta.client
            vpcs = ec2_resource.vpcs.all()

            vpcsInRegionObj = []
            if regionObj['vpcs']:
                vpcsInRegionObj = [x['vpc_id'] for x in regionObj['vpcs']]

            for vpc in vpcs:

                if regionObj['vpcs']:
                    if vpc.id not in vpcsInRegionObj:
                        continue

                ntag = []
                if vpc.tags:
                    ntag = [tag["Value"]
                            for tag in vpc.tags if tag["Key"] == "Name"]

                vpcName = ""

                # Alert (b) missing VPC name
                if (len(ntag) > 0):
                    vpcName = ntag[0]
                else:
                    logger.warning(
                        f'  **Alert** Missing VPC name in {regionObj["region"]}/{vpc.id}')

                if len(vpcName) > 0 and not (vpcName[0].isalpha() and re.match('^[a-zA-Z][0-9a-zA-Z\-]*$',vpcName) != None):
                    logger.warning(                        
                        f'  **Alert** VPC name {vpcName} must start with a letter and can only contain alphamumeric characters and hypen (-).')

                # Alert (j) VPC name > cls.VPC_NAME_MAX_LENGTH characters
                if len(vpcName) > cls.VPC_NAME_MAX_LENGTH:
                    logger.warning(
                        f'  **Alert** VPC name {vpcName} > {cls.VPC_NAME_MAX_LENGTH} chars, in {regionObj["region"]}/{vpc.id}')

                if vpcName in vpcDupNameCount:
                    vpcDupNameCount[vpcName].append(
                        {
                            "vpc_id": vpc.id,
                            "region": regionObj["region"]
                        }
                    )
                else:
                    vpcDupNameCount[vpcName] = [
                        {
                            "vpc_id": vpc.id,
                            "region": regionObj["region"]
                        }
                    ]

        lst = dict(filter(lambda ele: len(
            ele[1]) > 1, vpcDupNameCount.items()))

        # Alert (m) Duplicate VPC names
        for k, v in lst.items():
            logger.warning(
                f'  **Alert** duplicate VPC name {k} {len(v)} times:')
            for obj in v:
                logger.warning(f'            {obj["region"]}/{obj["vpc_id"]}')

        return {key: 0 for (key, value) in vpcDupNameCount.items() if len(value) > 1}

    @classmethod
    def discoverSubnetAssociations(cls, routeTables, rtb, attachmentSubnets):
        """
        discover subnet associations for the input 'rtb'

        :returns: a tuple 1) is this a main rtb, 
                          2) number of original subnet association, 
                          3) number of subnets that is NO associated to a tgw VPC attachment
        :rtype: (bool, int)
        """
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover Subnet Associations ({rtb.id})')

        isMainRTB = False
        subnets = []
        filterTgwSubnets = []
        for assoc in rtb.associations_attribute:
            try:
                # assocs.append(assoc['RouteTableAssociationId'])
                if 'SubnetId' in assoc:
                    routeTables.addSubnetRtbAssociation(
                        assoc['SubnetId'], rtb.id)
                    subnets.append(assoc['SubnetId'])
                    if not assoc['SubnetId'] in attachmentSubnets:
                        filterTgwSubnets.append(assoc['SubnetId'])
                else:
                    isMainRTB = True
                    logger.info(f"  main table")
            except KeyError:
                pass

        if len(subnets) == 0:
            if not isMainRTB:
                # alert (h): alert route table with no subnet association
                # will be alerted in the calling routine discoverRouteTables
                logger.info(
                    f"  {rtb.id} has no associated subnet")
        else:
            for s in subnets:
                if s in attachmentSubnets:
                    logger.info(f"  {s} - tgw attachment subnet (skipped)")
                else:
                    logger.info(f"  {s}")                

        return isMainRTB, len(subnets), len(filterTgwSubnets)

    @classmethod
    def discoverSubnets(cls, ec2_client, vpc, routeTables, regionInfo, attachmentSubnets, yamlObj):
        logger = logging.getLogger(__name__)
        logger.info(f'- Subnet import summary for {vpc.id}')
        subnets = vpc.subnets.all()
        subnetsObj = Subnets(vpc.id,routeTables)
        for sub in subnets:
            if not sub.id in attachmentSubnets:
                rtbId = routeTables.getRtbIdFromAssociation(sub.id)
                rtb = routeTables.get(rtbId)
                subObj = Subnet(sub,regionInfo)
                subObj.addAdditonalTags(yamlObj['subnet_tags'])
                subnetsObj.add(subObj)
                if rtb.isPublic():
                    logger.info(f'  {sub.id} (Public) {rtbId}')
                else:
                    logger.info(f'  {sub.id} (Private) {rtbId}')
            else:
                logger.info(f'  {sub.id} - tgw attachment subnet (skipped)')
        return subnetsObj

    @classmethod
    def discoverRouteTables(cls, ec2_client, vpc, vpc_cidrs, routeTables, attachmentSubnets, yamlObj):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check Route Tables for {vpc.id}')

        vpc_rtbs = vpc.route_tables.all()

        numberOfRtbs = 0
        for rtb in vpc_rtbs:
            numberOfRtbs = numberOfRtbs + 1
            logger.info(f'  {rtb.id}')

        # alert (f): number of route tables in VPC > 99
        if numberOfRtbs > 99:
            if cls.region in cls.vpcRouteTableALert:
                cls.vpcRouteTableALert[cls.region].append(vpc.id)
            else:
                cls.vpcRouteTableALert[cls.region] = [vpc.id]
            logger.warning(
                f'  **Alert** {vpc.id} has {numberOfRtbs} route table(s)')
        else:
            logger.debug(f'  {vpc.id} has {numberOfRtbs} route table(s)')

        summary = {}
        for rtb in vpc_rtbs:
            # assocs = []
            isMainRTB, orgAssociationAccount, subnetAssociationCount = cls.discoverSubnetAssociations(routeTables, rtb, attachmentSubnets)

            logger.info(f'- Discover route(s) for {rtb.id}')
            # logger.info(rtb.id)
            # logger.info("----------------------\n")

            rtable = RouteTable(rtb.id, rtb.tags)
            rtable.addAdditonalTags(yamlObj['route_table_tags'])
            rtable.addFilters(routeTables.getFilterCidrs())
            rtable.addExpectedCidrs(routeTables.getExpectedCidrs())
            rtable.addKnownTgwId(routeTables.getTgwId())

            rtable.setMain(isMainRTB)
            # keep track of the main routeTable id in routeTables
            if isMainRTB:
                routeTables.setMainRouteTable(rtb.id)

            # rtb.routes does not return the VPCE route so using the client interface instead
            rtb_routes = ec2_client.describe_route_tables(
                RouteTableIds=[rtb.id])

            # logger.info("Routes:\n")
            logger.info("  " + "".rjust(63, "."))
            logger.info("  " + "Prefix".ljust(25) +
                        "Next-hop".ljust(30) + "Origin")
            logger.info("  " + "".rjust(63, "."))

            localRouteCount = 0
            for rt in rtb_routes['RouteTables'][0]['Routes']:
                nhop = None
                if rt.get('GatewayId'):
                    nhop = rt['GatewayId']
                    # if nhop != "local":
                    #     if args.stage_vpcs and rt.get('DestinationPrefixListId'):
                    #         # This is the only AWS API call that is not already included in aviatrix-role-app
                    #         try:
                    #             response = ec2_client.modify_vpc_endpoint(
                    #                 VpcEndpointId=nhop, AddRouteTableIds=[new_rtb.id])
                    #         except botocore.exceptions.ClientError as e:
                    #             logger.info(
                    #                 f"{rt.get('DestinationPrefixListId')} - {nhop} --> Please add this entry manually\n")
                    #             pass
                    #     elif args.stage_vpcs:
                    #         if rt.get('DestinationIpv6CidrBlock'):
                    #             new_rt = new_rtb.create_route(
                    #                 DestinationIpv6CidrBlock=rt.get('DestinationIpv6CidrBlock'), GatewayId=nhop)
                    #         else:
                    #             new_rt = new_rtb.create_route(
                    #                 DestinationCidrBlock=rt.get('DestinationCidrBlock'), GatewayId=nhop)
                    #     else:
                    #         pass

                elif rt.get('TransitGatewayId'):
                    nhop = rt['TransitGatewayId']
                elif rt.get('VpcPeeringConnectionId'):
                    nhop = rt['VpcPeeringConnectionId']
                    # if args.stage_vpcs:
                    #     new_rt = new_rtb.create_route(DestinationCidrBlock=rt.get(
                    #         'DestinationCidrBlock'), VpcPeeringConnectionId=nhop)
                elif rt.get('NatGatewayId'):
                    nhop = rt['NatGatewayId']
                    # if args.stage_vpcs:
                    #     new_rt = new_rtb.create_route(
                    #         DestinationCidrBlock=rt['DestinationCidrBlock'], NatGatewayId=nhop)
                elif rt.get('NetworkInterfaceId'):
                    nhop = rt['NetworkInterfaceId']
                    # if args.stage_vpcs:
                    #     new_rt = new_rtb.create_route(DestinationCidrBlock=rt.get(
                    #         'DestinationCidrBlock'), NetworkInterfaceId=nhop)
                # elif rt.local_gateway_id:
                # The ID of the local gateway
                #    nhop = rt.local_gateway_id
                else:
                    logger.info(rt)

                try:
                    logger.info(
                        f"  {rt['DestinationPrefixListId'].ljust(25)}{nhop.ljust(30)}manual")
                except:
                    if rt.get('DestinationIpv6CidrBlock'):
                        logger.info(
                            f"  {rt.get('Origin')} - {rt.get('DestinationIpv6CidrBlock')} - {nhop}")
                    else:
                        if rt.get('Origin') == "CreateRouteTable":
                            logger.info(
                                f"  {rt.get('DestinationCidrBlock').ljust(25)}{nhop.ljust(30)}auto")
                        elif rt.get('Origin') == "CreateRoute":
                            logger.info(
                                f"  {rt.get('DestinationCidrBlock').ljust(25)}{nhop.ljust(30)}manual")
                        elif rt.get('Origin') == "EnableVgwRoutePropagation":
                            logger.info(
                                f"  {rt.get('DestinationCidrBlock').ljust(25)}{nhop.ljust(30)}VGW")
                        else:
                            logger.info("  " + rt.get('DestinationCidrBlock').ljust(
                                25), nhop.ljust(30), rt.get('Origin'))

                routeObj = Route(rt, nhop)
                rtable.add(routeObj)

                # alert (a): Unusual public route and endpoint
                try:
                    # if destination is not an IP address, it is vpce
                    dest_ipn = ipaddress.ip_network(routeObj.getDest())
                    if type(dest_ipn) is ipaddress.IPv6Network:
                        logger.warning(f'  **Alert** unexpected IPv6 route detected {routeObj.getDest()} to {nhop} in {rtb.id} - NOT copied')
                    # alert (l): Route to a TGW different than provided in yaml
                    elif nhop == 'local':
                        localRouteCount = localRouteCount + 1                        
                        # if routeObj.getDest() in vpc_cidrs:
                        #     localRouteCount = localRouteCount + 1
                        # else:
                        #     logger.warning(
                        #         f'  **Alert** unexpected route {routeObj.getDest()} to {nhop} in {rtb.id}')
                    elif rt['State'] != 'active':
                        logger.warning(
                            f'  **Alert** Inactive route ({rt["State"]}) {routeObj.getDest()} to {nhop} in {rtb.id} - NOT copied')
                    elif nhop.startswith('tgw-') and not nhop in routeTables.getTgwList():
                        logger.warning(
                            f'  **Alert** route {routeObj.getDest()} to unexpected {nhop} in {rtb.id}')
                    elif rtable.isRfc1918ExactMatch(routeObj.getDest()):
                        continue
                    elif routeObj.getDest() == "0.0.0.0/0" and nhop.startswith("igw-"):
                        continue
                    elif rtable.isRfc1918(dest_ipn):
                        logger.warning(
                            f'  **Alert** unexpected private IP {routeObj.getDest()} to {nhop} in {rtb.id}')
                    elif not rtable.isInExpectedCidrRange(routeObj.getDest()):
                        logger.warning(
                            f'  **Alert** unexpected public IP {routeObj.getDest()} to {nhop} in {rtb.id}')
                except ValueError:
                    if nhop.startswith('vpce-'):
                        logger.warning(
                            f'  **Alert** unexpected route {routeObj.getDest()} to {nhop} in {rtb.id}')

            # End rt looping

            # alert (g): Alert route table with no routes
            if len(rtb_routes['RouteTables'][0]['Routes']) == localRouteCount:
                logger.warning(f'  **Alert** empty route table {rtb.id}')

            # alert (i): A route table with an IGW which has any RFC1918 routes
            if rtable.isPublic() and rtable.hasRfc1918Route():
                logger.warning(
                    f'  **Alert** {rtb.id} is associated to an IGW and has RFC1918 routes')

            # alert (n): static route table entries > 35
            if rtable.isPublic():
                routeTableType = 'Public'
            else:
                routeTableType = 'Private'

            if rtable.staticRouteCount > 35:
                logger.warning(
                    f'  **Alert** {rtb.id} ({routeTableType}) has {rtable.staticRouteCount} (> 35) static routes')
            else:
                logger.info(
                    f'  {rtb.id} ({routeTableType}) has {rtable.staticRouteCount} static routes')

            summary[rtb.id] = f'{rtb.id} copied'
            # numAssociationsAttribute = len(rtb.associations_attribute)
            # Main route table will have one associations_attribute with no SubnetId defined
            if isMainRTB:
                routeTables.add(rtable)
            # Alert (h): Route tables not associated with any subnet unless it is a main RT
            # tfvars (8f): Exclude route tables not associated with any subnet unless it is a main RT -
            elif subnetAssociationCount == 0:
                if orgAssociationAccount == 0:
                    summary[rtb.id] = f'{rtb.id} has no subnet associations (skipped)'
                    logger.warning(f'  **Alert** {rtb.id} has no subnet associations (skipped)')
                else:
                    summary[rtb.id] = f'{rtb.id} associated ONLY to tgw VPC attachment subnet(s) (skipped)'
                    logger.warning(f'  **Alert** {rtb.id} associated ONLY to tgw VPC attachment subnet(s) (skipped)')
            # public route table with route to internal network
            elif rtable.isPublic() and (rtable.isAccessInternalNetwork() or rtable.hasRfc1918Route()):
                routeTables.add(rtable)
            # tfvars (8i): public route table with no TGW/VGW routes
            elif rtable.isPublic():
                rtable.ctrl_managed = False
                routeTables.add(rtable)
            # private route table with routes and subnet association
            elif not rtable.isPublic() and subnetAssociationCount > 0:
                routeTables.add(rtable)
            # tfvars (8e): Exclude route tables originally empty unless it is a main RT -
            # should not hit this condition at all because empty routetable without subnet association will be hitted first above.
            else:
                summary[rtb.id] = f'{rtb.id} unknown reason (skipped)'
                logger.warning(f'  **Alert** {rtb.id} unknown reason (skipped)')

        #
        # output summary
        #
        logger.info(f'- Route table copy summary for {vpc.id}')
        numberOfRtbs = 0
        for rtb in vpc_rtbs:
            numberOfRtbs = numberOfRtbs + 1
            logger.info(f'  {summary[rtb.id]}')

    @staticmethod
    def _is_subnet_of(a, b):
        try:
            # Always false if one is v4 and the other is v6.
            if a._version != b._version:
                raise TypeError(f"{a} and {b} are not of the same version")
            return (b.network_address <= a.network_address and
                    b.broadcast_address >= a.broadcast_address)
        except AttributeError:
            raise TypeError(f"Unable to test subnet containment "
                            f"between {a} and {b}")

    @classmethod
    def isExpectedVpcPrefix(self,ip,prefixes):
        ipn = ipaddress.ip_network(ip)
        for n in prefixes:
            if self._is_subnet_of(ipn,n):
                return True
        return False

    @classmethod
    def discoverVpcCidr(cls, ec2_client, vpc, yaml):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check {vpc.id} for cidr limit')
        expectVpcPrefix = yaml['expect_vpc_prefixes']
        allowVpcCidr = yaml['allow_vpc_cidrs']
        response = ec2_client.describe_vpcs(
            VpcIds=[
                vpc.id
            ]
        )

        # aws will return some with 'disassociated' state.
        # extract only the ones with State == 'associated', 
        associatedCidrList = [ x for x in response['Vpcs'][0]['CidrBlockAssociationSet'] if x['CidrBlockState']['State'] == 'associated']
        numberOfCidrs = len(associatedCidrList)

        # alert (d): VPC has 5 cidrs
        if (numberOfCidrs >= 5):
            logger.warning(
                f'  **Alert** {vpc.id} has {numberOfCidrs} (>= 5) cidr(s)')

        # filter out CIDR not starting with expect_vpc_prefixes
        # vpcCidrs = [ x['CidrBlock'] for x in response['Vpcs'][0]['CidrBlockAssociationSet'] if x['CidrBlock'].startswith("10.") ]
        vpcCidrs = []
        for x in associatedCidrList:
            # alert (o): VPC CIDR does not match any expected prefix     
            if not cls.isExpectedVpcPrefix(x['CidrBlock'],expectVpcPrefix):
                logger.warning(
                    f'  **Alert** {vpc.id} with cidr {x["CidrBlock"]} not matching expected VPC prefix')
            if cls.isExpectedVpcPrefix(x['CidrBlock'],allowVpcCidr):
                vpcCidrs.append(x['CidrBlock'])
            else:
                logger.info(
                    f'  {vpc.id} with cidr {x["CidrBlock"]} not matching accepted VPC cidr (filtered)')
        if len(vpcCidrs) == 0:
            logger.warning(
                f'  **Alert** {vpc.id} with EMPTY cidr list - does not have any accepted VPC cidr(s)')
        return vpcCidrs

    @classmethod
    def deduceSuffix(cls, vpcDupNameMap, vpcName, accountId):
        # Deduce the spoke gw_name for advertising the customized cidrs
        #
        # 1) Deduce gw_name_suffix
        gw_name_suffix = ""
        vpcNameAid = f"{vpcName}-{accountId}"
        if vpcNameAid in vpcDupNameMap:
            vpcDupNameMap[vpcNameAid] = vpcDupNameMap[vpcNameAid] + 1
            gw_name_suffix = vpcDupNameMap[vpcNameAid]

        return gw_name_suffix

    @classmethod
    def checkEipUsage(cls, ec2_client, vpcsInRegionObj, vpcs):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check EIP usage')
        response = ec2_client.describe_account_attributes(
            AttributeNames=[
                'vpc-max-elastic-ips',
            ],
        )
        try:
            eipLimit = int(response['AccountAttributes']
                           [0]['AttributeValues'][0]['AttributeValue'])
        except:
            eipLimit = 0

        response = ec2_client.describe_addresses()
        eipInUse = len(response['Addresses'])

        vpcCnt = 0
        for vpc in vpcs:
            if len(vpcsInRegionObj) > 0:
                if vpc.id not in vpcsInRegionObj:
                    continue
                vpcCnt = vpcCnt + 1
            else:
                vpcCnt = vpcCnt + 1

        eipLeft = eipLimit - eipInUse
        eipRequire = 2 * vpcCnt
        logger.info(f'  EIP limit:    {eipLimit}')
        logger.info(f'  EIP in use:   {eipInUse}')
        logger.info(f'  EIP required: {eipRequire}')
        if eipLeft < eipRequire:
            logger.warning(
                f'  **Alert** only {eipLeft} left, require {eipRequire} EIP(s) for {vpcCnt} VPC(s)')

    @classmethod
    def checkVpnConnection(cls, ec2_client, vpc):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check VPN connection in {vpc.id}')
        response = ec2_client.describe_vpn_gateways(
            Filters=[
                {
                    'Name': 'attachment.vpc-id',
                    'Values': [
                        vpc.id,
                    ]
                },
            ],
        )
        foundAny = False
        for vpnGateway in response['VpnGateways']:
            vpnGatewayId = vpnGateway['VpnGatewayId']
            response = ec2_client.describe_vpn_connections(
                Filters=[
                    {
                        'Name': 'vpn-gateway-id',
                        'Values': [
                            vpnGatewayId,
                        ]
                    },
                ],
                # VpnConnectionIds

            )
            for x in response['VpnConnections']:
                foundAny = True
                logger.warning(
                    f"  **Alert** {x['VpnConnectionId']} associated with {vpnGatewayId} attached to {vpc.id}")

        if not foundAny:
            logger.info(f"  no vpn connection found")

    @classmethod
    def discoverTgw(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover TGW')
        response = ec2_client.describe_transit_gateways()
        if len(response['TransitGateways']) == 0:
            logger.info(f'  no TGW found')
        else:
            for tgw in response['TransitGateways']:
                logger.info(f'  {tgw["TransitGatewayId"]}')

    @classmethod
    def discoverVgw(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover VGW')
        response = ec2_client.describe_vpn_gateways()
        if len(response['VpnGateways']) == 0:
            logger.info(f'  no VGW found')
        else:
            for vgw in response['VpnGateways']:
                logger.info(f'  {vgw["VpnGatewayId"]}')

    @classmethod
    def discoverIgw(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover IGW')
        response = ec2_client.describe_internet_gateways()
        if len(response['InternetGateways']) == 0:
            logger.info(f'  no IGW found')
        else:
            for igw in response['InternetGateways']:
                if len(igw['Attachments']) > 0:
                    logger.info(f'  {igw["InternetGatewayId"]} in {igw["Attachments"][0]["VpcId"]}')
                else:
                    logger.info(f'  {igw["InternetGatewayId"]} not attached')

    @classmethod
    def discoverSpokeGw(cls, ec2_client, vpcId):
        logger = logging.getLogger(__name__)
        logger.info(f'- Check if {vpcId} has been migrated')
        response = ec2_client.describe_instances(
            Filters=[
                {
                    'Name': 'tag-key',
                    'Values': [
                        "Aviatrix-Created-Resource",
                    ]
                },
                {
                    'Name': 'vpc-id',
                    'Values': [
                        vpcId
                    ]
                }
            ],
        )

        if len(response['Reservations']) == 0:
            logger.info(f'  no spoke gateway found')
        else:
            for ec2 in response['Reservations']:
                gwNameLst = [ x['Value'] for x in ec2['Instances'][0]['Tags']  if x['Key'] == 'Name' ]
                if len(gwNameLst) > 0:
                    logger.warning(f'  **Alert** VPC {vpcId} already migrated, found an aviatrix gateway {gwNameLst[0]}')
                    return True
                else:
                    logger.warning(f'  **Alert** VPC {vpcId} already migrated, found an aviatrix gateway with no Name tag')
                    return True
        return False

    @classmethod
    def discoverNatGw(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover NAT gateway')
        response = ec2_client.describe_nat_gateways()
        if len(response['NatGateways']) == 0:
            logger.info(f'  no NAT Gateway found')
        else:
            for nat in response['NatGateways']:
                subnetId = nat['SubnetId']
                vpcId = nat['VpcId']
                logger.info(f'  {nat["NatGatewayId"]} in {vpcId}/{subnetId}')

    @classmethod
    def discoverEndpoint(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover Endpoint')
        response = ec2_client.describe_vpc_endpoints()
        if len(response['VpcEndpoints']) == 0:
            logger.info(f'  no Endpoint found')
        else:
            for endpoint in response['VpcEndpoints']:
                serviceName = endpoint['ServiceName']
                vpcId = endpoint['VpcId']
                logger.info(f'  {endpoint["VpcEndpointId"]} ({vpcId}/{serviceName})')

    @classmethod
    def discoverPeering(cls, ec2_client):
        logger = logging.getLogger(__name__)
        logger.info(f'- Discover Peering')
        response = ec2_client.describe_vpc_peering_connections()

        if len(response['VpcPeeringConnections']) == 0:
            logger.info(f'  no Peering found')
        else:
            for peering in response['VpcPeeringConnections']:
                accepter = peering['AccepterVpcInfo']
                accepterVpcId = accepter['VpcId']
                accepterRegion = accepter['Region']
                accepterOwnerId = accepter['OwnerId']

                requester = peering['RequesterVpcInfo']
                requesterVpcId = requester['VpcId']
                requesterRegion = requester['Region']
                requesterOwnerId = requester['OwnerId']

                status = peering['Status']

                logger.info(f'  {requesterOwnerId}/{requesterRegion}/{requesterVpcId} {accepterOwnerId}/{accepterRegion}/{accepterVpcId} {status["Message"]}')