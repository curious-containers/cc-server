import json
import jsonschema
from threading import Thread
from traceback import format_exc
from flask import request, jsonify
from werkzeug.exceptions import BadRequest, Unauthorized
from gridfs import GridFS
from bson.objectid import ObjectId

from cc_server.helper import prepare_response, prepare_input
from cc_server.states import is_state
from cc_server.schemas import query_schema, tasks_schema, callback_schema, cancel_schema


def task_group_prototype():
    return {
        'state': -1,
        'created_at': None,
        'transitions': [],
        'username': None,
        'task_ids': []
    }


def auth(require_admin=True, require_credentials=True):
    """function decorator"""
    def dec(func):
        def wrapper(self, *args, **kwargs):
            if not self.authorize.verify_user(require_admin=require_admin, require_credentials=require_credentials):
                raise Unauthorized()
            return func(self, *args, **kwargs)
        return wrapper
    return dec


def _validate_schema_worker(json_input, schema):
    try:
        jsonschema.validate(json_input, schema)
    except:
        return format_exc()
    return None


def validation(schema):
    """function decorator"""
    def dec(func):
        def wrapper(self, json_input, *args, **kwargs):
            # json schema validation
            formatted_exception = self.pool.apply(_validate_schema_worker, (json_input, schema))
            if formatted_exception:
                if self.config.server.get('debug'):
                    print(formatted_exception)
                raise BadRequest('JSON input not valid: {}'.format(formatted_exception))

            # cast string IDs to ObjectIDs
            try:
                json_input = prepare_input(json_input)
            except:
                if self.config.server.get('debug'):
                    print(format_exc())
                raise BadRequest('JSON input not valid: {}'.format(format_exc()))

            # call request function
            return func(self, json_input, *args, **kwargs)
        return wrapper
    return dec


