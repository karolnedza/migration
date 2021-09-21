# VPC Migration 

### Summary

This script discovers VPCs routing info, builds terraform files and allows for switching traffic to the Aviatrix transit

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

5. The following environemnt variables can be defined to provide the controller username and password to the discovery-migration script, so you won't be prompted for the controller password at the command line:\
   ***export aviatrix_controller_user=admin***\
   ***export aviatrix_controller_password=&lt;password&gt;***

### Discovery:
6. Provide discovery info in the discovery.yaml file, e.g.:

```
aws:
  s3: 
    account: "955315316192"  
    role_name: "aviatrix-role-app"
    name: "aviatrix-discovery-migration"
    region: "us-east-1"
terraform:
  terraform_output: "/Users/xyz/terraform_output"
  terraform_version: ">= 0.13"
  aviatrix_provider: "= 2.18.2"
  aws_provider: "~> 3.15.0"
  enable_s3_backend: True
aviatrix:
  controller_ip: "33.204.174.31"
  controller_account: "955315316192"
  ctrl_role_app: "Networking.AviatrixService"
  ctrl_role_ec2: "Networking.AviatrixController"
  gateway_role_app: "Networking.AviatrixGateway"
  gateway_role_ec2: "Networking.AviatrixInstanceProfile"
alert:
  expect_dest_cidrs: ["146.197.0.0/16", "100.127.0.0/25", "100.64.0.0/25"]
  expect_vpc_prefixes: ["10.0.0.0/8", "100.127.0.0/16", "100.164.0.0/16"]
config:
  filter_tgw_attachment_subnet: True
  spoke_gw_name_format: "HEX_CIDR"     # HEX_CIDR or VPC_NAME
  allow_vpc_cidrs: ["10.0.0.0/8"]
  subnet_tags:
    - key: 'Networking-Created-Resource'
      value: 'Do-Not-Delete-Networking-Created-Resource'
  route_table_tags:
    - key: 'Aviatrix-Created-Resource'
      value: 'Do-Not-Delete-Aviatrix-Created-Resource'
tgw:
  tgw_account: "777456789012"
  tgw_role: "aviatrix-role-abc"
  tgw_by_region:
    us-east-1: "tgw-0068b1e974c52dc88"
    us-east-2: "tgw-0011223374c528899"
account_info:
  - account_id: "123456789012"
    role_name: "aviatrix-role-xyz"
    spoke_gw_size: "t3.micro"
    filter_cidrs: ["146.197.0.0/16"]
    hpe: False    
    regions:
      - region: "us-east-1"
        vpcs:
          - vpc_id: "vpc-04de3d319307cc5e9"
            gw_zones:
            avtx_cidr: "10.101.0.0/16"   
          - vpc_id: "vpc-0433454d6edec3b2d"
            gw_zones: ["a","b"]
            avtx_cidr: "10.111.0.0/16"
          - vpc_id: "vpc-0b111506a32e62fdf"
            gw_zones:
            avtx_cidr: "10.121.0.0/16"
switch_traffic:
  delete_tgw_route_delay: 5
cleanup:
  vpc_cidrs: ["10.11.0.0/23", "100.64.1.0/26"]
  resources: ["VGW"]
```

