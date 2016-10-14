User Documentation
==================

This user documentation contains information about how to schedule a task with CC-Server to run the CC-Sample-App and
how to build a custom Docker images containing arbitrary applications.

CC-Sample-App
-------------

*The following commands assume that docker-engine is installed on the users machine. Take a look at the*
`Administrator documentation <admin.html#docker-installation>`__ *for more information.*

The CC-Sample-App is a containerized application, which is compatible with CC-Server because it is based on
CC-Image-Ubuntu. There are several CC-Image flavors, that can be used as a base image for application containers.
They contain the Python code of CC-Container-Worker.

The source code of the images can be found on Github. All images have been uploaded to Docker Hub. The follwoing table
contains the corresponding web links and how to refer to the image when using docker-engine or a Dockerfile.

======================  =========================================================================  ===================================================================================  ==================================================
Image            Code                                                                              Registry                                                                             Docker URL
======================  =========================================================================  ===================================================================================  ==================================================
CC-Sample-App           `Github <https://github.com/curious-containers/cc-sample-app>`__           `Docker Hub <https://hub.docker.com/r/curiouscontainers/cc-sample-app/>`__           docker.io/curiouscontainers/cc-sample-app
CC-Image-Ubuntu         `Github <https://github.com/curious-containers/cc-image-ubuntu>`__         `Docker Hub <https://hub.docker.com/r/curiouscontainers/cc-image-ubuntu/>`__         docker.io/curiouscontainers/cc-image-ubuntu
CC-Image-Fedora         `Github <https://github.com/curious-containers/cc-image-fedora>`__         `Docker Hub <https://hub.docker.com/r/curiouscontainers/cc-image-fedora/>`__         docker.io/curiouscontainers/cc-image-fedora
CC-Image-Debian         `Github <https://github.com/curious-containers/cc-image-debian>`__         `Docker Hub <https://hub.docker.com/r/curiouscontainers/cc-image-debian/>`__         docker.io/curiouscontainers/cc-image-debian
CC-Image-Debian-Matlab  `Github <https://github.com/curious-containers/cc-image-debian-matlab>`__  `Docker Hub <https://hub.docker.com/r/curiouscontainers/cc-image-debian-matlab/>`__  docker.io/curiouscontainers/cc-image-debian-matlab
======================  =========================================================================  ===================================================================================  ==================================================

The CC-Sample-App contains the bash script *algorithm.sh* which is a minimal program that can be executed by
CC-Container-Worker. As can be seen in the source code of *algorithm.sh* below, the script does two different things.
It first copies the file *data.txt* from the *input_files* directory to the *result_files* directory. The second
command takes the CLI arguments *${@}* and writes them to the *parameters.txt* file.

.. code-block:: bash

   cp /home/ubuntu/input_files/data.txt /home/ubuntu/result_files/data.txt
   echo ${@} > /home/ubuntu/result_files/parameters.txt


The algorithm assumes to find one input file at a specific location in the local file system of the container image.
In addition both result files are written to the file system at specific locations. Since the *algorithm.sh* script will
be executed by CC-Container-Worker it is necessary to inform the worker about the locations of the
input file and the result files by creating a *config.toml* file as shown below. The field **application_command** defines
that the script will be executed with the bash interprated and that it is located in the system users home directory.
The **local_input_files** and **local_result_files** fields each contain a list with dictionaries describing the file
locations. It is not necessary that the given directories already exist, because they will be created by the
CC-Container-Worker. The worker software will throw an error, if a specified result file is not created by the application.
Result files can be marked as **optional**, in order to avoid this behaviour.

.. code-block:: toml

   [main]
   application_command = 'bash /home/ubuntu/algorithm.sh'
   local_input_files = [{
       'dir' = '/home/ubuntu/input_files',
       'name' = 'data.txt'
   }]
   local_result_files = [{
       'dir' = '/home/ubuntu/result_files',
       'name' = 'data.txt'
   }, {
       'dir' = '/home/ubuntu/result_files',
       'name' = 'parameters.txt',
       'optional' = true
   }]


