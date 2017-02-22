import json
import os
import docker
from docker.errors import APIError
from queue import Queue
from threading import Semaphore, Thread
from traceback import format_exc
from requests.exceptions import ReadTimeout, ConnectionError

from cc_commons.notification import notify
from cc_commons.states import end_states


def handle_api_errors():
    """function decorator"""
    def dec(func):
        def wrapper(self, container_id, collection):
            try:
                return func(self, container_id, collection)
            except (ReadTimeout, APIError, ConnectionError):
                self.update_node_status_by_container(container_id, collection)
                raise
        return wrapper
    return dec


class DockerClientProxy:
    def __init__(self, config, tee, mongo, node_name, node_config):
        self._config = config
        self._tee = tee
        self._mongo = mongo

        self.node_name = node_name
        self.node_config = node_config

        self._thread_limit = Semaphore(self._config.docker['thread_limit'])

        tls = False
        if self.node_config.get('tls'):
            tls = docker.tls.TLSConfig(**self.node_config['tls'])

        self.client = docker.Client(
            base_url=self.node_config['base_url'],
            tls=tls,
            timeout=self._config.docker.get('api_timeout')
        )

    def info(self):
        with self._thread_limit:
            info = self.client.info()

        application_containers = list(self._mongo.db['application_containers'].find({
            'state': {'$nin': end_states()},
            'cluster_node': self.node_name
        }, {
            'container_ram': 1
        }))

        data_containers = list(self._mongo.db['data_containers'].find({
            'state': {'$nin': end_states()},
            'cluster_node': self.node_name
        }, {
            'container_ram': 1
        }))

        dc_ram = [c['container_ram'] for c in data_containers]
        ac_ram = [c['container_ram'] for c in application_containers]

        reserved_ram = sum(dc_ram + ac_ram)

        return {
            'name': self.node_name,
            'total_ram': info['MemTotal'] // (1024 * 1024),
            'reserved_ram': reserved_ram,
            'total_cpus': info['NCPU'],
            'reserved_cpus': None,
            'active_application_containers': ac_ram,
            'active_data_containers': dc_ram
        }

    def node_status(self):
        is_dead = False
        container_name = 'inspect-{}'.format(self.node_name)
        description = None
        try:
            self.remove_container(container_name)
            self._create_inspection_container(container_name)
            self.start_container(container_name)
            self.wait_for_container(container_name)
        except (ReadTimeout, APIError, ConnectionError):
            is_dead = True
            description = format_exc()

        if not is_dead:
            for key, val in self.containers().items():
                if key == container_name:
                    if val['exit_status'] != 0:
                        is_dead = True
                        description = val['description']
                    break

        self.remove_container(container_name)

        return {'name': self.node_name, 'is_dead': is_dead, 'description': description}

    def containers(self):
        with self._thread_limit:
            containers = self.client.containers(quiet=False, all=True, limit=-1)
        result = {}
        for container in containers:
            exit_status = None
            description = None
            name = container['Names'][0].split('/')[-1]
            if container['Status'].split()[0].lower() == 'exited':
                exit_status = int(container['Status'].split('(')[-1].split(')')[0])
                description = container['Status']
            result[name] = {
                'exit_status': exit_status,
                'description': description,
                'node': self.node_name
            }
        return result

    def remove_container(self, container_name):
        try:
            with self._thread_limit:
                self.client.kill(str(container_name))
        except:
            pass
        try:
            with self._thread_limit:
                self.client.remove_container(str(container_name))
        except:
            pass

    def wait_for_container(self, container_name):
        with self._thread_limit:
            self.client.wait(str(container_name))

    def logs_from_container(self, container_name):
        with self._thread_limit:
            return self.client.logs(str(container_name)).decode("utf-8")

    def start_container(self, container_name):
        with self._thread_limit:
            self.client.start(str(container_name))

    def create_host_config(self, *args, **kwargs):
        with self._thread_limit:
            self.client.create_host_config(*args, **kwargs)

    def create_container(self, *args, **kwargs):
        with self._thread_limit:
            self.client.create_container(*args, **kwargs)

    def connect_container_to_network(self, *args, **kwargs):
        with self._thread_limit:
            self.client.connect_container_to_network(*args, **kwargs)

    def get_ip(self, _id):
        if self._config.docker.get('net'):
            return str(_id)
        with self._thread_limit:
            container = self.client.inspect_container(str(_id))
        return container['NetworkSettings']['Networks']['bridge']['IPAddress']

    def update_image(self, image, registry_auth):
        self._tee('Pull image {} on node {}.'.format(image, self.node_name))
        with self._thread_limit:
            for line in self.client.pull(image, stream=True, auth_config=registry_auth):
                line = str(line)
                if 'error' in line.lower():
                    raise Exception(line)

    def _create_inspection_container(self, container_name):
        settings = {
            'container_type': 'inspection',
            'inspection_url': '{}'.format(self._config.server['host'].rstrip('/'))
        }

        entry_point = self._config.defaults['data_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        self.create_container(
            name=container_name,
            image=self._config.defaults['data_container_description']['image'],
            command=command
        )

        if self._config.docker.get('net'):
            self.connect_container_to_network(
                container=str(container_name),
                net_id=self._config.docker['net']
            )


