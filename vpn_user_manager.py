import re
import subprocess
from pathlib import Path
from confluent_kafka import Consumer, Producer
import json
import threading
import socket
from dotenv import load_dotenv
import os
import time
load_dotenv()

MY_TOPIC = os.getenv("MY_TOPIC")


KAFKA_HOST = os.getenv("KAFKA_HOST")
KAFKA_PORT = os.getenv("KAFKA_PORT")

from enum import Enum

class VPNUserManagerStatus(Enum):
    CONFLICT = 0
    USER_NOT_FOUND = 1
    SERVER_NOT_RESPONCE=2
    INVALID_CONFIG_FILE = 3
    INVALID_ACTION= 4
    UNEXPECTED_ERROR = 5


class VPNUserManager:
    def __init__(self, config_file='/etc/ipsec.secrets'):
        
        self.config_file = Path(config_file)
        self.kafka_config = {
            'bootstrap.servers': f'{KAFKA_HOST}:{KAFKA_PORT}',
            'group.id': 'vpn-user-manager',
            'auto.offset.reset': 'earliest'
        }
        self.topic_commands = f'{MY_TOPIC}'

    def execute_ipsec_command(self):
        """Обновляет IPsec secrets"""
        try:
            subprocess.run(['sudo', 'ipsec', 'secrets'], check=True)
            self._send_kafka_event("ipsec_updated", "IPsec secrets reloaded")
        except subprocess.CalledProcessError as e:
            self._send_kafka_event("error", f"IPsec update failed: {e}")

    def _send_kafka_event(self, topic: str, data: dict):
        """Универсальный метод отправки сообщений"""
        producer = Producer({'bootstrap.servers': f'{KAFKA_HOST}:{KAFKA_PORT}'})
        try:
            producer.produce(
                topic=topic,
                value=json.dumps(data).encode('utf-8'),
                callback=lambda err, _: print(f"Delivery failed: {err}") if err else None
            )
            producer.flush()
            print(f'sended data {data}')
        except Exception as e:
            print(f"Failed to send message to {topic}: {e}")
        finally:
            producer.poll(0)

    def add_user(self, username: str, password: str, corr_id:str,  reply_to: str):
        """Добавляет пользователя в конфиг"""
        if not self.config_file.exists():
            self.config_file.touch()

        with open(self.config_file, 'r+') as f:
            content = f.read()
            if re.search(rf'^{username} : EAP ".+"$', content, re.MULTILINE):
                self._send_kafka_event(topic=reply_to, data={'status': 'failed', 'error': 'conflict', 'correlation_id': corr_id})
                return False

            f.write(f'\n{username} : EAP "{password}"')
        
        self.execute_ipsec_command()
        self._send_kafka_event(topic=reply_to, data={'status': 'success', 'error': '', 'correlation_id': corr_id})
        return True

    def remove_user(self, username: str, corr_id: str, reply_to: str):
        """Удаляет пользователя из конфига"""
        if not self.config_file.exists():
            self._send_kafka_event(topic=reply_to, data={'status': 'failed', 'error': 'invalid_config_file', 'correlation_id': corr_id})
            return False

        with open(self.config_file, 'r') as f:
            lines = f.readlines()

        new_lines = [line for line in lines if not line.strip().startswith(f'{username} : EAP ')]

        if len(new_lines) == len(lines):
            self._send_kafka_event(topic=reply_to, data={'status': 'failed', 'error': 'not_found', 'correlation_id': corr_id})
            return False

        with open(self.config_file, 'w') as f:
            f.writelines(new_lines)

        self.execute_ipsec_command()
        self._send_kafka_event(topic=reply_to, data={'status': 'success', 'error': '', 'correlation_id': corr_id})
        return True

    def process_kafka_commands(self):
        """Обрабатывает команды из Kafka с отправкой подтверждений"""
        consumer = Consumer({
            **self.kafka_config,
            'enable.auto.commit': False  # Ручное подтверждение
        })
        consumer.subscribe([self.topic_commands])

        while True:
            msg = consumer.poll(1.0)
            if not msg:
                continue

            command = None  # Инициализируем переменную заранее
            try:
                print(msg.value())
                command = json.loads(msg.value())
                reply_to = command.get('reply_to')
                corr_id = command.get('correlation_id')
                result = None

                if command['action'] == 'add':
                    result = self.add_user(command['username'], command['password'], corr_id=corr_id, reply_to=reply_to)
                elif command['action'] == 'remove':
                    result = self.remove_user(command['username'], corr_id=corr_id, reply_to=reply_to)
                else:
                    self._send_kafka_event(
                        reply_to or 'vpn-errors',
                        {'status': 'failed', 'error': 'invalid_action', 'correlation_id': corr_id}
                    )
                    continue

                # Отправляем подтверждение
                if reply_to:
                    self._send_kafka_event(
                        reply_to,
                        {
                            'status': 'success' if result else 'failed',
                            'correlation_id': corr_id,
                            'processed_at': int(time.time() * 1000)
                        }
                    )

                # Подтверждаем обработку сообщения
                consumer.commit(message=msg)

            except json.JSONDecodeError as e:
                error_msg = {'status': 'failed', 'error': f'Invalid JSON: {str(e)}'}
                self._send_kafka_event('vpn-errors', error_msg)
                print('exeption ', e)
            except Exception as e:
                print('exeption ', e)
                error_data = {
                    'status': 'failed',
                    'error': str(e),
                    'correlation_id': command.get('correlation_id', 'unknown') if command else 'unknown',
                    'original_message': msg.value().decode('utf-8') if msg else None
                }
                self._send_kafka_event(command.get('reply_to', 'vpn-errors') if command else 'vpn-errors', error_data)


    def start(self):
        """Запускает обработчик команд Kafka в отдельном потоке"""
        threading.Thread(target=self.process_kafka_commands, daemon=True).start()
        print('service started')
        # self._send_kafka_event("service_started", "VPN User Manager started")

# Пример использования
if __name__ == "__main__":
    manager = VPNUserManager()
    manager.start()
    
    # Демонстрация - в реальном коде это будет через Kafka
    # manager.add_user("test_user", "test123")
    # manager.remove_user("test_user")
    
    # Оставить процесс активным
    while True:
        time.sleep(1)