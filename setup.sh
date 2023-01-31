#!/bin/bash

python3 -mvenv venv
. venv/bin/activate
pip install trio
# trio-gtk not needed any more, but dependencies still are?
# sudo apt install libglib2.0-dev libgirepository1.0-dev libcairo2-dev
# pip install wheel pygobject pycairo
pip install ewmh
