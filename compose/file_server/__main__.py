import os
from multiprocessing import cpu_count
from flask import Flask, send_from_directory, request
from werkzeug.utils import secure_filename
from cc_server.commons.gunicorn_integration import WebApp

app = Flask('file_server')
application = app

input_files_dir = os.path.expanduser('~/input_files')
result_files_dir = os.path.expanduser('~/result_files')


@app.route('/<file_name>', methods=['GET'])
def get_file(file_name):
    file_name = secure_filename(file_name)
    return send_from_directory(input_files_dir, file_name, as_attachment=True)


@app.route('/<file_name>', methods=['POST'])
def post_file(file_name):
    file_name = secure_filename(file_name)
    file_path = os.path.join(result_files_dir, file_name)
    with open(file_path, 'wb') as f:
        f.write(request.data)
    return ''

if __name__ == '__main__':
    options = {
        'bind': '{}:{}'.format('0.0.0.0', 6000),
        'workers': cpu_count(),
        'worker_class': 'gevent'
    }

    WebApp(app_module='file_server.__main__', options=options).run()
