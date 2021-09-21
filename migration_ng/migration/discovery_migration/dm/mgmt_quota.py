#!/usr/bin/python3

import logging
import logging.config
import argparse
import botocore
import dm.logconf as logconf
from dm.commonlib import Common as common
import pdb

if __name__ == "__main__":
    # logging.config.fileConfig(fname='log.conf')
    logging.config.dictConfig(logconf.logging_config)
    logconf.logging_config['handlers']['consoleHandler']['level'] = logging.INFO
    logconf.logging_config['loggers']['dm']['handlers'] = ['consoleHandler']
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger("dm")

    args_parser = argparse.ArgumentParser(
        description='Request quota increase')
    args_parser.add_argument('accountId', metavar='accountId', type=str)
    args_parser.add_argument('region', metavar='region', type=str)
    args_parser.add_argument('role_arn', metavar='role_arn', type=str)
    args_parser.add_argument('resource', help='manage quota increase for resource, e.g. eip', metavar='resource', type=str)
    args_parser.add_argument('--req_quota', help='new quota limit')
    args_parser.add_argument('--req_id', help='check request status')
    args = args_parser.parse_args()

    role_arn = common.get_role_arn({
        'account_id': args.accountId,
        'role_name': args.role_arn
    })
    creds = common.get_temp_creds_for_account(role_arn)
    sq_client = common.get_sq_client_handler(args.region, creds)

    # EIP
    if args.resource == 'eip':
        try:
            response = sq_client.get_service_quota(
                ServiceCode="ec2", QuotaCode="L-0263D0A3")
            if not 'ErrorReason' in response:
                logger.info(f'{response["Quota"]["QuotaName"]}: {response["Quota"]["Value"]}')                
            else:
                logger.error(f'{response["ErrorReason"]["ErrorMessage"]}')
        except Exception as e:
            logger.error(e)

        if args.req_id:
            try:
                response = sq_client.get_requested_service_quota_change(RequestId=args.req_id)
                logger.info(f'ID:           {response["RequestedQuota"]["Id"]}')
                logger.info(f'Requester:    {response["RequestedQuota"]["Requester"]}')
                logger.info(f'Quota Name:   {response["RequestedQuota"]["QuotaName"]}')
                logger.info(f'Status:       {response["RequestedQuota"]["Status"]}')
                logger.info(f'Created:      {response["RequestedQuota"]["Created"]}')
                logger.info(f'Last Updated: {response["RequestedQuota"]["LastUpdated"]}')                
            except Exception as e:
                logger.error(e)
        
        if args.req_quota:
            try:
                response = sq_client.request_service_quota_increase(
                    ServiceCode="ec2", QuotaCode="L-0263D0A3", DesiredValue=float(args.req_quota))
                logger.info(f'Id:         {response["RequestedQuota"]["Id"]}')
                logger.info(f'Quota Name: {response["RequestedQuota"]["QuotaName"]}')                
                logger.info(f'Status:     {response["RequestedQuota"]["Status"]}')
            except Exception as e:
                logger.error(e)
        
