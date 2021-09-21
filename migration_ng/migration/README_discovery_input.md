## VPC migration script input:

- [discovery.yaml example](#discoveryyaml-example)

- [Input parameters](#migration-input-parameters)

### discovery.yaml example
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
    - key: "Networking-Created-Resource"
      value: "Do-Not-Delete-Networking-Created-Resource"
  route_table_tags:
    - key: "Aviatrix-Created-Resource"
      value: "Do-Not-Delete-Aviatrix-Created-Resource"
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

### Migration input parameters

| Field              |  Type         | Required | Description                                      |
| :-----------       |:------------- | :------- | :--------------------------------------------    |
| aws:               |               |   No    | Use AWS S3 to backup the generated account folder. Omit this section if S3 backup is not required. |
| s3:                |               |         | Setup s3 for storing the terraform output files  |
| account:           | string        |         | s3 bucket account number                         |
| role_name:         | string        |         | s3 bucket access permission                      |
| name:              | string        |         | s3 bucket name                                   |
| region:            | string        |         | s3 bucket region                                 |
|                    |               |          |                                                  |
| terraform:         |               |   Yes    | Mark the beginning of terraform info             |
| terraform_output   | string        |   Yes    | Absolute path to the TF files created            |
| terraform_version  | string        |   Yes    | Version string in terraform version syntax       |
| aviatrix_provider  | string        |   Yes    | Version string in terraform version syntax       |
| aws_provider       | string        |   Yes    | Version string in terraform version syntax       |
| enable_s3_backend  | bool          |   No     | Generate terraform S3 backend config. True by default if this attribute is omitted |
|                    |               |          |                                                  |
| aviatrix:          |               |   Yes    | Generate terraform resource for onboarding an Aviatrix account.              |
| controller_ip      | string        |   Yes    | Aviatrix controller IP address                   |
| controller_account | string        |   Yes    | The AWS Account # where the controller resides   |
| ctrl_role_app      | string        |   Yes    | Controller app role name to be used in the SPOKE account |
| ctrl_role_ec2      | string        |   Yes    | Name of the role associated with the controller EC2 |
| gateway_role_app   | string        |   Yes    | Gateway role name                                |
| gateway_role_ec2   | string        |   Yes    | Gateway instance profile name                    |
|                    |               |          |                                                  |
| alert:             |               |   Yes    | Mark beginning of alert                          |
| expect_dest_cidrs  | list          |   Yes    | Alert IP not fall within the given CIDR list.  Turn off this alert using ["0.0.0.0/0"]. |
| expect_vpc_prefixes| list          |   Yes    | Alert VPC prefix not fall within given CIDR ranges. Turn off this alert using ["0.0.0.0/0"].|
|                    |               |          |                                                  |
| config:            |               |   Yes    | Mark beginning of script feature config          |
| filter_tgw_attachment_subnet| bool |  Yes     | enable tgw attachment subnet filtering (True/False). Skip subnet used by TGW vpc attachement.|
| spoke_gw_name_format| string       |   Yes    | Valid value: "HEX_CIDR" or "VPC_NAME"            |
| allow_vpc_cidrs    | list          |   Yes    | List of allowed VPC CIDRs. Only the allowed CIDRs will be copied to vpc_cidr and passed to the brownfield spoke VPC terraform module. Set it to ["0.0.0.0/0"] to allow any CIDR. |
| subnet_tags        | list          |   No     | List of tags to be added to the subnet(s). Omit this section if no tags required.   |
| key                | String        |   No     |  name of the tag                                 |
| value              | String        |   No     |  value of the tag                                |
| route_table_tags   | list          |   No     | List of tags to be added to the route table(s). Omit this section if no tags required.   |
| key                | String        |   No     |  name of the tag                                 |
| value              | String        |   No     |  value of the tag                                |
|                    |               |          |                                                  |
| tgw:               |               |   Yes    | List out all the TGWs used, assuming all TGWs are defining within one account.   |
| tgw_account        | string        |   Yes    | TGW account number                               |
| tgw_role           | string        |   Yes    | TGW account access role                          |
| tgw_by_region:     |               |   Yes    | Mark beginning of tgw_by_region object, defining region and tgw_id pair |
| us-east-1          | string        |   No     | tgw_id in region us-east-1                       |
| us-east-2          | string        |   No     | tgw_id in region us-east-2                       |
|    ...             |  ...          |   ...    |         ...                                      |
| eu-north-1         | string        |   No     | tgw_id in region eu-north-1                      |
|                    |               |          |                                                  |
| account_info:      |               |   Yes    | Spoke VPC info          |
| account_id         | string        |   Yes    | AWS Account #                                    |
| role_name          | string        |   Yes    | IAM role assumed to execute API calls            |
| spoke_gw_size      | string        |   Yes    | Spoke gateway instance size                      |
| filter_cidrs       | list          |   Yes    | Filters out any route within specified CIDR when copying the route table.  No need to add RFC1918 routes in the list; they are filtered by default.  Set it to empty list [] if no filtering required. |
| hpe                | bool          |   Yes    | Spoke gateway setting (True/False)               |
|                    |               |          |                                                  |
| regions:           |               |   Yes    | Mark the beginning of region list                |
| region             | string        |   Yes    | AWS region                                       |
|                    |               |          |                                                  |
| vpcs:              |               |   Yes    | Mark the beginning of vpc list                   |
| vpc_id             | string        |    Yes    | VPC IDs to be migrated                           |
| gw_zones           | list ["a",...]|    No    | Zone letters to deploy spoke gateways in.  Discovery will deduce the zones if an empty list [] is used. |
| avtx_cidr          | string        |   Yes    | set avtx_cidr in vpc-id.tf                       |
|                    |               |          |                                                  |
| switch_traffic:    |               |   Yes    | Mark the beginning of switch_traffic config      |
| delete_tgw_route_delay| integer    |   No     | specifiy the delay between spoke-gw-advertize-cidr and tgw-route-removal. Default is 5 second.|
|                    |               |          |                                                  |
| cleanup:           |               |   Yes    | Mark the beginning of cleanup list               |
| vpc_cidrs          | list          |   Yes    | CIDR's to be deleted from VPC                    |
| resources          | list ["VGW"]  |   Yes    | Delete resources like VGW in a VPC               |

If gw_zones is not specified, gw_zones with the most private subnets will be used.
