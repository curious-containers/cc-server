REST API
========

This page has detailed descriptions of the CC-Server API.

Quick reference
---------------

.. qrefflask:: cc_server.__main__:app
   :undoc-static:

About the API
-------------

Every API endpoint accepts JSON objects and returns JSON objects. Requests should always produce a HTTP 200 status.
The *state* fields in response JSON objects indicate whether or not a request was successful.

**States**

0) **created**
1) **waiting**
2) **processing**
3) **success**
4) **failed**
5) **cancelled**

Most requests send either state 3 or state 4. Other states are used for task, app container and data container objects.

Authorization
^^^^^^^^^^^^^

CC-Server uses HTTP Basic Auth to authorize users on every API request. All API endpoints for users (which is everything
except the endpoints for container callbacks) require you to send **username** and **password** via the appropriate HTTP
header.

The following Python script shows how to do authorize an API call with the Python requests package.

.. code-block:: python

   import requests

   username = 'admin'
   password = 'PASSWORD'

   requests.get('cc.my-domain.tld', auth=(username, password))


The same can be achieved with *curl* in a bash script.

.. code-block:: bash

   username="admin"
   password="PASSWORD"

   curl -X GET --user ${username}:${password} cc.my-domain.tld


HTTP sessions are not supported. However a token
can be requested from the `GET /token endpoint <#get--token>`__, which is then used instead of the password in subsequent
requests. The following Python code shows how to request a token. See `GET /token <#get--token>`__ for more information.

.. code-block:: python

   import requests

   username = 'admin'
   password = 'PASSWORD'

   r = requests.get('my-domain.tld/cc/token', auth=(username, password))
   data = r.json()
   requests.get('my-domain.tld/cc', auth=(username, data['token']))


API reference
-------------

.. autoflask:: cc_server.__main__:app
   :undoc-static:
