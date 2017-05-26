import os
import sys

sys.path.insert(0, os.path.split(os.path.abspath(__file__))[0])

from cc_server_web.__main__ import prepare
prepare()

from cc_server_web.__main__ import app as application
