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

