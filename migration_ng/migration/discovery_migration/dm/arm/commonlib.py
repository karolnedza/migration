import logging
import dm.commonlib
import os
from os import makedirs
from os import path
from dm.arm.lib.arm_utils import get_ad_sp_credential
import dm.logconf as logconf
import sys

class Common(dm.commonlib.Common):

    REGION = {
        'westus'        : 'West US',
        'eastus'        : 'East US',
        'centralus'     : 'Central US',
        'westus2'       : 'West US 2',
        'northeurope'   : 'North Europe',
        'westeurope'    : 'West Europe',
        'southeastasia' : 'Southeast Asia',
        'japaneast'     : 'Japan East',
        'chinaeast2'    : 'China East 2',
        'chinanorth2'   : 'China North 2'
    }

    @classmethod
    def logSubscription(cls, id):
        logger = logging.getLogger(__name__)
        logger.warning("")
        logger.warning("".ljust(45, "+"))
        logger.warning("")
        logger.warning(f"    Subscription ID :  {id}")
        logger.warning("")
        logger.warning("".ljust(45, "+"))
        logger.warning("")

    @classmethod
    def logVnetHeader(cls, vnet):
        logger = logging.getLogger(__name__)

        name = vnet.name
        region = vnet.location
        rg = vnet.id.split('/')[4]
        cidrs = vnet.address_space.address_prefixes

        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")
        logger.info(f"    Vnet Name : {name}")
        logger.info(f"    CIDRs     : {cidrs}")
        logger.info(f"    Region    : {region}")
        logger.info(f"    RG        : {rg}")
        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")

    @classmethod
    def logRouteTableHeader(cls):
        logger = logging.getLogger(__name__)
        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")
        logger.info(f"    Route Tables")
        logger.info("")
        logger.info("".ljust(45, "-"))
        logger.info("")

    @classmethod
    def getAzureSubscriptionCred(cls,YAML,subscriptionId):
        logger = logging.getLogger(__name__)
        try:
            subscriptionInfo = YAML['subscriptionMap'][subscriptionId]
        except:
            logger.error(f'**Error** Missing arm_subscription_id defintion for {subscriptionId}')
            return None

        arm_tenant_id = subscriptionInfo['dir_id']
        arm_client_id = subscriptionInfo['app_id']
        arm_client_secret =  os.getenv(subscriptionInfo['secret_env'])
        credential = get_ad_sp_credential(arm_tenant_id, arm_client_id, arm_client_secret)
        if credential == None:
            logger.error(f'**Error** Failed to get Azure account credential for {subscriptionId}')
            return None
        
        cred = {
            'subscription_id': subscriptionId,
            'credentials': credential,
        }
        return cred

    @classmethod
    def getArmAccountName(cls, yamlObj):
        logger = logging.getLogger(__name__)
        accountName = 'AzureDev'
        try:
            accountName = yamlObj['terraform']['aviatrix_account']['account_name']
        except:
            logger.error(f'**Error** failed to read account name from yaml. Use default {accountName}')
        return accountName

    @classmethod
    def getAviatrixAccount(cls, yamlObj):
        logger = logging.getLogger(__name__)
        aviatrix_account = None
        try:
            aviatrix_account = yamlObj['terraform']['aviatrix_account']
        except:
            logger.error(f'**Error** failed to read terraform aviatrix account from yaml.')
        return aviatrix_account

    @classmethod
    def getAzurermSubscriptionInfo(cls, yamlObj):
        logger = logging.getLogger(__name__)
        aviatrix_account = None
        subMap = {}
        for azurerm in yamlObj['terraform']['azurerm']:
            subId = azurerm['arm_subscription_id']
            secret_env = azurerm['arm_application_secret_env']
            app_id = azurerm['arm_application_id']
            dir_id = azurerm['arm_directory_id']
            alias = azurerm['alias']
            subMap[subId] = {}
            subMap[subId]['secret_env'] = secret_env
            subMap[subId]['app_id'] = app_id
            subMap[subId]['dir_id'] = dir_id
            subMap[subId]['alias'] = alias

        return subMap

    @classmethod
    def getControllerPrivateIp(cls, yamlObj):
        logger = logging.getLogger(__name__)
        controller_private_ip = None
        try:
            controller_private_ip = yamlObj['aviatrix']['controller_private_ip']
        except:
            pass
        return controller_private_ip

    @classmethod
    def expectYamlType(cls,accounts_data,expectYamlFile):
        # logger is not available yet.
        if cls.getLabel(accounts_data) != expectYamlFile:
            print(f'**Alert** Expect YAML for {expectYamlFile}, got {cls.getLabel(accounts_data)} instead!')
            sys.exit()

    @classmethod
    def getPreStageDefaultRouteTable(cls, yamlObj):
        logger = logging.getLogger(__name__)
        default_rt = None
        try:
            default_rt = yamlObj['prestage']['default_route_table']
        except:
            pass
        return default_rt
    
    #
    # MGMT_VNET_CIDR section
    #
    @classmethod
    def getLogFolder(cls, yamlObj):
        logger = logging.getLogger(__name__)
        try:
            return yamlObj['log_output']
        except:
            logger.warning(f'**Alert** output folder attribute log_output not defined, default to "./"')
        return "./"

    @classmethod
    def intLogLocationMgmtVnetCidr(cls, accounts_data):
        target_folder = accounts_data['log_output']
        logFolder = f'{target_folder}/log'
        if not path.exists(logFolder):
            makedirs(logFolder)
        logconf.logging_config['handlers']['logConsoleHandler']['filename'] = f'{logFolder}/dm.log'
        logconf.logging_config['handlers']['alertHandler']['filename'] = f'{logFolder}/dm.alert.log'
        return logconf

    @classmethod
    def getVnetCidrSubscriptionInfo(cls, yamlObj):
        logger = logging.getLogger(__name__)
        aviatrix_account = None
        subMap = {}
        for azureSub in yamlObj['vnet_cidr']:
            subId = azureSub['arm_subscription_id']
            secret_env = azureSub['arm_application_secret_env']
            app_id = azureSub['arm_application_id']
            dir_id = azureSub['arm_directory_id']
            subMap[subId] = {}
            subMap[subId]['secret_env'] = secret_env
            subMap[subId]['app_id'] = app_id
            subMap[subId]['dir_id'] = dir_id
        return subMap

    @classmethod
    def getSubscriptionVnets(cls, subscription):
        try:
            if len(subscription['vnets']) == 0:
                return {}
            return subscription['vnets']
        except:
            return {}


    
