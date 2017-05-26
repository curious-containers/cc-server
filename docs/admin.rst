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

   git clone -b 0.10 --depth 1 https://github.com/curious-containers/cc-server
   cd cc-server


Configuration
^^^^^^^^^^^^^

*The following commands assume being inside the cc-server directory.*

Create a config.toml file. Visit the `TOML specification <https://github.com/toml-lang/toml>`__ for further information
about the file format. Use one of the included sample configuriation as a starting point. If you are connecting
CC-Server to a local docker-engine:

.. code-block:: bash

   cp sample_local_docker_config.toml config.toml


Else, if you are connecting CC-Server to a Docker cluster:

.. code-block:: bash

   cp sample_docker_cluster_config.toml config.toml


Else, if you are connection CC-Server to a Docker cluster created with **docker-machine**:

.. code-block:: bash

   cp sample_docker_machine_config.toml config.toml


server
""""""

CC-Server uses `flask <http://flask.pocoo.org/>`__ to run a light-weight web server providing a REST interface.
When starting the server it connects to an **internal_port** with port 5000 as default value. The server is then
reachable at localhost:5000 and requests can be sent to the API. This **internal_port** should never be exposed to
internet (configure a firewall to ensure this), because flask does not by default provide TLS encryption for the HTTP
communication. The external address, specified as **host**, must be reachable by the containers spawned by CC-Server.
In the case a local docker-engine is used, the host's IP adress for the Docker Bridge interface is reachable by the
containers. Run *ifconfig* in a shell and look for the appropriate network interface (e.g. docker0) and IP
(e.g. 172.17.0.1). With this configuration it is not necessary to expose the host to the internet. It should only be
used for development and testing purposes.

Another mandatory configuration parameter is **scheduling_interval_seconds**. CC-Server will run a scheduling process
after the time specified has passed. It will only run if there are active containers in the database. This feature has
been implemented to periodically check for containers that exited unexpectedly.

An optional file logging for CC-Server can be enabled by specifying a logging directory as **log_dir**. By setting the
optional field **suppress_stdout** to *true*, printing to the standard output can be disabled. This setting works
independently of the file logging mechanism. Both output mechanisms carry the same information.

.. code-block:: toml

   [server]
   host = 'http://172.17.0.1:5000'
   internal_port = 5000
   scheduling_interval_seconds = 60
   log_dir = '~/.cc_server/'
   suppress_stdout = false


For a production setup it is recommended to use Apache2 with mod_wsgi. In this case it is not necessary to specify an
**internal_port** and it will be ignored if already set. With mod_wsgi the standard output of CC-Server is redirected to
the Apache2 error log. To prevenet polluting the error log with the standard output information, it is recommended to
set **suppress_stdout** to *true* and to specify a **log_dir** instead. The **host** must be set to the address given in
the Apache2 virtual host config. Take a look at the `Apache 2 configuration <admin.html#apache-2-wsgi>`__ below for more
information.

.. code-block:: toml

   [server]
   host = 'https://my-domain.tld/cc'
   scheduling_interval_seconds = 60
   log_dir = '~/.cc_server/'
   suppress_stdout = true


CC-Server spawns two background processes, called tee and worker, on startup. It is necessary to specify a port for
each of the processes as **tee_port** and **worker_port**. The only requirements are, that the ports are distinct from
each other, not yet occupied by another process and that the ports are not restricted (port numbers <1024 are
restricted). In addition an arbitrary **secret** must be specified, which is used to authenticate other CC-Server
processes with the background processes.

.. code-block:: toml

   [ipc]
   tee_port = 14736
   worker_port = 14737
   secret = 'SECRET'


