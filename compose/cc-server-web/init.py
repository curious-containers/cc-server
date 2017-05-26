from multiprocessing import cpu_count

from cc_commons.configuration import Config
from cc_server_web.boilerplate import WebApp


config = Config()

options = {
    'bind': '{}:{}'.format(
        config.server_web['bind_host'],
        config.server_web['bind_port']
    ),
    'workers': config.server_web.get('num_workers', cpu_count())
}

WebApp(options).run()
