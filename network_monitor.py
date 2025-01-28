import psutil
import socket
import time
from kafka import KafkaProducer
import json
import subprocess

def get_ipsec_connections():
    try:
        # Выполняем команду для получения статуса IPsec
        result = subprocess.run(['ipsec', 'status'], capture_output=True, text=True, check=True)
        output = result.stdout
        
        # Подсчитываем количество подключений
        connections = output.splitlines()
        connection_count = sum(1 for line in connections if "ESTABLISHED" in line)
        print(connection_count)
        return connection_count

    except subprocess.CalledProcessError as e:
        print(f"error: {e}")
        return None





def get_network_usage(interface):
    net_io = psutil.net_io_counters(pernic=True)
    if interface in net_io:
        return net_io[interface]
    else:
        print(f"Interface {interface} is not found.")
        return None

def get_ip_address():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address

def main(interface, kafka_topic, kafka_server, interval):
    producer = KafkaProducer(bootstrap_servers=kafka_server,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    
    print(f"Interface: {interface}")

    previous_bytes_sent = 0
    previous_bytes_recv = 0
    ip_address = get_ip_address()

    try:
        while True:
            count_of_users = get_ipsec_connections()
            net_usage = get_network_usage(interface)
            if net_usage:
                bytes_sent = net_usage.bytes_sent
                bytes_recv = net_usage.bytes_recv
                
                # Вычисляем скорость
                speed_sent = (bytes_sent - previous_bytes_sent) * 8  # в битах
                speed_recv = (bytes_recv - previous_bytes_recv) * 8  # в битах
                
                # Конвертируем в мегабиты в секунду
                speed_sent_mbps = speed_sent / 1_000_000
                speed_recv_mbps = speed_recv / 1_000_000
                
                # Создаем сообщение
                message = {
                    'count_of_users': count_of_users,
                    'ip_address': ip_address,
                    'speed_sent_mbps': speed_sent_mbps,
                    'speed_recv_mbps': speed_recv_mbps
                }

                # Отправляем сообщение в Kafka
                producer.send(kafka_topic, message)
                producer.flush()

                print(f"sended: {message}")

                previous_bytes_sent = bytes_sent
                previous_bytes_recv = bytes_recv
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Monitoring stopped")
    finally:
        producer.close()

if __name__ == "__main__":
    interface_name = 'eth0'
    kafka_topic = 'network_usage'
    kafka_server = '109.196.101.63:9092'
    interval_seconds = 30.0
    main(interface_name, kafka_topic, kafka_server, interval_seconds)
