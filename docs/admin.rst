Administrator Documentation
===========================

The administrator documentation describes the installation and required dependencies of the CC-Server software, as well
as the configuration options. This software has been tested with Ubuntu 16.04, but may also work with other
Linux distributions. Adapt the following installation instructions to your own need. Python 3 is required. The software
is tested with Python 3.5, but other versions are likely to work as well.

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

Docker Cluster (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^

*As of version 0.7, connecting to a Docker Swarm manager is not supported anymore. CC-Server is now able to connect to
multiple docker-engines.*

A Docker cluster consists of multiple hosts, where each computer has a docker-engine installed. These hosts are called
**nodes** in the context of Curious Containers and can be physical computers, virtual machines or docker containers
running `docker-in-docker <https://github.com/jpetazzo/dind>`__.

The docker cluster must fullfill three requirements. First of all a cluster store
(e.g. `consul <https://www.consul.io/>`__) must be available to the cluster on a separate host. For each docker-engine
in the cluster, set the **cluster-store** as engine option. As a second requirement, the engine option
**cluster-advertise** must be specified in order to make the docker-engines listen on a TCP port (e.g.
*cluster-advertise=eth1:2376*). All firewalls on the nodes must also be configured to expose this port in a way,
that it is reachable by CC-Server. The third requirement is to enable a communication channel for containers running in
the cluster accross all nodes. This is achieved by connecting a Docker client to one of the nodes' docker-engines and to
create an `Overlay Network <https://docs.docker.com/engine/userguide/networking/get-started-overlay/>`__ for the
cluster. Please note, that this step needs to be done only once and that it is only possible if the **cluster-store**
has been configured correctly.

It is recommended to use `Docker Machine <https://docs.docker.com/machine/install-machine/>`__ in order to setup virtual
machines with the correct settings. A minimal working setup can be achieved by running the *setup.sh* script in the
`Docker-Cluster-Setup <https://github.com/curious-containers/docker-cluster-setup>`__ repository. Please set up
`Docker Machine <https://docs.docker.com/machine/install-machine/>`__ and
`Virtualbox <https://www.virtualbox.org/wiki/Linux_Downloads>`__ correctly before running this script.

.. code-block:: bash

   git clone https://github.com/curious-containers/docker-cluster-setup.git
   cd docker-cluster-setup

   # Customize the variables at the top of the setup.sh script or use the defaults
   # Run the script to set up a Docker cluster and an Overlay Network with the name cc-overlay-network
   bash setup.sh

   # Take a look at the Docker cluster installation
   docker-machine ls


The following figure shows a possible setup of Curious Containers with Docker Swarm.

|

.. image:: _static/images/cluster.*

|


CC-Server Installation (manual)
-------------------------------

*The following guide shows manual installation steps for CC-Server. For an easier deployment with docker-compose, skip
to the* `docker-compose deployment guide <admin.html#cc-server-deployment-docker-compose>`__ *below.*

The following installation instructions work with Ubuntu, but can be customized for other Linux operating systems.

Ubuntu Packages
^^^^^^^^^^^^^^^

.. code-block:: bash

   sudo apt-get install python3-pip libssl-dev libffi-dev


Python 3 Packages
^^^^^^^^^^^^^^^^^

It is recommended to install the Python packages globally for a certain system user, but without root privileges.

.. code-block:: bash

   pip3 install --user --upgrade toml jsonschema zmq requests pymongo docker-py flask gunicorn cryptography


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

   git clone -b 0.11 --depth 1 https://github.com/curious-containers/cc-server
   cd cc-server


Configuration
^^^^^^^^^^^^^

*The following commands assume being inside the cc-server directory.*

CC-Server uses `flask <http://flask.pocoo.org/>`__ to run a web server providing a REST interface. Since *flask*
implements the Python `WSGI <https://www.python.org/dev/peps/pep-0333/>`__ standard, different configuration options are
available. All configuration have in common, that exactly one instance of **cc_server_log** (zmq logging server for all
other process) and one instance of **cc_server_master** (zmq server for managing cluster resources) should be running.
The REST interface is provided by the **cc_server_web** module. Mutliple instances of this module can be running at any
time. It is advised to employ **gunicorn** or Apache2 with **mod-wsgi-py3** or other external WSGI servers. These servers
have multiprocessing/multithreading capabilities and therefore provide better performance than the integrated development
server in flask/werkzeug.

First create a config.toml file. Visit the `TOML specification <https://github.com/toml-lang/toml>`__ for further
information on the file format. Use one of the included sample configuriation as a starting point. If you are connecting
CC-Server to a local docker-engine:

.. code-block:: bash

   cp sample_local_docker_config.toml config.toml


Else, if you are connecting CC-Server to a Docker cluster:

.. code-block:: bash

   cp sample_docker_cluster_config.toml config.toml


Else, if you are connection CC-Server to a Docker cluster created with **docker-machine**:

.. code-block:: bash

   cp sample_docker_machine_config.toml config.toml


server_web
""""""""""

.. code-block:: toml

   [server_web]
   external_url = 'http://172.17.0.1:8000'
   bind_host = '127.0.0.1'
   bind_port = 8000
   num_workers = 4


+---------------+------------------+-----+--------------------------------------------------------------------+
| name          | type             | req | description                                                        |
+===============+==================+=====+====================================================================+
| external_url  | string           | yes | | Containers started by cc_server_master will send                 |
|               |                  |     | | callbacks to this url. Useful values are:                        |
|               |                  |     | | **http://172.17.0.1:8000** (local docker-engine)                 |
|               |                  |     | | **https://domain.tld/cc** (through proxy, e.g. Apache2)          |
+---------------+------------------+-----+--------------------------------------------------------------------+
| bind_host     | string           | yes | | Server binds to this host. Useful values are:                    |
|               |                  |     | | **127.0.0.1** (accessible via loopback interface)                |
|               |                  |     | | **0.0.0.0** (accessible via all interfaces,                      |
|               |                  |     | | e.g. for docker-compose)                                         |
+---------------+------------------+-----+--------------------------------------------------------------------+
| bind_port     | integer          | yes | | Server binds to this port.                                       |
+---------------+------------------+-----+--------------------------------------------------------------------+
| num_workers   | integer          | no  | | Used by gunicorn to start multiple worker processes.             |
|               |                  |     | | Default is **multiprocessing.cpu_count()**.                      |
+---------------+------------------+-----+--------------------------------------------------------------------+


server_master
"""""""""""""

.. code-block:: toml

   [server_master]
   external_url = 'tcp://localhost:8001'
   bind_host = '127.0.0.1'
   bind_port = 8001
   scheduling_interval_seconds = 60


+-----------------------------+------------------+-----+------------------------------------------------------+
| name                        | type             | req | description                                          |
+=============================+==================+=====+======================================================+
| external_url                | string           | yes | | cc_server_web will send zmq messages to this url.  |
|                             |                  |     | | Useful values are:                                 |
|                             |                  |     | | **tcp://localhost:8001**                           |
|                             |                  |     | | **tcp://cc-server-master:8001** (docker-compose)   |
+-----------------------------+------------------+-----+------------------------------------------------------+
| bind_host                   | string           | yes | | Server binds to this host. Useful values are:      |
|                             |                  |     | | **127.0.0.1** (accessible via loopback interface)  |
|                             |                  |     | | **0.0.0.0** (accessible via all interfaces,        |
|                             |                  |     | | e.g. for docker-compose   )                        |
+-----------------------------+------------------+-----+------------------------------------------------------+
| bind_port                   | integer          | yes | | Server binds to this port.                         |
+-----------------------------+------------------+-----+------------------------------------------------------+
| scheduling_interval_seconds | integer          | no  | | Scheduling is performed after receiving updates    |
|                             |                  |     | | via zmq. In addition, the scheduler can be started |
|                             |                  |     | | periodically by setting this scheduling interval   |
+-----------------------------+------------------+-----+------------------------------------------------------+


server_log
""""""""""

.. code-block:: toml

   [server_log]
   external_url = 'tcp://localhost:8002'
   bind_host = '127.0.0.1'
   bind_port = 8002
   log_dir = '~/.cc_server/logs/'
   suppress_stdout = false


+-----------------------------+------------------+-----+------------------------------------------------------+
| name                        | type             | req | description                                          |
+=============================+==================+=====+======================================================+
| external_url                | string           | yes | | cc_server_web and cc_server_master will send zmq   |
|                             |                  |     | | messages to this url. Useful values are:           |
|                             |                  |     | | **tcp://localhost:8002**                           |
|                             |                  |     | | **tcp://cc-server-log:8002** (docker-compose)      |
+-----------------------------+------------------+-----+------------------------------------------------------+
| bind_host                   | string           | yes | | Server binds to this host. Useful values are:      |
|                             |                  |     | | **127.0.0.1** (accessible via loopback interface)  |
|                             |                  |     | | **0.0.0.0** (accessible via all interfaces,        |
|                             |                  |     | | e.g. for docker-compose   )                        |
+-----------------------------+------------------+-----+------------------------------------------------------+
| bind_port                   | integer          | yes | | Server binds to this port.                         |
+-----------------------------+------------------+-----+------------------------------------------------------+
| log_dir                     | string           | no  | | If set, the process will write all log messages to |
|                             |                  |     | | a file in the specified folder.                    |
+-----------------------------+------------------+-----+------------------------------------------------------+
| suppress_stdout             | boolean          | no  | | If set to true, the log messages will not be       |
|                             |                  |     | | written to stdout.                                 |
+-----------------------------+------------------+-----+------------------------------------------------------+


mongo
"""""

.. code-block:: toml

   [mongo]
   username = 'ccdbAdmin'
   password = 'test'
   host = 'localhost'
   port = 27017
   db = 'ccdb'


+-----------------------------+------------------+-----+------------------------------------------------------+
| name                        | type             | req | description                                          |
+=============================+==================+=====+======================================================+
| username                    | string           | yes | | Credentials to connect to mongodb. When starting   |
|                             |                  |     | | cc_server via docker-compose, the given username   |
|                             |                  |     | | will be initially set in the database.             |
+-----------------------------+------------------+-----+------------------------------------------------------+
| password                    | string           | yes | | Credentials to connect to mongodb. When starting   |
|                             |                  |     | | cc_server via docker-compose, the given password   |
|                             |                  |     | | will be initially set in the database.             |
+-----------------------------+------------------+-----+------------------------------------------------------+
| host                        | string           | yes | | Hostname of the mongo server. Useful values are:   |
|                             |                  |     | | **localhost**                                      |
|                             |                  |     | | **mongo** (docker-compose)                         |
+-----------------------------+------------------+-----+------------------------------------------------------+
| port                        | integer          | yes | | Port number of mongo server. Userful value is:     |
|                             |                  |     | | **27017** (standard port)                          |
+-----------------------------+------------------+-----+------------------------------------------------------+
| db                          | string           | yes | | Name of the database provided by the mongo server. |
+-----------------------------+------------------+-----+------------------------------------------------------+


docker (connecting to docker-machine cluster)
"""""""""""""""""""""""""""""""""""""""""""""

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30
   net = 'cc-overlay-network'
   machines_dir = '~/.docker/machine/machines'

+-----------------------------+------------------+-----+------------------------------------------------------+
| name                        | type             | req | description                                          |
+=============================+==================+=====+======================================================+
| thread_limit                | integer          | yes | | cc_server_master will create one docker-py client  |
|                             |                  |     | | per docker-engine in a compute cluster.            |
|                             |                  |     | | This setting limits the number of concurrent calls |
|                             |                  |     | | per client, to prevent hitting bugs in docker.     |
+-----------------------------+------------------+-----+------------------------------------------------------+
| api_timeout                 | integer          | yes | | docker-py client times out after specified amount  |
|                             |                  |     | | of time, if the connected docker-engnine is not    |
|                             |                  |     | | reachable via the network.                         |
+-----------------------------+------------------+-----+------------------------------------------------------+
| net                         | string           | no  | | This setting refers to the name of a docker        |
|                             |                  |     | | overlay network. It is only necessary in cluster   |
|                             |                  |     | | configurations with multiple docker-engines        |
+-----------------------------+------------------+-----+------------------------------------------------------+
| machines_dir                | string           | no  | | This settings provides a convenient way to connect |
|                             |                  |     | | to a cluster of multiple docker-engine, which has  |
|                             |                  |     | | been set up using docker machine. Useful value is: |
|                             |                  |     | | **~/.docker/machine/machines**                     |
+-----------------------------+------------------+-----+------------------------------------------------------+


docker (connecting to local docker-engine)
""""""""""""""""""""""""""""""""""""""""""

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30

   [docker.nodes.local]
   base_url = 'unix://var/run/docker.sock'


When connecting to a local docker-engine the *net* and *machines_dir* options should not be set. In this case the
docker-engine is refered to as *docker.nodes.local*, where *local* is an arbitrary name for the given node. The
base_url refers to the local unix socket of the docker-engine.


docker (connecting to a cluster of docker-engines)
""""""""""""""""""""""""""""""""""""""""""""""""""

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30
   net = 'cc-overlay-network'

   [docker.nodes.cc-node1]
   base_url = 'tcp://192.168.99.101:2376'

   [docker.nodes.cc-node1.tls]
   verify = '/home/christoph/.docker/machine/machines/cc-node1/ca.pem'
   client_cert = [
       '/home/christoph/.docker/machine/machines/cc-node1/cert.pem',
       '/home/christoph/.docker/machine/machines/cc-node1/key.pem'
   ]
   assert_hostname = false

   [docker.nodes.cc-node2]
   base_url = 'tcp://192.168.99.102:2376'

   [docker.nodes.cc-node2.tls]
   verify = '/home/christoph/.docker/machine/machines/cc-node2/ca.pem'
   client_cert = [
       '/home/christoph/.docker/machine/machines/cc-node2/cert.pem',
       '/home/christoph/.docker/machine/machines/cc-node2/key.pem'
   ]
   assert_hostname = false


When connecting to a cluster of multiple docker-engines, without using the *machines_dir* option, every engine can
be specified separately. In this case the *net* option must be set. Every node is given an arbitrary name like
**cc-node1** and **cc-node2**. If TLS is configured for a docker-engine, the according settings are specified via
**docker.nodes.cc-node1.tls**.


defaults
""""""""

*The defaults section in the TOML configuration is for values, that usually do not need to be change in order to run
CC-Server.*


.. code-block:: toml

   [defaults.application_container_description]
   entry_point = 'python3 /opt/container_worker'


The **application_container_description** fields contain information about how to run an application container. The
images contain CC-Container-Worker, which is usually stored in the image file system at */opt/container_worker*.
The appropriate command to start the worker is given as **entry_point**. This default value can be overwritten by
specifying a different **entry_point** in a task.


.. code-block:: toml

   [defaults.data_container_description]
   image = 'docker.io/curiouscontainers/cc-image-ubuntu:0.10'
   entry_point = 'python3 /opt/container_worker'
   container_ram = 512


The **data_container_description** fields contain information about how to run a data container. CC-Image-Ubuntu and
CC-Image-Fedora are both supported as data container images. Specify the URL of one of theses images, or a customized
image, in the **image** field. The images contain CC-Container-Worker, which is usually stored in the image file system
at */opt/container_worker*. The appropriate command to start the worker is given as **entry_point**. The field
**container_ram** specifies the amount of memory for a data container in Megabytes.


.. code-block:: toml

   [defaults.data_container_description.registry_auth]
   username = 'REGISTRY_USER'
   password = 'PASSWORD'


If a custom data container image is specified in **data_container_description** and the access to this image in a Docker
registry is restricted, the appropriate **username** and **password** have to specified in **registry_auth**. The
**registry_auth** subsection should be deleted from the configuration file if not required.


.. code-block:: toml

   [defaults.scheduling_strategies]
   container_allocation = 'spread'


Changing the scheduling behaviour of CC-Server can be achieved by changing the values the **scheduling_strategies**
subsection. Currently only the **container_allocation** strategy can be changed. The value of **container_allocation** must
be either *spread* or *binpack*. The *spread* strategy allocates a new container on a Swarm Node with the highest amount
of free RAM and *binpack* allocates a new container on a Swarm Node with the lowest amount of free RAM still suitable for
the container.


.. code-block:: toml

   [defaults.error_handling]
   max_task_trials = 3
   dead_node_invalidation = true


CC-Server is fault tolerant, in the sense that faulty tasks are automatically restarted. Sometimes a restart will not fix
the problem, because the task configuration is wrong or a resource is not available. In order to avoid infite restart
loops, the number of restarts must be limited by setting the **max_task_trials** value in the **error_handling** subsection.
The **dead_node_validation** field should be set to *true* for improved error handling. If a node in the Docker cluster
is not responding or behaving incorrect, these errors will be detected and the node will be ignored by the CC-Server
scheduler.


.. code-block:: toml

   [defaults.error_handling.dead_node_notification]
   url = 'https://my-domain.tld/cluster'
   auth = {'auth_type' = 'basic', 'username' = 'admin', 'password' = 'PASSWORD'}


If **dead_node_invalidation** is set to *true*, an entirely optional notification mechanism can be activated. This
**dead_node_notification** will send an HTTP POST request, containing a JSON object with the **name** of the
corresponding cluster node, to the specified **url**. Setting authentication information in the **auth** field is
optional. Remove the complete **dead_node_invalidation** section from the config file if not required.


.. code-block:: toml

   [defaults.authorization]
   num_login_attempts = 3
   block_for_seconds = 120
   tokens_valid_for_seconds = 172800


The authorization module of CC-Server provides mechanism to avoid API exploitation. After a certain number of login attemps
with wrong user credentials, the authorization for this user will be blocked for a certain amount of time. These values
can be set as **number_login_attempts** and **block_for_seconds** in the **authorization** subsection. A user can request
a login token, which can be used instead of the original password for a certain amount of time specified as
**tokens_valid_for_seconds**.


Create User Accounts
^^^^^^^^^^^^^^^^^^^^

Users can be created with an interactive script. Run the *create_user* script and follow the instructions. The script
asks if admin rights should be granted to the user. Admin users can query and cancel tasks of other users via the REST
API, while standard users only get access to their own tasks.

.. code-block:: bash

   python3 scripts/create_user


Run the Code
^^^^^^^^^^^^

*The following commands assume being inside the cc-server directory.*

Running the application as specified below will run an insecure and single-threaded flask development server, which is
for development and testing purposes only. The server will be running on the **internal_port** specified in
*config.toml* (e.g. localhost:5000)

.. code-block:: bash

   scripts/start_cc_server


CC-Server will try to find the *config.toml* automatically. It will first look inside the system users home directory
(*~/.config/curious-containers/config.toml*). If the configuriation file is not there, it will try to find the
*config.toml* file in the source code directory of CC-Server (*/PATH/TO/cc-server/config.toml*).

If these locations are not suitable for the configuration file, the file path can be defined explicitely as a CLI
argument:

.. code-block:: bash

   scripts/start_cc_server /PATH/TO/my_config.toml


CC-Server Deployment (docker-compose)
-------------------------------------

*The following commands assume being inside the cc-server directory.*

Change to the compose directory and copy the sample configuration files to this directory. *config.toml* contains
the usual CC-Server settings as described in the `configuration chapter <admin.html#configuration>`__ above.
*credentials.toml* contains a **username** and **password** for an administrator user, which will be initialized
automatically, when starting CC-Server via docker-compose. For security reasons, these credentials must be changed,
before deploying CC-Server. *docker-compose.yml* describes the dependencies between various server components. If
any of these components are not needed or being deployed without docker-compose, they can be removed from the file.
Components specified in *docker-compose.yml*, which are not strictly required, are *dind* (if an external docker-engine
or cluster is used), *registry* (if an external docker registry is used) and *file-server* (which is mostly useful for
development).

.. code-block:: bash

   cd compose
   cp config_samples/config.toml .
   cp config_samples/credentials.toml .
   cp config_samples/docker-compose.yml .


Make sure `docker-compose <https://github.com/docker/compose/releases>`__ is installed. Use the scripts provided in the
*scripts* folder to start and stop CC-Server.

.. code-block:: bash

   scripts/start_cc_server
   scripts/stop_cc_server


The docker-compose deployment of CC-Server can also be registered as a system service with systemd. Go back to the
*cc-server* directory and run the *create_systemd_unit_file* script to automatically create a systemd unit file.

.. code-block:: bash

   # change directory from compose to cc-server
   cd ..

   # create systemd unit file
   sudo compose/scripts/create_systemd_unit_file -d $(pwd)

   # enable cc-server to automatically run it on system startup
   systemctl enable cc-server

   # start cc-server
   systemctl start cc-server


If the server configuration in the *config.toml* has not been changed, the CC-Server REST interface will be available
at *http://localhost:8000* All persitent data of the server components is stored at *~/.cc_server_compose*.


Apache2 TLS Proxy
^^^^^^^^^^^^^^^^^

The following Apache2 configuration enables a basic TLS proxy for CC-Server. First install Apache2 and enable the
required modules.

.. code-block:: bash

   sudo apt update
   sudo apt install apache2
   sudo a2enmod ssl
   sudo a2enmod proxy_http


Create an Apache2 site file at **/etc/apache2/sites-available/cc-server.conf** and add the following content:

.. code-block:: apache

   Listen 443

   <VirtualHost *:443>
       ServerName domain.tld

       SSLEngine On
       SSLCertificateFile /PATH/TO/cert.pem
       SSLCertificateKeyFile /PATH/TO/key.pem
       SSLCertificateChainFile /PATH/TO/chain.pem

       ProxyRequests Off
       ProxyPass /cc http://localhost:8000
       ProxyPassReverse /cc http://localhost:8000
   </VirtualHost>


**IMPORTANT NOTE:** This is not the most secure configuration possible, but only a simplified example. For more
information take a look at the following resources:
`Apache 2 SSL <https://httpd.apache.org/docs/current/ssl/>`__,
`Mozilla Server Side TLS <https://wiki.mozilla.org/Security/Server_Side_TLS>`__,
`Mozilla TLS Configuration <https://wiki.mozilla.org/Security/TLS_Configurations>`__

Enable the site file and restart Apache2.

.. code-block:: bash

   sudo a2ensite cc-server
   sudo systemctl restart apache2


CC-Server is now ready to use at *https://domain.tld/cc/*. Make sure to adapt the CC-Server configuration, to include
the new external url. Edit */PATH/TO/cc-server/compose/config.toml* and change the value of **web_server.external_url**
to **https://domain.tld/cc**.


Docker Registry
---------------

Container images created by users have to be deployed to a Docker registry. The official
`Docker Hub registry <https://hub.docker.com/>`__ with free public repositories or a paid plan for private repositories can
be used. Consider deploying a private Docker repository in order to provide free private repositories to your users.
Instructions can be found in the official `Docker Registry documentation <https://docs.docker.com/registry/deploying/>`__.


Web User Interface
------------------

The web interface CC-UI is an optional component and can be used to quickly access information about task groups, tasks,
application containers and data containers. The following instructions describe the deployment process with Apache 2,
assuming that the Apache web server is already set up with CC-Server running at *https://domain.tld/cc/*.

First edit the Apache configuration to contain the desired deployment directory (e.g. */PATH/TO/cc-ui*). Remember to
restart the web server afterwards.

.. code-block:: apache

   Listen 443

   <VirtualHost *:443>
       ServerName domain.tld

       SSLEngine On
       SSLCertificateFile /PATH/TO/cert.pem
       SSLCertificateKeyFile /PATH/TO/key.pem
       SSLCertificateChainFile /PATH/TO/chain.pem

       ProxyRequests Off
       ProxyPass /cc http://localhost:8000
       ProxyPassReverse /cc http://localhost:8000

       DocumentRoot /PATH/TO/cc-ui
       <Directory /PATH/TO/cc-ui>
           Require all granted
       </Directory>
   </VirtualHost>


Install **nodejs** and **npm** on your platform and run the following commands.

.. code-block:: bash

   git clone https://github.com/curious-containers/cc-ui.git
   cd cc-ui

   touch src/config.js
   npm install
   npm update
   npm run build


The *build* directory contains the generated HTML and JavaScript files. Copy the files to your deployment directory and
fix the file permissions for Apache.

.. code-block:: bash

   cp -R ./build /PATH/TO/cc-ui
   chown -R www-data:www-data /PATH/TO/cc-ui


CC-UI is now ready to use at *https://domain.tld/*.


Configuration
^^^^^^^^^^^^^

In the case, that CC-Server is not deployed at *https://domain.tld/cc/*, the location can be configured in the
**src/config.js** file.

.. code-block:: javascript

   export const host = 'https://domain.tld/path/to/cc/'


**IMPORTANT NOTE:** A Browser will not send REST requests to the CC-Server backend, if the protocol, ip/domain or port
are different from your CC-UI deployment. Take a look at `CORS <https://www.w3.org/TR/cors/>`__ and configure Apache to
accept cross-origin requests. This may affect the security of CC-UI (although CC-UI does not set cookies).
