import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth


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


def notify(tee, servers, meta_data):
    for connector_access in servers:
        try:
            json_data = connector_access.get('json_data')
            if connector_access.get('add_meta_data'):
                json_data = connector_access.get('json_data', {})
                for key, val in meta_data.items():
                    json_data[key] = val

            r = requests.post(
                connector_access['url'],
                json=json_data,
                auth=_auth(connector_access.get('auth')),
                verify=connector_access.get('ssl_verify', True)
            )
            r.raise_for_status()
        except:
            tee('Could not notify server: {}'.format(connector_access))
