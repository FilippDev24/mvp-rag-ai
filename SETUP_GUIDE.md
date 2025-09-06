# 🚀 Инструкция по запуску Knowledge Base RAG MVP

## 📋 Системные требования

### Минимальные требования:
- **Docker** и **Docker Compose** (рекомендуется Docker Desktop)
- **Ollama** (для локального LLM)
- **8 GB RAM** (минимум)
- **10 GB** свободного места на диске
- **macOS/Linux/Windows** с поддержкой Docker

### Рекомендуемые требования:
- **16 GB RAM** или больше
- **SSD диск** для лучшей производительности
- **Многоядерный процессор** (4+ ядра)

## 🛠️ Пошаговая инструкция по запуску

### Шаг 1: Подготовка окружения

```bash
# 1. Клонируйте репозиторий (если еще не сделано)
git clone <repository-url>
cd mvp-rag-ai

# 2. Создайте файл переменных окружения
cp .env.example .env
```

### Шаг 2: Настройка переменных окружения

Отредактируйте файл `.env` при необходимости:

```bash
# Откройте файл в любом редакторе
nano .env
# или
code .env
```

**Важные переменные для изменения:**
- `JWT_SECRET` - смените на уникальный секретный ключ (минимум 32 символа)
- `EMBEDDING_MODEL` - по умолчанию используется `intfloat/multilingual-e5-large-instruct`
- `LLM_MODEL` - модель для Ollama (по умолчанию `llama2`)

### Шаг 3: Установка и настройка Ollama

```bash
# Установите Ollama (если еще не установлен)
# macOS:
brew install ollama

# Linux:
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: скачайте с https://ollama.ai/download

# Запустите Ollama сервер
ollama serve

# В новом терминале скачайте модель
ollama pull llama2

# Проверьте, что модель загружена
ollama list
```

### Шаг 4: Запуск проекта

```bash
# Запустите все сервисы
docker-compose up -d

# Проверьте статус всех контейнеров
docker-compose ps
```

**Ожидаемый вывод:**
```
NAME            IMAGE                    STATUS
kb_backend      knowledge-base-backend   Up
kb_chromadb     chromadb/chroma:latest   Up
kb_frontend     node:18-alpine           Up
kb_postgres     postgres:15-alpine       Up
kb_redis        redis:7-alpine           Up
kb_worker       knowledge-base-worker    Up
```

### Шаг 5: Инициализация базы данных

```bash
# Войдите в контейнер backend
docker-compose exec backend sh

# Сгенерируйте Prisma клиент
npm run prisma:generate

# Примените миграции базы данных
npm run prisma:migrate

# Создайте начальные данные (админ пользователь)
npm run seed

# Выйдите из контейнера
exit
```

### Шаг 6: Проверка работоспособности

Откройте в браузере или проверьте через curl:

```bash
# Проверка API backend
curl http://localhost:8014/health
# Ожидаемый ответ: {"status":"ok","timestamp":"..."}

# Проверка ChromaDB
curl http://localhost:8012/api/v1/heartbeat
# Ожидаемый ответ: {"nanosecond heartbeat": ...}

# Проверка Ollama
curl http://localhost:11434/api/tags
# Ожидаемый ответ: {"models":[...]}

# Проверка Redis
docker-compose exec redis redis-cli ping
# Ожидаемый ответ: PONG
```

### Шаг 7: Доступ к приложению

