# Knowledge Base MVP with RAG

Система управления базой знаний с поддержкой RAG (Retrieval-Augmented Generation) для интеллектуального поиска и ответов на вопросы по загруженным документам.

## Архитектура

- **Backend**: Node.js + TypeScript + Express + Prisma
- **Worker**: Python + Celery для обработки документов и генерации эмбеддингов
- **Frontend**: React + TypeScript + Vite
- **База данных**: PostgreSQL
- **Векторная БД**: ChromaDB
- **Кэш/Очереди**: Redis
- **LLM**: Ollama

## Структура проекта

```
mvp-rag-ai/
├── backend/                 # Node.js API сервер
│   ├── src/
│   │   ├── controllers/     # Контроллеры API
│   │   ├── services/        # Бизнес-логика
│   │   ├── middlewares/     # Middleware
│   │   ├── routes/          # Маршруты API
│   │   ├── utils/           # Утилиты
│   │   └── index.ts         # Точка входа
│   ├── prisma/
│   │   └── schema.prisma    # Схема базы данных
│   ├── package.json
│   └── tsconfig.json
├── worker/                  # Python Celery worker
│   ├── processors/          # Обработчики документов
│   ├── tasks.py            # Celery задачи
│   ├── celery_app.py       # Конфигурация Celery
│   └── requirements.txt
├── frontend/               # React приложение
│   ├── src/
│   │   ├── components/     # React компоненты
│   │   ├── pages/          # Страницы
│   │   ├── services/       # API клиенты
│   │   ├── store/          # Состояние приложения
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml      # Docker конфигурация
└── .env.example           # Пример переменных окружения
```

## Быстрый старт

### 1. Клонирование и настройка

```bash
# Создать .env файл из примера
cp .env.example .env

# Отредактировать переменные окружения при необходимости
nano .env
```

### 2. Запуск с Docker

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус сервисов
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

### 3. Инициализация базы данных

```bash
# Войти в контейнер backend
docker-compose exec backend bash

# Сгенерировать Prisma клиент
npm run prisma:generate

# Применить миграции
npm run prisma:migrate

# (Опционально) Открыть Prisma Studio
npm run prisma:studio
```

### 4. Настройка Ollama

```bash
# Войти в контейнер Ollama
docker-compose exec ollama bash

# Скачать модель (например, llama2)
ollama pull llama2

# Проверить доступные модели
ollama list
```

## Разработка без Docker

### Backend

```bash
cd backend
npm install
npm run prisma:generate
npm run prisma:migrate
npm run dev
```

### Worker

```bash
cd worker
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Документы
- `POST /api/documents` - Загрузка документа
- `GET /api/documents` - Список документов
- `GET /api/documents/:id` - Получить документ
- `DELETE /api/documents/:id` - Удалить документ

### Запросы
- `POST /api/query` - Задать вопрос к базе знаний
- `GET /api/queries` - История запросов

### Система
- `GET /health` - Проверка здоровья API
- `GET /api/status` - Статус обработки документов

## Переменные окружения

Основные переменные (см. `.env.example`):

- `DATABASE_URL` - Строка подключения к PostgreSQL
- `REDIS_URL` - URL Redis сервера
- `CHROMA_HOST/PORT` - Настройки ChromaDB
- `OLLAMA_HOST` - URL Ollama сервера
- `JWT_SECRET` - Секретный ключ для JWT
- `EMBEDDING_MODEL` - Модель для генерации эмбеддингов
- `LLM_MODEL` - Модель для генерации ответов

## Мониторинг

### Проверка сервисов

```bash
# Проверка API
curl http://localhost:3001/health

# Проверка ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Проверка Ollama
curl http://localhost:11434/api/tags

# Проверка Redis
redis-cli ping
```

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f worker
```

## Разработка

### Добавление новых зависимостей

```bash
# Backend
docker-compose exec backend npm install package-name

# Worker
docker-compose exec worker pip install package-name

# Frontend
docker-compose exec frontend npm install package-name
```

### Работа с базой данных

```bash
# Создать миграцию
docker-compose exec backend npx prisma migrate dev --name migration_name

# Сбросить базу данных
docker-compose exec backend npx prisma migrate reset
```

## Производство

Для продакшена рекомендуется:

1. Использовать отдельные Docker образы для каждого сервиса
2. Настроить reverse proxy (nginx)
3. Использовать внешние управляемые сервисы для БД
4. Настроить мониторинг и логирование
5. Использовать секреты для чувствительных данных

## Лицензия

MIT
