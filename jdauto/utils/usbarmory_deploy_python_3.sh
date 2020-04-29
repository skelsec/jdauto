#!/bin/bash
apt install python3-pip python3.7-dev python3.7-venv git htop lsof

python3.7 -m pip install multiplexor jdauto
python3.7 -m pip uninstall asn1crypto
python3.7 -m pip install 'asn1crypto>=1.3.0'
