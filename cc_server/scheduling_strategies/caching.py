from cc_server.states import state_to_index
from cc_server.helper import key_generator


def data_container_prototype():
    return {
        'state': 0,
        'transitions': [],
        'username': None,
        'task_id': None,
        'input_files': [],
        'input_file_keys': [],
        'callbacks': [],
        'callback_key': key_generator(),
        'cluster_node': None
    }


class OneCachePerTaskNoDuplicates:
    def __init__(self, mongo, cluster):
        self.mongo = mongo
        self.cluster = cluster

    def apply(self, application_container_id):
        self.cluster.assign_existing_data_containers(application_container_id)

        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id},
            {'task_id': 1, 'data_container_ids': 1}
        )
        task = self.mongo.db['tasks'].find_one(
            {'_id': application_container['task_id']},
            {'input_files': 1, 'username': 1}
        )

        data_container_ids = application_container['data_container_ids']
        input_files = task['input_files']

        unassigned_input_files = []

        for i, (f, dc_id) in enumerate(zip(input_files, data_container_ids)):
            if dc_id:
                continue
            data_container = self.mongo.db['data_containers'].find_one(
                {'state': state_to_index('created'), 'input_files': f},
                {'_id': 1}
            )
            if data_container:
                data_container_ids[i] = data_container['_id']
                continue
            unassigned_input_files.append(f)

        if unassigned_input_files:
            data_container = data_container_prototype()
            data_container['username'] = task['username']
            data_container['input_files'] = unassigned_input_files
            data_container_id = self.mongo.db['data_containers'].insert_one(data_container).inserted_id
            data_container_ids = [val if val else data_container_id for val in data_container_ids]

        self.mongo.db['application_containers'].update_one(
            {'_id': application_container_id},
            {'$set': {'data_container_ids': data_container_ids}}
        )
