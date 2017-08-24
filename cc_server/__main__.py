from multiprocessing import Process

from cc_server.commons.configuration import Config
from cc_server.services.log.__main__ import main as log_main
from cc_server.services.master.__main__ import main as master_main
from cc_server.services.web.__main__ import main as web_main
from cc_server.services.files.__main__ import main as files_main


def main():
    config = Config()

    log = Process(target=log_main)
    log.daemon = True
    log.start()

    master = Process(target=master_main)
    master.daemon = True
    master.start()

    if config.server_files:
        files = Process(target=files_main)
        files.daemon = True
        files.start()

    web_main()


if __name__ == '__main__':
    main()
