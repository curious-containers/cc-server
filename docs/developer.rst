Developer Documentation
=======================

This page contains developer documentation. It is advised to read through the administrator and user documentation first.

Contributing
------------

If you find a bug or would like to request a feature, please file an
`issue on Github <https://github.com/curious-containers/cc-server/issues>`__. If you implemented a bug fix, please create a
`pull request <https://github.com/curious-containers/cc-server/pulls>`__. Pull requests for features should be discussed
first.

Building the Documentation
--------------------------

Clone CC-Server and install Python3 dependencies:

.. code-block:: bash

   git clone https://github.com/curious-containers/cc-server.git
   cd cc-server
   pip3 install --user --upgrade -r docs/requirements.txt


Run *make* inside the *docs* directory:

.. code-block:: bash

   cd docs
   make html

Docker Compose
--------------

Curious Containers provides a quick way to setup CC-Server via Docker Compose. First
`install the latest docker-engine <https://docs.docker.com/engine/installation/>`__ and
`Docker Compose <https://docs.docker.com/compose/install/>`__.

Clone the latest CC-Server code and change into the compose directory. Then copy or link the sample configuration files
from the config_samples directory to the current working directory. The configuration should work out of the box, but
may as well be customized, for example to prevent conflicting ports with other applications.

.. code-block:: bash

   git clone https://github.com/curious-containers/cc-server.git
   cd cc-server/compose
   cp -R config_samples/* .


In order to start CC-Server run **bin/start_cc_server**. This will create Containers for MongoDB, Docker Registry,
Docker-In-Docker, CC-Server-Log, CC-Server-Master and CC-Server-Web. CC-Server-Web will be available as *localhost:8000*.
Using the Docker Registry is optional. It is available at *localhost:5000*. During the setup MongoDB user credentials
are read from the **config.toml** file. These credentials can be changed before running *docker-compose*.

.. code-block:: bash

   bin/cc-start-server


First create a user for CC-Server. With the **cc-create-user** script the **config.toml** file used with docker-compose
can be referenced. In **config.toml** the hostname of the MongoDB is set to *mongo*, because this is the hostname of the
container created by docker-compose. Use --mongo-host to override this setting to *localhost*, which uses the MongoDB
port forwarding configured in **docker-compose.yml**.


.. code-block:: bash

   cd ..
   pip3 install --user --upgrade -r requirements.txt
   bin/cc-create-user --config-file=compose/config.toml --mongo-host=localhost


The Docker container for CC-Server will incorporate the CC-Server source code from the cloned git directory.
If you make changes to CC-Server, just remove all the started containers and execute the *docker-compose* command again
to run the latest code. Please note, that some data, namely the registry images, dind images, database contents and log
files, is persisted to your home directory at *~/.cc_server_compose* via Docker volumes. In order to start from scratch
delete this directory.

.. code-block:: bash

   bin/cc-stop-server

   # optional: delete all data
   sudo rm -rf ~/.cc_server_compose


Custom Data Connectors
----------------------

In the CC-Container-Worker source code all data connectors for input files are located in *downloaders.py* and all data
connectors for result files are located in *uploaders.py*. They are standalone functions, which share the same interface.
In the function signature of the downloaders two arguments, **connector_access** and **local_input_file**, are specified.
For the uploaders a three arguments, **connector_access**, **local_result_file** and **meta_data**, are specified. The
argument **connector_access** will be filled with a dictionary of the **connector_access** information for a certain
file, specified by a user in a task description. The **local_input_file** / **local_result_file** arguments will be
will be filled with the respective information from the *config.json* of the CC-Container-Worker, which contains
information, where the file can be found or should be placed in the local file system of the Docker container. The
**meta_data** argument must be in the function signature of the uploader, but is entirely optional to be used in the
code. The existing data connectors give a good example how these arguments are used.

In order to create custom data connectors, add Python modules with the names *cc_custom_downloaders* and
*cc_custom_uploaders* to your container image. Make sure to set the PYTHONPATH environment variable correctly. The
CC-Worker-Worker will automatically pick up all functions specified in these modules, which do not start with an
underscore. The only requirement is that the function signatures are specified correctly and that the given function
names are unique and do not collide with the existing connectors. A user can reference the custom connectors by
specifying **connector_type** equals the function name in a task description.


Sample implementation of a multi-file uploader
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**custom_uploaders.py**:

.. code-block:: python

   import os
   import glob
   import requests

   from cc_container_worker.commons import helper

   def http_multi_file(connector_access, local_result_file, meta_data):
       local_file_paths = glob.glob(os.path.join(
           local_result_file['dir'],
           local_result_file['names']
       ))

       for local_file_path in local_file_paths:
           with open(local_file_path, 'rb') as f:
               r = requests.put(
                   connector_access['url'],
                   data=f,
                   auth=helper.auth(connector_access.get('auth'))
               )
               r.raise_for_status()


**config.json** of CC-Container-Worker:

.. code-block:: json

   {
       "application_command": "bash /root/algorithm.sh",
       "local_input_files": [],
       "local_result_files": {
           "csv_data": {"dir": "/root/result_files", "names": "*.csv"}
       }
   }


**Dockerfile**:

.. code-block:: docker

   FROM docker.io/curiouscontainers/cc-image-fedora
   COPY config.json /root/.config/cc-container-worker/config.json

   COPY algorithm.sh /root/algorithm.sh

   COPY custom_uploaders.py /app/custom_uploaders.py

   ENV PYTHONPATH /app:${PYTHONPATH}


Excerpt from a sample **task**:

.. code-block:: json

   {
       "result_files": [{
           "local_result_file": "csv_data",
           "connector_type": "http_multi_file",
           "connector_access": {
               "url": "my-domain.tld/multi-file-endpoint",
               "auth": {
                   "auth_type": "basic",
                   "username": "ccdata",
                   "password": "PASSWORD"
               }
           }
       }]
   }
