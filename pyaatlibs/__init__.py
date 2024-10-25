import os
import platform

__version__ = "1.5.7"
__author__ = "Hao-Wei Lee"
if platform.system() == "Windows":
    SEP = "\\"
    STDNUL = "NUL"
else:
    SEP = "/"
    STDNUL = "/dev/null"

ROOT_DIR = SEP.join(os.path.dirname(os.path.realpath(__file__)).split(SEP)[:-1])

def get_path(*names):
	return "{}{}{}".format(ROOT_DIR, SEP, SEP.join(names))
