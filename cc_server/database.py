import pymongo

class Mongo:
    def __init__(self, config):
        self.config = config
        self.client = pymongo.MongoClient('mongodb://{}:{}@{}:{}/{}'.format(
            self.config.mongo['username'],
            self.config.mongo['password'],
            self.config.mongo['host'],
            self.config.mongo['port'],
            self.config.mongo['db']
        ))
        self.db = self.client[self.config.mongo['db']]

    def drop_db_collections(self, collections):
        for c in collections:
            self.db[c].drop()
