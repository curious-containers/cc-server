from toml import loads
from json import dumps
from subprocess import call
from time import sleep

CONFIG = '/root/.config/curious-containers/local_docker_config.toml'

with open(CONFIG) as f:
    configuration = loads(f.read())

data = {
    'user': configuration['mongo']['username'],
    'pwd': configuration['mongo']['password'],
    'roles': [{
        'role': 'readWrite',
        'db': configuration['mongo']['db']
    }]
}
command = 'mongo --host mongo --eval \'database = db.getSiblingDB("{}"); database.createUser({})\''.format(
    configuration['mongo']['db'],
    dumps(data)
)

for _ in range(10):
    code = call(command, shell=True)
    if code == 0:
        break
    else:
        sleep(1)
