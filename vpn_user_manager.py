


from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path
import subprocess
import re
import time
from typing import Optional
import logging
import os

app = FastAPI()
security = HTTPBasic()
logger = logging.getLogger(__name__)

# Конфигурация
CONFIG_FILE = os.getenv('IPSEC_CONFIG', '/etc/ipsec.secrets')
ADMIN_USERNAME = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'securepassword')

class VPNUserManager:
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = Path(config_file)
        
    def execute_ipsec_command(self):
        """Обновляет IPsec secrets"""
        try:
            result = subprocess.run(
                ['sudo', 'ipsec', 'secrets'], 
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("IPsec secrets reloaded: %s", result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("IPsec update failed: %s", e.stderr)
            return False

    def _validate_credentials(self, credentials: HTTPBasicCredentials = Depends(security)):
        """Проверка Basic Auth"""
        correct_username = credentials.username == ADMIN_USERNAME
        correct_password = credentials.password == ADMIN_PASSWORD
        
        if not (correct_username and correct_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    def add_user(self, username: str, password: str):
        """Добавляет пользователя в конфиг"""
        if not self.config_file.exists():
            self.config_file.touch(mode=0o600)

        with open(self.config_file, 'r+') as f:
            content = f.read()
            if re.search(rf'^{username} : EAP ".+"$', content, re.MULTILINE):
                raise HTTPException(
                    status_code=409,
                    detail="User already exists"
                )

            f.write(f'\n{username} : EAP "{password}"')
        
        if not self.execute_ipsec_command():
            raise HTTPException(
                status_code=500,
                detail="Failed to reload IPsec configuration"
            )
        return {"status": "success", "username": username}

    def remove_user(self, username: str):
        """Удаляет пользователя из конфига"""
        if not self.config_file.exists():
            raise HTTPException(
                status_code=500,
                detail="IPsec config file not found"
            )

        with open(self.config_file, 'r') as f:
            lines = f.readlines()

        new_lines = [line for line in lines if not line.strip().startswith(f'{username} : EAP ')]

        if len(new_lines) == len(lines):
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        with open(self.config_file, 'w') as f:
            f.writelines(new_lines)

        if not self.execute_ipsec_command():
            raise HTTPException(
                status_code=500,
                detail="Failed to reload IPsec configuration"
            )
        return {"status": "success", "username": username}
    def sync_users(self, valid_usernames: list):
        """Удаляет пользователей, отсутствующих в valid_usernames"""
        if not self.config_file.exists():
            raise HTTPException(
                status_code=500,
                detail="IPsec config file not found"
            )

        # Читаем текущих пользователей из файла
        with open(self.config_file, 'r') as f:
            content = f.read()
        
        # Ищем всех пользователей в формате 'username : EAP "password"'
        existing_users = re.findall(r'^(\w+) : EAP ".+"$', content, re.MULTILINE)
        
        # Определяем пользователей для удаления
        users_to_remove = [user for user in existing_users if user not in valid_usernames]
        
        # Удаляем пользователей
        for username in users_to_remove:
            self.remove_user(username)
        
        return {
            "status": "success",
            "removed_users": users_to_remove,
            "total_removed": len(users_to_remove)
        }

# Инициализация менеджера
manager = VPNUserManager()

# Эндпоинты FastAPI
@app.post("/users/")
def add_user(
    username: str,
    password: str,
    auth: HTTPBasicCredentials = Depends(manager._validate_credentials)
):
    """Добавление пользователя VPN"""
    return manager.add_user(username, password)

@app.delete("/users/{username}")
def remove_user(
    username: str,
    auth: HTTPBasicCredentials = Depends(manager._validate_credentials)
):
    """Удаление пользователя VPN"""
    return manager.remove_user(username)

@app.get("/health")
def health_check():
    """Проверка статуса сервиса"""
    return {"status": "ok", "timestamp": int(time.time())}

# Добавить эндпоинт в FastAPI
@app.post("/users/sync")
def sync_users(
    usernames: list[str],
    auth: HTTPBasicCredentials = Depends(manager._validate_credentials)
):
    """Синхронизирует пользователей с предоставленным списком"""
    return manager.sync_users(usernames)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="185.207.67.215", port=8080)