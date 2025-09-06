#!/usr/bin/env python3
"""
Скрипт для запуска Celery worker в режиме разработки
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Запуск Celery worker с правильными настройками"""
    
    # Загрузка переменных окружения
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Загружены переменные окружения из {env_path}")
    else:
        print(f"⚠️ Файл .env не найден в {env_path}")
    
    # Проверка критических переменных
    redis_url = os.getenv('REDIS_URL')
    chroma_host = os.getenv('CHROMA_HOST')
    chroma_port = os.getenv('CHROMA_PORT')
    
    print("\n=== Конфигурация ===")
    print(f"REDIS_URL: {redis_url}")
    print(f"CHROMA_HOST: {chroma_host}")
    print(f"CHROMA_PORT: {chroma_port}")
    
    if not redis_url:
        print("❌ REDIS_URL не установлен")
        sys.exit(1)
    
    # Команда для запуска Celery worker
    cmd = [
        'celery',
        '-A', 'celery_app',
        'worker',
        '--loglevel=info',
        '--concurrency=2',  # Для разработки
        '--pool=solo' if sys.platform == 'win32' else '--pool=prefork'
    ]
    
    print(f"\n🚀 Запуск Celery worker...")
    print(f"Команда: {' '.join(cmd)}")
    print("Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    try:
        # Запуск worker
        subprocess.run(cmd, cwd=Path(__file__).parent)
    except KeyboardInterrupt:
        print("\n\n🛑 Worker остановлен пользователем")
    except FileNotFoundError:
        print("❌ Celery не найден. Установите зависимости:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка запуска worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
