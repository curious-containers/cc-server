FROM docker.io/ubuntu:xenial

RUN apt-get update \
&& apt-get install -y apt-utils \
&& apt-get install -y apache2 libapache2-mod-wsgi-py3 python3-pip libssl-dev libffi-dev \
&& pip3 install --no-input --upgrade stance flask pymongo docker-py cryptography toml jsonschema requests

RUN mkdir -p /home/cc \
&& useradd -g users -d /home/cc -s /bin/bash cc \
&& groupadd cc \
&& usermod -aG cc cc \
&& chown -R cc:cc /home/cc

COPY wsgi.py /home/cc/cc-server/wsgi.py
COPY apache.conf /etc/apache2/sites-available/cc.conf

RUN a2ensite cc && echo "ServerName localhost" >> /etc/apache2/apache2.conf

ENV PYTHONPATH $PYTHONPATH:/home/cc/cc-server
