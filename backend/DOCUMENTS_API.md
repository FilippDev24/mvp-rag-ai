# Documents API - Knowledge Base RAG MVP

Полная документация по API для управления документами в системе Knowledge Base RAG MVP.

## 🚀 Быстрый старт

### 1. Запуск сервера
```bash
cd backend
npm run dev
```

### 2. Тестирование API
```bash
# Тест аутентификации
npm run test:auth

# Тест API документов
npm run test:documents
```

### 3. Postman коллекция
Импортируйте файл `documents-postman-collection.json` в Postman для интерактивного тестирования.

## 📋 API Endpoints

### Аутентификация
Все endpoints требуют JWT токен в заголовке `Authorization: Bearer <token>`

### Документы

#### `POST /api/documents/upload`
Загрузка нового документа

**Параметры (multipart/form-data):**
- `file` (file, required) - Файл документа
- `title` (string, required) - Название документа
- `accessLevel` (number, optional) - Уровень доступа (1-100, по умолчанию = уровень пользователя)

**Поддерживаемые форматы:**
- PDF (.pdf)
- Word (.docx, .doc)
- Текст (.txt)
- CSV (.csv)
- JSON (.json)
- Markdown (.md)
- RTF (.rtf)

**Ограничения:**
- Максимальный размер файла: 10MB
- Максимум 10 загрузок в минуту на пользователя

**Пример запроса:**
```bash
curl -X POST http://localhost:3001/api/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "title=My Document" \
  -F "accessLevel=50"
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "My Document",
    "filePath": "uploads/file-123456789.pdf",
    "fileType": "application/pdf",
    "accessLevel": 50,
    "uploadedBy": "user-id",
    "processed": false,
    "chunkCount": 0,
    "createdAt": "2024-01-01T00:00:00.000Z",
    "metadata": {
      "originalName": "document.pdf",
      "size": 1024000,
      "uploadedAt": "2024-01-01T00:00:00.000Z"
    },
    "user": {
      "id": "user-id",
      "email": "user@example.com",
      "fullName": "User Name"
    }
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

#### `GET /api/documents`
Получить список документов

**Query параметры:**
- `page` (number, optional) - Номер страницы (по умолчанию: 1)
- `limit` (number, optional) - Количество документов на странице (по умолчанию: 20, максимум: 100)

**Пример запроса:**
```bash
curl -X GET "http://localhost:3001/api/documents?page=1&limit=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "title": "Document 1",
      "fileType": "application/pdf",
      "accessLevel": 50,
      "processed": true,
      "chunkCount": 15,
      "createdAt": "2024-01-01T00:00:00.000Z",
      "user": {
        "id": "user-id",
        "email": "user@example.com",
        "fullName": "User Name"
      }
    }
  ],
  "metadata": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "totalPages": 1,
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

#### `GET /api/documents/:id`
Получить документ по ID

**Пример запроса:**
```bash
curl -X GET http://localhost:3001/api/documents/DOCUMENT_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### `DELETE /api/documents/:id`
Удалить документ

**Права доступа:**
- Администратор может удалить любой документ
- Пользователь может удалить только свои документы

**Пример запроса:**
```bash
curl -X DELETE http://localhost:3001/api/documents/DOCUMENT_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Чанки документов

#### `GET /api/documents/:id/chunks`
Получить чанки документа

**Query параметры:**
- `page` (number, optional) - Номер страницы (по умолчанию: 1)
- `limit` (number, optional) - Количество чанков на странице (по умолчанию: 50, максимум: 200)

**Пример запроса:**
```bash
curl -X GET "http://localhost:3001/api/documents/DOCUMENT_ID/chunks?page=1&limit=50" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Ответ:**
```json
{
  "success": true,
  "data": [
    {
      "id": "chunk-uuid",
      "documentId": "document-uuid",
      "chunkIndex": 0,
      "content": "Содержимое чанка...",
      "accessLevel": 50,
      "charCount": 500,
      "createdAt": "2024-01-01T00:00:00.000Z",
      "metadata": {}
    }
  ],
  "metadata": {
    "page": 1,
    "limit": 50,
    "total": 15,
    "totalPages": 1,
    "timestamp": "2024-01-01T00:00:00.000Z"
  }
}
```

#### `PUT /api/documents/:id/chunks/:chunkId`
Обновить чанк

**Права доступа:**
- Требуется уровень доступа 20+
- Администратор может редактировать любые чанки
- Пользователь может редактировать только чанки своих документов

**Body (JSON):**
```json
{
  "content": "Новое содержимое чанка",
  "metadata": {
    "updated": true,
    "updatedAt": "2024-01-01T00:00:00.000Z"
  }
}
```

**Пример запроса:**
```bash
curl -X PUT http://localhost:3001/api/documents/DOCUMENT_ID/chunks/CHUNK_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated content"}'
```

#### `DELETE /api/documents/:id/chunks/:chunkId`
Удалить чанк

**Права доступа:**
- Требуется уровень доступа 20+
- Администратор может удалить любые чанки
- Пользователь может удалить только чанки своих документов

**Пример запроса:**
```bash
curl -X DELETE http://localhost:3001/api/documents/DOCUMENT_ID/chunks/CHUNK_ID \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔐 Безопасность

