# VPC Migration 

### Summary

This script discovers VPCs routing info, builds terraform files and allows for switching traffic to the Aviatrix transit

The migration process involves 6 steps:

1. [Preparing the environment](#prerequisites)

2. [Discovering the VPC(s) configuration](#discovery)

3. [Building Aviatrix infrastructure](#Building-Aviatrix-infrastructure)

4. [Switching the traffic to the Aviatrix transit](#Switching-the-traffic-to-the-Aviatrix-transit)

5. [Synchronizing terraform state](#synchronize-terraform-state-with-the-API-based-switch-changes)

6. [Deleting unnecessary resources](#clean-up)

[Logging](#logs) and [s3 bucket](#s3-bucket) details

### Prerequisites:
1. Python 3.7
2. Python modules:\
   argparse, boto3, botocore, ipaddress, logging, PyYAML, requests, retry 
3. $PYTHONPATH pointing to the directory containing the "dm" folder\
   ***export PYTHONPATH="put your path here"/discovery_migration/***
4. An AWS role with the permissions to perform the migration\
   The role used by Aviatrix controller requires the following additions:\
      ***"ec2:ModifyVpcEndpoint",***\
      ***"ec2:DescribeTransitGatewayVpcAttachments",***\
      ***"ec2:GetTransitGatewayAttachmentPropagations",***\
      ***"ec2:ReplaceRouteTableAssociation"***\
      ***"ec2:DisassociateVpcCidrBlock"***\
      ***"ec2:DisassociateSubnetCidrBlock"***\
      ***"ec2:DetachVpnGateway"***\
      ***"ec2:DeleteVpnGateway"***\
      ***"directconnect:DeleteVirtualInterface"***

   The following permission are required for the script to creating a backup S3 bucket and managing the backup:\
      ***"s3:CreateBucket",***\
      ***"s3:DeleteBucket",***\
      ***"s3:ListBucket",***\
      ***"s3:GetObject",***\
      ***"s3:PutObject",***\
      ***"s3:DeleteObject",***\
      ***"s3:GetBucketVersioning",***\
      ***"s3:PutBucketVersioning",***\
      ***"s3:GetBucketPublicAccessBlock"***\
      ***"s3:PutBucketPublicAccessBlock"***

5. The following environment variables can be defined to provide the controller username and password to the discovery-migration script, so you won't be prompted for the controller password at the command line:\
   ***export aviatrix_controller_user=admin***\
   ***export aviatrix_controller_password=&lt;password&gt;***

### Discovery:
1. Provide [discovery info](README_discovery_input.md) in the discovery.yaml file

2. Run the discovery script to review and resolve the reported alerts \
   ***python3 -m dm.discovery discovery.yaml***

   - The script generates terraform files required to build Aviatrix infrastructure in the migrated VPC. They can be found in **&lt;terraform_output&gt;/&lt;account No&gt;**.

   - The script shows progress by printing to stdout the discovered VPC and detected alerts.  It produces two log files: **dm.log** contains the results of the checks and tasks that are done for each VPC; **dm.alert.log** captures the alert summary that are seen on stdout.  They can be found in **&lt;terraform_output&gt;/log**.

3. After resolving the alerts, run discovery again with the option --s3backup to backup the **&lt;terraform_output&gt;/&lt;account No&gt;** folder into the S3 bucket **&lt;bucket&gt;/dm/&lt;account No&gt;**: \
   ***python3 -m dm.discovery discovery.yaml --s3backup***

   This will allow the terraform files to be called later in switch_traffic time where new subnet-route-table association will be generated and appended to the existing terraform files.

**Migration restriction.**\
  A discovery.yaml file can be used to migrate all VPCs within an account in a single discovery/switch_traffic cycle or multiple yaml files can be used to migrating a set of VPCs at a time.  The only restriction is a discovery/switch_traffic/cleanup cycle should be completed before another cycle can be started on the same account, i.e., complete the migration (discovery/switch_traffic/cleanup) of the VPCs in an account before migrating other VPCs on the same account.

### Building Aviatrix infrastructure:

1. Copy terraform directory from the ***terraform_output*** folder to the ***aws_spokes*** one\
    The terraform files contain the Aviatrix infrastructure  resources, the discovered
    subnets and copied route tables.  The subnet resources should be imported before building the Aviatrix infrastructure .  
    
    The following steps should be performed in the ***account No*** directory:

2. Run ***terraform init***

3. Optional - Run ***terraform apply -target data.aws_ssm_parameter.avx-password*** to create TF state file if none exists.

4. Run ***source ./terraform-import-subnets.sh*** to import discovered subnet resources.

5. Run ***terraform apply*** to build Aviatrix infrastructure . Terraform will deploy and attach the spoke gateways.\
   It will also copy existing route tables.

### Switching the traffic to the Aviatrix transit
1. Run the switch_traffic command to switch traffic from AWS TGW/VGW to the Aviatrix transit. \
    This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived during the discovery phase) or use a local input yaml file:
      
      - Download discovery.yaml from the S3 bucket to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --yaml_file discovery.yaml***

    **dm.switch_traffic** is responsible for:\
      a) changing the subnets association to the new RTs created in the Building Aviatrix infrastructure phase\
      b) deleting the VPC-attachment-static-route in TGW routing table (***--rm_static_route***)\
      c) setting up the VPC advertised CIDRs in the Aviatrix spoke gateways.\
      
    It supports the following additional options:

      - ***--s3backup*** uploads the associated terraform output account folder into S3 at the end of switch_traffic, e.g.:\
      ***python3 -m dm.switch_traffic --s3backup --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--s3download*** downloads the account folder, containing the terraform script, from S3 at the beginning of switch_traffic. This is required if the local account folder has been removed because of a container restart, e.g.:\
      ***python3 -m dm.switch_traffic --s3download --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--revert*** restores the configuration back to its original state.\
      It includes restoring the original subnet and route table associations, adding back the deleted VPC-attachment-static routes into TGW routing table, and removing all the spoke gateway advertised CIDRs, e.g.:\
      ***python3 -m dm.switch_traffic -ctrl_user &lt;controller-admin-id&gt; --revert --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--dry_run*** runs through the switch_traffic logic and reports the detected alerts and list of changes to be made **without** actually making any changes, e.g.:\
      ***python3 -m dm.switch_traffic --dry_run --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

    If the environment variables for controller username and password are defined (see [Prerequisites](#prerequisites), Step 5), you can run the **switch_traffic**  without the **--ctrl_user** option; in which case, the migration script will not prompt you for the controller password and use the environment variable defined credential instead, e.g.:\
    ***python3 -m dm.switch_traffic --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;*** 

### Synchronize terraform state with the API based switch changes
1. Copy terraform directory from the ***terraform_output/&lt;account No&gt;*** folder to the ***aws_spokes*** folder again because **switch_traffic** will append new route-table-to-subnet-association resources to the corresponding ***&lt;vpc-id&gt;.tf*** in the ***terraform_output/&lt;account No&gt;*** folder.

2. Import new subnet-association resources into terraform\
   Run ***source ./terraform-import-associations.sh*** at the ***aws_spoke*** folder described in step 9. 


### Clean up
1. Run the following command to delete original route tables, VPC-TGW attachments, and VPC secondary CIDR's. This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived at discovery time) or use a local input yaml file: 

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.cleanup --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.cleanup --yaml_file discovery.yaml***

    **dm.cleanup** is responsible for
      a) deleting the revert.json from tmp folder locally and from s3.\
      b) deleting the original route tables\
      c) deleting the VPC-attachment\
      d) deleting the subnets attached to the VPC-attachment\
      e) deleting the route tables which are not associated with any subntes\
      f) deleting the secondary cidr's provided in vpc_cidrs\
      g) detaching and deleting the VGW associated with the vpc. 
      
    Cleanup process can be re-runned multiple times. 
    It also has a dry_run option: 

      ***--dry_run*** allows the users to review the resources to be deleted before the actual clean up, e.g.:

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
      ***python3 -m dm.cleanup --dry_run --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - Use a local yaml file. \
      ***python3 -m dm.cleanup --dry_run --yaml_file discovery.yaml***

### Logs

Both **dm.discovery** and **dm.switch_traffic** append its log to the end of the two log files: **dm.log** logs the details resulting from the checks and tasks that are done per VPC. **dm.alert.log** captures the same alert summary that are seen on stdout. Here is an example log that shows the beginning of each **dm.discovery** run:

      2021-05-06 13:58:33,348 #############################################
      2021-05-06 13:58:33,348 
      2021-05-06 13:58:33,348 dm.discovery my-managed-regions.yaml
      2021-05-06 13:58:33,348 
      2021-05-06 13:58:33,348 #############################################
      2021-05-06 13:58:33,348 
      2021-05-06 13:58:33,844 +++++++++++++++++++++++++++++++++++++++++++++
      2021-05-06 13:58:33,844 
      2021-05-06 13:58:33,844     Account ID :  123456789012
      2021-05-06 13:58:33,844     Role       :  aviatrix-role-app
      2021-05-06 13:58:33,844 
      2021-05-06 13:58:33,844 +++++++++++++++++++++++++++++++++++++++++++++
      2021-05-06 13:58:33,844 
      2021-05-06 13:58:33,844 - Check VPC for duplicate name
      2021-05-06 13:58:34,383   **Alert** VPC name test-vpc-test-vpc-test-vpc1 > 26 chars, in us-east-1/vpc-0b111506a32e62fdf
      2021-05-06 13:58:34,395 
      2021-05-06 13:58:34,395 =============================================
      2021-05-06 13:58:34,395 
      2021-05-06 13:58:34,395     Region     :  us-east-1
      2021-05-06 13:58:34,395 
      2021-05-06 13:58:34,395 =============================================
      2021-05-06 13:58:34,395 
      2021-05-06 13:58:34,396 - Check EIP usage
      2021-05-06 13:58:35,074   EIP limit:    80
      2021-05-06 13:58:35,075   EIP in use:   2
      2021-05-06 13:58:35,075   EIP required: 6
      2021-05-06 13:58:35,216 
      2021-05-06 13:58:35,216 ---------------------------------------------
      2021-05-06 13:58:35,216 
      2021-05-06 13:58:35,216     Vpc Name : plain-vpc
      2021-05-06 13:58:35,216     Vpc ID   : vpc-0433454d6edec3b2d
      2021-05-06 13:58:35,216     CIDRs    : ['10.62.0.0/16']
      2021-05-06 13:58:35,216 
      2021-05-06 13:58:35,216 ---------------------------------------------
      2021-05-06 13:58:35,216 
      
- The beginning of each **dm.discovery** or **dm.switch_traffic** run is marked by a line of number-sign characters (#), signifying the command and option that were used for the run.  In addition, one can identify the starting point of the latest run in the log by going to the end of the log file and search backward for the number-sign character. Similar structure applies to **dm.alert.log** as well.

- The logs file can be found at <terraform_output>/log.  They are also uploaded to the S3 bucket in <bucket>/dm/<spoke_account>/tmp at
the end of discovery or switch_traffic execution.

### S3 bucket

The S3 attributes in YAML specifies the bucket to be used in S3 for storing the logs and the  terraform files of each spoke VPC account.  If a new bucket is specified, **Discovery** will create the bucket with versioning and full privacy enabled.  If this is an existing bucket, **Discovery** will check if the bucket has versioning and full privacy enabled and will alert and terminate immediately if either one of the settings is missing.

- Discovery will backup the content of account folder into S3 at the end of each run when using the flag **--s3backup**.  The account folder contains the terraform files that will be retrieved at staging and switch_traffic time.

- Switch_traffic starts by downloading the account folder so it can
store the new subnet-route-table association resources to the existing terraform file.
At the end, it will upload the latest of the account folder back to S3.  In --revert mode, similar sequence occurs: 1) Terraform files are downloaded for the given accounts. 2) Previously added subnet-route-table resources are removed. 3) Upload all the account files back to S3.

### EIP quota request

**dm.mgmt_quota** is a helper script that is used for sending the increase-quota-limit request to AWS. Currently, only EIP is supported.  It has 3 three forms:

- List current limit on EIP:\
***python3 -m dm.mgmt_quota &lt;account_id&gt; &lt;region&gt; &lt;role&gt; eip*** 

- Request quota increase to the ***&lt;new_limit&gt;***:\
***python3 -m dm.mgmt_quota &lt;account_id&gt; &lt;region&gt; &lt;role&gt; eip --req_quota &lt;new_limit&gt;***\
This command also returns the request ID that can be used for querying the request status (see next example).

- Check request status:\
***python3 -m dm.mgmt_quota &lt;account_id&gt; &lt;region&gt; &lt;role&gt; eip --req_id &lt;req_id&gt;***\
***&lt;req_id&gt;*** is the ID returned by the quota increase request.

Here are the additional IAM permissions required for EIP quota request (L-0263D0A3):
***servicequotas:GetServiceQuota***\
***servicequotas:RequestServiceQuotaIncrease***\
***servicequotas:GetRequestedServiceQuotaChange***

Here is an example in json format:

    {
        "Effect": "Allow",
        "Action": [
            "servicequotas:GetServiceQuota",
            "servicequotas:RequestServiceQuotaIncrease"
        ],
        "Resource": "arn:aws:servicequotas:*:<ACCOUNT_ID>:ec2/L-0263D0A3"
    },
    {
        "Effect": "Allow",
        "Action": [
            "servicequotas:GetRequestedServiceQuotaChange"
        ],
        "Resource": "*"
    },

- First two permissions ***servicequotas:GetServiceQuota*** and ***servicequotas:RequestServiceQuotaIncrease*** are resource-level permission while ***servicequotas:GetRequestedServiceQuotaChange*** is not and requires a wildcard in the Resource value (https://docs.aws.amazon.com/servicequotas/latest/userguide/identity-access-management.html).