class DockerProvider:
    def __init__(self, config, tee, mongo):
        self._tee = tee
        self._mongo = mongo
        self._config = config

        self._node_configs = {}
        self._update_node_configs()
        self._clients = {}

        threads = []
        q = Queue()
        for node_name in self._node_configs:
            t = Thread(target=self._docker_client_proxy, args=(node_name, q))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        while not q.empty():
            client = q.get()
            if isinstance(client, DockerClientProxy):
                self._clients[client.node_name] = client
            else:
                node_name, formatted_exception = client
                self._mongo.db['dead_nodes'].update_one(
                    {'name': node_name},
                    {'$set': {'name': node_name, 'description': formatted_exception}},
                    upsert=True
                )
                self._tee('Dead node: {}'.format(node_name))

    def logs_from_container(self, container_id, collection):
        return self._client(container_id, collection).logs_from_container(container_id)

    def _docker_client_proxy(self, node_name, q):
        try:
            client = DockerClientProxy(
                config=self._config,
                tee=self._tee,
                mongo=self._mongo,
                node_name=node_name,
                node_config=self._node_configs[node_name]
            )
            client.containers()
            q.put(client)
        except:
            q.put((node_name, format_exc()))

    def _update_node_configs(self):
        node_configs = {}
        if self._config.docker.get('machines_dir'):
            machines_dir = os.path.expanduser(self._config.docker['machines_dir'])
            for machine_dir in os.listdir(machines_dir):
                with open(os.path.join(machines_dir, machine_dir, 'config.json')) as f:
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
                        'verify': machine_config['HostOptions']['AuthOptions']['CaCertPath'],
                        'client_cert': [
                            machine_config['HostOptions']['AuthOptions']['ClientCertPath'],
                            machine_config['HostOptions']['AuthOptions']['ClientKeyPath']
                        ],
                        'assert_hostname': False
                    }
                }
                node_configs[node_name] = node_config
        if self._config.docker.get('nodes'):
            for node_name, node_config in self._config.docker['nodes'].items():
                node_configs[node_name] = node_config
        self._node_configs = node_configs

    def update_nodes_status(self):
        if not self._config.defaults['error_handling'].get('dead_node_invalidation'):
            return
        self._tee('Update nodes status...')
        self._update_node_configs()
        threads = []
        for node_name in list(self._node_configs):
            t = Thread(target=self.update_node_status, args=(node_name,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def update_node_status_by_container(self, container_id, collection):
        container = self._mongo.db[collection].find_one(
            {'_id': container_id},
            {'cluster_node': 1}
        )
        self.update_node_status(container['cluster_node'])

    def update_node_status(self, node_name):
        if not self._config.defaults['error_handling'].get('dead_node_invalidation'):
            return
        self._update_node_configs()
        if node_name not in self._node_configs:
            if node_name in self._clients:
                del self._clients[node_name]
            self._tee('Could not find config for node: {}'.format(node_name))
            return
        self._tee('Update status of node: {}'.format(node_name))
        node = self._clients.get(node_name)
        if not node:
            node = DockerClientProxy(
                config=self._config,
                tee=self._tee,
                mongo=self._mongo,
                node_name=node_name,
                node_config=self._node_configs[node_name]
            )
        node_status = node.node_status()

        if node_status['is_dead']:
            if node_name in self._clients:
                del self._clients[node_name]

            self._mongo.db['dead_nodes'].update_one(
                {'name': node_status['name']},
                {'$set': {'name': node_status['name'], 'description': node_status['description']}},
                upsert=True
            )
            self._tee('Dead node: {}'.format(node_name))
            if self._config.defaults['error_handling'].get('dead_node_notification'):
                connector_access = self._config.defaults['error_handling']['dead_node_notification']
                connector_access['add_meta_data'] = True
                meta_data = {'name': node_name}
                notify(self._tee, [connector_access], meta_data)
        else:
            if node_name not in self._clients:
                self._clients[node_name] = node

            dead_nodes = self._mongo.db['dead_nodes'].find({'name': node['name']}, {'_id': 1})
            for dead_node in dead_nodes:
                self._mongo.db['dead_nodes'].delete_one({'_id': dead_node['_id']})

    def _client(self, container_id, collection):
        container = self._mongo.db[collection].find_one(
            {'_id': container_id},
            {'cluster_node': 1}
        )
        if not container:
            return None
        return self._clients.get(container['cluster_node'])

    @handle_api_errors()
    def get_ip(self, container_id, collection):
        return self._client(container_id, collection).get_ip(container_id)

    @handle_api_errors()
    def wait_for_container(self, container_id, collection):
        self._client(container_id, collection).wait_for_container(container_id)

    @handle_api_errors()
    def start_container(self, container_id, collection):
        self._client(container_id, collection).start_container(container_id)

    def remove_container(self, container_id, collection):
        client = self._client(container_id, collection)
        if client:
            client.remove_container(container_id)

    @handle_api_errors()
    def create_container(self, container_id, collection):
        if collection == 'application_containers':
            self._create_application_container(container_id)
        elif collection == 'data_containers':
            self._create_data_container(container_id)
        else:
            raise Exception('Collection not valid:', collection)

    def update_image(self, node_name, image, registry_auth):
        try:
            self._clients[node_name].update_image(image, registry_auth)
        except:
            self._tee('Error on image update for node: {}'.format(node_name))
            self.update_node_status(node_name)

    def update_data_container_image(self, image, registry_auth):
        nodes = self.nodes()
        threads = []
        for node in nodes:
            t = Thread(target=self._update_data_container_image, args=(node['name'], image, registry_auth))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def _update_data_container_image(self, node_name, image, registry_auth):
        try:
            self._clients[node_name].update_image(image, registry_auth)
        except:
            self._tee('Error on image update for node: {}'.format(node_name))
            del self._clients[node_name]
            self._mongo.db['dead_nodes'].update_one(
                {'name': node_name},
                {'$set': {'name': node_name, 'description': format_exc()}},
                upsert=True
            )
            self._tee('Dead node: {}'.format(node_name))

    def _create_application_container(self, application_container_id):
        application_container = self._mongo.db['application_containers'].find_one({'_id': application_container_id})
        task_id = application_container['task_id'][0]
        task = self._mongo.db['tasks'].find_one({'_id': task_id})

        settings = {
            'container_type': 'application',
            'container_id': str(application_container_id),
            'callback_key': application_container['callback_key'],
            'callback_url': '{}/application-containers/callback'.format(self._config.server['host'].rstrip('/'))
        }

        entry_point = self._config.defaults['application_container_description']['entry_point']
        if task['application_container_description'].get('entry_point'):
            entry_point = task['application_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        mem_limit = '{}MB'.format(task['application_container_description']['container_ram'])

        security_opt = None
        if task['application_container_description'].get('tracing'):
            security_opt = ['seccomp:unconfined']

        node_name = application_container['cluster_node']
        client = self._clients[node_name]

        host_config = client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit,
            security_opt=security_opt
        )

        client.create_container(
            name=str(application_container_id),
            image=task['application_container_description']['image'],
            host_config=host_config,
            command=command
        )

        if self._config.docker.get('net'):
            client.connect_container_to_network(
                container=str(application_container_id),
                net_id=self._config.docker['net']
            )

    def _create_data_container(self, data_container_id):
        data_container = self._mongo.db['data_containers'].find_one({'_id': data_container_id})

        settings = {
            'container_id': str(data_container_id),
            'container_type': 'data',
            'callback_key': data_container['callback_key'],
            'callback_url': '{}/data-containers/callback'.format(self._config.server['host'].rstrip('/')),
        }

        entry_point = self._config.defaults['data_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        mem_limit = '{}MB'.format(self._config.defaults['data_container_description']['container_ram'])

        node_name = data_container['cluster_node']
        client = self._clients[node_name]

        host_config = client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit
        )

        client.create_container(
            name=str(data_container_id),
            image=self._config.defaults['data_container_description']['image'],
            host_config=host_config,
            command=command
        )

        if self._config.docker.get('net'):
            client.connect_container_to_network(
                container=str(data_container_id),
                net_id=self._config.docker['net']
            )

    def nodes(self):
        threads = []
        q = Queue()
        for node_name in self._clients:
            t = Thread(target=self._client_info, args=(node_name, q))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        nodes = []
        while not q.empty():
            nodes.append(q.get())
        return nodes

    def _client_info(self, node_name, q):
        try:
            q.put(self._clients[node_name].info())
        except:
            self._tee('Error on info request for node: {}'.format(node_name))
            self.update_node_status(node_name)

    def containers(self):
        threads = []
        q = Queue()
        for node_name in self._clients:
            t = Thread(target=self._containers, args=(node_name, q))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        containers = {}
        while not q.empty():
            containers.update(q.get())
        return containers

    def _containers(self, node_name, q):
        try:
            q.put(self._clients[node_name].containers())
        except:
            self._tee('Error on container list for node: {}'.format(node_name))
            self.update_node_status(node_name)


def _to_mib(val, unit):
    if unit == 'B':
        return val / (1000 ** 2)
    elif unit == 'KiB':
        return val / 1000
    elif unit == 'MiB':
        return val
    elif unit == 'GiB':
        return val * 1000
    raise Exception("Unit '{}' not supported.".format(unit))
