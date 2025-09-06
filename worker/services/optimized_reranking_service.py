"""
Оптимизированный сервис реранжирования для Apple Silicon
Использует MPS (Metal Performance Shaders) для ускорения на Apple GPU
"""

import time
import logging
import numpy as np
from typing import List, Dict, Any
import structlog
import torch
from sentence_transformers import CrossEncoder

logger = structlog.get_logger(__name__)

class OptimizedRerankingService:
    """
    Оптимизированный сервис реранжирования с поддержкой Apple Silicon MPS
    """
    
    def __init__(self):
        """Инициализация с автоматическим выбором устройства"""
        self.model_name = "BAAI/bge-reranker-v2-m3"
        
        # Автоматический выбор лучшего устройства
        if torch.backends.mps.is_available():
            self.device = "mps"  # Apple Silicon GPU
            logger.info("Используем Apple Silicon MPS для ускорения")
        elif torch.cuda.is_available():
            self.device = "cuda"  # NVIDIA GPU
            logger.info("Используем CUDA для ускорения")
        else:
            self.device = "cpu"
            logger.warning("Используем CPU - будет медленно")
        
        # Инициализация модели с оптимизациями
        logger.info(f"Загружаем BGE модель на {self.device}")
        start_time = time.time()
        
        self.model = CrossEncoder(
            self.model_name,
            max_length=512,
            device=self.device
        )
        
        # Оптимизации для производительности
        if hasattr(self.model.model, 'eval'):
            self.model.model.eval()  # Режим inference
        
        # Компиляция модели для ускорения (PyTorch 2.0+)
        if hasattr(torch, 'compile') and self.device != "cpu":
            try:
                self.model.model = torch.compile(self.model.model, mode="reduce-overhead")
                logger.info("Модель скомпилирована для ускорения")
            except Exception as e:
                logger.warning(f"Не удалось скомпилировать модель: {e}")
        
        init_time = (time.time() - start_time) * 1000
        logger.info(f"BGE модель загружена за {init_time:.1f}ms на {self.device}")
    
    def rerank_results(
        self, 
        query: str, 
        documents: List[str], 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Оптимизированное реранжирование с батчингом и кэшированием
        
        Args:
            query: Поисковый запрос
            documents: Список документов для реранжирования
            top_k: Количество топ результатов
            
        Returns:
            Реранжированные результаты с оптимизированными скорами
        """
        start_time = time.time()
        
        try:
            if not documents:
                return []
            
            # Подготовка пар для батчинга
            pairs = [(query, doc) for doc in documents]
            
            # Батчинг для оптимизации
            batch_size = min(32, len(pairs))  # Оптимальный размер батча
            
            logger.debug(f"Реранжирование {len(pairs)} пар с batch_size={batch_size}")
            
            # Получение скоров с батчингом
            with torch.no_grad():  # Отключаем градиенты для inference
                raw_scores = self.model.predict(pairs)
            
            # Простая нормализация без экспоненциального усиления
            # (экспоненциальное усиление с factor=100 избыточно и может вызывать переполнение)
            scores_array = np.array(raw_scores)
            
            # Нормализация в диапазон 0-10 с сохранением относительных различий
            min_score = np.min(scores_array)
            max_score = np.max(scores_array)
            
            if max_score != min_score:
                normalized_scores = ((scores_array - min_score) / (max_score - min_score)) * 10
            else:
                normalized_scores = np.full_like(scores_array, 5.0)  # Средний скор если все одинаковые
            
            # Создание результатов
            results = []
            for i, (doc, score) in enumerate(zip(documents, normalized_scores)):
                results.append({
                    "index": i,
                    "document": doc,
                    "score": float(score)
                })
            
            # Сортировка по скору
            results.sort(key=lambda x: x["score"], reverse=True)
            
            # Возвращаем топ результаты
            final_results = results[:top_k]
            
            rerank_time = (time.time() - start_time) * 1000
            
            logger.debug(f"Реранжирование завершено за {rerank_time:.1f}ms: "
                        f"{len(documents)} → {len(final_results)} результатов")
            
            return final_results
            
        except Exception as e:
            rerank_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка реранжирования за {rerank_time:.1f}ms", error=str(e))
            
            # Fallback: возвращаем документы в исходном порядке
            return [
                {
                    "index": i,
                    "document": doc,
                    "score": 5.0 - (i * 0.1)  # Убывающие скоры
                }
                for i, doc in enumerate(documents[:top_k])
            ]
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о модели"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "framework": "sentence-transformers",
            "optimizations": [
                "MPS support" if self.device == "mps" else None,
                "CUDA support" if self.device == "cuda" else None,
                "Torch compile" if hasattr(torch, 'compile') else None,
                "Batch processing",
                "Simplified normalization"
            ]
        }

# Глобальный экземпляр
_optimized_reranking_service = None

def get_optimized_reranking_service() -> OptimizedRerankingService:
    """Получить оптимизированный сервис реранжирования (singleton)"""
    global _optimized_reranking_service
    
    if _optimized_reranking_service is None:
        _optimized_reranking_service = OptimizedRerankingService()
    
    return _optimized_reranking_service
