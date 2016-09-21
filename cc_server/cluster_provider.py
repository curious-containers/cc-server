import docker
import json
from threading import Semaphore, Thread
from psutil import virtual_memory
from queue import Queue
from uuid import uuid4


class DockerProvider:
    def __init__(self, mongo, config):
        self.mongo = mongo
        self.config = config

        tls = False
        if self.config.docker.get('tls'):
            tls = docker.tls.TLSConfig(**self.config.docker['tls'])

        self.client = docker.Client(
            base_url=self.config.docker['base_url'],
            tls=tls
        )

        self.thread_limit = Semaphore(self.config.docker['thread_limit'])

    def update_image(self, image, registry_auth):
        with self.thread_limit:
            for line in self.client.pull(image, stream=True, auth_config=registry_auth):
                line = str(line)
                if 'Error' in line:
                    raise(Exception(line))

    def list_containers(self):
        with self.thread_limit:
            return self.client.containers(quiet=False, all=True, limit=-1)

    def remove_container(self, _id):
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

    def wait_for_container(self, _id):
        with self.thread_limit:
            self.client.wait(str(_id))

    def logs_from_container(self, _id):
        with self.thread_limit:
            return self.client.logs(str(_id))

    def start_container(self, _id):
        with self.thread_limit:
            self.client.start(str(_id))

    def get_ip(self, _id):
        if self.config.docker.get('net'):
            return str(_id)
        container = self.client.inspect_container(str(_id))
        return container['NetworkSettings']['Networks']['bridge']['IPAddress']

    def create_inspection_container(self, name, node):
        settings = {
            'container_type': 'inspection'
        }

        entry_point = self.config.defaults['container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        with self.thread_limit:
            self.client.create_container(
                name=name,
                image=self.config.defaults['container_description']['image'],
                command=command,
                environment=['constraint:node=={}'.format(node)]
            )

    def create_application_container(self, application_container_id):
        application_container = self.mongo.db['application_containers'].find_one({'_id': application_container_id})
        task_id = application_container['task_id']
        task = self.mongo.db['tasks'].find_one({'_id': task_id})

        settings = {
            'container_id': str(application_container_id),
            'container_type': 'application',
            'callback_key': application_container['callback_key'],
            'callback_url': '{}/application-containers/callback'.format(self.config.server['host'].rstrip('/')),
            'result_files': task['result_files'],
            'mtu': self.config.defaults.get('mtu'),
            'no_cache': task.get('no_cache'),
            'parameters': task['application_container_description'].get('parameters')
        }

        entry_point = self.config.defaults['container_description']['entry_point']
        if task['application_container_description'].get('entry_point'):
            entry_point = task['application_container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        #print('application_container', command)

        privileged = False
        if self.config.defaults.get('mtu'):
            privileged = True

        mem_limit = '{}MB'.format(task['application_container_description']['container_ram'])

        host_config = self.client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit,
            privileged=privileged
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

    def create_data_container(self, data_container_id):
        data_container = self.mongo.db['data_containers'].find_one({'_id': data_container_id})

        settings = {
            'container_id': str(data_container_id),
            'container_type': 'data',
            'callback_key': data_container['callback_key'],
            'callback_url': '{}/data-containers/callback'.format(self.config.server['host'].rstrip('/')),
            'input_files': data_container['input_files'],
            'mtu': self.config.defaults.get('mtu')
        }

        entry_point = self.config.defaults['container_description']['entry_point']

        command = '{} \'{}\''.format(
            entry_point,
            json.dumps(settings)
        )

        #print('data_container', command)

        privileged = False
        if self.config.defaults.get('mtu'):
            privileged = True

        mem_limit = '{}MB'.format(self.config.defaults['container_description']['container_ram'])

        host_config = self.client.create_host_config(
            mem_limit=mem_limit,
            memswap_limit=mem_limit,
            privileged=privileged
        )

        with self.thread_limit:
            self.client.create_container(
                name=str(data_container_id),
                image=self.config.defaults['container_description']['image'],
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

    def _run_inspection_container(self, node, q):
        _id = uuid4()
        try:
            self.create_inspection_container(_id, node)
            self.start_container(_id)
            self.wait_for_container(_id)
            logs = self.logs_from_container(_id)
            result = json.loads(logs.decode("utf-8"))
            result['name'] = node
        except:
            result = {
                'name': node,
                'total_ram': 0,
                'reserved_ram': 0,
                'total_cpus': 0,
                'reserved_cpus': 0
            }
        Thread(target=self.remove_container, args=(_id,)).start()
        q.put(result)

    def _run_inspection_containers(self, info):
        q = Queue()
        threads = []
        for node in info:
            t = Thread(target=self._run_inspection_container, args=(node['ID'], q))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        nodes = list(q.queue)
        return nodes

    def nodes(self):
        return self._info()

    def _info(self):
        info = None

        # try receiving swarm mode style info
        with self.thread_limit:
            try:
                info = self.client.nodes()
            except:
                pass
        if info:
            print('info style: swarm mode.')
            raise Exception('The built-in swarm mode of docker-engine is NOT supported by Curious Containers.\n\
            Use the standalone version of Docker Swarm instead.\n\
            See the documentation for more information.')

        # recieve swarm classic style info
        with self.thread_limit:
            info = self.client.info()
        if info.get('SystemStatus'):
            print('info style: swarm classic.')
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
                else:
                    is_node_data = False
                    last_line = l
            return nodes

        # fallback to local docker-engine instead swarm
        print('info style: local docker-engine.')
        ram = virtual_memory()
        return [{
            'name': 'local',
            'total_ram': ram.total // (1024 * 1024),
            'reserved_ram': (ram.total - ram.available) // (1024 * 1024),
            'total_cpus': info['NCPU'],
            'reserved_cpus': None
        }]


def _to_mib(val, unit):
    if unit == 'B':
        return val // (1024 * 1024)
    if unit == 'KiB':
        return val // 1024
    if unit == 'GiB':
        return val * 1024
    return val
