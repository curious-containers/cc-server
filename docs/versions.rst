Version Management
==================

This site contains a Docker compatibility table and a change log, including migration instructions.

All Curious Container components (CC-Server, CC-Container-Worker and the CC-Images) have a version tag.
If you are using CC-Server 0.12 for example, you should use the other components with the exact same version number.
Docker images with a specific version tag can be pulled from a Docker registry and software versions with a certain tag
can be pulled from git.

*When migrating to a newer CC-Server version, rebuild your custom Docker images with the respective CC-Image.*

Change Log
----------

Version 0.12
^^^^^^^^^^^^

- Refactored Python module structure of CC-Server.
- Improved deployment (pip intallable) and scripts.
- Simplified docker-compose.yml.
- Breaking changes for various configuration, modules and script paths. Affects cc-server and cc-container-worker. Container image update is required.

Version 0.11
^^^^^^^^^^^^

- Major refactoring: using zeromq instead of stance and fully decoupled the flask processes from the master process. The code base is now split into 4 packages. The log and master processes won't start automatically now, see admin docs for updated installation instructions.
- Using gunicorn in cc-container-worker to allow for multiple processes serving files from a data container.
- Improved cluster node status checks.
- Improved compose configuration.
- Tokens are stored salted and hashed now.
- /nodes endpoint JSON format changed.
- Configuration TOML format changed.

Version 0.10
^^^^^^^^^^^^

- Added cron for running the scheduler after a specified time has passed. Therefore added new config option **scheduling_interval_seconds**.
- Removed put_worker API endpoint.
- Fixed bug with data containers, where input_files list was too large as cli parameter.
- Fixed bug where spread and binpack had the opposite meaning.

Version 0.9
^^^^^^^^^^^

- Maintenance release for bug fixes.
- Worker process logic is now in separate Python library: install stance via pip3.
- Schema validation for config.toml.

Version 0.8
^^^^^^^^^^^

- Major refactoring of CC-Server. Enabled support for multiprocess execution of CC-Server with Apache2 mod_wsgi support.
- Fixed security issue with aggregation pipelines of query requests, by having a whitelist for permitted operations.

Version 0.7
^^^^^^^^^^^

- Dropped Docker Swarm support in favor of connecting to the different docker-engines directly. This is a necessary change to improve fault tolerance with dead node invalidation in CC-Server.
- Changed config format for CC-Images from TOML to JSON. Result files are now specified as dict instead of list.
- The result files specification for tasks changed. All result files must now have a field **local_result_file** to reference the dict key of the CC-Image config.json.
- It is now possible to upload a result files multiple times to different remote locations.

Version 0.6
^^^^^^^^^^^

- This release fixes several critical bugs. Please note, that a new database will be created by default. In the CC-Server config.toml file, specify **dbname** as *db* to keep using the existing database.
- Experimental support for invalidation of dead cluster nodes
- Experimental support for tracing and sandboxing (undocumented)

Version 0.5
^^^^^^^^^^^

- Major refactoring of data connectors in CC-Container-Worker. Plugin architecture now supports custom data connectors.
- CC-Server API change to support the new data connector architecture.

Version 0.4
^^^^^^^^^^^

- CC-Server user API changed, to be HTTP standard compliant (using POST instead of GET and DELETE for endpoints with required JSON input).
- API does now return 400 (BadRequest) and 401 (Unauthorized) status codes if applicable.
- Query endpoints now support arbitrary MongoDB aggregation pipelines.
- HTTP input and result file handling improved in CC-Container-Worker.

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
