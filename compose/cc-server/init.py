import os
import toml

from cc_server.configuration import Config
from cc_server.tee import construct_function
from cc_server.database import Mongo
from cc_server.authorization import Authorize
from cc_server.__main__ import main

with open(os.path.expanduser('~/.config/curious-containers/credentials.toml')) as f:
    credentials = toml.load(f)

username = credentials['credentials']['username']
password = credentials['credentials']['password']

config = Config(None)

tee = construct_function(config)

mongo = Mongo(
    config=config
)
authorize = Authorize(
    tee=tee,
    mongo=mongo,
    config=config
)

authorize.create_user(username, password, True)

main()
