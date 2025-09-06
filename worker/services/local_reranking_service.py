import os
import logging
import requests
import time
from typing import List, Dict, Any
import json

logger = logging.getLogger(__name__)

class LocalRerankingService:
    """
    Сервис для реранжирования через локальный FastAPI сервер
    Обращается к нативному серверу на хосте для максимальной производительности
    
    ПОРТ: 8002 (локальный сервер реранжирования)
    """
    
    def __init__(self):
        # URL локального сервера (host.docker.internal для доступа к хосту из Docker)
        self.base_url = os.getenv('LOCAL_RERANKER_URL', 'http://host.docker.internal:8002')
        self.timeout = 30  # 30 секунд таймаут
        self.logger = logger
        
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
                self.logger.info(f"🚀 Local reranker server is healthy: device={health_data.get('device', 'unknown')}, port={health_data.get('port', 8002)}")
                return True
            else:
                self.logger.warning(f"⚠️  Local reranker server returned status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Cannot connect to local reranker server: {str(e)}")
            self.logger.error("🔧 Make sure to start the local server with: python local_reranker_server.py")
            return False
    
    def rerank_results(self, query: str, documents: List[str], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Реранжирование результатов поиска через локальный сервер
        
        Args:
            query: Поисковый запрос
            documents: Список документов для реранжирования
            top_k: Количество топ результатов
            
        Returns:
            Список реранжированных результатов с индексами и скорами
        """
        try:
            if not documents:
                return []
            
            start_time = time.time()
            
            # Подготовка запроса
            request_data = {
                "query": query,
                "documents": documents,
                "top_k": top_k
            }
            
            # Отправка запроса к локальному серверу
            response = requests.post(
                f"{self.base_url}/rerank",
                json=request_data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Server returned status {response.status_code}: {response.text}")
            
            result_data = response.json()
            total_time = time.time() - start_time
            
            self.logger.info(
                f"⚡ Reranked {len(documents)} documents in {total_time*1000:.1f}ms "
                f"(server processing: {result_data.get('processing_time_ms', 0):.1f}ms, "
                f"device: {result_data.get('device_used', 'unknown')})"
            )
            
            return result_data["results"]
            
        except requests.exceptions.Timeout:
            self.logger.error(f"⏰ Timeout waiting for reranking server (>{self.timeout}s)")
            return self._fallback_results(documents, top_k)
            
        except requests.exceptions.ConnectionError:
            self.logger.error("❌ Cannot connect to local reranking server")
            self.logger.error("🔧 Make sure to start: python local_reranker_server.py")
            return self._fallback_results(documents, top_k)
            
        except Exception as e:
            self.logger.error(f"❌ Error calling local reranking server: {str(e)}")
            return self._fallback_results(documents, top_k)
    
    def _fallback_results(self, documents: List[str], top_k: int) -> List[Dict[str, Any]]:
        """Fallback результаты если локальный сервер недоступен"""
        self.logger.warning("⚠️  Using fallback results (no reranking)")
        return [
            {"index": i, "score": 0.5, "document": doc} 
            for i, doc in enumerate(documents[:top_k])
        ]
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о модели реранжирования"""
        try:
            response = requests.get(f"{self.base_url}/model-info", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Server returned status {response.status_code}"}
        except Exception as e:
            return {"error": f"Cannot get model info: {str(e)}"}
    
    def test_performance(self, num_documents: int = 10) -> Dict[str, Any]:
        """Тест производительности реранжирования"""
        test_query = "Тестовый запрос для проверки производительности"
        test_documents = [f"Тестовый документ номер {i} с различным содержанием" for i in range(num_documents)]
        
        start_time = time.time()
        results = self.rerank_results(test_query, test_documents, top_k=num_documents)
        total_time = time.time() - start_time
        
        return {
            "num_documents": num_documents,
            "total_time_ms": total_time * 1000,
            "time_per_document_ms": (total_time * 1000) / num_documents,
            "results_count": len(results),
            "server_available": len(results) > 0 and results[0].get("score", 0) != 0.5
        }
