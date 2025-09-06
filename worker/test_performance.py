#!/usr/bin/env python3
"""
Скрипт для тестирования производительности RAG pipeline
Запуск: python test_performance.py
"""

import os
import sys
import logging
import time
from typing import Dict, Any

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('performance_test.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """
    Основная функция для тестирования производительности
    """
    try:
        logger.info("🚀 Starting comprehensive performance testing")
        
        # Импортируем профилировщик
        from performance_profiler import (
            profile_service_initialization,
            profile_search_pipeline,
            profile_isolated_reranking
        )
        
        # 1. ЭТАП 1: Профилирование инициализации сервисов
        logger.info("=" * 60)
        logger.info("ЭТАП 1: Профилирование инициализации сервисов")
        logger.info("=" * 60)
        
        init_start_time = time.time()
        init_result = profile_service_initialization()
        init_total_time = (time.time() - init_start_time) * 1000
        
        logger.info(f"✅ Инициализация сервисов завершена за {init_total_time:.1f}ms")
        
        services = init_result["services"]
        init_summary = init_result["profiler_summary"]
        
        # Выводим топ медленных операций инициализации
        logger.info("🐌 Самые медленные операции инициализации:")
        for i, op in enumerate(init_summary["slowest_operations"][:3], 1):
            logger.info(f"  {i}. {op['operation']}: {op['duration_ms']:.1f}ms")
        
        # 2. ЭТАП 2: Тестовые запросы для профилирования
        test_queries = [
            "Что такое должностная инструкция копирайтера?",
            "Какие обязанности у копирайтера?",
            "Расскажи о требованиях к копирайтеру",
            "Hello world test query",  # Английский запрос
            "Краткий вопрос"  # Короткий запрос
        ]
        
        access_level = 50  # Средний уровень доступа
        
        # 3. ЭТАП 3: Профилирование полного pipeline для каждого запроса
        logger.info("=" * 60)
        logger.info("ЭТАП 2: Профилирование полного search pipeline")
        logger.info("=" * 60)
        
        pipeline_results = []
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"📝 Тест {i}/{len(test_queries)}: '{query[:50]}...'")
            
            pipeline_start_time = time.time()
            pipeline_result = profile_search_pipeline(query, access_level, services)
            pipeline_total_time = (time.time() - pipeline_start_time) * 1000
            
            pipeline_results.append({
                "query": query,
                "total_time_ms": pipeline_total_time,
                "profiler_result": pipeline_result
            })
            
            if pipeline_result.get("pipeline_success"):
                logger.info(f"✅ Pipeline завершен за {pipeline_total_time:.1f}ms, "
                           f"найдено {pipeline_result.get('results_count', 0)} результатов")
            else:
                logger.error(f"❌ Pipeline failed: {pipeline_result.get('error', 'Unknown error')}")
            
            # Пауза между запросами
            time.sleep(1)
        
        # 4. ЭТАП 4: Изолированное тестирование реранжера
        logger.info("=" * 60)
        logger.info("ЭТАП 3: Изолированное тестирование реранжера")
        logger.info("=" * 60)
        
        # Создаем тестовые документы
        test_documents = [
            "Копирайтер отвечает за создание текстового контента для различных маркетинговых материалов.",
            "Должностная инструкция копирайтера включает написание рекламных текстов и контента для сайтов.",
            "Основные обязанности копирайтера: создание продающих текстов, редактирование контента, работа с SEO.",
            "Копирайтер должен обладать отличными навыками письма и понимать принципы маркетинга.",
            "В обязанности копирайтера входит создание контент-планов и работа с социальными сетями.",
            "Копирайтер работает с различными форматами контента: статьи, посты, рекламные тексты.",
            "Профессиональный копирайтер должен уметь адаптировать стиль письма под разные аудитории.",
            "Копирайтер участвует в разработке маркетинговых кампаний и создании брендинговых материалов.",
            "Современный копирайтер должен понимать цифровой маркетинг и SEO-оптимизацию.",
            "Копирайтер сотрудничает с дизайнерами и маркетологами для создания эффективного контента."
        ]
        
        test_query = "Что входит в обязанности копирайтера?"
        
        reranking_start_time = time.time()
        reranking_result = profile_isolated_reranking(
            test_query, test_documents, services["reranking_service"]
        )
        reranking_total_time = (time.time() - reranking_start_time) * 1000
        
        if reranking_result.get("reranking_success"):
            logger.info(f"✅ Изолированный реранжер завершен за {reranking_total_time:.1f}ms, "
                       f"обработано {reranking_result.get('documents_count', 0)} документов")
        else:
            logger.error(f"❌ Reranking failed: {reranking_result.get('error', 'Unknown error')}")
        
        # 5. ЭТАП 5: Сводный анализ
        logger.info("=" * 60)
        logger.info("ЭТАП 4: Сводный анализ производительности")
        logger.info("=" * 60)
        
        # Анализируем результаты
        successful_pipelines = [r for r in pipeline_results if r["profiler_result"].get("pipeline_success")]
        
        if successful_pipelines:
            avg_pipeline_time = sum(r["total_time_ms"] for r in successful_pipelines) / len(successful_pipelines)
            max_pipeline_time = max(r["total_time_ms"] for r in successful_pipelines)
            min_pipeline_time = min(r["total_time_ms"] for r in successful_pipelines)
            
            logger.info(f"📊 Статистика pipeline (успешных: {len(successful_pipelines)}):")
            logger.info(f"   Среднее время: {avg_pipeline_time:.1f}ms")
            logger.info(f"   Максимальное время: {max_pipeline_time:.1f}ms")
            logger.info(f"   Минимальное время: {min_pipeline_time:.1f}ms")
            
            # Находим самые медленные операции
            all_operations = {}
            for result in successful_pipelines:
                profiler_result = result["profiler_result"]
                if "all_measurements" in profiler_result:
                    for measurement in profiler_result["all_measurements"]:
                        op_name = measurement["operation"]
                        if op_name not in all_operations:
                            all_operations[op_name] = []
                        all_operations[op_name].append(measurement["duration_ms"])
            
            # Вычисляем средние времена для каждой операции
            avg_operations = {}
            for op_name, times in all_operations.items():
                avg_operations[op_name] = sum(times) / len(times)
            
            # Сортируем по среднему времени
            sorted_operations = sorted(avg_operations.items(), key=lambda x: x[1], reverse=True)
            
            logger.info("🐌 Самые медленные операции в среднем:")
            for i, (op_name, avg_time) in enumerate(sorted_operations[:5], 1):
                logger.info(f"   {i}. {op_name}: {avg_time:.1f}ms")
        
        # Сравнение с известными результатами
        logger.info("=" * 60)
        logger.info("СРАВНЕНИЕ С ИЗВЕСТНЫМИ РЕЗУЛЬТАТАМИ")
        logger.info("=" * 60)
        
        logger.info("🔍 Известные результаты:")
        logger.info("   Embedding: ~200ms ✅")
        logger.info("   ChromaDB vector search: ~150ms ✅")
        logger.info("   BM25 search: ~50ms ✅")
        logger.info("   RRF Fusion: ~1ms ✅")
        logger.info("   BGE Reranking: ~750ms ✅ (было 18000ms)")
        logger.info("   НЕИЗВЕСТНЫЙ КОМПОНЕНТ: ~24000ms ❓")
        
        if reranking_result.get("reranking_success"):
            isolated_reranking_time = reranking_result["total_pipeline_time_ms"]
            logger.info(f"📊 Текущий изолированный реранжер: {isolated_reranking_time:.1f}ms")
            
            if isolated_reranking_time > 1000:
                logger.warning(f"⚠️  Реранжер все еще медленный: {isolated_reranking_time:.1f}ms > 1000ms")
            else:
                logger.info(f"✅ Реранжер оптимизирован: {isolated_reranking_time:.1f}ms")
        
        if successful_pipelines:
            logger.info(f"📊 Текущий полный pipeline: {avg_pipeline_time:.1f}ms")
            
            if avg_pipeline_time > 5000:  # 5 секунд
                logger.error(f"❌ Pipeline все еще очень медленный: {avg_pipeline_time:.1f}ms")
                logger.info("🔍 Необходимо найти источник задержки в ~24 секунды")
            elif avg_pipeline_time > 2000:  # 2 секунды
                logger.warning(f"⚠️  Pipeline медленный: {avg_pipeline_time:.1f}ms")
            else:
                logger.info(f"✅ Pipeline оптимизирован: {avg_pipeline_time:.1f}ms")
        
        logger.info("🏁 Тестирование производительности завершено")
        logger.info("📁 Детальные отчеты сохранены в JSON файлы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка во время тестирования производительности: {str(e)}")
        raise e


if __name__ == "__main__":
    main()
