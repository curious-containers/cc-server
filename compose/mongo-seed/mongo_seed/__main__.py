from toml import loads
from json import dumps
from subprocess import call
from time import sleep

CONFIG = '/root/.config/cc-server/config.toml'

with open(CONFIG) as f:
    configuration = loads(f.read())

data = {
    'pwd': configuration['mongo']['password'],
    'roles': [{
        'role': 'readWrite',
        'db': configuration['mongo']['db']
    }]
}

update_command = 'mongo --host mongo --eval \'database = db.getSiblingDB("{}"); database.updateUser({}, {})\''.format(
    configuration['mongo']['db'],
    configuration['mongo']['username'],
    dumps(data)
)

data['user'] = configuration['mongo']['username']

create_command = 'mongo --host mongo --eval \'database = db.getSiblingDB("{}"); database.createUser({})\''.format(
    configuration['mongo']['db'],
    dumps(data)
)

for _ in range(10):
    code = call(update_command, shell=True)
    if code == 0:
        break
    else:
        code = call(create_command, shell=True)
        if code == 0:
            break
    sleep(1)
