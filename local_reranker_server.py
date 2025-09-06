#!/usr/bin/env python3
"""
Универсальный FastAPI сервер для реранжирования
Автоматически адаптируется под macOS (Apple Silicon) и Ubuntu (x86_64)
Запускается НА ХОСТЕ (не в Docker) для максимальной производительности

ПОРТ: 8002 (чтобы не конфликтовать с другими сервисами)
"""

import os
import platform
import logging
import time
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from sentence_transformers import CrossEncoder
import numpy as np
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определение платформы
PLATFORM = platform.system()
ARCHITECTURE = platform.machine()
IS_APPLE_SILICON = PLATFORM == "Darwin" and ARCHITECTURE == "arm64"
IS_UBUNTU = PLATFORM == "Linux"

logger.info(f"🖥️  Platform: {PLATFORM} {ARCHITECTURE}")
if IS_APPLE_SILICON:
    logger.info("🍎 Detected Apple Silicon - will use MPS optimizations")
elif IS_UBUNTU:
    logger.info("🐧 Detected Ubuntu - will use CUDA/CPU optimizations")

# Pydantic модели для API
class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_k: int = 10

class RerankResponse(BaseModel):
    results: List[Dict[str, Any]]
    processing_time_ms: float
    device_used: str

# Конфигурация
class RerankConfig:
    MODEL = os.getenv('RERANKER_MODEL', 'BAAI/bge-reranker-v2-m3')
    MAX_LENGTH = int(os.getenv('RERANKER_MAX_LENGTH', '512'))

# FastAPI приложение
app = FastAPI(
    title=f"Universal Reranker Service ({PLATFORM})",
    description=f"High-performance reranking service for {PLATFORM} {ARCHITECTURE}",
    version="1.0.0"
)

# Глобальные переменные
model = None
device = None
config = RerankConfig()

def setup_device_optimizations():
    """Настройка оптимизаций для конкретной платформы"""
    global device
    
    if IS_APPLE_SILICON:
        # Apple Silicon оптимизации
        if torch.backends.mps.is_available():
            device = "mps"
            logger.info("🚀 Using MPS (Metal Performance Shaders) for Apple Silicon")
        else:
            device = "cpu"
            logger.info("⚠️  MPS not available, using CPU")
            
    elif IS_UBUNTU:
        # Ubuntu оптимизации
        if torch.cuda.is_available():
            device = "cuda"
            logger.info("🚀 Using CUDA GPU on Ubuntu")
            # CUDA оптимизации
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            if hasattr(torch.backends.cuda, 'matmul'):
                torch.backends.cuda.matmul.allow_tf32 = True
            if hasattr(torch.backends.cudnn, 'allow_tf32'):
                torch.backends.cudnn.allow_tf32 = True
        else:
            device = "cpu"
            logger.info("⚠️  CUDA not available, using CPU")
            # CPU оптимизации для Ubuntu
            torch.set_num_threads(os.cpu_count())
            os.environ['OMP_NUM_THREADS'] = str(os.cpu_count())
            os.environ['MKL_NUM_THREADS'] = str(os.cpu_count())
    else:
        # Fallback для других платформ
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🔧 Using {device} on {PLATFORM}")

def clear_device_cache():
    """Очистка кэша устройства в зависимости от платформы"""
    if device == "mps" and IS_APPLE_SILICON:
        if hasattr(torch, 'mps') and hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()
        elif hasattr(torch.backends.mps, 'empty_cache'):
            torch.backends.mps.empty_cache()
    elif device == "cuda":
        torch.cuda.empty_cache()

