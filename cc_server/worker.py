import json
import os
from queue import Queue
from threading import Thread
from stance import Stance

from cc_commons.database import Mongo
from cc_commons.states import state_to_index
from cc_commons.tee import Tee

from cc_server.states import StateHandler
from cc_server.cluster import Cluster
from cc_server.scheduling import Scheduler


def _put(q):
    try:
        q.put_nowait(None)
    except:
        pass


class Worker:
    def __init__(self, config):
        self._config = config
        self._tee = None
        self._mongo = None
        self._state_handler = None
        self._cluster = None
        self._scheduler = None

        self._scheduling_q = None
        self._data_container_callback_q = None

    def late_init(self):
        s = Stance(Tee, port=self._config.ipc['tee_port'], secret=self._config.ipc['secret'])
        tee = s.register(config=self._config)
        if s.created_new_instance():
            print('| tee    | PID: {} | STARTED     | in worker |'.format(tee.getpid()))
            raise(Exception('Tee should have been started in main.'))
        else:
            print('| tee    | PID: {} | CONNECTED   | in worker |'.format(tee.getpid()))
        self._tee = tee.tee

        self._tee('Loaded TOML config from {}'.format(self._config.conf_file_path))

        self._mongo = Mongo(
            config=self._config
        )

        self._mongo.db['dead_nodes'].drop()

        self._state_handler = StateHandler(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo
        )
        self._cluster = Cluster(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo,
            state_handler=self._state_handler
        )
        self._scheduler = Scheduler(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo,
            state_handler=self._state_handler,
            cluster=self._cluster
        )

        self._scheduling_q = Queue(maxsize=1)
        self._data_container_callback_q = Queue(maxsize=1)

        self._tee('Pulling data container image...')
        self._cluster.update_data_container_image(self._config.defaults['data_container_description']['image'])

        self._tee('Cluster nodes:')
        self._tee(json.dumps(self._cluster.nodes(), indent=4))

        Thread(target=self._scheduling_loop).start()
        _put(self._scheduling_q)

    def getpid(self):
        return os.getpid()

    def _container_callback(self):
        self._cluster.clean_up_unused_data_containers()
        _put(self._scheduling_q)

    def container_callback(self):
        Thread(target=self._container_callback).start()

    def update_node_status(self, node_name):
        Thread(target=self._cluster.update_node_status, args=(node_name,)).start()

    def nodes(self):
        return self._cluster.nodes()

    def get_ip(self, container_id, collection):
        return self._cluster.get_ip(container_id, collection)

    def _update_images(self):
        application_containers = list(self._mongo.db['application_containers'].find(
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
            task = self._mongo.db['tasks'].find_one({'_id': task_id[0]})
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
                t = Thread(target=self._cluster.update_application_container_image, args=(
                    node_name, image, ra
                ))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()

    def _create_containers(self):
        application_containers = self._mongo.db['application_containers'].find(
            {'state': state_to_index('created')},
            {'_id': 1}
        )
        data_containers = self._mongo.db['data_containers'].find(
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
        self._tee('Scheduled:\n{}\tApplication Containers\n{}\tData Containers'.format(i, j))

    def _scheduling_loop(self):
        while True:
            self._scheduling_q.get()

            self._cluster.clean_up_containers()
            self._state_handler.update_task_groups()
            self._scheduler.schedule()
            self._update_images()
            self._create_containers()

    def schedule(self):
        _put(self._scheduling_q)

    def _cluster_start_application_container(self, application_container_id):
        self._check_data_container_dependencies(application_container_id)
        application_container = self._mongo.db['application_containers'].find_one(
            {'_id': application_container_id, 'state': state_to_index('processing')},
            {'_id': 1}
        )
        if application_container:
            self._cluster.start_container(application_container_id, 'application_containers')

    def _cluster_create_application_container(self, application_container_id):
        self._cluster.create_container(application_container_id, 'application_containers')
        Thread(target=self._cluster_start_application_container, args=(application_container_id,)).start()

    def _cluster_create_data_container(self, data_container_id):
        self._cluster.create_container(data_container_id, 'data_containers')
        Thread(target=self._cluster.start_container, args=(data_container_id, 'data_containers')).start()

    def data_container_callback(self):
        _put(self._data_container_callback_q)

    def _data_container_callback(self):
        while True:
            self._data_container_callback_q.get()
            clean_up = False
            data_containers = self._mongo.db['data_containers'].find(
                {'state': state_to_index('processing')}
            )
            for data_container in data_containers:
                # find depending jobs
                application_containers = self._mongo.db['application_containers'].find(
                    {
                        'state': state_to_index('waiting'),
                        'data_container_ids': data_container['_id']
                    }, {'_id': 1}
                )
                num_depending_jobs = 0
                for application_container in application_containers:
                    num_depending_jobs += 1
                    Thread(
                        target=self._cluster_start_application_container,
                        args=(application_container['_id'],)
                    ).start()
                if num_depending_jobs == 0:
                    clean_up = True
            if clean_up:
                Thread(target=self._cluster.clean_up_unused_data_containers).start()

    def _check_data_container_dependencies(self, application_container_id):
        application_container = self._mongo.db['application_containers'].find_one(
            {'_id': application_container_id, 'state': state_to_index('waiting')},
            {'data_container_ids': 1}
        )
        if not application_container:
            return

        data_containers = list(self._mongo.db['data_containers'].find(
            {'_id': {'$in': application_container['data_container_ids']}, 'state': state_to_index('processing')}
        ))

        if len(data_containers) < len(application_container['data_container_ids']):
            return

        description = 'All data containers for application container ready.'
        self._state_handler.transition('application_containers', application_container_id, 'processing', description)
