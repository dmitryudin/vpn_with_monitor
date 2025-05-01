import re
import subprocess
from pathlib import Path
from confluent_kafka import Consumer, Producer
import json
import threading

class VPNUserManager:
    def __init__(self, config_file='/etc/ipsec.conf'):
        self.config_file = Path(config_file)
        self.kafka_config = {
            'bootstrap.servers': 'kafka-broker:9092',
            'group.id': 'vpn-user-manager',
            'auto.offset.reset': 'earliest'
        }
        self.topic_commands = 'vpn-user-commands'
        self.topic_events = 'vpn-user-events'

    def execute_ipsec_command(self):
        """Обновляет IPsec secrets"""
        try:
            subprocess.run(['sudo', 'ipsec', 'secrets'], check=True)
            self._send_kafka_event("ipsec_updated", "IPsec secrets reloaded")
        except subprocess.CalledProcessError as e:
            self._send_kafka_event("error", f"IPsec update failed: {e}")

    def _send_kafka_event(self, topic: str, data: dict):
        """Универсальный метод отправки сообщений"""
        producer = Producer(self.kafka_config)
        try:
            producer.produce(
                topic=topic,
                value=json.dumps(data).encode('utf-8'),
                callback=lambda err, _: print(f"Delivery failed: {err}") if err else None
            )
            producer.flush()
        except Exception as e:
            print(f"Failed to send message to {topic}: {e}")
        finally:
            producer.poll(0)

    def add_user(self, username: str, password: str):
        """Добавляет пользователя в конфиг"""
        if not self.config_file.exists():
            self.config_file.touch()

        with open(self.config_file, 'r+') as f:
            content = f.read()
            if re.search(rf'^{username} : EAP ".+"$', content, re.MULTILINE):
                self._send_kafka_event("warning", f"User {username} already exists")
                return False

            f.write(f'\n{username} : EAP "{password}"')
        
        self.execute_ipsec_command()
        self._send_kafka_event("user_added", f"Added user {username}")
        return True

    def remove_user(self, username: str):
        """Удаляет пользователя из конфига"""
        if not self.config_file.exists():
            self._send_kafka_event("error", "Config file not found")
            return False

        with open(self.config_file, 'r') as f:
            lines = f.readlines()

        new_lines = [line for line in lines if not line.strip().startswith(f'{username} : EAP ')]

        if len(new_lines) == len(lines):
            self._send_kafka_event("warning", f"User {username} not found")
            return False

        with open(self.config_file, 'w') as f:
            f.writelines(new_lines)

        self.execute_ipsec_command()
        self._send_kafka_event("user_removed", f"Removed user {username}")
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

            try:
                command = json.loads(msg.value())
                reply_to = command.get('reply_to')
                corr_id = command.get('correlation_id')
                result = None

                if command['action'] == 'add':
                    result = self.add_user(command['username'], command['password'])
                elif command['action'] == 'remove':
                    result = self.remove_user(command['username'])
                else:
                    self._send_kafka_event(
                        reply_to,
                        {'status': 'failed', 'error': 'Invalid action', 'correlation_id': corr_id}
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

            except Exception as e:
                self._send_kafka_event(
                    command.get('reply_to', 'vpn-errors'),
                    {
                        'status': 'failed',
                        'error': str(e),
                        'correlation_id': command.get('correlation_id', 'unknown')
                    }
                )

    def start(self):
        """Запускает обработчик команд Kafka в отдельном потоке"""
        threading.Thread(target=self.process_kafka_commands, daemon=True).start()
        self._send_kafka_event("service_started", "VPN User Manager started")

# Пример использования
if __name__ == "__main__":
    manager = VPNUserManager()
    manager.start()
    
    # Демонстрация - в реальном коде это будет через Kafka
    manager.add_user("test_user", "test123")
    manager.remove_user("test_user")
    
    # Оставить процесс активным
    while True:
        pass