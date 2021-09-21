# Discovery Generator

Discovery Generator is a complimentary set of scripts to the [Discovery Migration](https://github.com/aviatrix-automation/discovery_migration) scripts. Discovery Generator can automatically discover VPCs and generate input files for use with [Discovery Migration's](https://github.com/aviatrix-automation/discovery_migration) network discovery, --stage_vpcs and --switch_traffic functions.

## Quick Start

The typical workflow for the Discovery Generator scripts is as follows:

1. Update `config.yaml`. See Configuration File section for details.
2. Generate `discovery.yaml` for use with [Discovery Migration's](https://github.com/aviatrix-automation/discovery_migration) discovery feature.

```
python3 generate.py config.yaml --discovery discovery.yaml
```

3. Generate an Excel file to be updated by the customer with help from Aviatrix Professional Services.

```
python3 generate.py config.yaml --excel customer.xlsx
```

4. After updating the Excel file, convert it to a YAML file for use with [Discovery Migration's](https://github.com/aviatrix-automation/discovery_migration) --stage_vpcs and --switch_traffic functions.

```
python3 convert_excel_to_yaml.py --excel customer.xlsx --yaml customer.yaml
```

## Configuration File

The configuration file should be structured like the following:

```
account_id:
- 012345678900
- 123456789000

aws_region:
- us-east-1
- us-east-2
- us-west-1
- us-west-2

controller:
  ip: 1.1.1.1
  username: admin

defaults:
  role_name: aviatrix-role-app
  managed_tgw: True
  avtx_transit: True
  spoke_gw_size: t3.medium
  insane_mode: True
  insane_az1: "a"
  insane_az2: "b"
```

- `account_id` is a list of accounts where you want to run the discovery.
- `aws_region` is a list of regions where you want to run the discovery. If `aws_region` is not specified, the script will run the discovery in all AWS regions. Be sure to comment out the "aws_region:" line as well and not just the list of regions if you want to perform the discovery in all regions.
- `controller` contains information about the Aviatrix Controller including the IP and username to log in as. You will be prompted for the Aviatrix Controller password when running the script.
- `defaults` contains default values that will be populated in the Excel file. The defaults can be changed as required.

**Note:** YAML is picky about the spacing/identation. If you see errors when running the scripts, confirm that the spacing/indentation is correct.

## Generate YAML file for use with general network discovery

If you want use [Discovery Migration](https://github.com/aviatrix-automation/discovery_migration) to perform general network discovery, typically you need to pass in a YAML file like the following:

```
account_info:
  - account_id: '012345678900'
    role_name: aviatrix-role-app
    aws_region: us-east-1
    vpcs:
      - vpc-005e7091aa01b8c38
  - account_id: '123456789000'
    role_name: aviatrix-role-app
    aws_region: us-west-2
    vpcs:
```

For large environments with a lot of VPCs, creating this file can be tedious and error-prone. Discovery Generator can automatically generate this YAML file with all of the VPCs discovered in the account_ids/aws_regions specified in `config.yaml`.

To run the script:

```
python3 generate.py config.yaml --discovery discovery.yaml
```

`discovery.yaml` (or your specified filename) is the output file that can be used by [Discovery Migration](https://github.com/aviatrix-automation/discovery_migration) to perform network discovery.

## Generate YAML file for staging VPCs and switching traffic

Discovery Generator can generate a YAML file that can be used by [Discovery Migration](https://github.com/aviatrix-automation/discovery_migration) to stage a VPC for migration or to switch traffic. This is a multi-step process. The first step will be to generate an Excel file with as much information populated as possible:

- Defaults for many values are read from the configuration file `config.yaml`
- The account name is retrieved from the Aviatrix Controller
- AWS TGW ID and Owner is retreived from AWS
- Unused /26 subnets are discovered for use with Insane Mode

The Excel file is updated as needed and then converted to YAML.

### 1. Generate Excel

```
python3 generate.py config.yaml --excel customer.xlsx
```

### 2. Update Excel

The Excel file will require some manual updates and modifications.

- Remove any VPCs that will not be migrated
- Specify which Aviatrix Transit Gateway to attach each Spoke Gateway to
- Verify that the script was able to find two available /26 subnets in each VPC
- Modify additional settings as needed

### 3. Convert Excel to YAML

```
python3 convert_excel_to_yaml.py --excel customer.xlsx --yaml customer.yaml
```

The Excel file will then be converted to a `customer.yaml` (or your specified filename) for use with [Discovery Migration](https://github.com/aviatrix-automation/discovery_migration) to stage VPCs and to switch traffic.

## Additional Information

The discovery YAML file and the Excel file can be generated simultaneously.

```
python3 generate.py config.yaml --discovery discovery.yaml --excel customer.xlsx
```
