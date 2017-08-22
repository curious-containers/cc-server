import os
from multiprocessing import cpu_count
from flask import Flask, send_from_directory, request
from werkzeug.utils import secure_filename

from cc_server.commons.gunicorn_integration import WebApp
from cc_server.commons.configuration import Config


app = Flask('file_server')

config = Config()
INPUT_FILES_DIR = os.path.expanduser(config.server_files['input_files_dir'])
RESULT_FILES_DIR = os.path.expanduser(config.server_files['result_files_dir'])


@app.route('/<file_name>', methods=['GET'])
def get_file(file_name):
    file_name = secure_filename(file_name)
    return send_from_directory(INPUT_FILES_DIR, file_name, as_attachment=True)


@app.route('/<file_name>', methods=['POST'])
def post_file(file_name):
    file_name = secure_filename(file_name)
    file_path = os.path.join(RESULT_FILES_DIR, file_name)
    with open(file_path, 'wb') as f:
        f.write(request.data)
    return ''


def main():
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
