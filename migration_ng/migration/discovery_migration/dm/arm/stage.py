#!/usr/bin/python3

import logging
import logging.config
from re import sub
import sys
import os
import argparse
import getpass
import json

from azure.mgmt import subscription
from dm.terraform import Terraform as tf
from dm.arm.routetables import RouteTables as AvxRouteTables
import dm.logconf as logconf
from dm.arm.commonlib import Common as common
from dm.arm.discoverylib import DiscoveryLib as dl
from dm.arm.lib.arm_utils import get_ad_sp_credential, list_subscriptions
from dm.arm.lib.arm_utils import create_route_tables
from dm.arm.lib.arm_utils import delete_route_tables
from dm.arm.stagelib import StageLib as sl
from dm.arm.lib.arm_utils import create_spoke_subnet
from dm.arm.lib.arm_utils import delete_spoke_subnet
from dm.arm.lib.arm_utils import get_all_vnets
from dm.arm.io import ArmIO as avxio
from dm.aviatrix import Aviatrix as av
import pdb


if __name__ == "__main__":
    # logging.config.fileConfig(fname='dm/log.conf')
    logging.config.dictConfig(logconf.logging_config)
    logger = logging.getLogger('dm')

    args_parser = argparse.ArgumentParser(
        description='Get VPC info from account(s)')
    args_parser.add_argument('file_path', metavar='yaml_file_path', type=str)
    args_parser.add_argument(
        '--ctrl_user', help='Aviatrix Controller username')
    args_parser.add_argument(
        '--revert', help='revert staging', action='store_true', default=False)
    args_parser.add_argument(
        '--tfvars_json', help='Output route table in tfvars.json', action='store_true', default=False)
    args = args_parser.parse_args()

    if args.ctrl_user:
        ctrl_pwd = getpass.getpass(prompt="Aviatrix Controller Password:")
        logger.info("")

    iargs = " ".join(sys.argv[1:])
    common.logCommandOptions(f'dm.stage {iargs}')

    input_file = args.file_path
    if not os.path.isfile(input_file):
        logger.error('YAML File does not exist')
        sys.exit()

    accounts_data = common.convert_yaml_to_json(input_file)
    target_folder = accounts_data['terraform']['terraform_output']

    CID = ""
    api_ep_url = None
    if args.ctrl_user:
        api_ep_url = "https://" + accounts_data['controller_ip'] + "/v1/"

        # Login to Controller and save CID
        try:
            response = av.login(api_endpoint_url=api_ep_url+"api",
                         username=args.ctrl_user,
                         password=ctrl_pwd)
            CID = response.json()["CID"]
        except KeyError:
            logger.info("Check your password")
            sys.exit()
        except Exception as e:
            logger.error(e)
            sys.exit()

    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    arm_tenant_id = os.getenv('AZURE_TENANT_ID')
    arm_client_id = os.getenv('AZURE_CLIENT_ID')
    arm_client_secret = os.getenv('AZURE_CLIENT_SECRET')

    credential = get_ad_sp_credential(arm_tenant_id, arm_client_id, arm_client_secret)

    allsubs = avxio.readJsonInfo(f"rt.json")
    pdb.set_trace()

    subs = list_subscriptions(credential)
    for subId, rtbs in allsubs.items():
        common.logSubscription(subId)
        if args.revert == False:
            create_route_tables(subscription_id,credential,rtbs)
        else:
            delete_route_tables(subscription_id,credential,rtbs)

    vnets = get_all_vnets(subscription_id, credential)
    for vnet in vnets:
        pdb.set_trace()
        if args.revert == False:
            create_spoke_subnet(subscription_id, credential, vnet)
            sl.deploy_spoke_gw_in_vnet(subscription_id, credential, accounts_data, api_ep_url, CID)
        else:
            delete_spoke_subnet(subscription_id, credential, vnet)                                                                                                                                                                                                                                                                                      