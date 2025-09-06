#!/usr/bin/env python3
"""
Универсальный FastAPI сервер для генерации эмбеддингов
Автоматически адаптируется под macOS (Apple Silicon) и Ubuntu (x86_64)
Запускается НА ХОСТЕ (не в Docker) для максимальной производительности

ПОРТ: 8003 (чтобы не конфликтовать с другими сервисами)
"""

import os
import platform
import logging
import time
import re
from typing import List, Dict, Any, Tuple, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
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
class EmbeddingRequest(BaseModel):
    texts: List[str]
    is_query: bool = False

class BatchEmbeddingRequest(BaseModel):
    texts: List[str]
    is_query: bool = False
    batch_size: int = 32

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    processing_time_ms: float
    device_used: str
    total_tokens: int
    model_info: Dict[str, Any]

class SingleEmbeddingRequest(BaseModel):
    text: str
    is_query: bool = False

class SingleEmbeddingResponse(BaseModel):
    embedding: List[float]
    processing_time_ms: float
    device_used: str
    tokens: int
    detected_language: Optional[str] = None
    instruction_prefix: Optional[str] = None

# Конфигурация эмбеддингов (согласно ТЗ)
class EmbeddingConfig:
    # Можно переопределить через переменные окружения
    MODEL = os.getenv('EMBEDDING_MODEL', 'intfloat/multilingual-e5-large-instruct')
    DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1024'))
    MAX_SEQ_LENGTH = int(os.getenv('EMBEDDING_MAX_SEQ_LENGTH', '512'))
    BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '32'))
    
    # Префиксы для instruct модели
    DOCUMENT_PREFIX = ""
    QUERY_PREFIX_RU = "Инструкция: Найди релевантные фрагменты документов для данного поискового запроса\nЗапрос: "
    QUERY_PREFIX_EN = "Instruct: Given a search query, retrieve relevant passages from knowledge base\nQuery: "

# FastAPI приложение
app = FastAPI(
    title=f"Universal Embedding Service ({PLATFORM})",
    description=f"High-performance embedding service for {PLATFORM} {ARCHITECTURE}",
    version="1.0.0"
)

# Глобальные переменные
model = None
tokenizer = None
device = None
config = EmbeddingConfig()

def detect_language(text: str) -> str:
    """Определение языка по наличию кириллицы"""
    cyrillic_chars = len(re.findall(r'[а-яё]', text.lower()))
    total_chars = len(re.findall(r'[а-яёa-z]', text.lower()))
    
    if total_chars == 0:
        return 'en'
    
    cyrillic_ratio = cyrillic_chars / total_chars
    return 'ru' if cyrillic_ratio > 0.3 else 'en'

