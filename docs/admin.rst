Administrator Documentation
===========================

The administrator documentation describes the installation and required dependencies of the CC-Server software, as well
as the configuration options. This software has been tested with Ubuntu 14.04 and 16.04, but may also work with other
Linux distributions. Adapt the following installation instructions to your own need. Python 3 is required. The software
is tested with Python 3.4, but newer versions are likely to work as well.

CC-Server is able to connect to a local docker-engine, which is useful for testing the software with a minimal
configuration effort or to deploy the software to a single production server. If this is the first time you are
installing CC-Server, this approach is recommended as a first step.

Git Installation
----------------

In order to clone the Curious Containers repositories from Github, it is necessary to install Git. Follow the
instructions in the official `Git documentation <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`__.

Docker Installation
-------------------

Please follow the official `Docker documenation <https://docs.docker.com/engine/installation/linux/ubuntulinux/>`__ for
installation instructions. Please always install the **latest version** (currently version 12) and do not use
outdated packages from your Linux distribution. Docker provides third-party repositories for all major platforms.

Docker Swarm (Optional)
^^^^^^^^^^^^^^^^^^^^^^^

CC-Server supports Docker Swarm for cluster computing. The instructions for setting up Docker Swarm vary depending on 
the underlying infrastructure. It is advised to read the official
`Docker Swarm documentation <https://docs.docker.com/swarm/overview/>`__.

In addition it is necessary to setup a Docker
Overlay network on top of Docker Swarm, in order to enable inter-container communication across multiple hosts. 
Installation instructions can be found in the official
`Docker Overlay Network documentation <https://docs.docker.com/engine/userguide/networking/get-started-overlay/>`__.

Setting up a small Docker Swarm on a local machine for testing purposes can be achieved with
`Docker Machine <https://docs.docker.com/machine/install-machine/>`__ and
`Virtualbox <https://www.virtualbox.org/wiki/Linux_Downloads>`__. After setting up Docker Machine and Virtualbox the bash
scripts from the `CC-Swarm-Setup repository <https://github.com/curious-containers/cc-swarm-setup>`__ can be used.

.. code-block:: bash

   git clone https://github.com/curious-containers/cc-swarm-setup.git
   cd cc-swarm-setup

   # Customize the variables at the top of the setup.sh script or use the defaults
   # Run the script to set up a Docker Swarm and a Overlay Network with the name cc-overlay-network.
   # IP and PORT of the Swarm Manager will be printed by the script after the installation is done.
   bash setup.sh

   # Source the variables of connect.sh to connect the your docker-engine to the Swarm Manager
   source connect.sh

   # Take a look at the Swarm installation
   docker info


The following figure shows a possible setup of Curious Containers with Swarm Swarm.

|

.. image:: _static/images/cluster.*

|

CC-Server Installation
----------------------

The following installation instructions work with Ubuntu, but can be customized for other Linux operating systems.

Ubuntu Packages
^^^^^^^^^^^^^^^

.. code-block:: bash

   sudo apt-get install python3-pip libssl-dev libffi-dev


Python 3 Packages
^^^^^^^^^^^^^^^^^

It is recommended to install the Python packages globally for a certain system user, but without root privileges.

.. code-block:: bash

   pip3 install --user --upgrade flask pymongo docker-py psutil cryptography toml jsonschema requests streql


MongoDB
^^^^^^^

Install MongoDB 3.2. Instructions can be found in the official
`MongoDB documentation <https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/>`__.

In order to setup a database user, change *DB_PASSWORD* to something secure and run the following bash script:

.. code-block:: bash

   DB=ccdb
   DB_USERNAME=ccdbAdmin
   DB_PASSWORD=PASSWORD

   data="{user: \"${DB_USERNAME}\", pwd: \"${DB_PASSWORD}\", roles: [{role: \"readWrite\", db: \"${DB}\"}]}"
   mongo --eval "database = db.getSiblingDB(\"${DB}\"); database.createUser(${data})"


Get the Code
^^^^^^^^^^^^

Clone a specific version from the Github repository:

.. code-block:: bash

   git clone -b 0.1 --depth 1 https://github.com/curious-containers/cc-server
   cd cc-server


Configuration
^^^^^^^^^^^^^

*The following commands assume being inside the cc-server directory.*

Create a config.toml file. Visit the `TOML specification <https://github.com/toml-lang/toml>`__ for further information
about the file format. Use one of the included sample configuriation as a starting point. If you are connecting
CC-Server to a local docker-engine:

.. code-block:: bash

   cp sample_local_docker_config.toml config.toml


Else, if you are connecting CC-Server to a Swarm Manager:

.. code-block:: bash

   cp sample_docker_swarm_config.toml config.toml


server
""""""

