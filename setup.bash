#!/bin/bash

/usr/bin/virtualenv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
