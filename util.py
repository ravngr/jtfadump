import math
import random
import re
import string
from subprocess import Popen, PIPE
import threading
import sys


# From http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)


# From http://stackoverflow.com/questions/12826723/possible-to-extract-the-git-repo-revision-hash-via-python-code
def get_git_hash():
    proc = Popen(['git', 'rev-parse','HEAD'], stdout=PIPE)
    (proc_out, _) = proc.communicate()
    return proc_out.strip()


# From http://stackoverflow.com/questions/1176136/convert-string-to-python-class-object
def class_from_str(class_name, parent):
    return reduce(getattr, class_name.split('.'), sys.modules[parent])


# From http://stackoverflow.com/questions/2400504/easiest-way-to-replace-a-string-using-a-dictionary-of-replacements
def replace_dict(substite_dict, data):
    pattern = re.compile(r'\b(' + '|'.join(re.escape(key) for key in substite_dict.keys()) + r')\b')

    if type(data) is list:
        return [pattern.sub(lambda x: substite_dict[x.group()], d) for d in data]
    else:
        return pattern.sub(lambda x: substite_dict[x.group()], data)


def rand_hex_str(length=8):
    return ''.join(random.choice(string.hexdigits[:16]) for x in range(length))


def str2bool(s):
    return True if s.lower() in ['true', '1', 'yes', 'y'] else False


# SNP file reading
class SNPFormatException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


_SNP_PARAMETER_TYPE = enum(S='S', Y='Y', Z='Z', G='G', H='H')


def read_snp(snp_path):
    with open(snp_path, 'r') as f:
        snp_text = f.readlines();

    # Replace punctuation
    snp_text[:] = [re.sub('[\t,]', ' ', line.upper().strip()) for line in snp_text]

    # Extract the option line
    option_line = [line for line in snp_text if re.match('^#.*', line)]

    if len(option_line) != 1:
        raise SNPFormatException("SNP format requires one option line ({} found)".format(len(option_line)))

    option_line = option_line[0]

    # Strip comments and option lines
    snp_text = [line for line in snp_text if not re.match('^[#!].*', line)]

    # Remove any invalid characters
    snp_text[:] = [re.sub('[^A-Z0-9.+\- ]+', '', line) for line in snp_text]

    # Strip empty lines
    snp_text = filter(None, snp_text)

    # Format
    unit_multiplier = 1e9
    parameter_type = _SNP_PARAMETER_TYPE.S
    unit_db = False
    unit_angle = True
    unit_r = 50

    options = filter(None, option_line.split(' '))
    skip = False

    for n in range(1, len(options)):
        if skip:
            skip = False
            continue

        if re.match('^[KMG]?HZ$', options[n]):
            if options[n][0] == 'H':
                unit_multiplier = 1
            elif options[n][0] == 'K':
                unit_multiplier = 1e3
            elif options[n][0] == 'M':
                unit_multiplier = 1e6
        elif re.match('^[SYZGH]$', options[n]):
            if options[n][0] == 'H':
                parameter_type = _SNP_PARAMETER_TYPE.H
            elif options[n][0] == 'G':
                parameter_type = _SNP_PARAMETER_TYPE.G
            elif options[n][0] == 'Z':
                parameter_type = _SNP_PARAMETER_TYPE.Z
            elif options[n][0] == 'Y':
                parameter_type = _SNP_PARAMETER_TYPE.Y
        elif re.match('^(MA|DB|RI)$', options[n]):
            if options[n][0] == 'D':
                unit_db = True
            elif options[n][0] == 'R':
                unit_angle = False
        elif options[n][0] == 'R':
            if (n + 1) >= len(options):
                raise SNPFormatException('Missing parameter for \'R\' field in option line')

            unit_r = int(options[n + 1])
            skip = True
        else:
            raise SNPFormatException("Invalid option line format (option: {})".format(options[n]))

    # Analyse the number of ports in the data
    data_length = len(snp_text)

    if data_length == 1:
        ports = 1
    else:
        field_count = [len(line.split(' ')) for line in snp_text]

        if field_count[0] == field_count[1]:
            ports = math.sqrt((field_count[0] - 1) / 2)
        else:
            ports = (field_count[0] - 1) / 2

    if ports != int(ports):
        raise SNPFormatException('Invalid data format')

    if ports > 4:
        raise SNPFormatException('SNP files with more than 4 ports are not supported')

    ports = int(ports)

    # Read data
    f = []
    data = []

    if ports > 2:
        step = ports
    else:
        step = 1

    for n in range(0, len(snp_text), step):
        # Concaternate multiple lines if necessary
        if ports > 2:
            data_line = ' '.join(snp_text[n:n + step])
        else:
            data_line = snp_text[n]

        data_fields = [float(d) for d in data_line.split(' ')]

        # 2 port data must be rearranged
        if ports == 2:
            data_fields = [data_fields[0], data_fields[1], data_fields[2], data_fields[5], data_fields[6], data_fields[3], data_fields[4], data_fields[7], data_fields[8]];

        net_data = [[]]
        
        for m in range(1, len(data_fields), 2):
            a = data_fields[m]
            b = data_fields[m + 1]
            
            if unit_db:
                a = math.pow(10, (a / 20))
            
            if unit_angle:
                mag = a
                ang = math.radians(b)
                
                a = mag * math.cos(ang)
                b = mag * math.sin(ang)
                
            if len(net_data[-1]) == ports:
                net_data.append([])
            
            net_data[-1].append(complex(a, b))

        data.append(((float(data_fields[0]) * unit_multiplier), net_data))

    return (parameter_type, unit_r, data)
