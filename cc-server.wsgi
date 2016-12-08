import os
import sys

# Specify path to cc-server here, if not already in PYTHONPATH
# sys.path.insert(0, '/path/to/cc-server')

from cc_server.__main__ import app as application
from cc_server.__main__ import prepare

prepare()
