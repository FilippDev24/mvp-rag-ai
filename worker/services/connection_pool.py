"""
Сервис connection pooling для оптимизации производительности
T1.5: Connection pooling для ChromaDB и других внешних сервисов
"""

import os
import time
import threading
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
import chromadb
import structlog

logger = structlog.get_logger(__name__)

class ChromaDBPool:
    """
    Connection pool для ChromaDB клиентов
    """
    
    def __init__(self, max_connections: int = 10, min_connections: int = 2):
        """
        Инициализация пула соединений ChromaDB
        
        Args:
            max_connections: Максимальное количество соединений
            min_connections: Минимальное количество соединений
        """
        self.max_connections = max_connections
        self.min_connections = min_connections
        
        # Парсим CHROMADB_URL или используем отдельные переменные
        chromadb_url = os.getenv('CHROMADB_URL', 'http://localhost:8000')
        if chromadb_url.startswith('http://'):
            # Парсим URL вида http://chromadb:8000
            url_parts = chromadb_url.replace('http://', '').split(':')
            self.chroma_host = url_parts[0]
            self.chroma_port = int(url_parts[1]) if len(url_parts) > 1 else 8000
        else:
            # Fallback на отдельные переменные
            self.chroma_host = os.getenv('CHROMA_HOST', 'localhost')
            self.chroma_port = int(os.getenv('CHROMA_PORT', '8000'))
        
        # Пул доступных соединений
        self.available_connections = Queue(maxsize=max_connections)
        self.active_connections = set()
        self.connection_count = 0
        
        # Блокировка для thread-safety
        self.lock = threading.Lock()
        
        # Статистика
        self.stats = {
            'total_created': 0,
            'total_borrowed': 0,
            'total_returned': 0,
            'total_errors': 0,
            'peak_active': 0
        }
        
        # Инициализируем минимальное количество соединений
        self._initialize_pool()
        
        logger.info("ChromaDBPool инициализирован", 
                   max_connections=max_connections,
                   min_connections=min_connections,
                   host=self.chroma_host,
                   port=self.chroma_port)
    
    def _initialize_pool(self):
        """Создание минимального количества соединений при инициализации"""
        try:
            for _ in range(self.min_connections):
                client = self._create_client()
                if client:
                    self.available_connections.put(client)
                    self.connection_count += 1
                    self.stats['total_created'] += 1
            
            logger.info(f"Создано {self.connection_count} начальных соединений ChromaDB")
            
        except Exception as e:
            logger.error("Ошибка инициализации пула ChromaDB", error=str(e))
    
    def _create_client(self) -> Optional[chromadb.HttpClient]:
        """
        Создание нового ChromaDB клиента
        
        Returns:
            ChromaDB клиент или None при ошибке
        """
        try:
            client = chromadb.HttpClient(
                host=self.chroma_host,
                port=self.chroma_port
            )
            
            # Проверяем соединение
            client.heartbeat()
            
            return client
            
        except Exception as e:
            logger.error("Ошибка создания ChromaDB клиента", error=str(e))
            self.stats['total_errors'] += 1
            return None
    
    def get_client(self, timeout: float = 30.0) -> Optional[chromadb.HttpClient]:
        """
        Получение клиента из пула
        
        Args:
            timeout: Таймаут ожидания доступного соединения
            
        Returns:
            ChromaDB клиент или None
        """
        start_time = time.time()
        
        try:
            # Пытаемся получить существующее соединение
            try:
                client = self.available_connections.get(timeout=min(timeout, 5.0))
                
                with self.lock:
                    self.active_connections.add(client)
                    self.stats['total_borrowed'] += 1
                    self.stats['peak_active'] = max(
                        self.stats['peak_active'], 
                        len(self.active_connections)
                    )
                
                # Проверяем что соединение живое
                try:
                    client.heartbeat()
                    
                    get_time = (time.time() - start_time) * 1000
                    logger.debug("Получен клиент из пула", 
                               get_time_ms=get_time,
                               active_connections=len(self.active_connections))
                    
                    return client
                    
                except Exception:
                    # Соединение мертвое, удаляем его
                    with self.lock:
                        self.active_connections.discard(client)
                        self.connection_count -= 1
                    
                    logger.warning("Удалено мертвое соединение из пула")
                
            except Empty:
                # Нет доступных соединений
                pass
            
            # Создаем новое соединение если можем
            with self.lock:
                if self.connection_count < self.max_connections:
                    client = self._create_client()
                    
                    if client:
                        self.active_connections.add(client)
                        self.connection_count += 1
                        self.stats['total_created'] += 1
                        self.stats['total_borrowed'] += 1
                        self.stats['peak_active'] = max(
                            self.stats['peak_active'], 
                            len(self.active_connections)
                        )
                        
                        get_time = (time.time() - start_time) * 1000
                        logger.debug("Создан новый клиент", 
                                   get_time_ms=get_time,
                                   total_connections=self.connection_count)
                        
                        return client
            
            # Ждем освобождения соединения
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout > 0:
                try:
                    client = self.available_connections.get(timeout=remaining_timeout)
                    
                    with self.lock:
                        self.active_connections.add(client)
                        self.stats['total_borrowed'] += 1
                    
                    # Проверяем соединение
                    try:
                        client.heartbeat()
                        return client
                    except Exception:
                        with self.lock:
                            self.active_connections.discard(client)
                            self.connection_count -= 1
                        
                except Empty:
                    pass
            
            logger.warning("Не удалось получить ChromaDB клиент", 
                          timeout=timeout,
                          active_connections=len(self.active_connections),
                          total_connections=self.connection_count)
            
            return None
            
        except Exception as e:
            logger.error("Ошибка получения клиента из пула", error=str(e))
            self.stats['total_errors'] += 1
            return None
    
    def return_client(self, client: chromadb.HttpClient):
        """
        Возврат клиента в пул
        
        Args:
            client: ChromaDB клиент для возврата
        """
        try:
            with self.lock:
                if client in self.active_connections:
                    self.active_connections.remove(client)
                    self.stats['total_returned'] += 1
                    
                    # Проверяем что соединение живое
                    try:
                        client.heartbeat()
                        
                        # Возвращаем в пул если есть место
                        if not self.available_connections.full():
                            self.available_connections.put_nowait(client)
                            logger.debug("Клиент возвращен в пул", 
                                       active_connections=len(self.active_connections))
                        else:
                            # Пул полный, закрываем соединение
                            self.connection_count -= 1
                            logger.debug("Пул полный, соединение закрыто")
                            
                    except Exception:
                        # Соединение мертвое
                        self.connection_count -= 1
                        logger.debug("Мертвое соединение удалено при возврате")
                
        except Exception as e:
            logger.error("Ошибка возврата клиента в пул", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики пула
        
        Returns:
            Статистика использования пула
        """
        with self.lock:
            return {
                "pool_config": {
                    "max_connections": self.max_connections,
                    "min_connections": self.min_connections,
                    "host": self.chroma_host,
                    "port": self.chroma_port
                },
                "current_state": {
                    "total_connections": self.connection_count,
                    "active_connections": len(self.active_connections),
                    "available_connections": self.available_connections.qsize()
                },
                "statistics": self.stats.copy()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья пула соединений
        
        Returns:
            Статус здоровья пула
        """
        try:
            # Пытаемся получить и вернуть соединение
            client = self.get_client(timeout=5.0)
            
            if client:
                self.return_client(client)
                
                return {
                    "status": "healthy",
                    "total_connections": self.connection_count,
                    "active_connections": len(self.active_connections)
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Cannot obtain connection from pool"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def close_all(self):
        """Закрытие всех соединений в пуле"""
        try:
            logger.info("Закрытие всех соединений в пуле")
            
            # Закрываем активные соединения
            with self.lock:
                active_copy = self.active_connections.copy()
                for client in active_copy:
                    try:
                        self.active_connections.remove(client)
                    except Exception:
                        pass
            
            # Закрываем доступные соединения
            while not self.available_connections.empty():
                try:
                    client = self.available_connections.get_nowait()
                except Empty:
                    break
            
            self.connection_count = 0
            logger.info("Все соединения закрыты")
            
        except Exception as e:
            logger.error("Ошибка закрытия пула", error=str(e))


# Глобальный экземпляр пула ChromaDB
_chromadb_pool_instance = None

def get_chromadb_pool() -> ChromaDBPool:
    """
    Получить глобальный экземпляр ChromaDBPool (singleton pattern)
    
    Returns:
        Экземпляр ChromaDBPool
    """
    global _chromadb_pool_instance
    
    if _chromadb_pool_instance is None:
        max_connections = int(os.getenv('CHROMADB_POOL_MAX', '10'))
        min_connections = int(os.getenv('CHROMADB_POOL_MIN', '2'))
        
        _chromadb_pool_instance = ChromaDBPool(
            max_connections=max_connections,
            min_connections=min_connections
        )
    
    return _chromadb_pool_instance


class PooledChromaDBClient:
    """
    Context manager для работы с пулом ChromaDB соединений
    """
    
    def __init__(self, pool: ChromaDBPool, timeout: float = 30.0):
        self.pool = pool
        self.timeout = timeout
        self.client = None
    
    def __enter__(self) -> Optional[chromadb.HttpClient]:
        self.client = self.pool.get_client(timeout=self.timeout)
        return self.client
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.pool.return_client(self.client)
