from threading import Lock
from traceback import format_exc

from bson.objectid import ObjectId

from cc_commons.states import state_to_index, end_states
from cc_server_master.cluster_provider import DockerProvider


class Cluster:
    def __init__(self, config, tee, mongo, state_handler, cluster_provider):
        self._config = config
        self._tee = tee
        self._mongo = mongo
        self._state_handler = state_handler
        self._cluster_provider = cluster_provider

        self._data_container_lock = Lock()

    def update_node_status(self, node_name):
        self._cluster_provider.update_node_status(node_name)

    def nodes(self):
        return self._cluster_provider.nodes()

    def update_image(self, node_name, image, registry_auth):
        self._cluster_provider.update_image(node_name, image, registry_auth)

    def start_container(self, container_id, collection):
        try:
            self._cluster_provider.start_container(container_id, collection)
            ip = self._cluster_provider.get_ip(container_id, collection)
            self._mongo.db[collection].update_one({'_id': container_id}, {'$set': {'ip': ip}})
        except:
            description = 'Container start failed.'
            self._state_handler.transition(collection, container_id, 'failed', description,
                                           exception=format_exc())
            self._cluster_provider.remove_container(container_id, collection)

    def assign_existing_data_containers(self, application_container_id):
        with self._data_container_lock:
            application_container = self._mongo.db['application_containers'].find_one(
                {'_id': application_container_id},
                {'task_id': 1}
            )
            task = self._mongo.db['tasks'].find_one(
                {'_id': application_container['task_id'][0]},
                {'input_files': 1}
            )

            files = task['input_files']
            data_container_ids = []
            for f in files:
                data_container = self._mongo.db['data_containers'].find_one(
                    {
                        'state': {'$in': [
                            state_to_index('created'),
                            state_to_index('waiting'),
                            state_to_index('processing')
                        ]},
                        'input_files': f
                    }, {'_id': 1}
                )
                if data_container:
                    data_container_ids.append(data_container['_id'])
                else:
                    data_container_ids.append(None)

            self._mongo.db['application_containers'].update({'_id': application_container_id}, {
                '$set': {'data_container_ids': data_container_ids}
            })

    def create_container(self, container_id, collection):
        try:
            self._cluster_provider.create_container(container_id, collection)
            description = 'Container waiting.'
            self._state_handler.transition(collection, container_id, 'waiting', description)
        except:
            description = 'Container creation failed.'
            self._state_handler.transition(collection, container_id, 'failed', description,
                                           exception=format_exc())
            self._cluster_provider.remove_container(container_id, collection)

    def containers(self):
        return self._cluster_provider.containers()

    def clean_up_containers(self):
        containers = self._cluster_provider.containers()
        for key in list(containers):
            try:
                ObjectId(key)
            except:
                del containers[key]

        for collection in ['application_containers', 'data_containers']:
            cursor = self._mongo.db[collection].find({
                '_id': {'$in': [ObjectId(key) for key in containers]}
            }, {'state': 1})
            for c in cursor:
                name = str(c['_id'])
                container = containers[name]
                if c['state'] in end_states():
                    self._cluster_provider.remove_container(c['_id'], collection)
                elif container.get('exit_status') and container['exit_status'] != 0:
                    logs = 'container logs not available'
                    try:
                        logs = self._cluster_provider.logs_from_container(c['_id'], collection)
                    except:
                        pass
                    description = 'Container exited unexpectedly ({}): {}'.format(container['description'], logs)
                    self._state_handler.transition(collection, c['_id'], 'failed', description)
                    self._cluster_provider.remove_container(c['_id'], collection)

        for collection in ['application_containers', 'data_containers']:
            cursor = self._mongo.db[collection].find({
                'state': {'$in': [1, 2]}
            }, {'_id': 1})
            for c in cursor:
                name = str(c['_id'])
                if name not in containers:
                    description = 'Container vanished.'
                    self._state_handler.transition(collection, c['_id'], 'failed', description)

    def clean_up_unused_data_containers(self):
        with self._data_container_lock:
            cursor = self._mongo.db['data_containers'].find(
                {'state': state_to_index('processing')},
                {'_id': 1}
            )
            for data_container in cursor:
                data_container_id = data_container['_id']
                application_container = self._mongo.db['application_containers'].find_one({
                    'state': {'$nin': end_states()},
                    'data_container_ids': data_container_id
                }, {'_id': 1})
                if application_container:
                    continue

                description = 'Container removed. Not in use by any application container.'
                self._state_handler.transition('data_containers', data_container_id, 'success', description)
                self._cluster_provider.remove_container(data_container_id, 'data_containers')
