from jsonschema import validate
from threading import Thread
from traceback import format_exc
from pprint import pprint
from flask import request, jsonify
from werkzeug.exceptions import BadRequest, Unauthorized

from cc_server.helper import prepare_response, prepare_input
from cc_server.states import is_state, state_to_index, end_states
from cc_server.schemas import query_schema, tasks_schema, callback_schema, cancel_schema


def task_group_prototype():
    return {
        'state': 0,
        'transitions': [],
        'username': None,
        'task_ids': []
    }


def auth(require_auth=True, require_admin=True, require_credentials=True):
    def dec(func):
        def wrapper(self, *args, **kwargs):
            if require_auth:
                if not self.authorize.verify_user(require_admin=require_admin, require_credentials=require_credentials):
                    raise Unauthorized()
            return jsonify(func(self, *args, **kwargs))
        return wrapper
    return dec


def validation(schema):
    def dec(func):
        def wrapper(self, json_input, *args, **kwargs):
            try:
                validate(json_input, schema)
                json_input = prepare_input(json_input)
            except:
                raise BadRequest('JSON input not valid: {}'.format(format_exc()))
            return func(self, json_input, *args, **kwargs)
        return wrapper
    return dec


class RequestHandler:
    def __init__(self, mongo, cluster, worker, authorize, config, state_handler):
        self.cluster = cluster
        self.mongo = mongo
        self.worker = worker
        self.authorize = authorize
        self.config = config
        self.state_handler = state_handler

    @auth(require_admin=False, require_credentials=False)
    def get_root(self):
        return {
            'status': state_to_index('success'),
            'description': 'Curious Containers Server is running.',
            'version': 0.3
        }

    @auth(require_admin=False)
    def get_token(self):
        token = self.authorize.issue_token()
        return {
            'state': state_to_index('success'),
            'token': token,
            'valid_for_seconds': self.config.defaults['authorization'].get('tokens_valid_for_seconds'),
            'description': 'Token issued successfully.'
        }

    def _cancel_tasks(self, json_input):
        task_ids = [task['_id'] for task in json_input['tasks']]
        if json_input.get('username'):
            tasks = self.mongo.db['tasks'].find({
                'username': json_input.get('username'),
                '_id': {'$in': task_ids},
                'state': {'$nin': end_states()}
            }, {
                '_id': 1
            })
        else:
            tasks = self.mongo.db['tasks'].find({
                '_id': {'$in': task_ids},
                'state': {'$nin': end_states()}
            }, {
                '_id': 1
            })
        task_ids = [task['_id'] for task in tasks]
        for _id in task_ids:
            description = 'Task cancelled.'
            self.state_handler.transition('tasks', _id, 'cancelled', description)
        tasks = self.mongo.db['tasks'].find(
            {'_id': {'$in': task_ids}},
            {'_id': 1, 'state': 1}
        )
        tasks = list(tasks)
        if tasks:
            Thread(target=self.worker.post_container_callback).start()
        else:
            return {
                'state': state_to_index('failed'),
                'description': 'No task cancelled.'
            }
        return prepare_response({
            'state': state_to_index('success'),
            'tasks': list(tasks),
            'description': 'Tasks cancelled.'
        })

    def _cancel_task(self, json_input):
        if json_input.get('username'):
            task = self.mongo.db['tasks'].find_one({
                'username': json_input.get('username'),
                '_id': json_input['_id'],
                'state': {'$nin': end_states()}
            }, {
                '_id': 1
            })
        else:
            task = self.mongo.db['tasks'].find_one({
                '_id': json_input['_id'],
                'state': {'$nin': end_states()}
            }, {
                '_id': 1
            })
        if task:
            Thread(target=self.worker.post_container_callback).start()
        else:
            return {
                'state': state_to_index('failed'),
                'description': 'Task not cancelled.'
            }
        description = 'Task cancelled.'
        self.state_handler.transition('tasks', task['_id'], 'cancelled', description)
        return {
            'state': state_to_index('success'),
            'description': 'Task cancelled.'
        }

    @auth(require_admin=False, require_credentials=False)
    @validation(cancel_schema)
    def post_tasks_cancel(self, json_input):
        if not self.authorize.verify_user(require_credentials=False):
            json_input['username'] = request.authorization.username

        if json_input.get('tasks'):
            return self._cancel_tasks(json_input)
        return self._cancel_task(json_input)

    def _register_task(self, json_input):
        json_input['state'] = 0
        json_input['trials'] = 0
        json_input['transitions'] = []
        task_id = self.mongo.db['tasks'].insert_one(json_input).inserted_id

        self.state_handler.transition('tasks', task_id, 'created', 'Task created.')
        self.state_handler.transition('tasks', task_id, 'waiting', 'Task waiting.')

        self.mongo.db['task_groups'].update({'_id': json_input['task_group_id']}, {
            '$push': {'task_ids': task_id},
        })

        return {'state': state_to_index('success'), '_id': task_id}

    def _create_task(self, json_input, task_group_id):
        json_input['username'] = request.authorization.username
        json_input['task_group_id'] = task_group_id
        response = self._register_task(json_input)
        Thread(target=self.worker.post_task).start()
        return response

    def _create_tasks(self, json_input, task_group_id):
        responses = []
        for json_task in json_input['tasks']:
            json_task['username'] = request.authorization.username
            json_task['task_group_id'] = task_group_id
            responses.append(self._register_task(json_task))
        Thread(target=self.worker.post_task).start()
        return prepare_response({'tasks': responses})

    @auth(require_admin=False, require_credentials=False)
    @validation(tasks_schema)
    def post_tasks(self, json_input):
        task_group = task_group_prototype()
        task_group['username'] = request.authorization.username
        task_group['tasks_count'] = len(json_input.get('tasks', [0]))
        task_group_id = self.mongo.db['task_groups'].insert_one(task_group).inserted_id
        self.state_handler.transition('task_groups', task_group_id, 'created', 'Task group created.')
        if json_input.get('tasks'):
            result = self._create_tasks(json_input, task_group_id)
            result['task_group_id'] = task_group_id
        else:
            result = self._create_task(json_input, task_group_id)
        self.state_handler.transition('task_groups', task_group_id, 'waiting', 'Task group waiting.')

        return prepare_response(result)

    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def _aggregate(self, json_input, collection):
        pipeline = [{'$match': json_input['match']}]
        if self.authorize.verify_user(require_credentials=False):
            description = 'Query executed as admin user.'
        else:
            description = 'Query executed.'
            pipeline.append({'$match': {'username': request.authorization.username}})
        if json_input.get('sort'):
            pipeline.append({'$sort': json_input['sort']})
        if json_input.get('project'):
            pipeline.append({'$project': json_input['project']})
        if json_input.get('limit'):
            pipeline.append({'$limit': json_input['limit']})
        try:
            containers = self.mongo.db[collection].aggregate(pipeline)
        except:
            raise BadRequest('Could not execute aggregation pipeline with MongoDB: {}'.format(format_exc()))
        return prepare_response({
            'state': state_to_index('success'),
            collection: list(containers),
            'description': description
        })

    def post_application_containers_query(self, json_input):
        return self._aggregate(json_input, 'application_containers')

    def post_data_containers_query(self, json_input):
        return self._aggregate(json_input, 'data_containers')

    def post_tasks_query(self, json_input):
        return self._aggregate(json_input, 'tasks')

    def post_task_groups_query(self, json_input):
        return self._aggregate(json_input, 'task_groups')

    @auth(require_auth=False)
    @validation(callback_schema)
    def post_application_container_callback(self, json_input):
        if not self.authorize.verify_callback(json_input, 'application_containers'):
            raise Unauthorized()

        self._validate_callback(json_input, 'application_containers')

        c = self.mongo.db['application_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'task_id': 1, 'data_container_ids': 1}
        )

        if is_state(c['state'], 'failed'):
            Thread(target=self.worker.post_container_callback).start()
            raise BadRequest('Container is in state failed.')

        if json_input['callback_type'] == 0:
            # collect input file information and send with response

            task_id = c['task_id']
            task = self.mongo.db['tasks'].find_one(
                {'_id': task_id},
                {'input_files': 1, 'no_cache': 1}
            )

            if task.get('no_cache'):
                response = {'input_files': task['input_files']}
            else:
                response = {'input_files': []}
                for input_file, data_container_id in zip(task['input_files'], c['data_container_ids']):

                    data_container = self.mongo.db['data_containers'].find_one(
                        {'_id': data_container_id},
                        {'input_files': 1, 'input_file_keys': 1}
                    )

                    ip = self.cluster.get_ip(data_container_id)

                    for f, k in zip(data_container['input_files'], data_container['input_file_keys']):
                        if f == input_file:
                            f = input_file
                            f['data_container_url'] = 'http://{}/'.format(ip)
                            f['input_file_key'] = k
                            response['input_files'].append(f)
                            break

            response['state'] = state_to_index('success')
            return response

        elif json_input['callback_type'] == 3:
            description = 'Callback with callback_type 3 and has been sent.'
            self.state_handler.transition('application_containers', c['_id'], 'success', description)
            Thread(target=self.worker.post_container_callback).start()

        return {'state': state_to_index('success')}

    @auth(require_auth=False)
    @validation(callback_schema)
    def post_data_container_callback(self, json_input):
        if not self.authorize.verify_callback(json_input, 'data_containers'):
            raise Unauthorized()

        self._validate_callback(json_input, 'data_containers')

        c = self.mongo.db['data_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'input_files': 1}
        )

        if is_state(c['state'], 'failed'):
            Thread(target=self.worker.post_container_callback).start()
            raise BadRequest('Container is in state failed.')

        if json_input['callback_type'] == 1:
            if not json_input['content'].get('input_file_keys') \
                    or len(json_input['content']['input_file_keys']) != len(c['input_files']):

                description = 'Callback with callback_type 1 did not send valid input_file_keys.'
                self.state_handler.transition('data_containers', c['_id'], 'failed', description)
                return {'state': state_to_index('failed'), 'description': 'Container is in state failed.'}

            self.mongo.db['data_containers'].update_one(
                {'_id': c['_id']},
                {'$set': {'input_file_keys': json_input['content']['input_file_keys']}}
            )

            description = 'Input files available in data container.'
            self.state_handler.transition('data_containers', c['_id'], 'processing', description)

            Thread(target=self.worker.post_data_container_callback).start()

        return {'state': state_to_index('success')}

    def _validate_callback(self, json_input, collection):
        c = self.mongo.db[collection].find_one({'_id': json_input['container_id']})
        if is_state(c['state'], 'failed') or is_state(c['state'], 'success'):
            return

        self.mongo.db[collection].update({'_id': c['_id']}, {
            '$push': {'callbacks': json_input}
        })

        if json_input['callback_type'] != len(c['callbacks']):
            description = 'Callback with invalid callback_type has been sent'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            return

        if is_state(json_input['content']['state'], 'failed'):
            description = 'Something went wrong on the other side.'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            pprint(json_input['content'])
            return

        if not is_state(json_input['content']['state'], 'success'):
            description = 'Callback with invalid state has been sent.'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            return
