import os
import sys
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.split(os.path.split(os.path.abspath(__file__))[0])[0])

request_handler = None
app = Flask('cc-server')


@app.route('/', methods=['GET'])
def get_root():
    """
    .. :quickref: User API; Retrieve server version
    Receive a message, indicating the server is running.

    **Example request**

    .. sourcecode:: http

        GET / HTTP/1.1

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "version": 0.9
        }

    """
    return jsonify({'version': 0.9})


@app.route('/nodes', methods=['GET'])
def get_nodes():
    """
    .. :quickref: User API; Query cluster nodes

    Query the status of all nodes in the cluster. Dead nodes will appear in a separate list.

    **Example request**

    .. sourcecode:: http

        GET /nodes HTTP/1.1

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "dead_nodes": [],
            "healthy_nodes": [{
                "active_application_containers": [],
                "active_data_containers": [],
                "name": "cc-node2",
                "reserved_cpus": null,
                "reserved_ram": 0,
                "total_cpus": 2,
                "total_ram": 2002
            }, {
                "active_application_containers": [],
                "active_data_containers": [],
                "name": "cc-node1",
                "reserved_cpus": null,
                "reserved_ram": 0,
                "total_cpus": 2,
                "total_ram": 2002
            }]
        }

    """
    return request_handler.get_nodes()


@app.route('/nodes', methods=['POST'])
def post_nodes():
    """
    .. :quickref: Dev API; Update cluster nodes

    **Developer documentation**

    *Requires admin user.*

    Update the status of cluster nodes specified in the request. The endpoint can be used to notify CC-Server after a
    dead cluster node has been repaired.

    **Example request**

    .. sourcecode:: http

        POST /nodes HTTP/1.1

        {
            "nodes": [{
                "name": "cc-node2"
            }]
        }

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {}

    """
    return request_handler.post_nodes(request.get_json())


@app.route('/worker', methods=['PUT'])
def put_worker():
    """
    .. :quickref: Dev API; Spawn worker thread

    *Requires admin user.*

    If CC-Server is stuck in an undefined state, a new worker thread can be spawned to pick up unfinished tasks. The
    same behaviour can be triggered by restarting CC-Server. This endpoint should be used for debugging purposes only.

    **Example request**

    .. sourcecode:: http

        PUT /worker HTTP/1.1

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {}

    """
    return request_handler.put_worker()


@app.route('/tasks/query', methods=['POST'])
def post_tasks_query():
    """
    .. :quickref: User API; Query tasks

    Send JSON object with a query, in order to retrieve a list of tasks.
    Admin users can retrieve tasks from every other user, while standard users can only retrieve their own tasks.

    **JSON fields**

    * **aggregate** (required): List of steps to be performed as MongoDB aggregation pipeline

    Take a look at the
    `MongoDB documentation <https://docs.mongodb.com/manual/reference/operator/aggregation-pipeline/>`__ for further
    instructions.

    The permitted operations in the aggregation pipeline are:

    $match, $project, $limit, $skip, $count, $sort, $unwind, $group, $sample, $replaceRoot, $addFields.

    **Example request**

    .. sourcecode:: http

        POST /tasks/query HTTP/1.1
        Accept: application/json

        {
            "aggregate": [
                {"$match": {"_id": {"$in": ["57f63f73e004231a26ed187e", "57f63f73e004231a26ed187f"]}}},
                {"$sort": {"_id": -1}},
                {"$project": {"state": 1}},
                {"$limit": 2}
            ]
        }

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "tasks": [
                {"_id": "57f63f73e004231a26ed187f", "state": 2},
                {"_id": "57f63f73e004231a26ed187e", "state": 2}
            ]
        }

    """
    return request_handler.post_tasks_query(request.get_json())