def get_query_prefix(query: str) -> Tuple[str, str]:
    """Получить подходящий префикс для запроса на основе языка"""
    detected_language = detect_language(query)
    
    if detected_language == 'ru':
        return config.QUERY_PREFIX_RU, 'ru'
    else:
        return config.QUERY_PREFIX_EN, 'en'

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
    global model, tokenizer
    
    try:
        setup_device_optimizations()
        
        logger.info(f"📥 Loading embedding model: {config.MODEL}")
        start_time = time.time()
        
        # Загружаем модель с учетом платформы
        model_device = device if device != "mps" else "cpu"  # SentenceTransformer может не поддерживать MPS напрямую
        
        model = SentenceTransformer(
            config.MODEL,
            device=model_device
        )
        
        # Настройки модели
        model.max_seq_length = config.MAX_SEQ_LENGTH
        model.eval()  # Режим inference
        
        # Загружаем токенизатор
        tokenizer = AutoTokenizer.from_pretrained(config.MODEL)
        
        # Очистка кэша
        clear_device_cache()
        
        load_time = time.time() - start_time
        logger.info(f"✅ Model loaded successfully in {load_time:.2f} seconds")
        
        # Прогрев модели
        logger.info("🔥 Warming up embedding model...")
        warmup_start = time.time()
        _ = model.encode("test document", normalize_embeddings=True)
        warmup_time = time.time() - warmup_start
        logger.info(f"✅ Model warmup completed in {warmup_time:.2f} seconds")
        logger.info(f"🎯 Ready for high-performance embedding generation on {PLATFORM}!")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize model: {str(e)}")
        raise e

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске сервера"""
    logger.info(f"🚀 Starting Universal Embedding Server on {PLATFORM} (port 8003)...")
    initialize_model()

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tokenizer_loaded": tokenizer is not None,
        "device": device,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
        "port": 8003,
        "service": "universal_embedding",
        "model_name": config.MODEL,
        "dimension": config.DIMENSION
    }

@app.post("/embed", response_model=SingleEmbeddingResponse)
async def generate_single_embedding(request: SingleEmbeddingRequest):
    """Генерация одного эмбеддинга"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    try:
        start_time = time.time()
        
        # Подготовка текста с префиксом
        if request.is_query:
            query_prefix, detected_language = get_query_prefix(request.text)
            prefixed_text = query_prefix + request.text
            instruction_prefix = query_prefix.split('\n')[0]
        else:
            prefixed_text = config.DOCUMENT_PREFIX + request.text
            detected_language = None
            instruction_prefix = None
        
        # Подсчет токенов
        tokens = len(tokenizer.encode(prefixed_text, truncation=True, max_length=config.MAX_SEQ_LENGTH))
        
        # Генерация эмбеддинга
        with torch.no_grad():
            clear_device_cache()
            
            embedding = model.encode(
                prefixed_text,
                batch_size=1,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"⚡ Generated embedding in {processing_time:.1f}ms ({tokens} tokens) on {device}")
        
        return SingleEmbeddingResponse(
            embedding=embedding.tolist(),
            processing_time_ms=processing_time,
            device_used=device,
            tokens=tokens,
            detected_language=detected_language,
            instruction_prefix=instruction_prefix
        )
        
    except Exception as e:
        logger.error(f"❌ Error generating embedding: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

@app.post("/embed-batch", response_model=EmbeddingResponse)
async def generate_batch_embeddings(request: BatchEmbeddingRequest):
    """Генерация батча эмбеддингов"""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    if not request.texts:
        return EmbeddingResponse(
            embeddings=[],
            processing_time_ms=0.0,
            device_used=device,
            total_tokens=0,
            model_info={"model": config.MODEL, "dimension": config.DIMENSION}
        )
    
    try:
        start_time = time.time()
        
        # Подготовка текстов с префиксами
        if request.is_query:
            prefixed_texts = []
            for text in request.texts:
                query_prefix, _ = get_query_prefix(text)
                prefixed_texts.append(query_prefix + text)
        else:
            prefixed_texts = [config.DOCUMENT_PREFIX + text for text in request.texts]
        
        # Подсчет общего количества токенов
        total_tokens = sum(
            len(tokenizer.encode(text, truncation=True, max_length=config.MAX_SEQ_LENGTH))
            for text in prefixed_texts
        )
        
        # Генерация эмбеддингов батчами
        embeddings = []
        batch_size = min(request.batch_size, config.BATCH_SIZE)
        
        with torch.no_grad():
            clear_device_cache()
            
            for i in range(0, len(prefixed_texts), batch_size):
                batch = prefixed_texts[i:i + batch_size]
                batch_embeddings = model.encode(
                    batch,
                    normalize_embeddings=True,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=False
                )
                embeddings.extend([emb.tolist() for emb in batch_embeddings])
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(f"⚡ Generated {len(embeddings)} embeddings in {processing_time:.1f}ms ({total_tokens} tokens) on {device}")
        
        return EmbeddingResponse(
            embeddings=embeddings,
            processing_time_ms=processing_time,
            device_used=device,
            total_tokens=total_tokens,
            model_info={
                "model": config.MODEL,
                "dimension": config.DIMENSION,
                "batch_size": len(request.texts),
                "is_query": request.is_query,
                "platform": f"{PLATFORM} {ARCHITECTURE}"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error generating batch embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch embedding generation failed: {str(e)}")

@app.get("/model-info")
async def get_model_info():
    """Информация о модели"""
    expected_perf = "50-200ms on Apple Silicon M4 Pro" if IS_APPLE_SILICON else "100-500ms on Ubuntu (depends on hardware)"
    
    return {
        "model_name": config.MODEL,
        "dimension": config.DIMENSION,
        "max_seq_length": config.MAX_SEQ_LENGTH,
        "batch_size": config.BATCH_SIZE,
        "device": device,
        "platform": PLATFORM,
        "architecture": ARCHITECTURE,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
        "port": 8003,
        "expected_performance": expected_perf
    }

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": f"Universal Embedding Server ({PLATFORM})",
        "status": "running",
        "port": 8003,
        "model": config.MODEL,
        "dimension": config.DIMENSION,
        "platform": f"{PLATFORM} {ARCHITECTURE}",
        "endpoints": {
            "health": "/health",
            "embed": "/embed",
            "embed_batch": "/embed-batch",
            "model_info": "/model-info"
        }
    }

if __name__ == "__main__":
    print(f"🚀 Starting Universal Embedding Server on {PLATFORM}...")
    print("📍 Port: 8003")
    print(f"🤖 Model: {config.MODEL}")
    print(f"📏 Dimension: {config.DIMENSION}")
    print(f"🎯 Optimized for {PLATFORM} {ARCHITECTURE}")
    
    # Запуск сервера
    uvicorn.run(
        "local_embedding_server:app",
        host="0.0.0.0",  # Слушаем на всех интерфейсах
        port=8003,
        log_level="info",
        reload=False
    )
