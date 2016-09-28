from jsonschema import validate
from threading import Thread
from traceback import format_exc
from pprint import pprint
from flask import request

from cc_server.helper import prepare_response, prepare_input
from cc_server.states import is_state, state_to_index
from cc_server.schemas import query_schema, tasks_schema, callback_schema, cancel_schema


class RequestHandler:
    def __init__(self, mongo, cluster, worker, authorize, config, state_handler):
        self.cluster = cluster
        self.mongo = mongo
        self.worker = worker
        self.authorize = authorize
        self.config = config
        self.state_handler = state_handler

    def get_root(self):
        if not self.authorize.verify_user(require_admin=False, require_credentials=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}
        return {
            'status': state_to_index('success'),
            'description': 'Curious Containers Server is running.',
            'version': 0.2
        }

    def get_token(self):
        if not self.authorize.verify_user(require_admin=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}

        token = self.authorize.issue_token()
        return {
            'state': state_to_index('success'),
            'token': token,
            'valid_for_seconds': self.config.main['authorization'].get('tokens_valid_for_seconds'),
            'description': 'Token issued successfully.'
        }

    def _delete_tasks(self, json_input):
        task_ids = [task['_id'] for task in json_input['tasks']]
        if json_input.get('username'):
            tasks = self.mongo.db['tasks'].find({
                'username': json_input.get('username'),
                '_id': {'$in': task_ids},
                'state': {'$nin': [state_to_index('success'), state_to_index('failed')]}
            }, {
                '_id': 1
            })
        else:
            tasks = self.mongo.db['tasks'].find({
                '_id': {'$in': task_ids},
                'state': {'$nin': [state_to_index('success'), state_to_index('failed')]}
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

    def _delete_task(self, json_input):
        if json_input.get('username'):
            task = self.mongo.db['tasks'].find_one({
                'username': json_input.get('username'),
                '_id': json_input['_id'],
                'state': {'$nin': [state_to_index('success'), state_to_index('failed')]}
            }, {
                '_id': 1
            })
        else:
            task = self.mongo.db['tasks'].find_one({
                '_id': json_input['_id'],
                'state': {'$nin': [state_to_index('success'), state_to_index('failed')]}
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

    def delete_tasks(self, json_input):
        if not self.authorize.verify_user(require_admin=False, require_credentials=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}
        try:
            validate(json_input, cancel_schema)
            json_input = prepare_input(json_input)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input for task is not valid.',
                'exception': format_exc()
            }

        if not self.authorize.verify_user(require_credentials=False):
            json_input['username'] = request.authorization.username

        if json_input.get('tasks'):
            return self._delete_tasks(json_input)
        return self._delete_task(json_input)

    def _register_task(self, json_input):
        json_input['state'] = 0
        json_input['trials'] = 0
        json_input['transitions'] = []
        task_id = self.mongo.db['tasks'].insert_one(json_input).inserted_id

        self.state_handler.transition('tasks', task_id, 'created', "Task created.")
        self.state_handler.transition('tasks', task_id, 'waiting', "Task waiting.")

        return {'state': state_to_index('success'), '_id': task_id}

    def _post_task(self, json_input):
        json_input['username'] = request.authorization.username
        response = self._register_task(json_input)
        Thread(target=self.worker.post_task).start()
        return response

    def _post_tasks(self, json_input):
        responses = []
        for json_task in json_input['tasks']:
            json_task['username'] = request.authorization.username
            responses.append(self._register_task(json_task))
        Thread(target=self.worker.post_task).start()
        return prepare_response({'tasks': responses})

    def post_tasks(self, json_input):
        if not self.authorize.verify_user(require_admin=False, require_credentials=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}
        try:
            validate(json_input, tasks_schema)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input for tasks is not valid.',
                'exception': format_exc()
            }

        if json_input.get('tasks'):
            result = self._post_tasks(json_input)
        else:
            result = self._post_task(json_input)
        return prepare_response(result)

    def get_tasks(self, json_input):
        if not self.authorize.verify_user(require_admin=False, require_credentials=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}
        try:
            validate(json_input, query_schema)
            json_input = prepare_input(json_input)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input is not valid.',
                'exception': format_exc()
            }

        description = 'Query executed as admin user.'
        if not self.authorize.verify_user(require_credentials=False):
            description = 'Query executed.'
            json_input['query']['username'] = request.authorization.username

        tasks = self.mongo.db['tasks'].find(json_input['query'], json_input.get('projection'))
        return prepare_response({'state': state_to_index('success'), 'tasks': list(tasks), 'description': description})

    def _get_containers(self, json_input, collection):
        if not self.authorize.verify_user(require_admin=False, require_credentials=False):
            return {'state': state_to_index('failed'), 'description': 'User not authorized.'}
        try:
            validate(json_input, query_schema)
            json_input = prepare_input(json_input)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input is not valid.',
                'exception': format_exc()
            }

        if self.authorize.verify_user(require_credentials=False):
            description = 'Query executed as admin user.'
            containers = self.mongo.db[collection].find(
                json_input['query'],
                json_input.get('projection')
            )
        else:
            description = 'Query executed.'
            tasks = self.mongo.db['tasks'].find(
                {'username': request.authorization.username},
                {'_id': 1}
            )
            additional_query = {'task_id': {'$in': [task['_id'] for task in tasks]}}
            pipeline = [
                {'$match': json_input['query']},
                {'$match': additional_query}
            ]
            if json_input.get('projection'):
                pipeline.append({'$project': json_input['projection']})
            containers = self.mongo.db[collection].aggregate(pipeline)

        return prepare_response({
            'state': state_to_index('success'),
            'containers': list(containers),
            'description': description
        })

    def get_application_containers(self, json_input):
        return self._get_containers(json_input, 'application_containers')

    def get_data_containers(self, json_input):
        return self._get_containers(json_input, 'data_containers')

    def post_application_container_callback(self, json_input):
        try:
            validate(json_input, callback_schema)
            json_input = prepare_input(json_input)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input for callback is not valid.',
                'exception': format_exc()
            }

        if not self.authorize.verify_callback(json_input, 'application_containers'):
            return {'state': state_to_index('failed'), 'description': 'Callback not authorized.'}

        self._validate_callback(json_input, 'application_containers')

        c = self.mongo.db['application_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'task_id': 1, 'data_container_ids': 1}
        )

        if is_state(c['state'], 'failed'):
            Thread(target=self.worker.post_container_callback).start()
            return {'state': state_to_index('failed'), 'description': 'Container is in state failed.'}

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

        elif json_input['callback_type'] == 2:
            self.mongo.db['data_containers'].update_one(
                {'_id': c['_id']},
                {'$set': {'telemetry': json_input['content'].get('telemetry')}}
            )

        elif json_input['callback_type'] == 3:
            description = 'Callback with callback_type 3 and has been sent.'
            self.state_handler.transition('application_containers', c['_id'], 'success', description)
            Thread(target=self.worker.post_container_callback).start()

        return {'state': state_to_index('success')}

    def post_data_container_callback(self, json_input):
        try:
            validate(json_input, callback_schema)
            json_input = prepare_input(json_input)
        except:
            return {
                'state': state_to_index('failed'),
                'description': 'JSON input for callback is not valid.',
                'exception': format_exc()
            }

        if not self.authorize.verify_callback(json_input, 'data_containers'):
            return {'state': state_to_index('failed'), 'description': 'Callback not authorized.'}

        self._validate_callback(json_input, 'data_containers')

        c = self.mongo.db['data_containers'].find_one(
            {'_id': json_input['container_id']},
            {'state': 1, 'input_files': 1}
        )

        if is_state(c['state'], 'failed'):
            Thread(target=self.worker.post_container_callback).start()
            return {'state': state_to_index('failed'), 'description': 'Container is in state failed.'}

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
