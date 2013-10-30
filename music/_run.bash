#!/bin/bash

source ../venv/bin/activate
export ZULU_SETTINGS=/path/to/config.zulu
python zulu.py

# this can be used for gunicorn
# gunicorn --access-logfile - -w 4 -b 127.0.0.1:5000 zulu:app
