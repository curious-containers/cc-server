from multiprocessing import Process


def main():
    from cc_server.log_service.__main__ import main as log_main
    from cc_server.master_service.__main__ import main as master_main
    from cc_server.web_service.__main__ import main as web_main

    log = Process(target=log_main)
    log.daemon = True
    log.start()

    scheduler = Process(target=master_main)
    scheduler.daemon = True
    scheduler.start()

    web_main()

if __name__ == '__main__':
    main()
