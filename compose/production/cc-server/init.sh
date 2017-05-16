#!/usr/bin/env bash

su cc -c "python3 -u /home/cc/.config/curious-containers/cc-server/init.py"

/usr/sbin/apache2ctl -D FOREGROUND