### Уровни доступа
- **1-9**: Базовый доступ (чтение)
- **10-19**: Загрузка документов
- **20-49**: Редактирование чанков
- **50-99**: Расширенные права
- **100**: Администратор

### Проверки безопасности
1. **JWT аутентификация** - все endpoints требуют валидный токен
2. **Проверка уровня доступа** - каждый endpoint проверяет минимальный уровень
3. **Фильтрация по уровню доступа** - пользователи видят только документы с подходящим уровнем
4. **Проверка владельца** - пользователи могут редактировать/удалять только свои документы (кроме админов)
5. **Rate limiting** - ограничение на количество загрузок
6. **Валидация файлов** - проверка типа и размера файлов

## 🧪 Тестирование

### Автоматические тесты
```bash
# Запуск всех тестов документов
npm run test:documents
```

Тесты покрывают:
- ✅ Аутентификацию
- ✅ Загрузку документов
- ✅ Получение списка документов
- ✅ Получение документа по ID
- ✅ Получение чанков документа
- ✅ Обновление чанков
- ✅ Удаление документов
- ✅ Обработку ошибок
- ✅ Проверку безопасности

### Postman коллекция
1. Импортируйте `documents-postman-collection.json`
2. Установите переменную `base_url` = `http://localhost:3001`
3. Запустите тест "Login" для получения JWT токена
4. Токен автоматически сохранится в переменной `jwt_token`
5. Запускайте остальные тесты

### Ручное тестирование

#### 1. Получение JWT токена
```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "Admin123!"}'
```

#### 2. Загрузка тестового документа
```bash
# Создайте тестовый файл
echo "This is a test document content." > test.txt

# Загрузите документ
curl -X POST http://localhost:3001/api/documents/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@test.txt" \
  -F "title=Test Document" \
  -F "accessLevel=50"
```

#### 3. Проверка списка документов
```bash
curl -X GET http://localhost:3001/api/documents \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔄 Интеграция с Worker

После загрузки документа:
1. Файл сохраняется в папку `uploads/`
2. Задача отправляется в Redis для обработки
3. Worker (Celery) обрабатывает документ:
   - Извлекает текст
   - Разбивает на чанки
   - Создает эмбеддинги
   - Сохраняет в ChromaDB
4. Статус `processed` обновляется на `true`
5. Счетчик `chunkCount` обновляется

## 📊 Мониторинг

### Логи
Все операции логируются в:
- `logs/combined.log` - все логи
- `logs/error.log` - только ошибки

### Метрики для отслеживания
- Время загрузки документов
- Количество обработанных документов
- Размер загруженных файлов
- Количество созданных чанков
- Ошибки обработки

## ❌ Коды ошибок

| Код | Описание |
|-----|----------|
| 400 | Неверные данные запроса |
| 401 | Не авторизован |
| 403 | Недостаточно прав доступа |
| 404 | Документ не найден |
| 413 | Файл слишком большой |
| 415 | Неподдерживаемый тип файла |
| 429 | Слишком много запросов |
| 500 | Внутренняя ошибка сервера |

## 🔧 Конфигурация

### Переменные окружения
```env
# Обязательные
DATABASE_URL=postgresql://user:password@localhost:5432/knowledge_base
JWT_SECRET=your-secret-key

# Опциональные
MAX_FILE_SIZE=10485760  # 10MB в байтах
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# Для продакшена
NODE_ENV=production
LOG_LEVEL=info
```

### Константы (src/types/index.ts)
```typescript
export const CONSTANTS = {
  MAX_FILE_SIZE: 10 * 1024 * 1024,  // 10MB
  MAX_CHUNKS_PER_DOC: 1000,
  ACCESS_LEVEL_MIN: 1,
  ACCESS_LEVEL_MAX: 100,
  ACCESS_LEVEL_DEFAULT: 50
} as const;
```

## 🚨 Troubleshooting

### Частые проблемы

#### 1. "Authentication required"
- Проверьте, что JWT токен передается в заголовке
- Убедитесь, что токен не истек
- Проверьте формат: `Authorization: Bearer <token>`

#### 2. "File too large"
- Максимальный размер файла: 10MB
- Проверьте переменную `MAX_FILE_SIZE`

#### 3. "File type not supported"
- Поддерживаются: PDF, DOCX, DOC, TXT, CSV, JSON, MD, RTF
- Проверьте расширение и MIME-type файла

#### 4. "Document not found or access denied"
- Документ может не существовать
- У пользователя может не быть прав доступа
- Проверьте `accessLevel` документа и пользователя

#### 5. Redis connection errors
- Убедитесь, что Redis запущен
- Проверьте настройки подключения в `.env`

### Отладка
```bash
# Проверка здоровья системы
curl http://localhost:3001/health

# Проверка логов
tail -f backend/logs/combined.log

# Проверка Redis
redis-cli ping
