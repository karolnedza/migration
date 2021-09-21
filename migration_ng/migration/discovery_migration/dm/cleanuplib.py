import logging
import sys
import botocore
import ipaddress
import os
from retry import retry
from dm.aws import Aws as aws

class CleanUp:

    DryRun = False

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    @retry(botocore.exceptions.ClientError, tries=10, delay=30)
    def deleteSubnet(cls, ec2_client, subnetIds):
        logger = logging.getLogger(__name__)
        if len(subnetIds) == 0:
            return
        logger.info(f'- Delete subnets associated with TGW')
        for subnet in subnetIds:
            logger.info(f'  Delete subnet {subnet}')
            if cls.DryRun:
                continue
            try:
                response = ec2_client.delete_subnet(
                    SubnetId = subnet
                )
            except botocore.exceptions.ClientError as e:
                if 'Error' in e.response and 'Code' in e.response['Error']:
                    if e.response['Error']['Code'] == 'DependencyViolation':
                        logger.info(f'  **Retrying** in next 30 sec..')
                        raise e
                    else:
                        logger.error(f'  **Error** {e}')

    @classmethod
    def deleteVpcCidr(cls, ec2_client, vpc, vpc_cidrs):
        logger = logging.getLogger(__name__)
        cidr_map={}
        if vpc_cidrs != None:
            response = ec2_client.describe_vpcs(
                Filters=[
                    {
                        'Name': 'vpc-id',
                        'Values': [
                            vpc.id,
                        ]
                    },
                ],
            )
            if 'Vpcs' not in response or len(response['Vpcs']) == 0:
                # No attributes for this specific vpc 
                return
            for Attr in response['Vpcs']:
                for Association in Attr['CidrBlockAssociationSet']:
                    if Association['CidrBlockState']['State'] == 'associated':
                        cidr_map[Association['CidrBlock']] = Association['AssociationId']
            
            ip_vpc_cidrs = [ipaddress.ip_network(x) for x in vpc_cidrs]
            for rmcidr in ip_vpc_cidrs:
                for vpc_cidr in cidr_map.keys():
                    # Check if either of the subnets in the vpc associated cidrs is a subset/subnet of provided cleanup vpx_cidrs list
                    if ipaddress.ip_network(vpc_cidr).subnet_of(rmcidr):
                        logger.info(f'- Delete CIDR {rmcidr} associated with VPC')
                        if cls.DryRun:
                            continue
                        try:
                            response = ec2_client.disassociate_vpc_cidr_block(
                                AssociationId=cidr_map[vpc_cidr]
                            )
                        except Exception as e:
                            logger.warning(f'  **Alert** {e}')
        else:
            # No vpc_cidrs list provided in the cleaup section 
            return

    @classmethod
    @retry(logger=logging.getLogger(__name__), tries=15, delay=60)
    def waitUntilVgwDetached(cls,ec2_client,vpc,cResources):
        logger = logging.getLogger(__name__)
        VpnGatewayId =''
        if not 'VGW' in cResources:
            return
        response = ec2_client.describe_vpn_gateways(
            Filters=[
                {
                    'Name': 'attachment.vpc-id',
                    'Values': [
                        vpc.id,
                    ]
                }
            ],
        )
        if len(response['VpnGateways']) == 0:
            return
        
        VpnGatewayId = response['VpnGateways'][0]['VpnGatewayId']
        if response['VpnGateways'][0]['VpcAttachments'][0]['State'] == 'detached':
            return
        elif response['VpnGateways'][0]['VpcAttachments'][0]['State'] == 'detaching':
            if not cls.DryRun:
                raise Exception(f'  {VpnGatewayId} is still detaching')


    NOT_YET = False
    DONE = True
    DEL_VIF = NOT_YET

    @classmethod
    @retry(logger=logging.getLogger(__name__), tries=15, delay=60)
    def deleteVif(cls, ec2_client, dc_client, vpc, cResources):
        logger = logging.getLogger(__name__)

        if not 'VGW' in cResources:
            return
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
        # check if no VpnGateways in the response
        if len(response['VpnGateways']) == 0:
            return

        VpnGatewayId = ''
        for Attr in response['VpnGateways']:
            if Attr['State'] != 'available':
                continue
            VpnGatewayId =  Attr['VpnGatewayId']

        if len(VpnGatewayId) == 0:
            return

        if cls.DEL_VIF == cls.NOT_YET:
            logger.info(f'- Discover VIF for {VpnGatewayId} in {vpc.id}')
            cls.DEL_VIF = cls.DONE

        response = dc_client.describe_virtual_interfaces()
        if len(response['virtualInterfaces']) == 0:
            logger.info(f'  No VIF found for {VpnGatewayId}')
            return

        vifLst = [ vif for vif in response['virtualInterfaces'] if vif['virtualGatewayId'] == VpnGatewayId ]

        if vifLst != None and len(vifLst) > 0:
            allDeleted = all([vif['virtualInterfaceState'] == 'deleted' for vif in vifLst])
            anyDeleting = any([vif['virtualInterfaceState'] == 'deleting' for vif in vifLst])            
            if allDeleted == True:
                for vif in vifLst:
                    logger.info(f'  {vif["virtualInterfaceId"]} is deleted')
            elif anyDeleting == True:
                vifIdLst = [vif['virtualInterfaceId'] for vif in vifLst if vif['virtualInterfaceState'] == 'deleting']
                if not cls.DryRun:
                    raise Exception(f'  Deleting {vifIdLst}')
                else:
                    logger.info(f'  Deleting {vifIdLst}')
            else:
                vifIdLst = [vif['virtualInterfaceId'] for vif in vifLst]
                if cls.DryRun:
                    logger.info(f'  Delete {vifIdLst}')
                else:
                    for vif in vifLst:
                        vifId = vif['virtualInterfaceId']
                        logger.info(f'  Delete {vifId}')
                        dc_client.delete_virtual_interface(virtualInterfaceId=vifId)
                    raise Exception(f'  Deleting {vifIdLst}')
        else:                
            logger.info(f'  No VIF found for {VpnGatewayId}')

    @classmethod
    @retry(botocore.exceptions.ClientError, tries=15, delay=60)
    def detachVpnGateway(cls, ec2_client, vpc, cResources):
        logger = logging.getLogger(__name__)
        VpnGatewayId =''
        if cResources != None:
            for entries in cResources:
                if entries.lower() != 'vgw':
                    continue
                response = ec2_client.describe_vpn_gateways(
                    Filters=[
                        {
                            'Name': 'attachment.vpc-id',
                            'Values': [
                                vpc.id,
                            ]
                        },
                        {
                            'Name': 'attachment.state',
                            'Values': [
                                'attached',
                            ]
                        },
                    ],
                )
                # check if no VpnGateways in the response
                if len(response['VpnGateways']) == 0:
                    return
                for Attr in response['VpnGateways']:
                    VpnGatewayId =  Attr['VpnGatewayId']
                logger.info(f'- Detach Virtual Private Gateway {VpnGatewayId}')
                try:    
                    if not cls.DryRun:
                        response = ec2_client.detach_vpn_gateway(
                            VpcId = vpc.id,
                            VpnGatewayId = VpnGatewayId
                        )      
                except botocore.exceptions.ClientError as e:
                    if 'Error' in e.response and 'Code' in e.response['Error']:
                        # 'Message': 'This call cannot be completed because there are pending VPNs or Virtual Interfaces'
                        # This occurs only when gateway association in direct connect gateway state is not completely associated.
                        if e.response['Error']['Code'] == 'InvalidParameterValue':
                            logger.info(f'  **Retrying** to detach the vgw in next 60 sec..')
                            raise e
                        else:
                            logger.error(f'  **Error** {e}')
        # No vgw resource provided in the cleaup section
        else:  
            return

    @classmethod
    @retry(botocore.exceptions.ClientError, tries=15, delay=60)
    def deleteVpnGateway(cls, ec2_client, vpc, cResources):
        logger = logging.getLogger(__name__)
        VpnGatewayId =''
        if cResources != None:
            if not 'VGW' in cResources:
                return
            response = ec2_client.describe_vpn_gateways(
                Filters=[
                    {
                        'Name': 'attachment.vpc-id',
                        'Values': [
                            vpc.id,
                        ]
                    },
                    # {
                    #     'Name': 'attachment.state',
                    #     'Values': [
                    #         'detaching',
                    #         'detached',
                    #     ]
                    # },
                ],
            )
            # check if no VpnGateways in the response
            if len(response['VpnGateways']) == 0:
                return
            for Attr in response['VpnGateways']:
                if Attr['State'] != 'available':
                    continue
                VpnGatewayId =  Attr['VpnGatewayId']
            if len(VpnGatewayId) == 0:
                logger.info(f'- VGW not found in {vpc.id}')
                return
            logger.info(f'- Delete {VpnGatewayId} in {vpc.id}')
            try:
                if cls.DryRun:
                    return    
                response = ec2_client.delete_vpn_gateway(
                    VpnGatewayId = VpnGatewayId
                )       
            except botocore.exceptions.ClientError as e:
                # This occurs when Dependency on DXGW asscociation.. takes 10min
                if 'Error' in e.response and 'Code' in e.response['Error']:
                    if e.response['Error']['Code'] == 'IncorrectState':
                        logger.info(f'  **Retrying** to delete the vgw in next 60 sec..')
                        raise e
                    else:
                        logger.error(f'  **Error** {e}')
        # No vgw resource provided in the cleaup section
        else:
            return

    @classmethod
    def deleteRevertFile(cls, accounts_data):
        logger = logging.getLogger(__name__)
        revert_file = ''
        target_folder = accounts_data['terraform']['terraform_output']
        logger.info(f'- Delete tmp/revert.json in local')
        if cls.DryRun:
            logger.info(f'- Delete tmp/revert.json in s3')
            return
        for account in accounts_data['account_info']:
            target_location = f"{target_folder}/{account['account_id']}"
            revert_file = f"{target_location}/tmp/revert.json"
            if os.path.isfile(revert_file):
                try:
                    os.remove(revert_file)
                except Exception as e:
                    logger.error(f"  Failed to delete the {revert_file} file {e}")
            aws.deleteBucketObj(accounts_data, target_location, 'tmp/revert.json')

    @classmethod
    def lookupOrgRouteTable(cls, vpc, rtb_target_rtb_map):
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
                    # 2) rtb_target_rtb_map stores: original rtb id => new rtb id
                    rtb_target_rtb_map[orgRouteTableId] = rtb.id
                else:
                    logger.warning(
                        f'  **Alert** cannot find org_<routeTableId> in the Org_RT tag of new route table {rtb.id}')
        # End of RTB iteration

    # NOT USED
    # To lookup VPC route tables specific to TGW attachment subnets 
    @classmethod
    def lookupVpcRouteTable_Tgw(cls, ec2_client, subnetIds):
        logger = logging.getLogger(__name__)
        count = 0
        TgwRtbId=[]
        if len(subnetIds) == 0:
            return
        logger.info(f'- Delete route tables associated with TGW')
        for subnet in subnetIds:
            try:
                response = ec2_client.describe_route_tables(
                    Filters=[
                        {
                            'Name': 'association.subnet-id',
                            'Values': [
                                subnet,
                            ]
                        },
                        {
                            'Name': 'association.main',
                            'Values': [
                                'false',
                            ]
                        },
                    ],
                )
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
            if len(response['RouteTables']) == 0:
                continue
            for Attr in response['RouteTables']:
                # Checking if subnet in the next iteration has association with same tgwid of previous iteration
                if Attr['RouteTableId'] not in TgwRtbId:
                    TgwRtbId.append(Attr['RouteTableId'])
                    for Assoc in Attr['Associations']:
                        # Checking if any other subnets are associated with this routetable apart from the provided subnetIds list
                        if Assoc['SubnetId'] not in subnetIds:
                            count =+ 1
        if cls.DryRun and count == 0:
            for rtb in TgwRtbId:
                logger.info(f'  Delete route table {rtb} ')
            return
        return TgwRtbId

    # NOT USED
    # To delete the VPC route tables specific to TGW Attachments subnets 
    @classmethod
    def deleteVpcRouteTable_Tgw(cls, ec2_client, vpc_Rtb_Tgw):
        logger = logging.getLogger(__name__)
        if cls.DryRun or len(vpc_Rtb_Tgw) == 0:
            return
        for rtbId in vpc_Rtb_Tgw:
            try:
                response = ec2_client.describe_route_tables(
                    RouteTableIds=[
                        rtbId,
                    ],
                )
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
            if response['RouteTables'] == []:
                logger.info(f'  Delete route table {rtb} ')
            try:
                response = ec2_client.delete_route_table(
                    RouteTableId=rtbId
                )
            except Exception as e:
                logger.warning(f'  **Alert** {e}')

    @classmethod
    def deleteRouteTable(cls, ec2_client, rtbId):
        logger = logging.getLogger(__name__)
        logger.info(
            f'  Delete route table {rtbId}')
        if cls.DryRun:
            return
        try:
            response = ec2_client.delete_route_table(
                RouteTableId=rtbId
            )
        except Exception as e:
            logger.warning(f'  **Alert** {e}')

    @classmethod
    def deleteVpcAttachement(cls, ec2_client, vpc, tgwId):
        logger = logging.getLogger(__name__)
        if tgwId == None:
            response = ec2_client.describe_transit_gateway_vpc_attachments(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc.id]},
                         {'Name': 'state', 'Values': [
                             'available']}
                         ]
            )
        else:
            response = ec2_client.describe_transit_gateway_vpc_attachments(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc.id]},
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'transit-gateway-id', 'Values': [tgwId]}
                ]
            )
        if len(response["TransitGatewayVpcAttachments"]) == 0:
            return
        for attachObj in response['TransitGatewayVpcAttachments']:
            tgwAttachmentId = attachObj['TransitGatewayAttachmentId']
            tgwIdInRecord = attachObj['TransitGatewayId']
            if tgwId != None and tgwIdInRecord == tgwId:
                response = ec2_client.describe_transit_gateway_route_tables(
                    Filters=[
                        {'Name': 'transit-gateway-id', 'Values': [tgwId]},
                        {'Name': 'state', 'Values': ['available']}
                    ]
                )
                logger.info(f'- Delete Transit Gateway Attachment {tgwAttachmentId}')
                if cls.DryRun:
                    continue
                try:
                    response = ec2_client.delete_transit_gateway_vpc_attachment(
                        TransitGatewayAttachmentId=tgwAttachmentId
                    )
                except Exception as e:
                    logger.warning(f'  **Alert** {e}')

    @classmethod
    def deleteTgwWithAccountId(cls, ec2_client, accountId, tgwList):
        logger = logging.getLogger(__name__)
        response = ec2_client.describe_transit_gateways(
            Filters=[
                {
                    'Name': 'owner-id',
                    'Values': [
                        accountId,
                    ]
                },
            ],
        )
        for tgw in response['TransitGateways']:
            cls.deleteTgwWithId(ec2_client, tgw['TransitGatewayId'], tgwList)

    @classmethod
    def deleteTgwWithId(cls, ec2_client, tgwId, tgwList):
        logger = logging.getLogger(__name__)
        if tgwId in tgwList:
            response = ec2_client.describe_transit_gateways(
                TransitGatewayIds=[
                    tgwId,
                ],
            )
            if len(response['TransitGateways']) == 0:
                logger.warning(
                    f'  **Alert** cannot delete {tgwId} because it does not exist')
                return
            elif response['TransitGateways'][0]['State'] == 'deleted':
                logger.warning(
                    f'  **Alert** cannot delete {tgwId} because it has been deleted')
                return

            try:
                response = ec2_client.describe_transit_gateway_vpc_attachments(
                    Filters=[
                        {
                            'Name': 'transit-gateway-id',
                            'Values': [
                                tgwId,
                            ]
                        },
                    ],
                )
            except Exception as e:
                logger.warning(f'  **Alert** {e}')
            if len(response['TransitGatewayVpcAttachments']) > 0:
                logger.warning(
                    f'  **Alert** cannot delete {tgwId}. There are still vpc attachment(s) connected to it')
                for x in response['TransitGatewayVpcAttachments']:
                    logger.warning(
                        f"  **Alert**   {x['TransitGatewayAttachmentId']} to {tgwId}")
            else:
                logger.info(f'- Delete {tgwId}')
                if cls.DryRun:
                    return
                try:
                    response = ec2_client.delete_transit_gateway(
                        TransitGatewayId=tgwId,
                    )
                except Exception as e:
                    logger.warning(f'  **Alert** {e}')
        else:
            logger.warning(
                f'  **Alert** cannot delete {tgwId} because it is not in {tgwList}')
