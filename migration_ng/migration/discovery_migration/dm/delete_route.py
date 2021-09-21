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
        description='Delete route in VPC route table(s)')
    args_parser.add_argument(
        '--dry_run', help='Dry run delete_route logic and show what will be done', action='store_true', default=False)
    args_parser.add_argument('accountId', metavar='accountId', type=str)
    args_parser.add_argument('role', metavar='role', type=str)    
    args_parser.add_argument('region', metavar='region', type=str)
    args_parser.add_argument('vpcId', metavar='vpc_id', type=str)
    args_parser.add_argument('cidrs', metavar='cidrs', help='list of comma separated cidr, e.g., 1.1.1.0/24,1.1.1.2.0/24', type=str)
    args = args_parser.parse_args()

    # Start iterating over the input yaml

    role_arn = f'arn:aws:iam::{args.accountId}:role/{args.role}'
    creds = common.get_temp_creds_for_account(role_arn)
    ec2_resource = common.get_ec2_resource_handler(args.region, creds)
    ec2_client = ec2_resource.meta.client

    print(f'Remove {args.cidrs} from all route tables in {args.vpcId}:')
    cidrLst = args.cidrs.split(",")
    vpc = ec2_resource.Vpc(args.vpcId)
    for routeTable in vpc.route_tables.all():
        for route in routeTable.routes:
            if route.destination_cidr_block in cidrLst:
                print(f'  delete {route.destination_cidr_block} in {routeTable.id}')
                if args.dry_run == False:
                    route.delete()
    print('Done')

