import boto3
import logging
import sys
import yaml
import json
import os
from os import makedirs
from os import path
import getpass
import dm.logconf as logconf
import ipaddress

class Common:

    # Convert input yaml into json
    @classmethod
    def convert_yaml_to_json(cls, file_path):
        with open(file_path, 'r') as fh:
            json_data = json.dumps(yaml.load(fh, Loader=yaml.FullLoader))
            json_data = json.loads(json_data)
        return(json_data)

    # Build role_arn
    @classmethod
    def get_role_arn(cls, account_info):
        account_num = account_info['account_id']
        role_name = account_info['role_name']
        role_arn = "arn:aws:iam::"+account_num+":role/"+role_name
        return(role_arn)

    # Get temp session using sts
    @classmethod
    def get_temp_creds_for_account(cls, role_arn, region_name='us-east-1', creds=None):
        logger = logging.getLogger(__name__)
        try:
            if creds == None:
                #
                # This is a STS call that invokes regional STS endpoint, using region us-east-1 by default.
                # This is the minimal workaround without revising each call to pass in a region.
                #
                # Reason: Use regional STS endpoint instead of the original global STS endpoint:
                #
                # - Regional endpoint returns a token compatible for all regions including regions (such as
                # Hong Kong) that are activated manually.
                # - Global endpoint (without region argument) returns a token only compatible to region enabled by default,
                # not including Hong Kong.
                #
                # Reference:
                # https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_enable-regions.html#sts-regions-manage-tokens
                #
                sts_client = boto3.client('sts', region_name=region_name, endpoint_url=f'https://sts.{region_name}.amazonaws.com')                
            else:
                sts_client = boto3.client('sts',
                    region_name=region_name,
                    endpoint_url=f'https://sts.{region_name}.amazonaws.com',
                    aws_access_key_id=creds['AccessKeyId'],
                    aws_secret_access_key=creds['SecretAccessKey'],
                    aws_session_token=creds['SessionToken']
                )
            assumed_role = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName="AssumeRoleSession1")
        except Exception as e:
            logger.error(e)
            sys.exit(1)
        creds = assumed_role['Credentials']
        return(creds)

    @classmethod
    def getTgwByRegion(cls, accounts_data):
        tgw_by_region = {}
        if 'tgw' in accounts_data and 'tgw_by_region' in accounts_data['tgw'] and accounts_data['tgw']['tgw_by_region'] != None:
            tgw_by_region = accounts_data['tgw']['tgw_by_region']
        return tgw_by_region

    @classmethod
    def getVpcCidrs(cls, accounts_data):
        vpc_cidrs = None
        if 'cleanup' in accounts_data and 'vpc_cidrs' in accounts_data['cleanup'] and len(accounts_data['cleanup']['vpc_cidrs']) > 0:
            vpc_cidrs = accounts_data['cleanup']['vpc_cidrs']
        return vpc_cidrs

    @classmethod
    def getCleanupResources(cls, accounts_data):
        resources = None
        try:
            # e.g.:
            # cleanup:
            #   resources: ["VGW"]
            resources = accounts_data['cleanup']['resources']
        except:
            return None
        return resources

    @classmethod
    def getTgwInGivenRegion(cls, regionObj, accounts_data, accountId):
        logger = logging.getLogger(__name__)

        tgw_by_region = cls.getTgwByRegion(accounts_data)
        tgw = None
        account_region = regionObj['region']
        if account_region in tgw_by_region:
            tgw = tgw_by_region[account_region]

        # diy_tgw_id in region overrides tgw_by_region
        if 'diy_tgw_id' in regionObj:
            tgw = regionObj['diy_tgw_id']
        
        if tgw == None:
            logger.warning(f'**Alert** missing tgw info for {accountId} in {account_region}')
        return tgw

    @classmethod
    def getS3BucketInfo(cls,yamlObj):
        logger = logging.getLogger(__name__)
        s3AccountNo = None
        s3Region = None
        s3RoleName = None
        try:
            s3Region = yamlObj['aws']['s3']['region']
            s3RoleName = yamlObj['aws']['s3']['role_name']
            s3AccountNo = yamlObj['aws']['s3']['account']   
        except Exception as e: 
            logger.warning(f'  **Alert** Failed to read S3 attribute(s) in yaml')
        return s3AccountNo, s3Region, s3RoleName

    @classmethod
    def getS3BucketName(cls,yamlObj):
        logger = logging.getLogger(__name__)
        s3BucketName = None
        try:
            s3BucketName = yamlObj['aws']['s3']['name']
        except Exception as e: 
            logger.warning(f'  **Alert** Failed to read S3 name attribute in yaml')
        return s3BucketName

    @classmethod
    def getDiyEc2Client(cls, ec2_client, regionObj, accounts_data):
        tgw_by_region = cls.getTgwByRegion(accounts_data)

        ec2_client_main = ec2_client

        if 'tgw' in accounts_data and 'tgw_account' in accounts_data['tgw'] and accounts_data['tgw']['tgw_account'] != None \
            and 'tgw_role' in accounts_data['tgw'] and accounts_data['tgw']['tgw_role'] != None:
            tgw_account = accounts_data['tgw']['tgw_account']
            tgw_role = accounts_data['tgw']['tgw_role']
            role_arn = "arn:aws:iam::" + tgw_account + ":role/" + tgw_role
            creds = cls.get_temp_creds_for_account(role_arn)
            ec2_resource_main = cls.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client_main = ec2_resource_main.meta.client

        if 'diy_tgw_account' in regionObj and 'diy_tgw_role' in regionObj:
            role_arn = "arn:aws:iam::" + \
                regionObj['diy_tgw_account'] + \
                ":role/"+regionObj['diy_tgw_role']
            creds = cls.get_temp_creds_for_account(role_arn)
            ec2_resource_main = cls.get_ec2_resource_handler(
                regionObj['region'], creds)
            ec2_client_main = ec2_resource_main.meta.client
        return ec2_client_main

    # Create ec2 handler

    @classmethod
    def get_ec2_resource_handler(cls, aws_region, creds):
        ec2_resource = boto3.resource(
            'ec2',
            region_name=aws_region,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        return(ec2_resource)

    @classmethod
    def get_dc_client_handler(cls, aws_region, creds):
        dc_client = boto3.client(
            'directconnect',
            region_name=aws_region,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        return(dc_client)

    @classmethod
    def get_sq_client_handler(cls, aws_region, creds):
        sq_client = boto3.client(
            'service-quotas',
            region_name=aws_region,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        return(sq_client)

    @classmethod
    def get_s3_resource_handler(cls, aws_region, creds):
        s3_resource = boto3.resource(
            's3',
            region_name=aws_region,
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken']
        )

        return(s3_resource)

    @classmethod
    def getFilterAttachmentSubnetFlag(cls, yamlObj):
        flag = False
        try:
            flag = yamlObj['config']['filter_tgw_attachment_subnet']
        except KeyError:
            pass
        return flag

    @classmethod
    def getExpectVpcPrefixes(cls, yamlObj):
        """
        expect_vpc_prefixes: Alert VPC cidr NOT fall within the given CIDR ranges
        """
        expectVpcPrefixes = []
        try:
            lst = yamlObj['alert']['expect_vpc_prefixes']
            expectVpcPrefixes = [ipaddress.ip_network(x) for x in lst]
        except:
            return []
        return expectVpcPrefixes

    @classmethod
    def getExpectDestCidrs(cls, yamlObj):
        """
        expect_dest_cidrs: Alert Route within given cidrs
        """
        expectDestCidrs = []
        try:
            expectDestCidrs = yamlObj['alert']['expect_dest_cidrs']
        except:
            return []
        return expectDestCidrs

    HEX_CIDR = 1
    VPC_NAME = 2

    @classmethod
    def getGwNameFormat(cls, yamlObj):
        algo = cls.HEX_CIDR
        try:
            algoStr = yamlObj['config']['spoke_gw_name_format']
            if algoStr == 'VPC_NAME':
                algo = cls.VPC_NAME
        except KeyError:
            pass
        return algo

    @classmethod
    def getAllowVpcCidr(cls, yamlObj):
        """
        allow_vpc_cidrs: filter out VPC CIDR not in given list
        """
        allowVpcCidrs = [ipaddress.ip_network("0.0.0.0/0")]
        try:
            lst = yamlObj['config']['allow_vpc_cidrs']
            allowVpcCidrs = [ipaddress.ip_network(x) for x in lst]
        except:
            return [ipaddress.ip_network("0.0.0.0/0")]
        return allowVpcCidrs

    @classmethod
    def getFilterCidrs(cls, yamlAccountObj):
        """
        filter_cidrs: filter out route within given cidr list
        """
        filterCidrs = []
        try:
            filterCidrs = yamlAccountObj['filter_cidrs']
        except:
            return []
        return filterCidrs

    @classmethod
    def getAvtxCidr(cls, vpcsInRegionObj, vpcId):
        avtx_cidr = ""
        if len(vpcsInRegionObj) > 0 and 'avtx_cidr' in vpcsInRegionObj[vpcId] and not vpcsInRegionObj[vpcId]['avtx_cidr'] == None:
            avtx_cidr = vpcsInRegionObj[vpcId]['avtx_cidr']
        return avtx_cidr

    @classmethod
    def getSubnetTags(cls, yamlObj):
        tagList = []
        try:
            tagsList = yamlObj['config']['subnet_tags']
            for tag in tagsList:
                key = tag['key']
                val = tag['value']
                tagList.append({'Key': key, 'Value': val})
        except:
            return []
        return tagList

    @classmethod
    def getRouteTableTags(cls, yamlObj):
        tagList = []
        try:
            tagsList = yamlObj['config']['route_table_tags']
            for tag in tagsList:
                key = tag['key'] 
                val = tag['value']
                tagList.append({'Key': key, 'Value': val})
        except:
            return []
        return tagList

    @classmethod
    def getTgwDeleteRouteDelay(cls, yamlObj):
        delay = 5
        try:
            delayStr = yamlObj['switch_traffic']['delete_tgw_route_delay']
            delay = int(delayStr)
        except KeyError:
            return 5
        return delay

    @classmethod
    def getEnableS3Backend(cls, yamlObj):
        flag = True
        try:
            flag = yamlObj['terraform']['enable_s3_backend']
        except KeyError:
            return True
        return flag

    @classmethod
    def logCommandOptions(cls, command):
        logger = logging.getLogger(__name__)
        logger.warning("")
        logger.warning("".ljust(45, "#"))
        logger.warning("")
        logger.warning(command)
        logger.warning("")
        logger.warning("".ljust(45, "#"))
        logger.warning("")

    @classmethod
    def logAccountHeader(cls, account):
        logger = logging.getLogger(__name__)
        logger.warning("")
        logger.warning("".ljust(45, "+"))
        logger.warning("")
        logger.warning(f"    Account ID :  {account['account_id']}")
        logger.warning(f"    Role       :  {account['role_name']}")
        logger.warning("")
        logger.warning("".ljust(45, "+"))
        logger.warning("")

    @classmethod
    def logRegionHeader(cls, regionObj):
        logger = logging.getLogger(__name__)
        logger.info("")
        logger.info("".ljust(45, "="))
        logger.info("") 
        logger.info(f"    Region     :  {regionObj['region']}")
        logger.info("")
        logger.info("".ljust(45, "="))
        logger.info("")

    @classmethod
    def logVpcHeader(cls, vpc):
        logger = logging.getLogger(__name__)
        ntag = []
        if vpc.tags:
            ntag = [tag["Value"]
                    for tag in vpc.tags if tag["Key"] == "Name"]

        cidrs = [cidr['CidrBlock']
                 for cidr in vpc.cidr_block_association_set]

        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")
        vpcName = ""
        if (len(ntag) > 0):
            vpcName = ntag[0]
            logger.info(f"    Vpc Name : {ntag[0]}")
        else:
            logger.info(f"    Vpc Name :")
        logger.info(f"    Vpc ID   : {vpc.id}")
        logger.info(f"    CIDRs    : {cidrs}")
        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")
        return vpcName

    @classmethod
    def logVgwRemovalHeader(cls):
        logger = logging.getLogger(__name__)

        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")
        logger.info(f"    Delete VGWs")
        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")

    @classmethod
    def getVpcsInRegion(cls, regionObj):
        vpcsInRegionObj = {}
        if regionObj['vpcs']:
            for x in regionObj['vpcs']:
                vpcId = x['vpc_id']
                vpcsInRegionObj[vpcId] = {}
                if 'avtx_cidr' in x:
                    vpcsInRegionObj[vpcId]['avtx_cidr'] = x['avtx_cidr']
                if 'gw_zones' in x:
                    vpcsInRegionObj[vpcId]['gw_zones'] = x['gw_zones']
        return vpcsInRegionObj

    @classmethod
    def getCtrlCredential(cls, args):
        logger = logging.getLogger(__name__)

        ctrl_user = os.environ.get('aviatrix_controller_user')
        ctrl_pwd = os.environ.get('aviatrix_controller_password')

        if args.ctrl_user:
            ctrl_user = args.ctrl_user
            ctrl_pwd = getpass.getpass(prompt="Aviatrix Controller Password:")
        else:
            if ctrl_user == None or ctrl_pwd == None:
                logger.error(f'tgw migration requires Aviatrix controller username: --ctrl_user <user>')
                sys.exit(1)
        
        return ctrl_user, ctrl_pwd

    @classmethod
    def initLogLocation(cls, accounts_data):
        target_folder = accounts_data['terraform']['terraform_output']
        logFolder = f'{target_folder}/log'
        if not path.exists(logFolder):
            makedirs(logFolder)
        logconf.logging_config['handlers']['logConsoleHandler']['filename'] = f'{logFolder}/dm.log'
        logconf.logging_config['handlers']['alertHandler']['filename'] = f'{logFolder}/dm.alert.log'
        return logconf

    @classmethod
    def getLabel(cls, accounts_data):
        logger = logging.getLogger(__name__)
        try:
            return accounts_data['label']
        except:
            logger.info(f'**alert** attribute "label" missing')
            return None


        