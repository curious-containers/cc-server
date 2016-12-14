import jsonschema
from traceback import format_exc
from flask import request, jsonify
from werkzeug.exceptions import BadRequest, Unauthorized
from threading import Thread

from cc_server.database import Mongo
from cc_server.authorization import Authorize
from cc_server.helper import prepare_response, prepare_input, get_ip
from cc_server.states import StateHandler, is_state
from cc_server.schemas import query_schema, tasks_schema, callback_schema, cancel_schema, nodes_schema


def task_group_prototype():
    return {
        'state': -1,
        'created_at': None,
        'transitions': [],
        'username': None,
        'task_ids': []
    }


def log(func):
    """function decorator"""
    def wrapper(self, *args, **kwargs):
        info = ['REQUEST:', request.method, request.url, 'from', get_ip()]
        try:
            info.append(request.authorization.username)
        except:
            pass
        try:
            result = func(self, *args, **kwargs)
        except Unauthorized:
            info.insert(1, '401')
            self.tee(' '.join(info))
            raise
        except BadRequest:
            info.insert(1, '400')
            self.tee(' '.join(info))
            raise
        except:
            info.insert(1, '500')
            self.tee(' '.join(info))
            raise
        info.insert(1, '200')
        self.tee(' '.join(info))
        return result
    return wrapper


def auth(require_admin=True, require_credentials=True):
    """function decorator"""
    def dec(func):
        def wrapper(self, *args, **kwargs):
            if not self.authorize.verify_user(require_admin=require_admin, require_credentials=require_credentials):
                raise Unauthorized()
            return func(self, *args, **kwargs)
        return wrapper
    return dec


def validation(schema):
    """function decorator"""
    def dec(func):
        def wrapper(self, json_input, *args, **kwargs):
            try:
                jsonschema.validate(json_input, schema)
                json_input = prepare_input(json_input)
            except:
                raise BadRequest('JSON input not valid: {}'.format(format_exc()))
            return func(self, json_input, *args, **kwargs)
        return wrapper
    return dec


