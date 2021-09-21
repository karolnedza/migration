__author__ = 'lmxiang'

import time
import http.client
import xmltodict
import traceback
import copy
from collections import OrderedDict
import json
from azure.servicemanagement import *
from azure.servicemanagement import ServiceManagementService
from azure.servicemanagement import OSVirtualHardDisk
from azure.servicemanagement import LinuxConfigurationSet
from azure.mgmt.compute import ComputeManagementClient
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.network.network_management_client import NetworkManagementClient

MS_MANAGEMENT_HOST = 'management.core.windows.net'

rtb_xml_template ="""
<RouteTable xmlns="http://schemas.microsoft.com/windowsazure">
        <Name>R0uTeTaBlEnAmE</Name>
        <Label>R0uTeTaBlEnAmElAbEl</Label>
        <Location>R0uTeTaBlEnAmEl0CaTi0N</Location>
</RouteTable>"""

SHORT_COUNTER = 120
LONG_COUNTER = 300


def ipstring_to_int(ip_addr):
    ip = ip_addr.split('.')
    return ((int(ip[0])<<24) + (int(ip[1])<<16) + (int(ip[2])<<8) + int(ip[3]))


def cidrstring_to_ipint(cidr, ipaddr):
    cidr = cidr.split('/')[0]
    ip = cidr.split('.')
    return ((int(ip[0])<<24) + (int(ip[1])<<16) + (int(ip[2])<<8) + int(ipaddr))


def int_to_ipstring(number):
    ip0 = str(number>>24)
    ip1 = str((number - (number & 0xFF000000))>>16)
    ip2 = str((number - (number & 0xFFFF0000))>>8)
    ip3 = str((number - (number & 0xFFFFFF00)))
    return (ip0 + '.' + ip1 + '.' + ip2 + '.' + ip3)


def calculate_vpc_subnet_bitlen(local_subnet_size):
    if local_subnet_size == 24:
        vpc_subnet_bitlen = 2
    elif local_subnet_size == 23:
        vpc_subnet_bitlen = 3
    else:
        vpc_subnet_bitlen = 4
    return vpc_subnet_bitlen


def get_xml_header_length():
    import xml.dom.minidom as xml
    header = xml.Document()
    declaration = header.toxml('utf-8')
    length = len(declaration)+1
    return length


def get_xml_from_json(json_input):
    length = get_xml_header_length()
    xml_with_header = xmltodict.unparse(json_input, pretty=True)
    xml_no_header = xml_with_header[length:]
    return xml_no_header


def validate_vnet_name(logger, vnet_name):
        logger.info('validate_vnet_name vnet_name=' + vnet_name)
        if set('[~!@#$%^&*()_+{}":;\']+$|?<>').intersection(vnet_name) \
                or '=' in vnet_name or '.' in vnet_name \
                or '/' in vnet_name or ("\\" in r"%r" % vnet_name):
            logger.error('VNet name should not contain special characters. Aborting...')
            return False
        if ' ' in vnet_name:
            logger.error('VNet name should not contain white space.  Aborting...')
            return False
        if len(vnet_name) >= 15:
            logger.error('VNet name cannot exceed 15 characters')
            return False
        return True


def get_vnet_name_with_local_ip(vnet_name):
    from tests.main import variables as _variables
    local_private_ip = _variables['cloudn_ip']
    if not '---' in vnet_name:
        vnet_name_with_local_ip = vnet_name + '---' + local_private_ip.replace('.','-')
    else:
        vnet_name_with_local_ip = vnet_name
    return vnet_name_with_local_ip


def vnet_name_in_azure(subscription_id, cert_path, vnet_name):
    from tests.main import variables as _variables
    local_private_ip = _variables['cloudn_ip']
    sms = ServiceManagementService(subscription_id, cert_path)
    vnets = [vn.name for vn in sms.list_virtual_network_sites()]
    vnet_name_with_ip = vnet_name + '---' + local_private_ip.replace('.', '-')
    if vnet_name_with_ip in vnets:
        return True
    else:
        return False


