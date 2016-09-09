from toml import loads
from json import dumps
from subprocess import call

CONFIG = '/root/.config/curious-containers/config.toml'

with open(CONFIG) as f:
    configuration = loads(f.read())

data = {
    'user': configuration['mongo']['username'],
    'pwd': configuration['mongo']['password'],
    'roles': [{
        'role': 'readWrite',
        'db': configuration['mongo']['dbname']
    }]
}
command = 'mongo --host mongo --eval \'database = db.getSiblingDB("{}"); database.createUser({})\''.format(
    configuration['mongo']['dbname'],
    dumps(data)
)
call(command, shell=True)
