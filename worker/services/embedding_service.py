import os
import numpy as np
import time
import re
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import logging

logger = logging.getLogger(__name__)

class EmbeddingConfig:
    """Конфигурация для эмбеддингов согласно требованиям ТЗ"""
    MODEL = 'intfloat/multilingual-e5-large-instruct'  # КРИТИЧНО: instruct модель
    DIMENSION = 1024                                    # НЕ МЕНЯТЬ!
    MAX_SEQ_LENGTH = 512                               # НЕ МЕНЯТЬ!
    BATCH_SIZE = 32
    
    # ОБЯЗАТЕЛЬНЫЕ префиксы для instruct модели
    DOCUMENT_PREFIX = ""  # Для документов БЕЗ инструкций
    
    # R5.1: РУСИФИКАЦИЯ - Адаптивные инструкции для разных языков
    QUERY_PREFIX_RU = "Инструкция: Найди релевантные фрагменты документов для данного поискового запроса\nЗапрос: "
    QUERY_PREFIX_EN = "Instruct: Given a search query, retrieve relevant passages from knowledge base\nQuery: "
    
    # Fallback для совместимости
    QUERY_PREFIX = QUERY_PREFIX_EN

# Глобальная модель для переиспользования между процессами
_global_model = None

class EmbeddingService:
    """
    Сервис для генерации эмбеддингов текста
    КРИТИЧНО: Использует multilingual-e5-large-instruct с особым форматом
    """
    
    def __init__(self):
        global _global_model
        self.config = EmbeddingConfig()
        self.logger = logger
        self.tokenizer = None
        
        if _global_model is None:
            self._load_model()
            _global_model = self.model
        else:
            self.model = _global_model
            self.logger.info("Using cached embedding model")
        
        # Загружаем токенизатор для подсчета токенов
        if self.tokenizer is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.MODEL)
    
    def _detect_language(self, text: str) -> str:
        """
        R5.1: Простое определение языка по наличию кириллицы
        
        Args:
            text: Текст для анализа
            
        Returns:
            'ru' для русского, 'en' для английского
        """
        # Подсчитываем кириллические символы
        cyrillic_chars = len(re.findall(r'[а-яё]', text.lower()))
        total_chars = len(re.findall(r'[а-яёa-z]', text.lower()))
        
        if total_chars == 0:
            return 'en'  # По умолчанию английский для пустых/символьных запросов
        
        # Если больше 30% кириллицы - считаем русским
        cyrillic_ratio = cyrillic_chars / total_chars
        language = 'ru' if cyrillic_ratio > 0.3 else 'en'
        
        self.logger.debug(f"Language detection: '{text[:50]}...' -> {language} (cyrillic: {cyrillic_ratio:.2f})")
        return language
    
    def _get_query_prefix(self, query: str) -> tuple[str, str]:
        """
        R5.1: Получить подходящий префикс для запроса на основе языка
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Tuple (prefix, detected_language)
        """
        detected_language = self._detect_language(query)
        
        if detected_language == 'ru':
            return self.config.QUERY_PREFIX_RU, 'ru'
        else:
            return self.config.QUERY_PREFIX_EN, 'en'
    
    def _load_model(self):
        """Загрузка instruct модели эмбеддингов согласно ТЗ"""
        try:
            self.logger.info(f"Loading embedding model: {self.config.MODEL}")
            
            # КРИТИЧНО: Загружаем instruct модель
            self.model = SentenceTransformer(
                self.config.MODEL,
                device='cpu'  # На M4 CPU быстрее GPU эмуляции
            )
            
            # Установка максимальной длины последовательности
            self.model.max_seq_length = self.config.MAX_SEQ_LENGTH
            
            # Включаем оптимизации для batch обработки
            self.model.eval()  # Переводим в режим inference
            
            self.logger.info("Instruct embedding model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading embedding model: {str(e)}")
            raise e
    
    def generate_document_embedding(self, text: str) -> Dict[str, Any]:
        """
        Генерация эмбеддинга для документа с метриками
        КРИТИЧНО: Для документов БЕЗ инструкций
        
        Args:
            text: Текст документа
            
        Returns:
            Словарь с эмбеддингом и метриками
        """
        start_time = time.time()
        
        try:
            # КРИТИЧНО: Для документов БЕЗ префикса Instruct
            prefixed_text = self.config.DOCUMENT_PREFIX + text
            
            # Подсчет токенов на входе
            tokens_in = len(self.tokenizer.encode(prefixed_text, truncation=True, max_length=self.config.MAX_SEQ_LENGTH))
            
            # Генерация эмбеддинга
            embedding = self.model.encode(
                prefixed_text,
                batch_size=1,
                normalize_embeddings=True,  # ОБЯЗАТЕЛЬНО!
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            embedding_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            self.logger.info(f"Document embedding generated: {embedding_time:.1f}ms, {tokens_in} tokens")
            
            return {
                "embedding": embedding.tolist(),
                "metrics": {
                    "embedding_time_ms": embedding_time,
                    "tokens_in": tokens_in,
                    "model": self.config.MODEL,
                    "dimension": self.config.DIMENSION
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating document embedding: {str(e)}")
            raise e
    
    def generate_query_embedding(self, query: str) -> Dict[str, Any]:
        """
        R5.1: Генерация эмбеддинга для запроса с адаптивными инструкциями
        КРИТИЧНО: С обязательным форматом Instruct для запросов
        
        Args:
            query: Текст запроса
            
        Returns:
            Словарь с эмбеддингом и метриками
        """
        start_time = time.time()
        
        try:
            # R5.1: Получаем адаптивный префикс на основе языка запроса
            query_prefix, detected_language = self._get_query_prefix(query)
            prefixed_query = query_prefix + query
            
            # Подсчет токенов на входе
            tokens_in = len(self.tokenizer.encode(prefixed_query, truncation=True, max_length=self.config.MAX_SEQ_LENGTH))
            
            # Генерация эмбеддинга
            embedding = self.model.encode(
                prefixed_query,
                batch_size=1,
                normalize_embeddings=True,  # ОБЯЗАТЕЛЬНО!
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            embedding_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            self.logger.info(f"Query embedding generated ({detected_language}): {embedding_time:.1f}ms, {tokens_in} tokens")
            
            return {
                "embedding": embedding.tolist(),
                "metrics": {
                    "embedding_time_ms": embedding_time,
                    "tokens_in": tokens_in,
                    "model": self.config.MODEL,
                    "dimension": self.config.DIMENSION,
                    "instruct_format": True,
                    "detected_language": detected_language,
                    "instruction_prefix": query_prefix.split('\n')[0]  # Первая строка инструкции для логов
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating query embedding: {str(e)}")
            raise e
    
    def generate_batch_embeddings(self, texts: List[str], is_query: bool = False) -> Dict[str, Any]:
        """
        Генерация эмбеддингов для батча текстов с метриками
        
        Args:
            texts: Список текстов
            is_query: True если это запросы, False если документы
            
        Returns:
            Словарь с эмбеддингами и метриками
        """
        start_time = time.time()
        
        try:
            # КРИТИЧНО: Добавление соответствующих префиксов
            prefix = self.config.QUERY_PREFIX if is_query else self.config.DOCUMENT_PREFIX
            prefixed_texts = [prefix + text for text in texts]
            
            # Подсчет общего количества токенов
            total_tokens = sum(
                len(self.tokenizer.encode(text, truncation=True, max_length=self.config.MAX_SEQ_LENGTH))
                for text in prefixed_texts
            )
            
            # Генерация эмбеддингов батчами
            embeddings = []
            for i in range(0, len(prefixed_texts), self.config.BATCH_SIZE):
                batch = prefixed_texts[i:i + self.config.BATCH_SIZE]
                batch_embeddings = self.model.encode(
                    batch,
                    normalize_embeddings=True,  # ОБЯЗАТЕЛЬНО!
                    batch_size=self.config.BATCH_SIZE,
                    convert_to_numpy=True
                )
                # Конвертируем в список списков
                embeddings.extend([emb.tolist() for emb in batch_embeddings])
            
            embedding_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            self.logger.info(f"Generated {len(embeddings)} batch embeddings: {embedding_time:.1f}ms, {total_tokens} tokens")
            
            return {
                "embeddings": embeddings,
                "metrics": {
                    "embedding_time_ms": embedding_time,
                    "total_tokens": total_tokens,
                    "batch_size": len(texts),
                    "model": self.config.MODEL,
                    "is_query": is_query,
                    "instruct_format": is_query
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating batch embeddings: {str(e)}")
            raise e
    
    def get_embedding_dimension(self) -> int:
        """Получить размерность эмбеддингов"""
        return self.config.DIMENSION
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о модели"""
        return {
            "model_name": self.config.MODEL,
            "dimension": self.config.DIMENSION,
            "max_seq_length": self.config.MAX_SEQ_LENGTH,
            "batch_size": self.config.BATCH_SIZE
        }