def azure_api_works(logger, account_name, subscription_id, certificate_path):
    # 1. read the account and get Azure subscription id and pem
    # 2. connect to Azure
    # 3. do try and except to:
    #       result = sms.list_locations()
    # if no exception, return True, else return False
    sms = ServiceManagementService(subscription_id, certificate_path)
    try:
        sms.list_locations()
        logger.debug("Azure API for %s works", account_name)
        return True
    except:
        logger.debug("Azure API for %s doesn't work", account_name)
        return False


def get_image_name(logger):
    image = 'https://carmelostorage.blob.core.windows.net/vhds/CN-bfef19fb/CloudN-Azure-05282015-os-2015-05-28.vhd'
#    from tests.main import variables as _variables
#    image = _variables['azure_image']
    try:
        cloudn_image_url = image.split('\n')[0]
        tmp = cloudn_image_url.split('.')[-2]
        gw_image_name = tmp.split('/')[-1]
    except:
        logger.error('cloudn azure image file parsing error, exiting...')
        return ''

    logger.info('image name %s', gw_image_name)
    return gw_image_name


def form_new_vnet_json_with_vnet_name_with_local_ip(logger, vnet_name, location, cidr, subnet_arry):
    new_vnet = {}
    new_vnet['@name'] = vnet_name
    new_vnet['@Location'] = location
    address_space = {}
    address_space['AddressPrefix'] = cidr
    new_vnet['AddressSpace'] = address_space
    subnet = {}
    sns = []
    i = 0
    no_of_subnet = len(subnet_arry)
    logger.info('Subnets are %s', str(subnet_arry))
    while i < no_of_subnet:
        sn = {}
        sn['@name'] = subnet_arry[i]['name']
        sn['AddressPrefix'] = subnet_arry[i]['AddressPrefix']
        sns.append(sn)
        i = i + 1
    subnet['Subnet'] = sns
    new_vnet['Subnets'] = subnet
    return new_vnet


def get_empty_vnet_json():
    empty_vnet = {}
    empty_vnet_sites = {}
    empty_vnet_sites['VirtualNetworkSite'] = []
    empty_vnet_conf = {}
    empty_vnet_conf['VirtualNetworkSites'] = empty_vnet_sites
    empty_ntwk_config = {}
    empty_ntwk_config['@xmlns']="http://schemas.microsoft.com/ServiceHosting/2011/07/NetworkConfiguration"
    empty_ntwk_config['VirtualNetworkConfiguration'] = empty_vnet_conf
    empty_vnet['NetworkConfiguration'] = empty_ntwk_config
    return empty_vnet


def get_existing_vnet_json_from_azure(logger, subscription_id, cert_file, vnet_name):
    conn = http.client.HTTPSConnection(MS_MANAGEMENT_HOST,
                                       cert_file=cert_file, key_file=cert_file)
    conn.request('GET', '/%s/services/networking/media' % subscription_id,
                 headers={'x-ms-version': '2015-04-01', 'Content-Type': 'text/plain'})
    result = conn.getresponse().read()
    conn.close()
    if bytes('ResourceNotFound', 'UTF-8') in result:
        return {}
    else:
        result_json = xmltodict.parse(result)
        try:
            sites = result_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite']
        except:
            return {}
        try:
            # this is multiple-vnet case
            for site in sites:
                name = site['@name']
                if name == vnet_name:
                    location = site['@Location']
                    cidr = site['AddressSpace']['AddressPrefix']
                    subnet_array = []
                    try:
                        for sub in site['Subnets']['Subnet']:
                            subnet_item = {}
                            subnet_item['name'] = sub['@name']
                            subnet_item['AddressPrefix'] = sub['AddressPrefix']
                            subnet_array.append(subnet_item)
                    except:
                        print(site['Subnets']['Subnet']['@name'])
                        subnet_item = {}
                        subnet_item['name'] = site['Subnets']['Subnet']['@name']
                        subnet_item['AddressPrefix'] = site['Subnets']['Subnet']['AddressPrefix']
                        subnet_array.append(subnet_item)
                    new_node = form_new_vnet_json_with_vnet_name_with_local_ip(logger, name, location, cidr, subnet_array)
                    return new_node
            return {}
        except:
            # this is single case
            # need to re-construct the json result
            # to make VirtualNetworkSite an array
            name = sites['@name']
            if name == vnet_name:
                location = sites['@Location']
                cidr = sites['AddressSpace']['AddressPrefix']
                subnet_array = []
                try:
                    one_subnet_only = sites['Subnets']['Subnet'][0]
                    for sub in sites['Subnets']['Subnet']:
                        subnet_item = {}
                        subnet_item['name'] = sub['@name']
                        subnet_item['AddressPrefix'] = sub['AddressPrefix']
                        subnet_array.append(subnet_item)
                except:
                    logger.error(sites['Subnets']['Subnet']['@name'])
                    subnet_item = {}
                    subnet_item['name'] = sites['Subnets']['Subnet']['@name']
                    subnet_item['AddressPrefix'] = sites['Subnets']['Subnet']['AddressPrefix']
                    subnet_array.append(subnet_item)
                new_node = form_new_vnet_json_with_vnet_name_with_local_ip(logger, name, location, cidr, subnet_array)
                return new_node
            else:
                return {}


