import argparse
import os
import re

import scipy.io as sio

def main():
    parse = argparse.ArgumentParser(description='Experiment System')
    parse.add_argument('-s', help='MAT file field to fill', dest='set', action='append')
    parse.add_argument('-r', help='MAT file field to rename', dest='replace', action='append')
    parse.add_argument('directory', help='Directories to search for mat files', nargs='+')

    args = parse.parse_args()

    # Build replacement dictionary
    field_set = {}
    field_replace = {}

    if args.set is not None:
        for field in args.set:
            field_part = field.split('=')
            field_set[field_part[0]] = field_part[1]

    if args.replace is not None:
        for field in args.replace:
            field_part = field.split('=')
            field_replace[field_part[0]] = field_part[1]

    # Import data from mat file
    files = []

    for dir in args.directory:
        files.extend([os.path.join(dir, file) for file in os.listdir(dir)])

    mat_pattern = re.compile('.*\.mat$')
    mat_files = filter(mat_pattern.match, files)

    for mat_file in mat_files:
        print("Fixing {}".format(mat_file))

        mat_data = sio.loadmat(mat_file)

        # Set field values
        for field, value in field_set.iteritems():
            mat_data[field] = value

        # Replace field names
        for field, replacement in field_replace.iteritems():
            if field in mat_data.keys():
                mat_data[replacement] = mat_data.pop(field)
            else:
                print "\tField skipped: {}".format(field)

        sio.savemat(mat_file, mat_data, do_compression=True)


if __name__ == "__main__":
    main()
