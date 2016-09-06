import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth


def _auth(http_auth):
    if not http_auth:
        return None

    if http_auth.get('basic_username'):
        return HTTPBasicAuth(
            http_auth.get('basic_username'),
            http_auth.get('basic_password')
        )

    if http_auth.get('digest_username'):
        return HTTPDigestAuth(
            http_auth.get('digest_username'),
            http_auth.get('digest_password')
        )

    raise Exception('Authorization information is not valid.')


def notify(servers):
    for server in servers:
        requests.post(
            server['http_url'],
            json=server.get('http_data'),
            auth=_auth(server.get('http_auth'))
        )
