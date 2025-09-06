import os
import chromadb
import psycopg2
import json
import time
from typing import List, Dict, Any, Optional
import logging
from .connection_pool import get_chromadb_pool, PooledChromaDBClient

logger = logging.getLogger(__name__)

class ChromaDBConfig:
    """Конфигурация ChromaDB согласно требованиям"""
    COLLECTION_NAME = "documents"
    DISTANCE_METRIC = "cosine"  # НЕ МЕНЯТЬ!
    
    # T1.1: HNSW параметры для оптимизации векторного поиска
    HNSW_CONFIG = {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,    # Качество построения индекса
        "hnsw:search_ef": 100,          # Скорость поиска
        "hnsw:M": 16                    # Связность графа
    }

class DatabaseService:
    """
    Сервис для работы с ChromaDB с connection pooling
    T1.5: Добавлен connection pooling для ChromaDB
    """
    
    def __init__(self):
        self.config = ChromaDBConfig()
        self.logger = logger
        
        # T1.5: Инициализация connection pool
        self.chromadb_pool = get_chromadb_pool()
        
        # Получаем коллекцию через пул для инициализации
        self._ensure_collection()
        
        self.logger.info("DatabaseService инициализирован с connection pooling")
    
    def _ensure_collection(self):
        """Убедиться, что коллекция существует и доступна"""
        try:
            # T1.5: Используем пул соединений
            # T1.1: Добавлены HNSW параметры для оптимизации
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if client:
                    client.get_or_create_collection(
                        name=self.config.COLLECTION_NAME,
                        metadata=self.config.HNSW_CONFIG
                    )
                    self.logger.info(f"Collection '{self.config.COLLECTION_NAME}' ensured with HNSW optimization")
                else:
                    raise Exception("Cannot get ChromaDB client from pool")
                    
        except Exception as e:
            self.logger.error(f"Error ensuring collection: {str(e)}")
            raise e

    def save_chunks_to_chromadb(self, chunks_data: List[Dict[str, Any]], embeddings: List[Any]) -> Dict[str, Any]:
        """
        Сохранение чанков в ChromaDB с connection pooling
        T1.5: Обновлено для использования пула соединений
        
        Args:
            chunks_data: Список чанков с метаданными
            embeddings: Список эмбеддингов
            
        Returns:
            Результат операции
        """
        try:
            if len(chunks_data) != len(embeddings):
                raise ValueError("Number of chunks and embeddings must match")
            
            ids = []
            documents = []
            metadatas = []
            embeddings_list = []
            
            for i, (chunk_data, embedding) in enumerate(zip(chunks_data, embeddings)):
                # Создание ID согласно требованиям: f"{doc_id}_{i}"
                chunk_id = f"{chunk_data['metadata']['doc_id']}_{i}"
                ids.append(chunk_id)
                
                # Текст документа
                documents.append(chunk_data['text'])
                
                # ИСПРАВЛЕНИЕ: Конвертируем списки в строки для ChromaDB
                metadata = chunk_data['metadata'].copy()
                
                # ChromaDB не поддерживает списки в метаданных - конвертируем в строки
                if 'semantic_keywords' in metadata and isinstance(metadata['semantic_keywords'], list):
                    metadata['semantic_keywords'] = ','.join(metadata['semantic_keywords'])
                
                if 'technical_keywords' in metadata and isinstance(metadata['technical_keywords'], list):
                    metadata['technical_keywords'] = ','.join(metadata['technical_keywords'])
                
                if 'all_keywords' in metadata and isinstance(metadata['all_keywords'], list):
                    metadata['all_keywords'] = ','.join(metadata['all_keywords'])
                
                metadatas.append(metadata)
                
                # Эмбеддинг (уже нормализованный)
                embeddings_list.append(embedding.tolist() if hasattr(embedding, 'tolist') else embedding)
            
            # T1.5: Используем пул соединений для сохранения
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if not client:
                    raise Exception("Cannot get ChromaDB client from pool")
                
                collection = client.get_or_create_collection(
                    name=self.config.COLLECTION_NAME,
                    metadata=self.config.HNSW_CONFIG
                )
                
                collection.add(
                    ids=ids,
                    embeddings=embeddings_list,
                    documents=documents,
                    metadatas=metadatas
                )
            
            self.logger.info(f"Saved {len(chunks_data)} chunks to ChromaDB via pool")
            
            return {
                "success": True,
                "chunks_saved": len(chunks_data),
                "collection_name": self.config.COLLECTION_NAME
            }
            
        except Exception as e:
            self.logger.error(f"Error saving chunks to ChromaDB: {str(e)}")
            raise e
    
    def save_chunks_to_postgres(self, chunks_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        ЭТАП 2: Сохранение чанков в PostgreSQL с ключевыми словами
        
        Args:
            chunks_data: Список чанков с метаданными (включая ключевые слова)
            
        Returns:
            Результат операции
        """
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL not found in environment")
            
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            
            # Подготовка данных для вставки с ключевыми словами
            insert_data = []
            for i, chunk_data in enumerate(chunks_data):
                chunk_id = f"{chunk_data['metadata']['doc_id']}_{i}"
                
                # КРИТИЧНО: Включаем ключевые слова в метаданные PostgreSQL
                metadata_with_keywords = chunk_data['metadata'].copy()
                
                # Убеждаемся, что ключевые слова включены в метаданные
                if 'semantic_keywords' in metadata_with_keywords:
                    self.logger.debug(f"Chunk {chunk_id} has {len(metadata_with_keywords.get('semantic_keywords', []))} semantic keywords")
                
                insert_data.append((
                    chunk_id,
                    chunk_data['metadata']['doc_id'],
                    chunk_data['metadata']['chunk_index'],
                    chunk_data['text'],
                    chunk_data['metadata']['access_level'],
                    len(chunk_data['text']),
                    json.dumps(metadata_with_keywords)  # Включает ключевые слова
                ))
            
            # Массовая вставка чанков с ключевыми словами
            cursor.executemany(
                """
                INSERT INTO chunks (id, document_id, chunk_index, content, access_level, char_count, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    access_level = EXCLUDED.access_level,
                    char_count = EXCLUDED.char_count,
                    metadata = EXCLUDED.metadata
                """,
                insert_data
            )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Saved {len(chunks_data)} chunks with keywords to PostgreSQL")
            
            return {
                "success": True,
                "chunks_saved": len(chunks_data),
                "keywords_included": True
            }
            
        except Exception as e:
            self.logger.error(f"Error saving chunks to PostgreSQL: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def query_chromadb(self, query_embedding: Any, access_level: int, top_k: int = 30) -> Dict[str, Any]:
        """
        Поиск в ChromaDB с фильтрацией по уровню доступа и метриками времени
        T1.5: Обновлено для использования connection pooling
        
        Args:
            query_embedding: Эмбеддинг запроса
            access_level: Уровень доступа пользователя
            top_k: Количество результатов
            
        Returns:
            Результаты поиска с метриками времени
        """
        start_time = time.time()
        
        try:
            # T1.5: Используем пул соединений для поиска
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if not client:
                    raise Exception("Cannot get ChromaDB client from pool")
                
                collection = client.get_or_create_collection(
                    name=self.config.COLLECTION_NAME,
                    metadata=self.config.HNSW_CONFIG
                )
                
                # В КАЖДОМ запросе к ChromaDB проверяем access_level
                results = collection.query(
                    query_embeddings=[query_embedding.tolist() if hasattr(query_embedding, 'tolist') else query_embedding],
                    n_results=top_k,
                    where={"access_level": {"$lte": access_level}}  # КРИТИЧНО!
                )
            
            search_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            self.logger.info(f"Found {len(results['documents'][0])} results for access level {access_level} in {search_time:.1f}ms")
            
            return {
                "success": True,
                "results": results,
                "total_found": len(results['documents'][0]),
                "search_time_ms": search_time
            }
            
        except Exception as e:
            self.logger.error(f"Error querying ChromaDB: {str(e)}")
            raise e
    
    def delete_document_chunks(self, doc_id: str) -> Dict[str, Any]:
        """
        Удаление всех чанков документа из ChromaDB
        T1.5: Обновлено для использования connection pooling
        
        Args:
            doc_id: ID документа
            
        Returns:
            Результат операции
        """
        try:
            # T1.5: Используем пул соединений для удаления
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if not client:
                    raise Exception("Cannot get ChromaDB client from pool")
                
                collection = client.get_or_create_collection(
                    name=self.config.COLLECTION_NAME,
                    metadata=self.config.HNSW_CONFIG
                )
                
                # Поиск всех чанков документа
                results = collection.get(
                    where={"doc_id": doc_id}
                )
                
                if results['ids']:
                    # Удаление чанков
                    collection.delete(ids=results['ids'])
                    
                    self.logger.info(f"Deleted {len(results['ids'])} chunks for document {doc_id}")
                    
                    return {
                        "success": True,
                        "chunks_deleted": len(results['ids'])
                    }
                else:
                    self.logger.info(f"No chunks found for document {doc_id}")
                    return {
                        "success": True,
                        "chunks_deleted": 0
                    }
                
        except Exception as e:
            self.logger.error(f"Error deleting document chunks: {str(e)}")
            raise e
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Получение статистики коллекции
        T1.5: Обновлено для использования connection pooling
        
        Returns:
            Статистика коллекции
        """
        try:
            # T1.5: Используем пул соединений для получения статистики
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if not client:
                    raise Exception("Cannot get ChromaDB client from pool")
                
                collection = client.get_or_create_collection(
                    name=self.config.COLLECTION_NAME,
                    metadata=self.config.HNSW_CONFIG
                )
                
                count = collection.count()
            
            return {
                "collection_name": self.config.COLLECTION_NAME,
                "total_chunks": count,
                "distance_metric": self.config.DISTANCE_METRIC
            }
            
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            raise e
    
    def get_collection(self):
        """
        Получить объект коллекции ChromaDB через пул соединений
        T1.5: Обновлено для работы с connection pooling
        
        Returns:
            Объект коллекции
        """
        # T1.5: Используем пул соединений для получения коллекции
        with PooledChromaDBClient(self.chromadb_pool) as client:
            if not client:
                raise Exception("Cannot get ChromaDB client from pool")
            
            return client.get_or_create_collection(
                name=self.config.COLLECTION_NAME,
                metadata=self.config.HNSW_CONFIG
            )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья соединения с ChromaDB
        T1.5: Обновлено для использования connection pooling
        
        Returns:
            Статус соединения
        """
        try:
            # T1.5: Используем пул соединений для health check
            with PooledChromaDBClient(self.chromadb_pool) as client:
                if not client:
                    raise Exception("Cannot get ChromaDB client from pool")
                
                # Простой запрос для проверки соединения
                client.heartbeat()
                
                collection = client.get_or_create_collection(
                    name=self.config.COLLECTION_NAME,
                    metadata=self.config.HNSW_CONFIG
                )
                
                total_chunks = collection.count()
            
            return {
                "status": "healthy",
                "collection_name": self.config.COLLECTION_NAME,
                "total_chunks": total_chunks
            }
            
        except Exception as e:
            self.logger.error(f"ChromaDB health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def update_document_status(self, document_id: str, status: str, chunk_count: int = None) -> Dict[str, Any]:
        """
        Обновление статуса документа в PostgreSQL
        
        Args:
            document_id: ID документа
            status: Новый статус (PROCESSING, COMPLETED, ERROR)
            chunk_count: Количество чанков (опционально)
            
        Returns:
            Результат операции
        """
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL not found in environment")
            
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            
            # Обновляем статус документа
            if chunk_count is not None:
                cursor.execute(
                    """
                    UPDATE documents 
                    SET status = %s, processed = true, processed_at = NOW(), chunk_count = %s 
                    WHERE id = %s
                    """,
                    (status, chunk_count, document_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE documents 
                    SET status = %s, processed = true, processed_at = NOW() 
                    WHERE id = %s
                    """,
                    (status, document_id)
                )
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Updated document {document_id} status to {status}")
            
            return {
                "success": True,
                "document_id": document_id,
                "status": status,
                "chunk_count": chunk_count
            }
            
        except Exception as e:
            self.logger.error(f"Error updating document status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
