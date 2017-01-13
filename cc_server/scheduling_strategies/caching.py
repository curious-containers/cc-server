from cc_commons.helper import generate_secret


def data_container_prototype(username, input_files, container_ram):
    return {
        'state': -1,
        'transitions': [],
        'username': username,
        'task_id': None,
        'input_files': input_files,
        'input_file_keys': [generate_secret() for _ in input_files],
        'callbacks': [],
        'callback_key': generate_secret(),
        'cluster_node': None,
        'container_ram': container_ram
    }


class OneCachePerTaskNoDuplicates:
    def __init__(self, config, tee, mongo, cluster):
        self.config = config
        self.tee = tee
        self.mongo = mongo
        self.cluster = cluster

    def apply(self, application_container_id):
        self.cluster.assign_existing_data_containers(application_container_id)

        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id},
            {'task_id': 1, 'data_container_ids': 1}
        )
        task = self.mongo.db['tasks'].find_one(
            {'_id': application_container['task_id'][0]},
            {'input_files': 1, 'username': 1}
        )

        data_container_ids = application_container['data_container_ids']
        input_files = task['input_files']

        unassigned_input_files = [f for f, dc_id in zip(input_files, data_container_ids) if not dc_id]

        if unassigned_input_files:
            container_ram = self.config.defaults['data_container_description']['container_ram']
            data_container = data_container_prototype(task['username'], input_files, container_ram)
            data_container_id = self.mongo.db['data_containers'].insert_one(data_container).inserted_id
            data_container_ids = [val if val else data_container_id for val in data_container_ids]

        self.mongo.db['application_containers'].update_one(
            {'_id': application_container_id},
            {'$set': {'data_container_ids': data_container_ids}}
        )
