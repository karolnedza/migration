import logging
import logging.config
import sys
import os
import json
import yaml
import argparse
import boto3
import ipaddress
import getpass
import requests
import time
from retry import retry
import botocore
from dm.exceptions import AviatrixException
import traceback
requests.packages.urllib3.disable_warnings()

class Aviatrix:

    @classmethod
    def _send_aviatrix_api(cls,
            api_endpoint_url="https://123.123.123.123/v1/api",
            request_method="POST",
            payload=dict(),
            retry_count=5,
            keyword_for_log="avx-migration-function---",
            indent=""):

        logger = logging.getLogger(__name__)
        response = None
        responses = list()
        request_type = request_method.upper()
        response_status_code = -1

        for i in range(retry_count):
            try:
                if request_type == "GET":
                    response = requests.get(
                        url=api_endpoint_url, params=payload, verify=False)
                    response_status_code = response.status_code
                elif request_type == "POST":
                    response = requests.post(
                        url=api_endpoint_url, data=payload, verify=False)
                    response_status_code = response.status_code
                else:
                    lambda_failure_reason = "ERROR: Bad HTTPS request type: " + request_method
                    logger.error(keyword_for_log + lambda_failure_reason)
                    return lambda_failure_reason
                responses.append(response)  # For error message/debugging purposes
            except requests.exceptions.ConnectionError as e:
                logger.error(indent + keyword_for_log +
                    "WARNING: Oops, it looks like the server is not responding...")
                responses.append(str(e))
            except Exception as e:
                traceback_msg = traceback.format_exc()
                logger.error(indent + keyword_for_log +
                    "Oops! Aviatrix Migration Function caught an exception! The traceback message is: ")
                logger.error(traceback_msg)
                lambda_failure_reason = "Oops! Aviatrix Mogration Function caught an exception! The traceback message is: \n" + \
                    str(traceback_msg)
                logger.error(keyword_for_log + lambda_failure_reason)
                # For error message/debugging purposes
                responses.append(str(traceback_msg))
            finally:
                if 200 == response_status_code:  # Successfully send HTTP request to controller Apache2 server
                    return response
                elif 404 == response_status_code:
                    lambda_failure_reason = "ERROR: Oops, 404 Not Found. Please check your URL or route path..."
                    logger.error(indent + keyword_for_log + lambda_failure_reason)

                if i+1 < retry_count:
                    logger.info(indent + keyword_for_log + "START: Wait until retry")
                    logger.info(indent + keyword_for_log + "    i == " + str(i))
                    wait_time_before_retry = pow(2, i)
                    logger.info(indent + keyword_for_log + "    Wait for: " + str(wait_time_before_retry) +
                        " second(s) until next retry")
                    time.sleep(wait_time_before_retry)
                    logger.info(indent + keyword_for_log +
                        "ENDED: Wait until retry  \n\n")
                else:
                    lambda_failure_reason = 'ERROR: Failed to invoke Aviatrix API. Max retry exceeded. ' + \
                                            'The following includes all retry responses: ' + \
                                            str(responses)
                    raise AviatrixException(message=lambda_failure_reason,)

        return response  # IF the code flow ends up here, the response might have some issues

    @classmethod
    def attach_vpc_to_aws_tgw(
            cls,
            api_endpoint_url="",
            CID="",
            vpc_access_account_name="",
            vpc_region_name="",
            vpc_id="",
            aws_tgw_name="",
            route_domain_name="Default_Domain",
            route_table_list="",
            customized_routes="",
            customized_route_advertisement="",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        request_method = "POST"
        payload = {
            "action": "attach_vpc_to_tgw",
            "CID": CID,
            "region": vpc_region_name,
            "vpc_account_name": vpc_access_account_name,
            "vpc_name": vpc_id,
            "tgw_name": aws_tgw_name,
            "route_domain_name": route_domain_name,
            "route_table_list": route_table_list,
            "customized_routes": customized_routes,
            "customized_route_advertisement": customized_route_advertisement
        }

        print(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        print(response.json())

        return response


    @classmethod    
    def detach_vpc_to_aws_tgw(
            cls,
            api_endpoint_url="",
            CID="",
            vpc_id="",
            aws_tgw_name="",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        request_method = "POST"
        payload = {
            "action": "detach_vpc_from_tgw",
            "CID": CID,
            "vpc_name": vpc_id,
            "tgw_name": aws_tgw_name
        }

        print(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        print(response.json())

        return response
    # Create spoke GWs

    @classmethod    
    def detach_spoke_from_transit_gw(
            cls,
            api_endpoint_url="",
            CID="",
            spoke_gw="",
            transit_gw="",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        logger = logging.getLogger(__name__)
        request_method = "POST"
        payload = {
            "action": "detach_spoke_from_transit_gw",
            "CID": CID,
            "spoke_gw": spoke_gw,
            "transit_gw": transit_gw
        }

        # logger.debug(indent + keyword_for_log + "Request payload     : \n" +
        #     str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        res = response.json()
        if res['return'] == False:
            logger.warning(f'  **Alert** {res["reason"]}')
        else:
            logger.info(f'  Done')            
        return response
    # Detach spoke from transit

    @classmethod    
    def attach_spoke_to_transit_gw(
            cls,
            api_endpoint_url="",
            CID="",
            spoke_gw="",
            transit_gw="",
            route_table_list="",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        logger = logging.getLogger(__name__)
        request_method = "POST"
        payload = {
            "action": "attach_spoke_to_transit_gw",
            "CID": CID,
            "spoke_gw": spoke_gw,
            "transit_gw": transit_gw,
            "route_table_list": route_table_list
        }

        logger.debug(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        res = response.json()
        if res['return'] == False:
            logger.warning(f'  **Alert** {res["reason"]}')
        else:
            logger.info(f'  Done')            
        return response
    # Detach spoke from transit

    @classmethod
    def create_spoke_gw(
            cls,
            api_endpoint_url="",
            CID="",
            vpc_access_account_name="",
            vpc_region_name="",
            vpc_id="",
            avx_tgw_name="",
            gw_name="",
            gw_size="",
            insane_subnet_1="",
            insane_subnet_2="",
            spoke_routes="",
            insane_mode="",
            route_table_list="",
            keyword_for_log="avx-migration-function---",
            indent="    ",
            ec2_resource=""):

        if insane_mode:
            insane_mode = "on"
            gw_subnet = insane_subnet_1[0]+"~~"+vpc_region_name+insane_subnet_1[1]
            hagw_subnet = insane_subnet_2[0]+"~~" + \
                vpc_region_name+insane_subnet_2[1]

        else:
            insane_mode = "off"
            public_subnets = cls.get_public_spoke_gw_cidr(vpc_id, ec2_resource)
            if len(public_subnets) == 2:
                gw_subnet = public_subnets[0].cidr_block
                hagw_subnet = public_subnets[1].cidr_block
            else:
                print("avx_spoke:true Tag is required on exactly two subnets")
                sys.exit()

        request_method = "POST"

        payload = {
            "action": "create_spoke_gw",
            "CID": CID,
            "account_name": vpc_access_account_name,
            "cloud_type": "1",
            "region": vpc_region_name,
            "vpc_id": vpc_id,
            "public_subnet": gw_subnet,
            "gw_name": gw_name,
            "gw_size": gw_size,
            "insane_mode": insane_mode
        }

        print(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        print(response.json())

        payload = {
            "action": "enable_spoke_ha",
            "CID": CID,
            "gw_name": gw_name,
            "public_subnet": hagw_subnet,
        }

        print(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        print(response.json())

        # Add custom VPC routes
        if spoke_routes:
            payload = {
                "action": "edit_gateway_custom_routes",
                "CID": CID,
                "gateway_name": gw_name,
                "cidr": spoke_routes
            }

            print(indent + keyword_for_log + "Request payload     : \n" +
                str(json.dumps(obj=payload, indent=4)))

            response = cls._send_aviatrix_api(
                api_endpoint_url=api_endpoint_url,
                request_method=request_method,
                payload=payload,
                keyword_for_log=keyword_for_log,
                indent=indent + "    ")

            print(response.json())

        return response
    # END def create_spoke_gw()

    @classmethod
    def attach_vpc_to_avx_tgw(
            cls,
            api_endpoint_url="",
            CID="",
            avx_tgw_name="",
            gw_name="",
            route_table_list="",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        request_method = "POST"

        payload = {
            "action": "attach_spoke_to_transit_gw",
            "CID": CID,
            "spoke_gw": gw_name,
            "transit_gw": avx_tgw_name,
            "route_table_list": route_table_list
        }
        print(indent + keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        print(response.json())

        # TODO: Add support for attaching to MCNS
        # First get attachment name
        # action=list_multi_cloud_security_domains_attachment_names&CID={{CID}}&transit_gateway_name=my-gateway009'

        # Then switch attachment to security domain.
        # Before this step, we should check if segmentation is enabled
        # but don't see API for that
        # --form 'action=associate_attachment_to_multi_cloud_security_domain'
        # --form 'CID={{CID}}'
        # --form 'domain_name=security-domain'
        # --form 'attachment_name=conn-1'

        return response


    @classmethod
    def create_tgw_security_domain(cls,api_endpoint_url="", CID="", tgw_name="", keyword_for_log="avx-migration-function---"):
        request_method = "POST"
        payload = {
            "action": "add_route_domain",
            "CID": CID,
            "tgw_name": tgw_name,
            "route_domain_name": "temp123"
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")

        print(response.json())
        return response

    @classmethod
    def delete_tgw_security_domain(cls,api_endpoint_url="", CID="", tgw_name="", keyword_for_log="avx-migration-function---"):
        request_method = "POST"
        payload = {
            "action": "delete_route_domain",
            "CID": CID,
            "tgw_name": tgw_name,
            "route_domain_name": "temp123"
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")

        print(response.json())
        return response

    @classmethod
    def list_tgw_security_domain(cls,api_endpoint_url="", CID="", tgw_name="", domain="", keyword_for_log="avx-migration-function---"):
        request_method = "GET"
        payload = {
            "action": "list_tgw_security_domain_details",
            "CID": CID,
            "tgw_name": tgw_name,
            "route_domain_name": domain
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        return response

    @classmethod
    def list_gateway_info(cls, api_endpoint_url="", CID="", vpc_access_account_name="", acx_gw_only="no", gw_name=None, keyword_for_log="avx-migration-function---"):
        """
        invoking from switch_traffic.py, e.g.:
          res = av.list_gateway_info(api_endpoint_url=api_ep_url+"api", CID=CID, vpc_access_account_name="AwsDev")
          print(res.json())
        """
        request_method = "GET"
        payload = {
            "action": "list_vpcs_summary",
            "CID": CID,
            "account_name": vpc_access_account_name,
            "acx_gw_only": acx_gw_only,
            "gateway_name": gw_name
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        
        return response

    @classmethod
    def list_accounts(cls, api_endpoint_url="", CID="", iam_based="", keyword_for_log="avx-migration-function---"):
        """
        invoking from discovery.py, e.g.:
          res = av.list_accounts(api_endpoint_url=api_ep_url+"api", CID=CID, iam_based="true")
          print(res.json())
        """
        logger = logging.getLogger(__name__)

        request_method = "GET"
        payload = {
            "action": "list_accounts",
            "CID": CID,
            "aws_iam_role_based": iam_based
        }

        logger.debug(f'  {keyword_for_log}' + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        
        return response

    @classmethod
    @retry(Exception, tries=15, delay=6)
    def switch_tgw_security_domain(cls,api_endpoint_url="", CID="", tgw_name="", domain="", gw_name="", vpc_name="", vpc_cidr="", keyword_for_log="avx-migration-function---"):
        request_method = "POST"

        payload = {
            "action": "switch_tgw_attachment_security_domain",
            "CID": CID,
            "tgw_name": tgw_name,
            "attachment_name": vpc_name,
            "route_domain_name": domain
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        if response.json()['return'] == False:
            raise Exception
        print(response.json())

        return response

    @classmethod
    def login(cls,
            api_endpoint_url="https://x.x.x.x/v1/api",
            username="admin",
            password="**********",
            keyword_for_log="avx-migration-function---",
            indent="    "):

        request_method = "POST"
        data = {
            "action": "login",
            "username": username,
            "password": password
        }

        payload_with_hidden_password = dict(data)
        payload_with_hidden_password["password"] = "************"

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=data,
            keyword_for_log=keyword_for_log,
            indent=indent + "    ")

        return response

    @classmethod
    def get_public_spoke_gw_cidr(cls,vpcid, ec2):
        filters = [{'Name': 'tag:avx_spoke', 'Values': ['true']},
                {'Name': 'vpc-id', 'Values': [vpcid]}]
        return list(ec2.subnets.filter(Filters=filters))
        
    @classmethod
    def list_tgw_name(cls, api_endpoint_url="", CID="", vpc_id="", keyword_for_log="avx-migration-function---"):
        request_method = "GET"
        payload = {
            "action": "list_all_tgw_attachments",
            "CID": CID,
        }

        print(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        for result in response.json()['results']:
            if result['name'] == vpc_id:
                tgw_name = result['tgw_name']
        return tgw_name


    @classmethod
    def list_spoke_gateways(cls, api_endpoint_url="", CID="", keyword_for_log="avx-migration-function---"):
        logger = logging.getLogger(__name__)
        request_method = "GET"
        payload = {
            "action": "list_primary_and_ha_spoke_gateways",
            "CID": CID,
        }

        logger.debug(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")
        responseJson = response.json()
        if responseJson['return'] == True:
            return response.json()
        else:
            return None

    @classmethod
    def get_spoke_gw_adv_cidr(cls, api_endpoint_url="", CID="", keyword_for_log="avx-migration-function---"):
        response = cls.list_spoke_gateways(api_endpoint_url, CID, keyword_for_log)
        if response == None:
            return []
        gwCidrList = {}
        for x in response['results']:
            gw_name = x['name']
            gwCidrList[gw_name] = x['include_cidr_list']
        return gwCidrList

    @classmethod
    @retry(logger=logging.getLogger(__name__),tries=10, delay=30)
    def edit_gw_adv_cidr(cls, api_endpoint_url="", CID="", gw_name="", cidrs="", keyword_for_log="avx-migration-function---"):
        logger = logging.getLogger(__name__)
        request_method = "POST"
        payload = {
            "action": "edit_gateway_advertised_cidr",
            "CID": CID,
            "gateway_name": gw_name,
            "cidr": cidrs
        }

        logger.debug(keyword_for_log + "Request payload     : \n" +
            str(json.dumps(obj=payload, indent=4)))

        response = cls._send_aviatrix_api(
            api_endpoint_url=api_endpoint_url,
            request_method=request_method,
            payload=payload,
            keyword_for_log=keyword_for_log,
            indent="    ")

        res = response.json()
        if 'return' in res and res['return'] == False:
            raise Exception(f'  {gw_name} connection to transit is not ready')
            # logger.error(f"  **Alert** {res['reason']}")
        else:
            logger.error(f'  Done')


    @classmethod
    def getCid(cls,api_ep_url,ctrl_user,ctrl_pwd):
        logger = logging.getLogger(__name__)        
        CID = ""

        # Login to Controller and save CID
        try:
            response = cls.login(api_endpoint_url=api_ep_url+"api",
                        username=ctrl_user,
                        password=ctrl_pwd)
            CID = response.json()["CID"]
        except KeyError:
            logger.error("Check your password")
            sys.exit()
        except Exception as e:
            logger.error(e)
            sys.exit()

        return CID
