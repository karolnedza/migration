from abc import ABC, abstractmethod

class VnetCidrMgmtInf(ABC):

    @abstractmethod
    def getAccountList(self):
        """
        Returns a list of account object from MGMT_VNET_CIDR yaml 
        """
        pass

    @abstractmethod
    def intLogLocation(self, accounts_data):
        pass