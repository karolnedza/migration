import pdb

class Subnet:
    RG_I = 4
    VNET_I = 8

    def __init__(self,subnet):
        self.rgName = subnet.id.split('/')[self.RG_I]
        self.vnetName = subnet.id.split('/')[self.VNET_I]
        self.subnet_id = subnet.id
        self.cidr_block = subnet.address_prefix
        self.subnetName = subnet.name
        self.tags = {}
        self.tagKeyList = []
        self.delegations = subnet.delegations
        self.serviceEndpoints = []
        if subnet.service_endpoints != None:
            self.serviceEndpoints = [ str(x.service) for x in subnet.service_endpoints ]
        self.isPublic = True
        self.resourceName = f'{self.vnetName}_{self.subnetName}'.replace('.','_')
        self.provider = ''

    def setPublic(self):
        self.isPublic = True

    def setResourceName(self,name):
        self.resourceName = name

    def setProvider(self,name):
        self.provider = name

    def getId(self):
        return self.subnet_id

    def addAdditonalTags(self, tags):
        for t in tags:
            if not t['Key'] in self.tagKeyList:
                key = t['Key']
                val = t['Value']
                self.tags[key] = val


    def toHcl(self,outfile,ident=0):
        space = ident * ' '

        outfile.write(f'{space}resource "azurerm_subnet" "{self.resourceName}" {{\n')
        outfile.write(f'{space}  name = "{self.subnetName}"\n')
        outfile.write(f'{space}  resource_group_name = "{self.rgName}"\n')
        outfile.write(f'{space}  virtual_network_name = "{self.vnetName}"\n')
        outfile.write(f'{space}  address_prefixes = ["{self.cidr_block}"]\n')
        if len(self.serviceEndpoints) > 0:
            # spstr = ",".join(self.serviceEndpoints)
            spStr = str(self.serviceEndpoints).replace("'",'"')
            outfile.write(f'{space}  service_endpoints = {spStr}\n')

        for delegate in self.delegations:
            outfile.write(f'{space}  delegation {{\n')
            outfile.write(f'{space}    name = "{delegate.name}"\n')
            outfile.write(f'{space}    service_delegation {{\n')
            outfile.write(f'{space}      name = "{delegate.service_name}"\n')
            daStr = str(delegate.actions).replace("'",'"')
            outfile.write(f'{space}      actions = {daStr}\n')
            outfile.write(f'{space}    }}\n')
            outfile.write(f'{space}  }}\n')

        outfile.write(f'{space}  provider = azurerm.{self.provider}\n')
        outfile.write(f'{space}}}\n\n')


    def toTfImport(self,outfile,ident=0):
        outfile.write(f'terraform import azurerm_subnet.{self.resourceName} {self.subnet_id}\n')

    def toUndoTfimport(self,outfile,ident=0):
        outfile.write(f'terraform state rm azurerm_subnet.{self.resourceName}\n')
        