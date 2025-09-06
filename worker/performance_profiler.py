"""
Детальный профилировщик производительности для поиска узких мест в RAG pipeline
"""

import time
import logging
import json
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import psutil
import os

logger = logging.getLogger(__name__)

class PerformanceProfiler:
    """
    Профилировщик для детального анализа производительности RAG pipeline
    """
    
    def __init__(self):
        self.measurements = {}
        self.current_operation = None
        self.start_time = None
        self.process = psutil.Process(os.getpid())
        
    @contextmanager
    def measure(self, operation_name: str, details: Dict[str, Any] = None):
        """
        Контекстный менеджер для измерения времени выполнения операции
        
        Args:
            operation_name: Название операции
            details: Дополнительные детали операции
        """
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            logger.info(f"🔍 PROFILER: Starting {operation_name}")
            yield
            
        finally:
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            duration_ms = (end_time - start_time) * 1000
            memory_delta = end_memory - start_memory
            
            measurement = {
                "operation": operation_name,
                "duration_ms": duration_ms,
                "start_memory_mb": start_memory,
                "end_memory_mb": end_memory,
                "memory_delta_mb": memory_delta,
                "timestamp": start_time,
                "details": details or {}
            }
            
            self.measurements[operation_name] = measurement
            
            logger.info(f"⏱️  PROFILER: {operation_name} completed in {duration_ms:.1f}ms "
                       f"(memory: {memory_delta:+.1f}MB)")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Получить сводку всех измерений
        
        Returns:
            Сводка производительности
        """
        if not self.measurements:
            return {"error": "No measurements recorded"}
        
        total_time = sum(m["duration_ms"] for m in self.measurements.values())
        sorted_measurements = sorted(
            self.measurements.values(), 
            key=lambda x: x["duration_ms"], 
            reverse=True
        )
        
        return {
            "total_pipeline_time_ms": total_time,
            "measurements_count": len(self.measurements),
            "slowest_operations": sorted_measurements[:5],
            "all_measurements": sorted_measurements,
            "memory_usage": {
                "peak_memory_mb": max(m["end_memory_mb"] for m in self.measurements.values()),
                "total_memory_delta_mb": sum(m["memory_delta_mb"] for m in self.measurements.values())
            }
        }
    
    def print_detailed_report(self):
        """
        Вывести детальный отчет в лог
        """
        summary = self.get_summary()
        
        if "error" in summary:
            logger.error(f"PROFILER REPORT: {summary['error']}")
            return
        
        logger.info("=" * 80)
        logger.info("🔍 DETAILED PERFORMANCE REPORT")
        logger.info("=" * 80)
        logger.info(f"Total Pipeline Time: {summary['total_pipeline_time_ms']:.1f}ms")
        logger.info(f"Peak Memory Usage: {summary['memory_usage']['peak_memory_mb']:.1f}MB")
        logger.info(f"Total Memory Delta: {summary['memory_usage']['total_memory_delta_mb']:+.1f}MB")
        logger.info("-" * 80)
        
        for i, measurement in enumerate(summary['all_measurements'], 1):
            percentage = (measurement['duration_ms'] / summary['total_pipeline_time_ms']) * 100
            logger.info(f"{i:2d}. {measurement['operation']:<30} "
                       f"{measurement['duration_ms']:>8.1f}ms ({percentage:>5.1f}%) "
                       f"[mem: {measurement['memory_delta_mb']:+.1f}MB]")
            
            # Показываем детали для самых медленных операций
            if i <= 3 and measurement.get('details'):
                for key, value in measurement['details'].items():
                    logger.info(f"    {key}: {value}")
        
        logger.info("=" * 80)
    
    def save_report_to_file(self, filename: str = None):
        """
        Сохранить отчет в файл
        
        Args:
            filename: Имя файла (по умолчанию с timestamp)
        """
        if not filename:
            timestamp = int(time.time())
            filename = f"performance_report_{timestamp}.json"
        
        summary = self.get_summary()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📊 Performance report saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving performance report: {str(e)}")


def profile_service_initialization():
    """
    Профилирование инициализации всех сервисов
    """
    profiler = PerformanceProfiler()
    
    try:
        # Импорты с измерением времени
        with profiler.measure("imports", {"type": "module_imports"}):
            from services.chunking_service import SemanticChunkingService
            from services.embedding_service import EmbeddingService
            from services.database_service import DatabaseService
            from services.local_reranking_service import LocalRerankingService
            from services.keyword_service import get_keyword_service
            from services.search_service import get_search_service
        
        # Инициализация каждого сервиса отдельно
        with profiler.measure("chunking_service_init", {"service": "SemanticChunkingService"}):
            chunking_service = SemanticChunkingService()
        
        with profiler.measure("embedding_service_init", {"service": "EmbeddingService"}):
            embedding_service = EmbeddingService()
        
        with profiler.measure("database_service_init", {"service": "DatabaseService"}):
            database_service = DatabaseService()
        
        with profiler.measure("reranking_service_init", {"service": "LocalRerankingService"}):
            reranking_service = LocalRerankingService()
        
        with profiler.measure("keyword_service_init", {"service": "KeywordService"}):
            keyword_service = get_keyword_service()
        
        with profiler.measure("search_service_init", {"service": "SearchService"}):
            search_service = get_search_service(database_service, embedding_service, reranking_service)
        
        # Генерируем отчет
        profiler.print_detailed_report()
        profiler.save_report_to_file("service_initialization_profile.json")
        
        return {
            "services": {
                "chunking_service": chunking_service,
                "embedding_service": embedding_service,
                "database_service": database_service,
                "reranking_service": reranking_service,
                "keyword_service": keyword_service,
                "search_service": search_service
            },
            "profiler_summary": profiler.get_summary()
        }
        
    except Exception as e:
        logger.error(f"Error during service initialization profiling: {str(e)}")
        profiler.print_detailed_report()
        raise e


def profile_search_pipeline(query: str, access_level: int, services: Dict[str, Any]):
    """
    Детальное профилирование полного search pipeline
    
    Args:
        query: Поисковый запрос
        access_level: Уровень доступа
        services: Словарь с инициализированными сервисами
    """
    profiler = PerformanceProfiler()
    
    try:
        logger.info(f"🔍 Starting detailed search pipeline profiling for query: '{query[:50]}...'")
        
        # 1. Генерация эмбеддинга запроса
        with profiler.measure("query_embedding_generation", {
            "query_length": len(query),
            "model": "multilingual-e5-large-instruct"
        }):
            query_embedding_result = services["embedding_service"].generate_query_embedding(query)
            query_embedding = query_embedding_result["embedding"]
        
        # 2. ChromaDB векторный поиск
        with profiler.measure("chromadb_vector_search", {
            "access_level": access_level,
            "top_k": 30
        }):
            search_result = services["database_service"].query_chromadb(
                query_embedding, access_level, top_k=30
            )
        
        if not search_result["success"] or not search_result["results"]["documents"][0]:
            logger.warning("No results from ChromaDB search")
            profiler.print_detailed_report()
            return profiler.get_summary()
        
        documents = search_result["results"]["documents"][0]
        metadatas = search_result["results"]["metadatas"][0]
        
        # 3. BM25 инициализация (если нужно)
        with profiler.measure("bm25_initialization", {
            "access_level": access_level,
            "documents_count": len(documents)
        }):
            services["search_service"]._ensure_bm25_initialized(access_level)
        
        # 4. BM25 поиск
        with profiler.measure("bm25_search", {
            "query_length": len(query),
            "top_k": 30
        }):
            bm25_results = services["search_service"]._bm25_search(query, access_level, 30)
        
        # 5. RRF Fusion
        with profiler.measure("rrf_fusion", {
            "vector_results": len(documents),
            "bm25_results": len(bm25_results)
        }):
            # Форматируем векторные результаты для RRF
            vector_results = []
            for i, (doc, metadata) in enumerate(zip(documents, metadatas)):
                vector_results.append({
                    "id": f"{metadata.get('doc_id', 'unknown')}_{metadata.get('chunk_index', i)}",
                    "content": doc,
                    "metadata": metadata,
                    "score": 1.0,  # Placeholder score
                    "type": "vector",
                    "rank": i + 1
                })
            
            fused_results = services["search_service"]._rrf_fusion(
                vector_results, bm25_results, 0.7, 0.3
            )
        
        # 6. Реранжирование
        if fused_results:
            with profiler.measure("reranking", {
                "documents_count": len(fused_results),
                "rerank_top_k": 10,
                "model": "BAAI/bge-reranker-v2-m3"
            }):
                reranked_results = services["search_service"]._rerank_results(
                    query, fused_results, 10
                )
        else:
            reranked_results = []
        
        # 7. Формирование контекста
        with profiler.measure("context_formation", {
            "final_results": len(reranked_results)
        }):
            context_parts = []
            for i, result in enumerate(reranked_results):
                metadata = result.get("metadata", {})
                doc_title = metadata.get("doc_title", "Неизвестный документ")
                context_part = f"[Источник {i + 1}: {doc_title}]\n{result.get('content', '')}\n"
                context_parts.append(context_part)
            
            context = "\n".join(context_parts)
        
        # Генерируем детальный отчет
        profiler.print_detailed_report()
        profiler.save_report_to_file(f"search_pipeline_profile_{int(time.time())}.json")
        
        summary = profiler.get_summary()
        summary.update({
            "query": query,
            "access_level": access_level,
            "results_count": len(reranked_results),
            "context_length": len(context),
            "pipeline_success": True
        })
        
        return summary
        
    except Exception as e:
        logger.error(f"Error during search pipeline profiling: {str(e)}")
        profiler.print_detailed_report()
        
        summary = profiler.get_summary()
        summary.update({
            "query": query,
            "access_level": access_level,
            "pipeline_success": False,
            "error": str(e)
        })
        
        return summary


def profile_isolated_reranking(query: str, documents: List[str], reranking_service):
    """
    Изолированное профилирование только реранжера
    
    Args:
        query: Поисковый запрос
        documents: Список документов для реранжирования
        reranking_service: Сервис реранжирования
    """
    profiler = PerformanceProfiler()
    
    try:
        logger.info(f"🔍 Starting isolated reranking profiling for {len(documents)} documents")
        
        with profiler.measure("isolated_reranking", {
            "query_length": len(query),
            "documents_count": len(documents),
            "model": "BAAI/bge-reranker-v2-m3"
        }):
            results = reranking_service.rerank_results(query, documents, top_k=10)
        
        profiler.print_detailed_report()
        
        summary = profiler.get_summary()
        summary.update({
            "query": query,
            "documents_count": len(documents),
            "results_count": len(results),
            "reranking_success": True
        })
        
        return summary
        
    except Exception as e:
        logger.error(f"Error during isolated reranking profiling: {str(e)}")
        profiler.print_detailed_report()
        
        summary = profiler.get_summary()
        summary.update({
            "query": query,
            "documents_count": len(documents),
            "reranking_success": False,
            "error": str(e)
        })
        
        return summary
