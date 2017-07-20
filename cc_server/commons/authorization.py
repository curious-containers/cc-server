from os import urandom
from time import time

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import request

from cc_server.commons.helper import generate_secret, get_ip, equal_keys


class Authorize:
    def __init__(self, config, tee, mongo):
        self._tee = tee
        self._mongo = mongo
        self._config = config

    def create_user(self, username, password, is_admin):
        salt = urandom(16)
        kdf = _kdf(salt)
        user = {
            'username': username,
            'password': kdf.derive(password.encode('utf-8')),
            'salt': salt,
            'is_admin': is_admin
        }
        self._mongo.db['users'].update_one({'username': username}, {'$set': user}, upsert=True)

    def verify_user(self, require_admin=True, require_credentials=True):
        auth = request.authorization
        if not auth:
            return False
        username = auth.username
        password = auth.password

        user = self._mongo.db['users'].find_one({'username': username})
        if not user:
            return False

        result = False

        ip = get_ip()
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
        container = self._mongo.db[collection].find_one(
            {'_id': json_input['container_id']},
            {'callback_key': 1}
        )
        if not container:
            return False
        if not equal_keys(container['callback_key'], json_input['callback_key']):
            return False
        return True

    def _is_blocked_temporarily(self, username):
        num_login_attempts = self._config.defaults['authorization']['num_login_attempts']
        block_for_seconds = self._config.defaults['authorization']['block_for_seconds']
        self._mongo.db['block_entries'].delete_many({'timestamp': {'$lt': time() - block_for_seconds}})
        block_entries = list(self._mongo.db['block_entries'].find({'username': username}))
        if len(block_entries) > num_login_attempts:
            return True
        return False

    def _add_block_entry(self, username):
        self._mongo.db['block_entries'].insert_one({
            'username': username,
            'timestamp': time()
        })
        self._tee('Unverified login attempt: added block entry!')

    def issue_token(self):
        salt = urandom(16)
        kdf = _kdf(salt)
        token = generate_secret()
        username = request.authorization.username
        ip = get_ip()
        self._mongo.db['tokens'].insert_one({
            'username': username,
            'ip': ip,
            'salt': salt,
            'token': kdf.derive(token.encode('utf-8')),
            'timestamp': time()
        })
        return token

    def _verify_user_by_token(self, user, token, ip):
        tokens_valid_for_seconds = self._config.defaults['authorization']['tokens_valid_for_seconds']
        self._mongo.db['tokens'].delete_many({'timestamp': {'$lt': time() - tokens_valid_for_seconds}})
        cursor = self._mongo.db['tokens'].find(
            {'username': user['username'], 'ip': ip},
            {'token': 1, 'salt': 1}
        )
        for c in cursor:
            try:
                kdf = _kdf(c['salt'])
                kdf.verify(token.encode('utf-8'), c['token'])
                return True
            except:
                pass
        return False


def _verify_user_by_credentials(user, password):
    kdf = _kdf(user['salt'])
    try:
        kdf.verify(password.encode('utf-8'), user['password'])
    except:
        return False

    return True


def _kdf(salt):
    return PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
