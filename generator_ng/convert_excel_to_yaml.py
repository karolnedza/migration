import argparse
import os
import pandas as pd
import sys
import yaml

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Excel to YAML for Discovery Migration"
    )
    parser.add_argument("-e", "--excel", help="Excel file to convert from")
    parser.add_argument("-y", "--yaml", help="YAML file to convert to")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        print(
            "Specify an Excel file for input and a YAML file for output.\n\n\tpython3 convert_excel_to_yaml.py --excel <EXCEL_INPUT_FILE> --yaml <YAML_OUTPUT_FILE>\n"
        )
        parser.print_help()
        sys.exit()
    if args.excel == None or args.yaml == None:
        print(
            "Specify an Excel file for input and a YAML file for output.\n\n\tpython3 convert_excel_to_yaml.py --excel <EXCEL_INPUT_FILE> --yaml <YAML_OUTPUT_FILE>\n"
        )
        parser.print_help()
        sys.exit()
    excel_file = args.excel
    yaml_file = args.yaml
    try:
        df = pd.read_excel(excel_file)
    except FileNotFoundError:
        print("File not found", excel_file)
        sys.exit()
    with open(yaml_file, "w") as outfile:
        yaml.dump(
            df.reset_index(drop=True).to_dict(orient="records"),
            outfile,
            sort_keys=False,
            width=72,
            indent=2,
            default_flow_style=False,
        )
    with open(yaml_file, "r+") as infile:
        data = infile.read()
        data = data.replace("true", "True")
        data = data.replace("false", "False")
        data = data.replace("'", "")
        data = data.replace(".nan", "")
        infile.truncate(0)
        infile.seek(0)
        infile.write("account_info:\n")
        infile.write(data)

    # Convert legacy YAML format to nextgen format
    # i is the index for input
    # j is the index for output
    # k is the index for regions

    with open(yaml_file) as f:
        input = yaml.safe_load(f)

    output = {"account_info": []}

    i = 0
    while i < len(input["account_info"]):
        j = 0
        not_added = True
        while j < len(output["account_info"]):
            # account_id, role_name, spoke_gw_size, filter_cidrs, hpe can be combined
            combinable_object = {
                "account_id": '"{}"'.format(input["account_info"][i]["account_id"]),
                "role_name": input["account_info"][i]["role_name"],
                "spoke_gw_size": input["account_info"][i]["spoke_gw_size"],
                "filter_cidrs": input["account_info"][i]["filter_cidrs"],
                "hpe": input["account_info"][i]["hpe"],
            }
            # Check if the current entry has the exact same combinable values as a previously added account
            if combinable_object.items() <= output["account_info"][j].items():
                # If the region exists, add the vpc_object
                k = 0
                while k < len(output["account_info"][j]["regions"]):
                    if (
                        input["account_info"][i]["region"]
                        == output["account_info"][j]["regions"][k]["region"]
                    ):
                        vpc_object = {
                            "vpc_id": input["account_info"][i]["vpc_id"],
                            "gw_zones": input["account_info"][i]["gw_zones"],
                            "avtx_cidr": '"{}"'.format(input["account_info"][i]["avtx_cidr"]),
                        }
                        output["account_info"][j]["regions"][k]["vpcs"].append(
                            vpc_object
                        )
                        not_added = False
                        break
                    k += 1
                # Didn't find the current region so adding the region_object (which includes the vpc)
                if k == len(output["account_info"][j]["regions"]):
                    region_object = {
                        "region": input["account_info"][i]["region"],
                        "vpcs": [
                            {
                                "vpc_id": input["account_info"][i]["vpc_id"],
                                "gw_zones": input["account_info"][i]["gw_zones"],
                                "avtx_cidr": '"{}"'.format(input["account_info"][i]["avtx_cidr"]),
                            }
                        ],
                    }
                    output["account_info"][j]["regions"].append(region_object)
                    not_added = False
                    break
            j += 1
        # This entry couldn't be combined into a previously added account so add the full account_info_object
        if j == len(output["account_info"]) and not_added:
            account_info_object = {
                "account_id": '"{}"'.format(input["account_info"][i]["account_id"]),
                "role_name": input["account_info"][i]["role_name"],
                "spoke_gw_size": input["account_info"][i]["spoke_gw_size"],
                "filter_cidrs": input["account_info"][i]["filter_cidrs"],
                "hpe": input["account_info"][i]["hpe"],
                "regions": [
                    {
                        "region": input["account_info"][i]["region"],
                        "vpcs": [
                            {
                                "vpc_id": input["account_info"][i]["vpc_id"],
                                "gw_zones": input["account_info"][i]["gw_zones"],
                                "avtx_cidr": '"{}"'.format(input["account_info"][i]["avtx_cidr"]),
                            }
                        ],
                    }
                ],
            }
            output["account_info"].append(account_info_object)
        i += 1

    temp_filename = "convert-temp.yml"
    temp_file = open(temp_filename, "w")
    yaml.dump(output, temp_file, sort_keys=False, default_flow_style=None)

    template_file = "template.yaml"
    filenames = [template_file, temp_filename]      
    with open(yaml_file, "w") as outfile:
        for fname in filenames:
            with open(fname) as infile:
                outfile.write(infile.read())

    with open(yaml_file, "r+") as infile:
        data = infile.read()
        data = data.replace("true", "True")
        data = data.replace("false", "False")
        data = data.replace("'", "")
        data = data.replace(".nan", "")
        infile.truncate(0)
        infile.seek(0)
        infile.write(data)

    os.remove(temp_filename)
