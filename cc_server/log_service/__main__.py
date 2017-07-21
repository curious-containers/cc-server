import atexit
import datetime
import os
import zmq

from cc_server.commons.configuration import Config

FILE_NAME = 'server.log'


def main():
    config = Config()

    # start zmq server
    context = zmq.Context()
    logger_socket = context.socket(zmq.PULL)
    logger_socket.bind('tcp://{}:{}'.format(
        config.server_log['bind_host'],
        config.server_log['bind_port']
    ))

    # create folder if not existent
    log_path = None
    if config.server_log.get('log_dir'):
        log_dir = os.path.expanduser(config.server_log['log_dir'])
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, FILE_NAME)

    # define possible functions for tee
    def stdout_func(message):
        print(message)

    def file_func(message):
        with open(log_path, 'a') as f:
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S |"), message, file=f)

    def both_func(message):
        print(message)
        file_func(message)

    def neither_func(_):
        pass

    # choose function for tee
    suppress_stdout = config.server_log.get('suppress_stdout')
    tee = stdout_func
    if suppress_stdout:
        tee = neither_func
        if log_path:
            tee = file_func
    elif log_path:
        tee = both_func

    # inform at exit
    def at_exit():
        tee('Stopped logger with pid {}'.format(os.getpid()))

    atexit.register(at_exit)

    # log status
    tee('Started logger with pid {}'.format(os.getpid()))
    tee('Loaded TOML config from {}'.format(config.config_file_path))

    # start endless loop
    while True:
        m = logger_socket.recv_string()
        tee(m)

if __name__ == '__main__':
    main()
