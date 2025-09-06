# Chat RAG API Documentation

## Overview

RAG (Retrieval-Augmented Generation) Chat API для Knowledge Base MVP согласно техническим требованиям.

## RAG Pipeline Process

1. **Query → Embedding** (multilingual-e5-large)
2. **ChromaDB search** (top 30)
3. **Filter by access_level** 
4. **Rerank with cross-encoder** (top 10)
5. **Build context with metadata**
6. **Send to Ollama** with system prompt
7. **Stream response** to frontend

## Authentication

Все endpoints требуют JWT токен в заголовке:
```
Authorization: Bearer <jwt_token>
```

## Endpoints

### POST /api/chat/message

Основной endpoint для RAG запросов.

**Request:**
```json
{
  "message": "Что такое искусственный интеллект?",
  "sessionId": "uuid-optional"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "answer": "Искусственный интеллект - это...",
    "sources": [
      {
        "chunk": {
          "id": "doc1_0",
          "documentId": "doc1",
          "chunkIndex": 0,
          "content": "Текст чанка...",
          "accessLevel": 50
        },
        "document": {
          "id": "doc1",
          "title": "Введение в ИИ",
          "accessLevel": 50
        },
        "score": 0.85,
        "relevance": 0.92
      }
    ],
    "sessionId": "session-uuid",
    "messageId": "message-uuid",
    "metadata": {
      "processingTime": 1500,
      "chunksUsed": 5,
      "model": "llama3.1",
      "timestamp": "2024-01-01T00:00:00.000Z"
    }
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00.000Z",
    "processingTime": 1500
  }
}
```

### POST /api/chat/stream

Streaming endpoint для RAG ответов.

**Request:** Аналогично `/api/chat/message`

**Response:** Server-Sent Events (SSE)

```
event: sources
data: {"sources": [...], "totalFound": 15, "rerankedCount": 10}

event: answer
data: {"text": "Искусственный", "done": false}

event: answer
data: {"text": " интеллект", "done": false}

event: answer
data: {"text": "", "done": true}

event: end
data: {}
```

### GET /api/chat/sessions

Получение списка сессий пользователя.

**Query Parameters:**
- `page` (optional): Номер страницы (default: 1)
- `limit` (optional): Количество на странице (default: 20, max: 100)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "session-uuid",
      "title": "Вопрос об ИИ...",
      "createdAt": "2024-01-01T00:00:00.000Z",
      "updatedAt": "2024-01-01T00:00:00.000Z",
      "messages": [
        {
          "id": "message-uuid",
          "role": "assistant",
          "content": "Последнее сообщение...",
          "createdAt": "2024-01-01T00:00:00.000Z"
        }
      ]
    }
  ],
  "metadata": {
    "page": 1,
    "total": 5,
    "totalPages": 1,
    "hasNext": false,
    "hasPrev": false,
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

### GET /api/chat/sessions/:sessionId

Получение сообщений сессии.

**Path Parameters:**
- `sessionId`: UUID сессии

**Query Parameters:**
- `page` (optional): Номер страницы (default: 1)
- `limit` (optional): Количество на странице (default: 50, max: 100)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "message-uuid",
      "sessionId": "session-uuid",
      "role": "user",
      "content": "Что такое ИИ?",
      "metadata": {
        "accessLevel": 50
      },
      "createdAt": "2024-01-01T00:00:00.000Z"
    },
    {
      "id": "message-uuid-2",
      "sessionId": "session-uuid",
      "role": "assistant",
      "content": "Искусственный интеллект...",
      "metadata": {
        "sources": [...],
        "processingTime": 1500,
        "chunksUsed": 5,
        "model": "llama3.1"
      },
      "createdAt": "2024-01-01T00:00:00.000Z"
    }
  ],
  "metadata": {
    "page": 1,
    "total": 2,
    "totalPages": 1,
    "hasNext": false,
    "hasPrev": false,
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

### DELETE /api/chat/sessions/:sessionId

Удаление сессии.

**Path Parameters:**
- `sessionId`: UUID сессии

**Response:**
```json
{
  "success": true,
  "data": {
    "sessionId": "session-uuid"
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

## Error Responses

Все ошибки возвращаются в едином формате:

```json
{
  "success": false,
  "error": "Описание ошибки",
  "metadata": {
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

### HTTP Status Codes

- `200` - Успешный запрос
- `400` - Ошибка валидации данных
- `401` - Не авторизован
- `403` - Недостаточно прав доступа
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Access Level Security

**КРИТИЧНО:** Все RAG запросы фильтруются по `accessLevel` пользователя:

- Пользователь с `accessLevel: 50` видит только документы с `accessLevel <= 50`
- Фильтрация происходит на уровне ChromaDB запроса
- Нет возможности обойти проверку уровня доступа

## Testing

Запуск тестов:

```bash
# Тестирование Chat API
npm run test:chat
```

## Dependencies

### Backend Services
- **Backend API**: Express.js на порту 3001
- **Worker API**: Flask на порту 8001  
- **Celery Worker**: Обработка RAG задач
- **ChromaDB**: Векторная база данных на порту 8002
- **Ollama**: LLM сервис на порту 11434
- **Redis**: Очередь задач на порту 6379
- **PostgreSQL**: Основная БД на порту 5432

### RAG Pipeline Components
1. **Embedding Service**: `intfloat/multilingual-e5-large`
2. **Vector Search**: ChromaDB с cosine similarity
3. **Reranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
4. **LLM**: Ollama с моделью `llama3.1`

## Performance Metrics

Типичные времена обработки:
- **Embedding генерация**: 100-300ms
- **ChromaDB поиск**: 50-150ms  
- **Реранжирование**: 200-500ms
- **Ollama генерация**: 1000-3000ms
- **Общее время**: 1500-4000ms

## Rate Limiting

- Максимум 60 запросов в минуту на пользователя
- Максимум 10 одновременных запросов на пользователя
- Таймаут запроса: 120 секунд

## Monitoring

Логируются все:
- RAG запросы с временем обработки
- Ошибки поиска и генерации
- Метрики качества ответов
- Использование ресурсов
