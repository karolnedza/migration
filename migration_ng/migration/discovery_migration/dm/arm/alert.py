import logging
import pdb
class Alert:

    @classmethod
    def setupAlerts(cls,yamlObj):
        logger = logging.getLogger(__name__)
        try:
            for aKey, aVal in yamlObj['alert'].items():
                cls.AlertTable[aKey.lower()] = aVal
        except KeyError as e:
            logger.error(f'  {e}')


    # alert (2g) VNET name > 31 characters
    VNET_NAME_LENGTH_ALERT = 'vnet_name_length'
    VNET_PEERING = 'vnet_peering'

    AlertTable = {
        VNET_NAME_LENGTH_ALERT: 31,
        VNET_PEERING: False
    }

    @classmethod
    def alertVnetNameLength(cls,vnetObj):
        logger = logging.getLogger(__name__)
        if cls.AlertTable[cls.VNET_NAME_LENGTH_ALERT] > 0:
            if len(vnetObj.name)  > cls.AlertTable[cls.VNET_NAME_LENGTH_ALERT]:
                logger.warning(f'  **Alert** vnet name {vnetObj.name} has more than {cls.AlertTable[cls.VNET_NAME_LENGTH_ALERT]} chars')

    @classmethod
    def alertVnetPeering(cls,vnetObj):
        logger = logging.getLogger(__name__)
        if cls.AlertTable[cls.VNET_PEERING] == True:
            if len(vnetObj.virtual_network_peerings) > 0:
                logger.warning(f'  **Alert** vnet peering found in {vnetObj.name}')

