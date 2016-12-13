import os
import datetime
import signal
from threading import Thread
from queue import Queue
from multiprocessing.managers import BaseManager


def connect(config):
    TeeManager.register('get_tee')
    m = TeeManager(address=('', config.ipc['tee_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.connect()
    return m.get_tee()


def start(config):
    tee = Tee(
        config=config
    )
    TeeManager.register('get_tee', callable=lambda: tee)
    m = TeeManager(address=('', config.ipc['tee_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.start()
    tee = m.get_tee()
    tee.late_init()
    return tee


def stop(config):
    TeeManager.register('get_tee')
    m = TeeManager(address=('', config.ipc['tee_port']), authkey=config.ipc['secret'].encode('utf-8'))
    m.connect()
    tee = m.get_tee()
    pid = tee.get_pid()
    os.kill(pid, signal.SIGTERM)


def get_tee(config):
    try:
        tee = connect(config=config)
        print('tee | PID: {} | CONNECTED'.format(tee.get_pid()))
    except:
        tee = start(config=config)
        print('tee | PID: {} | STARTED'.format(tee.get_pid()))
    return tee.tee


class TeeManager(BaseManager):
    pass


class Tee:
    def __init__(self, config):
        self.config = config
        self.q = None

    def late_init(self):
        self.q = Queue()
        Thread(target=self._loop, args=()).start()

    def tee(self, message):
        self.q.put(message)

    def get_pid(self):
        return os.getpid()

    def _loop(self):
        log_path = None
        if self.config.server.get('log_dir'):
            log_dir = os.path.expanduser(self.config.server['log_dir'])
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_path = os.path.join(log_dir, 'server.log')
        suppress_stdout = self.config.server.get('suppress_stdout')

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
            tee(self.q.get())
