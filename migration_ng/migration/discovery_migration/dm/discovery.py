#!/usr/bin/python3

import logging
import logging.config
import sys
import os
import ipaddress
import argparse
import getpass
from dm.terraform import Terraform as tf
from dm.routetables import RouteTables
from dm.discoverylib import DiscoveryLib as dl
from dm.commonlib import Common as common
from dm.aviatrix import Aviatrix as av
from dm.aws import Aws as aws

if __name__ == "__main__":
    # logging.config.fileConfig(fname='dm/log.conf')

    args_parser = argparse.ArgumentParser(
        description='Get VPC info from account(s)')
    args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    # args_parser.add_argument(
    #     '--ctrl_user', help='Aviatrix Controller username')
    args_parser.add_argument(
        '--s3backup', help='At the end of discovery, backup all generated files into S3', action='store_true', default=False)
    args_parser.add_argument(
        '--tfvars_json', help='Output route table in tfvars.json', action='store_true', default=False)
    args = args_parser.parse_args()
    input_file = args.file_path
    if not os.path.isfile(input_file):
        print('YAML File does not exist')
        sys.exit()
    
    ## setup logging
    accounts_data = common.convert_yaml_to_json(input_file)
    logconf = common.initLogLocation(accounts_data)
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.discovery {iargs}')

    ## create bucket if needed
    if aws.createBucketIfneeded(accounts_data) == False:
        sys.exit()

    ##
    target_folder = accounts_data['terraform']['terraform_output']
    vpcAid2GwNameMap = {}
    tfVersion = accounts_data['terraform']['terraform_version']
    avxProvider = accounts_data['terraform']['aviatrix_provider']
    awsProvider = accounts_data['terraform']['aws_provider']

    YAML = {
        'subnet_tags' : common.getSubnetTags(accounts_data),
        'route_table_tags' : common.getRouteTableTags(accounts_data),
        'filter_tgw_attachment_subnet' : common.getFilterAttachmentSubnetFlag(accounts_data),
        'gw_name_format': common.getGwNameFormat(accounts_data),
        'expect_vpc_prefixes': common.getExpectVpcPrefixes(accounts_data),
        'expect_dest_cidrs': common.getExpectDestCidrs(accounts_data),
        'allow_vpc_cidrs': common.getAllowVpcCidr(accounts_data),
        'enable_s3_backend': common.getEnableS3Backend(accounts_data)
    }

    tf.generateModuleFolder(target_folder,YAML['gw_name_format'])
    tf.generateModuleVersionsTf(target_folder, {
        'terraform_version': f'"{tfVersion}"',
        'aviatrix_provider': f'"{avxProvider}"',
        'aws_provider': f'"{awsProvider}"'
    })

    # Start iterating over the input yaml
    # expect_dest_cidrs = []
    # expect_vpc_prefixes = []
    # if 'alert' in accounts_data:
    #     if 'expect_dest_cidrs' in accounts_data['alert']:
    #         expect_dest_cidrs = accounts_data['alert']['expect_dest_cidrs']
        # if 'expect_vpc_prefixes' in accounts_data['alert']:
        #     lst = accounts_data['alert']['expect_vpc_prefixes']
        #     expect_vpc_prefixes = [ipaddress.ip_network(x) for x in lst]

    for account in accounts_data['account_info']:
        target_location = f"{target_folder}/{account['account_id']}"

        tf.setupAccountFolder(target_location,YAML)        
        tf.generateVersionTf({
            'terraform_version': f'"{tfVersion}"',
            'aviatrix_provider': f'"{avxProvider}"',
            'aws_provider': f'"{awsProvider}"'
        })
        tf.copyYaml(f'{target_location}/tmp', input_file)
        tf.generateTfVars({
            'account_id': account['account_id'],
            'aws_account_role': account['role_name'],
            'controller_ip': accounts_data['aviatrix']['controller_ip'],
            'controller_account': accounts_data['aviatrix']['controller_account'],
            'ctrl_role_app': accounts_data['aviatrix']['ctrl_role_app'],
            'ctrl_role_ec2': accounts_data['aviatrix']['ctrl_role_ec2'],
            'gateway_role_app': accounts_data['aviatrix']['gateway_role_app'],
            'gateway_role_ec2': accounts_data['aviatrix']['gateway_role_ec2']
        })

        role_arn = common.get_role_arn(account)
        creds = common.get_temp_creds_for_account(role_arn)

        common.logAccountHeader(account)

        vpcDupNameCount = {}
        if YAML['gw_name_format'] == common.VPC_NAME:
            # check VPC with duplicate name
            # vpcDupNameCount stores the current suffix count for duplicate VPC Name
            vpcDupNameCount = dl.checkVpcsDuplicateName(account, creds)

        tf.deleteTfImport()
        tf.deleteUndoSubnetsTfImport()

        for regionObj in account['regions']:
            common.logRegionHeader(regionObj)

            account_region = regionObj['region']
            dl.setRegion(account_region)

            tgwInRegion = common.getTgwInGivenRegion(regionObj,accounts_data,account['account_id'])
            expect_tgws = []
            if tgwInRegion != None:
                expect_tgws = [tgwInRegion]
            
            ec2_resource = common.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client = ec2_resource.meta.client

            vpcs = ec2_resource.vpcs.all()

            # update providers.tf
            regionAlias = regionObj['region']
            regionAlias = regionAlias.replace("-", "_")
            regionAlias = f'spoke_{regionAlias}'

            regionInfo = {
                'region': regionObj['region'],
                'alias': regionAlias
            }

            vpcsInRegionObj = common.getVpcsInRegion(regionObj)

            dl.checkEipUsage(ec2_client, vpcsInRegionObj, vpcs)
            dl.discoverTgw(ec2_client)
            dl.discoverVgw(ec2_client)
            dl.discoverIgw(ec2_client)
            dl.discoverNatGw(ec2_client)
            dl.discoverEndpoint(ec2_client)
            dl.discoverPeering(ec2_client)

            for vpc in vpcs:
                # If subset of VPCs specified
                if len(vpcsInRegionObj) > 0 and vpc.id not in vpcsInRegionObj:
                    continue
                vpcName = common.logVpcHeader(vpc)
                logger.warning(f"- Process {regionObj['region']}/{vpc.id}")

                if dl.discoverSpokeGw(ec2_client,vpc.id) == True:
                    sys.exit(1)

                new_rtbs = []
                rtb_subnets = {}
                routeTables = RouteTables(vpc.id)
                YAML['filter_cidrs'] = common.getFilterCidrs(account)
                # if 'filter_cidrs' in account:
                    # routeTables.setFilterCidrs(account['filter_cidrs'])
                routeTables.setFilterCidrs(YAML['filter_cidrs'])
                routeTables.setExpectedCidrs(YAML['expect_dest_cidrs'])
                routeTables.setTgwList(expect_tgws)

                # Check if IGW exists
                igwId = dl.checkVpcForIgw(ec2_client, vpc)

                # alert (p): Site-to-site VPN connections associated with VGW attached to the VPC
                dl.checkVpnConnection(ec2_client, vpc)

                # for gw_name with suffix, store it in a map: vpc.id-account.id => gw_name
                gw_name_suffix_tfstr = ""
                if YAML['gw_name_format'] == common.VPC_NAME:
                    gw_name_suffix_tfstr = f'gw_name_suffix = ""'
                    if vpcName in vpcDupNameCount:
                        vpcDupNameCount[vpcName] = vpcDupNameCount[vpcName] + 1
                        gw_name_suffix = vpcDupNameCount[vpcName]
                        gw_name_suffix_tfstr = f'gw_name_suffix = "{gw_name_suffix}"'
                        key = f"{vpc.id}-{account['account_id']}"
                        vpcAid2GwNameMap[key] = f"{vpcName}-{account['account_id']}-{gw_name_suffix}-gw"

                # get attachement subnets
                attachmentSubnets = []
                if YAML['filter_tgw_attachment_subnet']:
                    attachmentSubnets = aws.getTgwAttachementSubnets(ec2_client, vpc, tgwInRegion)

                # Check number of Cidrs associated VPC
                vpc_cidrs = dl.discoverVpcCidr(ec2_client, vpc, YAML)

                dl.discoverRouteTables(ec2_client, vpc, vpc_cidrs, routeTables, attachmentSubnets, YAML)

                # filter attachement subnets
                subnetsObj = dl.discoverSubnets(ec2_client, vpc, routeTables, regionInfo, attachmentSubnets, YAML)

                # Check AZ if defined
                gw_zones = []
                if len(vpcsInRegionObj) > 0 and 'gw_zones' in vpcsInRegionObj[vpc.id] and not vpcsInRegionObj[vpc.id]['gw_zones'] == None:
                    gw_zones = dl.checkAz(
                        ec2_client, regionObj['region'], vpcsInRegionObj[vpc.id]['gw_zones'])
                    if len(gw_zones) == 0:
                        gw_zones = dl.discoverAz(ec2_client, routeTables, vpc, gw_zones, attachmentSubnets)
                    elif len(gw_zones) == 1:
                        discover_gw_zones = dl.discoverAz(
                            ec2_client, routeTables, vpc, gw_zones, attachmentSubnets)
                        gw_zones.append(discover_gw_zones[0])
                    elif len(gw_zones) >= 2:
                        gw_zones = gw_zones[:2]
                else:
                    gw_zones = dl.discoverAz(ec2_client, routeTables, vpc, gw_zones, attachmentSubnets)

                avtx_cidr = ""
                if len(vpcsInRegionObj) > 0 and 'avtx_cidr' in vpcsInRegionObj[vpc.id] and not vpcsInRegionObj[vpc.id]['avtx_cidr'] == None:
                    avtx_cidr = vpcsInRegionObj[vpc.id]['avtx_cidr']

                # Determine if there are any VPC peering connections
                # dl.checkVpcForPeerings(vpc)

                #
                # generate vpc_id.tf
                #
                vpcTfData = {
                    'vpc_id': vpc.id,
                    'vpc_name': vpcName,
                    'igw_id': igwId,
                    'avtx_cidr': avtx_cidr,
                    'hpe': str(account['hpe']).lower(),
                    'avtx_gw_size': account['spoke_gw_size'],
                    'region': regionObj['region'],
                    'route_tables': f'route_tables_{vpc.id}',
                    'providers': f'aws.{regionAlias}',
                    'gw_zones': f'{gw_zones}'.replace("'", "\""),
                    'vpc_cidr': f'{vpc_cidrs}'.replace("'", "\""),
                    'avtx_cidr': f'{avtx_cidr}',
                    'gw_name_suffix': gw_name_suffix_tfstr
                }
                tf.generateVpcTf(vpcTfData)
                tfName = f"aws-{regionObj['region']}-{vpc.id}.tf"
                logger.info(f"- Generate {tfName}")
                if YAML['gw_name_format'] == common.VPC_NAME and len(vpcName) > dl.VPC_NAME_MAX_LENGTH:
                    logger.warning(
                        f'  **Alert** Please modify the VPC name in {tfName} before running terraform apply. VPC name has to be shorter than {dl.VPC_NAME_MAX_LENGTH+1} characters.')

                if args.tfvars_json:
                    tf.routeTablesToDict(
                        regionObj['region'], vpc.id, routeTables)
                else:
                    tf.routeTablesToHcl(
                        regionObj['region'], vpc.id, routeTables)
                    tf.subnetsToHcl(regionObj['region'], vpc.id, subnetsObj)
                    tf.subnetsToTfImport(subnetsObj)
                    tf.undoSubnetsToTfImport(vpc.id, subnetsObj)
                tfName = f"aws-{regionObj['region']}-{vpc.id}.auto.tfvars"
                logger.info(f"- Generate {tfName}")

        if len(vpcAid2GwNameMap) > 0:
            tf.storeJsonInfo("gw-name.json", vpcAid2GwNameMap)
        if args.s3backup:
            aws.uploadAllFiles('discovery',accounts_data, target_location)