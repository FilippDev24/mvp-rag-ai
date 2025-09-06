"""
Детальный профилировщик реранжирования для выявления причины замедления в pipeline
"""

import time
import psutil
import gc
import torch
import threading
import logging
from typing import List, Dict, Any
from services.reranking_service import RerankingService
from services.search_service import get_search_service
from services.database_service import DatabaseService
from services.embedding_service import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetailedRerankingProfiler:
    """Детальный профилировщик для анализа реранжирования"""
    
    def __init__(self):
        self.process = psutil.Process()
        
    def get_memory_info(self) -> Dict[str, float]:
        """Получить информацию о памяти"""
        memory_info = self.process.memory_info()
        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": self.process.memory_percent()
        }
    
    def get_gpu_info(self) -> Dict[str, Any]:
        """Получить информацию о GPU"""
        if torch.cuda.is_available():
            return {
                "available": True,
                "device_count": torch.cuda.device_count(),
                "current_device": torch.cuda.current_device(),
                "memory_allocated": torch.cuda.memory_allocated() / 1024 / 1024,
                "memory_reserved": torch.cuda.memory_reserved() / 1024 / 1024,
                "memory_cached": torch.cuda.memory_cached() / 1024 / 1024 if hasattr(torch.cuda, 'memory_cached') else 0
            }
        return {"available": False}
    
    def profile_isolated_reranking(self, query: str, documents: List[str], iterations: int = 3) -> Dict[str, Any]:
        """Профилирование изолированного реранжирования"""
        logger.info(f"=== ПРОФИЛИРОВАНИЕ ИЗОЛИРОВАННОГО РЕРАНЖИРОВАНИЯ ===")
        
        # Инициализация сервиса
        reranking_service = RerankingService()
        
        results = []
        
        for i in range(iterations):
            logger.info(f"Итерация {i+1}/{iterations}")
            
            # Сбор мусора перед тестом
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Начальные метрики
            start_memory = self.get_memory_info()
            start_gpu = self.get_gpu_info()
            start_time = time.time()
            
            # Выполнение реранжирования
            reranked_results = reranking_service.rerank_results(query, documents, top_k=10)
            
            # Финальные метрики
            end_time = time.time()
            end_memory = self.get_memory_info()
            end_gpu = self.get_gpu_info()
            
            execution_time = (end_time - start_time) * 1000
            
            iteration_result = {
                "iteration": i + 1,
                "execution_time_ms": execution_time,
                "memory_before": start_memory,
                "memory_after": end_memory,
                "memory_delta_mb": end_memory["rss_mb"] - start_memory["rss_mb"],
                "gpu_before": start_gpu,
                "gpu_after": end_gpu,
                "results_count": len(reranked_results),
                "top_score": reranked_results[0]["score"] if reranked_results else 0
            }
            
            results.append(iteration_result)
            logger.info(f"Время выполнения: {execution_time:.1f}ms")
        
        # Статистика
        times = [r["execution_time_ms"] for r in results]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        return {
            "type": "isolated_reranking",
            "iterations": iterations,
            "results": results,
            "statistics": {
                "avg_time_ms": avg_time,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "std_dev_ms": (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
            }
        }
    
    def profile_pipeline_reranking(self, query: str, access_level: int = 50, iterations: int = 3) -> Dict[str, Any]:
        """Профилирование реранжирования в составе SearchService pipeline"""
        logger.info(f"=== ПРОФИЛИРОВАНИЕ РЕРАНЖИРОВАНИЯ В PIPELINE ===")
        
        # Инициализация сервисов
        database_service = DatabaseService()
        embedding_service = EmbeddingService()
        reranking_service = RerankingService()
        search_service = get_search_service(database_service, embedding_service, reranking_service)
        
        results = []
        
        for i in range(iterations):
            logger.info(f"Итерация {i+1}/{iterations}")
            
            # Сбор мусора перед тестом
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Начальные метрики
            start_memory = self.get_memory_info()
            start_gpu = self.get_gpu_info()
            start_time = time.time()
            
            # Выполнение полного поиска с реранжированием
            search_results = search_service.hybrid_search(
                query=query,
                access_level=access_level,
                top_k=30,
                rerank_top_k=10
            )
            
            # Финальные метрики
            end_time = time.time()
            end_memory = self.get_memory_info()
            end_gpu = self.get_gpu_info()
            
            execution_time = (end_time - start_time) * 1000
            
            iteration_result = {
                "iteration": i + 1,
                "execution_time_ms": execution_time,
                "memory_before": start_memory,
                "memory_after": end_memory,
                "memory_delta_mb": end_memory["rss_mb"] - start_memory["rss_mb"],
                "gpu_before": start_gpu,
                "gpu_after": end_gpu,
                "search_success": search_results.get("success", False),
                "results_count": search_results.get("final_results_count", 0),
                "vector_results": search_results.get("vector_results_count", 0),
                "bm25_results": search_results.get("bm25_results_count", 0),
                "fused_results": search_results.get("fused_results_count", 0),
                "embedding_time_ms": search_results.get("embedding_time_ms", 0)
            }
            
            results.append(iteration_result)
            logger.info(f"Время выполнения pipeline: {execution_time:.1f}ms")
        
        # Статистика
        times = [r["execution_time_ms"] for r in results]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        return {
            "type": "pipeline_reranking",
            "iterations": iterations,
            "results": results,
            "statistics": {
                "avg_time_ms": avg_time,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "std_dev_ms": (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
            }
        }
    
    def profile_step_by_step_pipeline(self, query: str, access_level: int = 50) -> Dict[str, Any]:
        """Пошаговое профилирование pipeline для выявления узких мест"""
        logger.info(f"=== ПОШАГОВОЕ ПРОФИЛИРОВАНИЕ PIPELINE ===")
        
        # Инициализация сервисов
        database_service = DatabaseService()
        embedding_service = EmbeddingService()
        reranking_service = RerankingService()
        search_service = get_search_service(database_service, embedding_service, reranking_service)
        
        # Сбор мусора
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        steps_timing = {}
        memory_tracking = {}
        
        # Общее начало
        total_start = time.time()
        start_memory = self.get_memory_info()
        
        # Шаг 1: Инициализация BM25
        step_start = time.time()
        search_service._ensure_bm25_initialized(access_level)
        steps_timing["bm25_init"] = (time.time() - step_start) * 1000
        memory_tracking["after_bm25_init"] = self.get_memory_info()
        
        # Шаг 2: Векторный поиск
        step_start = time.time()
        vector_results, embedding_metrics = search_service._vector_search(query, access_level, 30)
        steps_timing["vector_search"] = (time.time() - step_start) * 1000
        steps_timing["embedding_time"] = embedding_metrics.get("embedding_time_ms", 0)
        memory_tracking["after_vector_search"] = self.get_memory_info()
        
        # Шаг 3: BM25 поиск
        step_start = time.time()
        bm25_results = search_service._bm25_search(query, access_level, 30)
        steps_timing["bm25_search"] = (time.time() - step_start) * 1000
        memory_tracking["after_bm25_search"] = self.get_memory_info()
        
        # Шаг 4: RRF Fusion
        step_start = time.time()
        fused_results = search_service._rrf_fusion(vector_results, bm25_results, 0.7, 0.3)
        steps_timing["rrf_fusion"] = (time.time() - step_start) * 1000
        memory_tracking["after_rrf_fusion"] = self.get_memory_info()
        
        # Шаг 5: Подготовка к реранжированию
        step_start = time.time()
        documents = [result["content"] for result in fused_results]
        steps_timing["rerank_preparation"] = (time.time() - step_start) * 1000
        memory_tracking["before_reranking"] = self.get_memory_info()
        
        # Шаг 6: ДЕТАЛЬНОЕ ПРОФИЛИРОВАНИЕ РЕРАНЖИРОВАНИЯ
        logger.info(f"Начинаем детальное профилирование реранжирования для {len(documents)} документов")
        
        # 6.1: Подготовка пар
        step_start = time.time()
        pairs = [(query, doc) for doc in documents]
        steps_timing["rerank_pairs_preparation"] = (time.time() - step_start) * 1000
        
        # 6.2: Загрузка модели (если не загружена)
        step_start = time.time()
        model_loaded = reranking_service.model is not None
        if not model_loaded:
            reranking_service._load_model()
        steps_timing["rerank_model_loading"] = (time.time() - step_start) * 1000
        
        # 6.3: Предсказание скоров
        step_start = time.time()
        memory_before_predict = self.get_memory_info()
        gpu_before_predict = self.get_gpu_info()
        
        with torch.no_grad():
            scores = reranking_service.model.predict(pairs)
        
        steps_timing["rerank_model_predict"] = (time.time() - step_start) * 1000
        memory_after_predict = self.get_memory_info()
        gpu_after_predict = self.get_gpu_info()
        
        # 6.4: Постобработка скоров
        step_start = time.time()
        import numpy as np
        scores_array = np.array(scores)
        max_logit = np.max(scores_array)
        amplification_factor = 100
        amplified_scores = np.exp(scores_array * amplification_factor)
        min_amplified = np.min(amplified_scores)
        max_amplified = np.max(amplified_scores)
        
        if max_amplified > min_amplified:
            final_scores = (amplified_scores - min_amplified) / (max_amplified - min_amplified) * 10
        else:
            final_scores = np.ones_like(amplified_scores) * 5.0
        
        steps_timing["rerank_postprocessing"] = (time.time() - step_start) * 1000
        
        # 6.5: Создание результатов
        step_start = time.time()
        rerank_results = []
        for i, (raw_score, final_score) in enumerate(zip(scores_array, final_scores)):
            rerank_results.append({
                "index": i,
                "score": float(final_score),
                "raw_logit": float(raw_score),
                "document": documents[i]
            })
        rerank_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = rerank_results[:10]
        
        steps_timing["rerank_results_creation"] = (time.time() - step_start) * 1000
        
        # Общее время реранжирования
        total_rerank_time = (
            steps_timing["rerank_pairs_preparation"] +
            steps_timing["rerank_model_loading"] +
            steps_timing["rerank_model_predict"] +
            steps_timing["rerank_postprocessing"] +
            steps_timing["rerank_results_creation"]
        )
        steps_timing["total_reranking"] = total_rerank_time
        
        memory_tracking["after_reranking"] = self.get_memory_info()
        
        # Общее время
        total_time = (time.time() - total_start) * 1000
        steps_timing["total_pipeline"] = total_time
        
        # Анализ памяти
        memory_deltas = {}
        prev_memory = start_memory["rss_mb"]
        for step, memory_info in memory_tracking.items():
            current_memory = memory_info["rss_mb"]
            memory_deltas[step] = current_memory - prev_memory
            prev_memory = current_memory
        
        return {
            "type": "step_by_step_pipeline",
            "query": query,
            "access_level": access_level,
            "documents_count": len(documents),
            "steps_timing_ms": steps_timing,
            "memory_tracking": memory_tracking,
            "memory_deltas_mb": memory_deltas,
            "reranking_details": {
                "model_loaded_initially": model_loaded,
                "pairs_count": len(pairs),
                "memory_before_predict": memory_before_predict,
                "memory_after_predict": memory_after_predict,
                "memory_delta_predict_mb": memory_after_predict["rss_mb"] - memory_before_predict["rss_mb"],
                "gpu_before_predict": gpu_before_predict,
                "gpu_after_predict": gpu_after_predict,
                "scores_stats": {
                    "min_raw": float(scores_array.min()),
                    "max_raw": float(scores_array.max()),
                    "mean_raw": float(scores_array.mean()),
                    "min_final": float(final_scores.min()),
                    "max_final": float(final_scores.max()),
                    "mean_final": float(final_scores.mean())
                }
            },
            "performance_analysis": {
                "reranking_percentage": (total_rerank_time / total_time) * 100,
                "model_predict_percentage": (steps_timing["rerank_model_predict"] / total_time) * 100,
                "slowest_step": max(steps_timing.items(), key=lambda x: x[1])
            }
        }
    
    def run_comprehensive_analysis(self, query: str = "Какие документы есть в системе?", access_level: int = 50) -> Dict[str, Any]:
        """Запуск комплексного анализа"""
        logger.info(f"=== КОМПЛЕКСНЫЙ АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ РЕРАНЖИРОВАНИЯ ===")
        logger.info(f"Query: {query}")
        logger.info(f"Access level: {access_level}")
        
        # Получаем тестовые документы из базы
        database_service = DatabaseService()
        collection = database_service.get_collection()
        
        # Получаем документы для тестирования
        test_docs = collection.get(
            where={"access_level": {"$lte": access_level}},
            limit=30,
            include=['documents']
        )
        
        if not test_docs['documents']:
            logger.error("Нет документов для тестирования!")
            return {"error": "No documents found for testing"}
        
        documents = test_docs['documents'][:20]  # Берем 20 документов для тестирования
        logger.info(f"Используем {len(documents)} документов для тестирования")
        
        results = {}
        
        # 1. Изолированное реранжирование
        logger.info("\n" + "="*50)
        results["isolated"] = self.profile_isolated_reranking(query, documents, iterations=3)
        
        # 2. Реранжирование в pipeline
        logger.info("\n" + "="*50)
        results["pipeline"] = self.profile_pipeline_reranking(query, access_level, iterations=3)
        
        # 3. Пошаговый анализ
        logger.info("\n" + "="*50)
        results["step_by_step"] = self.profile_step_by_step_pipeline(query, access_level)
        
        # 4. Сравнительный анализ
        isolated_avg = results["isolated"]["statistics"]["avg_time_ms"]
        pipeline_avg = results["pipeline"]["statistics"]["avg_time_ms"]
        rerank_time_in_pipeline = results["step_by_step"]["steps_timing_ms"]["total_reranking"]
        
        results["comparison"] = {
            "isolated_avg_ms": isolated_avg,
            "pipeline_avg_ms": pipeline_avg,
            "rerank_time_in_pipeline_ms": rerank_time_in_pipeline,
            "slowdown_factor_pipeline_vs_isolated": pipeline_avg / isolated_avg if isolated_avg > 0 else 0,
            "slowdown_factor_pipeline_rerank_vs_isolated": rerank_time_in_pipeline / isolated_avg if isolated_avg > 0 else 0,
            "rerank_percentage_of_pipeline": (rerank_time_in_pipeline / pipeline_avg) * 100 if pipeline_avg > 0 else 0
        }
        
        # 5. Выводы и рекомендации
        results["analysis"] = self._analyze_results(results)
        
        return results
    
    def _analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ результатов и выводы"""
        comparison = results["comparison"]
        step_by_step = results["step_by_step"]
        
        analysis = {
            "findings": [],
            "bottlenecks": [],
            "recommendations": []
        }
        
        # Анализ замедления
        slowdown = comparison["slowdown_factor_pipeline_vs_isolated"]
        if slowdown > 10:
            analysis["findings"].append(f"КРИТИЧЕСКОЕ замедление: {slowdown:.1f}x медленнее в pipeline")
        elif slowdown > 3:
            analysis["findings"].append(f"Значительное замедление: {slowdown:.1f}x медленнее в pipeline")
        
        # Анализ узких мест
        steps_timing = step_by_step["steps_timing_ms"]
        total_time = steps_timing["total_pipeline"]
        
        for step, time_ms in steps_timing.items():
            if step != "total_pipeline" and (time_ms / total_time) > 0.5:  # Более 50% времени
                analysis["bottlenecks"].append(f"{step}: {time_ms:.1f}ms ({(time_ms/total_time)*100:.1f}%)")
        
        # Анализ памяти
        memory_deltas = step_by_step["memory_deltas_mb"]
        for step, delta in memory_deltas.items():
            if delta > 100:  # Более 100MB
                analysis["bottlenecks"].append(f"Память {step}: +{delta:.1f}MB")
        
        # Рекомендации
        rerank_percentage = comparison["rerank_percentage_of_pipeline"]
        if rerank_percentage > 80:
            analysis["recommendations"].append("Реранжирование занимает >80% времени - критично оптимизировать")
        
        predict_time = steps_timing.get("rerank_model_predict", 0)
        if predict_time > 20000:  # Более 20 секунд
            analysis["recommendations"].append("model.predict() занимает >20сек - проверить модель и данные")
        
        return analysis


def main():
    """Основная функция для запуска анализа"""
    profiler = DetailedRerankingProfiler()
    
    # Запускаем комплексный анализ
    results = profiler.run_comprehensive_analysis(
        query="Какие документы есть в системе?",
        access_level=50
    )
    
    # Выводим результаты
    print("\n" + "="*80)
    print("РЕЗУЛЬТАТЫ КОМПЛЕКСНОГО АНАЛИЗА")
    print("="*80)
    
    comparison = results["comparison"]
    print(f"\n📊 СРАВНИТЕЛЬНАЯ СТАТИСТИКА:")
    print(f"Изолированное реранжирование: {comparison['isolated_avg_ms']:.1f}ms")
    print(f"Pipeline полностью: {comparison['pipeline_avg_ms']:.1f}ms")
    print(f"Реранжирование в pipeline: {comparison['rerank_time_in_pipeline_ms']:.1f}ms")
    print(f"Замедление pipeline vs isolated: {comparison['slowdown_factor_pipeline_vs_isolated']:.1f}x")
    print(f"Доля реранжирования в pipeline: {comparison['rerank_percentage_of_pipeline']:.1f}%")
    
    step_by_step = results["step_by_step"]
    print(f"\n⏱️ ПОШАГОВОЕ ВРЕМЯ:")
    for step, time_ms in step_by_step["steps_timing_ms"].items():
        if step != "total_pipeline":
            percentage = (time_ms / step_by_step["steps_timing_ms"]["total_pipeline"]) * 100
            print(f"  {step}: {time_ms:.1f}ms ({percentage:.1f}%)")
    
    analysis = results["analysis"]
    print(f"\n🔍 АНАЛИЗ:")
    for finding in analysis["findings"]:
        print(f"  • {finding}")
    
    print(f"\n🚨 УЗКИЕ МЕСТА:")
    for bottleneck in analysis["bottlenecks"]:
        print(f"  • {bottleneck}")
    
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    for recommendation in analysis["recommendations"]:
        print(f"  • {recommendation}")
    
    # Детали реранжирования
    rerank_details = step_by_step["reranking_details"]
    print(f"\n🔬 ДЕТАЛИ РЕРАНЖИРОВАНИЯ:")
    print(f"  Документов: {step_by_step['documents_count']}")
    print(f"  Пар для обработки: {rerank_details['pairs_count']}")
    print(f"  Память до predict: {rerank_details['memory_before_predict']['rss_mb']:.1f}MB")
    print(f"  Память после predict: {rerank_details['memory_after_predict']['rss_mb']:.1f}MB")
    print(f"  Прирост памяти: {rerank_details['memory_delta_predict_mb']:.1f}MB")
    print(f"  model.predict() время: {step_by_step['steps_timing_ms']['rerank_model_predict']:.1f}ms")
    
    return results


if __name__ == "__main__":
    main()
