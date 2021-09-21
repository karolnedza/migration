from azure.mgmt.network import NetworkManagementClient
from dm.arm.lib.arm_utils import _check_cred_id
from dm.arm.lib.arm_utils import create_spoke_subnet
from dm.arm.commonlib import Common as common
from dm.aviatrix import Aviatrix as av
from dm.arm.discoverylib import DiscoveryLib as dl
import logging
import pdb

class StageLib:
    @classmethod
    def deploy_spoke_gw_in_vnet(subscription_id, credentials, accounts_data, api_url, CID):
        logger = logging.getLogger('dm')
        if not _check_cred_id(subscription_id, credentials):
            return None

        network_client = NetworkManagementClient(credentials, subscription_id)

        vnet_iter = network_client.virtual_networks.list_all()
        vnets = list(vnet_iter)

        logger.info(f'- Detected {len(vnets)} vnets')
        logger.info("  " + "".rjust(63, "."))
        logger.info("  " + "Vnet name".ljust(25) +
                    "Vnet cidr".ljust(25) + "rg")
        logger.info("  " + "".rjust(63, "."))

        subscription_ids = accounts_data['account_info']
        pdb.set_trace()
        for vnet in vnets:
            # info = 'vnet_name: ' + vnet.name + \
            #        ' vnet_cidr: ' + vnet.address_space.address_prefixes[0]
            logger.info(
                f'  {vnet.name.ljust(25)}{vnet.address_space.address_prefixes[0].ljust(25)}{vnet.id.split("/")[4]}')

        for vnet in vnets:
            common.logVnetHeader(vnet)
            pdb.set_trace()
            dl.list_subnets(vnet)
            # Create two subnets

            # create_spoke_subnet
            # create_subnet(subscription_id, credentials, region, group_name, vnet_name, subnet_name,
            #                 vnet_cidr, subnet_cidr)
            response = av.create_spoke_gw(
                            api_endpoint_url=api_url+"api",
                            CID=CID,
                            vpc_access_account_name=account['acc_name'],
                            vpc_region_name=account['aws_region'],
                            vpc_id=vpc.id,
                            avx_tgw_name=account['transit_gw'],
                            gw_name=gw_name,
                            gw_size=gw_size,
                            insane_subnet_1=account['insane_az1'],
                            insane_subnet_2=account['insane_az2'],
                            spoke_routes=",".join(account['spoke_routes']),
                            insane_mode=account['insane_mode'],
                            route_table_list=",".join(new_rtbs),
                            keyword_for_log="avx-migration-function---",
                            indent="    ",
                            ec2_resource=ec2_resource)