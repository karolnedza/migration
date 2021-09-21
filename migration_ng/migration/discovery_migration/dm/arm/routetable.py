import logging
import ipaddress
from dm.arm.commonlib import Common as common
import pdb
class RouteTable:
    def __init__(self,id,tags,isFilter=True):
        self.id = id
        foundName = False
        self.tags = {}
        self.knownTgwId = ""
        self.staticRouteCount = 0
        # 1. copy tags
        # 2. if a Name tag is found, update theNname in Name tag
        # 3. if no Name tag, deduce route table name from id
        if tags != None:
            for key, val in tags.items():
                if key == 'Name':
                    self.tags['Name'] =  f"aviatrix-{val}"
                    foundName = True
                else:
                    self.tags[key] = val
        if not foundName:
            idObj = self.id.split("/")            
            self.tags['Name'] = f"aviatrix-{idObj[-1]}"

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

        self.main = "False"
        self.isFilter = isFilter
        self.publicTable = False
        self.accessInternalNetwork = False
        self.hasRfc1918 = False
        self.ctrl_managed = True
        self.disableBgpPropagation = "false"
        self.logger = logging.getLogger(__name__)

    def getId(self):
        return self.id

    def setRegion(self, region):
        self.region = region

    def setDisableBgpPropagation(self, propagate):
        self.disableBgpPropagation = propagate
    
    def add(self,route):
        # if route.origin != 'EnableVgwRoutePropagation':
        #     self.staticRouteCount = self.staticRouteCount + 1

        # if route.target.startswith("igw-"):
        #     self.publicTable = True
        # elif route.target.startswith("vgw-"):
        #     self.accessInternalNetwork = True
        # elif route.target.startswith("tgw-"):
        #     self.accessInternalNetwork = True            

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

    def isFilterRoute(self,dest,target):
        try:
            ipn = ipaddress.ip_network(dest)
            # filter RFC1918 for exact match
            destStr = dest.strip()
            for n in self.rfcCidrs:
                if destStr == n:
                    self.hasRfc1918 = True
                    return True

            # For alert purpose, check if this route table has Rfc1918 route
            if not target == 'local':
                if (self.isRfc1918(ipn)):
                    self.hasRfc1918 = True

            # filter yaml input filter_cidrs with subset
            for n in self.ipv4Cidrs:
                if self._is_subnet_of(ipn,n):
                    return True
        except ValueError:
            pass

        # tfvars (c): filter tgw/vgw
        if target != None and (target == 'local' or target.startswith('vgw-') or target.startswith('tgw-')):
            return True
        # elif target.startswith('tgw-') and target == self.knownTgwId:
        #     return True

        return False

    def addFilters(self,cidrs):
        for cidr in cidrs:
            self.ipv4Cidrs.append(ipaddress.ip_network(cidr))

    def addKnownTgwId(self,tgwId):
        self.knownTgwId = tgwId

    def addAdditonalTags(self, tags):
        for t in tags:
            key = t['Key']
            val = t['Value']
            self.tags[key] = val

    def toDict(self):
        routeTable = {}

        routeTable['Main'] = self.main
        routeTable['ctrl_managed'] = self.ctrl_managed
        routeTable['region'] = self.region
        routeTable['disable_bgp_propagation'] = self.disableBgpPropagation
        routes = {}        
        for key, value in self.routes.items():
            routes[key] = value.toDict()
        routeTable['routes'] = routes

        routeTable['tags'] = self.tags

        return routeTable

    def toHcl(self,outfile,ident):
        space = ident * ' '
        key = f'org_{self.id}'
        outfile.write(f'{space}"{key}" = {{\n')
        outfile.write(f'{space}  Main = "{self.main}"\n')
        outfile.write(f'{space}  ctrl_managed = "{self.ctrl_managed}"\n')
        outfile.write(f'{space}  region = "{common.REGION[self.region]}"\n')
        outfile.write(f'{space}  disable_bgp_propagation = "{self.disableBgpPropagation}"\n')

        outfile.write(f'{space}  routes = {{\n')
        for key, value in self.routes.items():
            value.toHcl(outfile,ident+4)
        outfile.write(f'{space}  }}\n')        

        outfile.write(f'{space}  tags = {{\n')
        for key, value in self.tags.items():
            outfile.write(f'{space}    "{key}" = "{value}"\n')
        outfile.write(f'{space}  }}\n')        
        outfile.write(f'{space}}}\n')
