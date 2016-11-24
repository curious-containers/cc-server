import docker
import json
from threading import Semaphore, Thread
from queue import Queue
from requests.exceptions import ReadTimeout
from docker.errors import APIError
from traceback import format_exc
from pprint import pprint

from cc_server.states import end_states


def handle_api_errors():
    """function decorator"""
    def dec(func):
        def wrapper(self, container_id, collection):
            try:
                return func(self, container_id, collection)
            except (ReadTimeout, APIError):
                self._update_node_status_by_container(container_id, collection)
                raise
        return wrapper
    return dec


class DockerClientProxy:
    def __init__(self, node_name, mongo, config):
        self.node_name = node_name
        self.mongo = mongo
        self.config = config
        self.node_config = config.docker['nodes'][node_name]

        tls = False
        if self.node_config.get('tls'):
            tls = docker.tls.TLSConfig(**self.node_config['tls'])

        self.client = docker.Client(
            base_url=self.node_config['base_url'],
            tls=tls,
            timeout=self.config.docker.get('api_timeout')
        )

        self.thread_limit = Semaphore(self.config.docker['thread_limit'])

    def info(self):
        with self.thread_limit:
            info = self.client.info()

        application_containers = list(self.mongo.db['application_containers'].find({
            'state': {'$nin': end_states()},
            'cluster_node': self.node_name
        }, {
            'container_ram': 1
        }))

        data_containers = list(self.mongo.db['data_containers'].find({
            'state': {'$nin': end_states()},
            'cluster_node': self.node_name
        }, {
            'container_ram': 1
        }))

        reserved_ram = sum([c['container_ram'] for c in data_containers + application_containers])

        return {
            'name': self.node_name,
            'total_ram': info['MemTotal'] // (1024 * 1024),
            'reserved_ram': reserved_ram,
            'total_cpus': info['NCPU'],
            'reserved_cpus': None,
            'active_application_containers': len(application_containers),
            'active_data_containers': len(data_containers)
        }

    def node_status(self):
        if not self.config.defaults['error_handling'].get('dead_node_invalidation'):
            return

        is_dead = False
        container_name = 'inspect-{}'.format(self.node_name)
        reason = None
        try:
            self.remove_container(container_name)
            self._create_inspection_container(container_name)
            self.start_container(container_name)
            self.wait_for_container(container_name)
        except (ReadTimeout, APIError):
            is_dead = True
            reason = format_exc()

        if not is_dead:
            containers = self.list_containers()
            for container in containers:
                if container['Names'][0].split('/')[1] == container_name:
                    if '0' not in container['Status']:
                        is_dead = True
                        reason = container['Status']
                    break

        self.remove_container(container_name)

        return {'name': self.node_name, 'is_dead': is_dead, 'reason': reason}

    def list_containers(self):
        with self.thread_limit:
            containers = self.client.containers(quiet=False, all=True, limit=-1)
        return containers

    def remove_container(self, container_name):
        try:
            with self.thread_limit:
                self.client.kill(str(container_name))
        except:
            pass
        try:
            with self.thread_limit:
                self.client.remove_container(str(container_name))
        except:
            pass

    def wait_for_container(self, container_name):
        with self.thread_limit:
            self.client.wait(str(container_name))

    def logs_from_container(self, container_name):
        with self.thread_limit:
            return self.client.logs(str(container_name)).decode("utf-8")

    def start_container(self, container_name):
        with self.thread_limit:
            self.client.start(str(container_name))

    def create_host_config(self, *args, **kwargs):
        with self.thread_limit:
            self.client.create_host_config(*args, **kwargs)

    def create_container(self, *args, **kwargs):
        with self.thread_limit:
            self.client.create_container(*args, **kwargs)

    def connect_container_to_network(self, *args, **kwargs):
        with self.thread_limit:
            self.client.connect_container_to_network(*args, **kwargs)

    def get_ip(self, _id):
        if self.config.docker.get('net'):
            return str(_id)
        with self.thread_limit:
            container = self.client.inspect_container(str(_id))
        return container['NetworkSettings']['Networks']['bridge']['IPAddress']

    def update_image(self, image, registry_auth):
        with self.thread_limit:
            for line in self.client.pull(image, stream=True, auth_config=registry_auth):
                line = str(line)
                if self.config.server.get('debug'):
                    print(line)
                if 'error' in line.lower():
                    raise Exception(line)

    def _create_inspection_container(self, container_name):
        settings = {
            'container_type': 'inspection',
            'inspection_url': '{}'.format(self.config.server['host'].rstrip('/'))
        }

        entry_point = self.config.defaults['data_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        if self.config.server.get('debug'):
            print('inspection_container', command)

        self.create_container(
            name=container_name,
            image=self.config.defaults['data_container_description']['image'],
            command=command
        )

        if self.config.docker.get('net'):
            self.connect_container_to_network(
                container=str(container_name),
                net_id=self.config.docker['net']
            )


class DockerProvider:
    def __init__(self, mongo, config):
        self.mongo = mongo
        self.config = config

        nodes = self.config.docker['nodes']
        self.clients = {}
        for node_name in nodes:
            self.clients[node_name] = DockerClientProxy(node_name, mongo, config)

    def update_nodes_status(self):
        if not self.config.defaults['error_handling'].get('dead_node_invalidation'):
            return
        print('Update nodes status...')
        threads = []
        for node_name in self.clients:
            t = Thread(target=self.update_node_status, args=(node_name,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        print('Dead nodes:')
        pprint(list(self.mongo.db['dead_nodes'].find({}, {'name': 1})))

    def _update_node_status_by_container(self, container_id, collection):
        container = self.mongo.db[collection].find_one(
            {'_id': container_id},
            {'cluster_node': 1}
        )
        self.update_node_status(container['cluster_node'])

    def update_node_status(self, node_name):
        node = self.clients[node_name].node_status()
        if node['is_dead']:
            self.mongo.db['dead_nodes'].update_one(
                {'name': node['name']},
                {'$set': {'name': node['name'], 'reason': node['reason']}},
                upsert=True
            )
        else:
            dead_nodes = self.mongo.db['dead_nodes'].find({'name': node['name']}, {'_id': 1})
            for dead_node in dead_nodes:
                self.mongo.db['dead_nodes'].delete_one({'_id': dead_node['_id']})

    def _client(self, container_id, collection):
        container = self.mongo.db[collection].find_one(
            {'_id': container_id},
            {'cluster_node': 1}
        )
        return self.clients[container['cluster_node']]

    @handle_api_errors()
    def get_ip(self, container_id, collection):
        return self._client(container_id, collection).get_ip(container_id)

    @handle_api_errors()
    def wait_for_container(self, container_id, collection):
        self._client(container_id, collection).wait_for_container(container_id)

    @handle_api_errors()
    def start_container(self, container_id, collection):
        self._client(container_id, collection).start_container(container_id)

    @handle_api_errors()
    def remove_container(self, container_id, collection):
        self._client(container_id, collection).start_container(container_id)

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
            self.clients[node_name].update_image(image, registry_auth)
        except:
            print('Error on image update for node {}: {}'.format(node_name, format_exc()))

    def update_data_container_image(self, image, registry_auth):
        nodes = self.nodes()
        threads = []
        for node in nodes:
            t = Thread(target=self.update_image, args=(node['name'], image, registry_auth))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def _create_application_container(self, application_container_id):
        application_container = self.mongo.db['application_containers'].find_one({'_id': application_container_id})
        task_id = application_container['task_id'][0]
        task = self.mongo.db['tasks'].find_one({'_id': task_id})

        settings = {
            'container_type': 'application',
            'container_id': str(application_container_id),
            'callback_key': application_container['callback_key'],
            'callback_url': '{}/application-containers/callback'.format(self.config.server['host'].rstrip('/'))
        }

        entry_point = self.config.defaults['application_container_description']['entry_point']
        if task['application_container_description'].get('entry_point'):
            entry_point = task['application_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        if self.config.server.get('debug'):
            print('application_container', command)

        mem_limit = '{}MB'.format(task['application_container_description']['container_ram'])

        security_opt = None
        if task['application_container_description'].get('tracing'):
            security_opt = ['seccomp:unconfined']

        node_name = application_container['cluster_node']
        client = self.clients[node_name]

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

        if self.config.docker.get('net'):
            client.connect_container_to_network(
                container=str(application_container_id),
                net_id=self.config.docker['net']
            )

    def _create_data_container(self, data_container_id):
        data_container = self.mongo.db['data_containers'].find_one({'_id': data_container_id})

        settings = {
            'container_id': str(data_container_id),
            'container_type': 'data',
            'callback_key': data_container['callback_key'],
            'callback_url': '{}/data-containers/callback'.format(self.config.server['host'].rstrip('/')),
            'input_files': data_container['input_files'],
            'input_file_keys': data_container['input_file_keys']
        }

        entry_point = self.config.defaults['data_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        if self.config.server.get('debug'):
            print('data_container', command)

        mem_limit = '{}MB'.format(self.config.defaults['data_container_description']['container_ram'])

        node_name = data_container['cluster_node']
        client = self.clients[node_name]

        host_config = client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit
        )

        client.create_container(
            name=str(data_container_id),
            image=self.config.defaults['data_container_description']['image'],
            host_config=host_config,
            command=command
        )

        if self.config.docker.get('net'):
            client.connect_container_to_network(
                container=str(data_container_id),
                net_id=self.config.docker['net']
            )

    def nodes(self):
        dead_nodes = self.mongo.db['dead_nodes'].find({}, {'name': 1})
        dead_node_names = set()
        dead_node_names.update([dead_node['name'] for dead_node in dead_nodes])
        threads = []
        q = Queue()
        for node_name in self.clients:
            if node_name not in dead_node_names:
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
            q.put(self.clients[node_name].info())
        except:
            print('Error on info request for node {}: {}'.format(node_name, format_exc()))

    def list_containers(self):
        threads = []
        q = Queue()
        for node_name in self.clients:
            t = Thread(target=self._list_containers, args=(node_name, q))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        container_list = []
        while not q.empty():
            container_list += q.get()
        return container_list

    def _list_containers(self, node_name, q):
        try:
            q.put(self.clients[node_name].info())
        except:
            print('Error on container list for node {}: {}'.format(node_name, format_exc()))



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
