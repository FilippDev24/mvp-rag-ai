# Стратегия поддержки macOS (разработка) и Ubuntu (продакшн)

## 🎯 ПРОБЛЕМА
Как поддерживать единую кодовую базу для разработки на macOS и продакшна на Ubuntu, учитывая различия в архитектуре и ML-моделях?

## 🏗️ АРХИТЕКТУРНОЕ РЕШЕНИЕ

### 1. **Единая кодовая база с адаптивной конфигурацией**

```
knowledge-base-mvp/
├── backend/                    # Одинаковый для всех платформ
├── frontend/                   # Одинаковый для всех платформ  
├── worker/                     # Одинаковый для всех платформ
├── ml-services/               # 🔥 НОВАЯ ПАПКА
│   ├── embedding_server.py    # Универсальный сервер
│   ├── reranker_server.py     # Универсальный сервер
│   ├── requirements.txt       # Универсальные зависимости
│   └── config/
│       ├── macos.py          # Конфиг для macOS
│       ├── ubuntu.py         # Конфиг для Ubuntu
│       └── base.py           # Базовый конфиг
├── deployment/
│   ├── docker-compose.dev.yml     # Для разработки (macOS)
│   ├── docker-compose.prod.yml    # Для продакшна (Ubuntu)
│   ├── .env.dev                   # Переменные для разработки
│   ├── .env.prod                  # Переменные для продакшна
│   └── scripts/
│       ├── deploy.sh              # Скрипт развертывания
│       ├── setup-ubuntu.sh        # Настройка Ubuntu сервера
│       └── update.sh              # Обновление на сервере
└── README.md
```

### 2. **Универсальные ML-сервисы**

#### Адаптивный embedding сервер:
```python
# ml-services/embedding_server.py
import platform
from config.base import BaseConfig

if platform.system() == "Darwin":  # macOS
    from config.macos import MacOSConfig as PlatformConfig
else:  # Linux/Ubuntu
    from config.ubuntu import Ubuntu Config as PlatformConfig

class EmbeddingService:
    def __init__(self):
        self.config = PlatformConfig()
        self.device = self.config.get_optimal_device()
        self.model = self.config.load_model()
```

#### Конфигурации по платформам:
```python
# config/macos.py
class MacOSConfig(BaseConfig):
    def get_optimal_device(self):
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def get_optimizations(self):
        return {
            "use_metal": True,
            "batch_size": 32,
            "threads": 8
        }

# config/ubuntu.py  
class UbuntuConfig(BaseConfig):
    def get_optimal_device(self):
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    
    def get_optimizations(self):
        return {
            "use_cuda": torch.cuda.is_available(),
            "batch_size": 16,  # Консервативнее для CPU
            "threads": os.cpu_count()
        }
```

## 🚀 WORKFLOW РАЗРАБОТКИ И РАЗВЕРТЫВАНИЯ

### Локальная разработка (macOS):
```bash
# 1. Разработка как обычно
npm run dev                    # Backend
npm run dev                    # Frontend  
python ml-services/embedding_server.py    # ML-сервисы
docker compose -f deployment/docker-compose.dev.yml up

# 2. Тестирование изменений
npm test
python -m pytest worker/
```

### Развертывание на продакшн (Ubuntu):
```bash
# 3. Коммит изменений
git add .
git commit -m "Feature: новая функциональность"
git push origin main

# 4. Автоматическое развертывание на сервере
./deployment/scripts/deploy.sh
```

## 🔄 АВТОМАТИЗАЦИЯ РАЗВЕРТЫВАНИЯ

### Скрипт развертывания (`deployment/scripts/deploy.sh`):
```bash
#!/bin/bash
set -e

echo "🚀 Starting deployment to Ubuntu server..."

# 1. Подключение к серверу и обновление кода
ssh -i ~/.ssh/edds_server_key div@89.169.150.113 << 'EOF'
    cd /opt/knowledge-base
    
    echo "📥 Pulling latest code..."
    git pull origin main
    
    echo "🔄 Updating ML services..."
    source venv/bin/activate
    pip install -r ml-services/requirements.txt
    
    echo "🐳 Updating Docker containers..."
    docker compose -f deployment/docker-compose.prod.yml down
    docker compose -f deployment/docker-compose.prod.yml up -d --build
    
    echo "🤖 Restarting ML services..."
    sudo systemctl restart kb-embedding
    sudo systemctl restart kb-reranker
    
    echo "✅ Deployment completed!"
EOF

echo "🎉 Deployment to Ubuntu server completed successfully!"
```

