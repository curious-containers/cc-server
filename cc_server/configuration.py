import os
import sys
from toml import loads


class Config:
    def __init__(self):
        possible_conf_file_paths = []
        try:
            possible_conf_file_paths.append(sys.argv[1])
        except:
            pass

        try:
            possible_conf_file_paths.append(
                os.path.expanduser('~/.config/curious-containers/config.toml')
            )
        except:
            pass

        try:
            possible_conf_file_paths.append(
                os.path.join(os.path.split(os.path.split(os.path.abspath(__file__))[0])[0], 'config.toml')
            )
        except:
            pass

        config = None

        for conf_file_path in possible_conf_file_paths:
            try:
                with open(conf_file_path) as f:
                    config = loads(f.read())
                    self.conf_file_path = conf_file_path
                    break
            except:
                pass

        if not config:
            raise Exception('No valid TOML file found. Try specifying a file path as first CLI argument.')

        self.server = config['server']
        self.mongo = config['mongo']
        self.docker = config['docker']
        self.defaults = config['defaults']
