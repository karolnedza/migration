#!/usr/bin/python3

import logging
import logging.config
import argparse
import botocore
import dm.logconf as logconf
from dm.commonlib import Common as common

if __name__ == "__main__":
    # logging.config.fileConfig(fname='log.conf')
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger("dm")

    args_parser = argparse.ArgumentParser(
        description='Get VPC info from account(s)')
    # args_parser.add_argument('accountId', metavar='accountId', type=str)
    args_parser.add_argument('region', metavar='region', type=str)
    args_parser.add_argument('role_arn', metavar='role_arn', type=str)
    args_parser.add_argument('vpceId', metavar='vpc_endpoint_id', type=str)
    args_parser.add_argument('routeTableId', metavar='route_table_id', type=str)
    args = args_parser.parse_args()

    # Start iterating over the input yaml

    creds = common.get_temp_creds_for_account(args.role_arn)
    ec2_resource = common.get_ec2_resource_handler(args.region, creds)
    ec2_client = ec2_resource.meta.client

    try:
        response = ec2_client.modify_vpc_endpoint(VpcEndpointId=args.vpceId, AddRouteTableIds=[args.routeTableId])
        print(f"- Added {args.vpceId} to {args.routeTableId}")        
    except botocore.exceptions.ClientError as e:
        print(e)
        print(f"  **Alert** {args.routeTableId} - {args.vpceId} --> Please add this entry manually")