### Первоначальная настройка сервера (`deployment/scripts/setup-ubuntu.sh`):
```bash
#!/bin/bash
set -e

echo "🛠️ Setting up Ubuntu server for Knowledge Base..."

# Установка зависимостей
sudo apt update
sudo apt install -y docker.io docker-compose-plugin python3-pip python3-venv nodejs npm

# Создание пользователя приложения
sudo useradd -m -s /bin/bash kb-app
sudo usermod -aG docker kb-app

# Создание директорий
sudo mkdir -p /opt/knowledge-base
sudo chown kb-app:kb-app /opt/knowledge-base

# Клонирование репозитория
cd /opt/knowledge-base
git clone https://github.com/your-repo/knowledge-base-mvp.git .

# Настройка Python окружения
python3 -m venv venv
source venv/bin/activate
pip install -r ml-services/requirements.txt

# Создание systemd сервисов
sudo cp deployment/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kb-embedding kb-reranker

# Установка Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:8b  # или другая модель

echo "✅ Ubuntu server setup completed!"
```

## 📁 КОНФИГУРАЦИОННЫЕ ФАЙЛЫ

### Docker Compose для разработки:
```yaml
# deployment/docker-compose.dev.yml
services:
  backend:
    environment:
      - LOCAL_EMBEDDING_URL=http://host.docker.internal:8003
      - LOCAL_RERANKER_URL=http://host.docker.internal:8002
      - OLLAMA_HOST=http://host.docker.internal:11434
```

### Docker Compose для продакшна:
```yaml
# deployment/docker-compose.prod.yml  
services:
  backend:
    environment:
      - LOCAL_EMBEDDING_URL=http://localhost:8003
      - LOCAL_RERANKER_URL=http://localhost:8002
      - OLLAMA_HOST=http://localhost:11434
      - NODE_ENV=production
    restart: unless-stopped
```

### Systemd сервисы:
```ini
# deployment/systemd/kb-embedding.service
[Unit]
Description=Knowledge Base Embedding Service
After=network.target

[Service]
Type=simple
User=kb-app
WorkingDirectory=/opt/knowledge-base
Environment=PYTHONPATH=/opt/knowledge-base
ExecStart=/opt/knowledge-base/venv/bin/python ml-services/embedding_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 🔧 ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ

### Разработка (.env.dev):
```env
NODE_ENV=development
LOCAL_EMBEDDING_URL=http://localhost:8003
LOCAL_RERANKER_URL=http://localhost:8002
OLLAMA_HOST=http://localhost:11434
PLATFORM=macos
```

### Продакшн (.env.prod):
```env
NODE_ENV=production
LOCAL_EMBEDDING_URL=http://localhost:8003
LOCAL_RERANKER_URL=http://localhost:8002
OLLAMA_HOST=http://localhost:11434
PLATFORM=ubuntu
```

## 🎯 ПРЕИМУЩЕСТВА ЭТОГО ПОДХОДА

### ✅ Что решается:
1. **Единая кодовая база** - один репозиторий для всех платформ
2. **Автоматическое развертывание** - один скрипт для обновления
3. **Платформо-специфичные оптимизации** - максимальная производительность везде
4. **Простота разработки** - разработчик работает как обычно
5. **Надежность** - systemd следит за сервисами

### 🔄 Workflow в действии:
1. **Разработка**: Пишете код на macOS как обычно
2. **Тестирование**: Локальные тесты проходят
3. **Коммит**: `git push origin main`
4. **Развертывание**: `./deployment/scripts/deploy.sh`
5. **Готово**: Код работает на Ubuntu сервере

## 🚨 КРИТИЧЕСКИЕ МОМЕНТЫ

### Что нужно учесть:
1. **Производительность**: Ubuntu может быть медленнее - нужно тестировать
2. **Зависимости**: Версии PyTorch могут отличаться
3. **Мониторинг**: Нужно следить за ресурсами на сервере
4. **Бэкапы**: Регулярные бэкапы БД и конфигураций

## 📋 ПЛАН РЕАЛИЗАЦИИ

### Сегодня:
1. Создать структуру папок
2. Адаптировать ML-сервисы
3. Создать конфигурационные файлы

### Завтра:
1. Настроить сервер
2. Протестировать развертывание
3. Настроить мониторинг

### На неделе:
1. Полное тестирование
2. Оптимизация производительности
3. Документация

---

**Результат**: Вы разрабатываете на macOS, а продакшн автоматически обновляется на Ubuntu одной командой! 🚀
