class Subnets:
    def __init__(self,vnetName):
        self.publicCount = 0
        self.privateCount = 0
        self.subnets = []
        self.vnetName = vnetName

    def add(self, subnet):
        self.publicCount = self.publicCount + 1
        # subnet.setResourceName(f'{self.vnetName}-{self.publicCount}')
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
