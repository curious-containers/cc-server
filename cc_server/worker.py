from threading import Lock, Thread

from cc_server.states import state_to_index


class Worker:
    def __init__(self, mongo, cluster, scheduler, state_handler):
        self.cluster = cluster
        self.mongo = mongo
        self.scheduler = scheduler
        self.state_handler = state_handler
        self.post_task_lock = Lock()
        self.post_data_container_callback_lock = Lock()
        self.scheduling_thread_count_lock = Lock()
        self.scheduling_thread_count = 0

    def _check_thread_count(self):
        with self.scheduling_thread_count_lock:
            if self.scheduling_thread_count < 2:
                self.scheduling_thread_count += 1
                return True
            return False

    def _decrement_thread_count(self):
        with self.scheduling_thread_count_lock:
            self.scheduling_thread_count -= 1

    def post_container_callback(self):
        self.cluster.clean_up_finished_containers()
        self.cluster.clean_up_unused_data_containers()
        self.post_task()

    def update_images(self):
        application_containers = self.mongo.db['application_containers'].find(
            {'state': state_to_index('created')},
            {'task_id': 1}
        )
        task_ids = [ac['task_id'][0] for ac in application_containers]
        tasks = self.mongo.db['tasks'].find({'_id': {'$in': task_ids}})
        images = {
            task['application_container_description']['image']:
            task['application_container_description'].get('registry_auth')
            for task in tasks}
        threads = []
        for image, registry_auth in images.items():
            t = Thread(target=self.cluster.update_application_container_image, args=(image, registry_auth))
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

        print('-------- Scheduled --------\n{}\tApplication Containers\n{}\tData Containers'.format(i, j))

    def post_task(self):
        if not self._check_thread_count():
            return
        with self.post_task_lock:

            self.cluster.clean_up_exited_containers()
            self.state_handler.update_task_groups()
            self.scheduler.schedule()
            self.update_images()
            self.create_containers()

            self._decrement_thread_count()

    def _cluster_start_application_container(self, application_container_id):
        self._check_data_container_dependencies(application_container_id)
        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id, 'state': state_to_index('processing')},
            {'_id': 1}
        )
        if application_container:
            self.cluster.start_application_container(application_container_id)

    def _cluster_create_application_container(self, application_container_id):
        self.cluster.create_application_container(application_container_id)
        Thread(target=self._cluster_start_application_container, args=(application_container_id,)).start()

    def _cluster_create_data_container(self, data_container_id):
        self.cluster.create_data_container(data_container_id)
        Thread(target=self.cluster.start_data_container, args=(data_container_id,)).start()

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

