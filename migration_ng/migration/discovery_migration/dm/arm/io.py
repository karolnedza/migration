import json
from os import path
from os import makedirs
import os
from string import Template
import shutil
import logging
import sys
import pathlib

class ArmIO:

    DryRun = False
    DmPath = pathlib.Path(__file__).parent.absolute()

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def routeTablesToHcl(cls, region, vpcId, routeTables):
        with open(f'{cls.base}/aws-{region}-{vpcId}.auto.tfvars', 'w') as outfile:
            routeTables.toHcl(outfile)

    @classmethod
    def routeTablesToDict(cls, region, vpcId, routeTables):
        with open(f'{cls.base}/aws-{region}-{vpcId}.auto.tfvars.json', 'w') as outfile:
            outfile.write(json.dumps(routeTables.toDict(), indent=2))

    @classmethod
    def storeTgwRouteInfo(cls, tgwRtbInfo):
        if cls.DryRun:
            return
        with open(f'aws-tgw-route-info.json', 'w') as outfile:
            outfile.write(json.dumps(tgwRtbInfo, indent=2))

    @classmethod
    def readTgwRouteInfo(cls):
        if path.exists('aws-tgw-route-info.json'):
            with open('aws-tgw-route-info.json', 'r') as ifile:
                return json.load(ifile)
        return {
            "static": {},
            "propagated": {}
        }

    @classmethod
    def checkTgwRouteInfo(cls):
        if cls.DryRun:
            return
        logger = logging.getLogger(__name__)
        if path.exists('aws-tgw-route-info.json'):
            logger.info(
                f'Please remove or backup the last aws-tgw-route-info.json before re-running traffic_switch.')
            sys.exit(1)

    @classmethod
    def storeJsonInfo(cls, fname, info):
        with open(fname, 'w') as outfile:
            outfile.write(json.dumps(info, indent=2))

    @classmethod
    def readJsonInfo(cls,fname):
        if path.exists(fname):
            with open(fname, 'r') as ifile:
                return json.load(ifile)
        return {}

    base = ""

    @classmethod
    def generateVpcTf(cls, data):
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/vpc_id.tf') as f:
            src = Template(f.read())
            result = src.substitute(data)

        vpcId = data['vpc_id']
        with open(f"{cls.base}/aws-{data['region']}-{vpcId}.tf", 'w') as outfile:
            outfile.write(result)

        cls.updateVariablesTf(data['route_tables'])

    @classmethod
    def generateTfVars(cls, data):
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/terraform.tfvars') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform.tfvars', 'w') as outfile:
            outfile.write(result)

    @classmethod
    def updateVariablesTf(cls, name):
        with open(f'{cls.base}/variables.tf', 'a') as outfile:
            outfile.write(f'variable "{name}" {{}}\n')

    @classmethod
    def updateProvidersTf(cls, data):
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/provider.template') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{cls.base}/providers.tf', 'a') as outfile:
            outfile.write("\n")
            outfile.write(result)

    @classmethod
    def setupAccountFolder(cls, base):
        cls.base = base
        if not path.exists(base):
            makedirs(base)

        # Copy versions.tf
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/versions.tf',
                        f'{cls.base}/versions.tf')
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/main.tf', f'{cls.base}/main.tf')
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/variables.tf',
                        f'{cls.base}/variables.tf')
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/providers.tf',
                        f'{cls.base}/providers.tf')

    @classmethod
    def copyYaml(cls, base, yaml):
        cls.base = base
        if not path.exists(base):
            makedirs(base)

        shutil.copyfile(f'./{yaml}', f'{cls.base}/discovery.yaml')

    # The following functions are used by switch_traffic
    #

    @classmethod
    def initSwitchTrafficTf(cls, base):

        if cls.DryRun:
            return

        cls.base = base
        with open(f'{cls.base}/subnet-associations.tf', 'w') as outfile:
            pass
        with open(f'{cls.base}/main-rtb-associations.tf', 'w') as outfile:
            pass
        with open(f'{cls.base}/terraform_import.sh', 'w') as outfile:
            pass

    @classmethod
    def createSubnetAssociationTf(cls, data):

        if cls.DryRun:
            return
        
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/subnet-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        with open(f'{cls.base}/subnet-associations.tf', 'a') as outfile:
            outfile.write("\n")
            outfile.write("\n")
            outfile.write(result)

        with open(f'{cls.DmPath}/../vpc_template/terraform_import.sh') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform_import.sh', 'a') as outfile:
            outfile.write("\n")
            outfile.write(result)

    @classmethod
    def createMainRtbAssociationTf(cls, data):

        if cls.DryRun:
            return

        result = ""
        with open(f'{cls.DmPath}/../vpc_template/main-rtb-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        with open(f'{cls.base}/main-rtb-associations.tf', 'a') as outfile:
            outfile.write("\n")
            outfile.write("\n")
            outfile.write(result)
