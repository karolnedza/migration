import json
from os import path
from os import makedirs
import os
from string import Template
import shutil
import logging
import sys
import pathlib
from dm.arm.commonlib import Common as common

class Terraform:

    DryRun = False
    DmPath = f'{pathlib.Path(__file__).parent.absolute()}/../../vnet_template'

    @classmethod
    def setDryRun(cls):
        cls.DryRun = True

    @classmethod
    def routeTablesToHcl(cls, vnetName, routeTables):
        if routeTables.getRouteTableCount() == 0:
            return
        with open(f'{cls.base}/{vnetName}.auto.tfvars', 'w') as outfile:
            routeTables.toHcl(outfile)

    @classmethod
    def subnetsToHcl(cls, vnetName, subnets):
        with open(f'{cls.base}/{vnetName}.tf', 'a') as outfile:
            subnets.toHcl(outfile)

    @classmethod
    def subnetsToTfImport(cls, vnet, subnets):
        with open(f'{cls.base}/terraform-import-subnets.sh', 'a') as outfile:
            outfile.write(f'terraform import azurerm_virtual_network.{vnet.name} {vnet.id}\n')
            subnets.toTfImport(outfile)

    @classmethod
    def undoSubnetsToTfImport(cls, vnet, subnets, tag=None):
        composeTag = ''
        if tag != None:
            composeTag = f'-{tag}'

        with open(f'{cls.base}/tmp/terraform-undo-import-subnets{composeTag}.sh', 'a') as outfile:
            outfile.write(f'terraform state rm azurerm_virtual_network.{vnet.name}\n')
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
        if not path.exists(f'{cls.base}/tmp'):
            makedirs(f'{cls.base}/tmp')

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
    def generateVnetTf(cls, data):
        result = ""
        with open(f'{cls.DmPath}/vnet_id.tf') as f:
            src = Template(f.read())
            result = src.substitute(data)

        vnetName = data['vnet_name']
        with open(f"{cls.base}/{vnetName}.tf", 'w') as outfile:
            outfile.write(result)
            outfile.write("\n")            

        # cls.updateVariablesTf(data['route_tables'])

    @classmethod
    def generateVnetResourceTf(cls, data):
        vnetName = data['vnet_name']
        region = data['region']
        resource_group = data['resource_group']
        vnet_cidr = data['vnet_cidr']
        tags = data['tags']
        provider = data['provider']
        with open(f"{cls.base}/{vnetName}.tf", 'a') as outfile:
            outfile.write(f'resource "azurerm_virtual_network" "{vnetName}" {{\n')
            outfile.write(f'  location            = "{region}"\n')
            outfile.write(f'  name                = "{vnetName}"\n')
            outfile.write(f'  resource_group_name = "{resource_group}"\n')
            outfile.write(f'  address_space       = {vnet_cidr}\n')
            if len(tags) > 0:
                outfile.write(f'  tags                = {{\n')
                for key, val in tags.items():
                    outfile.write(f'    {key} = "{val}"\n')
                outfile.write(f'  }}\n')
            else:
                outfile.write(f'  tags                = {{}}\n')
            outfile.write(f'  lifecycle {{\n')
            outfile.write(f'    ignore_changes = [tags]\n')
            outfile.write(f'  }}\n')
            outfile.write(f'  provider            = azurerm.{provider}\n')
            outfile.write(f'}}\n\n')

    @classmethod
    def updateSwitchTraffic(cls, data):
        logger = logging.getLogger(__name__)
        vnet_name = data['vnet_name']        
        infile = f"{cls.base}/{vnet_name}.tf"
        if data['switch_traffic']:
            logger.info(f'- Set switch_traffic to true in {infile}')
        else:
            logger.info(f'- Set switch_traffic to false in {infile}')

        if cls.DryRun:
            return

        outfile = f"{cls.base}/{vnet_name}.tf.output"
        with open(infile, 'r') as ifile:
            with open(outfile, 'w') as ofile:
                for line in ifile:
                    if line.strip().startswith("switch_traffic"):
                        if data['switch_traffic']:
                            ofile.write(line.replace(f'switch_traffic      = false', 'switch_traffic      = true'))
                        else:
                            ofile.write(line.replace(f'switch_traffic      = true', 'switch_traffic      = false'))
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
        with open(f'{cls.DmPath}/terraform.tfvars') as f:
            src = Template(f.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform.tfvars', 'w') as outfile:
            outfile.write(result)

    @classmethod
    def generateVersionTf(cls, data):
        result = ""
        with open(f'{cls.DmPath}/versions.tf') as f:
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

    @classmethod
    def setupAccountFolder(cls, base, yamlObj):
        logger = logging.getLogger(__name__)
        cls.base = base
        if not path.exists(f'{base}/tmp'):
            makedirs(f'{base}/tmp')

        # shutil.copyfile(f'{cls.DmPath}/main.tf', f'{cls.base}/main.tf')
        # shutil.copyfile(f'{cls.DmPath}/providers.tf', f'{cls.base}/providers.tf')
        shutil.copyfile(f'{cls.DmPath}/variables.tf',
                        f'{cls.base}/variables.tf')
        # shutil.copyfile(f'{cls.DmPath}/account.tf', f'{cls.base}/account.tf')
        try:
            subId = yamlObj['terraform']['aviatrix_account']['arm_subscription_id']
            clientId = yamlObj['terraform']['aviatrix_account']['arm_application_id']
            clientSecret = yamlObj['terraform']['aviatrix_account']['arm_application_secret_data_src']
            tenantId = yamlObj['terraform']['aviatrix_account']['arm_directory_id']
        except Exception as e:
            logger.warning(f'  **Alert** Skip aviatrix_account resource generation. Failed to read terraform/aviatrix_account attribute: {e}')
            return

        accountName = yamlObj['terraform']['aviatrix_account']['account_name']
        with open(f'{cls.base}/account.tf', 'w') as outfile:
            outfile.write(f'resource "aviatrix_account" "azure" {{\n')
            outfile.write(f'  cloud_type          = 8\n')
            outfile.write(f'  arm_subscription_id = "{subId}"\n')
            outfile.write(f'  arm_application_id  = "{clientId}"\n')
            outfile.write(f'  arm_application_key = {clientSecret}\n')
            outfile.write(f'  arm_directory_id    = "{tenantId}"\n')
            outfile.write(f'  account_name        = "{accountName}"\n')
            outfile.write(f'}}\n\n')
        # shutil.copyfile(f'{cls.DmPath}/providers.tf',
        #                 f'{cls.base}/providers.tf')

    @classmethod
    def generateProviderTf(cls, yamlObj):

        shutil.copyfile(f'{cls.DmPath}/providers.tf', f'{cls.base}/providers.tf')
        with open(f'{cls.base}/providers.tf', 'a') as outfile:
            outfile.write(f'\n')
            for azurerm in yamlObj['terraform']['azurerm']:
                subId = azurerm['arm_subscription_id']
                clientId = azurerm['arm_application_id']
                clientSecret = azurerm['arm_application_secret_data_src']
                tenantId = azurerm['arm_directory_id']
                alias = azurerm['alias']
                outfile.write(f'provider "azurerm" {{\n')
                outfile.write(f'  features {{}}\n')
                outfile.write(f'  skip_provider_registration = true\n')
                outfile.write(f'  subscription_id            = "{subId}"\n')
                outfile.write(f'  client_id                  = "{clientId}"\n')
                outfile.write(f'  client_secret              = {clientSecret}\n')
                outfile.write(f'  tenant_id                  = "{tenantId}"\n')
                outfile.write(f'  alias                      = "{alias}"\n')
                outfile.write(f'}}\n\n')


        # shutil.copyfile(f'{cls.DmPath}/variables.tf',
        #                 f'{cls.base}/variables.tf')
        # shutil.copyfile(f'{cls.DmPath}/account.tf', f'{cls.base}/account.tf')
        # shutil.copyfile(f'{cls.DmPath}/providers.tf',
        #                 f'{cls.base}/providers.tf')


    @classmethod
    def generateOnboardAccountTf(cls,isGenerate):
        result = ""
        with open(f'{cls.DmPath}/main.tf') as rf:
            src = Template(rf.read())
            if isGenerate:
                result = src.substitute({'count': 1})
            else:
                result = src.substitute({'count': 0})

        with open(f'{cls.base}/main.tf', 'w') as f:
            f.write(result)

    @classmethod
    def generateModuleFolder(cls, base):
        target = f'{base}/module_azure_brownfield_spoke_vnet'
        if not path.exists(target):
            makedirs(target)

        shutil.copyfile(f'{cls.DmPath}/module_arm_brownfield_spoke_vnet/main.tf', f'{target}/main.tf')
        shutil.copyfile(f'{cls.DmPath}/module_arm_brownfield_spoke_vnet/variables.tf', 
                        f'{target}/variables.tf')

    @classmethod
    def generateModuleVersionsTf(cls, base, data):
        target = f'{base}/module_azure_brownfield_spoke_vnet'

        result = ""
        with open(f'{cls.DmPath}/module_arm_brownfield_spoke_vnet/versions.tf') as f:
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
            revertInfo['vnetid-tf-size'][fabs] = fsize
            logger.info(f'- Store {cls.base}/{filename} size {fsize} in revert info')
    
    @classmethod
    def revertFile(cls, filename, revertInfo):
        logger = logging.getLogger(__name__)
        if cls.DryRun:
            return

        fabs = f"{cls.base}/{filename}"
        fsize = revertInfo['vnetid-tf-size'][fabs]

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
        with open(f'{cls.DmPath}/subnet-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        vnetName = data['vnet_name']
        with open(f"{cls.base}/{vnetName}.tf", 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

        with open(f'{cls.DmPath}/terraform-import-associations.sh') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        with open(f'{cls.base}/terraform-import-associations.sh', 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

        with open(f'{cls.base}/tmp/terraform-undo-import-associations.sh', 'a') as outfile:
            outfile.write(f'terraform state rm azurerm_subnet_route_table_association.{data["rname"]}\n')

    @classmethod
    def createMainRtbAssociationTf(cls, data):

        if cls.DryRun:
            return

        result = ""
        with open(f'{cls.DmPath}/main-rtb-associations.tf') as infile:
            src = Template(infile.read())
            result = src.substitute(data)

        vpcId = data['vpc_id']
        with open(f"{cls.base}/aws-{data['region']}-{vpcId}.tf", 'a') as outfile:
            outfile.write(result)
            outfile.write("\n")

    @classmethod
    def setOutputBase(cls, base):
        cls.base = base