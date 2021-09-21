import pdb

class RouteTables:
    def __init__(self,subscriptionId):
        self.rTables = {}
        self.subscriptionId = subscriptionId
        self.association = {}
        self.tgwId = None
        self.filterCidrs = []
        self.tgwList = []

    def setTgwId(self,tgwId):
        self.tgwId = tgwId

    def getTgwId(self):
        return self.tgwId

    def setTgwList(self,tgwList):
        if tgwList == None:
            self.tgwList = []
        else:
            self.tgwList = tgwList

    def getTgwList(self):
        return self.tgwList
    
    def setFilterCidrs(self, cidrs):
        self.filterCidrs = cidrs

    def getFilterCidrs(self):
        return self.filterCidrs

    def addSubnetRtbAssociation(self,subnetId,rtbId):
        self.association[subnetId] = rtbId

    def getRtbIdFromAssociation(self,subnetId):
        if subnetId in self.association:
            return self.association[subnetId]
        else:
            return None

    def getRouteTableCount(self):
        return len(self.rTables)

    def add(self,rTable):
        id = rTable.getId()
        self.rTables[id] = rTable
    
    def get(self,rtbId):
        if rtbId in self.rTables:
            return self.rTables[rtbId]
        else:
            return None
    
    def toDict(self):
        rtbsName = f'route_tables_{self.subscriptionId}'
        rTables = {
            rtbsName : {}
        }
        for k, v in self.rTables.items():
            idObj = k.split("/")
            idObj[-1] = v.tags['Name']
            key = "/".join(idObj)
            rTables[rtbsName][key] = v.toDict()
        return rTables

    def toHcl(self,outfile,ident=0):
        space = ident * ' '
        rtbsName = f'route_tables_{self.subscriptionId}'
        outfile.write(f'{space}{rtbsName} = {{\n')

        for k, v in self.rTables.items():
            v.toHcl(outfile,ident+2)

        outfile.write(f'{space}}}\n')
