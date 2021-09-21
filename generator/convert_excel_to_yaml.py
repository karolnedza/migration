import argparse
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
