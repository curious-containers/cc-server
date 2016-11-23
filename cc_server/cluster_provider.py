import sys
import docker
import json
from threading import Semaphore, Thread, Lock
from queue import Queue, Empty
from requests.exceptions import ReadTimeout
from docker.errors import APIError
from traceback import format_exc
from pprint import pprint

from cc_server.states import end_states


def handle_errors():
    """function decorator"""
    def dec(func):
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except:
                self.update_nodes_status()
                raise
        return wrapper
    return dec


class DockerProvider:
    def __init__(self, mongo, config):
        self.mongo = mongo
        self.config = config

        tls = False
        if self.config.docker.get('tls'):
            tls = docker.tls.TLSConfig(**self.config.docker['tls'])

        self.client = docker.Client(
            base_url=self.config.docker['base_url'],
            tls=tls,
            timeout=self.config.docker.get('api_timeout')
        )

        self.thread_limit = Semaphore(self.config.docker['thread_limit'])
        self._node_invalidation_lock = Lock()
        self._info_style = self.detect_info_style()

    def detect_info_style(self):
        info = None
        # try receiving swarm mode style info
        with self.thread_limit:
            try:
                info = self.client.nodes()
            except:
                pass
        if info:
            print('info style: swarm mode.')
            print('The built-in swarm mode of docker-engine is NOT supported by Curious Containers.', file=sys.stderr)
            print('Use the standalone version of Docker Swarm instead.', file=sys.stderr)
            print('See the documentation for more information.', file=sys.stderr)
            exit(1)
        # recieve swarm classic style info
        with self.thread_limit:
            info = self.client.info()
        if info.get('SystemStatus'):
            print('info style: swarm classic.')
            return self._swarm_classic_info_style
        # fallback to local docker-engine instead swarm
        print('info style: local docker-engine.')
        return self._local_docker_engine_info_style

    def _update_node_status(self, node):
        if node.get('status', 'healthy') != 'healthy':
            return

        is_dead = False
        node_name = node['name']
        container_name = 'inspect_{}'.format(node_name)
        reason = None
        try:
            self._remove_container(container_name)
            self._create_inspection_container(container_name, node_name)
            self._start_container(container_name)
            self._wait_for_container(container_name)
        except (ReadTimeout, APIError):
            is_dead = True
            reason = format_exc()

        if not is_dead:
            containers = self._list_containers()
            for container in containers:
                if container['Names'][0].split('/')[1] == container_name:
                    if '0' not in container['Status']:
                        is_dead = True
                        reason = container['Status']
                    break

        self._remove_container(container_name)

        if is_dead:
            self.mongo.db['dead_nodes'].update_one(
                {'name': node_name},
                {'$set': {'name': node_name, 'reason': reason}},
                upsert=True
            )
        else:
            resurrected_nodes = self.mongo.db['dead_nodes'].find({'name': node_name}, {'_id': 1})
            for resurrected_node in resurrected_nodes:
                self.mongo.db['dead_nodes'].delete_one({'_id': resurrected_node['_id']})

    def update_nodes_status(self):
        if not self.config.defaults['error_handling'].get('dead_node_invalidation'):
            return
        if self._node_invalidation_lock.locked():
            return
        with self._node_invalidation_lock:
            print('Update nodes status...')
            nodes = self._info_style()
            threads = []
            for node in nodes:
                t = Thread(target=self._update_node_status, args=(node,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
            print('Dead nodes:')
            pprint(list(self.mongo.db['dead_nodes'].find({}, {'name': 1})))

    def _filter_dead_nodes(self, nodes):
        result = []
        for node in nodes:
            if node.get('status', 'healthy') != 'healthy':
                continue
            dead_node = self.mongo.db['dead_nodes'].find_one(
                {'name': node['name']},
                {'_id': 1}
            )
            if dead_node:
                continue
            result.append(node)
        return result

    def _swarm_classic_info_style(self):
        with self.thread_limit:
            info = self.client.info()
        nodes = []
        anchor = '└'
        last_line = None
        is_node_data = False
        for l in info['SystemStatus']:
            key = l[0]
            val = l[1]
            if anchor in key:
                if not is_node_data:
                    is_node_data = True
                    nodes.append({
                        'name': last_line[0].strip()
                    })
                key = key.strip().lstrip(anchor).strip()
                if key == 'Reserved CPUs':
                    reserved_cpus, total_cpus = [v.strip() for v in val.split('/')]
                    nodes[-1]['reserved_cpus'] = int(reserved_cpus)
                    nodes[-1]['total_cpus'] = int(total_cpus)
                elif key == 'Reserved Memory':
                    vals = val.split()
                    nodes[-1]['reserved_ram'] = _to_mib(float(vals[0]), vals[1])
                    nodes[-1]['total_ram'] = _to_mib(float(vals[3]), vals[4])
                elif key == 'Status':
                    nodes[-1]['status'] = val.lower()
            else:
                is_node_data = False
                last_line = l
        return nodes

    def _local_docker_engine_info_style(self):
        with self.thread_limit:
            info = self.client.info()

        application_containers = self.mongo.db['application_containers'].find({
            'state': {'$nin': end_states()},
        }, {'task_id': 1})

        data_containers = self.mongo.db['data_containers'].find({
            'state': {'$nin': end_states()},
        }, {'_id': 1})

        tasks = self.mongo.db['tasks'].find({
            '_id': {'$in': [application_container['task_id'] for application_container in application_containers]}
        }, {'application_container_description': 1})

        reserved_ram = sum([task['application_container_description']['container_ram'] for task in tasks])
        reserved_ram += len(list(data_containers)) * self.config.defaults['data_container_description']['container_ram']

        return [{
            'name': 'local',
            'total_ram': info['MemTotal'] // (1024 * 1024),
            'reserved_ram': reserved_ram,
            'total_cpus': info['NCPU'],
            'reserved_cpus': None
        }]

    @handle_errors()
    def update_image(self, image, registry_auth):
        errors = Queue()
        if self.config.docker.get('pull_timeout'):
            t = Thread(target=self._update_image, args=(image, registry_auth, errors))
            t.start()
            t.join(timeout=self.config.docker['pull_timeout'])
            if t.is_alive():
                raise Exception('Pull timeout.')
        else:
            self._update_image(image, registry_auth, errors)
        try:
            e = errors.get(block=False)
            raise e
        except Empty:
            pass

    def _update_image(self, image, registry_auth, errors):
        with self.thread_limit:
            for line in self.client.pull(image, stream=True, auth_config=registry_auth):
                line = str(line)
                if self.config.server.get('debug'):
                    print(line)
                if 'error' in line.lower():
                    errors.put(Exception(line))
                    return

    @handle_errors()
    def list_containers(self):
        return self._list_containers()

    def _list_containers(self):
        with self.thread_limit:
            return self.client.containers(quiet=False, all=True, limit=-1)

    @handle_errors()
    def remove_container(self, _id):
        self._remove_container(_id)

    def _remove_container(self, _id):
        try:
            with self.thread_limit:
                self.client.kill(str(_id))
        except:
            pass
        try:
            with self.thread_limit:
                self.client.remove_container(str(_id))
        except:
            pass

    @handle_errors()
    def wait_for_container(self, _id):
        self._wait_for_container(_id)

    def _wait_for_container(self, _id):
        with self.thread_limit:
            self.client.wait(str(_id))

    @handle_errors()
    def logs_from_container(self, _id):
        self._logs_from_container(_id)

    def _logs_from_container(self, _id):
        with self.thread_limit:
            return self.client.logs(str(_id)).decode("utf-8")

    @handle_errors()
    def start_container(self, _id):
        self._start_container(_id)

    def _start_container(self, _id):
        with self.thread_limit:
            self.client.start(str(_id))

    @handle_errors()
    def get_ip(self, _id):
        if self.config.docker.get('net'):
            return str(_id)
        container = self.client.inspect_container(str(_id))
        return container['NetworkSettings']['Networks']['bridge']['IPAddress']

    def _create_inspection_container(self, container_name, node_name):
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

        with self.thread_limit:
            self.client.create_container(
                name=container_name,
                image=self.config.defaults['data_container_description']['image'],
                command=command,
                environment=['constraint:node=={}'.format(node_name)]
            )

        if self.config.docker.get('net'):
            with self.thread_limit:
                self.client.connect_container_to_network(
                    container=str(container_name),
                    net_id=self.config.docker['net']
                )

    @handle_errors()
    def create_application_container(self, application_container_id):
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

        host_config = self.client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit,
            security_opt=security_opt
        )

        with self.thread_limit:
            self.client.create_container(
                name=str(application_container_id),
                image=task['application_container_description']['image'],
                host_config=host_config,
                command=command,
                environment=['constraint:node=={}'.format(application_container['cluster_node'])]
            )

        if self.config.docker.get('net'):
            with self.thread_limit:
                self.client.connect_container_to_network(
                    container=str(application_container_id),
                    net_id=self.config.docker['net']
                )

    @handle_errors()
    def create_data_container(self, data_container_id):
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

        host_config = self.client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit
        )

        with self.thread_limit:
            self.client.create_container(
                name=str(data_container_id),
                image=self.config.defaults['data_container_description']['image'],
                host_config=host_config,
                command=command,
                environment=['constraint:node=={}'.format(data_container['cluster_node'])]
            )

        if self.config.docker.get('net'):
            with self.thread_limit:
                self.client.connect_container_to_network(
                    container=str(data_container_id),
                    net_id=self.config.docker['net']
                )

    @handle_errors()
    def nodes(self):
        return self._filter_dead_nodes(self._info_style())


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
