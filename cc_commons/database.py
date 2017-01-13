import pymongo


class Mongo:
    def __init__(self, config):
        self._config = config
        self.client = pymongo.MongoClient('mongodb://{}:{}@{}:{}/{}'.format(
            self._config.mongo['username'],
            self._config.mongo['password'],
            self._config.mongo['host'],
            self._config.mongo['port'],
            self._config.mongo['db']
        ))
        self.db = self.client[self._config.mongo['db']]

    def drop_db_collections(self, collections):
        for c in collections:
            self.db[c].drop()
