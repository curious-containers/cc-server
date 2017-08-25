import os
import atexit
import zmq
from multiprocessing import cpu_count
from flask import Flask, send_from_directory, request
from werkzeug.utils import secure_filename

from cc_server.commons.configuration import Config
from cc_server.commons.helper import close_sockets
from cc_server.commons.gunicorn_integration import WebApp


app = Flask('cc-server-files')

tee = None
input_files_dir = None
result_files_dir = None


@app.route('/<file_name>', methods=['GET'])
def get_file(file_name):
    file_name = secure_filename(file_name)
    tee('Sending file: {}'.format(file_name))
    return send_from_directory(input_files_dir, file_name, as_attachment=True)


@app.route('/<file_name>', methods=['POST'])
def post_file(file_name):
    file_name = secure_filename(file_name)
    file_path = os.path.join(result_files_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(request.data)
    tee('Receiving file: {}'.format(file_name))
    return ''


def prepare():
    config = Config()

    global tee
    global input_files_dir
    global result_files_dir

    context = zmq.Context()
    logger_socket = context.socket(zmq.PUSH)
    logger_socket.connect(config.server_log['external_url'])
    tee = logger_socket.send_string

    atexit.register(close_sockets, [logger_socket])

    input_files_dir = os.path.expanduser(config.server_files['input_files_dir'])
    result_files_dir = os.path.expanduser(config.server_files['result_files_dir'])

    tee('Started service files with pid {}'.format(os.getpid()))

    return config


def main():
    config = Config()

    options = {
        'bind': '{}:{}'.format(
            config.server_files['bind_host'],
            config.server_files['bind_port']
        ),
        'workers': config.server_files.get('num_workers', cpu_count()),
        'worker_class': 'gevent'
    }

    WebApp(app_module='cc_server.services.files.wsgi', options=options).run()

if __name__ == '__main__':
    main()
