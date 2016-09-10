FROM docker.io/ubuntu:xenial

RUN apt-get update \
&& apt-get install -y apt-utils python3-pip libssl-dev libffi-dev \
&& pip3 install --no-input --upgrade flask pymongo docker-py psutil cryptography toml jsonschema requests streql

ENV PYTHONPATH $PYTHONPATH:/opt

ENV USERNAME admin
ENV PASSWORD PASSWORD
