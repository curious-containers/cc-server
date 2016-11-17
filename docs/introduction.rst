Introduction
============

**Curious Containers** is an application management service that is able to execute thousands of short-lived applications
in an distributed cluster environment by employing Docker Swarm.

In this context applications are atomic entities taking files and parameters as input and producing new files as output.
They are short-lived in a sense that they calculate something and terminate as soon as all results have been produced.

Curious Containers supports scientific use cases like **biomedical analysis** and **reproducible research** by providing
standardized methods for packaging applications and executing them in a compute environment. Therefore application
dependencies are added to a compatible Docker container image, including all necessary scripts, binaries and
configurations.

Software Components
-------------------

The Curious Containers software consists of two main components.

CC-Server
^^^^^^^^^

CC-Server is a web service connecting to a *docker-engine* or a *Docker Swarm*. Tasks containing application
descriptions can be registered via a REST interface and the service takes care of scheduling the execution of these
tasks.

CC-Container-Worker
^^^^^^^^^^^^^^^^^^^

CC-Container-Worker is packaged inside a Docker image together with the application itself. When a container is
started the worker software is invoked. The worker takes care of all the actions that need to be performed inside the
running container. These actions include downloading input files, executing the application, collecting telemetry data
(e.g. RAM usage) and uploading result files. After each action a callback is sent to the server, informing about the
execution status and potential errors.

Features
--------

Curious Containers is designed to support the daily work of researchers and data scientists by letting them focus on
applications instead of infrastructure.

Light-Weight
^^^^^^^^^^^^

Curious Containers is an approach to provide a light-weight abstraction layer for compute clusters by completely
separating applications from the host operating system.

Fault Tolerant
^^^^^^^^^^^^^^

It aims to be fault tolerant by restarting cancelled tasks and works around bugs in Docker Swarm (e.g. Swarm
errors caused by highly parallelized API calls).

Telemetry and Meta Data
^^^^^^^^^^^^^^^^^^^^^^^

All meta data (e.g. timestamps, execution states and errors) and telemetry data from supervising applications in a
running container (e.g. RAM usage) is persisted in a database and can be analyzed.

Connecting to Data Archives
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The CC-Container-Worker is able to connect to remote data archives for downloading input files and uploading result
files via multiple data transfer protocols (e.g. sftp, http).

Caching
^^^^^^^

Curious Containers supports caching input data in so-called data containers, making the files
available in the local network as long as depending applications are running. 

Data Security
^^^^^^^^^^^^^

Since data security is a major concern when supporting biomedical use cases, the software ensures that data only
lives inside containers and that all containers (including their data files) are deleted from the compute environment
when not required any longer.

Open Source
^^^^^^^^^^^

All parts of Curious Containers are open source under the Apache 2 license.
`Contributing <developer.html#contributing>`__ to the project is appreciated but not mandatory.

Extensible Codebase
^^^^^^^^^^^^^^^^^^^

The software has a small and extensible codebase, allowing custom implementations of scheduling routines and data
connectors.

What it's not
-------------

Curious Containers is not a workflow management system. Dependencies between multiple applications cannot be
expressed, hence all applications are atomic entities. Nevertheless a separate workflow software could employ Curious
Containers as a backend.

It is not an orchestration software managing long-lived applications (e.g. web services). Therefore this software
is not directly comparable to projects like `Docker Compose <https://docs.docker.com/compose/>`__,
`Kubernetes <http://kubernetes.io/>`__ or `Apache Mesos <https://mesos.apache.org/>`__.

Questions?
----------

Feel free to post questions in the `issues area of CC-Server on Github <https://github.com/curious-containers/cc-server/issues>`__.
