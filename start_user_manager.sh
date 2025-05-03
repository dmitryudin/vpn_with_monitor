#!/bin/bash
# source /home/vpn/vpn_with_monitor/venv/bin/activate

# Сброс всех правил
sudo /usr/sbin/iptables -F          # Очистить все правила
sudo /usr/sbin/iptables -X          # Удалить пользовательские цепочки
sudo /usr/sbin/iptables -Z          # Обнулить счётчики пакетов и байтов

# Установить политики по умолчанию (разрешить всё)
sudo /usr/sbin/iptables -P INPUT ACCEPT
sudo /usr/sbin/iptables -P OUTPUT ACCEPT
sudo /usr/sbin/iptables -P FORWARD ACCEPT
/usr/bin/python3 /home/vpn/vpn_with_monitor/vpn_user_manager.py
