from cc_server.states import state_to_index


class FIFO:
    def __init__(self, mongo):
        self.mongo = mongo

    def __iter__(self):
        cursor = self.mongo.db['tasks'].aggregate([
            {'$match': {'state': state_to_index('waiting')}},
            {'$sort': {'transitions.0.timestamp': 1}}
        ])
        for task in cursor:
            yield task