def get_all_existing_vnets_json_from_azure(logger, subscription_id, cert_file):
    conn = http.client.HTTPSConnection(MS_MANAGEMENT_HOST,
                                       cert_file=cert_file, key_file=cert_file)
    conn.request('GET', '/%s/services/networking/media' % subscription_id,
           headers={'x-ms-version': '2015-04-01',
           'Content-Type': 'text/plain'})
    result = conn.getresponse().read()
    conn.close()

    logger.info('original xml:')
    logger.info(result)

    if 'ResourceNotFound' in result.decode('utf-8'):
        logger.info('get_all_existing_vnets_json_from_azure has no existing VNet')
        return get_empty_vnet_json()
    else:
        result_json = xmltodict.parse(result)
        logger.info('original vnet json')
        logger.info(json.dumps(result_json, indent=2))
        try:
            sites = result_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite']
        except:
            return result_json
        try:
            # this is multiple-vnet case
            one_site_only = sites[0]
            return result_json
        except:
            # this is single case
            # need to re-construct the json result
            # to make VirtualNetworkSite an array
            new_node = copy.deepcopy(sites)
            logger.info('new node json')
            logger.info(json.dumps(new_node, indent=2))
            vnet_sites = result_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']
            vnet_sites['VirtualNetworkSite'] = []
            vnet_sites['VirtualNetworkSite'].append(new_node)

            logger.info('final vnet json')
            logger.info(json.dumps(vnet_sites, indent=2))
            return  result_json
            #new_vnet = add_one_vnet_json(vnet_json, new_node)
            return new_vnet


def get_vnet_subnets_in_azure(logger, subscription_id, cert_path, vnet_name):
    vnet_info = get_existing_vnet_json_from_azure(logger, subscription_id, cert_path, vnet_name)
    vnet_subnets = vnet_info['Subnets']['Subnet']
    return vnet_subnets


def get_role_instance_status(deployment, role_instance_name):
    for role_instance in deployment.role_instance_list:
        if role_instance.instance_name == role_instance_name:
            return role_instance.instance_status
    return None


def wait_for_async(logger, sms, request_id, max_count):
    count = 0
    result = sms.get_operation_status(request_id)
    while result.status == 'InProgress':
        count = count + 1
        if count > max_count:
            logger.error("timeout for async wait......")
            return 'Failed'
        time.sleep(2)
        result = sms.get_operation_status(request_id)

    if result.status != 'Succeeded':
        if result.error:
            error = 'Asynchronous operation error code: ' + result.error.code
            logger.error(error)
            return result.error.code
        logger.error('Asynchronous operation did not succeed.....' + result.status)
        return 'Failed'
    else:
        return 'Succeeded'


def wait_for_role(logger, sms, service_name, deployment_name, role_instance_name, max_count, status='ReadyRole'):
    count = 0
    props = sms.get_deployment_by_name(service_name, deployment_name)
    while get_role_instance_status(props, role_instance_name) != status:
        count = count + 1
        if count > max_count:
           logger.error('Azure timeout waiting for role instance status.')
           return False
        time.sleep(5)
        props = sms.get_deployment_by_name(service_name, deployment_name)
    return True


def wait_for_deployment(logger, sms, service_name, deployment_name, state):
    logger.info('vm and cs are %s %s and state is %s', service_name,deployment_name, state)
    count = 0
    max_count = 360
    props = sms.get_deployment_by_name(service_name, deployment_name)
    while props.status != state:
        count = count + 1
        if count > max_count:
           logger.error('Azure timeout waiting for deployment status.')
           return False
        time.sleep(5)
        props = sms.get_deployment_by_name(service_name, deployment_name)
    return True