mongo
"""""

Connect CC-Server to the previously installed MongoDB server. Assuming the database server is running the
same machine as CC-Server, the **host** is specified as localhost and the standard port is 27017. The **username**,
**password** and **db** must be changed according to the privious MongoDB settings.

.. code-block:: toml

   [mongo]
   username = 'ccdbAdmin'
   password = 'PASSWORD'
   host = 'localhost'
   port = 27017
   db = 'ccdb'


docker
""""""

CC-Server can use a local docker-engine or a Docker cluster in order to run Docker containers. If the local
docker-engine is used, **base_url** is set to *unix://var/run/docker.sock*. CC-Server is a highly parallelized
application, which spawns hundrets of threads. The number of threads, accessing the docker-engine in parallel, must be
limited by setting **thread_limit** in order to avoid severe Docker bugs (currently version 12). The default value *8*
is a reasonable choice, but higher values could speed up the processing times. In addition an optional **api_timeout**
parameter can be set, to limit the time of requests to a Docker engine. Shorter values can speed up error detection but
can on the other hand increase the likelihood of false positives.

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30

   [docker.nodes.local]
   base_url = 'unix://var/run/docker.sock'


If using a Docker cluster, the configuration becomes more complex. The **base_url** is changed to the IP and PORT of the
specific docker-engine. A Docker Overlay Network must be created beforehand and the name of the network is given as **net**.
The API of a Docker Manager is usually protected by a TLS encryption. When using Docker Machine for the Swarm setup, the
certificate files can be found in the system users home directory at *~/.docker/machine/machines*. CC-Server is using
the docker-py Python package. Take a look at the official
`docker-py documentation <http://docker-py.readthedocs.io/en/stable/tls/>`__ for more information about TLS options. Delete
the **docker.nodes.<node_name>.tls** sections from the configuration file if not required.

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30
   net = 'cc-overlay-network'

   [docker.nodes.cc-node1]
   base_url = '192.168.99.101:2376'

   [docker.nodes.cc-node1.tls]
   verify = '/home/USER/.docker/machine/machines/cc-node1/ca.pem'
   client_cert = [
       '/home/USER/.docker/machine/machines/cc-node1/cert.pem',
       '/home/USER/.docker/machine/machines/cc-node1/key.pem'
   ]
   assert_hostname = false

   [docker.nodes.cc-node2]
   base_url = '192.168.99.102:2376'

   [docker.nodes.cc-node2.tls]
   verify = '/home/USER/.docker/machine/machines/cc-node2/ca.pem'
   client_cert = [
       '/home/USER/.docker/machine/machines/cc-node2/cert.pem',
       '/home/USER/.docker/machine/machines/cc-node2/key.pem'
   ]
   assert_hostname = false


If **docker-machine** has been used to setup the cluster, the following shorthand configuration can be used. The
**machines_dir** parameter should point to a directory automatically created by docker-machine, containing subdirectories
for all cluster nodes. CC-Server will read all necessary information from the corresponding node directories and the
resuling cluster configuration should be identical to what has been specified above.

.. code-block:: toml

   [docker]
   thread_limit = 8
   api_timeout = 30
   net = 'cc-overlay-network'
   machines_dir = '~/.docker/machine/machines'


defaults
""""""""

*The defaults section in the TOML configuration is for values, that usually do not need to be change in order to run
CC-Server.*

The **application_container_description** fields contain information about how to run an application container. The
images contain CC-Container-Worker, which is usually stored in the image file system at */opt/container_worker*.
The appropriate command to start the worker is given as **entry_point**. This default value can be overwritten by
specifying a different **entry_point** in a task.

.. code-block:: toml

   [defaults.application_container_description]
   entry_point = 'python3 /opt/container_worker'


The **data_container_description** fields contain information about how to run a data container. CC-Image-Ubuntu and
CC-Image-Fedora are both supported as data container images. Specify the URL of one of theses images, or a customized
image, in the **image** field. The images contain CC-Container-Worker, which is usually stored in the image file system
at */opt/container_worker*. The appropriate command to start the worker is given as **entry_point**. The field
**container_ram** specifies the amount of memory for a data container in Megabytes.

.. code-block:: toml

   [defaults.data_container_description]
   image = 'docker.io/curiouscontainers/cc-image-ubuntu:0.10'
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
The **dead_node_validation** field should be set to *true* for improved error handling. If a node in the Docker cluster
is not responding or behaving incorrect, these errors will be detected and the node will be ignored by the CC-Server
scheduler.

.. code-block:: toml

   [defaults.error_handling]
   max_task_trials = 3
   dead_node_invalidation = true


If **dead_node_invalidation** is set to *true*, an entirely optional notification mechanism can be activated. This
**dead_node_notification** will send an HTTP POST request, containing a JSON object with the **name** of the
corresponding cluster node, to the specified **url**. Setting authentication information in the **auth** field is
optional. Remove the complete **dead_node_invalidation** section from the config file if not required.

.. code-block:: toml

   [defaults.error_handling.dead_node_notification]
   url = 'https://my-domain.tld/cluster'
   auth = {'auth_type' = 'basic', 'username' = 'admin', 'password' = 'PASSWORD'}


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

Running the application as specified below will run an insecure and single-threaded flask development server, which is
for development and testing purposes only. The server will be running on the **internal_port** specified in
*config.toml* (e.g. localhost:5000)

.. code-block:: bash

   python3 cc_server


CC-Server will try to find the *config.toml* automatically. It will first look inside the system users home directory
(*~/.config/curious-containers/config.toml*). If the configuriation file is not there, it will try to find the
*config.toml* file in the source code directory of CC-Server (*/PATH/TO/cc-server/config.toml*).

If these locations are not suitable for the configuration file, the file path can be defined explicitely as a CLI
argument:

.. code-block:: bash

   python3 cc_server /PATH/TO/my_config.toml


Apache 2 WSGI
^^^^^^^^^^^^^

*First take a look at the* `server documentation <admin.html#server>`__ *above and configure the config.toml file of
CC-Server for production usage with Apache 2.*

The following sample configuration shows how to setup Apache 2 and mod_wsgi for CC-Server. The mod_wsgi extension can
run multiple processes serving web requests with the CC-Server flask application, which improves the performace compared
to the flask development server. In addition Apache 2 should be configured to encrypt the incoming web requests with
TLS.

On Ubuntu install Apache2 and the Python3 version of mod_wsgi as follows:

.. code-block:: bash

   sudo apt update
   sudo apt install apache2 libapache2-mod-wsgi-py3
   sudo a2enmod ssl


Create a new Apache 2 site configuration file at */etc/apache2/sites-available/cc-server.conf* and copy the file content
from the code block below. Replace all occurences of */PATH/TO* with the appropriate absolute paths to the CC-Server
source code and *wsgi.py* file, as well as the SSL certificates. The configuration assumes that a system user *ccuser*
has been created beforehand and that this user has permissions to read and execute the CC-Server code and *wsgi.py*
script. This can be customized to run under any other system user, except root. The number of of processes and threads
should be customized to fit the available system resources (e.g. CPU and RAM).

.. code-block:: apache

   Listen 443

   <VirtualHost *:443>
       ServerName my-domain.tld

       SSLEngine On
       SSLCertificateFile /PATH/TO/cert.pem
       SSLCertificateKeyFile /PATH/TO/key.pem
       SSLCertificateChainFile /PATH/TO/chain.pem

       WSGIDaemonProcess cc-server user=ccuser group=ccuser processes=4 threads=16
       WSGIScriptAlias /cc /PATH/TO/cc-server/wsgi.py
       WSGIImportScript /PATH/TO/cc-server/wsgi.py process-group=cc-server application-group=%{GLOBAL}
       WSGIPassAuthorization On

       <Directory /PATH/TO/cc-server>
           <Files wsgi.py>
               WSGIApplicationGroup %{GLOBAL}
               WSGIProcessGroup cc-server
               Require all granted
          </Files>
       </Directory>
   </VirtualHost>


**IMPORTANT NOTE:** This is not the most secure configuration possible, but only a simplified example. For more
information take a look at the following resources:
`Apache 2 SSL <https://httpd.apache.org/docs/current/ssl/>`__,
`Mozilla Server Side TLS <https://wiki.mozilla.org/Security/Server_Side_TLS>`__,
`Mozilla TLS Configuration <https://wiki.mozilla.org/Security/TLS_Configurations>`__


The newly created site can now be enabled with the following commands:

.. code-block:: bash

   sudo a2ensite cc-server.conf
   sudo service apache2 restart


CC-Server is now ready to use at *https://my-domain.tld/cc/*.


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
assuming that the Apache web server is already set up with CC-Server running at *https://my-domain.tld/cc/*.

First edit the Apache configuration to contain the desired deployment directory (e.g. */PATH/TO/cc-ui*). Remember to
restart the web server afterwards.

.. code-block:: apache

   Listen 443

   <VirtualHost *:443>
       ServerName my-domain.tld

       SSLEngine On
       SSLCertificateFile /PATH/TO/cert.pem
       SSLCertificateKeyFile /PATH/TO/key.pem
       SSLCertificateChainFile /PATH/TO/chain.pem

       WSGIDaemonProcess cc-server user=ccuser group=ccuser processes=4 threads=16
       WSGIScriptAlias /cc /PATH/TO/cc-server/wsgi.py
       WSGIImportScript /PATH/TO/cc-server/wsgi.py process-group=cc-server application-group=%{GLOBAL}
       WSGIPassAuthorization On

       <Directory /PATH/TO/cc-server>
           <Files wsgi.py>
               WSGIApplicationGroup %{GLOBAL}
               WSGIProcessGroup cc-server
               Require all granted
          </Files>
       </Directory>

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


CC-UI is now ready to use at *https://my-domain.tld/*.


Configuration
^^^^^^^^^^^^^

In the case, that CC-Server is not deployed at *https://my-domain.tld/cc/*, the location can be configured in the
**src/config.js** file.

.. code-block:: javascript

   export const host = 'https://my-domain.tld/path/to/cc/'


**IMPORTANT NOTE:** A Browser will not send REST requests to the CC-Server backend, if the protocol, ip/domain or port
are different from your CC-UI deployment. Take a look at `CORS <https://www.w3.org/TR/cors/>`__ and configure Apache to
accept cross-origin requests. This may affect the security of CC-UI (although CC-UI does not set cookies).