class RequestHandler:
    def __init__(self, mongo, cluster, worker, authorize, config, state_handler, pool):
        self.cluster = cluster
        self.mongo = mongo
        self.worker = worker
        self.authorize = authorize
        self.config = config
        self.state_handler = state_handler
        self.pool = pool

    @auth(require_admin=False, require_credentials=False)
    def get_root(self):
        return jsonify({'version': 0.5})

    @auth(require_admin=False)
    def put_worker(self):
        Thread(target=self.worker.post_task).start()
        return jsonify({})

    @auth(require_admin=False)
    def get_token(self):
        token = self.authorize.issue_token()
        return jsonify({
            'token': token,
            'valid_for_seconds': self.config.defaults['authorization'].get('tokens_valid_for_seconds')
        })

    def _cancel(self, json_input):
        description = 'Task cancelled.'
        self.state_handler.transition('tasks', json_input['_id'], 'cancelled', description)
        task = self.mongo.db['tasks'].find_one({
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
            task = self.mongo.db['tasks'].find_one(
                {'username': username, '_id': json_input['_id']},
                {'_id': 1}
            )
        else:
            task = self.mongo.db['tasks'].find_one(
                {'_id': json_input['_id']},
                {'_id': 1}
            )
        if not task:
            raise BadRequest('Task not found: {}'.format(json_input['_id']))

    @auth(require_admin=False, require_credentials=False)
    @validation(cancel_schema)
    def post_tasks_cancel(self, json_input):
        username = None
        if not self.authorize.verify_user(require_credentials=False):
            username = request.authorization.username

        if json_input.get('tasks'):
            response = self._cancel_tasks(json_input, username)
        else:
            response = self._cancel_task(json_input, username)
        Thread(target=self.worker.post_container_callback).start()
        return jsonify(prepare_response(response))

    def _register_task(self, json_input, task_group_id):
        json_input['username'] = request.authorization.username
        json_input['state'] = -1
        json_input['created_at'] = None
        json_input['trials'] = 0
        json_input['transitions'] = []
        json_input['task_group_id'] = [task_group_id]
        task_id = self.mongo.db['tasks'].insert_one(json_input).inserted_id

        self.state_handler.transition('tasks', task_id, 'created', 'Task created.')
        self.state_handler.transition('tasks', task_id, 'waiting', 'Task waiting.')

        self.mongo.db['task_groups'].update({'_id': task_group_id}, {
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
        else:
            result = self._create_task(json_input, task_group_id)
        self.state_handler.transition('task_groups', task_group_id, 'waiting', 'Task group waiting.')
        Thread(target=self.worker.post_task).start()
        return jsonify(prepare_response(result))

    def _aggregate(self, json_input, collection):
        pipeline = json_input['aggregate']
        if not self.authorize.verify_user(require_credentials=False):
            pipeline = [{'$match': {'username': request.authorization.username}}] + pipeline

        try:
            cursor = self.mongo.db[collection].aggregate(pipeline)
        except:
            raise BadRequest('Could not execute aggregation pipeline with MongoDB: {}'.format(format_exc()))

        result = list(cursor)
        return {collection: result}

    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_application_containers_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'application_containers')))

    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_data_containers_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'data_containers')))

    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_tasks_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'tasks')))

    @auth(require_admin=False, require_credentials=False)
    @validation(query_schema)
    def post_task_groups_query(self, json_input):
        return jsonify(prepare_response(self._aggregate(json_input, 'task_groups')))

    @auth(require_admin=False, require_credentials=False)
    def get_application_containers_tracing(self, _id):
        try:
            _id = ObjectId(_id)
        except:
            raise BadRequest('_id not valid: {}'.format(format_exc()))

        query = {'aggregate': [
            {'$match': {'_id': _id}},
            {'$project': {'callbacks.content.telemetry.tracing': 1}}
        ]}
        result = self._aggregate(query, 'application_containers')
        tracing_id = None
        try:
            tracing_id = result['application_containers'][0]['callbacks'][2]['content']['telemetry']['tracing'][0]
        except:
            pass

        if not tracing_id:
            return jsonify({})

        gridfs = GridFS(self.mongo.db, collection='tracing')
        tracing = gridfs.find_one({'_id': tracing_id}).read().decode('utf-8')
        if not tracing:
            return jsonify({})

        return tracing

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
            raise BadRequest('Container failed.')

        if json_input['callback_type'] == 0:
            # collect input file information and send with response

            task_id = c['task_id'][0]
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
            self.state_handler.transition('application_containers', c['_id'], 'success', description)
            Thread(target=self.worker.post_container_callback).start()

        return jsonify({})

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
            raise BadRequest('Container failed.')

        if json_input['callback_type'] == 1:
            description = 'Input files available in data container.'
            self.state_handler.transition('data_containers', c['_id'], 'processing', description)

            Thread(target=self.worker.post_data_container_callback).start()

        return jsonify({})

    def _validate_callback(self, json_input, collection):
        c = self.mongo.db[collection].find_one({'_id': json_input['container_id']})
        if is_state(c['state'], 'failed') or is_state(c['state'], 'success'):
            return

        #if json_input['content'].get('telemetry') and json_input['content'].get('telemetry').get('tracing'):
        #    gridfs = GridFS(self.mongo.db, collection='tracing')
        #    tracing_id = gridfs.put(json.dumps(json_input['content']['telemetry']['tracing']), encoding='utf-8')
        #    json_input['content']['telemetry']['tracing'] = [tracing_id]

        self.mongo.db[collection].update({'_id': c['_id']}, {
            '$push': {'callbacks': json_input}
        })

        if json_input['callback_type'] != len(c['callbacks']):
            description = 'Callback with invalid callback_type has been sent.'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            return

        if is_state(json_input['content']['state'], 'failed'):
            description = 'Something went wrong on the other side.'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            return

        if not is_state(json_input['content']['state'], 'success'):
            description = 'Callback with invalid state has been sent.'
            self.state_handler.transition(collection, c['_id'], 'failed', description)
            return
