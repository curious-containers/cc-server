import os
from pymongo import MongoClient

from cc_server.configuration import Config
from cc_server.authorization import Authorize
from cc_server.__main__ import main

CONFIG = '/root/.config/curious-containers/config.toml'

username = os.environ['USERNAME']
password = os.environ['PASSWORD']

config = Config(None)

mongo = MongoClient('mongodb://%s:%s@%s/%s' % (
    config.mongo['username'],
    config.mongo['password'],
    config.mongo['host'],
    config.mongo['dbname']
))

authorize = Authorize(
    mongo=mongo,
    config=config
)

authorize.create_user(username, password, True)

main()
