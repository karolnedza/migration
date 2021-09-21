import json
from os import path
from os import makedirs
import os
from string import Template
import shutil
import logging
import sys
import pathlib
from dm.commonlib import Common as common

class Terraform:

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
    def subnetsToHcl(cls, region, vpcId, subnets):
        with open(f'{cls.base}/aws-{region}-{vpcId}.tf', 'a') as outfile:
            subnets.toHcl(outfile)

    @classmethod
    def subnetsToTfImport(cls, subnets):
        with open(f'{cls.base}/terraform-import-subnets.sh', 'a') as outfile:
            subnets.toTfImport(outfile)

    @classmethod
    def undoSubnetsToTfImport(cls, vpcId, subnets, tag=None):
        composeTag = ''
        if tag != None:
            composeTag = f'-{tag}'

        with open(f'{cls.base}/tmp/terraform-undo-import-subnets{composeTag}.sh', 'a') as outfile:
            subnets.toUndoTfimport(outfile)

    @classmethod
    def routeTablesToDict(cls, region, vpcId, routeTables):
        with open(f'{cls.base}/aws-{region}-{vpcId}.auto.tfvars.json', 'w') as outfile:
            outfile.write(json.dumps(routeTables.toDict(), indent=2))

    @classmethod
    def storeRevertInfo(cls, stInfo):
        if cls.DryRun:
            return
        
        if not path.exists(f'{cls.base}/tmp'):
            makedirs(f'{cls.base}/tmp')

        with open(f'{cls.base}/tmp/revert.json', 'w') as outfile:
            outfile.write(json.dumps(stInfo, indent=2))

    @classmethod
    def readRevertInfo(cls):
        if path.exists(f'{cls.base}/tmp/revert.json'):
            with open(f'{cls.base}/tmp/revert.json', 'r') as ifile:
                return json.load(ifile)
        return {
            "vpcid-tf-size": {},
            "static": {},
            "propagated": {}
        }

    @classmethod
    def deleteRevertInfo(cls):
        logger = logging.getLogger(__name__)
        logger.info(f'- Remove {cls.base}/tmp/revert.json')
        if cls.DryRun:
            return

        os.remove(f'{cls.base}/tmp/revert.json')

    @classmethod
    def isRevertInfoExist(cls):
        logger = logging.getLogger(__name__)
        if path.exists(f'{cls.base}/tmp/revert.json'):
            return True
        return False

    @classmethod
    def storeJsonInfo(cls, fname, info):
        with open(f'{cls.base}/tmp/{fname}', 'w') as outfile:
            outfile.write(json.dumps(info, indent=2))

    @classmethod
    def readJsonInfo(cls,fname):
        if path.exists(f'{cls.base}/tmp/{fname}'):
            with open(f'{cls.base}/tmp/{fname}', 'r') as ifile:
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
            outfile.write("\n")            

        # cls.updateVariablesTf(data['route_tables'])

    @classmethod
    def updateSwitchTraffic(cls, data):
        logger = logging.getLogger(__name__)
        vpcId = data['vpc_id']        
        infile = f"{cls.base}/aws-{data['region']}-{vpcId}.tf"
        if data['switch_traffic']:
            logger.info(f'- Set switch_traffic to true in {infile}')
        else:
            logger.info(f'- Set switch_traffic to false in {infile}')

        if cls.DryRun:
            return

        outfile = f"{cls.base}/aws-{data['region']}-{vpcId}.tf.output"
        with open(infile, 'r') as ifile:
            with open(outfile, 'w') as ofile:
                for line in ifile:
                    if line.strip().startswith("switch_traffic"):
                        if data['switch_traffic']:
                            ofile.write(line.replace(f'switch_traffic = false', 'switch_traffic = true'))
                        else:
                            ofile.write(line.replace(f'switch_traffic = true', 'switch_traffic = false'))
                    else:
                        ofile.write(line)

        shutil.copyfile(outfile, infile)
        os.remove(outfile)

        # with fileinput.FileInput(input_file, inplace=True, backup='.bak') as file_object:
        #     for line in file_object:
        #         if line.strip().startswith("switch_traffic"):
        #             if data['switch_traffic']:
        #                 print(line.rstrip().replace(f'switch_traffic = false', 'switch_traffic = true'))
        #             else:
        #                 print(line.rstrip().replace(f'switch_traffic = true', 'switch_traffic = false'))
        #         else:
        #             print(line.rstrip())


    @classmethod
    def generateTfVars(cls, data):
        if cls.DryRun:
            return
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/terraform.tfvars') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform.tfvars', 'w') as outfile:
            outfile.write(result)

    @classmethod
    def generateVersionTf(cls, data):
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/versions.tf') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{cls.base}/versions.tf', 'w') as outfile:
            outfile.write(result)

    @classmethod
    def deleteTfImport(cls):
        if os.path.exists(f'{cls.base}/terraform-import-subnets.sh'):
            os.remove(f'{cls.base}/terraform-import-subnets.sh')

    @classmethod
    def deleteUndoSubnetsTfImport(cls,tag=None):
        composeTag = ''
        if tag != None:
            composeTag = f'-{tag}'

        if os.path.exists(f'{cls.base}/tmp/terraform-undo-import-subnets{composeTag}.sh'):
            os.remove(f'{cls.base}/tmp/terraform-undo-import-subnets{composeTag}.sh')

    @classmethod
    def updateVariablesTf(cls, name):
        with open(f'{cls.base}/variables.tf', 'a') as outfile:
            outfile.write(f'variable "{name}" {{}}\n')


    S3_BACKEND = """\
terraform {
  backend "s3" {}
}        
"""

    @classmethod
    def setupAccountFolder(cls, base, yamlObj):
        cls.base = base
        if not path.exists(f'{base}/tmp'):
            makedirs(f'{base}/tmp')

        with open(f'{cls.DmPath}/../vpc_template/main.tf') as rf:
            src = Template(rf.read())
            if yamlObj['enable_s3_backend'] == True:
                result = src.substitute({'s3_backend': cls.S3_BACKEND})
            else:
                result = src.substitute({'s3_backend': ''})
        with open(f'{cls.base}/main.tf', 'w') as f:
            f.write(result)

        shutil.copyfile(f'{cls.DmPath}/../vpc_template/variables.tf',
                        f'{cls.base}/variables.tf')
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/providers.tf',
                        f'{cls.base}/providers.tf')

    @classmethod
    def generateOnboardAccountTf(cls,isGenerate):
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/main.tf') as rf:
            src = Template(rf.read())
            if isGenerate:
                result = src.substitute({'count': 1})
            else:
                result = src.substitute({'count': 0})

        with open(f'{cls.base}/main.tf', 'w') as f:
            f.write(result)

    @classmethod
    def generateModuleFolder(cls, base, gw_name_format=common.HEX_CIDR):

        target = f'{base}/module_aws_brownfield_spoke_vpc'        
        if not path.exists(target):
            makedirs(target)

        if gw_name_format == common.HEX_CIDR:
            shutil.copyfile(f'{cls.DmPath}/../vpc_template/module_aws_brownfield_spoke_vpc/main-hex-cidr.tf', f'{target}/main.tf')
        else:
            shutil.copyfile(f'{cls.DmPath}/../vpc_template/module_aws_brownfield_spoke_vpc/main-vpc-name.tf', f'{target}/main.tf')
        shutil.copyfile(f'{cls.DmPath}/../vpc_template/module_aws_brownfield_spoke_vpc/variables.tf', 
                        f'{target}/variables.tf')

    @classmethod
    def generateModuleVersionsTf(cls, base, data):
        target = f'{base}/module_aws_brownfield_spoke_vpc'

        result = ""
        with open(f'{cls.DmPath}/../vpc_template/module_aws_brownfield_spoke_vpc/versions.tf') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{target}/versions.tf', 'w') as outfile:
            outfile.write(result)

    @classmethod
    def copyYaml(cls, base, yaml):
        if not path.exists(base):
            makedirs(base)

        shutil.copyfile(f'./{yaml}', f'{base}/discovery.yaml')

    # The following functions are used by switch_traffic
    #

    @classmethod
    def setSwitchTrafficTargetFolder(cls, base):
        cls.base = base

    @classmethod
    def storeFileSize(cls, filename, revertInfo):
        logger = logging.getLogger(__name__)

        with open(f"{cls.base}/{filename}",'a') as outfile:
            outfile.seek(0, os.SEEK_END)
            fsize = outfile.tell()
            fabs = f"{cls.base}/{filename}"
            revertInfo['vpcid-tf-size'][fabs] = fsize
            logger.info(f'- Store {cls.base}/{filename} size {fsize} in revert info')
    
    @classmethod
    def revertFile(cls, filename, revertInfo):
        logger = logging.getLogger(__name__)
        if cls.DryRun:
            return

        fabs = f"{cls.base}/{filename}"
        fsize = revertInfo['vpcid-tf-size'][fabs]

        logger.info(f'- Revert {cls.base}/{filename}')

        if fsize == 0:
            os.remove(f'{cls.base}/{filename}')
            return

        with open(f"{cls.base}/{filename}","a") as outfile:
            outfile.seek(fsize)
            outfile.truncate()

    @classmethod
    def deleteSubnetAssociationTf(cls):
        if cls.DryRun:
            return
        if os.path.exists(f'{cls.base}/terraform-import-associations.sh'):
            os.remove(f'{cls.base}/terraform-import-associations.sh')

    @classmethod
    def deleteUndoSubnetAssociationTf(cls):
        if cls.DryRun:
            return
        if os.path.exists(f'{cls.base}/tmp/terraform-undo-import-associations.sh'):
            os.remove(f'{cls.base}/tmp/terraform-undo-import-associations.sh')

    @classmethod
    def createSubnetAssociationTf(cls, data):

        if cls.DryRun:
            return
        
        result = ""
        with open(f'{cls.DmPath}/../vpc_template/subnet-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        vpcId = data['vpc_id']
        with open(f"{cls.base}/aws-{data['region']}-{vpcId}.tf", 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

        with open(f'{cls.DmPath}/../vpc_template/terraform-import-associations.sh') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform-import-associations.sh', 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

        with open(f'{cls.base}/tmp/terraform-undo-import-associations.sh', 'a') as outfile:
            outfile.write(f'terraform state rm aws_route_table_association.{data["rname"]}\n')

    @classmethod
    def createMainRtbAssociationTf(cls, data):

        if cls.DryRun:
            return

        result = ""
        with open(f'{cls.DmPath}/../vpc_template/main-rtb-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        vpcId = data['vpc_id']
        with open(f"{cls.base}/aws-{data['region']}-{vpcId}.tf", 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

        with open(f'{cls.base}/tmp/terraform-undo-import-associations.sh', 'a') as outfile:
            outfile.write(f'terraform state rm aws_main_route_table_association.{data["rname"]}\n')