def wait_for_vm_to_be_ready(logger, sms, vm_name, state):
    logger.info('vm_name is %s and state is %s', vm_name, state)
    if wait_for_deployment(logger, sms, vm_name, vm_name, state) == False:
        return False;
    else:
        if wait_for_role(logger, sms, vm_name, vm_name, vm_name, 720) == False:
            return False;
    logger.info('VM is ready: %s', vm_name)
    return True


def form_new_vnet_json_with_vnet_name(vnet_name, location, cidr, subnet_arry):
    vnet_name_with_local_ip = get_vnet_name_with_local_ip(vnet_name)
    new_vnet = {}
    new_vnet['@name'] = vnet_name_with_local_ip
    new_vnet['@Location'] = location
    address_space = {}
    address_space['AddressPrefix'] = cidr
    new_vnet['AddressSpace'] = address_space
    subnet = {}
    sns = []
    i = 0
    no_of_subnet = len(subnet_arry)
    while i < no_of_subnet:
        sn = {}
        sn['@name'] = subnet_arry[i]['name']
        sn['AddressPrefix'] = subnet_arry[i]['AddressPrefix']
        sns.append(sn)
        i = i + 1
    subnet['Subnet'] = sns
    new_vnet['Subnets'] = subnet
    return new_vnet


def add_one_vnet_json(vnet_json, new_node):
    try:
        vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite'].append(new_node)
    except:
        vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites'] = {}
        vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite'] = []
        vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite'].append(new_node)
    return vnet_json


def set_vnets_in_azure(logger, subscription_id, cert_path, vnet_json):
    conn = http.client.HTTPSConnection(MS_MANAGEMENT_HOST,
                                       cert_file=cert_path, key_file=cert_path)
    conn.set_debuglevel(1)
    vnet_xml = get_xml_from_json(vnet_json)
    logger.debug(vnet_xml)
    conn.request('PUT', '/%s/services/networking/media' % subscription_id, vnet_xml, headers={'x-ms-version': '2015-04-01', 'Content-Type': 'text/plain'})
    result = conn.getresponse()
    conn.close()
    if result.reason == "Accepted":
        logger.info("set_vnets_in_azure passed")
        return True
    else:
        logger.error("set_vnets_in_azure failed")
        return False


def add_new_vnet_in_azure(logger, subscription_id, cert_path, vnet_name, location, cidr, subnet_arry):
    vnets = get_all_existing_vnets_json_from_azure(logger, subscription_id, cert_path)
    logger.info('add_new_vnet_in_azure get_all_existing_vnets_json_from_azure')
    logger.info(json.dumps(vnets, indent=2))
    if vnet_name_in_azure(subscription_id, cert_path, vnet_name):
        return False
    new_node = form_new_vnet_json_with_vnet_name(vnet_name, location, cidr, subnet_arry)
    new_vnets = add_one_vnet_json(vnets, new_node)
    logger.info('add_new_vnet_in_azure add_one_vnet_json')
    logger.info(json.dumps(new_vnets, indent=2))
    status = set_vnets_in_azure(logger, subscription_id, cert_path, new_vnets)
    if status:
        logger.info("add_new_vnet_in_azure passed.")
        return True
    else:
        logger.error("add_new_vnet_in_azure failed. Abort.")
        return False


