# Implementation Plan

## [Overview]
Комплексная оптимизация RAG системы для устранения критических ошибок, дублирования кода и повышения качества работы системы.

Анализ выявил серьезные архитектурные проблемы: дублирование поисковой логики между TypeScript и Python компонентами, неэффективную обработку контекста, неполную реализацию кэширования, избыточную сложность архитектуры и потенциальные утечки памяти. Система требует унификации поисковой логики, оптимизации RAG pipeline, улучшения качества ответов и упрощения архитектуры для достижения более стабильной и производительной работы.

## [Types]
Определение новых типов и интерфейсов для унифицированной архитектуры.

```typescript
// backend/src/types/search.ts
export interface UnifiedSearchRequest {
  query: string;
  accessLevel: number;
  searchType: 'vector' | 'hybrid' | 'semantic';
  options: {
    topK?: number;
    rerankTopK?: number;
    vectorWeight?: number;
    bm25Weight?: number;
    useCache?: boolean;
  };
}

export interface SearchMetrics {
  embeddingTime: number;
  searchTime: number;
  rerankTime: number;
  totalTime: number;
  candidatesFound: number;
  candidatesReranked: number;
  cacheHit: boolean;
}

export interface OptimizedSearchResult {
  id: string;
  content: string;
  metadata: Record<string, any>;
  score: number;
  relevanceScore: number;
  documentTitle: string;
  chunkIndex: number;
}

export interface ContextOptimizationResult {
  optimizedContext: string;
  originalLength: number;
  optimizedLength: number;
  chunksUsed: number;
  duplicatesRemoved: number;
}
```

```python
# worker/types/search_types.py
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

class SearchType(Enum):
    VECTOR = "vector"
    HYBRID = "hybrid" 
    SEMANTIC = "semantic"

@dataclass
class SearchRequest:
    query: str
    access_level: int
    search_type: SearchType
    top_k: int = 30
    rerank_top_k: int = 10
    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    use_cache: bool = True

@dataclass
class SearchMetrics:
    embedding_time_ms: float
    search_time_ms: float
    rerank_time_ms: float
    total_time_ms: float
    candidates_found: int
    candidates_reranked: int
    cache_hit: bool
```

## [Files]
Детальная разбивка изменений файлов для оптимизации системы.

**Новые файлы:**
- `backend/src/services/unifiedSearchService.ts` - Унифицированный поисковый сервис
- `backend/src/services/contextOptimizer.ts` - Оптимизатор контекста
- `backend/src/types/search.ts` - Типы для поиска
- `worker/services/unified_search_service.py` - Унифицированный Python поисковый сервис
- `worker/types/search_types.py` - Python типы для поиска
- `worker/services/memory_manager.py` - Менеджер памяти для предотвращения утечек
- `worker/services/performance_monitor.py` - Мониторинг производительности

**Модифицируемые файлы:**
- `backend/src/services/chatService.ts` - Интеграция с унифицированным поиском
- `backend/src/services/searchService.ts` - Упрощение и делегирование в унифицированный сервис
- `worker/tasks.py` - Оптимизация задач и управление памятью
- `worker/services/search_service.py` - Рефакторинг для унификации
- `worker/services/chunking_service.py` - Улучшение семантического чанкинга
- `worker/services/embedding_service.py` - Оптимизация управления памятью
- `worker/services/cache_service.py` - Улучшение кэш-стратегий

**Удаляемые файлы:**
- Дублирующие компоненты в `worker/debug_*.py` (консолидация в единый debug модуль)

**Конфигурационные изменения:**
- `docker-compose.yml` - Оптимизация настроек памяти для worker
- `worker/requirements.txt` - Добавление библиотек для мониторинга памяти

## [Functions]
Детальная разбивка изменений функций для оптимизации.

**Новые функции:**

`backend/src/services/unifiedSearchService.ts`:
- `performUnifiedSearch(request: UnifiedSearchRequest): Promise<SearchResponse>` - Главная функция унифицированного поиска
- `optimizeSearchStrategy(query: string, accessLevel: number): SearchType` - Выбор оптимальной стратегии поиска
- `validateSearchRequest(request: UnifiedSearchRequest): ValidationResult` - Валидация запросов

`backend/src/services/contextOptimizer.ts`:
- `optimizeContext(context: string, maxLength: number): ContextOptimizationResult` - Оптимизация контекста
- `removeDuplicateChunks(chunks: SearchResult[]): SearchResult[]` - Удаление дубликатов
- `prioritizeChunks(chunks: SearchResult[], query: string): SearchResult[]` - Приоритизация чанков

`worker/services/unified_search_service.py`:
- `execute_unified_search(request: SearchRequest) -> SearchResponse` - Выполнение унифицированного поиска
- `optimize_search_parameters(query: str, access_level: int) -> Dict` - Оптимизация параметров
- `merge_search_results(vector_results: List, bm25_results: List) -> List` - Объединение результатов

`worker/services/memory_manager.py`:
- `monitor_memory_usage() -> MemoryStats` - Мониторинг использования памяти
- `cleanup_unused_models() -> None` - Очистка неиспользуемых моделей
- `optimize_batch_processing(batch_size: int) -> int` - Оптимизация размера батча

**Модифицируемые функции:**

`backend/src/services/chatService.ts`:
- `processRAGQuery()` - Интеграция с унифицированным поиском, улучшение обработки контекста
- `callNewHybridSearch()` - Замена на вызов унифицированного сервиса
- `selectOptimalChunks()` - Перенос логики в contextOptimizer
- `buildSystemPrompt()` - Оптимизация промпта с учетом нового контекста

`worker/tasks.py`:
- `process_document()` - Добавление мониторинга памяти и оптимизации
- `rag_query()` - Интеграция с унифицированным поиском
- `hybrid_search()` - Упрощение через делегирование