@app.route('/tasks', methods=['POST'])
def post_tasks():
    """
    .. :quickref: User API; Schedule tasks

    Send JSON object with one or more task descriptions, in order to schedule them with the server.

    **JSON fields**

    * **tags** (optional): Tags are optional descriptions of given tasks. Can be used to identify tasks in the database.
    * **no_cache** (optional, default = *false*): If *true*, no data container is launched for the given task, such that the app container downloads input files directly.
    * **application_container_description.image** (required): URL pointing to a Docker image in a Docker registry.
    * **application_container_description.container_ram** (required): Amount of RAM assigned to the app container in Megabytes.
    * **application_container_description.registry_auth** (optional, default = None): If the specified image is not publicly accessible, a dict with username and password keys must be defined.
    * **application_container_description.entry_point** (optional, default is specified in config.toml of CC-Server): Program invoked by CC-Server when starting the app container. Only required if the location of the CC-Container-Worker in the container image is customized.
    * **application_container_description.parameters** (optional): Parameters are given to the app, when executed by CC-Container-Worker. Depending on the configuration of the container image. Parameters can be a JSON object or array.
    * **input_files** (required): List of input files in remote data repositories. This list maps to the list of local_input_files specified in the container image configuration. The list might be empty.
    * **result_files** (required): List of destinations of result files in remote data repositories. This list maps to the list of local_result_files specified in the container image configuration.
    * **notifications** (optional): List of HTTP servers that will receive a notification as soon as the task succeeded, failed or got cancelled.

    **Example request 1: single task**

    .. sourcecode:: http

        POST /tasks HTTP/1.1
        Accept: application/json

        {
            "tags": ["experiment1"],
            "no_cache": true,
            "application_container_description": {
                "image": "docker.io/curiouscontainers/cc-sample-app",
                "container_ram": 1024,
                "registry_auth": {
                    "username": "USERNAME",
                    "password": "PASSWORD"
                },
                "entry_point": "python3 /opt/container_worker",
                "parameters": ["--arg1", "value1", "--arg2", "value2"]
            },
            "input_files": [{
                "connector_type": "ssh",
                "connector_access": {
                    "host": "my-domain.tld",
                    "username": "ccdata",
                    "password": "PASSWORD",
                    "file_dir": "/home/ccdata/input_files",
                    "file_name": "some_data.csv"
                }

            }],
            "result_files": [{
                "local_result_file": "file_a",
                "connector_type": "ssh",
                "connector_access": {
                    "host": "my-domain.tld",
                    "username": "ccdata",
                    "password": "PASSWORD",
                    "file_dir": "/home/ccdata/result_files",
                    "file_name": "some_data.csv"
                }
            }, {
                "local_result_file": "file_b",
                "connector_type": "ssh",
                "connector_access": {
                    "host": "my-domain.tld",
                    "username": "ccdata",
                    "password": "PASSWORD",
                    "file_dir": "/home/ccdata/result_files",
                    "file_name": "parameters.txt"
                }
            }],
            "notifications": [{
                "url": "my-domain.tld/notify/",
                "method": "POST"
            }]
        }

    **Example response 1**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "_id": "57fbf45df62690000101afa5"
        }

    **Example request 2: multiple tasks**

    .. sourcecode:: http

        POST /tasks HTTP/1.1
        Accept: application/json

        {
            "tasks": [{
                "application_container_description": {
                    "image": "docker.io/curiouscontainers/cc-sample-app",
                    "container_ram": 1024
                },
                "input_files": [{
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/input_files/A/some_data.csv"
                    }

                }],
                "result_files": [{
                    "local_result_file": "file_a",
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/result_files/A/1/",
                        "method": "POST"
                    }
                }, {
                    "local_result_file": "file_b",
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/result_files/A/2/",
                        "method": "POST"
                    }
                }]
            }, {
                "application_container_description": {
                    "image": "docker.io/curiouscontainers/cc-sample-app",
                    "container_ram": 1024
                },
                "input_files": [{
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/input_files/B/some_data.csv"
                    }

                }],
                "result_files": [{
                    "local_result_file": "file_a",
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/result_files/B/1/",
                        "method": "POST"
                    }
                }, {
                    "local_result_file": "file_b",
                    "connector_type": "http",
                    "connector_access": {
                        "url": "https://my-domain.tld/result_files/B/2/",
                        "method": "POST"
                    }
                }]
            }]
        }

    **Example response 2**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "task_group_id": "57fbf45df62690000101afa4",
            "tasks": [{
                "_id": "57fbf45df62690000101afa5"
            }, {
                "_id": "57fbf45df62690000101afa6"
            }]
        }

    """
    return request_handler.post_tasks(request.get_json())


@app.route('/tasks/cancel', methods=['POST'])
def post_tasks_cancel():
    """
    .. :quickref: User API; Cancel tasks

    Send JSON object with one or more task IDs, in order to cancel their execution if they are still running.
    Admin users can cancel tasks from every other user, while standard users can only cancel their own tasks.

    **JSON fields**

    * **_id** (required)

    **Example request 1: single task**

    .. sourcecode:: http

        POST /tasks/cancel HTTP/1.1
        Accept: application/json

        {
            "_id": "57c3f73ae004232bd8b9b005"
        }

    **Example response 1: single task**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "_id": "57c3f73ae004232bd8b9b005",
            "state": 5
        }

    **Example request 2: multiple tasks**

    .. sourcecode:: http

        POST /tasks/cancel HTTP/1.1
        Accept: application/json

        {
            "tasks": [{
                "_id": "57c3f73ae004232bd8b9b005"
            },{
                "_id": "57c3f73ae004232bd8b9b006"
            }]
        }

    **Example response 2**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "tasks": [{
                "_id": "57c3f73ae004232bd8b9b005",
                "state": 5
            }, {
                "_id": "57c3f73ae004232bd8b9b006",
                "state": 5
            }]
        }

    """
    return request_handler.post_tasks_cancel(request.get_json())


