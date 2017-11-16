import json
import os
from threading import Lock, Thread
from traceback import format_exc
from bson.objectid import ObjectId

from cc_server.commons.states import state_to_index, end_states
from cc_server.commons.notification import notify


class Cluster:
    def __init__(self, config, tee, mongo, state_handler, cluster_provider):
        self._config = config
        self._tee = tee
        self._mongo = mongo
        self._state_handler = state_handler
        self._cluster_provider = cluster_provider

        self._data_container_lock = Lock()

        self._create_nodes_on_startup()

    def update_image(self, node_name, image, registry_auth):
        try:
            self._cluster_provider.update_image(node_name, image, registry_auth)
        except:
            pass

    def create_container(self, container_id, collection):
        node_name = self._lookup_node_name(container_id, collection)
        try:
            self._cluster_provider.create_container(container_id, collection)
            description = 'Container waiting.'
            self._state_handler.transition(collection, container_id, 'waiting', description)
        except:
            description = 'Container creation failed.'
            if not self._update_node_and_check_if_online(node_name):
                description = 'Container creation failed due to node {} being offline.'.format(node_name)
            self._state_handler.transition(collection, container_id, 'failed', description, exception=format_exc())
            self._cluster_provider.remove_container(node_name, container_id)

    def start_container(self, container_id, collection):
        node_name = self._lookup_node_name(container_id, collection)
        try:
            self._cluster_provider.start_container(node_name, container_id)
            ip = self._cluster_provider.get_ip(node_name, container_id)
            self._mongo.db[collection].update_one({'_id': container_id}, {'$set': {'ip': ip}})
        except:
            description = 'Container start failed.'
            if not self._update_node_and_check_if_online(node_name):
                description = 'Container start failed due to node {} being offline.'.format(node_name)
            self._state_handler.transition(collection, container_id, 'failed', description, exception=format_exc())
            self._cluster_provider.remove_container(node_name, container_id)

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
                node_name = self._lookup_node_name(c['_id'], collection)
                if c['state'] in end_states():
                    self._cluster_provider.remove_container(node_name, c['_id'])
                elif container.get('exit_status') and container['exit_status'] != 0:
                    logs = 'container logs not available'
                    try:
                        logs = self._cluster_provider.logs_from_container(node_name, c['_id'])
                    except:
                        pass
                    description = 'Container exited unexpectedly ({}): {}'.format(container['description'], logs)
                    self._state_handler.transition(collection, c['_id'], 'failed', description)
                    self._cluster_provider.remove_container(node_name, c['_id'])

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
                node_name = self._lookup_node_name(data_container_id, 'data_containers')
                self._cluster_provider.remove_container(node_name, data_container_id)

    def _lookup_node_name(self, container_id, collection):
        container = self._mongo.db[collection].find_one(
            {'_id': container_id},
            {'cluster_node': 1}
        )
        if not container:
            return None
        return container['cluster_node']

    def _create_nodes_on_startup(self):
        self._mongo.db['nodes'].drop()
        node_configs = self._read_node_configs()
        threads = []
        for node_name, node_config in node_configs.items():
            self._tee('Create node {}.'.format(node_name))
            t = Thread(target=self._update_node, args=(node_name, node_config, True))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        self._cluster_provider.create_network()

    def _update_node_and_check_if_online(self, node_name):
        self.update_node(node_name)
        node = self._mongo.db['nodes'].find_one({'cluster_node': node_name}, {'is_online': 1})
        return node['is_online']

    def update_node(self, node_name):
        node_configs = self._read_node_configs()
        node_config = node_configs.get(node_name)
        if not node_config:
            s = 'Config for node {} does not exist.'.format(node_name)
            self._tee(s)
            node = self._mongo.db['nodes'].find_one({'cluster_node': node_name}, {'is_online': 1})
            if node and node.get('is_online'):
                self._mongo.db['nodes'].update_one(
                    {'cluster_node': node_name},
                    {'$set': {
                        'is_online': False,
                        'debug_info': s
                    }},
                    upsert=True
                )
        self._update_node(node_name, node_config, False)

    def _update_node(self, node_name, node_config, startup):
        node = {
            'cluster_node': node_name,
            'config': node_config,
            'is_online': True,
            'debug_info': None,
            'total_ram': None,
            'total_cpus': None
        }

        try:
            self._cluster_provider.update_node(node_name, node_config, startup)
            info = self._cluster_provider.node_info(node_name)
            node['total_ram'] = info['total_ram']
            node['total_cpus'] = info['total_cpus']
        except:
            node['debug_info'] = format_exc()
            node['is_online'] = False

        self._mongo.db['nodes'].update_one({'cluster_node': node_name}, {'$set': node}, upsert=True)

        self._tee(json.dumps(node, indent=4))

        if not node['is_online'] and self._config.defaults['error_handling'].get('node_offline_notification'):
            connector_access = self._config.defaults['error_handling']['node_offline_notification']
            connector_access['add_meta_data'] = True
            meta_data = {'name': node_name}
            notify(self._tee, [connector_access], meta_data)

    def _read_node_configs(self):
        node_configs = {}
        if self._config.docker.get('docker_machine_dir'):
            machine_dir = os.path.expanduser(self._config.docker['docker_machine_dir'])
            machines_dir = os.path.join(machine_dir, 'machines')
            for d in os.listdir(machines_dir):
                with open(os.path.join(machines_dir, d, 'config.json')) as f:
                    machine_config = json.load(f)
                node_name = machine_config['Driver']['MachineName']
                if not machine_config['HostOptions']['EngineOptions'].get('ArbitraryFlags'):
                    continue
                port = None
                try:
                    for flag in machine_config['HostOptions']['EngineOptions']['ArbitraryFlags']:
                        key, val = flag.split('=')
                        if key == 'cluster-advertise':
                            port = int(val.split(':')[-1])
                            break
                except:
                    pass
                if not port:
                    continue
                node_config = {
                    'base_url': '{}:{}'.format(machine_config['Driver']['IPAddress'], port),
                    'tls': {
                        'verify': os.path.join(machine_dir, 'certs', 'ca.pem'),
                        'client_cert': [
                            os.path.join(machine_dir, 'certs', 'cert.pem'),
                            os.path.join(machine_dir, 'certs', 'key.pem')
                        ],
                        'assert_hostname': False
                    }
                }
                node_configs[node_name] = node_config
        if self._config.docker.get('nodes'):
            for node_name, node_config in self._config.docker['nodes'].items():
                node_configs[node_name] = node_config
        return node_configs
