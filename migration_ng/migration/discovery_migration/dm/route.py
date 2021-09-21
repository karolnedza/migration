class Route:
    def __init__(self, route, nhop):
        self.target = nhop
        self.origin = route['Origin']
        if ('DestinationPrefixListId' in route):
            self.dest = route['DestinationPrefixListId']
        elif ('DestinationIpv6CidrBlock' in route):
            self.dest = route['DestinationIpv6CidrBlock']
        else:
            self.dest = route['DestinationCidrBlock']
        self.state = route['State']

    def getDest(self):
        return self.dest

    def getState(self):
        return self.state

    def toDict(self):
        return {
            "destination": self.dest,
            "target": self.target
        }

    def toHcl(self,outfile,ident):
        space = ident * ' '
        outfile.write(f'{space}{self.id} = {{\n')
        outfile.write(f'{space}  destination = "{self.dest}"\n')
        outfile.write(f'{space}  target = "{self.target}"\n')        
        outfile.write(f'{space}}}\n')