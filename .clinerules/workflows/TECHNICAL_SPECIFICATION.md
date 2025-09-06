# ТЕХНИЧЕСКОЕ ЗАДАНИЕ: MVP База знаний с RAG

## 1. Архитектура системы

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React     │────▶│  Node.js    │────▶│  PostgreSQL │
│   Frontend  │     │   API       │     │   Database  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
            ┌─────────────┐ ┌─────────────┐
            │   ChromaDB  │ │   Ollama    │
            │  (Vectors)  │ │   (LLM)     │
            └─────────────┘ └─────────────┘
                    ▲
            ┌─────────────┐
            │   Redis     │
            │   + Celery  │
            │  (Workers)  │
            └─────────────┘
```

## 2. Технологический стек

### Backend
- **API**: Node.js + Express + TypeScript
- **ORM**: Prisma (знают все AI-агенты)
- **Обработка документов**: Python + Celery
- **Очередь**: Redis + BullMQ (Node) + Celery (Python)
- **База данных**: PostgreSQL
- **Векторная БД**: ChromaDB
- **Эмбеддинги**: sentence-transformers (multilingual-e5-large)
- **LLM**: Ollama (qwen2.5:3b, gpt-oss:20b)
- **Аутентификация**: JWT + bcrypt

### Frontend
- **Framework**: React + TypeScript
- **UI**: Ant Design или Chakra UI (готовые компоненты)
- **State**: Zustand (проще Redux)
- **HTTP**: Axios
- **Markdown**: react-markdown

## 3. Структура базы данных

```sql
-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    access_level INTEGER DEFAULT 10,
    role ENUM('admin', 'user') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Документы
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_type VARCHAR(50),
    access_level INTEGER DEFAULT 50,
    uploaded_by UUID REFERENCES users(id),
    processed BOOLEAN DEFAULT FALSE,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Чанки
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT,
    access_level INTEGER,
    char_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- История чатов
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Сообщения
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role ENUM('user', 'assistant', 'system'),
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 4. API Endpoints

```typescript
// Аутентификация
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me

// Документы
POST   /api/documents/upload
GET    /api/documents
GET    /api/documents/:id
DELETE /api/documents/:id
GET    /api/documents/:id/chunks
PUT    /api/documents/:id/chunks/:chunkId
DELETE /api/documents/:id/chunks/:chunkId

// Чат
POST   /api/chat/message
GET    /api/chat/sessions
GET    /api/chat/sessions/:id
DELETE /api/chat/sessions/:id

// Админ
POST   /api/admin/users
PUT    /api/admin/users/:id
DELETE /api/admin/users/:id
```

## 5. Обработка документов (Python Worker)

```python
# Структура обработчиков
document_processors/
├── base_processor.py       # Абстрактный класс
├── docx_processor.py       # Word документы
├── pdf_processor.py        # PDF (в будущем)
├── csv_processor.py        # CSV/Excel
├── json_processor.py       # JSON
└── url_processor.py        # Веб-страницы (в будущем)
```

### Метаданные чанков

```json
{
  "document_id": "uuid",
  "document_title": "string",
  "chunk_index": 0,
  "total_chunks": 10,
  "access_level": 50,
  "char_start": 0,
  "char_end": 1000,
  "overlap_prev": 100,
  "overlap_next": 100,
  "file_type": "docx",
  "section_title": "Глава 1",
  "page_number": 1,
  "created_at": "2024-01-01T00:00:00Z",
  "keywords": ["ключевое", "слово"],
  "language": "ru"
}
```

## 6. RAG Pipeline

```python
# Процесс поиска
1. Query → Embedding (multilingual-e5-large)
2. ChromaDB search (top 30)
3. Filter by access_level
4. Rerank with cross-encoder (top 10)
5. Build context with metadata
6. Send to Ollama with system prompt
7. Stream response to frontend
```

## 7. Конфигурация Docker Compose

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: knowledge_base
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  chroma:
    image: chromadb/chroma
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma

  api:
    build: ./backend
    ports:
      - "3001:3001"
    depends_on:
      - postgres
      - redis
      - chroma
    environment:
      DATABASE_URL: postgresql://admin:secure_password@postgres:5432/knowledge_base
      REDIS_URL: redis://redis:6379
      CHROMA_URL: http://chroma:8000

  worker:
    build: ./worker
    depends_on:
      - redis
      - postgres
      - chroma
    environment:
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://admin:secure_password@postgres:5432/knowledge_base
      CHROMA_URL: http://chroma:8000

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
  chroma_data:
```

## 8. Ключевые настройки

```javascript
// config.js
export const CONFIG = {
  chunking: {
    size: 1000,
    overlap: 100,
    minSize: 200
  },
  embedding: {
    model: 'intfloat/multilingual-e5-large',
    dimension: 1024
  },
  reranking: {
    model: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
    topK: 10
  },
  llm: {
    model: 'qwen2.5:3b', // или 'gpt-oss:20b'
    temperature: 0.7,
    maxTokens: 2000
  },
  search: {
    initialResults: 30,
    finalResults: 10
  }
};
```

## 9. Интерфейс предпросмотра чанков

```typescript
interface ChunkPreview {
  id: string;
  index: number;
  content: string;
  charCount: number;
  metadata: {
    overlap_prev: number;
    overlap_next: number;
    section_title?: string;
  };
  highlighted?: boolean;
  editable: boolean;
}
```

## 10. Этапы разработки

### Фаза 1: Фундамент (3-4 дня)
- Структура проекта + Docker Compose
- База данных + Prisma миграции
- JWT аутентификация
- Базовый API

### Фаза 2: Обработка документов (2-3 дня)
- Celery воркеры
- DOCX процессор + чанкинг
- Эмбеддинги + ChromaDB
- Предпросмотр чанков UI

### Фаза 3: RAG (2-3 дня)
- Поисковый pipeline
- Интеграция Ollama
- Streaming ответов
- Cross-encoder ранжирование

### Фаза 4: UI/UX (2-3 дня)
- Чат интерфейс
- Управление документами
- История сессий
- Админ панель

### Фаза 5: Оптимизация (ongoing)
- Тестирование качества
- Настройка промптов
- A/B тесты моделей
- Метрики и логирование

## Команды для старта

```bash
# Установка зависимостей
cd backend && npm install
cd ../worker && pip install -r requirements.txt
cd ../frontend && npm install

# Запуск Ollama
ollama pull qwen2.5:3b
ollama pull gpt-oss:20b

# Запуск системы
docker-compose up -d
npm run migrate # в backend
npm run dev # в каждой папке
```

## ПРИНЦИП

Эта архитектура масштабируется горизонтально. Можно добавлять воркеры, реплики API, новые типы документов без переписывания кода.

## Дополнительные требования

### Безопасность
- Валидация всех входных данных
- Rate limiting для API
- Санитизация загружаемых файлов
- Логирование всех операций

### Производительность
- Кэширование частых запросов
- Пагинация для больших списков
- Оптимизация SQL запросов
- Мониторинг производительности

### Мониторинг
- Health checks для всех сервисов
- Метрики использования
- Логирование ошибок
- Алерты при сбоях

### Тестирование
- Unit тесты для критичных функций
- Integration тесты для API
- E2E тесты для основных сценариев
- Load тесты для проверки нагрузки
