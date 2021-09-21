import argparse
import boto3
import getpass
import ipaddress
import os
import requests
import xlsxwriter
import yaml
import sys

requests.packages.urllib3.disable_warnings()


def get_account_list(config):
    controller = config["controller"]["ip"]
    username = config["controller"]["username"]
    password = getpass.getpass(
        prompt="Aviatrix Controller " + username + "@" + controller + "'s password:"
    )
    controller_api_url = "https://" + controller + "/v1/api"

    r = requests.post(
        controller_api_url,
        data={"action": "login", "username": username, "password": password},
        verify=False,
    )
    try:
        CID = r.json()["CID"]
    except:
        print(
            "Login failed. Please check Aviatrix Controller IP, username and password."
        )
        sys.exit()
    r = requests.post(
        controller_api_url,
        data={"action": "list_accounts", "CID": CID, "aws_iam_role_based": True},
        verify=False,
    )
    account_list = r.json()["results"]["account_list"]
    return account_list


def get_acct_name(account_id, account_list):
    for account in account_list:
        if account_id == account["account_number"]:
            return account["account_name"]


def get_regions(creds):
    ec2_resource = get_ec2_resource_handler("us-east-1", creds)
    ec2 = ec2_resource.meta.client
    response = ec2.describe_regions()
    regions = response["Regions"]
    list_of_regions = []
    for region in regions:
        list_of_regions.append(region["RegionName"])
    return list_of_regions


def get_subnets(vpc, ec2):
    list_of_subnets = []
    response = ec2.describe_subnets()
    for subnet in response["Subnets"]:
        list_of_subnets.append(subnet["CidrBlock"])
    return list_of_subnets


# Return a list of subnets that don't overlap with existing subnets in the VPC
def get_available_subnets(list_of_vpc_subnets, vpc_cidr, prefix):
    non_overlapping_subnets = []
    new_subnets = ipaddress.ip_network(vpc_cidr).subnets(new_prefix=prefix)
    for subnet in new_subnets:
        # If the subnet doesn't overlap with any subnets in the VPC, append to list
        result = map(
            lambda x: ipaddress.ip_network(subnet).overlaps(ipaddress.ip_network(x)),
            list_of_vpc_subnets,
        )
        if not any(result):
            non_overlapping_subnets.append(str(subnet))
    return non_overlapping_subnets


def get_role_arn(account_id, role_name):
    role_arn = "arn:aws:iam::" + str(account_id) + ":role/" + role_name
    return role_arn


def get_temp_creds_for_account(role_arn):
    sts_client = boto3.client("sts")
    try:
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn, RoleSessionName="AssumeRoleSession1"
        )
    except Exception as e:
        print(e)
        sys.exit(1)
    creds = assumed_role["Credentials"]
    return creds


