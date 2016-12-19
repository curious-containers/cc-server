import os
import datetime
from threading import Thread
from queue import Queue


class Tee:
    def __init__(self, config):
        self._config = config
        self._q = None

    def late_init(self):
        self._q = Queue()
        Thread(target=self._loop, args=()).start()

    def tee(self, message):
        self._q.put(message)

    def getpid(self):
        return os.getpid()

    def _loop(self):
        log_path = None
        if self._config.server.get('log_dir'):
            log_dir = os.path.expanduser(self._config.server['log_dir'])
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_path = os.path.join(log_dir, 'server.log')
        suppress_stdout = self._config.server.get('suppress_stdout')

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

        tee = stdout_func
        if suppress_stdout:
            tee = neither_func
            if log_path:
                tee = file_func
        elif log_path:
            tee = both_func

        while True:
            tee(self._q.get())
