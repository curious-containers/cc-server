FROM docker.io/ubuntu:xenial

RUN apt-get update \
&& apt-get install -y apt-utils python3-pip libssl-dev libffi-dev \
&& pip3 install --no-input --upgrade stance flask pymongo docker-py cryptography toml jsonschema requests

ENV PYTHONPATH $PYTHONPATH:/opt
