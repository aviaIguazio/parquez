#!/usr/bin/bash

if ! [ -d venv  ] ; then
        mkdir venv
        virtualenv venv
        source venv/bin/activate
        pip install -r config/requirements.txt
else
        source venv/bin/activate
fi

python parquez.py ${1} ${2} ${3} ${4} ${5} ${6} ${7} ${8} ${9} ${10} ${11} ${12} ${13} ${14}

