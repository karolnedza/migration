class RouteTables:
    def __init__(self,vpcId):
        self.rTables = {}
        self.vpcId = vpcId
        self.association = {}
        self.tgwId = None
        self.filterCidrs = []
        self.expectedCidrs = []
        self.tgwList = []
        self.mainRouteTableId = None

    def setMainRouteTable(self, rtbId):
        self.mainRouteTableId = rtbId
    
    def getMainRouteTable(self):
        return self.mainRouteTableId

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

    def setExpectedCidrs(self, cidrs):
        self.expectedCidrs = cidrs

    def getExpectedCidrs(self):
        return self.expectedCidrs

    def addSubnetRtbAssociation(self,subnetId,rtbId):
        self.association[subnetId] = rtbId

    def getRtbIdFromAssociation(self,subnetId):
        if subnetId in self.association:
            return self.association[subnetId]
        else:
            return self.mainRouteTableId

    def add(self,rTable):
        id = rTable.getId()
        self.rTables[id] = rTable
    
    def get(self,rtbId):
        if rtbId in self.rTables:
            return self.rTables[rtbId]
        else:
            return None
    
    def toDict(self):
        rtbsName = f'route_tables_{self.vpcId}'
        rTables = {
            rtbsName : {}
        }
        for k, v in self.rTables.items():
            key = f'org_{k}'
            rTables[rtbsName][key] = v.toDict()
        return rTables

    def toHcl(self,outfile,ident=0):
        space = ident * ' '
        rtbsName = f'route_tables_{self.vpcId}'
        outfile.write(f'{space}{rtbsName} = {{\n')

        for k, v in self.rTables.items():
            key = f'org_{k}'            
            v.toHcl(outfile,ident+2)

        outfile.write(f'{space}}}\n')
