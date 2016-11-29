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

Install additional Python3 packages:

.. code-block:: bash

   pip3 install --user --upgrade flask sphinx sphinx-autobuild sphinxcontrib-httpdomain sphinx_rtd_theme bibtex-pygments-lexer


Run *make* inside the docs-src directory:

.. code-block:: bash

   cd docs
   make html

Docker Compose
--------------

Curious Containers provides a quick way to setup a development envrionment via Docker Compose. First
`install the latest docker-engine <https://docs.docker.com/engine/installation/linux/ubuntulinux/>`__ and
`Docker Compose <https://docs.docker.com/compose/install/>`__.

Clone the latest CC-Server code and change into the compose directory.

.. code-block:: bash

   git clone https://github.com/curious-containers/cc-server.git
   cd cc-server/compose


In order to start CC-Server run the following command. This will create Containers for MongoDB, Docker-In-Docker and
CC-Server. CC-Server will be available as *localhost:5000*. During the setup MongoDB user credentials are read from the
**config.toml** file and the CC-Server user credentials are read from the **credentials.toml** file. These credentials
can be changed before running *docker-compose*.

.. code-block:: bash

   docker-compose up cc-server


The Docker container for CC-Server will incorporate the CC-Server source code from the cloned git directory.
If you make changes to CC-Server, just stop the server and execute the *docker-compose* command again to run the latest
code. Please note, that this will not create a fresh MongoDB for each restart. In order to delete the database use
the following command.

.. code-block:: bash

   docker-compose kill mongo && docker-compose rm -f mongo


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

In order to create custom data connectors, the empty Python files *custom_downloaders.py* and *custom_uploaders.py* of
CC-Container-Worker can be overwritten when building a container image and filled. The CC-Worker-Worker will
automatically pick up all functions specified in these files, which do not start with an underscore. The only
requirement is that the function signatures are specified correctly and that the given function names are unique and do
not collide with the existing connectors. A user can reference the custom connectors by specifying **connector_type**
equals the function name in a task description.


Sample implementation of a multi-file uploader
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**custom_uploaders.py**:

.. code-block:: python

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
           "csv_data": {"dir": "/home/ubuntu/result_files", "names": "*.csv"}
       }
   }


**Dockerfile**:

.. code-block:: docker

   FROM docker.io/curiouscontainers/cc-image-ubuntu
   COPY config.json /opt/config.json

   COPY custom_uploaders.py /opt/container_worker/custom_uploaders.py

   COPY algorithm.sh /home/ubuntu/algorithm.sh


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