class RequestHandler:
    def __init__(self, config, tee, worker):
        self._config = config
        self._worker = worker
        self._tee = tee
        self._mongo = Mongo(
            config=self._config
        )
        self._state_handler = StateHandler(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo
        )
        self._authorize = Authorize(
            config=self._config,
            tee=self._tee,
            mongo=self._mongo
        )

    @log
    @auth(require_credentials=False)
    @validation(nodes_schema)
    def post_nodes(self, json_input):
        for node in json_input['nodes']:
            self._worker.update_node_status(node['name'])
        return jsonify({})

    @log
    @auth(require_admin=False, require_credentials=False)
    def get_nodes(self):
        return jsonify(prepare_response({
            'healthy_nodes': self._worker.nodes(),
            'dead_nodes': list(self._mongo.db['dead_nodes'].find({}))
        }))

    @log
    @auth(require_credentials=False)
    def put_worker(self):
        self._worker.schedule()
        return jsonify({})

    @log
    @auth(require_admin=False)
    def get_token(self):
        token = self._authorize.issue_token()
        return jsonify({
            'token': token,
            'valid_for_seconds': self._config.defaults['authorization'].get('tokens_valid_for_seconds')
        })

    def _cancel(self, json_input):
        description = 'Task cancelled.'
        self._state_handler.transition('tasks', json_input['_id'], 'cancelled', description)
        task = self._mongo.db['tasks'].find_one({
            '_id': json_input['_id']
        }, {
            '_id': 1,
            'state': 1
        })
        return task

    def _cancel_task(self, json_input, username):
        self._is_task(json_input, username)
        return self._cancel(json_input)

    def _cancel_tasks(self, json_input, username):
        for task in json_input['tasks']:
            self._is_task(task, username)
        responses = []
        for task in json_input['tasks']:
            responses.append(self._cancel(task))
        return {'tasks': responses}

    def _is_task(self, json_input, username):
        if username:
            task = self._mongo.db['tasks'].find_one(
                {'username': username, '_id': json_input['_id']},
                {'_id': 1}
            )
        else:
            task = self._mongo.db['tasks'].find_one(
                {'_id': json_input['_id']},
                {'_id': 1}
            )
        if not task:
            raise BadRequest('Task not found: {}'.format(json_input['_id']))

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(cancel_schema)
    def post_tasks_cancel(self, json_input):
        username = None
        if not self._authorize.verify_user(require_credentials=False):
            username = request.authorization.username

        if json_input.get('tasks'):
            response = self._cancel_tasks(json_input, username)
        else:
            response = self._cancel_task(json_input, username)
        self._worker.container_callback()
        return jsonify(prepare_response(response))

    def _register_task(self, json_input, task_group_id):
        json_input['username'] = request.authorization.username
        json_input['state'] = -1
        json_input['created_at'] = None
        json_input['trials'] = 0
        json_input['transitions'] = []
        json_input['task_group_id'] = [task_group_id]
        task_id = self._mongo.db['tasks'].insert_one(json_input).inserted_id

        self._state_handler.transition('tasks', task_id, 'created', 'Task created.')
        self._state_handler.transition('tasks', task_id, 'waiting', 'Task waiting.')

        self._mongo.db['task_groups'].update({'_id': task_group_id}, {
            '$push': {'task_ids': task_id},
        })

        return {'_id': task_id}

    def _create_task(self, json_input, task_group_id):
        return self._register_task(json_input, task_group_id)

    def _create_tasks(self, json_input, task_group_id):
        responses = []
        for json_task in json_input['tasks']:
            responses.append(self._register_task(json_task, task_group_id))
        return {'tasks': responses, 'task_group_id': task_group_id}

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(tasks_schema)
    def post_tasks(self, json_input):
        task_group = task_group_prototype()
        task_group['username'] = request.authorization.username
        task_group['tasks_count'] = len(json_input.get('tasks', [0]))
        task_group_id = self._mongo.db['task_groups'].insert_one(task_group).inserted_id
        self._state_handler.transition('task_groups', task_group_id, 'created', 'Task group created.')
        if json_input.get('tasks'):
            result = self._create_tasks(json_input, task_group_id)
        else:
            result = self._create_task(json_input, task_group_id)
        self._state_handler.transition('task_groups', task_group_id, 'waiting', 'Task group waiting.')
        self._worker.schedule()
        return jsonify(prepare_response(result))

    def _aggregate(self, json_input, collection):
        pipeline = json_input['aggregate']
        if not self._authorize.verify_user(require_credentials=False):
            pipeline = [{'$match': {'username': request.authorization.username}}] + pipeline

        try:
            cursor = self._mongo.db[collection].aggregate(pipeline)
        except:
            raise BadRequest('Could not execute aggregation pipeline with MongoDB: {}'.format(format_exc()))

        result = list(cursor)
        return {collection: result}

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_application_containers_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'application_containers')))

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_data_containers_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'data_containers')))

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_tasks_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'tasks')))

    @log
    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_task_groups_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'task_groups')))

    @log
    @validation(callback_schema)
    def post_application_container_callback(self, json_input):
        if not self._authorize.verify_callback(json_input, 'application_containers'):
            raise Unauthorized()

        self._validate_callback(json_input, 'application_containers')

        c = self._mongo.db['application_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'task_id': 1, 'data_container_ids': 1}
        )

        if is_state(c['state'], 'failed'):
            self._worker.container_callback()
            raise BadRequest('Container failed.')

        if json_input['callback_type'] == 0:
            # collect input file information and send with response

            task_id = c['task_id'][0]
            task = self._mongo.db['tasks'].find_one(
                {'_id': task_id},
                {'input_files': 1, 'no_cache': 1, 'result_files': 1, 'application_container_description': 1}
            )

            response = {
                'task_id': str(task_id),
                'result_files': task['result_files'],
                'parameters': task['application_container_description'].get('parameters'),
                'sandbox': task['application_container_description'].get('sandbox'),
                'tracing': task['application_container_description'].get('tracing')
            }

            if task.get('no_cache'):
                response['input_files'] = task['input_files']
            else:
                response['input_files'] = []
                for input_file, data_container_id in zip(task['input_files'], c['data_container_ids']):

                    data_container = self._mongo.db['data_containers'].find_one(
                        {'_id': data_container_id},
                        {'input_files': 1, 'input_file_keys': 1}
                    )

                    ip = self._worker.get_ip(data_container_id, 'data_containers')

                    for f, k in zip(data_container['input_files'], data_container['input_file_keys']):
                        if f == input_file:
                            response['input_files'].append({
                                'connector_type': 'http',
                                'connector_access': {
                                    'url': 'http://{}/{}'.format(ip, k)
                                }
                            })
                            break
            return jsonify(response)

        elif json_input['callback_type'] == 3:
            description = 'Callback with callback_type 3 and has been sent.'
            self._state_handler.transition('application_containers', c['_id'], 'success', description)
            self._worker.container_callback()

        return jsonify({})

    @log
    @validation(callback_schema)
    def post_data_container_callback(self, json_input):
        if not self._authorize.verify_callback(json_input, 'data_containers'):
            raise Unauthorized()

        self._validate_callback(json_input, 'data_containers')

        c = self._mongo.db['data_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'input_files': 1}
        )

        if is_state(c['state'], 'failed'):
            self._worker.container_callback()
            raise BadRequest('Container failed.')

        if json_input['callback_type'] == 1:
            description = 'Input files available in data container.'
            self._state_handler.transition('data_containers', c['_id'], 'processing', description)
            self._worker.data_container_callback()

        return jsonify({})

    def _validate_callback(self, json_input, collection):
        c = self._mongo.db[collection].find_one({'_id': json_input['container_id']})
        if is_state(c['state'], 'failed') or is_state(c['state'], 'success'):
            return

        self._mongo.db[collection].update({'_id': c['_id']}, {
            '$push': {'callbacks': json_input}
        })

        if json_input['callback_type'] != len(c['callbacks']):
            description = 'Callback with invalid callback_type has been sent.'
            self._state_handler.transition(collection, c['_id'], 'failed', description)
            return

        if is_state(json_input['content']['state'], 'failed'):
            description = 'Something went wrong on the other side.'
            self._state_handler.transition(collection, c['_id'], 'failed', description)
            return

        if not is_state(json_input['content']['state'], 'success'):
            description = 'Callback with invalid state has been sent.'
            self._state_handler.transition(collection, c['_id'], 'failed', description)
            return
