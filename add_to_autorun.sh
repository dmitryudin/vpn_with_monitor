#!/bin/bash
apt update
apt install python3-pip
apt install net-tools uvicorn
pip3 install psutil kafka-python dotenv confluent_kafka fastapi uvicorn
cp ./network_monitor.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable network_monitor.service

cp ./user_manager.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable user_manager.service



# Сброс всех правил
sudo iptables -F          # Очистить все правила
sudo iptables -X          # Удалить пользовательские цепочки
sudo iptables -Z          # Обнулить счётчики пакетов и байтов

# Установить политики по умолчанию (разрешить всё)
sudo iptables -P INPUT ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -P FORWARD ACCEPT