| Field              |  Type         | Required | Description                                      |
| :-----------       |:------------- | :------- | :--------------------------------------------    |
| aws:               |               |   Yes    | Mark the beginning of aws info                   |
| s3:                |               |   Yes    | Setup s3 for storing the terraform output files  |
| account:           | string        |   Yes    | s3 bucket account number                         |
| role_name:         | string        |   Yes    | s3 bucket access permission                      |
| name:              | string        |   Yes    | s3 bucket name                                   |
| region:            | string        |   Yes    | s3 bucket region                                 |
|                    |               |          |                                                  |
| terraform:         |               |   Yes    | Mark the beginning of terraform info             |
| terraform_output   | string        |   Yes    | Absolute path to the TF files created            |
| terraform_version  | string        |   Yes    | Version string in terraform version syntax       |
| aviatrix_provider  | string        |   Yes    | Version string in terraform version syntax       |
| aws_provider       | string        |   Yes    | Version string in terraform version syntax       |
| enable_s3_backend  | bool          |   No     | Generate terraform S3 backend config. True by default |
|                    |               |          |                                                  |
| aviatrix:          |               |   Yes    | Mark the beginning of aviatrix info              |
| controller_ip      | string        |   Yes    | Aviatrix controller IP address                   |
| controller_account | string        |   Yes    | The AWS Account # where the controller resides   |
| ctrl_role_app      | string        |   Yes    |                                                  |
| ctrl_role_ec2      | string        |   Yes    |                                                  |
| gateway_role_app   | string        |   Yes    |                                                  |
| gateway_role_ec2   | string        |   Yes    |                                                  |
|                    |               |          |                                                  |
| alert:             |               |   Yes    | Mark beginning of alert                          |
| expect_dest_cidrs  | list          |   Yes    | Alert public IP to unexpected dest. cidrs        |
| expect_vpc_prefixes| list          |   Yes    | Alert VPC prefix not fall within given cidr ranges|
|                    |               |          |                                                  |
| config:            |               |   Yes    | Mark beginning of script feature config          |
| filter_tgw_attachment_subnet| bool |  Yes     | enable tgw attachement subent filtering (True/False)|
| spoke_gw_name_format| string       |   Yes    | Valid value: "HEX_CIDR" or "VPC_NAME"            |
| allow_vpc_cidrs    | list          |   Yes    | List of allowed VPC CIDRs                        |
| subnet_tags        | list          |   No     | List of tags to be added to the subnet(s)        |
| key                | String        |   No     |  name of the tag                                 |
| value              | String        |   No     |  value of the tag                                |
| route_table_tags   | list          |   No     | List of tags to be added to the route table(s)   |
| key                | String        |   No     |  name of the tag                                 |
| value              | String        |   No     |  value of the tag                                |
|                    |               |          |                                                  |
| tgw:               |               |   Yes    | Mark beginning of tgw info                       |
| tgw_account        | string        |   Yes    | TGW account number                               |
| tgw_role           | string        |   Yes    | TGW account access role                          |
| tgw_by_region:     |               |   Yes    | Mark beginning of tgw_by_region object, defining region and tgw_id pair |
| us-east-1          | string        |   No     | tgw_id in region us-east-1                       |
| us-east-2          | string        |   No     | tgw_id in region us-east-2                       |
|    ...             |  ...          |   ...    |         ...                                      |
| eu-north-1         | string        |   No     | tgw_id in region eu-north-1                      |
|                    |               |          |                                                  |
| account_info:      |               |   Yes    | Mark the beginning of account_info list          |
| account_id         | string        |   Yes    | AWS Account #                                    |
| role_name          | string        |   Yes    | IAM role assumed to execute API calls            |
| spoke_gw_size      | string        |   Yes    | Spoke gateway instance size                      |
| filter_cidrs       | list          |   Yes    | Filters out any route within specified CIDR      |
| hpe                | bool          |   Yes    | Spoke gateway setting (True/False)               |
|                    |               |          |                                                  |
| regions:           |               |   Yes    | Mark the beginning of region list                |
| region             | string        |   Yes    | AWS region                                       |
|                    |               |          |                                                  |
| vpcs:              |               |   Yes    | Mark the beginning of vpc list                   |
| vpc_id             | string        |    No    | VPC IDs to be migrated                           |
| gw_zones           | list ["a",...]|    No    | Zone letters to deploy spoke gateways in         |
| avtx_cidr          | string        |   Yes    | set avtx_cidr in vpc-id.tf                       |
|                    |               |          |                                                  |
 switch_traffic:    |               |   Yes    | Mark the beginning of switch_traffic config      |
| delete_tgw_route_delay| integer    |   No     | specifiy the delay between spoke-gw-advertize-cidr and tgw-route-removal. Default is 5 second. |
|                    |               |          |                                                  |
| cleanup:           |               |   Yes    | Mark the beginning of cleanup list               |
| vpc_cidrs          | list          |   Yes    | CIDR's to be deleted from VPC                    |
| resources          | list ["VGW"]  |   Yes    | Delete resources like VGW in a VPC               |

When no vpc_id and gw_zones are defined, all vpcs withn the region are candidates for migration. gw_zones with the most private subnets will be used.

7. Run the discovery script to review and resolve the reported alerts \
   ***python3 -m dm.discovery discovery.yaml***

   - The script generates terraform files required to build Aviatrix infrastracture in the migrated VPC. They can be found in **&lt;terraform_output&gt;/&lt;account No&gt;**.

   - The script shows progress by printing to stdout the discovered VPC and detected alerts.  It produces two log files: **dm.log** contains the results of the checks and tasks that are done for each VPC; **dm.alert.log** captures the alert summary that are seen on stdout.  They can be found in **&lt;terraform_output&gt;/log**.

8. After resolving the alerts, run discovery again with the option --s3backup to backup the **&lt;terraform_output&gt;/&lt;account No&gt;** folder into the S3 bucket **&lt;bucket&gt;/dm/&lt;account No&gt;**: \
   ***python3 -m dm.discovery discovery.yaml --s3backup***

   This will allow the terraform files to be called later in switch_traffic time where new subnet-route-table association will be generated and appended to the existing terraform files.

