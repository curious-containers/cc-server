import os
import toml
from jsonschema import validate
from argparse import ArgumentParser

from cc_server.commons.schemas import cc_server_config_schema


class Config:
    def __init__(self):
        parser = ArgumentParser(
            description='CC-Server Configuration'
        )
        parser.add_argument(
            '-f', '--config-file', dest='config_file', metavar='FILE',
            help='path to a configuration FILE in TOML format'
        )
        parser.add_argument(
            '-m', '--mongo-host', dest='mongo_host', metavar='HOST',
            help='override the HOST name of the MongoDB configuration'
        )
        parser.add_argument(
            '-p', '--mongo-port', dest='mongo_port', metavar='PORT',
            help='override the PORT number of the MongoDB configuration'
        )

        args = parser.parse_args()

        self.config_file_path = os.path.join(os.path.expanduser('~'), '.config', 'cc-server', 'config.toml')
        if args.config_file:
            self.config_file_path = args.config_file

        with open(self.config_file_path) as f:
            config = toml.load(f)

        validate(config, cc_server_config_schema)

        self.server_web = config['server_web']
        self.server_master = config['server_master']
        self.server_log = config['server_log']
        self.mongo = config['mongo']
        self.docker = config['docker']
        self.defaults = config['defaults']

        if args.mongo_host:
            self.mongo['host'] = args.mongo_host

        if args.mongo_port:
            self.mongo['port'] = int(args.mongo_port)
