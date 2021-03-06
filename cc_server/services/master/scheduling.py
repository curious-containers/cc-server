from cc_server.commons.helper import generate_secret
from cc_server.commons.states import end_states
from cc_server.services.master.scheduling_strategies.task_selection import FIFO
from cc_server.services.master.scheduling_strategies.caching import OneCachePerTaskNoDuplicates
from cc_server.services.master.scheduling_strategies.container_allocation import binpack, spread


def application_container_prototype(container_ram):
    return {
        'state': -1,
        'created_at': None,
        'transitions': [],
        'username': None,
        'task_id': None,
        'data_container_ids': [],
        'callbacks': [],
        'callback_key': generate_secret(),
        'cluster_node': None,
        'container_ram': container_ram
    }


class Scheduler:
    def __init__(self, config, tee, mongo, state_handler, cluster):
        self._config = config
        self._tee = tee
        self._mongo = mongo
        self._state_handler = state_handler
        self._cluster = cluster

        # scheduling strategies
        if config.defaults['scheduling_strategies']['container_allocation'] == 'spread':
            container_allocation = spread
        elif config.defaults['scheduling_strategies']['container_allocation'] == 'binpack':
            container_allocation = binpack
        self._container_allocation = container_allocation
        self._task_selection = FIFO(mongo=self._mongo)
        self._caching = OneCachePerTaskNoDuplicates(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo,
            cluster=self._cluster
        )

    def schedule(self):
        dc_ram = self._config.defaults['data_container_description']['container_ram']

        nodes_list = self._mongo.db['nodes'].find(
            {'is_online': True},
            {'cluster_node': 1, 'total_ram': 1}
        )

        nodes = {}

        for node in nodes_list:
            node_name = node['cluster_node']
            application_containers = list(self._mongo.db['application_containers'].find({
                'state': {'$nin': end_states()},
                'cluster_node': node_name
            }, {
                'container_ram': 1
            }))
            data_containers = list(self._mongo.db['data_containers'].find({
                'state': {'$nin': end_states()},
                'cluster_node': node_name
            }, {
                'container_ram': 1
            }))

            reserved_dc_ram = [c['container_ram'] for c in data_containers]
            reserved_ac_ram = [c['container_ram'] for c in application_containers]

            node['reserved_ram'] = sum(reserved_dc_ram + reserved_ac_ram)
            node['free_ram'] = node['total_ram'] - node['reserved_ram']

            nodes[node_name] = node

        for task in self._task_selection:
            ac_ram = task['application_container_description']['container_ram']
            required_dc_ram = dc_ram
            if task.get('no_cache'):
                required_dc_ram = 0

            if not _is_task_fitting(nodes, ac_ram, required_dc_ram):
                description = 'Task is too large for cluster.'
                self._state_handler.transition('tasks', task['_id'], 'failed', description)
                continue

            application_container = application_container_prototype(ac_ram)
            application_container['task_id'] = [task['_id']]
            application_container['username'] = task['username']
            application_container_id = self._mongo.db['application_containers'].insert_one(application_container).inserted_id

            if not task.get('no_cache'):
                self._caching.apply(application_container_id)

            data_containers = self._mongo.db['data_containers'].find(
                {'state': -1},
                {'_id': 1, 'cluster_node': 1}
            )

            assign_to_node = []
            for data_container in data_containers:
                if not data_container['cluster_node']:
                    assign_to_node.append((dc_ram, data_container['_id'], 'data_containers'))
            assign_to_node.append((ac_ram, application_container_id, 'application_containers'))
            assign_to_node.sort(reverse=True)

            failed = False

            for ram, _id, collection in assign_to_node:
                node_name = self._container_allocation(nodes, ram)
                if not node_name:
                    failed = True
                    break
                self._mongo.db[collection].update_one(
                    {'_id': _id},
                    {'$set': {'cluster_node': node_name}}
                )
                nodes[node_name]['free_ram'] -= ram

            if failed:
                for ram, _id, collection in assign_to_node:
                    self._mongo.db[collection].delete_one({'_id': _id})
                break

            for ram, _id, collection in assign_to_node:
                description = 'Container created.'
                self._state_handler.transition(collection, _id, 'created', description)


def _is_task_fitting(nodes, ac_ram, dc_ram):
    first_ram = max(ac_ram, dc_ram)
    second_ram = min(ac_ram, dc_ram)

    is_first_fitting = False
    is_second_fitting = False

    for name, node in nodes.items():
        node_ram = node['total_ram']
        if not is_first_fitting and first_ram <= node_ram:
            is_first_fitting = True
            node_ram -= first_ram
        if not is_second_fitting and second_ram <= node_ram:
            is_second_fitting = True
        if is_first_fitting and is_second_fitting:
            return True
    return False
