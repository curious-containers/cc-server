from queue import Queue
from threading import Thread
from time import sleep

from cc_commons.states import state_to_index, end_states


def _put(q):
    try:
        q.put_nowait(None)
    except:
        pass


class Worker:
    def __init__(self, config, tee, mongo, state_handler, cluster, scheduler):
        self._config = config
        self._tee = tee
        self._mongo = mongo
        self._state_handler = state_handler
        self._cluster = cluster
        self._scheduler = scheduler

        self._scheduling_q = Queue(maxsize=1)
        self._data_container_callback_q = Queue(maxsize=1)

        # initialize permanent threads
        Thread(target=self._scheduling_loop).start()
        Thread(target=self._data_container_callback_loop).start()

        if self._config.server_master.get('scheduling_interval_seconds'):
            Thread(target=self._cron).start()

    def _cron(self):
        while True:
            work_to_do = False
            task = self._mongo.db['tasks'].find_one(
                {'state': {'$nin': end_states()}},
                {'_id': 1}
            )
            if task:
                work_to_do = True
            else:
                application_container = self._mongo.db['application_containers'].find_one(
                    {'state': {'$nin': end_states()}},
                    {'_id': 1}
                )
                if application_container:
                    work_to_do = True
                else:
                    data_container = self._mongo.db['data_containers'].find_one(
                        {'state': {'$nin': end_states()}},
                        {'_id': 1}
                    )
                    if data_container:
                        work_to_do = True

            if work_to_do:
                _put(self._scheduling_q)
                _put(self._data_container_callback_q)

            sleep(self._config.server_master['scheduling_interval_seconds'])

    def _container_callback(self):
        self._cluster.clean_up_unused_data_containers()
        _put(self._scheduling_q)

    def container_callback(self):
        Thread(target=self._container_callback).start()

    def update_node(self, node_name):
        Thread(target=self._cluster.update_node, args=(node_name,)).start()

    def _update_images(self):
        application_containers = list(self._mongo.db['application_containers'].find(
            {'state': state_to_index('created')},
            {'task_id': 1, 'cluster_node': 1}
        ))
        data_containers = list(self._mongo.db['data_containers'].find(
            {'state': state_to_index('created')},
            {'cluster_node': 1}
        ))

        nodes = {}
        i = j = 0
        for container in application_containers:
            node_name = container['cluster_node']
            nodes[node_name] = set()
            i += 1

        for container in data_containers:
            node_name = container['cluster_node']
            nodes[node_name] = set()
            j += 1

        self._tee('Scheduled:\n{}\tApplication Containers\n{}\tData Containers'.format(i, j))

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

        for data_container in data_containers:
            node_name = data_container['cluster_node']
            registry_auth = None
            if self._config.defaults['data_container_description'].get('registry_auth'):
                ra = self._config.defaults['data_container_description']['registry_auth']
                registry_auth = (ra['username'], ra['password'])
            nodes[node_name].update([(
                self._config.defaults['data_container_description']['image'],
                registry_auth
            )])

        threads = []
        for node_name, node in nodes.items():
            for image, registry_auth in node:
                ra = None
                if registry_auth:
                    ra = {'username': registry_auth[0], 'password': registry_auth[1]}
                t = Thread(target=self._cluster.update_image, args=(
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

        threads = []
        for ac in application_containers:
            t = Thread(target=self._cluster_create_application_container, args=(ac['_id'],))
            threads.append(t)
            t.start()

        for dc in data_containers:
            t = Thread(target=self._cluster_create_data_container, args=(dc['_id'],))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

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

    def _data_container_callback_loop(self):
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

        data_containers = self._mongo.db['data_containers'].find(
            {'_id': {'$in': application_container['data_container_ids']}, 'state': state_to_index('processing')}
        )
        data_container_ids = [data_container['_id'] for data_container in data_containers]

        for data_container_id in application_container['data_container_ids']:
            if data_container_id not in data_container_ids:
                return

        description = 'All data containers for application container ready.'
        self._state_handler.transition('application_containers', application_container_id, 'processing', description)
