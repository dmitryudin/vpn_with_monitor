#!/bin/bash
apt update
apt install python3-pip
apt install net-tools
pip3 install psutil kafka-python
cp ./network_monitor.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable network_monitor.service