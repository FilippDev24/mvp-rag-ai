# Python Worker для Knowledge Base RAG MVP

Этот модуль отвечает за обработку документов, создание эмбеддингов и работу с векторной базой данных ChromaDB.

## 🏗️ Архитектура

```
worker/
├── processors/           # Обработчики документов
│   ├── base_processor.py       # Абстрактный базовый класс
│   ├── docx_processor.py       # Word документы
│   ├── csv_processor.py        # CSV файлы
│   └── json_processor.py       # JSON файлы
├── services/            # Основные сервисы
│   ├── chunking_service.py     # Разбивка на чанки
│   ├── embedding_service.py    # Генерация эмбеддингов
│   └── database_service.py     # Работа с ChromaDB
├── celery_app.py        # Конфигурация Celery
├── tasks.py             # Celery задачи
├── test_worker.py       # Тестовый скрипт
├── requirements.txt     # Python зависимости
├── .env                 # Переменные окружения
└── README.md           # Эта документация
```

## 🔧 Конфигурация

### Переменные окружения (.env)

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379

# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Embedding Model Configuration
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
MAX_SEQ_LENGTH=512
BATCH_SIZE=32

# Processing Configuration
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
MIN_CHUNK_SIZE=200
```

## 📋 Установка и запуск

### 1. Установка зависимостей

```bash
cd worker
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
# Отредактируйте .env файл под ваши настройки
```

### 3. Запуск тестов

```bash
python test_worker.py
```

### 4. Запуск Celery worker

```bash
celery -A celery_app worker --loglevel=info
```

## 🔄 Процесс обработки документов

### ОБЯЗАТЕЛЬНЫЙ порядок согласно требованиям:

1. **Извлечение текста** - используется соответствующий процессор
2. **Очистка текста** - удаление лишних символов и форматирования
3. **Разбивка на чанки** - размер 1000, overlap 100
4. **Создание метаданных** для КАЖДОГО чанка с access_level
5. **Создание эмбеддинга** С ПРЕФИКСОМ "passage: "
6. **Сохранение в ChromaDB** с метаданными

### Метаданные чанков

```json
{
  "doc_id": "uuid",
  "chunk_index": 0,
  "access_level": 50,
  "char_start": 0,
  "char_end": 1000,
  "created_at": "2024-01-01T00:00:00Z",
  "char_count": 1000,
  "overlap_prev": 100,
  "overlap_next": 100,
  "total_chunks": 10
}
```

## 🎯 Основные задачи Celery

### process_document

Обработка загруженного документа:

```python
from tasks import process_document

result = process_document.delay(
    document_id="doc_123",
    file_path="/path/to/file.docx",
    access_level=50,
    document_title="Название документа"
)
```

### query_knowledge_base

Поиск в базе знаний:

```python
from tasks import query_knowledge_base

result = query_knowledge_base.delay(
    query="Поисковый запрос",
    access_level=50,
    top_k=30
)
```

### delete_document

Удаление документа из ChromaDB:

```python
from tasks import delete_document

result = delete_document.delay(document_id="doc_123")
```

### health_check

Проверка здоровья worker:

```python
from tasks import health_check