In order to create the CC-Sample-App it is necessary to build a Docker image, containing *algorithm.sh* and *config.toml*.
For this purpose a Dockerfile must be defined as follows. The **FROM** statement defines the base image, in this case
CC-Image-Ubuntu was chosen. The first **COPY** statement copies *config.toml* to the */opt* directory in the container images
file system. This path cannot be changed, because CC-Container-Worker assumes the file to be at this specific location.
The second **COPY** statement copies the application *algorithm.sh* to the location previously defined in *config.toml*
via **application_command**.

.. code-block:: docker

   FROM docker.io/curiouscontainers/cc-image-ubuntu:0.2
   COPY config.toml /opt/config.toml

   COPY algorithm.sh /home/ubuntu/algorithm.sh


The image is built from the Dockerfile by running the *docker build*. The git repository of the CC-Sample-App contains a bash
script *build.sh*, which contains the necessary steps and defines the **REGISTRY_URL** of the image. When forking
CC-Sample-App for a custom image, this URL must be changed to something else. Login to the desired Docker registry with
*docker login* before running this script.

.. code-block:: bash

   REGISTRY_URL=docker.io/curiouscontainers/cc-sample-app

   docker pull docker.io/curiouscontainers/cc-image-ubuntu:0.1
   docker pull ${REGISTRY_URL}
   docker build -t ${REGISTRY_URL} .
   docker push ${REGISTRY_URL}


Please take a look at the official `Docker Build documentation <https://docs.docker.com/engine/reference/builder/>`__
to fully understand the build process and Docker registries.


Schedule a Task
^^^^^^^^^^^^^^^

*The following instructions assume, that CC-Server has been setup beforehand. If not, either follow the*
`manual installation steps <admin.html>`__ *in the administrator documentation or*
`setup CC-Server via Docker Compose <developer.html#docker-compose>`__ *as described in the developer documentation.*

This part of the documentation explains how to schedule a task with CC-Server. A task is a JSON object, which is send
to the CC-Server API, containing information about how to run a compatible Docker image (e.g. CC-Sample-App). The script
below shows how to send such a request with Python. More detailed information about the JSON fields can be found in the
accompanied `API documentation <api.html#post--tasks>`__.

Install the Python *requests* package:

.. code-block:: bash

   sudo apt-get install python3-pip
   pip3 install --user --upgrade requests


Modify and run the following Python 3 code:

.. code-block:: python

   import json
   import requests

   username = 'admin'
   password = 'PASSWORD'

   task = {
       "tags": ["experiment1"],
       "no_cache": true,
       "application_container_description": {
           "image": "docker.io/curiouscontainers/cc-sample-app",
           "container_ram": 1024,
           "parameters": ["--arg1", "value1", "--arg2", "value2"]
       },
       "input_files": [{
           "ssh_host": "my-domain.tld",
           "ssh_username": "ccdata",
           "ssh_password": "PASSWORD",
           "ssh_file_dir": "/home/ccdata/input_files",
           "ssh_file_name": "some_data.csv"
       }],
       "result_files": [{
           "ssh_host": "my-domain.tld",
           "ssh_username": "ccdata",
           "ssh_password": "PASSWORD",
           "ssh_file_dir": "/home/ccdata/result_files",
           "ssh_file_name": "some_data.csv"
       }, {
           "ssh_host": "my-domain.tld",
           "ssh_username": "ccdata",
           "ssh_password": "PASSWORD",
           "ssh_file_dir": "/home/ccdata/result_files",
           "ssh_file_name": "parameters.txt"
       }]
   }

   requests.post('https://cc.my-domain.tld/tasks', json=task, auth=(username, password))


In the *config.toml* file of the CC-Sample-App one input file and two result files have been defined. The purpose of Curious
Containers is, to run applications with arbitrary inputs and outputs. Therefore the task JSON object must contain
information about input file sources and result file destinations. The input file downloads and result file uploads are
executed by the CC-Container-Worker in a running container.

The worker connects to the remote data archive, downloads the input files and stores them at the location defined in
*config.toml* in the containers file system. The first element in the **input_files** list of the task maps to the first
element of the **local_input_files** list of the *config.toml* file. The same holds for all other elements in
the list, as well as for the **result_files** and **local_result_files** lists. Since this describes a *one-to-one*
element mapping of two lists, it is required that as many **input_files** and **result_files** are defined in the task,
as defined in the respective **local_input_files** and **local_result_files** lists.

