FROM docker.io/fedora:26

RUN dnf install -y python3-devel openssl-devel libffi-devel \
&& pip3 install --no-input --user --upgrade \
toml jsonschema zmq requests pymongo docker-py flask gunicorn cryptography gevent

ENV PYTHONPATH /opt:${PYTHONPATH}