def create_vnet_sandbox(logger, vnet_name, vnet_region, vnet_cidr):
    from tests.main import variables as _variables
    if _variables['azure_subscription_id'] == "" or _variables['azure_cert_path'] == "" \
            or _variables['azure_account_name'] == "":
        logger.error("azure account information is incomplete. Abort ...")
        return False

    account_name = _variables['azure_account_name']
    s_id = _variables['azure_subscription_id']
    c_path = _variables['azure_cert_path']

    sms = ServiceManagementService(s_id, c_path)

    logger.info("Connect to Azure %s", vnet_region)

    if not azure_api_works(logger, account_name, s_id, c_path):
        logger.error("Azure API for %s doesn't work. Please check again. Abort.", account_name)
        return False

    # check if the vnet name is unique in Azure
    if vnet_name_in_azure(s_id, c_path, vnet_name):
        reason = 'VNET ' + vnet_name + ' has already been taken,'
        reason += ' please use a different name.'
        logger.error(reason)
        return False

    subnet_array = []

    public_subnet = {}
    public_subnet['name'] = 'public-1'
    public_subnet['AddressPrefix'] = vnet_cidr
    subnet_array.append(public_subnet)
    logger.info('create subnet %s - %s', public_subnet['name'], public_subnet['AddressPrefix'])

    # create a new vnet
    vnet_created = False
    logger.info('calling add_new_vnet_in_azure %s, %s, %s...', vnet_name, vnet_region, vnet_cidr)
    vnet_created = add_new_vnet_in_azure(logger, s_id, c_path, vnet_name, vnet_region, vnet_cidr, subnet_array)
    if not vnet_created:
        reason = 'vnet ' + vnet_name + ' creation failed....'
        logger.error(reason)
        return False

    logger.info('Azure vnet creation succeeded ......')

    logger.info('about to return from create_vnet_sandbox ...')
    return True


