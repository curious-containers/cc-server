import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from traceback import format_exc


def _auth(http_auth):
    if not http_auth:
        return None

    if http_auth['auth_type'] == 'basic':
        return HTTPBasicAuth(
            http_auth['username'],
            http_auth['password']
        )

    if http_auth['auth_type'] == 'digest':
        return HTTPDigestAuth(
            http_auth['username'],
            http_auth['password']
        )

    raise Exception('Authorization information is not valid.')


def notify(servers):
    for connector_access in servers:
        try:
            json_data = None
            http_method = connector_access['method'].lower()
            if http_method == 'put':
                method_func = requests.put
            elif http_method == 'post':
                method_func = requests.post
                json_data = connector_access.get('json_data')
            else:
                raise Exception('HTTP method not valid: {}'.format(connector_access['method']))
            method_func(
                connector_access['url'],
                json=json_data,
                auth=_auth(connector_access.get('auth')),
                verify=connector_access.get('ssl_verify', True)
            )
        except:
            print(format_exc())