`worker/services/chunking_service.py`:
- `create_chunks()` - Улучшение семантического разбиения
- `optimize_chunk_boundaries()` - Новая логика оптимизации границ чанков

**Удаляемые функции:**
- Дублирующие функции поиска в `backend/src/services/searchService.ts`
- Устаревшие debug функции в worker модулях

## [Classes]
Детальная разбивка изменений классов для архитектурной оптимизации.

**Новые классы:**

`UnifiedSearchService` (TypeScript):
- Методы: `search()`, `validateRequest()`, `optimizeStrategy()`
- Назначение: Единая точка входа для всех поисковых операций
- Расположение: `backend/src/services/unifiedSearchService.ts`

`ContextOptimizer` (TypeScript):
- Методы: `optimize()`, `removeDuplicates()`, `prioritize()`, `truncateIntelligently()`
- Назначение: Оптимизация контекста для LLM
- Расположение: `backend/src/services/contextOptimizer.ts`

`UnifiedSearchService` (Python):
- Методы: `execute_search()`, `merge_results()`, `apply_filters()`
- Назначение: Python реализация унифицированного поиска
- Расположение: `worker/services/unified_search_service.py`

`MemoryManager` (Python):
- Методы: `monitor()`, `cleanup()`, `optimize_batch_size()`, `prevent_leaks()`
- Назначение: Управление памятью и предотвращение утечек
- Расположение: `worker/services/memory_manager.py`

`PerformanceMonitor` (Python):
- Методы: `track_metrics()`, `analyze_bottlenecks()`, `generate_report()`
- Назначение: Мониторинг производительности системы
- Расположение: `worker/services/performance_monitor.py`

**Модифицируемые классы:**

`ChatService` (TypeScript):
- Изменения: Интеграция с UnifiedSearchService, улучшение обработки контекста
- Новые методы: `optimizePromptContext()`, `validateSearchResponse()`
- Удаляемые методы: `callNewHybridSearch()` (замена на унифицированный вызов)

`SearchService` (TypeScript):
- Изменения: Упрощение до делегирующего класса
- Сохраняемые методы: `hybridSearch()` (как обертка)
- Новые методы: `delegateToUnified()`

`SearchService` (Python):
- Изменения: Рефакторинг для работы с унифицированным сервисом
- Оптимизация: Улучшение управления памятью в BM25 индексе
- Новые методы: `optimize_memory_usage()`, `validate_search_params()`

`EmbeddingService` (Python):
- Изменения: Добавление управления памятью модели
- Новые методы: `cleanup_model_cache()`, `optimize_batch_processing()`
- Оптимизация: Предотвращение утечек памяти при batch обработке

**Удаляемые классы:**
- Дублирующие debug классы в worker модулях (консолидация функциональности)

## [Dependencies]
Обновление зависимостей для поддержки новой функциональности.

**Backend (package.json):**
```json
{
  "dependencies": {
    "memory-usage": "^0.1.0",
    "performance-now": "^2.1.0"
  }
}
```

**Worker (requirements.txt):**
```
# Мониторинг памяти
psutil==5.9.6
memory-profiler==0.61.0

# Оптимизация производительности  
line-profiler==4.1.1
py-spy==0.3.14

# Улучшенное кэширование
diskcache==5.6.3
```

**Docker оптимизации:**
- Увеличение лимитов памяти для worker контейнера
- Добавление health checks для мониторинга производительности
- Оптимизация настроек JVM для лучшего управления памятью

## [Testing]
Стратегия тестирования для обеспечения качества оптимизаций.

**Новые тестовые файлы:**
- `backend/src/tests/unifiedSearchService.test.ts` - Тесты унифицированного поиска
- `backend/src/tests/contextOptimizer.test.ts` - Тесты оптимизации контекста
- `worker/tests/test_unified_search.py` - Python тесты унифицированного поиска
- `worker/tests/test_memory_manager.py` - Тесты управления памятью
- `worker/tests/test_performance_monitor.py` - Тесты мониторинга производительности

**Интеграционные тесты:**
- Тестирование полного RAG pipeline с новой архитектурой
- Нагрузочное тестирование для выявления утечек памяти
- Тестирование кэширования и производительности

**Модификация существующих тестов:**
- Обновление тестов ChatService для новой логики
- Адаптация тестов SearchService под унифицированную архитектуру

## [Implementation Order]
Последовательность реализации для минимизации рисков и обеспечения стабильности.

1. **Этап 1: Создание базовой инфраструктуры (1-2 дня)**
   - Создание типов и интерфейсов
   - Реализация MemoryManager и PerformanceMonitor
   - Настройка мониторинга и логирования

2. **Этап 2: Унификация поисковой логики (2-3 дня)**
   - Создание UnifiedSearchService (Python)
   - Создание UnifiedSearchService (TypeScript)
   - Интеграция с существующими компонентами

3. **Этап 3: Оптимизация контекста (1-2 дня)**
   - Реализация ContextOptimizer
   - Интеграция с ChatService
   - Тестирование качества ответов

4. **Этап 4: Рефакторинг существующих сервисов (2-3 дня)**
   - Модификация ChatService
   - Упрощение SearchService
   - Оптимизация worker задач

5. **Этап 5: Оптимизация производительности (1-2 дня)**
   - Улучшение управления памятью
   - Оптимизация кэширования
   - Настройка Docker конфигурации

6. **Этап 6: Тестирование и валидация (1-2 дня)**
   - Комплексное тестирование
   - Нагрузочное тестирование
   - Валидация производительности

7. **Этап 7: Очистка и документация (1 день)**
   - Удаление устаревшего кода
   - Обновление документации
   - Финальная оптимизация