def create_user_instance(logger, vnet_name, vnet_id, vnet_region, vnet_size, instance_info):
    from tests.main import variables as _variables
    from random import randint
    rand = randint(0,1000)
    inst_name = vnet_id.replace("CN", "INST") + "-" + str(rand)
    label_name = inst_name
    instance_info.append({"service_name":inst_name})
    az_vnet_name = get_vnet_name_with_local_ip(vnet_name)

    if _variables['azure_subscription_id'] == "" or _variables['azure_cert_path'] == "" \
            or _variables['azure_account_name'] == "":
        logger.error("azure account information is incomplete. Abort ...")
        return False

    account_name = _variables['azure_account_name']
    subscription_id = _variables['azure_subscription_id']
    certification_path = _variables['azure_cert_path']
    location = vnet_region

    sms = ServiceManagementService(subscription_id, certification_path)

    logger.info("Connect to Azure %s", vnet_region)

    if not azure_api_works(logger, account_name, subscription_id, certification_path):
        logger.error("Azure API for %s doesn't work. Please check again. Abort.", account_name)
        return False

    vnet_found = False
    vnets = [vn.name for vn in sms.list_virtual_network_sites()]

    if az_vnet_name in vnets:
        logger.debug("VNet %s does exist", az_vnet_name)
        vnet_found = True

    if vnet_found == False:
        logger.error("VNet %s does not exist. Please check again. Abort", az_vnet_name)
        return False

    # disable_ssh_password_authentication = False
    linux_config = LinuxConfigurationSet('ubuntu', 'ubuntu', 'password1!', False)

    image_name = get_image_name(logger) + '-' + location.replace(' ', '-')

    info = 'Image name ' + image_name
    logger.info(info)

    if image_name == '':
        reason =  'Can not find the cloud gateway image name, exiting...'
        logger.error(reason)
        return False

    try:
        image_prop = sms.get_os_image(image_name)
    except:
        reason = 'Can not load the Azure cloud gateway image ' + image_name
        logger.error(reason)
        return False

    if image_prop.location != vnet_region:
        reason = 'Vnet Region ' + location + ' is different from image location ' + image_prop.location + \
                 '. Please download Cloudn gateway image to the Vnet region storage through CloudN Onboarding. Abort. '
        logger.error(reason)
        return False

    storage_name = image_prop.media_link.split('.')[0].split('//')[1]

    # allocate or define the subnet where cloudx sits on
    subnets = get_vnet_subnets_in_azure(logger, subscription_id, certification_path, az_vnet_name)
    new_subnet_cidr = subnets[len(subnets)-1]['AddressPrefix']
    subnet_name = subnets[len(subnets)-1]['@name']
    info = 'new_subnet_cidr is ' +  new_subnet_cidr
    logger.info(info)

    # reserve vip for cloud service and VM
    logger.info('before create_reserved_ip_address')
    rsv_ip_addr_name = 'ip-' + az_vnet_name
    rsv_ip_addr_result = sms.create_reserved_ip_address(rsv_ip_addr_name, rsv_ip_addr_name, vnet_region)
    # it does not have request_id...self._wait_for_async(sms,result.request_id)
    time.sleep(60)
    logger.info('after create_reserved_ip_address')
    ip_addr_obj = sms.get_reserved_ip_address(rsv_ip_addr_name)
    info =  'rsv_ip_addr is ' + rsv_ip_addr_name + ' ' + ip_addr_obj.address
    logger.info(info)
    instance_info.append({"rsv_ip_addr":ip_addr_obj.address})

    service_name = inst_name
    service_label = inst_name
    description = 'create cloudN VNET from the Windows Azure cloud'

    logger.debug(az_vnet_name + ' ' + service_name + ' ' + service_label + ' ')
    logger.info('before create_hosted_service')
    # Provision hosted service itself if not already existing

    if service_name not in [s.service_name for s in sms.list_hosted_services()]:
        try:
            logger.info("%s does not exist. Create a new one ...", service_name)
            sms.create_hosted_service(service_name, service_label, description, location=location)
        except Exception:
            sms.delete_reserved_ip_address(rsv_ip_addr_name)
            reason = 'the cloud service name ' + service_name + ' already exists. abort'
            logger.error(reason)
            return False

    logger.info('after create_hosted_service')
    logger.info('hosted service  ' + service_name + ' has been created...')

    media_link = 'https://' + storage_name + '.blob.core.windows.net/vhds/' + inst_name + '/' + image_name
    os_hd = OSVirtualHardDisk(image_name, media_link)

    # use the 4th IP address in the subnet
    subnet_ip = new_subnet_cidr.split('/')[0]
    vnet_subnet_ip = int_to_ipstring(ipstring_to_int(subnet_ip) + 4)
    logger.info('vnet_subnet_ip: %s', vnet_subnet_ip)

    role_size = vnet_size

    # Endpoint configuration
    endpoint_config = ConfigurationSet()
    endpoint_config.configuration_set_type = 'NetworkConfiguration'
    endpoint_config.static_private_ip = vnet_subnet_ip
    endpoint1 = ConfigurationSetInputEndpoint(name='SSH', protocol='tcp', port='22', local_port='22', load_balanced_endpoint_set_name=None, enable_direct_server_return=False)
    endpoint_config.input_endpoints.input_endpoints.append(endpoint1)
    endpoint_config.subnet_names.append(subnet_name)

    logger.info('before create_virtual_machine_deployment')
    instance_info.append({"vnet_subnet_ip":vnet_subnet_ip})
    count = 0
    while 1:
        host_number = 4
        count = count + 1
        if count > 255:
            logger.error('Azure timeout create_virtual_machine_deployment')
            return False
    # Launch Virtual Machine
        try:
            result = sms.create_virtual_machine_deployment(
                service_name=inst_name,
                deployment_name=inst_name,
                deployment_slot='production',
                label=label_name,
                role_name=inst_name,
                role_type='PersistentVMRole',
                system_config=linux_config,
                os_virtual_hard_disk=os_hd,
                network_config=endpoint_config,
                virtual_network_name=az_vnet_name,
                reserved_ip_name=rsv_ip_addr_name,
                role_size=role_size
            )
        except Exception as e:
            reason = 'create_virtual_machine_deployment exception. \n' + str(e)
            logger.error(reason)
            logger.error(str(traceback.format_exc()))
            return False

        logger.info('after create_virtual_machine_deployment')
        result_id = result.request_id
        status = sms.get_operation_status(result_id)
        logger.info('Operation status: %s...', status.status)

        ret = wait_for_async(logger, sms, result_id, LONG_COUNTER)
        if ret == 'Networking.DeploymentVNetAddressAllocationFailure':
            logger.info('create_virtual_machine_deployment DeploymentVNetAddressAllocationFailure')
            host_number = host_number + 1
            vnet_subnet_ip = int_to_ipstring(ipstring_to_int(subnet_ip) + host_number)
            instance_info[2] = {"vnet_subnet_ip":vnet_subnet_ip}
            endpoint_config.static_private_ip = vnet_subnet_ip
            logger.info('try new vnet_subnet_ip: ' + vnet_subnet_ip)
            continue
        elif ret == 'Failed':
            reason = 'create_virtual_machine_deployment wait_for_async failed. \n'
            logger.error(reason)
            return False
        else:
            logger.info('create_virtual_machine_deployment succeeded.')
            break

    if wait_for_vm_to_be_ready(logger, sms, inst_name, 'Running') == False:
        reason = 'wait_for_vm_to_be_ready failed.'
        logger.error(reason)
        return False

    instance_info.append({"virtual_network_id":az_vnet_name})

    return True