def get_ec2_resource_handler(aws_region, creds):
    ec2_resource = boto3.resource(
        "ec2",
        region_name=aws_region,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
    return ec2_resource


def create_excel_headers(worksheet):
    worksheet.write(0, 0, "account_id")
    worksheet.write(0, 1, "acc_name")
    worksheet.write(0, 2, "role_name")
    worksheet.write(0, 3, "region")
    worksheet.write(0, 4, "vpc_id")
    worksheet.write(0, 5, "spoke_routes")
    worksheet.write(0, 6, "managed_tgw")
    worksheet.write(0, 7, "transit_gw")
    worksheet.write(0, 8, "diy_tgw_id")
    worksheet.write(0, 9, "diy_tgw_account")
    worksheet.write(0, 10, "avtx_transit")
    worksheet.write(0, 11, "spoke_gw_name")
    worksheet.write(0, 12, "spoke_gw_size")
    worksheet.write(0, 13, "hpe")
    worksheet.write(0, 14, "hpe_az1")
    worksheet.write(0, 15, "hpe_az2")
    worksheet.write(0, 16, "filter_cidrs")
    worksheet.write(0, 17, "gw_zones")
    worksheet.write(0, 18, "avtx_cidr")
    worksheet.set_column(0, 15, 20)


def write_to_excel(worksheet, config):
    row = 1

    try:
        accounts = config["account_id"]
    except KeyError:
        print("account_id not found in", config_file)
        sys.exit()

    try:
        defaults = config["defaults"]
    except KeyError:
        print("defaults not found in", config_file)
        sys.exit()

    for account in accounts:
        role_arn = get_role_arn(account, defaults["role_name"])
        creds = get_temp_creds_for_account(role_arn)

        try:
            regions = config["aws_region"]
        except KeyError:
            regions = get_regions(creds)

        for region in regions:
            ec2_resource = get_ec2_resource_handler(region, creds)
            ec2 = ec2_resource.meta.client
            response = ec2.describe_vpcs()
            vpcs = response["Vpcs"]
            for vpc in vpcs:
                worksheet.write(row, 0, '"' + str(account) + '"')
                worksheet.write(row, 1, get_acct_name(str(account), account_list))
                worksheet.write(row, 2, defaults["role_name"])
                worksheet.write(row, 3, region)
                worksheet.write(row, 4, vpc["VpcId"])
                worksheet.write(row, 5, "[]")
                worksheet.write(row, 6, defaults["managed_tgw"])

                response = ec2.describe_transit_gateway_attachments(
                    Filters=[
                        {"Name": "resource-type", "Values": ["vpc"]},
                        {"Name": "resource-id", "Values": [vpc["VpcId"]]},
                    ]
                )
                if response["TransitGatewayAttachments"]:
                    tgw_id = response["TransitGatewayAttachments"][0][
                        "TransitGatewayId"
                    ]
                    tgw_owner = response["TransitGatewayAttachments"][0][
                        "TransitGatewayOwnerId"
                    ]
                    worksheet.write(row, 8, tgw_id)
                    worksheet.write(row, 9, '"' + tgw_owner + '"')

                worksheet.write(row, 10, defaults["avtx_transit"])

                vpcname = ""
                if "Tags" in vpc:
                    for tag in vpc["Tags"]:
                        if tag["Key"] == "Name":
                            vpcname = tag["Value"]
                spoke_gw_name = (vpcname + "-AVXGW").replace(" ", "_")
                worksheet.write(row, 11, spoke_gw_name)

                worksheet.write(row, 12, defaults["spoke_gw_size"])
                worksheet.write(row, 13, defaults["hpe"])

                hpe_subnets = get_available_subnets(
                    get_subnets(vpc, ec2), vpc["CidrBlock"], 26
                )
                try:
                    hpe_az1 = (
                        '["' + hpe_subnets[0] + '","' + defaults["hpe_az1"] + '"]'
                    )
                except IndexError:
                    hpe_az1 = '["","' + defaults["hpe_az1"] + '"]'
                try:
                    hpe_az2 = (
                        '["' + hpe_subnets[1] + '","' + defaults["hpe_az2"] + '"]'
                    )
                except IndexError:
                    hpe_az2 = '["","' + defaults["hpe_az2"] + '"]'
                worksheet.write(row, 14, hpe_az1)
                worksheet.write(row, 15, hpe_az2)
                worksheet.write(row, 16, '[]')
                worksheet.write(row, 17, defaults["gw_zones"])

                row += 1


def generate_discovery_yaml(config):
    try:
        accounts = config["account_id"]
    except KeyError:
        print("account_id not found in", config_file)
        sys.exit()
    try:
        defaults = config["defaults"]
    except KeyError:
        print("defaults not found in", config_file)
        sys.exit()
    discovery = {"account_info": []}
    for account in accounts:
        role_arn = get_role_arn(account, defaults["role_name"])
        creds = get_temp_creds_for_account(role_arn)
        try:
            regions = config["aws_region"]
        except KeyError:
            regions = get_regions(creds)
        for region in regions:
            ec2_resource = get_ec2_resource_handler(region, creds)
            ec2 = ec2_resource.meta.client
            response = ec2.describe_vpcs()
            vpcs = response["Vpcs"]
            current_region = {
                "account_id": str(account),
                "acc_name": get_acct_name(str(account), account_list),
                "role_name": defaults["role_name"],
                "aws_region": region,
                "vpcs": [],
            }
            for vpc in vpcs:
                current_region["vpcs"].append(vpc["VpcId"])
            discovery["account_info"].append(current_region)
    return discovery


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate discovery yaml and Excel file"
    )
    parser.add_argument(
        "config_file",
        help="Configuration file specifying AWS account_ids and regions, Aviatrix Controller information \
             and default values to populate the Excel file with",
    )
    parser.add_argument(
        "-d",
        "--discovery",
        metavar="discovery_file",
        help="Generates a yaml file for use with the discovery_migration script",
    )
    parser.add_argument(
        "-e",
        "--excel",
        metavar="excel_file",
        help="Generates an Excel file that can be updated and then converted to yaml using convert_excel_to_yaml.py",
    )
    args = parser.parse_args()

    if len(sys.argv) == 2:
        parser.print_help()
        sys.exit()

    config_file = args.config_file
    if not os.path.isfile(args.config_file):
        print("Config file not found:", args.config_file)
        sys.exit()

    config = []
    with open(config_file) as f:
        config = yaml.safe_load(f)

    account_list = get_account_list(config)

    if args.discovery:
        print("Generating discovery file:", args.discovery)
        discovery_yaml = generate_discovery_yaml(config)
        file = open(args.discovery, "w")
        yaml.dump(discovery_yaml, file, sort_keys=False)
        file.close()

    if args.excel:
        print("Generating Excel file:", args.excel)
        workbook = xlsxwriter.Workbook(args.excel)
        worksheet = workbook.add_worksheet()
        create_excel_headers(worksheet)
        write_to_excel(worksheet, config)
        workbook.close()
