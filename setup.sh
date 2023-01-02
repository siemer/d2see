#!/bin/bash

python3 -mvenv venv
. venv/bin/activate
pip install trio
pip install wheel  # otherwise trio-gtk does not install
# also required for trio-gtk: 'sudo apt install libglib2.0-dev'
# apt libcairo2-dev was required for pip pycairo
# and then this for trio-gtk: sudo apt install libgirepository1.0-dev
pip install trio-gtk
