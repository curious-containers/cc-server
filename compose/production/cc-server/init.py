import os
import toml
from time import sleep

from cc_commons.authorization import Authorize
from cc_commons.database import Mongo

from cc_server.configuration import Config

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
    except:
        sleep(1)
