#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import argparse

from dm.commonlib import Common as common
from dm.aws import Aws as aws
from dm.cleanuplib import CleanUp as cu
import dm.logconf as logconf
from dm.routetables import RouteTables
from dm.discoverylib import DiscoveryLib as dl

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(
        description='Delete origin route tables, VPC attachments and TGWs after migration')
    args_parser.add_argument(
        '--s3_yaml_download', help='a list of comma separated strings in the form: <s3_account>,<s3_role>,<s3_bucket>,<spoke_account>')
    args_parser.add_argument(
        '--yaml_file', help='specify input <yaml_file>')
    args_parser.add_argument(
        '--dry_run', help='Dry run cleanup logic and show what will be done', action='store_true', default=False)
    args = args_parser.parse_args()

    if args.dry_run:
        cu.setDryRun()

    input_file = ''
    if args.s3_yaml_download != None:
        if not aws.downloadS3Yaml(args.s3_yaml_download):
            print(f'Failed to download YAML File from S3 using the yaml info: {args.s3_yaml_download}')
            sys.exit()
        input_file = '/tmp/discovery.yaml'
    elif args.yaml_file:
        input_file = args.yaml_file
    else:
        print('Missing input yaml! Please use --s3_yaml_download to download from S3  or --yaml_file to specify the local filename')

    if not os.path.isfile(input_file):
        print(f'YAML File {input_file} does not exist')
        sys.exit()

    accounts_data = common.convert_yaml_to_json(input_file)
    logconf = common.initLogLocation(accounts_data)
    logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO    
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.cleanup {iargs}')

    if 'cleanup' not in accounts_data:
        logger.error('Cleanup section in YAML File does not exist')
        sys.exit()

    # 1) Delete revert.json file
    cu.deleteRevertFile(accounts_data)

    # Start iterating over the input yaml
    for account in accounts_data['account_info']:
        common.logAccountHeader(account)        
        role_arn = common.get_role_arn(account)
        creds = common.get_temp_creds_for_account(role_arn)

        for regionObj in account['regions']:
            common.logRegionHeader(regionObj)
            ec2_resource = common.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client = ec2_resource.meta.client
            # ec2_client_diy = common.getDiyEc2Client(ec2_client, regionObj, accounts_data)
            tgwInRegion = common.getTgwInGivenRegion(regionObj,accounts_data,account['account_id'])
            vpcsInRegionObj = common.getVpcsInRegion(regionObj)
            vpc_cidrs = common.getVpcCidrs(accounts_data)
            cleanupResources = common.getCleanupResources(accounts_data)
            vpcs = ec2_resource.vpcs.all()
            for vpc in vpcs:
                # If subset of VPCs specified
                if len(vpcsInRegionObj) > 0 and vpc.id not in vpcsInRegionObj:
                    continue
                common.logVpcHeader(vpc)
                logger.warning(f"- Process {regionObj['region']}/{vpc.id}")

                # 2) Delete origin route table
                rtb_target_rtb_map = {}
                cu.lookupOrgRouteTable(vpc, rtb_target_rtb_map)
                logger.info(f'- Delete original route tables')
                for rtbId in rtb_target_rtb_map.keys():
                    cu.deleteRouteTable(ec2_client, rtbId)

                # 3) Fetch TGW Attachment subnets and Delete VPC attachment
                VpcAttachmentSubnets = []
                if accounts_data['config']['filter_tgw_attachment_subnet'] == True:
                    VpcAttachmentSubnets = aws.getTgwAttachementSubnets(ec2_client, vpc, tgwInRegion)
                    cu.deleteVpcAttachement(ec2_client, vpc, tgwInRegion)                

                    # 4) Delete TGW Attachment Subnets
                    try:
                        cu.deleteSubnet(ec2_client, VpcAttachmentSubnets)
                    except Exception as e:
                        logger.error(f'  **Error** {e}')

                # 5) Delete all route tables that are not associated with any subnets, except main route table.
                # rtbAssoCountXcldVpcAttchSub i.e Count of total subnet associations with a route table excluding VPC attachment subnet associations  
                # Always use rtbAssoCountXcldVpcAttchSub. Since attachment subnets are deleted prior to invoking this call
                # rtbAssoCountXcldVpcAttchSub will give you the right result even during the dry run.

                # Its a just a dummy object to use discoverSubnetAssociations
                routeTables = RouteTables(vpc.id)
                logger.info(f'- Delete all non associated route tables')
                for rtb in vpc.route_tables.all():
                    isMainRTB, orgAssociationCount, rtbAssoCountXcldVpcAttchSub = dl.discoverSubnetAssociations(routeTables, rtb, VpcAttachmentSubnets)
                    if isMainRTB == False and rtbAssoCountXcldVpcAttchSub == 0:
                        cu.deleteRouteTable(ec2_client, rtb.id)

                # 6) Delete VPC CIDR
                cu.deleteVpcCidr(ec2_client, vpc, vpc_cidrs)

                # 7) Detach VGW
                try:
                    cu.detachVpnGateway(ec2_client, vpc, cleanupResources)
                except Exception as e:
                    logger.error(f'  **Error** {e}')

            # End of vpcs iteration

            # 8) Delete VGW
            # Detaching VGW takes ~12min if the resource is associated with DXGW belore deleting, so detaching is invoked prior to deleting all the VPC's
            # which gives buffer time to validate if VGW is detached. 
            dc_client = common.get_dc_client_handler(regionObj['region'], creds)
            common.logVgwRemovalHeader()                  
            for vpc in vpcs:
                if len(vpcsInRegionObj) > 0 and vpc.id not in vpcsInRegionObj:
                    continue

                try:
                    cu.waitUntilVgwDetached(ec2_client, vpc, cleanupResources)
                except Exception as e:
                    logger.info(f'  Detaching VGW takes 10-15 minutes. Please try to rerun dm.cleanup after 30 min to make sure VGW is deleted.')
                    continue

                try:
                    cu.DEL_VIF = cu.NOT_YET
                    cu.deleteVif(ec2_client, dc_client, vpc, cleanupResources)                    
                    cu.deleteVpnGateway(ec2_client, vpc, cleanupResources)
                except Exception as e:
                    if 'Error' in e.response and 'Code' in e.response['Error']:
                        if e.response['Error']['Code'] == 'IncorrectState':
                            logger.info(f'  Deleting VGW takes 10-15 minutes. Please try to rerun dm.cleanup after 30 min to make sure VGW is deleted.')
    
            # 9) Delete TGW
            # tgwList = accounts_data['tgw']
            # if regionObj['diy_tgw_id'] != None:
            #     tgwId = regionObj['diy_tgw_id']
            #     if not tgwId in tgwList:
            #         logger.warning(
            #             f'  **Alert** cannot delete {tgwId} because it is not in {tgwList}')
            #     else:
            #         cu.deleteTgwWithId(ec2_client_diy, tgwId, tgwList)
            # elif regionObj['diy_tgw_account'] != None:
            #     cu.deleteTgwWithAccountId(
            #         ec2_client_diy, regionObj['diy_tgw_account'], tgwList)
            # else:
            #     cu.deleteTgwWithAccountId(
            #         ec2_client_diy, account['account_id'], tgwList)

        # End of account['regions'] iteration
    # End of accounts_data['account_info'] iteration