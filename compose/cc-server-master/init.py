import os
import toml
from time import sleep
from pymongo.errors import OperationFailure

from cc_commons.authorization import Authorize
from cc_commons.configuration import Config
from cc_commons.database import Mongo

from cc_server_master.__main__ import main

with open(os.path.expanduser('~/.config/curious-containers/credentials.toml')) as f:
    credentials = toml.load(f)

username = credentials['credentials']['username']
password = credentials['credentials']['password']

config = Config()

mongo = Mongo(
    config=config
)
authorize = Authorize(
    config=config,
    tee=print,
    mongo=mongo
)

for _ in range(10):
    try:
        authorize.create_user(username, password, True)
        break
    except OperationFailure:
        sleep(1)

main()
