class Route:
    def __init__(self, route):
        self.target = route.next_hop_ip_address
        self.dest = route.address_prefix
        self.type = route.next_hop_type

    def getDest(self):
        return self.dest

    def toDict(self):
        return {
            "destination": self.dest,
            "target": self.target,
            "type": self.type
        }

    def toHcl(self,outfile,ident):
        space = ident * ' '
        outfile.write(f'{space}{self.id} = {{\n')
        outfile.write(f'{space}  destination = "{self.dest}"\n')
        outfile.write(f'{space}  target = "{self.target}"\n')
        outfile.write(f'{space}  type = "{self.type}"\n')
        outfile.write(f'{space}}}\n')