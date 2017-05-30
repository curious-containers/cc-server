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

CC-Server uses `flask <http://flask.pocoo.org/>`__ to run a web server providing a REST interface. Since *flask*
implements the Python `WSGI <https://www.python.org/dev/peps/pep-0333/>`__ standard, different configuration options are
available. All configuration have in common, that exactly one instance of **cc_server_log** and one instance of
**cc_server_master** should be running. The **cc_server_web** can be executed via **gunicorn**, Apache2 with
**mod-wsgi-py3** or other external WSGI servers. These servers have multiprocessing/multithreading capabilities and
therefore provide better performance than the development server integrated in flask/werkzeug.

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


+---------------+------------------+-----+------------------------------------------------------------------+
| name          | type             | req | description                                                      |
+===============+==================+=====+==================================================================+
| external_url  | string           | yes | | Containers started by cc_server_master will send               |
|               |                  |     | | callbacks to this url. Useful values are:                      |
|               |                  |     | | **http://172.17.0.1:8000** (local docker-engine config)        |
|               |                  |     | | **https://domain.tld/cc** (through proxy, e.g. Apache2)        |
+---------------+------------------+-----+------------------------------------------------------------------+
| bind_host     | string           | yes | | Server binds to this host. Useful values are:                  |
|               |                  |     | | **127.0.0.1** (accessible via loopback interface)              |
|               |                  |     | | **0.0.0.0** (accessible via all interfaces,                    |
|               |                  |     | | e.g. docker-compose config)                                    |
+---------------+------------------+-----+------------------------------------------------------------------+
| bind_port     | integer          | yes | | Server binds to this port.                                     |
+---------------+------------------+-----+------------------------------------------------------------------+
| num_workers   | integer          | no  | | Used by gunicorn to start multiple worker processes.           |
|               |                  |     | | Default is **multiprocessing.cpu_count()**.                    |
+---------------+------------------+-----+------------------------------------------------------------------+


server_master
"""""""""""""

.. code-block:: toml

   [server_master]
   external_url = 'tcp://localhost:8001'
   bind_host = '127.0.0.1'
   bind_port = 8001
   scheduling_interval_seconds = 60


+-----------------------------+------------------+-----+---------------------------------------------------------------+
| name                        | type             | req | description                                                   |
+=============================+==================+=====+===============================================================+
| external_url                | string           | yes | | cc_server_web will send zmq messages to this url.           |
|                             |                  |     | | Useful values are:                                          |
|                             |                  |     | | **tcp://localhost:8001**                                    |
|                             |                  |     | | **tcp://cc-server-master:8001** (docker-compose config)     |
+-----------------------------+------------------+-----+---------------------------------------------------------------+
| bind_host                   | string           | yes | | Server binds to this host. Useful values are:               |
|                             |                  |     | | **127.0.0.1** (accessible via loopback interface)           |
|                             |                  |     | | **0.0.0.0** (accessible via all interfaces,                 |
|                             |                  |     | | e.g. docker-compose config)                                 |
+-----------------------------+------------------+-----+---------------------------------------------------------------+
| bind_port                   | integer          | yes | | Server binds to this port.                                  |
+-----------------------------+------------------+-----+---------------------------------------------------------------+
| scheduling_interval_seconds | integer          | yes | | TODO                                                        |
+-----------------------------+------------------+-----+---------------------------------------------------------------+


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
