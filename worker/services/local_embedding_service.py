import os
import time
import logging
from typing import List, Dict, Any
import requests
import json

logger = logging.getLogger(__name__)

class LocalEmbeddingService:
    """
    Сервис для генерации эмбеддингов через локальный FastAPI сервер
    Обращается к нативному серверу на хосте для максимальной производительности
    
    ПОРТ: 8003 (локальный сервер эмбеддингов)
    """
    
    def __init__(self):
        # URL локального сервера (host.docker.internal для доступа к хосту из Docker)
        self.base_url = os.getenv('LOCAL_EMBEDDING_URL', 'http://host.docker.internal:8003')
        self.timeout = 30  # 30 секунд таймаут
        self.logger = logger
        
        # Информация о модели (кэшируется)
        self._model_info = None
        
        # Проверяем доступность сервера при инициализации
        self._check_server_health()
    
    def _check_server_health(self):
        """Проверка доступности локального сервера"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                health_data = response.json()
                self.logger.info(f"🚀 Local embedding server is healthy: device={health_data.get('device', 'unknown')}, port={health_data.get('port', 8003)}")
                return True
            else:
                self.logger.warning(f"⚠️  Local embedding server returned status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Cannot connect to local embedding server: {str(e)}")
            self.logger.error("🔧 Make sure to start the local server with: python local_embedding_server.py")
            return False
    
    def _get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели (с кэшированием)"""
        if self._model_info is None:
            try:
                response = requests.get(f"{self.base_url}/model-info", timeout=5)
                if response.status_code == 200:
                    self._model_info = response.json()
                    self.logger.info(f"Model info cached: {self._model_info.get('model_name', 'unknown')}")
                else:
                    self.logger.error(f"Failed to get model info: {response.status_code}")
                    # Fallback значения
                    self._model_info = {
                        "model_name": "intfloat/multilingual-e5-large-instruct",
                        "dimension": 1024,
                        "max_seq_length": 512
                    }
            except Exception as e:
                self.logger.error(f"Error getting model info: {str(e)}")
                # Fallback значения
                self._model_info = {
                    "model_name": "intfloat/multilingual-e5-large-instruct",
                    "dimension": 1024,
                    "max_seq_length": 512
                }
        
        return self._model_info
    
    def generate_query_embedding(self, query: str) -> Dict[str, Any]:
        """
        Генерация эмбеддинга для запроса через локальный сервер
        
        Args:
            query: Текст запроса
            
        Returns:
            Словарь с эмбеддингом и метриками
        """
        try:
            start_time = time.time()
            
            # Подготовка запроса
            request_data = {
                "text": query,
                "is_query": True
            }
            
            # Отправка запроса к локальному серверу
            response = requests.post(
                f"{self.base_url}/embed",
                json=request_data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Server returned status {response.status_code}: {response.text}")
            
            result_data = response.json()
            total_time = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"⚡ Generated query embedding in {total_time:.1f}ms "
                f"(server processing: {result_data.get('processing_time_ms', 0):.1f}ms, "
                f"device: {result_data.get('device_used', 'unknown')})"
            )
            
            return {
                "embedding": result_data["embedding"],
                "metrics": {
                    "embedding_time_ms": result_data["processing_time_ms"],
                    "total_time_ms": total_time,
                    "tokens_in": result_data["tokens"],
                    "model": self._get_model_info().get("model_name", "unknown"),
                    "dimension": self._get_model_info().get("dimension", 1024),
                    "device_used": result_data["device_used"],
                    "detected_language": result_data.get("detected_language"),
                    "instruction_prefix": result_data.get("instruction_prefix"),
                    "instruct_format": True,
                    "service": "local_embedding_server"
                }
            }
            
        except requests.exceptions.Timeout:
            self.logger.error(f"⏰ Timeout waiting for embedding server (>{self.timeout}s)")
            raise Exception("Embedding server timeout")
            
        except requests.exceptions.ConnectionError:
            self.logger.error("❌ Cannot connect to local embedding server")
            self.logger.error("🔧 Make sure to start: python local_embedding_server.py")
            raise Exception("Cannot connect to embedding server")
            
        except Exception as e:
            self.logger.error(f"❌ Error calling local embedding server: {str(e)}")
            raise e
    
    def generate_batch_embeddings(self, texts: List[str], is_query: bool = False) -> Dict[str, Any]:
        """
        Генерация эмбеддингов для батча текстов через локальный сервер
        
        Args:
            texts: Список текстов
            is_query: True если это запросы, False если документы
            
        Returns:
            Словарь с эмбеддингами и метриками
        """
        try:
            if not texts:
                return {
                    "embeddings": [],
                    "metrics": {
                        "embedding_time_ms": 0,
                        "total_time_ms": 0,
                        "total_tokens": 0,
                        "batch_size": 0,
                        "service": "local_embedding_server"
                    }
                }
            
            start_time = time.time()
            
            # Подготовка запроса
            request_data = {
                "texts": texts,
                "is_query": is_query,
                "batch_size": min(len(texts), 32)  # Оптимальный размер батча
            }
            
            # Отправка запроса к локальному серверу
            response = requests.post(
                f"{self.base_url}/embed-batch",
                json=request_data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Server returned status {response.status_code}: {response.text}")
            
            result_data = response.json()
            total_time = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"⚡ Generated {len(result_data['embeddings'])} batch embeddings in {total_time:.1f}ms "
                f"(server processing: {result_data.get('processing_time_ms', 0):.1f}ms, "
                f"device: {result_data.get('device_used', 'unknown')})"
            )
            
            return {
                "embeddings": result_data["embeddings"],
                "metrics": {
                    "embedding_time_ms": result_data["processing_time_ms"],
                    "total_time_ms": total_time,
                    "total_tokens": result_data["total_tokens"],
                    "batch_size": len(texts),
                    "model": result_data["model_info"].get("model", "unknown"),
                    "device_used": result_data["device_used"],
                    "is_query": is_query,
                    "instruct_format": is_query,
                    "service": "local_embedding_server"
                }
            }
            
        except requests.exceptions.Timeout:
            self.logger.error(f"⏰ Timeout waiting for embedding server (>{self.timeout}s)")
            raise Exception("Embedding server timeout")
            
        except requests.exceptions.ConnectionError:
            self.logger.error("❌ Cannot connect to local embedding server")
            self.logger.error("🔧 Make sure to start: python local_embedding_server.py")
            raise Exception("Cannot connect to embedding server")
            
        except Exception as e:
            self.logger.error(f"❌ Error calling local embedding server: {str(e)}")
            raise e
    
    def get_embedding_dimension(self) -> int:
        """Получить размерность эмбеддингов"""
        return self._get_model_info().get("dimension", 1024)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о модели"""
        model_info = self._get_model_info()
        return {
            "model_name": model_info.get("model_name", "intfloat/multilingual-e5-large-instruct"),
            "dimension": model_info.get("dimension", 1024),
            "max_seq_length": model_info.get("max_seq_length", 512),
            "batch_size": 32,
            "service": "local_embedding_server",
            "device": model_info.get("device", "unknown"),
            "port": model_info.get("port", 8003)
        }
    
    def test_performance(self, num_texts: int = 10) -> Dict[str, Any]:
        """Тест производительности генерации эмбеддингов"""
        test_texts = [f"Тестовый текст номер {i} для проверки производительности эмбеддингов" for i in range(num_texts)]
        
        start_time = time.time()
        result = self.generate_batch_embeddings(test_texts, is_query=False)
        total_time = time.time() - start_time
        
        return {
            "num_texts": num_texts,
            "total_time_ms": total_time * 1000,
            "time_per_text_ms": (total_time * 1000) / num_texts,
            "embeddings_count": len(result["embeddings"]),
            "server_available": len(result["embeddings"]) > 0,
            "server_processing_time_ms": result["metrics"].get("embedding_time_ms", 0)
        }

# Глобальный экземпляр для переиспользования
_global_local_embedding_service = None

def get_local_embedding_service() -> LocalEmbeddingService:
    """Получить глобальный экземпляр LocalEmbeddingService"""
    global _global_local_embedding_service
    
    if _global_local_embedding_service is None:
        _global_local_embedding_service = LocalEmbeddingService()
    
    return _global_local_embedding_service