Data Connectors for Input Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Data Connectors are implemented in CC-Container-Worker. This section describes the currently available connectors for
downloading input files. The data source must be reachable from the container. The easiest way to achieve this, is to
expose the data source to the internet. More advanced routing configurations may be possible, but are not discussed here.
The data connectors use the information specified in a tasks **input_files** list.

SFTP via SSH (Recommended)
""""""""""""""""""""""""""

This connector uses an SSH tunnel to transfer files via the SFTP protocol. This data connector is recommended, because
it is the easiest way to configure a secure file server, that can be exposed to the internet if required. Create a new
system user (e.g *ccdata*) with a strong password on a server and enable ssh access with password authentication.
The user should only have access to the users home directory. Place the files that should be accessible in this directory.
Specify the mandatory JSON fields **ssh_host**, **ssh_username**, **ssh_password**, **ssh_file_dir** and **ssh_file_name**.

.. code-block:: json

   {
       "ssh_host": "my-domain.tld",
       "ssh_username": "ccdata",
       "ssh_password": "PASSWORD",
       "ssh_file_dir": "/home/ccdata/input_files",
       "ssh_file_name": "some_data.csv"
   }


HTTP
""""

*The exact behaviour of the HTTP data connector depends on implementation details of the source HTTP server.*

It is possible to download input files from a web server via an HTTP GET request. The only required field is
**http_url** pointing to a server resource. A string with additional JSON data can be set with the **http_data** field,
but is not required. The optional field **http_auth** can either contain **basic_username** and **basic_password** to
enable *HTTPBasicAuth* or **digest_username** and **digest_password** to enable *HTTPDigestAuth*.

.. code-block:: json

   {
       "http_url": "https://my-domain.tld/input_files/some_data.csv",
       "http_data": {
           "key1": "value1",
           "key2": "value2"
       },
       "http_auth": {
           "basic_username": "ccdata",
           "basic_password": "PASSWORD"
       }
   }

Data Connectors for Result Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Data Connectors are implemented in CC-Container-Worker. This section describes the currently available connectors for
uploading result files. The destination server must be reachable from the container. The easiest way to achieve this, is to
expose the server to the internet. More advanced routing configurations may be possible, but are not discussed here.
The data connectors use the information specified in a tasks **result_files** list.

SFTP via SSH (Recommended)
""""""""""""""""""""""""""

This data connector for uploading result files works exactly like the
`equivalent data connector for input files <#sftp-via-ssh-recommended>`__. The destination **ssh_file_dir** will be
created by the data connector if it is not yet existent. Already existing files will be overwritten.

.. code-block:: json

   {
       "ssh_host": "my-domain.tld",
       "ssh_username": "ccdata",
       "ssh_password": "PASSWORD",
       "ssh_file_dir": "/home/ccdata/result_files",
       "ssh_file_name": "some_data.csv"
   }


HTTP
""""

*The exact behaviour of the HTTP data connector depends on implementation details of the destination HTTP server.*

This data connector can be used to upload result files to a web server via an HTTP POST request. The only required field
is **http_url** pointing to a server resource. The optional field **http_auth** can either contain **basic_username**
and **basic_password** to enable *HTTPBasicAuth* or **digest_username** and **digest_password** to enable
*HTTPDigestAuth*. The file will be uploaded with the *application/octet-stream* content type. A file name that is sent
to the destination server alongside the actual file must be specified in the **http_file_name** field.

.. code-block:: json

   {
       "http_url": "https://my-domain.tld/result_files/some_data.csv",
       "http_file_name": "some_data.csv",
       "http_auth": {
           "basic_username": "ccdata",
           "basic_password": "PASSWORD"
       }
   }


JSON via HTTP
"""""""""""""

Instead of uploading a file, it is possible to upload result values in a JSON object via an HTTP POST request. In order
to use this feature, the application running in the container must write a JSON encoded string to a file. The JSON data
connector will read the contents from the file and decode the JSON data. If some additional data is specified in the
**json_data** field, the respective key-value pairs will be added to the JSON data produced by the application. The
resulting JSON data will be send to an HTTP server specified in the mandatory **json_url** field. The optional field
**json_auth** can either contain **basic_username** and **basic_password** to enable *HTTPBasicAuth* or
**digest_username** and **digest_password** to enable *HTTPDigestAuth*.

.. code-block:: json

   {
       "json_url": "https://my-domain.tld/result_json/",
       "json_data": {
           "key1": "value1",
           "key2": "value2"
       },
       "json_auth": {
           "basic_username": "ccdata",
           "basic_password": "PASSWORD"
       }
   }


