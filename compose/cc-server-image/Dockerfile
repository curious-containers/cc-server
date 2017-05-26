FROM docker.io/ubuntu:xenial

RUN apt-get update \
&& apt-get install -y python3-pip libssl-dev libffi-dev \
&& pip3 install --no-input --upgrade toml jsonschema zmq requests pymongo docker-py flask gunicorn cryptography

ENV PYTHONPATH $PYTHONPATH:/opt
