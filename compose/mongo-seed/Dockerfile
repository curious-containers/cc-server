FROM mongo

RUN apt-get update \
&& apt-get install -y python3-pip \
&& pip3 install --no-input --upgrade toml

ENV PYTHONPATH $PYTHONPATH:/opt
