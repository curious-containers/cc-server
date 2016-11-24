from cc_server.helper import generate_secret


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
        'telemetry': None,
        'cluster_node': None,
        'container_ram': container_ram
    }


class Scheduler:
    def __init__(self, mongo, cluster, config, state_handler, container_allocation, task_selection, caching):
        self.mongo = mongo
        self.cluster = cluster
        self.config = config
        self.state_handler = state_handler

        # scheduling strategies
        self.container_allocation = container_allocation
        self.task_selection = task_selection
        self.caching = caching

    def schedule(self):
        dc_ram = self.config.defaults['data_container_description']['container_ram']

        nodes = {node['name']: node for node in self.cluster.nodes()}
        for name, node in nodes.items():
            node['free_ram'] = node['total_ram'] - node['reserved_ram']

        for task in self.task_selection:
            ac_ram = task['application_container_description']['container_ram']
            if not _is_task_fitting(nodes, ac_ram, dc_ram):
                description = 'Task is too large for cluster.'
                self.state_handler.transition('tasks', task['_id'], 'failed', description)
                continue

            application_container = application_container_prototype(ac_ram)
            application_container['task_id'] = [task['_id']]
            application_container['username'] = task['username']
            application_container_id = self.mongo.db['application_containers'].insert_one(application_container).inserted_id

            if not task.get('no_cache'):
                self.caching.apply(application_container_id)

            data_containers = self.mongo.db['data_containers'].find(
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
                cluster_node = self.container_allocation(nodes, ram)
                if not cluster_node:
                    failed = True
                    break
                self.mongo.db[collection].update_one(
                    {'_id': _id},
                    {'$set': {'cluster_node': cluster_node}}
                )
                nodes[cluster_node]['free_ram'] -= ram

            if failed:
                for ram, _id, collection in assign_to_node:
                    self.mongo.db[collection].delete_one({'_id': _id})
                break

            for ram, _id, collection in assign_to_node:
                description = 'Container created.'
                self.state_handler.transition(collection, _id, 'created', description)


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
