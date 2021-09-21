class Subnet:
    def __init__(self,subnet,regionInfo):
        self.subnet_id = subnet.subnet_id
        self.map_public_ip_on_launch = subnet.map_public_ip_on_launch
        self.availability_zone = subnet.availability_zone
        self.cidr_block = subnet.cidr_block
        self.vpc_id = subnet.vpc_id
        self.tags = []
        self.tagKeyList = []        
        if subnet.tags != None:
            for tag in subnet.tags:
                self.tags.append(
                    {
                        'Key': tag['Key'],
                        'Value': tag['Value']
                    }
                )
                self.tagKeyList.append(tag['Key'])
        self.isPublic = False
        self.resourceName = ""
        self.tfRegion = regionInfo['alias']

    def setPublic(self):
        self.isPublic = True

    def setResourceName(self,name):
        self.resourceName = name

    def getId(self):
        return self.subnet_id

    def addAdditonalTags(self, tags):
        for t in tags:
            if not t['Key'] in self.tagKeyList:
                self.tags.append(t)

    def toHcl(self,outfile,ident=0):
        space = ident * ' '

        outfile.write(f'{space}resource "aws_subnet" "{self.resourceName}" {{\n')
        outfile.write(f'{space}  vpc_id = "{self.vpc_id}"\n')
        outfile.write(f'{space}  cidr_block = "{self.cidr_block}"\n')
        outfile.write(f'{space}  availability_zone = "{self.availability_zone}"\n')

        outfile.write(f'{space}  tags = {{\n')
        for tag in self.tags:
            key = tag['Key']
            if key.startswith("aws:"):
                continue
            value = tag['Value']
            outfile.write(f'{space}    "{key}" = "{value}"\n')
        outfile.write(f'{space}  }}\n')
        outfile.write(f'{space}  provider = aws.{self.tfRegion}\n')
        outfile.write(f'{space}}}\n\n')

    def toTfImport(self,outfile,ident=0):
        outfile.write(f'terraform import aws_subnet.{self.resourceName} {self.subnet_id}\n')

    def toUndoTfimport(self,outfile,ident=0):
        outfile.write(f'terraform state rm aws_subnet.{self.resourceName}\n')
        