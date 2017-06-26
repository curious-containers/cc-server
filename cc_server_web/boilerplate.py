from gunicorn.app.base import BaseApplication
from gunicorn import util


class WebApp(BaseApplication):
    def __init__(self, options=None):
        self.options = options or {}
        super(WebApp, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in self.options.items()
                       if key in self.cfg.settings and value is not None])
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return util.import_app("cc_server_web.wsgi")
