import sys
from os import urandom
from binascii import hexlify
from streql import equals
from bson.objectid import ObjectId
from flask import request


class RedirectStdStreams(object):
    # source: http://stackoverflow.com/questions/6796492/temporarily-redirect-stdout-stderr
    def __init__(self, stdout=None, stderr=None):
        self._stdout = stdout or sys.stdout
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.old_stdout.flush()
        self.old_stderr.flush()
        sys.stdout, sys.stderr = self._stdout, self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        self._stderr.flush()
        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr


def get_ip():
    headers = ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR']
    ip = None
    for header in headers:
        ip = request.environ.get(header)
        if ip:
            break
    if not ip:
        ip = '127.0.0.1'
    return ip


def generate_secret():
    return hexlify(urandom(24)).decode('utf-8')


def equal_keys(a, b):
    return equals(a.encode('utf-8'), b.encode('utf-8'))


def _prepare_input(data, replace):
    if isinstance(data, dict):
        result = {}
        for key, val in data.items():
            if not replace and (key.endswith('_id') or key.endswith('_ids')):
                result[key] = _prepare_input(val, True)
            else:
                result[key] = _prepare_input(val, replace)
        return result
    elif isinstance(data, list):
        return [_prepare_input(e, replace) for e in data]
    elif replace and isinstance(data, str):
        return ObjectId(data)
    return data


def prepare_input(data):
    return _prepare_input(data, False)


def _prepare(data, replace_objectid, replace_secret):
    if isinstance(data, dict):
        result = {}
        for key, val in data.items():
            if not replace_secret and ('key' in key or 'password' in key):
                result[key] = _prepare(val, replace_objectid, True)
            else:
                result[key] = _prepare(val, replace_objectid, replace_secret)
        return result
    elif isinstance(data, list):
        return [_prepare(e, replace_objectid, replace_secret) for e in data]
    elif isinstance(data, ObjectId):
        if replace_objectid:
            return str(data)
    elif replace_secret:
        return 10*'*'
    return data


def prepare_response(data):
    return _prepare(data, True, False)


def remove_secrets(data):
    return _prepare(data, False, False)