def initialize_model():
    """Универсальная инициализация модели"""
    global model
    
    try:
        setup_device_optimizations()
        
        logger.info(f"📥 Loading reranker model: {config.MODEL}")
        start_time = time.time()
        
        # Загружаем модель с учетом платформы
        model = CrossEncoder(
            config.MODEL,
            max_length=config.MAX_LENGTH,
            device=device
        )
        
        # Очистка кэша
        clear_device_cache()
        
        load_time = time.time() - start_time
        logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")
        
        # Прогрев модели
        logger.info("🔥 Warming up reranker model...")
        warmup_start = time.time()
        _ = model.predict([("test query", "test document")])
        warmup_time = time.time() - warmup_start
        logger.info(f"✅ Model warmup completed in {warmup_time:.2f} seconds")
        logger.info(f"🎯 Ready for high-performance reranking on {PLATFORM}!")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize model: {str(e)}")
        raise e

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске сервера"""
    logger.info(f"🚀 Starting Universal Reranker Server on {PLATFORM} (port 8002)...")
    initialize_model()

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "device": device,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
        "port": 8002,
        "service": "universal_reranker",
        "model_name": config.MODEL
    }

@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """
    Универсальное реранжирование документов
    """
    if model is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    if not request.documents:
        return RerankResponse(
            results=[],
            processing_time_ms=0.0,
            device_used=device
        )
    
    try:
        start_time = time.time()
        
        # Подготовка пар (query, document)
        pairs = [(request.query, doc) for doc in request.documents]
        
        # Реранжирование с отключенными градиентами для максимальной скорости
        with torch.no_grad():
            clear_device_cache()
            scores = model.predict(pairs)
        
        # Обработка скоров (используем ту же логику, что и в оригинале)
        scores_array = np.array(scores)
        
        # Экспоненциальное масштабирование для усиления различий
        amplification_factor = 100
        amplified_scores = np.exp(scores_array * amplification_factor)
        
        # Нормализация в диапазон 0-10
        min_amplified = np.min(amplified_scores)
        max_amplified = np.max(amplified_scores)
        
        if max_amplified > min_amplified:
            final_scores = (amplified_scores - min_amplified) / (max_amplified - min_amplified) * 10
        else:
            final_scores = np.ones_like(amplified_scores) * 5.0
        
        # Создание результатов
        results = []
        for i, (raw_score, final_score) in enumerate(zip(scores_array, final_scores)):
            results.append({
                "index": i,
                "score": float(final_score),
                "raw_logit": float(raw_score),
                "document": request.documents[i]
            })
        
        # Сортировка по убыванию скора
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Возврат топ-K результатов
        top_results = results[:request.top_k]
        
        processing_time = (time.time() - start_time) * 1000  # в миллисекундах
        
        logger.info(f"⚡ Reranked {len(request.documents)} documents in {processing_time:.1f}ms on {device}")
        
        return RerankResponse(
            results=top_results,
            processing_time_ms=processing_time,
            device_used=device
        )
        
    except Exception as e:
        logger.error(f"❌ Error during reranking: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reranking failed: {str(e)}")

@app.get("/model-info")
async def get_model_info():
    """Информация о модели"""
    expected_perf = "100-300ms on Apple Silicon M4 Pro" if IS_APPLE_SILICON else "200-800ms on Ubuntu (depends on hardware)"
    
    return {
        "model_name": config.MODEL,
        "max_length": config.MAX_LENGTH,
        "device": device,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
        "port": 8002,
        "expected_performance": expected_perf
    }

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": f"Universal Reranker Server ({PLATFORM})",
        "status": "running",
        "port": 8002,
        "model": config.MODEL,
        "platform": f"{PLATFORM} {ARCHITECTURE}",
        "endpoints": {
            "health": "/health",
            "rerank": "/rerank",
            "model_info": "/model-info"
        }
    }

if __name__ == "__main__":
    print(f"🚀 Starting Universal Reranker Server on {PLATFORM}...")
    print("📍 Port: 8002")
    print(f"🤖 Model: {config.MODEL}")
    print(f"🎯 Optimized for {PLATFORM} {ARCHITECTURE}")
    
    # Запуск сервера
    uvicorn.run(
        "local_reranker_server:app",
        host="0.0.0.0",  # Слушаем на всех интерфейсах
        port=8002,
        log_level="info",
        reload=False
    )
