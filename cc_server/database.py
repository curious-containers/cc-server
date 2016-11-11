import pymongo


class Mongo:
    def __init__(self, config):
        self.db = pymongo.MongoClient('mongodb://%s:%s@%s/%s' % (
            config.mongo['username'],
            config.mongo['password'],
            config.mongo['host'],
            config.mongo['dbname']
        ))[config.mongo['dbname']]

    def drop_db_collections(self, collections):
        for c in collections:
            self.db[c].drop()
