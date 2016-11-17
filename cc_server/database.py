import pymongo


class Mongo:
    def __init__(self, config):
        self.client = pymongo.MongoClient('mongodb://{}:{}@{}:{}/{}'.format(
            config.mongo['username'],
            config.mongo['password'],
            config.mongo['host'],
            config.mongo['port'],
            config.mongo['db']
        ))
        self.db = self.client[config.mongo['db']]

    def drop_db_collections(self, collections):
        for c in collections:
            self.db[c].drop()
