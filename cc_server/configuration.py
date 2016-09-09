from os.path import expanduser, join
from os import getcwd
from toml import loads


class Config:
    def __init__(self, file_path):
        possible_conf_file_paths = [
            file_path,
            join(getcwd(), 'config.toml'),
            join(getcwd(), '..', 'config.toml')
        ]

        try:
            possible_conf_file_paths.append(
                expanduser('~/.config/curious-containers/config.toml')
            )
        except:
            pass

        config = None

        for conf_file_path in possible_conf_file_paths:
            try:
                with open(conf_file_path) as f:
                    config = loads(f.read())
                    print('Loaded TOML config from {}'.format(conf_file_path))
                    break
            except:
                pass

        if not config:
            raise Exception('No valid TOML file found. Try specifying a file path as first CLI argument.')

        self.server = config['server']
        self.mongo = config['mongo']
        self.docker = config['docker']
        self.defaults = config['defaults']