def cleanup_vnet_resources(logger, vnet_name, vnet_region, instance_info):
    from tests.main import variables as _variables
    logger.info('cleanup_vnet_resources ' + vnet_name)
    cloud_service_name = instance_info[0]["service_name"]
    logger.debug("cloud_service_name is " + cloud_service_name)
    az_vnet_name = get_vnet_name_with_local_ip(vnet_name)
    cloud_service_name = cloud_service_name.strip()

    account_name = _variables['azure_account_name']
    subscription_id = _variables['azure_subscription_id']
    certification_path = _variables['azure_cert_path']

    sms = ServiceManagementService(subscription_id, certification_path)

    logger.info("Connect to Azure %s", vnet_region)

    if not azure_api_works(logger, account_name, subscription_id, certification_path):
        logger.error("Azure API for %s doesn't work. Please check again. Abort", account_name)
        return False

    count = 0
    while 1:
        count = count + 1
        if count > SHORT_COUNTER:
            logger.error('Timeout cleanup_vnet_resources list_hosted_services')
            return False
        try:
            cloud_services = sms.list_hosted_services()
            break
        except Exception as e:
            logger.error(str(e.message))
            time.sleep(5)

    found = False
    for cs in cloud_services:
        if cs.service_name == cloud_service_name:
            found = True
            break
    if found:
        info = 'Cloud Service ' + cloud_service_name
        info += ' is found... Proceed to deletion...'
        logger.info(info)
    else:
        reason = 'the cloud service ' + cloud_service_name
        reason += ' does not exist. abort'
        logger.error(reason)
        return False

    if found:
        count = 0
        while 1:
            count = count + 1
            if count > SHORT_COUNTER:
                logger.error('Timeout cleanup_vnet_resources get_hosted_service_properties')
                return False
            try:
                props = sms.get_hosted_service_properties(cloud_service_name, True)
                break
            except:
                reason = 'the cloud service ' + cloud_service_name
                reason += ' does not exist. abort'
                logger.error(reason)
                time.sleep(5)
    logger.info("cleanup_vnet_resources get_hosted_service_properties done")

    disk_name = cloud_service_name + '-' + cloud_service_name
    disk_names = []
    if found:
        for deployment in props.deployments:
            for role in deployment.role_list:
                role_props = sms.get_role(cloud_service_name, cloud_service_name, cloud_service_name)
                if disk_name in role_props.os_virtual_hard_disk.disk_name:
                    logger.info('found disk ' + role_props.os_virtual_hard_disk.disk_name + '.  Need to delete it....')
                    disk_names.append(role_props.os_virtual_hard_disk.disk_name)

    logger.info('call sms.delete_deployment(%s, %s)...', cloud_service_name, cloud_service_name)
    try:
        result = sms.delete_deployment(cloud_service_name, cloud_service_name)
        wait_for_async(logger, sms, result.request_id, SHORT_COUNTER)
    except Exception as e:
        logger.error('cloud_service_name %s not found with exception %s...', cloud_service_name, str(e))
        return False

    logger.info('call sms.delete_hosted_service(%s)...', cloud_service_name)
    try:
        sms.delete_hosted_service(cloud_service_name)
    except:
        logger.error('cloud_service_name %s not found', cloud_service_name)
        return False

    logger.info('sms.delete_hosted_service(%s) is DONE...', cloud_service_name)

    rsv_ip_addr_name = 'ip-' + az_vnet_name
    logger.info('Delete reserved IP address %s....', rsv_ip_addr_name)
    count = 0
    while 1:
        count = count + 1
        if count > SHORT_COUNTER:
            logger.error('Timeout delete_reserved_ip_address')
            return False
        try:
            result = sms.delete_reserved_ip_address(rsv_ip_addr_name)
            break
        except Exception as e:
            logger.error(str(e.message))
            if 'not exist' in str(e):
                return False
            time.sleep(5)
            return False

    logger.info('Delete reserved IP address %s DONE....', rsv_ip_addr_name)

    return True


