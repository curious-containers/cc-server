import sys
import docker
import json
from threading import Semaphore

from cc_server.states import end_states


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
        reserved_ram += len(list(data_containers)) * self.config.defaults['container_description']['container_ram']

        return [{
            'name': 'local',
            'total_ram': info['MemTotal'] // (1024 * 1024),
            'reserved_ram': reserved_ram,
            'total_cpus': info['NCPU'],
            'reserved_cpus': None
        }]

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

    def nodes(self):
        return self._info_style()


def _to_mib(val, unit):
    if unit == 'B':
        return val // (1024 * 1024)
    if unit == 'KiB':
        return val // 1024
    if unit == 'GiB':
        return val * 1024
    return val