CLI Parameters
^^^^^^^^^^^^^^

Running an application in a container with certain parameters can be achieved by setting a JSON object with key-value
pairs or a JSON array in the **parameters** field of **application_container_description** in a task.

The following example shows a JSON object, which contains strings, numbers, objects and arrays.

.. code-block:: json

   {
       "parameters": {
           "--arg1": "value1",
           "arg2": 3.14,
           "--arg3": {
               "number": 42,
               "bool": false
           },
           "arg4": [
               2.71,
               "e"
           ]
       }
   }


Since the parameters have been defined as a JSON object, the CC-Container-Worker will convert it to a JSON encoded string.
This string is then appended to the **application_command** as the first CLI argument and results in the following call
of a *algorithm.py* script.

.. code-block:: bash

   python3 algorithm.py '{"arg4": [2.71, "e"], "arg2": 3.14, "--arg3": {"number": 42, "bool": false}, "--arg1": "value1"}'


This is useful for programs written in a language that provides a JSON parser (e.g. Python). In the *algorithm.py*
script this could be parsed as shown in the following Python code.

.. code-block:: python

   import sys
   import json

   parameters = json.loads(sys.argv[1])


If parsing a JSON encoded string is not a viable option, a JSON array can be passed to the parameters field instead.

.. code-block:: json

   {
       "parameters": ["--arg1", "value1", "--arg2", 3.14]
   }

As a result, the program call contains distinct CLI arguments.

.. code-block:: bash

  bash algorithm.sh --arg1 value1 --arg2 3.14


This is useful for shell scripts like *algorithm.sh*, which do not provide a JSON parser.


Building an App Container
-------------------------

When building a compatible app container, it is advised to start with the
`CC-Sample-App code <https://github.com/curious-containers/cc-sample-app>`__ and modify it.

The following steps guide you through the customizing process:

1. Change the **REGISTRY_URL** in the *build.sh* file. The URL should point to a registry and group you have access to.
2. If the application should be based on a CC-Image other than CC-Image-Ubuntu, the appropriate URL must be given in *build.sh* and in the *Dockerfile*.
3. Instead of copying *algorithm.sh* to the container, modify the Dockerfile to include all necessary scripts, binaries and dependencies of your own application.
4. Modify the *config.toml* file to include only input files required by the application and only result files that will be uploaded to a remote data archive as soon as the application terminates. Temporary or intermediate result files must not be included in this list.
5. Modify the **application_command** in *config.toml* to point at the application that will be invoked by CC-Container-Worker.
6. Make sure that the *config.toml* will be copied to the */opt* directory in the *Dockerfile*.

The **application_command** syntax might not be sufficient for all use cases. For example the application might
handle CLI arguments in a certain way not provided by the CC-Container-Worker, the application might use pipes for the
data intput/output or the application consists of multiple binaries that should be invoked. In these cases it is
advised to write a wrapper shell script to handle the custom behaviour.


Deployment
^^^^^^^^^^

In order to deploy the application and make it available to the Curious Containers software it is necessary to build
a Docker image from the previously specified Dockerfile and to push the image to a Docker registry. Run the *build.sh*
file for this purpose. Usually the *docker pull* and/or *push* commands in *build.sh* can only access the desired
registry if the user is logged in. Run *docker login registry.my-domain.tld* (for a private registry) or *docker login*
(for Docker Hub) before executing *build.sh*.

Input File Cache
----------------

If several tasks are started in parallel and these tasks require the same input files from a remote data archive, it is
advised to set the **no_cache** option for all tasks to *false* (which is the default behaviour). In this case before the
application containers are executed, a data container will be started as an input file cache. This data container will
download the input files from the remote data archive once. As soon as the files are downloaded, the application containers
will be started and retrieve their input files from this data container. This should speed up the file downloads, because
all data transfer is handled in the container network and not via the internet. The CC-Server will assure, that application
containers can only gain access to the files specified in their task description, by providing secret keys for each input
file to the application container. The data container will verify these keys before serving the files. A data container
will be deleted as soon as all depending application containers have terminated.

The sequence diagram below shows the caching behaviour controlled by the CC-Server.

|

.. image:: _static/images/sequence.*