# launch CloudN VPN and ping an instance in CloudN VPC
def vpn_ping_user_instance(logger, vnet_name, ssh_ip, ssh_username, ssh_pwd, instance_info):

    from autotest.lib.vpc_utils import launch_ssh_client, ping_aws_user_instance, close_ssh_client

    # find out the user instance's IP address
    instance_ip = instance_info[2]['vnet_subnet_ip']

    if instance_ip:
        # ssh into the instance connected to local CloudN
        ssh = launch_ssh_client(logger, ssh_ip, ssh_username, ssh_pwd)

        # ping AWS user instance
        if ssh:
            ping_result = ping_aws_user_instance(logger, ssh, instance_ip, vnet_name)
            # Shut down SSH client
            close_ssh_client(logger, ssh)
        else:
            logger.error("Failed to ssh into the instance")
            return False
    else:
        logger.error("Can't find a user instance in VNet %s", vnet_name)
        return False

    return ping_result

def ping_between_vm(logger, vnet_name, ssh_ip, ssh_username, ssh_pwd=None, instance_ip=None, retry=10, ssh_key_file=None):

    from autotest.lib.vpc_utils import launch_ssh_client, ping_aws_user_instance, close_ssh_client

    if instance_ip:
        # ssh into the instance connected to local CloudN
        ssh = launch_ssh_client(logger, ssh_ip, ssh_username, ssh_pwd, ssh_key_file)

        # ping AWS user instance
        if ssh:
            ping_result = ping_aws_user_instance(logger, ssh, instance_ip, vnet_name, retry=retry)
            # Shut down SSH client
            close_ssh_client(logger, ssh)
        else:
            logger.error("Failed to ssh into the instance")
            return False
    else:
        logger.error("Can't find a user instance in VNet %s", vnet_name)
        return False

    return ping_result


def remove_one_vnet_from_json(vnet_json, vnet_name):
    for site in vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite']:
        if site['@name'] == vnet_name:
            vnet_json['NetworkConfiguration']['VirtualNetworkConfiguration']['VirtualNetworkSites']['VirtualNetworkSite'].remove(site)
            break
    return vnet_json


def remove_vnet_in_azure(logger, vnet_name):
    from tests.main import variables as _variables
    subscription_id = _variables['azure_subscription_id']
    cert_path = _variables['azure_cert_path']

    vnets = get_all_existing_vnets_json_from_azure(logger, subscription_id, cert_path)
    vnets = remove_one_vnet_from_json(vnets, vnet_name)
    status = set_vnets_in_azure(logger, subscription_id, cert_path, vnets)
    if status:
        logger.info('remove_vnet_in_azure %s passed.....', vnet_name)
    else:
        logger.error('remove_vnet_in_azure %s failed.....', vnet_name)

    return status


def stop_vm(SUBSCRIPTION_ID,GROUP_NAME, VM_NAME, TENANT_ID, CLIENT, KEY):
    credentials = ServicePrincipalCredentials(
        client_id=CLIENT,
        secret=KEY,
        tenant=TENANT_ID
    )
    compute_client = ComputeManagementClient(credentials, SUBSCRIPTION_ID)
    compute_client.virtual_machines.power_off(GROUP_NAME, VM_NAME)


def start_vm(SUBSCRIPTION_ID,GROUP_NAME, VM_NAME, TENANT_ID, CLIENT, KEY):
    credentials = ServicePrincipalCredentials(
        client_id=CLIENT,
        secret=KEY,
        tenant=TENANT_ID
    )
    compute_client = ComputeManagementClient(credentials, SUBSCRIPTION_ID)
    compute_client.virtual_machines.start(GROUP_NAME, VM_NAME)

def del_azure_route_table(LOGGER, SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, ROUTE_TABLE_NAME, ROUTE_NAME, TENANT_ID, CLIENT, KEY):
    credentials = ServicePrincipalCredentials(
        client_id=CLIENT,
        secret=KEY,
        tenant=TENANT_ID
        )
    network_mgmgt_client = NetworkManagementClient(credentials, SUBSCRIPTION_ID)
    response = network_mgmgt_client.routes.delete(RESOURCE_GROUP_NAME, ROUTE_TABLE_NAME, ROUTE_NAME)
    LOGGER.info('response{}'.format(response))