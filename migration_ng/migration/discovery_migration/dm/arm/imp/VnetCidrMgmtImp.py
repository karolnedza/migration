from dm.arm.inf.VnetCidrMgmtInf import VnetCidrMgmtInf
from dm.arm.commonlib import Common as common
import copy

class ClusterVnetCidrMgmt(VnetCidrMgmtInf):
    """
    Read MGMT_VNET_CIDR yaml that defines subscriptions, vnets and vnet cidrs relation.

    """
    def getAccountList(self, accounts_data):
        return accounts_data['vnet_cidr']

    def intLogLocation(self, accounts_data):
        return common.intLogLocationMgmtVnetCidr(accounts_data)


class MigrateVnetCidrMgmt(VnetCidrMgmtInf):
    """
    This class expects AZURE yaml form of input and returns
    subscription info of the following MGMT_VNET_CIDR format:

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
    """    
    def getAccountList(self, accounts_data):
        subObjList = copy.deepcopy(accounts_data['terraform']['azurerm'])
        for subObj in subObjList:
            subObj['vnets'] = {}

        for sub in accounts_data['account_info']:
            # compose vnetDict:
            vnetDict = {}
            for vnetObj in sub['vnets']:
                key = vnetObj['vnet_name']
                val = vnetObj['avtx_cidr']
                vnetDict[key] = val
            
            # add vnetDict into subObjList
            for subObj in subObjList:
                if sub['subscription_id'] == subObj['arm_subscription_id']:
                    subObj['vnets'] = vnetDict

        return subObjList

    def intLogLocation(self, accounts_data):
        return common.initLogLocation(accounts_data)