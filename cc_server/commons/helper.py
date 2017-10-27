from os import urandom
from binascii import hexlify
from bson.objectid import ObjectId
from flask import request
from hmac import compare_digest


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
    return compare_digest(a, b)


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
        try:
            return ObjectId(data)
        except:
            return data
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


def close_sockets(sockets):
    for s in sockets:
        s.close()
