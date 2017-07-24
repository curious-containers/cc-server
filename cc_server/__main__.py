from multiprocessing import Process


def main():
    from cc_server import log_service
    from cc_server import master_service
    from cc_server import web_service

    log = Process(target=log_service.main)
    log.daemon = True
    log.start()

    scheduler = Process(target=master_service.main)
    scheduler.daemon = True
    scheduler.start()

    web_service.main()

if __name__ == '__main__':
    main()
