import os
import json
import signal
from queue import Queue
from threading import Lock, Thread
from multiprocessing.managers import BaseManager

from cc_server.tee import get_tee
from cc_server.database import Mongo
from cc_server.cluster import Cluster
from cc_server.states import StateHandler, state_to_index
from cc_server.scheduling import Scheduler


def connect(config):
    WorkerManager.register('get_worker')
    m = WorkerManager(address=('', config.ipc['worker_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.connect()
    return m.get_worker()


def start(config):
    worker = Worker(
        config=config
    )
    WorkerManager.register('get_worker', callable=lambda: worker)
    m = WorkerManager(address=('', config.ipc['worker_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.start()
    worker = m.get_worker()
    worker.late_init()
    return worker


def stop(config):
    WorkerManager.register('get_worker')
    m = WorkerManager(address=('', config.ipc['worker_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.connect()
    worker = m.get_worker()
    pid = worker.get_pid()
    os.kill(pid, signal.SIGTERM)


def get_worker(config):
    try:
        worker = connect(config=config)
        print('worker | PID: {} | CONNECTED'.format(worker.get_pid()))
    except:
        worker = start(config=config)
        print('worker | PID: {} | STARTED'.format(worker.get_pid()))
    return worker


class WorkerManager(BaseManager):
    pass


class Worker:
    def __init__(self, config):
        self.config = config
        self.tee = None
        self.mongo = None
        self.state_handler = None
        self.cluster = None
        self.scheduler = None
        self.scheduling_q = None
        self.post_data_container_callback_lock = None

    def late_init(self):
        self.tee = get_tee(self.config)

        self.tee('Loaded TOML config from {}'.format(self.config.conf_file_path))

        self.mongo = Mongo(
            config=self.config
        )

        self.mongo.db['dead_nodes'].drop()

        self.state_handler = StateHandler(
            config=self.config,
            tee=self.tee,
            mongo=self.mongo
        )
        self.cluster = Cluster(
            config=self.config,
            tee=self.tee,
            mongo=self.mongo,
            state_handler=self.state_handler
        )
        self.scheduler = Scheduler(
            config=self.config,
            tee=self.tee,
            mongo=self.mongo,
            state_handler=self.state_handler,
            cluster=self.cluster
        )
        self.post_data_container_callback_lock = Lock()
        self.scheduling_q = Queue(maxsize=1)

        self.tee('Pulling data container image...')
        self.cluster.update_data_container_image(self.config.defaults['data_container_description']['image'])

        self.tee('Cluster nodes:')
        self.tee(json.dumps(self.cluster.nodes(), indent=4))

        Thread(target=self._scheduling_loop).start()
        self._put_scheduling_q()

    def get_pid(self):
        return os.getpid()

    def _put_scheduling_q(self):
        try:
            self.scheduling_q.put_nowait(None)
        except:
            pass

    def post_container_callback(self):
        self.cluster.clean_up_unused_data_containers()
        self._put_scheduling_q()

    def update_node_status(self, node_name):
        self.cluster.update_node_status(node_name)

    def nodes(self):
        return self.cluster.nodes()

    def get_ip(self, container_id, collection):
        return self.cluster.get_ip(container_id, collection)

    def update_images(self):
        application_containers = list(self.mongo.db['application_containers'].find(
            {'state': state_to_index('created')},
            {'task_id': 1, 'cluster_node': 1}
        ))
        nodes = {}
        for application_container in application_containers:
            node_name = application_container['cluster_node']
            nodes[node_name] = set()
        for application_container in application_containers:
            node_name = application_container['cluster_node']
            task_id = application_container['task_id']
            task = self.mongo.db['tasks'].find_one({'_id': task_id[0]})
            registry_auth = None
            if task['application_container_description'].get('registry_auth'):
                ra = task['application_container_description']['registry_auth']
                registry_auth = (ra['username'], ra['password'])
            nodes[node_name].update([(
                task['application_container_description']['image'],
                registry_auth
            )])
        threads = []
        for node_name, node in nodes.items():
            for image, registry_auth in node:
                ra = None
                if registry_auth:
                    ra = {'username': registry_auth[0], 'password': registry_auth[1]}
                t = Thread(target=self.cluster.update_application_container_image, args=(
                    node_name, image, ra
                ))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()

    def create_containers(self):
        application_containers = self.mongo.db['application_containers'].find(
            {'state': state_to_index('created')},
            {'_id': 1}
        )
        data_containers = self.mongo.db['data_containers'].find(
            {'state': state_to_index('created')},
            {'_id': 1}
        )

        i = j = 0
        threads = []
        for ac in application_containers:
            t = Thread(target=self._cluster_create_application_container, args=(ac['_id'],))
            threads.append(t)
            t.start()
            i += 1
        for dc in data_containers:
            t = Thread(target=self._cluster_create_data_container, args=(dc['_id'],))
            threads.append(t)
            t.start()
            j += 1
        for t in threads:
            t.join()
        self.tee('Scheduled:\n{}\tApplication Containers\n{}\tData Containers'.format(i, j))

    def _scheduling_loop(self):
        while True:
            self.scheduling_q.get()

            self.cluster.clean_up_containers()
            self.state_handler.update_task_groups()
            self.scheduler.schedule()
            self.update_images()
            self.create_containers()

    def schedule(self):
        self._put_scheduling_q()

    def _cluster_start_application_container(self, application_container_id):
        self._check_data_container_dependencies(application_container_id)
        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id, 'state': state_to_index('processing')},
            {'_id': 1}
        )
        if application_container:
            self.cluster.start_container(application_container_id, 'application_containers')

    def _cluster_create_application_container(self, application_container_id):
        self.cluster.create_container(application_container_id, 'application_containers')
        Thread(target=self._cluster_start_application_container, args=(application_container_id,)).start()

    def _cluster_create_data_container(self, data_container_id):
        self.cluster.create_container(data_container_id, 'data_containers')
        Thread(target=self.cluster.start_container, args=(data_container_id, 'data_containers')).start()

    def post_data_container_callback(self):
        clean_up = False
        with self.post_data_container_callback_lock:
            data_containers = self.mongo.db['data_containers'].find(
                {'state': state_to_index('processing')}
            )
            for data_container in data_containers:
                # find depending jobs
                application_containers = self.mongo.db['application_containers'].find(
                    {
                        'state': state_to_index('waiting'),
                        'data_container_ids': data_container['_id']
                    }, {'_id': 1}
                )
                num_depending_jobs = 0
                for application_container in application_containers:
                    num_depending_jobs += 1
                    Thread(target=self._cluster_start_application_container, args=(application_container['_id'],)).start()
                if num_depending_jobs == 0:
                    clean_up = True
        if clean_up:
            self.cluster.clean_up_unused_data_containers()

    def _check_data_container_dependencies(self, application_container_id):
        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id, 'state': state_to_index('waiting')},
            {'data_container_ids': 1}
        )
        if not application_container:
            return

        data_containers = list(self.mongo.db['data_containers'].find(
            {'_id': {'$in': application_container['data_container_ids']}, 'state': state_to_index('processing')}
        ))

        if len(data_containers) < len(application_container['data_container_ids']):
            return

        description = 'All data containers for application container ready.'
        self.state_handler.transition('application_containers', application_container_id, 'processing', description)
