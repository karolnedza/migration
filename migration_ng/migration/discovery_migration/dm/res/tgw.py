from dm.aws import Aws as aws
import logging

class Tgw:
    def __init__(self, ec2_client,regionObj):
        self.logger = logging.getLogger(__name__)

        self.tgwId = None
        # setup tgw ID for unexpected route alert
        #
        # 1) If yaml has tgw account Id, role, and tgwId, lookup tgw 
        # and verify that tgwId matches.
        # 2) If yaml has no account ID, no tgw lookup needed
        # 3) If yaml provides account Id and role, lookup tgwId
        # 4) Alert any route that does not match tgwId.
        self.logger.info(f'- Discover TGW')
        tgwId = aws.getTgwId(ec2_client)
        if tgwId == None:
            self.logger.warning(f'  **Alert** no TGW found for VPCs in {regionObj["region"]}')
        elif regionObj["diy_tgw_id"] == None:
            self.logger.info(f'  no given tgw, discovered {tgwId}')
        elif not regionObj["diy_tgw_id"] == tgwId:
            self.logger.warning(f'  **Alert** given {regionObj["diy_tgw_id"]} does not match the one discovered {tgwId}')
        else:
            self.logger.info(f'  given tgwId {regionObj["diy_tgw_id"]} matches the one discovered {tgwId}')
        self.tgwId = tgwId
    
    def getId(self):
        return self.tgwId

    def tgwRouteCheck(self):
        pass