import os
import datetime
import atexit
from time import sleep
from threading import Thread
from queue import Queue
from multiprocessing.managers import BaseManager

from cc_server.helper import RedirectStdStreams


def _connect(config):
    TeeManager.register('get_tee')
    m = TeeManager(address=('', config.ipc['tee_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.connect()
    tee = m.get_tee()
    print('| tee    | PID: {} | CONNECTED  |'.format(tee.get_pid()))
    return tee


def _start(config):
    tee = Tee(
        config=config
    )
    TeeManager.register('get_tee', callable=lambda: tee)
    m = TeeManager(address=('', config.ipc['tee_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.start()
    tee = m.get_tee()
    pid = tee.get_pid()
    atexit.register(_terminate, m, pid)
    tee.late_init()
    print('| tee    | PID: {} | STARTED    |'.format(pid))
    return tee


def _terminate(manager, pid):
    manager.shutdown()
    print('| tee    | PID: {} | TERMINATED |'.format(pid))


def get_tee(config):
    try:
        with open(os.devnull, 'w') as devnull:
            with RedirectStdStreams(stderr=devnull):
                return _connect(config=config).tee
    except:
        try:
            with open(os.devnull, 'w') as devnull:
                with RedirectStdStreams(stderr=devnull):
                    return _start(config=config).tee
        except:
            sleep(1)
            return _connect(config=config).tee


class TeeManager(BaseManager):
    pass


class Tee:
    def __init__(self, config):
        self._config = config
        self._q = None

    def late_init(self):
        self._q = Queue()
        Thread(target=self._loop, args=()).start()

    def tee(self, message):
        self._q.put(message)

    def get_pid(self):
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
