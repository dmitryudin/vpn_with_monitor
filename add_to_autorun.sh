#!/bin/bash
apt update
apt install python3-pip
apt install net-tools
pip3 install psutil kafka-python dotenv confluent_kafka
cp ./network_monitor.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable network_monitor.service

cp ./user_manager.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable user_manager.service