import json
from threading import Lock
from traceback import format_exc
from bson.objectid import ObjectId

from cc_server.states import state_to_index, end_states


class Cluster:
    def __init__(self, tee, mongo, cluster_provider, config, state_handler):
        self.tee = tee
        self.mongo = mongo
        self.cluster_provider = cluster_provider
        self.config = config
        self.state_handler = state_handler

        self.data_container_lock = Lock()

    def get_ip(self, container_id, collection):
        ip = None
        try:
            ip = self.cluster_provider.get_ip(container_id, collection)
        except:
            description = 'Could not get container ip.'
            self.state_handler.transition(collection, container_id, 'failed', description,
                                          exception=format_exc())
            self.cluster_provider.remove_container(container_id, collection)
        return ip

    def update_nodes_status(self):
        self.cluster_provider.update_nodes_status()

    def update_node_status(self, node_name):
        self.cluster_provider.update_node_status(node_name)

    def nodes(self):
        return self.cluster_provider.nodes()

    def update_data_container_image(self, image):
        registry_auth = self.config.defaults['data_container_description'].get('registry_auth')
        self.cluster_provider.update_data_container_image(image, registry_auth)

    def update_application_container_image(self, node_name, image, registry_auth):
        self.cluster_provider.update_image(node_name, image, registry_auth)

    def start_container(self, container_id, collection):
        try:
            self.cluster_provider.start_container(container_id, collection)
        except:
            description = 'Container start failed.'
            self.state_handler.transition(collection, container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(container_id, collection)

    def assign_existing_data_containers(self, application_container_id):
        with self.data_container_lock:
            application_container = self.mongo.db['application_containers'].find_one(
                {'_id': application_container_id},
                {'task_id': 1}
            )
            task = self.mongo.db['tasks'].find_one(
                {'_id': application_container['task_id'][0]},
                {'input_files': 1}
            )

            files = task['input_files']
            data_container_ids = []
            for f in files:
                data_container = self.mongo.db['data_containers'].find_one(
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

            self.mongo.db['application_containers'].update({'_id': application_container_id}, {
                '$set': {'data_container_ids': data_container_ids}
            })

    def create_container(self, container_id, collection):
        try:
            self.cluster_provider.create_container(container_id, collection)
            description = 'Container waiting.'
            self.state_handler.transition(collection, container_id, 'waiting', description)
        except:
            description = 'Container creation failed.'
            self.state_handler.transition(collection, container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(container_id, collection)

    def list_containers(self):
        return self.cluster_provider.list_containers()

    def clean_up_containers(self):
        containers = self.cluster_provider.containers()
        for key in containers:
            try:
                ObjectId(key)
            except:
                del containers[key]

        for collection in ['application_containers', 'data_containers']:
            cursor = self.mongo.db[collection].find({
                '_id': {'$in': [ObjectId(key) for key in containers]}
            }, {'state': 1})
            for c in cursor:
                name = str(c['_id'])
                container = containers[name]
                if c['state'] in end_states():
                    self.cluster_provider.remove_container(c['_id'], collection)
                elif container.get('exit_status') and container['exit_status'] != 0:
                    description = 'Container exited unexpectedly: {}'.format(container['description'])
                    self.state_handler.transition(collection, c['_id'], 'failed', description)
                    self.cluster_provider.remove_container(c['_id'], collection)

        for collection in ['application_containers', 'data_containers']:
            cursor = self.mongo.db[collection].find({
                'state': {'$nin': end_states()}
            }, {'_id': 1})
            for c in cursor:
                name = str(c['_id'])
                if name not in containers:
                    description = 'Container vanished.'
                    self.state_handler.transition(collection, c['_id'], 'failed', description)

    def clean_up_unused_data_containers(self):
        with self.data_container_lock:
            cursor = self.mongo.db['data_containers'].find(
                {'state': state_to_index('processing')},
                {'_id': 1}
            )
            for data_container in cursor:
                data_container_id = data_container['_id']
                application_container = self.mongo.db['application_containers'].find_one({
                    'state': {'$nin': end_states()},
                    'data_container_ids': data_container_id
                }, {'_id': 1})
                if application_container:
                    continue

                description = 'Container removed. Not in use by any application container.'
                self.state_handler.transition('data_containers', data_container_id, 'success', description)
                self.cluster_provider.remove_container(data_container_id, 'data_containers')
