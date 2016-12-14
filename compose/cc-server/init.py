import os
import toml

from cc_server.configuration import Config
from cc_server.database import Mongo
from cc_server.authorization import Authorize
from cc_server.__main__ import main

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

authorize.create_user(username, password, True)

main()
