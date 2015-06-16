import argparse
import ConfigParser
import os

import data_capture
import equipment

def main():
    # Parse command line arguments
    parse = argparse.ArgumentParser(description='VNA file transfer')

    parse.add_argument('config', help='Configuration file')
    parse.add_argument('dir', choices=['push', 'pull'], help='Transfer direction')
    parse.add_argument('files', help='Filename(s) to transfer', nargs='+')

    parse.add_argument('--remote-path', dest='remote_path', help='Target VNA directory')

    args = parse.parse_args()

    # Read configuration file(s)
    cfg = ConfigParser.RawConfigParser()
    cfg.read(args.config)

    vna_address = cfg.get(data_capture.VNAData._CFG_SECTION, 'vna_address')
    print("Connect to ".format(vna_address))

    vna_connector = equipment.VISAConnector(vna_address)

    vna = equipment.NetworkAnalyzer(vna_connector)

    to_vna = args.dir == 'push'

    for file in args.files:
        vna.file_transfer(file, os.path.basename(file), to_vna)


if __name__ == "__main__":
    main()