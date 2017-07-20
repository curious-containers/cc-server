from time import time

from cc_server.commons.helper import remove_secrets
from cc_server.commons.notification import notify

STATES = [
    'created',
    'waiting',
    'processing',
    'success',          # end state
    'failed',           # end state
    'cancelled'         # end state
]


# public functions
def index_to_state(index):
    return STATES[index]


def end_states():
    return [
        state_to_index('success'),
        state_to_index('failed'),
        state_to_index('cancelled')
    ]


def state_to_index(state):
    for i, s in enumerate(STATES):
        if s == state:
            return i
    raise Exception('Invalid state: %s' % str(state))


def is_state(index, compare_state):
    compare_index = state_to_index(compare_state)
    return index == compare_index


def transition(state, description, exception, caused_by):
    return {
        'timestamp': time(),
        'state': state_to_index(state),
        'description': description,
        'exception': exception,  # optional
        'caused_by': caused_by  # optional
    }


class StateHandler:
    def __init__(self, config, tee, mongo):
        self._config = config
        self._tee = tee
        self._mongo = mongo

    def transition(self, collection, _id, state, description, exception=None):
        if collection == 'tasks':
            self._task_transition(_id, state, description, exception, None)
        elif collection == 'application_containers':
            self._application_container_transition(_id, state, description, exception, None)
        elif collection == 'data_containers':
            self._data_container_transition(_id, state, description, exception, None)
        elif collection == 'task_groups':
            self._task_group_transition(_id, state, description, exception, None)
        else:
            raise Exception('Invalid collection: %s' % collection)

    def _task_group_transition(self, task_group_id, state, description, exception, caused_by):
        task_group = self._mongo.db['task_groups'].find_one(
            {'_id': task_group_id},
            {'state': 1}
        )

        if task_group['state'] in end_states():
            return

        if state_to_index(state) == task_group['state']:
            return

        t = transition(state, description, exception, caused_by)
        self._append_transition('task_groups', task_group_id, t)

    def _application_container_transition(self, application_container_id, state, description, exception, caused_by):
        application_container = self._mongo.db['application_containers'].find_one(
            {'_id': application_container_id},
            {'task_id': 1, 'state': 1}
        )

        if application_container['state'] in end_states():
            return

        t = transition(state, description, exception, caused_by)
        self._append_transition('application_containers', application_container_id, t)

        task_id = application_container['task_id'][0]

        if state == 'created':
            self._task_transition(
                task_id, 'processing', description, None, {'application_container_id': application_container_id}
            )

        elif state == 'failed':
            self._task_transition(
                task_id, 'failed', description, None, {'application_container_id': application_container_id}
            )

        elif state == 'success':
            self._task_transition(
                task_id, 'success', description, None, {'application_container_id': application_container_id}
            )

    def _append_transition(self, collection, _id, t):
        if is_state(t['state'], 'failed'):
            self._tee('{} {} {} {} {}'.format(
                collection, _id, index_to_state(t['state']), t['description'], t.get('exception'))
            )
        else:
            self._tee('{} {} {}'.format(collection, _id, index_to_state(t['state'])))

        if is_state(t['state'], 'created'):
            self._mongo.db[collection].update({'_id': _id}, {
                '$push': {'transitions': t},
                '$set': {
                    'state': t['state'],
                    'created_at': t['timestamp']
                }
            })
        else:
            self._mongo.db[collection].update({'_id': _id}, {
                '$push': {'transitions': t},
                '$set': {'state': t['state']}
            })
        if t['state'] in end_states():
            data = self._mongo.db[collection].find_one({'_id': _id})
            del data['_id']
            data = remove_secrets(data)
            self._mongo.db[collection].update_one({'_id': _id}, {'$set': data})

    def _task_transition(self, task_id, state, description, exception, caused_by):
        task = self._mongo.db['tasks'].find_one(
            {'_id': task_id},
            {'trials': 1, 'notifications': 1, 'state': 1, 'task_group_id': 1}
        )

        if task['state'] in end_states():
            return

        if state == 'failed':
            trials = task['trials'] + 1
            self._mongo.db['tasks'].update_one(
                {'_id': task_id},
                {'$set': {'trials': trials}}
            )
            max_task_trials = self._config.defaults['error_handling']['max_task_trials']

            if trials < max_task_trials:
                state = 'waiting'
                description = 'Task waiting again (trial {} of {}): {}'.format(trials, max_task_trials, description)

        if state == 'cancelled':
            application_containers = self._mongo.db['application_containers'].find({
                'state': {'$nin': end_states()},
                'task_id': task_id
            }, {'_id': 1})

            for application_container in application_containers:
                ac_id = application_container['_id']
                ac_description = 'Application container cancelled: %s' % description
                self._application_container_transition(
                    ac_id, 'cancelled', ac_description, None, {'task_id': task_id}
                )

        t = transition(state, description, exception, caused_by)
        self._append_transition('tasks', task_id, t)

        if state == 'processing':
            task_group = self._mongo.db['task_groups'].find_one(
                {'_id': task['task_group_id'][0], 'state': state_to_index('waiting')},
                {'_id': 1}
            )
            if task_group:
                description = 'Task group processing.'
                self._task_group_transition(
                    task['task_group_id'][0], 'processing', description, None, {'task_id': task_id}
                )

        if state_to_index(state) in end_states():
            if task.get('notifications'):
                meta_data = {'task_id': task_id}
                notify(self._tee, task['notifications'], meta_data)

    def update_task_groups(self):
        task_groups = self._mongo.db['task_groups'].find(
            {'state': {'$nin': end_states()}},
            {'task_ids': 1, 'tasks_count': 1}
        )
        for task_group in task_groups:
            tasks = self._mongo.db['tasks'].find(
                {
                    '_id': {'$in': task_group['task_ids']},
                    'state': {'$in': end_states()}
                },
                {'_id': 1}
            )
            tasks = list(tasks)
            if task_group['tasks_count'] != len(tasks):
                continue
            task = self._mongo.db['tasks'].find_one(
                {
                    '_id': {'$in': task_group['task_ids']},
                    'state': state_to_index('success')
                },
                {'_id': 1}
            )
            if task:
                description = 'All tasks in group finished.'
                self._task_group_transition(task_group['_id'], 'success', description, None, None)
                continue
            description = 'All tasks in group failed or have been cancelled.'
            self._task_group_transition(task_group['_id'], 'failed', description, None, None)

    def _data_container_transition(self, data_container_id, state, description, exception, caused_by):
        data_container = self._mongo.db['data_containers'].find_one(
            {'_id': data_container_id},
            {'state': 1}
        )

        if data_container['state'] in end_states():
            return

        t = transition(state, description, exception, caused_by)
        self._append_transition('data_containers', data_container_id, t)

        if state == 'failed':
            application_containers = self._mongo.db['application_containers'].find({
                'state': {'$nin': end_states()},
                'data_container_ids': data_container_id
            }, {'_id': 1})

            for application_container in application_containers:
                ac_id = application_container['_id']
                ac_description = 'Application container failed: %s' % description
                self._application_container_transition(
                    ac_id, 'failed', ac_description, None, {'data_container_id': data_container_id}
                )



