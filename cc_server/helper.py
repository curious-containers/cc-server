from os import urandom
from binascii import hexlify
from streql import equals
from bson.objectid import ObjectId

UNSAFE_KEYS = [
    'password',
    'callback_key',
    'ssh_password',
    'http_data',
    'http_auth',
    'json_data',
    'json_auth'
]


def key_generator():
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


def prepare_response(data):
    if isinstance(data, dict):
        result = {}
        for key, val in data.items():
            if key in UNSAFE_KEYS:
                val = 10*'*'
            else:
                val = prepare_response(val)
            result[key] = val
        return result
    elif isinstance(data, list):
        return [prepare_response(e) for e in data]
    elif isinstance(data, ObjectId):
        return str(data)
    return data
