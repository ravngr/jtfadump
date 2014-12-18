import random
import string
from subprocess import Popen, PIPE
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

def rand_hex_str():
    return ''.join(random.choice(string.hexdigits[:16]) for x in range(8))
