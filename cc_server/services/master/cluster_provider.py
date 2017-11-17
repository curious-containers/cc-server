import json
import docker
from queue import Queue
from threading import Semaphore, Thread


class ClusterProviderException(Exception):
    pass


class DockerClientProxy:
    def __init__(self, config, tee, node_name, node_config):
        self._config = config
        self._tee = tee

        self.node_name = node_name
        self.node_config = node_config

        self._thread_limit = Semaphore(self._config.docker['thread_limit'])

        tls = False
        if self.node_config.get('tls'):
            tls = docker.tls.TLSConfig(**self.node_config['tls'])

        try:
            client_class = docker.APIClient
        except AttributeError:
            client_class = docker.Client
            self._tee('Node {}: Fallback to old docker-py Client.'.format(self.node_name))

        self.client = client_class(
            base_url=self.node_config['base_url'],
            tls=tls,
            timeout=self._config.docker.get('api_timeout'),
            version='auto'
        )

    def info(self):
        with self._thread_limit:
            info = self.client.info()

        return {
            'cluster_node': self.node_name,
            'total_ram': info['MemTotal'] // (1024 * 1024),
            'total_cpus': info['NCPU']
        }

    def inspect(self):
        self._tee('Inspect node {}.'.format(self.node_name))

        self.update_image(
            self._config.defaults['inspection_container_description']['image'],
            self._config.defaults['inspection_container_description'].get('registry_auth')
        )

        container_name = 'inspect-{}'.format(self.node_name)

        self.remove_container(container_name)
        self._create_inspection_container(container_name)
        self.start_container(container_name)
        self.wait_for_container(container_name)

        for key, val in self.containers().items():
            if key == container_name:
                if val['exit_status'] != 0:
                    s = 'Inspection container on node {} exited with code {}: {}'.format(
                        self.node_name, val['exit_status'], val['description']
                    )
                    raise ClusterProviderException(s)
                break

        self.remove_container(container_name)

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

    def create_network(self):
        network_name = self._config.docker.get('net')
        if network_name:
            networks = self.client.networks(names=[network_name])
            if not networks:
                self._tee('Create net {} via node {}.'.format(network_name, self.node_name))
                self.client.create_network(network_name, driver='overlay')

    def create_container(self, *args, **kwargs):
        container_name = kwargs['name']
        containers = self.containers()
        if container_name in containers:
            self.remove_container(container_name)

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
        with self._thread_limit:
            self._tee('Pull image {} on node {}.'.format(image, self.node_name))
            for line in self.client.pull(image, stream=True, auth_config=registry_auth):
                line = str(line)
                if 'error' in line.lower():
                    raise ClusterProviderException(line)

    def _create_inspection_container(self, container_name):
        settings = {
            'inspection_url': '{}'.format(self._config.server_web['external_url'].rstrip('/'))
        }

        entry_point = self._config.defaults['inspection_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        self.create_container(
            name=container_name,
            image=self._config.defaults['inspection_container_description']['image'],
            command=command
        )

        if self._config.docker.get('net'):
            self.connect_container_to_network(
                str(container_name),
                net_id=self._config.docker['net']
            )


class DockerProvider:
    def __init__(self, config, tee, mongo):
        self._tee = tee
        self._mongo = mongo
        self._config = config

        self._clients = {}

    def logs_from_container(self, node_name, container_id):
        return self._clients[node_name].logs_from_container(container_id)

    def node_info(self, node_name):
        return self._clients[node_name].info()

    def update_node(self, node_name, node_config, startup):
        if not node_config:
            if node_name in self._clients:
                del self._clients[node_name]
            raise Exception('Could not find config for node {}.'.format(node_name))

        try:
            node = self._clients[node_name]
            if not startup:
                node.inspect()
            info = node.info(node_name)
        except:
            if node_name in self._clients:
                del self._clients[node_name]
            node = DockerClientProxy(
                config=self._config,
                tee=self._tee,
                node_name=node_name,
                node_config=node_config
            )
            if not startup:
                node.inspect()
            info = node.info()

        self._clients[node_name] = node
        return info

    def get_ip(self, node_name, container_id):
        return self._clients[node_name].get_ip(container_id)

    def create_network(self):
        if not self._clients:
            return
        node_name = list(self._clients)[0]
        client = self._clients[node_name]
        client.create_network()

    def wait_for_container(self, node_name, container_id):
        self._clients[node_name].wait_for_container(container_id)

    def start_container(self, node_name, container_id):
        self._clients[node_name].start_container(container_id)

    def create_container(self, container_id, collection):
        if collection == 'application_containers':
            self._create_application_container(container_id)
        elif collection == 'data_containers':
            self._create_data_container(container_id)
        else:
            raise ClusterProviderException('Collection {} not valid.', collection)

    def remove_container(self, node_name, container_id):
        try:
            self._clients[node_name].remove_container(container_id)
        except:
            pass

    def update_image(self, node_name, image, registry_auth):
        self._clients[node_name].update_image(image, registry_auth)

    def _create_application_container(self, application_container_id):
        application_container = self._mongo.db['application_containers'].find_one({'_id': application_container_id})
        task_id = application_container['task_id'][0]
        task = self._mongo.db['tasks'].find_one({'_id': task_id})

        settings = {
            'container_id': str(application_container_id),
            'callback_key': application_container['callback_key'],
            'callback_url': '{}/application-containers/callback'.format(self._config.server_web['external_url'].rstrip('/'))
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
                str(application_container_id),
                net_id=self._config.docker['net']
            )

    def _create_data_container(self, data_container_id):
        data_container = self._mongo.db['data_containers'].find_one({'_id': data_container_id})

        settings = {
            'container_id': str(data_container_id),
            'callback_key': data_container['callback_key'],
            'callback_url': '{}/data-containers/callback'.format(self._config.server_web['external_url'].rstrip('/')),
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
                str(data_container_id),
                net_id=self._config.docker['net']
            )

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
            containers = self._clients[node_name].containers()
            q.put(containers)
        except:
            self._tee('Error on container list for node {}.'.format(node_name))


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
