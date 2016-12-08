import os
import datetime
from threading import Lock


def construct_function(config):
    config = config
    lock = Lock()
    log_path = None
    if config.server.get('log_dir'):
        log_dir = os.path.expanduser(config.server['log_dir'])
        log_path = os.path.join(log_dir, 'cc-server.log')
    suppress_stdout = config.server.get('suppress_stdout')

    def stdout_func(*args):
        print(*args)

    def file_func(*args):
        with lock:
            with open(log_path, 'a') as f:
                print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S |"), *args, file=f)

    def both_func(*args):
        print(*args)
        file_func(*args)

    def neither_func(*args):
        pass

    tee = stdout_func
    if suppress_stdout:
        tee = neither_func
        if log_path:
            tee = file_func
    elif log_path:
        tee = both_func

    return tee
