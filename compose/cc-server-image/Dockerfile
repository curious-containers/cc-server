FROM docker.io/fedora:26

RUN dnf install -y python3-toml python3-jsonschema python3-zmq python3-requests python3-pymongo python3-docker \
python3-flask python3-gunicorn python3-cryptography python3-gevent python3-chardet \
&& useradd --create-home -s /bin/bash ccuser

WORKDIR /home/ccuser
USER ccuser

ENV PYTHONPATH /home/ccuser:${PYTHONPATH}