9. **Migration restriction.**  A discovery.yaml file can be used to migrate all VPCs within an account in a single discovery/switch_traffic cycle or multiple yaml files can be used to migrating a set of VPCs at a time.  The only restriction is a discovery/switch_traffic/cleanup cycle should be completed before another cycle can be started on the same account, i.e., complete the migration (discovery/switch_traffic/cleanup) of the VPCs in an account before migrating other VPCs on the same account.

### Building Aviatrix infrastructure:

10. Copy terraform directory from the ***terraform_output/&lt;account No&gt;*** folder to the ***aws_spokes*** one

11. The terraform files contains the Aviatrix infrastracture resources and the discovered
    subnet resources.  The subnet resources should be imported before building the Aviatrix infrastracture.  Here are the steps to be 
    performed in the ***account No*** directory:

    a. Run **terraform init**

    b. Run **terraform apply -target data.aws_ssm_parameter.avx-password** to resolve the Aviatrix provider dependence.

    c. Run **source ./terraform-import-subnets.sh** to import discovered subnet resources.

    d. Run **terraform apply** to build Aviatrix infrastracture. Terraform will deploy and attach the spoke gateways.
       It will also copy existing route tables.

### Switching the traffic to the Aviatrix transit
12. Run the switch_traffic command to switch traffic from AWS TGW to Aviatrix spoke/transit.  This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived at discovery time) or use a local input yaml file: 

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --yaml_file discovery.yaml***

    **dm.switch_traffic** is responsible for
      a) changing the subnets association to the new RTs created in step 9, b) deleting the VPC-attachement-static-route in TGW routing table (***--rm_static_route***), and c) setting up the VPC advertised CIDRs in the Aviatrix spoke gateways.  It supports the following options:

      - ***--s3backup*** uploads the associated terraform output account folder into S3 at the end of switch_traffic, e.g.:\
      ***python3 -m dm.switch_traffic --s3backup --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--s3download*** downloads the account folder, containing the terraform script, from S3 at the beginning of switch_traffic. This is required if the local account folder has been removed because of a container restart, e.g.:\
      ***python3 -m dm.switch_traffic --s3download --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--revert*** restores the configuration back to its original state. It includes restoring the original subnet and route table associations, adding back the deleted VPC-attachement-static routes into TGW routing table, and removing all the spoke gateway advertised CIDRs, e.g.:\
      ***python3 -m dm.switch_traffic -ctrl_user &lt;controller-admin-id&gt; --revert --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--dry_run*** runs through the switch_traffic logic and reports the detected alerts and list of changes to be made **without** actually making any changes, e.g.:\
      ***python3 -m dm.switch_traffic --dry_run --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

    If the environment variables for controller username and password are defined (see Step 5), you can run the **switch_traffic**  without the **--ctrl_user** option; in which case, the migration script will not prompt you for the controller password and use the environment variable defined credential instead, e.g.:\
    ***python3 -m dm.switch_traffic --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;*** 

13. Copy terraform directory from the ***terraform_output/&lt;account No&gt;*** folder to the ***aws_spokes*** folder again because **switch_traffic** will append new route-table-to-subnet-association resources to the corresponding ***&lt;vpc-id&gt;.tf*** in the ***terraform_output/&lt;account No&gt;*** folder.

14. **Import new subnet-association resources into terraform.** Run ***source ./terraform-import-associations.sh*** at the ***aws_spoke*** folder after the copy (see Step 13). 

### Clean up
15. Run the following command to delete original route tables, VPC-TGW attachements, and VPC secondary CIDR's. This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived at discovery time) or use a local input yaml file: 

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.cleanup --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.cleanup --yaml_file discovery.yaml***

    **dm.cleanup** is responsible for
      a) deletes the revert.json from tmp folder locally and from s3. b) deletes the original route tables c) deletes the VPC-attachement. d) deletes the subnets attached to the VPC-attachement e) deletes the route tables which are not associated with any subntes. f) deletes the secondary cidr's provided in vpc_cidrs g) detaches and deletes the VGW associated with the vpc. Cleanup process can be re-runned multiple times. 
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

The S3 attributes in YAML specifies the bucket to be used in S3 for storing the logs and the  terraform files of each spoke VPC account.  If a new bucket is specified, **Discovery** will create the bucket with versioning and full privacy enabled.  If this is an existing bucket, **Discovery** will check if the bucket has versioning and full privacy enabled and will alert and terminate immedately if either one of the settings is missing.

- Discovery will backup the content of account folder into S3 at the end of each run when using the flag **--s3backup**.  The account folder contains the terraform files that will be retrieved at staging and switch_traffic time.

- Switch_traffic starts by downloading the account folder so it can
store the new subnet-route-table association resources to the existing terraform file.
At the end, it will upload the latest of the account folder back to S3.  In --revert mode, similar sequence occurs: 1) Terraform files are downloaded for the given accounts. 2) Previously added subnet-route-table resources are removed. 3) Upload all the account files back to S3.



