class Subnets:
    def __init__(self,vpcId,routeTables):
        self.publicCount = 0
        self.privateCount = 0
        self.subnets = []
        self.routeTables = routeTables
        self.vpcId = vpcId

    def add(self, subnet):
        subId = subnet.getId()
        rtbId = self.routeTables.getRtbIdFromAssociation(subId)
        rtb = self.routeTables.get(rtbId)
        if rtb.isPublic():
            subnet.setPublic()
            self.publicCount = self.publicCount + 1
            subnet.setResourceName(f'{self.vpcId}-public-{self.publicCount}')
        else:
            self.privateCount = self.privateCount + 1            
            subnet.setResourceName(f'{self.vpcId}-private-{self.privateCount}')
        self.subnets.append(subnet)

    def toHcl(self,outfile,ident=0):
        for sub in self.subnets:
            sub.toHcl(outfile,ident)

    def toTfImport(self,outfile,ident=0):
        for sub in self.subnets:
            sub.toTfImport(outfile,ident)

    def toUndoTfimport(self,outfile,ident=0):
        for sub in self.subnets:
            sub.toUndoTfimport(outfile,ident)
