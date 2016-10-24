from threading import Lock
from traceback import format_exc
from bson.objectid import ObjectId

from cc_server.states import state_to_index, end_states


class Cluster:
    def __init__(self, mongo, cluster_provider, config, state_handler):
        self.mongo = mongo
        self.cluster_provider = cluster_provider
        self.config = config
        self.state_handler = state_handler

        self.data_container_lock = Lock()

    def get_ip(self, _id):
        return self.cluster_provider.get_ip(_id)

    def nodes(self):
        return self.cluster_provider.nodes()

    def update_data_container_image(self, image):
        registry_auth = self.config.defaults['container_description'].get('registry_auth')
        self.cluster_provider.update_image(image, registry_auth)

    def update_application_container_image(self, image, registry_auth):
        try:
            self.cluster_provider.update_image(image, registry_auth)
        except:
            print(format_exc())

    def start_data_container(self, data_container_id):
        try:
            self.cluster_provider.start_container(data_container_id)
        except:
            description = 'Container start failed.'
            self.state_handler.transition('data_containers', data_container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(data_container_id)

    def start_application_container(self, application_container_id):
        try:
            self.cluster_provider.start_container(application_container_id)
        except:
            description = 'Container start failed.'
            self.state_handler.transition('application_containers', application_container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(application_container_id)

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

    def create_data_container(self, data_container_id):
        try:
            self.cluster_provider.create_data_container(data_container_id)
            description = 'Container waiting.'
            self.state_handler.transition('data_containers', data_container_id, 'waiting', description)
        except:
            description = 'Container creation failed.'
            self.state_handler.transition('data_containers', data_container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(data_container_id)

    def create_application_container(self, application_container_id):
        try:
            self.cluster_provider.create_application_container(application_container_id)
            description = 'Container waiting.'
            self.state_handler.transition('application_containers', application_container_id, 'waiting', description)
        except:
            description = 'Container creation failed.'
            self.state_handler.transition('application_containers', application_container_id, 'failed', description,
                       exception=format_exc())
            self.cluster_provider.remove_container(application_container_id)

    def clean_up_finished_containers(self):
        container_ids = []
        for container in self.cluster_provider.list_containers():
            try:
                container_ids.append(ObjectId(container['Names'][0].split('/')[-1]))
            except:
                pass
        if container_ids:
            cursors = [
                self.mongo.db['application_containers'].find({
                    '_id': {'$in': container_ids},
                    'state': {'$in': end_states()}
                }, {'_id': 1}),
                self.mongo.db['data_containers'].find({
                    '_id': {'$in': container_ids},
                    'state': {'$in': end_states()}
                }, {'_id': 1})
            ]
            for cursor in cursors:
                for container in cursor:
                    self.cluster_provider.remove_container(container['_id'])

    def clean_up_exited_containers(self):
        containers = {}
        for container in self.cluster_provider.list_containers():
            try:
                status = container['Status'].split()
                if status[0].lower() == 'exited':
                    container_id = container['Names'][0].split('/')[-1]
                    containers[container_id] = container['Status']
            except:
                pass

        container_ids = []
        for _id, status in containers.items():
            try:
                container_ids.append(ObjectId(_id))
            except:
                pass

        if container_ids:
            cursors = {}
            cursors['application_containers'] = self.mongo.db['application_containers'].find({
                '_id': {'$in': container_ids},
                'state': {'$nin': end_states()}
            }, {'_id': 1})
            cursors['data_containers'] = self.mongo.db['data_containers'].find({
                '_id': {'$in': container_ids},
                'state': {'$nin': end_states()}
            }, {'_id': 1})

            for collection, cursor in cursors.items():
                for container in cursor:
                    status = containers[str(container['_id'])]
                    description = 'Container exited unexpectedly ({}).'.format(status)
                    self.state_handler.transition(collection, container['_id'], 'failed', description)
                    self.cluster_provider.remove_container(container['_id'])

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
                self.cluster_provider.remove_container(data_container_id)
