import os
import atexit
import zmq

from cc_server.commons.configuration import Config
from cc_server.commons.database import Mongo
from cc_server.commons.states import StateHandler
from cc_server.services.master.cluster import Cluster
from cc_server.services.master.cluster_provider import DockerProvider
from cc_server.services.master.scheduling import Scheduler
from cc_server.services.master.worker import Worker


def main():
    config = Config()

    # start zmq server
    context = zmq.Context()
    master_socket = context.socket(zmq.PULL)
    master_socket.bind('tcp://{}:{}'.format(
        config.server_master['bind_host'],
        config.server_master['bind_port']
    ))

    # connect to logger
    logger_socket = context.socket(zmq.PUSH)
    logger_socket.connect(config.server_log['external_url'])
    tee = logger_socket.send_string

    # initialize singletons
    mongo = Mongo(
        config=config
    )
    state_handler = StateHandler(
        config=config,
        tee=tee,
        mongo=mongo
    )
    cluster_provider = DockerProvider(
        config=config,
        tee=tee,
        mongo=mongo
    )
    cluster = Cluster(
        config=config,
        tee=tee,
        mongo=mongo,
        state_handler=state_handler,
        cluster_provider=cluster_provider
    )
    scheduler = Scheduler(
        config=config,
        tee=tee,
        mongo=mongo,
        state_handler=state_handler,
        cluster=cluster
    )
    worker = Worker(
        config=config,
        tee=tee,
        mongo=mongo,
        state_handler=state_handler,
        cluster=cluster,
        scheduler=scheduler
    )

    # inform at exit
    def at_exit():
        tee('Stopped service master with pid {}'.format(os.getpid()))

    atexit.register(at_exit)

    # log status
    tee('Started service master with pid {}'.format(os.getpid()))

    # start endless loop
    while True:
        d = master_socket.recv_json()
        action = d.get('action')
        if action == 'schedule':
            pass
            worker.schedule()
        elif action == 'container_callback':
            pass
            worker.container_callback()
        elif action == 'data_container_callback':
            pass
            worker.data_container_callback()
        elif action == 'update_node_status':
            node_name = d.get('data', {}).get('node_name')
            if node_name:
                pass


if __name__ == '__main__':
    main()