- **Frontend**: http://localhost:8015
- **Backend API**: http://localhost:8014
- **Prisma Studio**: `docker-compose exec backend npm run prisma:studio` (http://localhost:5555)

## 🔐 Первый вход в систему

**Данные администратора по умолчанию:**
- Email: `admin@test.com`
- Пароль: `Admin123!`

⚠️ **ВАЖНО**: Смените пароль администратора после первого входа!

## 📊 Мониторинг и логи

### Просмотр логов:

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f frontend
```

### Проверка состояния сервисов:

```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Проверка здоровья PostgreSQL
docker-compose exec postgres pg_isready -U admin -d knowledge_base
```

## 🔧 Разработка (без Docker)

Если вы хотите запустить сервисы локально для разработки:

### Backend:
```bash
cd backend
npm install
npm run prisma:generate
npm run prisma:migrate
npm run dev
```

### Worker:
```bash
cd worker
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

**Примечание**: При локальном запуске измените порты в `.env` файле на стандартные (без префикса 80xx).

## 📝 Использование системы

### 1. Загрузка документов

1. Войдите в систему через http://localhost:8015
2. Перейдите в раздел "Документы"
3. Нажмите "Загрузить документ"
4. Выберите файл (.docx, .pdf, .txt, .csv, .json)
5. Укажите уровень доступа (1-100)
6. Дождитесь обработки документа

### 2. Поиск и вопросы

1. Перейдите в раздел "Чат" или "Поиск"
2. Задайте вопрос на естественном языке
3. Система найдет релевантные фрагменты и сгенерирует ответ
4. Просмотрите источники ответа

### 3. Управление чанками

1. В разделе "Документы" выберите документ
2. Нажмите "Просмотр чанков"
3. Редактируйте или удаляйте неточные фрагменты
4. Изменения автоматически обновятся в векторной базе

## ❗ Решение проблем

### Проблема: Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose logs

# Пересоберите образы
docker-compose build --no-cache

# Очистите Docker
docker system prune -a
```

### Проблема: Ollama недоступен

```bash
# Проверьте, что Ollama запущен
ollama serve

# Проверьте доступность
curl http://localhost:11434/api/tags

# Для Docker Desktop на Mac/Windows используйте host.docker.internal
```

### Проблема: База данных недоступна

```bash
# Проверьте статус PostgreSQL
docker-compose exec postgres pg_isready -U admin -d knowledge_base

# Пересоздайте базу данных
docker-compose down -v
docker-compose up -d postgres
# Подождите 30 секунд
docker-compose up -d
```

### Проблема: Worker не обрабатывает документы

```bash
# Проверьте логи worker
docker-compose logs -f worker

# Проверьте очереди Redis
docker-compose exec redis redis-cli
> KEYS *
> LLEN celery

# Перезапустите worker
docker-compose restart worker
```

### Проблема: Медленная обработка документов

1. Увеличьте количество worker процессов:
```bash
# В docker-compose.yml измените команду worker на:
command: celery -A celery_app worker --loglevel=info --concurrency=4
```

2. Используйте более быструю модель эмбеддингов:
```bash
# В .env измените на:
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

## 🔄 Обновление системы

```bash
# Остановите сервисы
docker-compose down

# Обновите код
git pull

# Пересоберите образы
docker-compose build

# Запустите с новыми миграциями
docker-compose up -d
docker-compose exec backend npm run prisma:migrate
```

## 🧹 Очистка системы

```bash
# Остановить и удалить все контейнеры
docker-compose down

# Удалить все данные (ОСТОРОЖНО!)
docker-compose down -v

# Очистить Docker образы
docker system prune -a
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь, что все порты свободны
3. Проверьте системные требования
4. Перезапустите Docker Desktop
5. Создайте issue в репозитории с описанием проблемы и логами

## 🎯 Полезные команды

```bash
# Быстрая перезагрузка всех сервисов
docker-compose restart

# Обновление только одного сервиса
docker-compose up -d --no-deps backend

# Выполнение команд в контейнере
docker-compose exec backend npm run prisma:studio
docker-compose exec worker python debug_chromadb.py

# Мониторинг ресурсов
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Бэкап базы данных
docker-compose exec postgres pg_dump -U admin knowledge_base > backup.sql

# Восстановление базы данных
docker-compose exec -T postgres psql -U admin knowledge_base < backup.sql
```

---

**Готово!** 🎉 Ваша система Knowledge Base RAG MVP запущена и готова к использованию.
