import logging
import botocore
import boto3
from os import listdir
from os import path, makedirs, walk
from dm.terraform import Terraform as tf
from dm.commonlib import Common as common

class Aws:

    DryRun = False

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def updateSubnetAssociation(cls, revert, ec2_client, region, regionAlias, vpcId, rtb_target_rtb_map, rtb_assocs_map):
        logger = logging.getLogger(__name__)
        if len(rtb_target_rtb_map.keys()) == 0:
            logger.info(f'- Switch subnet(s)')
            logger.warning(
                f'  **Alert** no subnet needs to be switched in {vpcId}')
        for rtb in rtb_target_rtb_map.keys():
            logger.info(
                f'- Switch subnet(s) from {rtb} to {rtb_target_rtb_map[rtb]}')
            if not rtb in rtb_assocs_map:
                logger.warning(f'  **Alert** {rtb} not found')
                continue
            if len(rtb_assocs_map[rtb]) == 0:
                logger.warning(f'  **Alert** no subnets associated with {rtb}')
            for assoc in rtb_assocs_map[rtb]:
                # RouteTableAssociation object without Subnet ID defines Main Route Table
                if 'SubnetId' in assoc:
                    logger.info(
                        f"  {assoc['RouteTableAssociationId']} {assoc['SubnetId']}")
                    if revert == False:
                        tf.createSubnetAssociationTf({
                            'region': region,
                            'vpc_id': vpcId,
                            'rname': f"{assoc['SubnetId']}_{rtb_target_rtb_map[rtb]}",
                            'subnet_id': assoc['SubnetId'],
                            'route_table_id': rtb_target_rtb_map[rtb],
                            'provider': f'aws.{regionAlias}'
                        })
                else:
                    logger.info(f"  {assoc['RouteTableAssociationId']} Main")
                    if revert == False:
                        tf.createMainRtbAssociationTf({
                            'region': region,
                            'rname': f"{vpcId}_{rtb_target_rtb_map[rtb]}",
                            'vpc_id': vpcId,
                            'route_table_id': rtb_target_rtb_map[rtb],
                            'provider': f'aws.{regionAlias}'
                        })

                if cls.DryRun:
                    continue
                
                try:
                    response = ec2_client.replace_route_table_association(
                        RouteTableId=rtb_target_rtb_map[rtb], AssociationId=assoc['RouteTableAssociationId'])
                except Exception as e:
                    logger.warning(f'  **Alert** {e}')

    @classmethod
    def storeAndDeleteTgwRoute(cls, tgwRtbInfo, key, ec2_client, tgwRtbId, routes):
        logger = logging.getLogger(__name__)
        for route in routes:
            cidr = route['DestinationCidrBlock']
            logger.info(f'  delete route {cidr}')
            response = ec2_client.delete_transit_gateway_route(
                TransitGatewayRouteTableId=tgwRtbId,
                DestinationCidrBlock=cidr)
            if not key in tgwRtbInfo:
                tgwRtbInfo[key] = []
            tgwRtbInfo[key].append(cidr)

    @classmethod
    def mgmtTgwAttachmentStaticRoute(cls, revert, tgwRtbInfo, initialKey, ec2_client, vpc, tgwId):
        if revert == False:
            cls.deleteTgwAttachementStaticRoute(
                tgwRtbInfo, initialKey, ec2_client, vpc, tgwId)
        else:
            cls.restoreTgwAttachementStaticRoute(
                tgwRtbInfo, initialKey, ec2_client, vpc, tgwId)

    @classmethod
    def getTgwId(cls, ec2_client):
        response = ec2_client.describe_transit_gateways()
        if len(response['TransitGateways']) > 0:
            return response['TransitGateways'][0]['TransitGatewayId']
        else:
            return None

    @classmethod
    def getTgwAttachementSubnets(cls, ec2_client, vpc, tgwId):
        """
        for the given vpc and tgwId, lookup the attachement and returns the
        subnets used in the attachement
        """
        logger = logging.getLogger(__name__)
        # Lookup tgwId and tgwAttachmentId for a vpc
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
            return []

        return response['TransitGatewayVpcAttachments'][0]['SubnetIds']


    @classmethod
    def restoreTgwAttachementStaticRoute(cls, tgwRtbInfo, initialKey, ec2_client, vpc, tgwId):
        logger = logging.getLogger(__name__)
        # Lookup tgwId and tgwAttachmentId for a vpc
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

        # if len(response["TransitGatewayVpcAttachments"]) == 0:
        #     return

        for attachObj in response['TransitGatewayVpcAttachments']:

            tgwAttachmentId = attachObj['TransitGatewayAttachmentId']
            tgwId = attachObj['TransitGatewayId']

            response = ec2_client.describe_transit_gateway_route_tables(
                Filters=[
                    {'Name': 'transit-gateway-id', 'Values': [tgwId]},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )

            # iterate all tgw route tables
            for x in response['TransitGatewayRouteTables']:
                tgwRtbId = x['TransitGatewayRouteTableId']
                key = f'{initialKey}-{tgwAttachmentId}-{tgwRtbId}'

                if not key in tgwRtbInfo:
                    continue
                logger.info(
                    f'- Restore static route(s) for {tgwAttachmentId} into {tgwId}/{tgwRtbId}')
                for cidr in tgwRtbInfo[key]:
                    try:
                        logger.info(f'  add route {cidr}')
                        if cls.DryRun:
                            continue
                        response = ec2_client.create_transit_gateway_route(
                            DestinationCidrBlock=cidr,
                            TransitGatewayRouteTableId=tgwRtbId,
                            TransitGatewayAttachmentId=tgwAttachmentId
                        )
                    except botocore.exceptions.ClientError as err:
                        logger.error(f'  **Alert** {err}')

    @classmethod
    def deleteTgwAttachementStaticRoute(cls, tgwRtbInfo, initialKey, ec2_client, vpc, tgwId):
        logger = logging.getLogger(__name__)
        # Lookup tgwId and tgwAttachmentId for a vpc
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

        # if len(response["TransitGatewayVpcAttachments"]) == 0:
        #     return

        for attachObj in response['TransitGatewayVpcAttachments']:

            tgwAttachmentId = attachObj['TransitGatewayAttachmentId']
            tgwId = attachObj['TransitGatewayId']

            response = ec2_client.describe_transit_gateway_route_tables(
                Filters=[
                    {'Name': 'transit-gateway-id', 'Values': [tgwId]},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )

            # iterate all tgw route tables
            for x in response['TransitGatewayRouteTables']:
                tgwRtbId = x['TransitGatewayRouteTableId']

                response = ec2_client.search_transit_gateway_routes(
                    TransitGatewayRouteTableId=tgwRtbId,
                    Filters=[
                        {
                            'Name': 'attachment.transit-gateway-attachment-id',
                            'Values': [
                                    tgwAttachmentId,
                            ]
                        },
                        {
                            'Name': 'type',
                            'Values': [
                                    'static',
                            ]
                        }
                    ])
                if len(response['Routes']) == 0:
                    continue
                logger.info(
                    f'- Delete static route(s) for {tgwAttachmentId} from {tgwId}/{tgwRtbId}')
                key = f'{initialKey}-{tgwAttachmentId}-{tgwRtbId}'

                if cls.DryRun:
                    continue
                cls.storeAndDeleteTgwRoute(
                    tgwRtbInfo, key, ec2_client, tgwRtbId, response['Routes'])

    @classmethod
    def mgmtTgwAttachementPropagatedRoute(cls, revert, tgwRtbInfo, initialKey, ec2_client, vpc, tgwId):
        # Lookup tgwId and tgwAttachmentId for a vpc
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

        for attachObj in response['TransitGatewayVpcAttachments']:
            logger = logging.getLogger(__name__)
            if revert == False:
                tgw_attach_id = attachObj["TransitGatewayAttachmentId"]
                response = ec2_client.get_transit_gateway_attachment_propagations(
                    TransitGatewayAttachmentId=tgw_attach_id)

                key = f'{initialKey}-{vpc.id}'
                if len(response['TransitGatewayAttachmentPropagations']) == 0:
                    return
                tgwRtbInfo[key] = response['TransitGatewayAttachmentPropagations']
                # Disable spoke CIDR propagation to DIY TGW
                for tgw_rtb in response['TransitGatewayAttachmentPropagations']:
                    logger.info(
                        f"- Disable route table propogation for {tgw_rtb['TransitGatewayRouteTableId']}")
                    try:
                        if cls.DryRun:
                            continue
                        response = ec2_client.disable_transit_gateway_route_table_propagation(
                            TransitGatewayRouteTableId=tgw_rtb['TransitGatewayRouteTableId'], TransitGatewayAttachmentId=tgw_attach_id)
                    except botocore.exceptions.ClientError as err:
                        logger.error(f'  **Alert** {err}')
            else:
                tgw_attach_id = attachObj["TransitGatewayAttachmentId"]
                response = ec2_client.get_transit_gateway_attachment_propagations(
                    TransitGatewayAttachmentId=tgw_attach_id)

                key = f'{initialKey}-{vpc.id}'
                if not key in tgwRtbInfo:
                    return
                plist = tgwRtbInfo[key]
                for tgw_rtb in plist:
                    if tgw_rtb['State'] == 'enabled':
                        logger.info(
                            f"- Enable route table propogation for {tgw_rtb['TransitGatewayRouteTableId']}")
                        try:
                            if cls.DryRun:
                                continue
                            response = ec2_client.enable_transit_gateway_route_table_propagation(
                                TransitGatewayRouteTableId=tgw_rtb['TransitGatewayRouteTableId'], TransitGatewayAttachmentId=tgw_attach_id)
                        except botocore.exceptions.ClientError as err:
                            logger.error(f'  **Alert** {err}')

    @classmethod
    def listAllFiles(cls,bucket, prefix='', suffix='', contains='', s3=None):
        logger = logging.getLogger(__name__)
        if s3 == None:
            logger.warning(f'  **Alert** failed to listAllFiles - no access to S3.')
            return

        # kwargs = {'Bucket': bucket, 'Delimiter': '/'}
        kwargs = {'Bucket': bucket, 'Prefix': prefix}

        while True:
            response = s3.list_objects_v2(**kwargs)
            if 'Contents' in response:
                for s3Obj in response['Contents']:
                    key = s3Obj['Key']
                    if key.find(contains) >= 0:
                        yield key, s3Obj['LastModified']
            try:
                kwargs['ContinuationToken'] = response['NextContinuationToken']
            except KeyError:
                break

    @classmethod
    def getS3Client(cls, accountNo, s3RoleName, s3Region):
        role_arn = "arn:aws:iam::" + \
                accountNo + ":role/"+s3RoleName
        creds = common.get_temp_creds_for_account(role_arn)
        s3_handler = common.get_s3_resource_handler(s3Region, creds)
        s3_client = s3_handler.meta.client
        return s3_client

    @classmethod
    def getS3Access(cls, yamlObj):
        logger = logging.getLogger(__name__)
        s3AccountNo, s3Region, s3RoleName = common.getS3BucketInfo(yamlObj)
        if s3AccountNo == None or s3Region == None or s3RoleName == None:
            return None

        s3 = cls.getS3Client(s3AccountNo, s3RoleName, s3Region)
        return s3

    @classmethod
    def uploadAllFiles(cls,stage,yamlObj,absolutePath):
        """
        upload all files from 'folder' to S3

        :param yamlObj: yaml json input
        :type yamlObj: str
        :param absolutePath: absolute path to the target folder that contains the files to be uploaded
        :type absolutePath: str
        :returns: None
        :rtype:
        """

        logger = logging.getLogger(__name__)
        logger.info(f'- Upload {absolutePath} to S3')        

        bucket = common.getS3BucketName(yamlObj)
        if bucket == None:
            logger.warning(f'  **Alert** failed to read S3 bucket name for upload')            
            return
        s3 = cls.getS3Access(yamlObj)
        if s3 == None:
            logger.warning(f'  **Alert** failed to upload - no access to S3.')
            return

        pathLen = len(absolutePath) - len(absolutePath.split('/')[-1])

        for root, dirs, files in walk(absolutePath, topdown=True):
            s3BucketPrefix = f'dm/{root[pathLen:]}'
            for f in files:
                # only upload file not starting with a dot ('.')
                if f.startswith('.') or f.endswith('.tfstate') or f.endswith('.backup'):
                    continue
                fabs = f'{root}/{f}'

                logger.info(f'  {fabs} to {s3BucketPrefix}/{f}')
                if not cls.DryRun:
                    s3.upload_file(fabs,bucket,f'{s3BucketPrefix}/{f}')
            # only upload subfolder not starting with a dot ('.')
            dirs[:] = [d for d in dirs if not d.startswith('.')]

        # upload log files
        target_folder = yamlObj['terraform']['terraform_output']
        for f in ['dm.log', 'dm.alert.log']:
            logFile = f'{target_folder}/log/{f}'
            if path.exists(logFile):
                s3.upload_file(logFile,bucket,f'dm/{absolutePath[pathLen:]}/tmp/{stage}-{f}')

    
    @classmethod
    def createBucketIfneeded(cls,yamlObj):
        """
        create S3 Bucket for storing the generated account folder with terraform output files.

        1) If bucket does not exist, create bucket, enable versioning, disabling public access.
        2) If bucket exists, check if versioning is enabled and public access is disabled.
           Terminate the script if either condition is False.
        """
        logger = logging.getLogger(__name__)
        bucket = common.getS3BucketName(yamlObj)
        account, region, role = common.getS3BucketInfo(yamlObj)

        if bucket == None or account == None or region == None or role == None:
            return True

        s3 = cls.getS3Access(yamlObj)        
        logger.info(f'- Check if S3 bucket {bucket} exists')

        if cls.isBucketExist(s3, bucket, account):
            logger.info(f'  found S3 bucket {bucket} in account {account}')

            # if S3 bucket verioning is NOT enabled, alert the user and terminate
            try:
                response = s3.get_bucket_versioning(Bucket=bucket, ExpectedBucketOwner=account)
                if not 'Status' in response or response['Status'] != 'Enabled':
                    logger.warning(f'  **Alert** versioning disabled for S3 bucket {bucket} in {account}')
                    return False
            except botocore.exceptions.ClientError as e:
                logger.warning(f'  failed to check versioning for S3 bucket {bucket} in {account}')
                logger.error(f'  {e}')
                return False

            # if S3 bucket Public access is NOT disabled, alert the user and terminate
            try:
                response = s3.get_public_access_block(Bucket=bucket, ExpectedBucketOwner=account)
                for key, val in response['PublicAccessBlockConfiguration'].items():
                    if val != True:
                        logger.warning(f'  **Alert** S3 bucket {bucket} in {account} is NOT fully disabled for public access')
                        return False
                        break
            except botocore.exceptions.ClientError as e:
                logger.warning(f'  **Alert** S3 bucket {bucket} in {account} is NOT fully disabled for public access')
                logger.error(f'  {e}')
                return False
            return True
        else:
            # create S3 bucket
            try:
                if region == 'us-east-1':
                    response = s3.create_bucket(
                        Bucket=bucket
                    )
                else:
                    response = s3.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={
                            'LocationConstraint': region,
                        },
                    )
                logger.info(f'  created S3 bucket {bucket} in account {account}')
            except botocore.exceptions.ClientError as e:
                logger.info(f'  failed to create S3 bucket {bucket} in {account}')                
                logger.error(f'  {e}')
                return False
            bpa = cls.blockPublicAccess(s3,bucket,account)
            ebv = cls.enableBucketVersioning(s3,bucket,account)
            if bpa == False or ebv == False:
                return False
            return True

    @classmethod
    def enableBucketVersioning(cls,s3,bucket,account):
        logger = logging.getLogger(__name__)
        try:
            response = s3.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={
                    'MFADelete': 'Disabled',
                    'Status': 'Enabled'
                },
                ExpectedBucketOwner=account
            )
        except botocore.exceptions.ClientError as e:
            logger.info(f'  failed to enable versioning for S3 bucket {bucket} in {account}')
            logger.error(f'  {e}')
            return False

        logger.info(f'  enabled versioning for S3 bucket {bucket} in {account}')
        return True

    @classmethod
    def blockPublicAccess(cls,s3,bucket,account):
        logger = logging.getLogger(__name__)
        try:
            response = s3.put_public_access_block(
                Bucket=bucket,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                },
                ExpectedBucketOwner=account
            )
        except botocore.exceptions.ClientError as e:
            logger.info(f'  failed to block public access for S3 bucket {bucket} in {account}')
            logger.error(f'  {e}')
            return False

        logger.info(f'  blocked public access to S3 bucket {bucket} in {account}')
        return True

    @classmethod
    def isBucketExist(cls,s3,bucket,accountId):
        logger = logging.getLogger(__name__)
        try:
            response = s3.head_bucket(Bucket = bucket, ExpectedBucketOwner=accountId)
        except botocore.exceptions.ClientError as ex:
            logger.info(f'  S3 bucket {bucket} {ex.response["Error"]["Message"]}')
            return False
        return True
        

    @classmethod
    def downloadAllFiles(cls,yamlObj,target_location):
        """
        Download all files from S3 into target_location

        :param bucket: s3 bucket name
        :type bucket: str
        :param prefix: path to account folder in 'bucket'
        :type prefix: str
        :param target_location: absolute path to account folder
        :type target_location: str
        """
        logger = logging.getLogger(__name__)
        bucket = common.getS3BucketName(yamlObj)

        if bucket == None:
            logger.warning(f'  **Alert** failed to read S3 bucket name for download')            
            return

        account_id = target_location.split('/')[-1]
        logger.info(f'- Download S3 {bucket}/dm/{account_id} to {target_location}')
        s3BucketPrefix=f'dm/{account_id}/'

        s3 = cls.getS3Access(yamlObj)
        if s3 == None:
            logger.warning(f'  **Alert** failed to download - no access to S3.')
            return

        if not path.exists(target_location):
            makedirs(target_location)

        for s3Obj, lastMod in cls.listAllFiles(bucket, s3BucketPrefix, s3=s3):
            # do not download log files
            if s3Obj.endswith('.log') or s3Obj.endswith('.tfstate') or s3Obj.endswith('.backup'):
                continue
            logger.info(f'  {s3Obj}')
            cls.downloadBucketObj(bucket, target_location, s3BucketPrefix, s3Obj, s3)

    @classmethod
    def downloadS3Yaml(cls, bucketStr):
        logger = logging.getLogger(__name__)
        logger.info(f'- Download YAML from S3')

        bucketSpec = bucketStr.split(',')
        if len(bucketSpec) != 4:
            logger.error(f'  s3_yaml_download should have 4 components - found {len(bucketSpec)} instead')
            return False
        
        s3Region = 'us-east-1'
        s3AccountNo = bucketSpec[0]
        s3RoleName = bucketSpec[1]
        s3Bucket = bucketSpec[2]
        spokeAccount = bucketSpec[3]

        s3 = cls.getS3Client(s3AccountNo, s3RoleName, s3Region)
        if s3 == None:
            logger.error(f'  Access to S3 failed')
            return False

        key = f'dm/{spokeAccount}/tmp/discovery.yaml'
        try:
            s3.download_file(s3Bucket,key,f'/tmp/discovery.yaml')
        except botocore.exceptions.ClientError as err:
            logger.error(f'{err}')
            return False
        return True


    @classmethod    
    def downloadBucketObj(cls,bucket,dest,prefix,key,s3):
        """
        call S3 API to download the file specified by 'key' in 'bucket' to the 'dest' folder.
        'prefix' will be stripped from the key to determine the final location of the file in 'dest'
        because subfolders could form part of the key.

        :param bucket: bucket name
        :param dest: terraform_output plus account_id, e.g., /Users/xyz/tfoutput/112233878644
        :param prefix: search prefix in the bucket, e.g., dm/112233878644/
        :param key: key to file in the bucket, e.g., dm/112233878644/aws-us-east-1-vpc-04de3d319307cc5e9.auto.tfvars
        """
    
        #
        # deduce the subfolder in key (if existed) given the prefix dm/112233878644
        # so it can be created under 'dest' before downloading the file.
        #
        # e.g.:
        # key:       dm/112233878644/tmp/test
        # subfolder: tmp
        #
        # key:       dm/112233878644/tmp/tmp2/test
        # subfolder: tmp/tmp2
        # dest path: /Users/xyz/tfoutput/112233878644/tmp/tmp2

        li = key.rfind('/')
        subfolder = key[len(prefix):li]
        dpath = f'{dest}/{subfolder}'

        # create the subfolder if needed
        if not path.exists(dpath):
            makedirs(dpath)

        filename = key[len(prefix):]
        dfile = dest + '/' + filename
        #
        # e.g., 
        # key:   dm/205987878622/aws-us-east-1-vpc-04de3d319307cc5e9.auto.tfvars
        # dfile: /Users/xyz/tfoutput/205987878622/aws-us-east-1-vpc-04de3d319307cc5e9.auto.tfvars
        #
        # with subfolder, e.g.:
        # key:   dm/205987878622/tmp/test
        # dfile: /Users/xyz/tfoutput/205987878622/tmp/test
        #
        if not cls.DryRun:
            s3.download_file(bucket,key,dfile)

    @classmethod    
    def deleteBucketObj(cls,yamlObj,target_location,filename):
        """
        Delete the filename from S3

        :param yamlObj: input yaml object
        :target_location: absolute path to account folder
        :filename: the path to the filename relative to target_location
        """
        logger = logging.getLogger(__name__)
        logger.info(f'- Delete {filename} in S3')
        bucket = common.getS3BucketName(yamlObj)
        if bucket == None:
            logger.warning(f'  **Alert** cannot access S3 bucket for upload')            
            return
        s3 = cls.getS3Access(yamlObj)
        if s3 == None:
            logger.warning(f'  **Alert** failed to upload - no access to S3.')
            return
        accountId = target_location.split('/')[-1]
        key = f'dm/{accountId}/{filename}'
        if cls.DryRun:
            return
        s3.delete_object(Bucket=bucket,Key=key)

    @classmethod
    def deleteSubnet(cls, client, subnetId):
        logger = logging.getLogger(__name__)
        logger.info(f'- Delete {subnetId}')

        if cls.DryRun:
            return

        response = client.delete_subnet(
            SubnetId=subnetId
        )