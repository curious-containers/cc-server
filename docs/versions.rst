Version Management
==================

This site contains a Docker compatibility table and a change log, including migration instructions.

All Curious Container components (CC-Server, CC-Container-Worker and the CC-Images) have a version tag.
If you are using CC-Server 0.3 for example, you should use the other components with the exact same version number.
Docker images with a specific version tag can be pulled from a Docker registry and software versions with a certain tag
can be pulled from git.

*When migrating to a newer CC-Server version, rebuild your custom Docker images with the respective CC-Image.*

Docker Compatibility
--------------------

===========  =========
CC-Server    Docker
===========  =========
0.1          12
0.2          12
0.3          12
0.4          12
===========  =========

Change Log
----------

Version 0.4 (in development)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- CC-Server user API changed, to be HTTP standard compliant

Version 0.3
^^^^^^^^^^^

- Improved GET tasks, application_containers and data_containers, by adding the ability to sort results. The API for these endpoints has changed.
- Added task groups: tasks, which have been sent via the same request, are in one group. Added a new API endpoint for this functionality.
- Added support for optional result files.

Version 0.2
^^^^^^^^^^^

- CC-Server is not compatible with the built-in swarm mode of docker-engine. CC-Server does now show an error message, if swarm mode is detected. See admin docs for more information.
- **parameters_as_json** has been removed from the *config.toml* of CC-Container-Worker. Parameters can now be defined as JSON object or JSON array to trigger the specific behavior. See user docs for more information.
- Improved ram info for local docker-engine by calculating ram usage from containers in database instead of using psutil (which is no dependency any more).
- Improved data security by removing passwords and other sensitive information from database, when not used anymore.
