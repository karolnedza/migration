# VNET Migration 

### Summary

This script discovers VNET routing info, builds terraform files and allows for switching traffic to the Aviatrix transit

The migration process involves 6 steps:

1. [Preparing the environment](#prerequisites)

2. [Discovering the VNET(s) configuration](#discovery)

3. [Building Aviatrix infrastructure](#Building-Aviatrix-infrastructure)

4. [Switching the traffic to the Aviatrix transit](#Switching-the-traffic-to-the-Aviatrix-transit)

5. [Synchronizing terraform state](#synchronize-terraform-state-with-the-API-based-switch-changes)

6. [Deleting unnecessary resources](#clean-up)

[Logging](#logs) and [s3 bucket](#s3-bucket) details

### Prerequisites:
1. Python 3.8
2. Required Python modules are captured in two requirement files. Install all the requirements as follows:
   ***pip install -r discovery_migration/aws_requirements.txt*** \
   ***pip install -r discovery_migration/azure_requirements.txt***

3. $PYTHONPATH pointing to the directory containing the "dm" folder\
   ***export PYTHONPATH="put your path here"/discovery_migration/***

4. The following permission are required for the script to creating a backup S3 bucket and managing the backup:\
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


### Sample dicovery yaml file:

      label: "AZURE"
      aws:
        s3: 
          name: "discovery-migration-terraform1"
          region: "us-east-2"
          account: "205987878622"  
          role_name: "aviatrix-role-app"
      terraform:
        terraform_output: "/Users/ybwong/MY_STUFF/tfoutput"
        terraform_version: ">= 0.14"
        aviatrix_provider: "= 2.19.4"
        arm_provider: "~> 2.46.0"
        azurerm:
          - arm_subscription_id: "6f1b55d5-4e5a-4166-8175-cfc4d58d2515"
            arm_directory_id: "4780055e-ce37-4f02-b33d-fdad8493a4b6"
            arm_application_id: "b6e09b37-b6cf-49ee-a42f-dcf3946974c1"
            arm_application_secret_env: "ARM_CLIENT_SECRET"
            arm_application_secret_data_src: "data.aws_ssm_parameter.avx-azure-client-secret.value"
            alias: "s0_sub_core_01"
        aviatrix_account:
          arm_subscription_id: "6f1b55d5-4e5a-4166-8175-cfc4d58d2515"
          arm_directory_id: "4780055e-ce37-4f02-b33d-fdad8493a4b6"
          arm_application_id: "b6e09b37-b6cf-49ee-a42f-dcf3946974c1"
          arm_application_secret_data_src: "data.aws_ssm_parameter.avx-azure-client-secret.value"
          account_name: "arm_dev"
      aviatrix:
        controller_ip: "52.3.72.231"
      alert:
        vnet_name_length: 31
        vnet_peering: True
      config:
        route_table_tags:
          - key: "Aviatrix-Created-Resource"
            value: "Do-Not-Delete-Aviatrix-Created-Resource"
      account_info:
        - subscription_id: "6f1b55d5-4e5a-4166-8175-cfc4d58d2515"
           vnets:
              - vnet_name: "vn_firenet-test_VPC1-US-East"
                use_azs: True
                avtx_cidr: "10.112.0.0/16"
              - vnet_name: "vn_firenet-test_VPC2-US-East"
                use_azs: True
                avtx_cidr: "13.1.1.0/24"
           spoke_gw_size: "Standard_D3_v2"
           hpe: True
      prestage:
         default_route_table: "dummy_rt"
      cleanup:
         resources: ["PEERING"]


| Field              |  Type         | Required | Description                                      |
| :-----------       |:------------- | :------- | :--------------------------------------------    |
| label:             | string        |   Yes    | Mark this yaml for Azure discovery               | 
| aws:               |               |   No     | Use AWS S3 to backup the generated account folder. Omit this section if S3 backup is not required. |
| s3:                |               |          | Setup s3 for storing the terraform output files  |
| account:           | string        |          | s3 bucket account number                         |
| role_name:         | string        |          | s3 bucket access permission                      |
| name:              | string        |          | s3 bucket name                                   |
| region:            | string        |          | s3 bucket region                                 |
|                    |               |          |                                                  |
| terraform:         |               |   Yes    | Mark the beginning of terraform info             |
| terraform_output   | string        |   Yes    | Absolute path to the TF files created            |
| terraform_version  | string        |   Yes    | Version string in terraform version syntax       |
| aviatrix_provider  | string        |   Yes    | Version string in terraform version syntax       |
| arm_provider       | string        |   Yes    | Version string in terraform version syntax       |
|                    |               |          |                                                  |
| azurerm:           | List          |   Yes    | Define the next 5 attributes for each azurerm provider. |
| arm_subscription_id|               |   Yes    |                                                  |
| arm_directory_id   |               |   Yes    | Also referred to as the tenant id                |
| arm_application_id |               |   Yes    |                                                  |
|arm_application_secret_data_src|    |   Yes    | AWS data source that holds the application secret|
| alias              | string        |   Yes    | provider alias                                   |
|                    |               |          |                                                  |
| aviatrix_account:  |               |   Yes    | Generate terraform resource for onboarding Aviatrix account. Omit the next four attributes and define ONLY the account_name if account has already been onboarded |
| arm_subscription_id|               |   No     |                                                  |
| arm_directory_id   |               |   No     |                                                  |
| arm_application_id |               |   No     |                                                  |
|arm_application_secret_data_src|    |   No     |                                                  |
| account_name       | string        |   Yes    |                                                  |
|                    |               |          |                                                  |
| aviatrix:          |               |   Yes    | Mark the beginning of aviatrix info              |
| controller_ip      | string        |   Yes    | Aviatrix controller IP address                   |
|                    |               |          |                                                  |
| alert:             |               |   Yes    | Mark beginning of alert                          |
| ​vnet_name_length   | int           |   Yes    | Alert vnet name length longer than given value. Set to 0 to diable alert.        |
| ​vnet_peering       | bool          |   Yes    | Alert VPC peering. Set to False to disable alert.|
|                    |               |          |                                                  |
| config:            |               |   No     | Mark beginning of script feature config          |
| route_table_tags   | list          |   No     | List of tags to be added to the route table(s). Omit this section if no tags required.   |
| key                | String        |   No     |  name of the tag                                 |
| value              | String        |   No     |  value of the tag                                |
|                    |               |          |                                                  |
| account_info:      |               |   Yes    | Spoke VNET info           |
| subscription_id    | string        |   Yes    | Azure subscription #                             |
| spoke_gw_size      | string        |   Yes    | Spoke gateway instance size                      |
| hpe                | bool          |   Yes    | Spoke gateway setting (True/False)               |
|                    |               |          |                                                  |
| vnets:             |               |   Yes    | Mark the beginning of vnet list                  |
| vnet_name          | string        |   Yes    | VNET to be migrated                              |
| use_azs            | bool          |   Yes    |                                                  |
| avtx_cidr          | string        |   Yes    | set avtx_cidr in vnet.tf                         |
|                    |               |          |                                                  |
| prestage:          |               |   No     |  Only if prestaging is rqeuired                  |
| default_route_table| string        |          |  RT name <vnet_name>-<default_route_table>       |
|                    |               |          |                                                  |
| cleanup:           |               |   Yes    | Mark the beginning of cleanup list               |
| resources          | list ["PEERING"]  |   Yes    | Delete resource in VNET.  Use an empty list [] to omit deletion.    |


### Pre-discovery:

Two additional steps are required for Azure migration before running discovery:

1. Add **avtx_cidr** to VNET using **dm.arm.mgmt_vnet_cdir**:\
   ***python -m dm.arm.mgmt_vnet_cidr discovery.yaml***\
   <br>
   Currently, Azure does not allow CIDR to be added to VNET with peering(s). This script provides VNET CIDR management by first removing the peerings and updating the CIDR and then restoring all the peerings at the end.  It supports the following usages:
   
   - To add cidrs specified in yaml:\
     ***python -m dm.arm.mgmt_vnet_cidr cidr.yaml***
   - To delete cidrs:\
     ***python -m dm.arm.mgmt_vnet_cidr cidr.yaml --delete***
   - To add cidrs without restoring peering:\
     ***python -m dm.arm.mgmt_vnet_cidr cidr.yaml --deletePeering***
   - To delete cidrs without restoring peering:\
     ***python -m dm.arm.mgmt_vnet_cidr cidr.yaml --delete --deletePeering***\
   <br>

   Here is an example of cidr.yaml defined with the **label** attribute **"MGMT_VNET_CIDR"**:

         label: "MGMT_VNET_CIDR"
         log_output: "/home/<userId>/migration/output"
         vnet_cidr:
         - arm_subscription_id: "23241dsae-16d2-4d23-8635-1edd1289473ec9"
            arm_directory_id: "ab46df99a-9006-4ee8-bffb-abcc616faed8e"
            arm_application_id: "8de8519d-04cc-4e33-b435-79e9e478d8dd"
            arm_application_secret_env: "ARM_CLIENT_SECRET"
            vnets:
               vn_firenet-test_VPC1-US-East: "12.1.1.0/24,14.1.1.0/24"
         - arm_subscription_id: "23241dsae-16d2-4d23-8635-1edd1289473ec9"
            arm_directory_id: "ab46df99a-9006-4ee8-bffb-abcc616faed8e"
            arm_application_id: "8de8519d-04cc-4e33-b435-79e9e478d8dd"
            arm_application_secret_env: "ARM_CLIENT_SECRET"
            vnets:
               vn_firenet-test_VPC2-US-East: "13.1.1.0/24"

   - This example shows the structure of two different subscriptions.  The vnets attribute is an object of multiple vnet_name to cidrs pairs.  Only one is shown in this case. 
   
   - **MGMT_VNET_CIDR** yaml can be used to add CIDRs for a cluster of vnets that are interconnected by peerings at the same time, avoiding mulitple outages.

   - Instead of using **MGMT_VNET_CIDR**, **dm.arm.mgmt_vnet_cidr** can also consume the regular **discovery** yaml (marked with the **label** attribute **"AZURE"**). In this case, only the CIDRs of the VNETs planned for the next migration will be added.

2. Run **dm.arm.prestage** to create an empty route table in each of the vnet planned for  migration and associate it to the subnets without any route table association.  This step would allow the migration process to have direct control of the new UDR route table to be created and manages its properties.  This is required until the controller can expose the management of the default UDR route table it created for subnet without route table association.  It supports the following usages:

   - Create the empty route table and asssociate subnet (without route table) to it.\
     ***python3 -m dm.arm.prestage --yaml_file discovery.yaml***
   - Revert the pre-staging process, deleting the subnet associations and the route table.\
     ***python3 -m dm.arm.prestage --revert --yaml_file discovery.yaml***
   - Perform a dry run and see what would be done.\
     ***python3 -m dm.arm.prestage --dry_run --yaml_file discovery.yaml***\
   <br>

   The following attributes are required to be defined in the discovery yaml:

         prestage:
            default_route_table: "dummy_rt"
   
   - The empty route table will have a name of the following form:\
     &lt;vnet_name&gt;-&lt;default_route_table&gt;

### Discovery:
1. Provide [discovery info](README_discovery_input.md) in the discovery.yaml file

2. Run the discovery script to review and resolve the reported alerts \
   ***python3 -m dm.arm.discovery azure_discovery.yaml***

   - The script generates terraform files required to build Aviatrix infrastructure in the migrated VNET. They can be found in **&lt;terraform_output&gt;/&lt;account No&gt;**.

   - The script shows progress by printing to stdout the discovered VNET and detected alerts.  It produces two log files: **dm.log** contains the results of the checks and tasks that are done for each VPC; **dm.alert.log** captures the alert summary that are seen on stdout.  They can be found in **&lt;terraform_output&gt;/log**.

3. After resolving the alerts, run discovery again with the option --s3backup to backup the **&lt;terraform_output&gt;/&lt;account No&gt;** folder into the S3 bucket **&lt;bucket&gt;/dm/&lt;account No&gt;**: \
   ***python3 -m dm.arm.discovery discovery.yaml --s3backup***

   This will allow the terraform files to be called later in switch_traffic time where new subnet-route-table association will be generated and appended to the existing terraform files.

**Migration restriction.**\
  A discovery.yaml file can be used to migrate all VNETs within an account in a single discovery/switch_traffic cycle or multiple yaml files can be used to migrating a set of VNETs at a time.  The only restriction is a discovery/switch_traffic/cleanup cycle should be completed before another cycle can be started on the same account, i.e., complete the migration (discovery/switch_traffic/cleanup) of the VNETs in an account before migrating other VNETs on the same account.

### Building Aviatrix infrastructure:

1. Copy terraform directory from the ***terraform_output*** folder to the ***azure_spokes*** one\
    The terraform files contain the Aviatrix infrastructure  resources, the discovered
    subnets and copied route tables.  The subnet resources should be imported before building the Aviatrix infrastructure .  
    
    The following steps should be performed in the ***account No*** directory:

2. Run ***terraform init***

3. Optional - Run terraform apply on the following two targets to create TF state file if none exists.
  ***terraform apply -target data.aws_ssm_parameter.avx-azure-client-secret***\
  ***terraform apply -target data.aws_ssm_parameter.avx-password***

4. Run ***source ./terraform-import-subnets.sh*** to import discovered subnet resources.\
   <br>
   To undo the import, run ***source ./tmp/terraform-undo-import-associations.sh***.

5. Run ***terraform apply*** to build Aviatrix infrastructure . Terraform will deploy and attach the spoke gateways.\
   It will also copy existing route tables.

### Switching the traffic to the Aviatrix transit
1. Run the switch_traffic command to switch traffic from AWS TGW/VGW to the Aviatrix transit. \
    This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived during the discovery phase) or use a local input yaml file:
      
      - Download discovery.yaml from the S3 bucket to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.arm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.arm.switch_traffic --ctrl_user &lt;controller-admin-id&gt; --rm_static_route --yaml_file discovery.yaml***

    **dm.arm.switch_traffic** is responsible for:\
      a) changing the subnets association to the new RTs created in the Building Aviatrix infrastructure phase\
      b) setting up the VNET advertised CIDRs in the Aviatrix spoke gateways.
      
    It supports the following additional options:

      - ***--s3backup*** uploads the associated terraform output account folder into S3 at the end of switch_traffic, e.g.:\
      ***python3 -m dm.arm.switch_traffic --s3backup --ctrl_user &lt;controller-admin-id&gt;  --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--s3download*** downloads the account folder, containing the terraform script, from S3 at the beginning of switch_traffic. This is required if the local account folder has been removed because of a container restart, e.g.:\
      ***python3 -m dm.arm.switch_traffic --s3download --ctrl_user &lt;controller-admin-id&gt;  --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - ***--revert*** restores the configuration back to its original state.\
      It includes restoring the original subnet and route table associations and removing all the spoke gateway advertised CIDRs, e.g.:\
      ***python3 -m dm.arm.switch_traffic -ctrl_user &lt;controller-admin-id&gt; --revert --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt ;spoke_account&gt;***

      - ***--dry_run*** runs through the switch_traffic logic and reports the detected alerts and list of changes to be made **without** actually making any changes, e.g.:\
      ***python3 -m dm.arm.switch_traffic --dry_run --ctrl_user &lt;controller-admin-id&gt; --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

    If the environment variables for controller username and password are defined (see [Prerequisites](#prerequisites), Step 5), you can run the **switch_traffic**  without the **--ctrl_user** option; in which case, the migration script will not prompt you for the controller password and use the environment variable defined credential instead, e.g.:\
    ***python3 -m dm.arm.switch_traffic --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;*** 

### Synchronize terraform state with the API based switch changes
1. Copy terraform directory from the ***terraform_output/&lt;account No&gt;*** folder to the ***aws_spokes*** folder again because **switch_traffic** will append new route-table-to-subnet-association resources to the corresponding ***&lt;vpc-id&gt;.tf*** in the ***terraform_output/&lt;account No&gt;*** folder.

2. Import new subnet-association resources into terraform\
   Run ***source ./terraform-import-associations.sh*** at the ***azure_spoke*** folder described in step 9.\
   <br>

   To undo the import, run ***source ./tmp/terraform-undo-import-associations.sh***.



### Clean up
1. Run the following command to delete original route tables, VPC-TGW attachments, and VPC secondary CIDR's. This command has two forms, depending whether you want to download the discovery.yaml from S3
(archived at discovery time) or use a local input yaml file: 

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
        ***python3 -m dm.arm.cleanup --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***        

      - Use a local yaml file. \
        ***python3 -m dm.arm.cleanup --yaml_file discovery.yaml***

    **dm.arm.cleanup** is responsible for
      a) deleting the revert.json from tmp folder locally and from s3.\
      b) deleting the original route tables\
      c) deleting the Peering
      
    Cleanup process can be re-run multiple times. 
    It also has a dry_run option: 

      ***--dry_run*** allows the users to review the resources to be deleted before the actual clean up, e.g.:

      - Download discovery.yaml from S3 to /tmp/discovery.yaml.  The is the typical flow.\
      ***python3 -m dm.arm.cleanup --dry_run --s3_yaml_download &lt;s3_account&gt;,&lt;s3_account_role&gt;,&lt;s3_bucket&gt;,&lt;spoke_account&gt;***

      - Use a local yaml file. \
      ***python3 -m dm.arm.cleanup --dry_run --yaml_file discovery.yaml***

### Logs

Both **dm.arm.discovery** and **dm.arm.switch_traffic** append its log to the end of the two log files: **dm.log** logs the details resulting from the checks and tasks that are done per VPC. **dm.alert.log** captures the same alert summary that are seen on stdout. Here is an example log that shows the beginning of each **dm.arm.discovery** run:

      2021-08-28 00:15:44,618 #############################################
      2021-08-28 00:15:44,618 
      2021-08-28 00:15:44,618 dm.arm.discovery azure.yaml
      2021-08-28 00:15:44,618 
      2021-08-28 00:15:44,618 #############################################
      2021-08-28 00:15:44,618 
      2021-08-28 00:15:44,618   **Alert** Failed to read S3 name attribute in yaml
      2021-08-28 00:15:44,618   **Alert** Failed to read S3 attribute(s) in yaml
      2021-08-28 00:15:44,624 +++++++++++++++++++++++++++++++++++++++++++++
      2021-08-28 00:15:44,624 
      2021-08-28 00:15:44,624     Subscription ID :  6f1b55d5-4e5a-4166-8175-cfc4d58d2515
      2021-08-28 00:15:44,625 
      2021-08-28 00:15:44,625 +++++++++++++++++++++++++++++++++++++++++++++
      2021-08-28 00:15:44,625 
      2021-08-28 00:15:45,023 - Discover route table without subnet association
      2021-08-28 00:15:45,710   **Alert** westus rt_firenet-test_VPC1-EU-West.subnet1 has no subnet association
      2021-08-28 00:15:45,710   **Alert** westus rt_firenet-test_VPC1-EU-West.subnet2 has no subnet association
      2021-08-28 00:15:45,710   **Alert** westus rt_firenet-test_VPC1-EU-West.subnet3 has no subnet association
      2021-08-28 00:15:45,710   **Alert** westus test-route-table has no subnet association
      2021-08-28 00:15:45,710   **Alert** northeurope rt-test-north-europe has no subnet association
      2021-08-28 00:15:45,710   **Alert** southeastasia rt-test-southeast-asia has no subnet association
      2021-08-28 00:15:45,711   **Alert** centralus rtb-private has no subnet association
      2021-08-28 00:15:45,711   **Alert** japaneast rt-test-japan-test has no subnet association
      2021-08-28 00:15:45,711   **Alert** westus2 rt-test-west-us-2 has no subnet association
      2021-08-28 00:15:46,221 - Discover vnets: 7 vnets
      2021-08-28 00:15:46,221   ...............................................................
      2021-08-28 00:15:46,221   Vnet cidr                Vnet name (rg)           
      2021-08-28 00:15:46,221   ...............................................................
      2021-08-28 00:15:46,221   10.1.0.0/16              vn_firenet-test_VPC1-US-East  (rg_firenet-test_eastus)
      2021-08-28 00:15:46,222   10.137.24.0/21           vn_firenet-test_VPC2-US-East  (rg_firenet-test_eastus)
      2021-08-28 00:15:46,718 - check if vn_firenet-test_VPC1-US-East has been migrated
      2021-08-28 00:15:47,445   no spoke gateway found
      2021-08-28 00:15:47,445 
      2021-08-28 00:15:47,446 ---------------------------------------------
      2021-08-28 00:15:47,446 
      2021-08-28 00:15:47,446     Vnet Name : vn_firenet-test_VPC1-US-East
      2021-08-28 00:15:47,446     CIDRs     : ['10.1.0.0/16', '10.112.0.0/16']
      2021-08-28 00:15:47,446     Region    : eastus
      2021-08-28 00:15:47,446     RG        : rg_firenet-test_eastus
      2021-08-28 00:15:47,446 
      2021-08-28 00:15:47,446 ---------------------------------------------
      2021-08-28 00:15:47,446 
      2021-08-28 00:15:48,959 - Discover peerings
      2021-08-28 00:15:48,959   **Alert** vnet peering found in vn_firenet-test_VPC1-US-East
      2021-08-28 00:15:48,960   vpc1-to-vpc2 vn_firenet-test_VPC2-US-East (2292eeae-0602-442c-8635-1db589473ec9/rg_firenet-test_eastus)
      2021-08-28 00:15:48,960 - Discover VNG
      2021-08-28 00:15:48,960   VNG not found
      2021-08-28 00:15:48,961 - Discover subnet: 6 subnet(s)
      2021-08-28 00:15:48,961   Found Azure GatewaySubnet (rg_firenet-test_eastus) -- skipped 
      2021-08-28 00:15:48,961   sn_firenet-test_VPC1-US-East.subnet1 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,961     address_prefix: 10.1.1.0/24
      2021-08-28 00:15:48,961     network_security_group: None
      2021-08-28 00:15:48,961     route_table: rt_firenet-test_VPC1-US-East.subnet1 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     delegations: []
      2021-08-28 00:15:48,962   sn_firenet-test_VPC1-US-East.subnet2 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     address_prefix: 10.1.2.0/24
      2021-08-28 00:15:48,962     network_security_group: None
      2021-08-28 00:15:48,962     route_table: rt_firenet-test_VPC1-US-East.subnet2 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     delegations: []
      2021-08-28 00:15:48,962   default (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     address_prefix: 10.1.0.0/24
      2021-08-28 00:15:48,962     network_security_group: None
      2021-08-28 00:15:48,962     route_table: rt_firenet-test_VPC1-US-East.subnet1 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     delegations: []
      2021-08-28 00:15:48,962   subnet-no-table2 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     address_prefix: 10.1.4.0/24
      2021-08-28 00:15:48,962     network_security_group: None
      2021-08-28 00:15:48,962     route_table: vn_firenet-test_VPC1-US-East-dummy_rt (rg_firenet-test_eastus)
      2021-08-28 00:15:48,962     delegations: []
      2021-08-28 00:15:48,962   subnet-no-table1 (rg_firenet-test_eastus)
      2021-08-28 00:15:48,963     address_prefix: 10.1.3.0/24
      2021-08-28 00:15:48,963     network_security_group: None
      2021-08-28 00:15:48,963     route_table: vn_firenet-test_VPC1-US-East-dummy_rt (rg_firenet-test_eastus)
      2021-08-28 00:15:48,963     delegations: []
      2021-08-28 00:15:49,699 
      2021-08-28 00:15:49,699 ---------------------------------------------
      2021-08-28 00:15:49,699 
      2021-08-28 00:15:49,700     Route Tables
      2021-08-28 00:15:49,700 
      2021-08-28 00:15:49,700 ---------------------------------------------
      2021-08-28 00:15:49,700 
      2021-08-28 00:15:49,700 - Discover route table(s):
      2021-08-28 00:15:49,700   route table: rt_firenet-test_VPC1-US-East.subnet1
      2021-08-28 00:15:49,700     subnet: vn_firenet-test_VPC1-US-East/sn_firenet-test_VPC1-US-East.subnet1
      2021-08-28 00:15:49,700     subnet: vn_firenet-test_VPC1-US-East/default
      2021-08-28 00:15:49,700     **Alert** empty UDR route table rt_firenet-test_VPC1-US-East.subnet1
      2021-08-28 00:15:49,700   route table: rt_firenet-test_VPC1-US-East.subnet2
      2021-08-28 00:15:49,700     subnet: vn_firenet-test_VPC1-US-East/sn_firenet-test_VPC1-US-East.subnet2
      2021-08-28 00:15:49,700     **Alert** empty UDR route table rt_firenet-test_VPC1-US-East.subnet2
      2021-08-28 00:15:49,700   skip aviatrix created default vn_firenet-test_VPC1-US-East-dummy_rt
      
- The beginning of each **dm.arm.discovery** or **dm.arm.switch_traffic** run is marked by a line of number-sign characters (#), signifying the command and option that were used for the run.  In addition, one can identify the starting point of the latest run in the log by going to the end of the log file and search backward for the number-sign character. Similar structure applies to **dm.alert.log** as well.

- The logs file can be found at <terraform_output>/log.  They are also uploaded to the S3 bucket in <bucket>/dm/<spoke_account>/tmp at
the end of discovery or switch_traffic execution.

### S3 bucket

The S3 attributes in YAML specifies the bucket to be used in S3 for storing the logs and the  terraform files of each spoke VPC account.  If a new bucket is specified, **Discovery** will create the bucket with versioning and full privacy enabled.  If this is an existing bucket, **Discovery** will check if the bucket has versioning and full privacy enabled and will alert and terminate immediately if either one of the settings is missing.

- Discovery will backup the content of account folder into S3 at the end of each run when using the flag **--s3backup**.  The account folder contains the terraform files that will be retrieved at staging and switch_traffic time.

- Switch_traffic starts by downloading the account folder so it can
store the new subnet-route-table association resources to the existing terraform file.
At the end, it will upload the latest of the account folder back to S3.  In --revert mode, similar sequence occurs: 1) Terraform files are downloaded for the given accounts. 2) Previously added subnet-route-table resources are removed. 3) Upload all the account files back to S3.
