"""
Сервис кэширования для оптимизации производительности поиска
T1.4: Кэширование поисковых запросов в Redis
"""

import os
import json
import hashlib
import time
import redis
from typing import Dict, Any, Optional, List
import structlog

logger = structlog.get_logger(__name__)

class CacheService:
    """
    Сервис кэширования результатов поиска в Redis
    """
    
    def __init__(self):
        """Инициализация подключения к Redis"""
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        
        # Настройки кэширования
        self.search_cache_ttl = 3600  # 1 час
        self.bm25_cache_ttl = 7200    # 2 часа
        
        # Префиксы для разных типов кэша
        self.search_prefix = "search_cache:"
        self.bm25_prefix = "bm25_cache:"
        
        logger.info("CacheService инициализирован", redis_url=self.redis_url)
    
    def _generate_search_cache_key(
        self, 
        query: str, 
        access_level: int, 
        search_params: Dict[str, Any] = None
    ) -> str:
        """
        Генерация ключа кэша для поискового запроса
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа пользователя
            search_params: Дополнительные параметры поиска
            
        Returns:
            Ключ кэша
        """
        # Создаём уникальный хэш на основе всех параметров
        cache_data = {
            "query": query.strip().lower(),
            "access_level": access_level,
            "params": search_params or {}
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
        
        return f"{self.search_prefix}{cache_hash}"
    
    def get_cached_search_results(
        self, 
        query: str, 
        access_level: int, 
        search_params: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получение кэшированных результатов поиска
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа пользователя
            search_params: Дополнительные параметры поиска
            
        Returns:
            Кэшированные результаты или None
        """
        try:
            cache_key = self._generate_search_cache_key(query, access_level, search_params)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                results = json.loads(cached_data)
                
                # Добавляем метку что результат из кэша
                results["from_cache"] = True
                results["cache_hit_time"] = time.time()
                
                logger.info("Cache HIT для поискового запроса", 
                           query=query[:50], 
                           access_level=access_level,
                           cache_key=cache_key[:20])
                
                return results
            
            logger.debug("Cache MISS для поискового запроса", 
                        query=query[:50], 
                        access_level=access_level)
            
            return None
            
        except Exception as e:
            logger.error("Ошибка получения из кэша", error=str(e))
            return None
    
    def cache_search_results(
        self, 
        query: str, 
        access_level: int, 
        results: Dict[str, Any],
        search_params: Dict[str, Any] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Кэширование результатов поиска
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа пользователя
            results: Результаты поиска для кэширования
            search_params: Дополнительные параметры поиска
            ttl: Время жизни кэша (по умолчанию self.search_cache_ttl)
            
        Returns:
            True если успешно закэшировано
        """
        try:
            cache_key = self._generate_search_cache_key(query, access_level, search_params)
            
            # Добавляем метаданные кэша
            cache_data = results.copy()
            cache_data.update({
                "cached_at": time.time(),
                "cache_ttl": ttl or self.search_cache_ttl,
                "from_cache": False
            })
            
            # Сохраняем в Redis
            success = self.redis_client.setex(
                cache_key,
                ttl or self.search_cache_ttl,
                json.dumps(cache_data, ensure_ascii=False)
            )
            
            if success:
                logger.info("Результаты поиска закэшированы", 
                           query=query[:50], 
                           access_level=access_level,
                           results_count=len(results.get("results", [])),
                           ttl=ttl or self.search_cache_ttl)
            
            return success
            
        except Exception as e:
            logger.error("Ошибка кэширования результатов", error=str(e))
            return False
    
    def invalidate_search_cache(self, pattern: str = None) -> int:
        """
        Инвалидация кэша поиска
        
        Args:
            pattern: Паттерн для удаления (по умолчанию все поисковые кэши)
            
        Returns:
            Количество удалённых ключей
        """
        try:
            search_pattern = pattern or f"{self.search_prefix}*"
            keys = self.redis_client.keys(search_pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info("Инвалидирован поисковый кэш", 
                           pattern=search_pattern, 
                           deleted_keys=deleted)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error("Ошибка инвалидации кэша", error=str(e))
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получение статистики кэша
        
        Returns:
            Статистика использования кэша
        """
        try:
            # Подсчёт ключей по типам
            search_keys = len(self.redis_client.keys(f"{self.search_prefix}*"))
            bm25_keys = len(self.redis_client.keys(f"{self.bm25_prefix}*"))
            
            # Информация о Redis
            redis_info = self.redis_client.info('memory')
            
            return {
                "search_cache_keys": search_keys,
                "bm25_cache_keys": bm25_keys,
                "redis_memory_used": redis_info.get('used_memory_human', 'N/A'),
                "redis_memory_peak": redis_info.get('used_memory_peak_human', 'N/A'),
                "cache_ttl": {
                    "search": self.search_cache_ttl,
                    "bm25": self.bm25_cache_ttl
                }
            }
            
        except Exception as e:
            logger.error("Ошибка получения статистики кэша", error=str(e))
            return {"error": str(e)}
    
    def get_cached_bm25_index(self, access_level: int) -> Optional[Dict[str, Any]]:
        """
        Получение кэшированного BM25 индекса
        
        Args:
            access_level: Уровень доступа пользователя
            
        Returns:
            Кэшированный BM25 индекс или None
        """
        try:
            cache_key = f"{self.bm25_prefix}index_{access_level}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                import pickle
                bm25_data = pickle.loads(cached_data.encode('latin1'))
                
                logger.info("BM25 индекс загружен из кэша", 
                           access_level=access_level,
                           docs_count=len(bm25_data.get('docs', [])))
                
                return bm25_data
            
            logger.debug("BM25 индекс не найден в кэше", access_level=access_level)
            return None
            
        except Exception as e:
            logger.error("Ошибка загрузки BM25 из кэша", error=str(e))
            return None
    
    def cache_bm25_index(
        self, 
        access_level: int, 
        bm25_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Кэширование BM25 индекса
        
        Args:
            access_level: Уровень доступа пользователя
            bm25_data: Данные BM25 индекса для кэширования
            ttl: Время жизни кэша (по умолчанию self.bm25_cache_ttl)
            
        Returns:
            True если успешно закэшировано
        """
        try:
            cache_key = f"{self.bm25_prefix}index_{access_level}"
            
            # Добавляем метаданные кэша
            cache_data = bm25_data.copy()
            cache_data.update({
                "cached_at": time.time(),
                "access_level": access_level,
                "cache_ttl": ttl or self.bm25_cache_ttl
            })
            
            # Сериализуем с помощью pickle для сохранения объектов BM25
            import pickle
            serialized_data = pickle.dumps(cache_data).decode('latin1')
            
            # Сохраняем в Redis
            success = self.redis_client.setex(
                cache_key,
                ttl or self.bm25_cache_ttl,
                serialized_data
            )
            
            if success:
                logger.info("BM25 индекс закэширован", 
                           access_level=access_level,
                           docs_count=len(bm25_data.get('docs', [])),
                           ttl=ttl or self.bm25_cache_ttl)
            
            return success
            
        except Exception as e:
            logger.error("Ошибка кэширования BM25 индекса", error=str(e))
            return False
    
    def invalidate_bm25_cache(self, access_level: int = None) -> int:
        """
        Инвалидация кэша BM25 индекса
        
        Args:
            access_level: Конкретный уровень доступа или None для всех
            
        Returns:
            Количество удалённых ключей
        """
        try:
            if access_level is not None:
                # Удаляем конкретный индекс
                cache_key = f"{self.bm25_prefix}index_{access_level}"
                deleted = self.redis_client.delete(cache_key)
                
                if deleted:
                    logger.info("Инвалидирован BM25 кэш", access_level=access_level)
                
                return deleted
            else:
                # Удаляем все BM25 индексы
                bm25_pattern = f"{self.bm25_prefix}*"
                keys = self.redis_client.keys(bm25_pattern)
                
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    logger.info("Инвалидированы все BM25 кэши", deleted_keys=deleted)
                    return deleted
                
                return 0
                
        except Exception as e:
            logger.error("Ошибка инвалидации BM25 кэша", error=str(e))
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья Redis соединения
        
        Returns:
            Статус соединения
        """
        try:
            # Простой ping
            pong = self.redis_client.ping()
            
            if pong:
                return {
                    "status": "healthy",
                    "redis_url": self.redis_url,
                    "connection": "active"
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Redis ping failed"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Глобальный экземпляр кэш-сервиса
_cache_service_instance = None

def get_cache_service() -> CacheService:
    """
    Получить глобальный экземпляр CacheService (singleton pattern)
    
    Returns:
        Экземпляр CacheService
    """
    global _cache_service_instance
    
    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
    
    return _cache_service_instance
