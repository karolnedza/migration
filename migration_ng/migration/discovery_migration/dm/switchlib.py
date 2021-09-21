import logging
import ipaddress

class SwitchTraffic:

    @classmethod
    def isExpectedVpcPrefix(self,ip,prefixes):
        ipn = ipaddress.ip_network(ip)
        for n in prefixes:
            if ipn.subnet_of(n):
                return True
        return False

    @classmethod
    def discoverVpcCidr(cls,ec2_client,vpc,yaml):
        logger = logging.getLogger(__name__)
        allowVpcCidr = yaml['allow_vpc_cidrs']
        response = ec2_client.describe_vpcs(
            VpcIds = [
                vpc.id
            ]
        )

        # filter out CIDR not starting with 10.x.x.x
        # vpcCidrs = [ x['CidrBlock'] for x in response['Vpcs'][0]['CidrBlockAssociationSet'] if x['CidrBlock'].startswith("10.") ]
        # return vpcCidrs

        # aws will return some with 'disassociated' state.
        # extract only the ones with State == 'associated'
        associatedCidrList = [ x for x in response['Vpcs'][0]['CidrBlockAssociationSet'] if x['CidrBlockState']['State'] == 'associated']
        vpcCidrs = []
        # retain vpc Cidrs that are within allow_vpc_cidrs list
        for x in associatedCidrList:
            if cls.isExpectedVpcPrefix(x['CidrBlock'],allowVpcCidr):
                vpcCidrs.append(x['CidrBlock'])
        return vpcCidrs

    @classmethod
    def discoverSubnetAssociation(cls,rtb,assocs,subnets):
        for assoc in rtb.associations_attribute:
            try:
                assocs.append(assoc)
                subnets.append(assoc['SubnetId'])
            except KeyError:
                pass

    @classmethod
    def discoverRouteTable(cls,revert,vpc,rtb_target_rtb_map,rtb_assocs_map):
        logger = logging.getLogger(__name__)
        vpc_rtbs = vpc.route_tables.all()

        for rtb in vpc_rtbs:
            subnets = []
            assocs = []

            # check if it is a new table by checking if there is an Org_rt tag
            tags = [t for t in rtb.tags if t['Key'] == 'Org_RT']
            # rtb is new rtb created in staging if it has an Org_RT tag
            if (len(tags) > 0):
                orgRouteTableIdStr = tags[0]['Value']
                orgRouteTableId = ""
                if orgRouteTableIdStr.startswith("org_"):
                    orgRouteTableId = orgRouteTableIdStr[4:]
                    # 1) current rtb is new rtb created by staging.
                    # 2) For switch_traffic, lookup subnets association in original rtb.
                    # 3) rtb_target_rtb_map stores: original rtb id => new rtb id
                    if revert == False:
                        rtb_target_rtb_map[orgRouteTableId] = rtb.id
                        continue
                    # 1) current rtb is new rtb created by staging.
                    # 2) For switch_traffic --revert, lookup subnet association in new rtb
                    # 3) rtb_target_rtb_map stores: new rtb id => original rtb id
                    else:
                        rtb_target_rtb_map[rtb.id] = orgRouteTableId
                else:
                    logger.warning(f'  **Alert** cannot find org_<routeTableId> in the Org_RT tag of new route table {rtb.id}')

                # For switch_traffic --revert, discover subnet association in new rtb
                if revert == True:
                    cls.discoverSubnetAssociation(rtb, assocs, subnets)
            else:
                # For switch_traffic, discover subnet association in original rtb
                if revert == False:
                    cls.discoverSubnetAssociation(rtb, assocs, subnets)

            # print(f'rtb id: {rtb.id}')
            # for assoc in rtb.associations_attribute:
            #     try:
            #         assocs.append(assoc)
            #         subnets.append(assoc['SubnetId'])
            #     except KeyError:
            #         pass

            # print(f"Associated subnets: {subnets}\n")
            # Key is RTB ID and value is association_id
            rtb_assocs_map[rtb.id] = assocs

            # Add VGW propagation to new RTB as well
            # if args.vgw_prop and args.stage_vpcs:
            #     print(f"Propagating VGWs - {rtb.propagating_vgws}")
            #     for vgw in rtb.propagating_vgws:
            #         response = ec2_client.enable_vgw_route_propagation(
            #             GatewayId=vgw,
            #             RouteTableId=new_rtb.id)

        # End of RTB iteration

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
        'us-west-2'      : 'usw2',
        'us-west-1'      : 'usw1',
        'us-east-1'      : 'use1',
        'eu-west-1'      : 'euw1',
        'eu-central-1'   : 'euc1',
        'ap-southeast-1' : 'apse1',
        'ap-northeast-1' : 'apne1',
        'cn-north-1'     : 'cnn1',
        'cn-northwest-1' : 'cnnw1'
    }

    @classmethod
    def deduceGwNameWithSubnetCidr(cls,regionId,cidr):
        # Deduce the spoke gw_name for advertising the customized cidrs
        ip = cidr.split('/')[0]
        octal = ip.split('.')
        gw_name = f'aws-{cls.region[regionId]}-{int(octal[0]):02x}{int(octal[1]):02x}{int(octal[2]):02x}{int(octal[3]):02x}-gw'
        return gw_name
