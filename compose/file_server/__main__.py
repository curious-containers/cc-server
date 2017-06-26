import os
from flask import Flask, send_from_directory, request
from werkzeug.utils import secure_filename

app = Flask('file_server')

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
