from dm.arm.routetables import RouteTables

import pdb
class Subscriptions:
    def __init__(self):
        self.subs = {}

    def add(self, subId, vnetName, routeTables):
        if not subId in self.subs:
            self.subs[subId] = []
        self.subs[subId].append({vnetName: routeTables})

    # { 
    #   subscription1: [ {vnet1: routeTables1} ],
    #   subscription2: [ {vnet2: routeTables2} ],            
    # }
    def toDict(self):
        subs = {}
        for subsId, lstOfVnets in self.subs.items():
            subs[subsId] = []
            for vnetObj in lstOfVnets:
                for vnet, rtbs in vnetObj.items():
                    rtbsObj = rtbs.toDict()
                    subs[subsId].append({vnet: rtbsObj})
        return subs