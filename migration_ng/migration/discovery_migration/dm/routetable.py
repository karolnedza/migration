import logging
import ipaddress

class RouteTable:
    def __init__(self,id,tags,isFilter=True):
        self.id = id
        foundName = False
        self.tags = []
        self.knownTgwId = ""
        self.staticRouteCount = 0
        self.tagKeyList = []
        for t in tags:
            if t['Key'] == 'Name':
                self.tags.append({'Key': 'Name', 'Value': f"aviatrix-{t['Value']}"})
                foundName = True
            else:
                self.tags.append(t)
            self.tagKeyList.append(t['Key'])
        if not foundName:
            self.tags.append({'Key': 'Name', 'Value': f"aviatrix-"})
            self.tagKeyList.append('Name')

        # self.tags = [ {'Key': t['Key'], 'Value': f"aviatrix-{t['Value']}"} if t['Key'] == 'Name' else t for t in tags ]

        self.routes = {}
        self.count = 0
        self.rfcCidrs = [
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16'
        ]
        self.rfcCidrNetworks = [
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16')
        ]
        
        self.ipv4Cidrs = []
        self.expectedIpv4Cidrs = []

        self.main = "False"
        self.isFilter = isFilter
        self.publicTable = False
        self.accessInternalNetwork = False
        self.hasRfc1918 = False
        self.ctrl_managed = True
        self.logger = logging.getLogger(__name__)

    def getId(self):
        return self.id
    
    def add(self,route):
        if route.origin != 'EnableVgwRoutePropagation':
            self.staticRouteCount = self.staticRouteCount + 1

        # do not copy route if they are NOT in active state
        if route.getState() != 'active':
            return False

        if route.target.startswith("igw-"):
            self.publicTable = True
        elif route.target.startswith("vgw-"):
            self.accessInternalNetwork = True
        elif route.target.startswith("tgw-"):
            self.accessInternalNetwork = True            

        if (self.isFilter and self.isFilterRoute(route.dest,route.target)):
            return False
        self.count = self.count + 1
        routeId = f'route_{self.count}'
        route.id = routeId
        self.routes[routeId] = route
        return True
    
    def setMain(self,isMain):
        if isMain:
            self.main = "True"
            self.tags = [ {'Key': t['Key'], 'Value': f'aviatrix-main'} if t['Key'] == 'Name' and t['Value'] == 'aviatrix-' else t for t in self.tags ]
        else:
            self.main = "False"

    def isPublic(self):
        return self.publicTable

    def isAccessInternalNetwork(self):
        return self.accessInternalNetwork

    def hasRfc1918Route(self):
        return self.hasRfc1918

    @staticmethod
    def _is_subnet_of(a, b):
        try:
            # Always false if one is v4 and the other is v6.
            if a._version != b._version:
                raise TypeError(f"{a} and {b} are not of the same version")
            return (b.network_address <= a.network_address and
                    b.broadcast_address >= a.broadcast_address)
        except AttributeError:
            raise TypeError(f"Unable to test subnet containment "
                            f"between {a} and {b}")

    def isRfc1918(self,ipn):
        for n in self.rfcCidrNetworks:
            if self._is_subnet_of(ipn,n):
                return True
        return False

    def isRfc1918ExactMatch(self,ip):
        ipStr = ip.strip()
        for n in self.rfcCidrs:
            if ipStr == n:
                return True
        return False

    def isInFilterCidrRange(self,ipn):
        for n in self.ipv4Cidrs:
            if self._is_subnet_of(ipn,n):
                return True
        return False

    def isInExpectedCidrRange(self,ip):
        ipn = ipaddress.ip_network(ip)
        for n in self.expectedIpv4Cidrs:
            if self._is_subnet_of(ipn,n):
                return True
        return False

    def isFilterRoute(self,dest,target):
        try:
            # filter RFC1918 for exact match
            # tfvars 8(d): Exclude RFC1918 summaries
            if self.isRfc1918ExactMatch(dest):
                self.hasRfc1918 = True
                return True

            # filter out IPv6 route, not able to handle
            ipn = ipaddress.ip_network(dest)
            if type(ipn) is ipaddress.IPv6Network:
                return True

            # For alert purpose, check if this route table has Rfc1918 route
            if not target == 'local':
                if (self.isRfc1918(ipn)):
                    self.hasRfc1918 = True

            # filter yaml input filter_cidrs with subset
            # tfvars 8(d): Exclude 146.197.x.x
            if self.isInFilterCidrRange(ipn):
                return True
        except ValueError:
            pass

        # tfvars 8(c): Exclude routes with the next-hop = TGW/VGW 
        if target == 'local' or target.startswith('vgw-') or target.startswith('tgw-'):
            return True
        # elif target.startswith('tgw-') and target == self.knownTgwId:
        #     return True

        return False

    def addFilters(self,cidrs):
        for cidr in cidrs:
            self.ipv4Cidrs.append(ipaddress.ip_network(cidr))

    def addExpectedCidrs(self,cidrs):
        for cidr in cidrs:
            self.expectedIpv4Cidrs.append(ipaddress.ip_network(cidr))

    def addKnownTgwId(self,tgwId):
        self.knownTgwId = tgwId

    def addAdditonalTags(self, tags):
        for t in tags:
            if not t['Key'] in self.tagKeyList:
                self.tags.append(t)

    def toDict(self):
        routeTable = {}

        routeTable['Main'] = self.main
        routeTable['ctrl_managed'] = self.ctrl_managed
        routes = {}        
        for key, value in self.routes.items():
            routes[key] = value.toDict()
        routeTable['routes'] = routes

        tags = {}
        for tag in self.tags:
            key = tag['Key']
            tags[key] = tag['Value']
        routeTable['tags'] = tags

        return routeTable

    def toHcl(self,outfile,ident):
        space = ident * ' '
        key = f'org_{self.id}'
        outfile.write(f'{space}{key} = {{\n')
        outfile.write(f'{space}  Main = "{self.main}"\n')
        outfile.write(f'{space}  ctrl_managed = "{self.ctrl_managed}"\n')

        outfile.write(f'{space}  routes = {{\n')
        for key, value in self.routes.items():
            value.toHcl(outfile,ident+4)
        outfile.write(f'{space}  }}\n')        

        outfile.write(f'{space}  tags = {{\n')
        for tag in self.tags:
            key = tag['Key']
            if key.startswith("aws:"):
                continue
            value = tag['Value']
            outfile.write(f'{space}    "{key}" = "{value}"\n')
        outfile.write(f'{space}  }}\n')        
        outfile.write(f'{space}}}\n')
