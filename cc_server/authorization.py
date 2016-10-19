from os import urandom
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from time import time
from flask import request

from cc_server.helper import key_generator, equal_keys


def _get_ip():
    headers = ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'REMOTE_ADDR']
    ip = None
    for header in headers:
        ip = request.environ.get(header)
        if ip:
            break
    if not ip:
        ip = '127.0.0.1'
    print('IP:', ip)
    return ip


class Authorize:
    def __init__(self, mongo, config):
        self.mongo = mongo
        self.config = config

    def create_user(self, username, password, is_admin):
        salt = urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        user = {
            'username': username,
            'password': kdf.derive(password.encode('utf-8')),
            'salt': salt,
            'hash_function': 'SHA256',
            'is_admin': is_admin
        }
        self.mongo.db['users'].update_one({'username': username}, {'$set': user}, upsert=True)

    def verify_user(self, require_admin=True, require_credentials=True):
        auth = request.authorization
        if not auth:
            return False
        username = auth.username
        password = auth.password

        user = self.mongo.db['users'].find_one({'username': username})
        if not user:
            return False

        result = False

        ip = _get_ip()
        if not require_credentials:
            result = self._verify_user_by_token(user, password, ip)

        if not result and self._is_blocked_temporarily(username):
            return False

        if not result:
            result = _verify_user_by_credentials(user, password)

        if not result:
            self._add_block_entry(username)
            return False

        if not require_admin or user['is_admin']:
            return True

        return False

    def verify_callback(self, json_input, collection):
        container = self.mongo.db[collection].find_one(
            {'_id': json_input['container_id']},
            {'callback_key': 1}
        )
        if not container:
            return False
        if not equal_keys(container['callback_key'], json_input['callback_key']):
            return False
        return True

    def _is_blocked_temporarily(self, username):
        num_login_attempts = self.config.defaults['authorization']['num_login_attempts']
        block_for_seconds = self.config.defaults['authorization']['block_for_seconds']
        self.mongo.db['block_entries'].delete_many({'timestamp': {'$lt': time() - block_for_seconds}})
        block_entries = list(self.mongo.db['block_entries'].find({'username': username}))
        if len(block_entries) > num_login_attempts:
            return True
        return False

    def _add_block_entry(self, username):
        self.mongo.db['block_entries'].insert_one({
            'username': username,
            'timestamp': time()
        })
        print('Unverified login attempt: added block entry!')

    def issue_token(self):
        token = key_generator()
        username = request.authorization.username
        ip = _get_ip()
        self.mongo.db['tokens'].insert_one({
            'username': username,
            'ip': ip,
            'token': token,
            'timestamp': time()
        })
        return token

    def _verify_user_by_token(self, user, token, ip):
        tokens_valid_for_seconds = self.config.defaults['authorization']['tokens_valid_for_seconds']
        self.mongo.db['tokens'].delete_many({'timestamp': {'$lt': time() - tokens_valid_for_seconds}})
        t = self.mongo.db['tokens'].find_one({
            'username': user['username'],
            'ip': ip,
            'token': token
        })
        if t:
            return True
        return False


def _verify_user_by_credentials(user, password):
    kdf = PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=user['salt'],
        iterations=100000,
        backend=default_backend()
    )
    try:
        kdf.verify(password.encode('utf-8'), user['password'])
    except:
        return False

    return True