result = health_check.delay()
```

## 🔍 Поддерживаемые форматы файлов

| Формат | Расширение | Процессор | Описание |
|--------|------------|-----------|----------|
| Word | `.docx` | DocxProcessor | Извлечение текста из параграфов и таблиц |
| CSV | `.csv` | CsvProcessor | Структурированное представление данных |
| JSON | `.json` | JsonProcessor | Рекурсивное извлечение всех текстовых значений |

## 🧠 Модель эмбеддингов

### Используемая модель: `intfloat/multilingual-e5-large`

**КРИТИЧЕСКИЕ настройки (НЕ МЕНЯТЬ!):**
- Размерность: 1024
- Максимальная длина: 512 токенов
- Метрика расстояния: cosine
- Нормализация: обязательна

### Префиксы

- **Документы**: `"passage: " + text`
- **Запросы**: `"query: " + text`

## 🗄️ ChromaDB

### Конфигурация коллекции

```python
COLLECTION_NAME = "documents"
DISTANCE_METRIC = "cosine"  # НЕ МЕНЯТЬ!
```

### Фильтрация по уровню доступа

**КРИТИЧНО**: В КАЖДОМ запросе проверяется access_level:

```python
results = collection.query(
    query_embeddings=[embedding],
    where={"access_level": {"$lte": user_access_level}}
)
```

## 🔒 Безопасность

### Уровни доступа

- Минимальный: 1
- Максимальный: 100
- По умолчанию: 50

### Проверки

1. **Каждый чанк** содержит access_level в метаданных
2. **Каждый поиск** фильтруется по access_level пользователя
3. **Валидация файлов** перед обработкой

## 📊 Мониторинг и логирование

### Логируемые события

- Все операции обработки документов
- Все ошибки с полным стеком
- Статистика генерации эмбеддингов
- Операции с ChromaDB

### Метрики

- Время обработки документа
- Количество созданных чанков
- Размер эмбеддингов
- Результаты поиска

## 🧪 Тестирование

### Запуск всех тестов

```bash
python test_worker.py
```

### Тестируемые компоненты

1. **Процессоры документов** - инициализация и поддерживаемые форматы
2. **ChunkingService** - создание чанков и статистика
3. **EmbeddingService** - генерация эмбеддингов
4. **DatabaseService** - подключение к ChromaDB
5. **Полный пайплайн** - от документа до поиска

## ⚠️ Частые проблемы

### ChromaDB недоступен

```
❌ Ошибка в DatabaseService: Connection refused
```

**Решение**: Убедитесь, что ChromaDB запущен:
```bash
docker run -p 8000:8000 chromadb/chroma
```

### Модель эмбеддингов не загружается

```
❌ Ошибка в EmbeddingService: Model not found
```

**Решение**: Модель загрузится автоматически при первом запуске. Требуется интернет-соединение.

### Недостаточно памяти

```
❌ CUDA out of memory
```

**Решение**: Уменьшите BATCH_SIZE в конфигурации или используйте CPU:
```python
device = "cpu"  # вместо "cuda"
```

## 🚀 Производительность

### Рекомендуемые настройки

- **BATCH_SIZE**: 32 (для GPU), 8 (для CPU)
- **WORKER_CONCURRENCY**: количество CPU ядер
- **CHUNK_SIZE**: 1000 символов
- **CHUNK_OVERLAP**: 100 символов

### Оптимизация

1. Используйте GPU для генерации эмбеддингов
2. Настройте пул соединений для ChromaDB
3. Кэшируйте модель эмбеддингов
4. Мониторьте использование памяти

## 📝 Логи

### Уровни логирования

- **INFO**: Основные операции
- **ERROR**: Ошибки с полным контекстом
- **DEBUG**: Детальная отладочная информация

### Пример лога

```
2024-01-01 12:00:00 - tasks - INFO - Starting document processing for document_id: doc_123
2024-01-01 12:00:01 - chunking_service - INFO - Created 5 chunks for document doc_123
2024-01-01 12:00:05 - embedding_service - INFO - Generated 5 embeddings for document doc_123
2024-01-01 12:00:06 - database_service - INFO - Saved 5 chunks to ChromaDB
2024-01-01 12:00:06 - tasks - INFO - Document processing completed for document_id: doc_123
```

## 🔄 Интеграция с Backend

Worker интегрируется с Node.js backend через Redis и Celery:

1. **Backend** отправляет задачу в Redis
2. **Worker** получает задачу и обрабатывает
3. **Worker** возвращает результат через Redis
4. **Backend** получает результат и обновляет БД

### Пример интеграции

```typescript
// Backend отправляет задачу
const task = await celeryClient.sendTask('tasks.process_document', [
  documentId,
  filePath,
  accessLevel,
  documentTitle
]);

// Получение результата
const result = await task.get();
