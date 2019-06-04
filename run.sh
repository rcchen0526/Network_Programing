#!/bin/bash
cd
mkdir NP
cd NP
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
curl -O http://52.68.108.247:8000/application_server.tar
tar -xvf application_server.tar
cd application_server
pip3 install -I -r application_server_requirement.txt
python3 -u application_server.py 0.0.0.0 25563 > application_server.log