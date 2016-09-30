from time import time
from pprint import pprint

from cc_server.notification import notify
from cc_server.helper import remove_secrets

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


def _transition(state, description, exception, caused_by):
    return {
        'timestamp': time(),
        'state': state_to_index(state),
        'description': description,
        'exception': exception,  # optional
        'caused_by': caused_by  # optional
    }


class StateHandler:
    def __init__(self, mongo, config):
        self.mongo = mongo
        self.config = config

    def transition(self, collection, _id, state, description, exception=None):
        if collection == 'tasks':
            self._task_transition(_id, state, description, exception, None)
        elif collection == 'application_containers':
            self._application_container_transition(_id, state, description, exception, None)
        elif collection == 'data_containers':
            self._data_container_transition(_id, state, description, exception, None)
        else:
            raise Exception('Invalid collection: %s' % collection)

    def _application_container_transition(self, application_container_id, state, description, exception, caused_by):
        application_container = self.mongo.db['application_containers'].find_one(
            {'_id': application_container_id},
            {'task_id': 1, 'state': 1}
        )

        if application_container['state'] in end_states():
            return

        t = _transition(state, description, exception, caused_by)
        self._append_transition('application_containers', application_container_id, t)

        if state == 'created':
            task_id = application_container['task_id']
            self._task_transition(
                task_id, 'processing', description, None, {'application_container_id': application_container_id}
            )

        elif state == 'failed':
            task_id = application_container['task_id']
            self._task_transition(
                task_id, 'failed', description, None, {'application_container_id': application_container_id}
            )

        elif state == 'success':
            task_id = application_container['task_id']
            self._task_transition(
                task_id, 'success', description, None, {'application_container_id': application_container_id}
            )

    def _append_transition(self, collection, _id, t):
        if is_state(t['state'], 'failed'):
            print(collection, _id, index_to_state(t['state']), t['description'], t.get('exception'))
        else:
            print(collection, _id, index_to_state(t['state']))

        self.mongo.db[collection].update({'_id': _id}, {
            '$push': {'transitions': t},
            '$set': {'state': t['state']}
        })
        if t['state'] in end_states():
            data = self.mongo.db[collection].find_one({'_id': _id})
            del data['_id']
            data = remove_secrets(data)
            self.mongo.db[collection].update_one({'_id': _id}, {'$set': data})

    def _task_transition(self, task_id, state, description, exception, caused_by):
        task = self.mongo.db['tasks'].find_one(
            {'_id': task_id},
            {'trials': 1, 'notifications': 1, 'state': 1}
        )

        if task['state'] in end_states():
            return

        if state == 'failed':
            trials = task['trials'] + 1
            self.mongo.db['tasks'].update_one(
                {'_id': task_id},
                {'$set': {'trials': trials}}
            )
            max_task_trials = self.config.defaults['error_handling']['max_task_trials']

            if trials < max_task_trials:
                state = 'waiting'
                description = 'Task waiting again (trial {} of {}): {}'.format(trials, max_task_trials, description)

        if state == 'cancelled':
            application_containers = self.mongo.db['application_containers'].find({
                'state': {'$nin': end_states()},
                'task_id': task_id
            }, {'_id': 1})

            for application_container in application_containers:
                ac_id = application_container['_id']
                ac_description = 'Application container cancelled: %s' % description
                self._application_container_transition(
                    ac_id, 'cancelled', ac_description, None, {'task_id': task_id}
                )

        t = _transition(state, description, exception, caused_by)
        self._append_transition('tasks', task_id, t)

        if (state == 'failed' or state == 'success' or state == 'cancelled') and task.get('notifications'):
            notify(task['notifications'])

    def _data_container_transition(self, data_container_id, state, description, exception, caused_by):
        data_container = self.mongo.db['data_containers'].find_one(
            {'_id': data_container_id},
            {'state': 1}
        )

        if data_container['state'] in end_states():
            return

        t = _transition(state, description, exception, caused_by)
        self._append_transition('data_containers', data_container_id, t)

        if state == 'failed':
            application_containers = self.mongo.db['application_containers'].find({
                'state': {'$nin': end_states()},
                'data_container_ids': data_container_id
            }, {'_id': 1})

            for application_container in application_containers:
                ac_id = application_container['_id']
                ac_description = 'Application container failed: %s' % description
                self._application_container_transition(
                    ac_id, 'failed', ac_description, None, {'data_container_id': data_container_id}
                )


