# 🤖 RAG Knowledge Base MVP

Универсальная система для работы с документами на основе RAG (Retrieval-Augmented Generation) с поддержкой локального и продакшн развертывания.

## 🚀 Быстрый старт

### Локальный запуск (один клик)
```bash
# Клонируем репозиторий
git clone https://github.com/FilippDev24/mvp-rag-ai.git
cd mvp-rag-ai

# Запускаем все сервисы
chmod +x start.sh
./start.sh
```

### Продакшн запуск (Ubuntu + GPU)
```bash
# На сервере Ubuntu
chmod +x deployment/start-production.sh
cd deployment
./start-production.sh
```

## 📋 Содержание

- [Архитектура системы](#-архитектура-системы)
- [Системные требования](#-системные-требования)
- [Установка и настройка](#-установка-и-настройка)
- [Запуск сервисов](#-запуск-сервисов)
- [API документация](#-api-документация)
- [Конфигурация](#-конфигурация)
- [Мониторинг](#-мониторинг)
- [Устранение неполадок](#-устранение-неполадок)

## 🏗️ Архитектура системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Worker        │
│   (React)       │◄──►│   (Node.js)     │◄──►│   (Python)      │
│   Port: 3000    │    │   Port: 3001    │    │   (Celery)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   PostgreSQL    │              │
         │              │   Port: 5432    │              │
         │              └─────────────────┘              │
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────┤     Redis       │◄─────────────┘
                        │   Port: 6379    │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │   ChromaDB      │
                        │   Port: 8012    │
                        └─────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ML Services (Host)                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│ Embedding       │ Reranker        │ LLM                         │
│ Service         │ Service         │ (vLLM/Ollama)               │
│ Port: 8003      │ Port: 8002      │ Port: 8000                  │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Компоненты системы

- **Frontend**: React приложение с интерфейсом для загрузки документов и чата
- **Backend**: Node.js API сервер с аутентификацией и бизнес-логикой
- **Worker**: Python сервис для обработки документов и ML операций
- **PostgreSQL**: Основная база данных для метаданных
- **Redis**: Очередь задач для Celery и кэширование
- **ChromaDB**: Векторная база данных для эмбеддингов
- **ML Services**: Локальные сервисы для эмбеддингов, ранжирования и генерации

## 💻 Системные требования

### Минимальные требования (локальная разработка)
- **OS**: macOS 10.15+ или Ubuntu 20.04+
- **RAM**: 8 GB
- **CPU**: 4 ядра
- **Диск**: 20 GB свободного места
- **Docker**: 20.10+
- **Python**: 3.8+
- **Node.js**: 18+

### Рекомендуемые требования (продакшн)
- **OS**: Ubuntu 22.04 LTS
- **RAM**: 32 GB+
- **CPU**: 8+ ядер
- **GPU**: NVIDIA с 16+ GB VRAM (для vLLM)
- **Диск**: 100+ GB SSD
- **Docker**: 24.0+ с NVIDIA Container Toolkit

## 🛠️ Установка и настройка

### 1. Клонирование репозитория
```bash
git clone https://github.com/FilippDev24/mvp-rag-ai.git
cd mvp-rag-ai
```

### 2. Настройка окружения

#### Локальная разработка
```bash
# Копируем и настраиваем .env файл
cp .env.example .env
nano .env  # Редактируем при необходимости
```

#### Продакшн
```bash
# Настраиваем продакшн окружение
cp deployment/.env.prod deployment/.env.prod.local
nano deployment/.env.prod.local  # Обязательно измените пароли!
```

### 3. Установка зависимостей

#### Docker (обязательно)
```bash
# Ubuntu
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# macOS
# Установите Docker Desktop с официального сайта
```

#### NVIDIA Docker (для продакшн с GPU)
```bash
# Ubuntu
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

## 🚀 Запуск сервисов

### Локальная разработка

#### Автоматический запуск (рекомендуется)
```bash
# Запуск всех сервисов
./start.sh

# Запуск с пересборкой образов
./start.sh --rebuild

# Запуск только Docker сервисов (без ML)
./start.sh --skip-ml

# Очистка Docker перед запуском
./start.sh --cleanup

# Агрессивная очистка (включая volumes с данными)
./start.sh --cleanup-aggressive

# Подробный вывод
./start.sh --verbose
```

#### Ручной запуск
```bash
# 1. Запуск ML сервисов
./start_ml_services.sh

# 2. Запуск Docker сервисов
docker-compose up -d

# 3. Проверка статуса
docker-compose ps
```

### Продакшн развертывание

#### На Ubuntu сервере
```bash
cd deployment

# Стандартный запуск (vLLM на хосте)
./start-production.sh

# Запуск с vLLM в Docker контейнере
./start-production.sh --vllm-container

# Запуск с пересборкой
./start-production.sh --rebuild

# Очистка Docker перед запуском
./start-production.sh --cleanup
```

#### Настройка vLLM на хосте
```bash
# Установка vLLM
pip install vllm

# Запуск gpt-oss-20b модели
vllm serve openai/gpt-oss-20b \
  --dtype bfloat16 \
  --max-model-len 8192 \
  --host 0.0.0.0 \
  --port 8000
```

### Остановка сервисов

```bash
# Локально
./stop.sh

# Продакшн
cd deployment
./stop-production.sh

# Полная очистка (удаление данных)
./stop.sh --clean-all

# Глубокая очистка Docker системы
./cleanup-docker.sh

# Агрессивная очистка (включая volumes)
./cleanup-docker.sh --aggressive
```

## 📚 API документация

### Основные endpoints

#### Аутентификация
```bash
# Регистрация
POST /api/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "User Name"
}

# Вход
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

#### Документы
```bash
# Загрузка документа
POST /api/documents/upload
Content-Type: multipart/form-data
- file: document.docx
- title: "Document Title"
- accessLevel: 50

# Список документов
GET /api/documents

# Получение документа
GET /api/documents/:id
```

#### Чат и поиск
```bash
# Поиск по документам
POST /api/chat/search
{
  "query": "Поисковый запрос",
  "limit": 10
}

# Чат с документами
POST /api/chat/query
{
  "message": "Вопрос по документам",
  "conversationId": "uuid"
}
```

### Полная документация
- [Backend API](backend/DOCUMENTS_API.md)
- [Chat API](backend/CHAT_API.md)
- [Postman Collection](backend/postman-collection.json)

## ⚙️ Конфигурация

### Переменные окружения

#### Основные настройки
```env
# База данных
DATABASE_URL=postgresql://user:pass@localhost:5432/knowledge_base

# JWT
JWT_SECRET=your-super-secure-secret-key-32-chars-minimum
JWT_EXPIRY=7d

# ML сервисы
LOCAL_EMBEDDING_URL=http://localhost:8003
LOCAL_RERANKER_URL=http://localhost:8002
VLLM_HOST=http://localhost:8000

# Модели
EMBEDDING_MODEL=intfloat/multilingual-e5-large-instruct
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

#### Продакшн настройки
```env
NODE_ENV=production
LOG_LEVEL=info
POSTGRES_PASSWORD=secure-production-password
```

### Настройка моделей

#### Embedding модель
- **Модель**: `intfloat/multilingual-e5-large-instruct`
- **Размерность**: 1024
- **Поддержка языков**: Русский, английский, многоязычность

#### Reranker модель
- **Модель**: `BAAI/bge-reranker-v2-m3`
- **Максимальная длина**: 512 токенов
- **Поддержка**: Кросс-языковое ранжирование

#### LLM модель
- **Локально**: Ollama (llama3.1, qwen2.5)
- **Продакшн**: vLLM с gpt-oss-20b

## 📊 Мониторинг

### Проверка состояния сервисов

```bash
# Статус Docker контейнеров
docker-compose ps

# Логи сервисов
docker-compose logs -f backend
docker-compose logs -f worker

# Статус ML сервисов
curl http://localhost:8003/health  # Embedding
curl http://localhost:8002/health  # Reranker
curl http://localhost:8000/v1/models  # LLM

# Проверка API
curl http://localhost:3001/api/health
```

### Мониторинг ресурсов

```bash
# Docker статистика
docker stats

# GPU использование (продакшн)
nvidia-smi
watch -n 1 nvidia-smi

# Системные ресурсы
htop
```

### Логи

```bash
# ML сервисы
tail -f logs/embedding_service.log
tail -f logs/reranker_service.log

# Backend
tail -f backend/logs/app.log

# Worker
docker-compose logs -f worker
```

## 🔧 Устранение неполадок

### Частые проблемы

#### 1. Порты заняты
```bash
# Проверка занятых портов
lsof -i :8000  # vLLM
lsof -i :8003  # Embedding
lsof -i :8002  # Reranker

# Остановка процессов
./stop.sh --force

# Глубокая очистка системы
./cleanup-docker.sh --aggressive
```

#### 2. ML сервисы не запускаются
```bash
# Проверка виртуальных окружений
ls -la venv_*

# Пересоздание окружений
rm -rf venv_embedding venv_reranker
./start_ml_services.sh
```

#### 3. Docker проблемы
```bash
# Автоматическая очистка Docker
./cleanup-docker.sh

# Агрессивная очистка (удаляет данные!)
./cleanup-docker.sh --aggressive

# Предварительный просмотр очистки
./cleanup-docker.sh --dry-run

# Пересборка образов после очистки
./start.sh --rebuild --cleanup
```

#### 4. GPU не определяется
```bash
# Проверка NVIDIA драйверов
nvidia-smi

# Проверка Docker GPU поддержки
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Перезапуск Docker
sudo systemctl restart docker
```

### Диагностика

#### Проверка подключений
```bash
# PostgreSQL
psql -h localhost -p 5432 -U admin -d knowledge_base

# Redis
redis-cli -h localhost -p 6379 ping

# ChromaDB
curl http://localhost:8012/api/v1/heartbeat
```

#### Тестирование ML сервисов
```bash
# Embedding сервис
curl -X POST http://localhost:8003/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["test text"]}'

# Reranker сервис
curl -X POST http://localhost:8002/rerank \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "documents": ["doc1", "doc2"]}'
```

## 🔐 Безопасность

### Продакшн рекомендации

1. **Измените все пароли** в `.env.prod`
2. **Настройте firewall** для ограничения доступа
3. **Используйте HTTPS** с SSL сертификатами
4. **Регулярно обновляйте** зависимости
5. **Настройте backup** базы данных

### Настройка SSL (Nginx)
```bash
# Установка Nginx
sudo apt install nginx

# Копирование конфигурации
sudo cp deployment/nginx-rag-ai.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/nginx-rag-ai.conf /etc/nginx/sites-enabled/

# SSL сертификат (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 🧹 Управление Docker системой

### Автоматическая очистка
```bash
# Стандартная очистка (безопасная)
./cleanup-docker.sh

# Агрессивная очистка (удаляет volumes с данными!)
./cleanup-docker.sh --aggressive

# Предварительный просмотр
./cleanup-docker.sh --dry-run

# Очистка только контейнеров
./cleanup-docker.sh --containers-only

# Очистка только образов
./cleanup-docker.sh --images-only
```

### Интеграция с запуском
```bash
# Очистка + запуск
./start.sh --cleanup

# Агрессивная очистка + запуск
./start.sh --cleanup-aggressive

# Продакшн с очисткой
cd deployment && ./start-production.sh --cleanup
```

## 🤝 Разработка

### Структура проекта
```
mvp-rag-ai/
├── backend/          # Node.js API сервер
├── frontend/         # React приложение
├── worker/           # Python обработчик документов
├── deployment/       # Продакшн конфигурация
├── start.sh         # Универсальный запуск
├── stop.sh          # Остановка сервисов
├── cleanup-docker.sh # Очистка Docker системы
├── start-vllm-host.sh # Запуск vLLM на хосте
└── README.md        # Документация
```

### Локальная разработка
```bash
# Backend разработка
cd backend
npm run dev

# Frontend разработка
cd frontend
npm run dev

# Worker разработка
cd worker
python start_worker.py
```

### Тестирование
```bash
# Backend тесты
cd backend
npm test

# Проверка типов
npm run type-check

# Линтер
npm run lint
```

## 📞 Поддержка

### Контакты
- **GitHub**: [FilippDev24/mvp-rag-ai](https://github.com/FilippDev24/mvp-rag-ai)
- **Issues**: [GitHub Issues](https://github.com/FilippDev24/mvp-rag-ai/issues)

### Полезные ссылки
- [Docker Documentation](https://docs.docker.com/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Ollama Documentation](https://ollama.ai/docs)

---

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей.

---

**🚀 Готово к запуску! Выполните `./start.sh` для начала работы.**