CC-Server uses `flask <http://flask.pocoo.org/>`__ to run a light-weight web server providing a REST interface.
When starting the server it connects to an **internal_port** with port 5000 as default value. The server is then
reachable at localhost:5000 and requests can be sent to the API. This **internal_port** should never be exposed to
internet (configure a firewall to ensure this), because flask does not provide TLS encryption for the HTTP communication.
Another web server (e.g. Apache 2) can be used as a TLS proxy by forwarding requests to the **internal_port**.
Therefore the external adress of CC-Server (e.g. https://cc.my-domain.tld) differs from the internal adress (e.g. 
http://localhost:5000) and the external adress must be specified as **host**. CC-Server runs Docker containers
with a CC-Container-Worker. Since the worker sends callback requests to this **host** adress, this adress must be
reachable by the container. The easiest way to achieve this, is to expose the **host** adress to the internet. More
advanced routing configurations may be possible, but are not discussed here. Take a look at the
[Apache 2 TLS Proxy documentation](#apache-2-tls-proxy) for a sample configuration. An optional debug log for
the flask webserver can be enabled by specifying a logging directory as **log_dir**.

.. code-block:: toml

   [server]
   host = 'https://cc.my-domain.tld'
   internal_port = 5000
   log_dir = '~/.cc_server/'

mongo
"""""

Connect CC-Server to the previously installed MongoDB server. Assuming the database server is running the
same machine as CC-Server, the **host** is specified as localhost. The **username**, **password** and **dbname** must be
changed according to the privious MongoDB settings.

.. code-block:: toml

   [mongo]
   username = 'ccdbAdmin'
   password = 'PASSWORD'
   host = 'localhost'
   dbname = 'ccdb'


docker
""""""

CC-Server can use a local docker-engine or a Docker Swarm in order to run Docker containers. If the local
docker-engine is used, **base_url** is set to *unix://var/run/docker.sock*. CC-Server is a highly parallelized
application, which spawns hundrets of threads. The number of threads, accessing the Docker API in parallel, must be
limited by setting **thread_limit** in order to avoid severe Docker bugs (currently version 12). The default value *8*
is a reasonable choice, but higher values could speed up the processing times.

.. code-block:: toml

   [docker]
   thread_limit = 8
   base_url = 'unix://var/run/docker.sock'


If using Docker Swarm, the configuration becomes more complex. The **base_url** is changed to the IP and PORT of the
Swarm Manager. A Docker Overlay Network must be created beforehand and the name of the network is given as **net**.
The API of a Docker Manager is usually protected by a TLS encryption. When using Docker Machine for the Swarm setup, the
certificate files can be found in the system users home directory at *~/.docker/machine/machines*. CC-Server is using
the docker-py Python package. Take a look at the official
`docker-py documentation <http://docker-py.readthedocs.io/en/stable/tls/>`__ for more information about TLS options. Delete
the **docker.tls** section from the configuration file if not required.

.. code-block:: toml

   [docker]
   thread_limit = 8
   base_url = '192.168.99.99:3376'
   net = 'cc-overlay-network'

   [docker.tls]
   verify = '/home/USER/.docker/machine/machines/cc-manager/ca.pem'
   client_cert = [
       '/home/USER/.docker/machine/machines/cc-manager/cert.pem',
       '/home/USER/.docker/machine/machines/cc-manager/key.pem'
   ]
   assert_hostname = false


defaults
""""""""

*The defaults section in the TOML configuration is for values, that usually do not need to be change in order to run
CC-Server.*

The **data_container_description** fields contain information about how to run a data container. CC-Image-Ubuntu and
CC-Image-Fedora are both supported as data container images. Specify the URL of one of theses images, or a customized
image, in the **image** field. The images contain CC-Container-Worker, which is usually stored in the image file system
at */opt/container_worker*. The appropriate command to start the worker is given as **entry_point**. The field
**container_ram** specifies the amount of memory for a data container in Megabytes.

.. code-block:: toml

   [defaults.data_container_description]
   image = 'docker.io/curiouscontainers/cc-image-ubuntu:0.1'
   entry_point = 'python3 /opt/container_worker'
   container_ram = 512


If a custom data container image is specified in **data_container_description** and the access to this image in a Docker
registry is restricted, the appropriate **username** and **password** have to specified in **registry_auth**. The
**registry_auth** subsection should be deleted from the configuration file if not required.

.. code-block:: toml

   [defaults.data_container_description.registry_auth]
   username = 'REGISTRY_USER'
   password = 'PASSWORD'


Changing the scheduling behaviour of CC-Server can be achieved by changing the values the **scheduling_strategies**
subsection. Currently only the **container_allocation** strategy can be changed. The value of **container_allocation** must
be either *spread* or *binpack*. The *spread* strategy allocates a new container on a Swarm Node with the highest amount
of free RAM and *binpack* allocates a new container on a Swarm Node with the lowest amount of free RAM still suitable for
the container.

.. code-block:: toml

   [defaults.scheduling_strategies]
   container_allocation = 'spread'


CC-Server is fault tolerant, in the sense that faulty tasks are automatically restarted. Sometimes a restart will not fix
the problem, because the task configuration is wrong or a resource is not available. In order to avoid infite restart
loops, the number of restarts must be limited by setting the **max_task_trials** value in the **error_handling** subsection.

.. code-block:: toml

   [defaults.error_handling]
   max_task_trials = 3


The authorization module of CC-Server provides mechanism to avoid API exploitation. After a certain number of login attemps
with wrong user credentials, the authorization for this user will be blocked for a certain amount of time. These values
can be set as **number_login_attempts** and **block_for_seconds** in the **authorization** subsection. A user can request
a login token, which can be used instead of the original password for a certain amount of time specified as
**tokens_valid_for_seconds**.

.. code-block:: toml

   [defaults.authorization]
   num_login_attempts = 3
   block_for_seconds = 120
   tokens_valid_for_seconds = 172800


In the **mtu** section the maximum transmission unit for network interfaces of the Docker containers can be set. This is
a possible workaround for problems that arise when setting up Docker Swarm with a Docker Overlay Network (VXLAN) on top
of another VXLAN (e.g. using Docker Swarm in an OpenStack Cloud). Be careful with this option, because CC-Server will
start the containers in *privileged* mode to enable CC-Container-Worker to modify the network interfaces in the running
container. The **mtu** subsection should be deleted from the configuration file if not required.

.. code-block:: toml

   [defaults.mtu]
   eth0 = 1450
   eth1 = 1450


Create User Accounts
^^^^^^^^^^^^^^^^^^^^

Users can be created with an interactive script. Run the *create_user* script and follow the instructions. The script
asks if admin rights should be granted to the user. Admin users can query and cancel tasks of other users via the REST API,
while standard users only get access to their own tasks.

.. code-block:: bash

   python3 scripts/create_user


Run the Code
^^^^^^^^^^^^

*The following commands assume being inside the cc-server directory.*

.. code-block:: bash

   python3 cc_server


CC-Server will try to find the config.toml automatically. It will first look inside the directory from where the server
got launched (*./config.toml*). If the configuriation file is not there, it will first try to find it one directory
above (*../config.toml*) and then in the system users home directory (*~/.config/curious-containers/config.toml*).

If these locations are not suitable for the configuration file, the file path can be defined explicitely as a CLI argument:

.. code-block:: bash

   python3 cc_server /path/to/my_config.toml


If the server is not launched from within the git directory, but from another relative or absolute path, the location of
the curious_containers Python module must be specified in the PYTHONPATH. This can be achieved by specifying the path as
environment variable.

.. code-block:: bash

   export PYTHONPATH=/path/to/cc-server:${PYTHONPATH}
   python3 /path/to/cc-server/cc_server /path/to/cc-server/config.toml


For a permanent change, the path can be added to the *~/.profile* file:

.. code-block:: bash

   echo 'PYTHONPATH=/path/to/cc-server:${PYTHONPATH}' >> ~/.profile


Apache 2 TLS Proxy
^^^^^^^^^^^^^^^^^^

A TLS proxy should always be used to protect the CC-Server API. Make sure that the internal port is protected by a
firewall. The following sample configuration shows how this can be achieved with Apache 2.

**IMPORTANT NOTE:** This is not the most secure configuration possible, but only a simplified example. For more
information take a look at the official `Apache 2 documentation <https://httpd.apache.org/docs/current/ssl/>`__ and the
`Mozilla Wiki <https://wiki.mozilla.org/Security/Server_Side_TLS>`__.

.. code-block:: apache

   Listen 443

   <VirtualHost *:443>
       ProxyRequests Off
       SSLEngine On
       SSLCertificateFile /PATH/TO/cert.pem
       SSLCertificateKeyFile /PATH/TO/key.pem
       SSLCertificateChainFile /PATH/TO/chain.pem

       ServerName cc.my-domain.tld
       ServerAlias cc.my-domain.tld

       ProxyPass / http://localhost:5000/
       ProxyPassReverse / http://localhost:5000/
       RedirectMatch ^/$ https://cc.my-domain.tld:443
   </VirtualHost>


Docker Registry (Optional)
--------------------------

Container images created by users have to be deployed to a Docker registry. The official
`Docker Hub registry <https://hub.docker.com/>`__ with free public repositories or a paid plan for private repositories can
be used. Consider deploying a private Docker repository in order to provide free private repositories to your users.
Instructions can be found in the official `Docker Registry documentation <https://docs.docker.com/registry/deploying/>`__.