@app.route('/token', methods=['GET'])
def get_token():
    """
    .. :quickref: User API; Retrieve authentication token

    Send JSON object with username and password, in order to retrieve an authentication token.
    For subsequent requests the password can be replaced by the token value for authentication.
    Tokens are tied to the IP address of the requesting user and only valid for a certain period of time defined in the
    CC-Server configuration.
    When requesting another token, the original password must be used for authentication.

    **Example request**

    .. sourcecode:: http

        GET /token HTTP/1.1

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {
            "token": "7e2950f21e3f0afd77253b8e13e2ee4da923e545389d424b",
            "valid_for_seconds": 172800
        }

    """
    return request_handler.get_token()


@app.route('/task-groups/query', methods=['POST'])
def post_task_groups_query():
    """
    .. :quickref: User API; Query task groups

    Send JSON object with a query, in order to retrieve a list of task groups.
    Admin users can retrieve task groups from every other user, while standard users can only retrieve their own task
    groups.

    Works exactly like the `POST /tasks/query endpoint <#post--tasks-query>`__.
    """
    return request_handler.post_task_groups_query(request.get_json())


@app.route('/application-containers/query', methods=['POST'])
def post_application_containers_query():
    """
    .. :quickref: User API; Query app containers

    Send JSON object with a query, in order to retrieve a list of app containers.
    Admin users can retrieve app containers from every other user, while standard users can only retrieve their own app
    containers.

    Works exactly like the `POST /tasks/query endpoint <#post--tasks-query>`__.
    """
    return request_handler.post_application_containers_query(request.get_json())


@app.route('/data-containers/query', methods=['POST'])
def post_data_containers_query():
    """
    .. :quickref: User API; Query data containers

    Send JSON object with a query, in order to retrieve a list of data containers.
    Admin users can retrieve data containers from every other user, while standard users can only retrieve their own
    data containers.

    Works exactly like the `POST /tasks/query endpoint <#post--tasks-query>`__.
    """
    return request_handler.post_data_containers_query(request.get_json())


@app.route('/application-containers/callback', methods=['POST'])
def post_application_container_callback():
    """
    .. :quickref: Dev API; App container callbacks

    **Developer documentation**

    Callback endpoint for app containers.

    **JSON fields**

    * **callback_key** (required)
    * **callback_type** (required)
    * **container_id** (required)
    * **content** (required)

    **Example request**

    .. sourcecode:: http

        POST /application-containers/callback HTTP/1.1
        Accept: application/json

        {
            "callback_key": "6318aa06b08935ba12f6396cb25981b1a7e71586d6100338",
            "callback_type": 3,
            "container_id": "57c3f517e00423251662f036",
            "content": {
                "state": 3,
                "description": "Result files sent."
            }
        }

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {}

    """
    return request_handler.post_application_container_callback(request.get_json())


@app.route('/data-containers/callback', methods=['POST'])
def post_data_container_callback():
    """
    .. :quickref: Dev API; Data container callbacks

    **Developer documentation**

    Callback endpoint data containers.

    **JSON fields**

    * **callback_key** (required)
    * **callback_type** (required)
    * **container_id** (required)
    * **content** (required)

    **Example request**

    .. sourcecode:: http

        POST /data-containers/callback HTTP/1.1
        Accept: application/json

        {
            "callback_key": "6318aa06b08935ba12f6396cb25981b1a7e71586d6100338",
            "callback_type": 0,
            "container_id": "57c3f517e00423251662f036",
            "content": {
                "state": 3,
                "description": "Container started."
            }
        }

    **Example response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Vary: Accept
        Content-Type: application/json

        {}

    """
    return request_handler.post_data_container_callback(request.get_json())


def prepare():
    from stance import Stance
    from cc_server.configuration import Config
    config = Config()

    from cc_commons.tee import Tee
    s = Stance(Tee, port=config.ipc['tee_port'], secret=config.ipc['secret'])
    tee = s.register(config=config)
    if s.created_new_instance():
        print('| tee    | PID: {} | STARTED     | in main   |'.format(tee.getpid()))
        tee.late_init()
        print('| tee    | PID: {} | INITIALIZED | in main   |'.format(tee.getpid()))
    else:
        print('| tee    | PID: {} | CONNECTED   | in main   |'.format(tee.getpid()))

    from cc_server.worker import Worker
    s = Stance(Worker, port=config.ipc['worker_port'], secret=config.ipc['secret'])
    worker = s.register(config=config)
    if s.created_new_instance():
        print('| worker | PID: {} | STARTED     | in main   |'.format(worker.getpid()))
        worker.late_init()
        print('| worker | PID: {} | INITIALIZED | in main   |'.format(worker.getpid()))
    else:
        print('| worker | PID: {} | CONNECTED   | in main   |'.format(worker.getpid()))

    from cc_server.request_handler import RequestHandler
    global request_handler
    request_handler = RequestHandler(
        config=config,
        tee=tee.tee,
        worker=worker
    )

    return config


def main():
    config = prepare()
    app.run(host='0.0.0.0', port=config.server['internal_port'])

if __name__ == '__main__':
    main()
