import os
import logging
import json
from typing import List, Dict, Any
from celery_app import celery_app
from processors.base_processor import BaseProcessor
from processors.docx_processor import DocxProcessor
from processors.csv_processor import CsvProcessor
from processors.json_processor import JsonProcessor
from services.chunking_service import SemanticChunkingService
from services.local_embedding_service import LocalEmbeddingService
from services.database_service import DatabaseService
from services.local_reranking_service import LocalRerankingService
from services.keyword_service import get_keyword_service
from services.search_service import get_search_service
from services.query_expansion_service import get_query_expansion_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ИСПРАВЛЕНИЕ: Используем singleton pattern вместо глобальных None переменных
def get_services():
    """Получить инициализированные сервисы через singleton pattern"""
    chunking_service = SemanticChunkingService()
    embedding_service = LocalEmbeddingService()  # Используем локальный сервис эмбеддингов
    database_service = DatabaseService()
    reranking_service = LocalRerankingService()  # Используем локальный сервис реранжирования
    keyword_service = get_keyword_service()  # Используем singleton
    search_service = get_search_service(database_service, embedding_service, reranking_service)  # ЭТАП 3
    
    return chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service

# Маппинг процессоров по расширениям файлов
PROCESSORS = {
    '.docx': DocxProcessor(),
    '.csv': CsvProcessor(),
    '.json': JsonProcessor(),
}

def get_processor_for_file(file_path: str) -> BaseProcessor:
    """
    Получить подходящий процессор для файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Экземпляр процессора
        
    Raises:
        ValueError: Если расширение файла не поддерживается
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext not in PROCESSORS:
        raise ValueError(f"Unsupported file extension: {file_ext}")
    
    return PROCESSORS[file_ext]

@celery_app.task(bind=True)
def process_document(self, document_id: str, file_path: str, access_level: int, document_title: str = None) -> Dict[str, Any]:
    """
    УЛУЧШЕННЫЙ порядок обработки с семантическим chunking:
    1. Извлечение структурированного содержимого
    2. Анализ структуры документа и извлечение метаданных
    3. Семантическое разбиение на чанки с учетом структуры
    4. Создание расширенных метаданных для КАЖДОГО чанка
    5. Создание эмбеддинга С ПРЕФИКСОМ
    6. Сохранение в ChromaDB и PostgreSQL
    
    Args:
        document_id: ID документа
        file_path: Путь к файлу
        access_level: Уровень доступа (КРИТИЧНО!)
        document_title: Название документа
        
    Returns:
        Результат обработки с расширенными метаданными
    """
    try:
        logger.info(f"Starting enhanced document processing for document_id: {document_id}")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # 1. Извлечение структурированного содержимого
        processor = get_processor_for_file(file_path)
        extraction_result = processor.process_document(file_path, document_id, access_level)
        
        if not extraction_result["success"]:
            raise ValueError(f"Text extraction failed: {extraction_result.get('error', 'Unknown error')}")
        
        text = extraction_result["text"]
        structured_data = extraction_result.get("structured_data", {})
        document_metadata = extraction_result.get("document_metadata", {})
        document_sections = extraction_result.get("document_sections", [])
        
        logger.info(f"Extracted structured content from document {document_id}: "
                   f"text_length={len(text)}, "
                   f"sections={len(document_sections)}, "
                   f"type={document_metadata.get('type', 'unknown')}, "
                   f"tables={extraction_result.get('tables_count', 0)}")
        
        # 2. Получение названия документа из БД для метаданных
        try:
            import psycopg2
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                conn = psycopg2.connect(database_url)
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM documents WHERE id = %s", (document_id,))
                result = cursor.fetchone()
                db_document_title = result[0] if result else document_title or "Неизвестный документ"
                cursor.close()
                conn.close()
            else:
                db_document_title = document_title or "Неизвестный документ"
        except Exception as e:
            logger.warning(f"Could not fetch document title: {str(e)}")
            db_document_title = document_title or "Неизвестный документ"
        
        # Обогащаем метаданные документа
        if not document_metadata.get("title"):
            document_metadata["title"] = db_document_title
        
        # 3. Семантическое разбиение на чанки с учетом структуры
        # Преобразуем document_sections в нужный формат
        from services.document_analyzer import DocumentSection
        sections_objects = []
        for section_data in document_sections:
            section = DocumentSection(
                title=section_data["title"],
                content=section_data["content"],
                level=section_data["level"],
                section_type=section_data["section_type"],
                start_pos=section_data["start_pos"],
                end_pos=section_data["end_pos"],
                metadata=section_data["metadata"]
            )
            sections_objects.append(section)
        
        chunks_data = chunking_service.create_chunks(
            text, 
            document_id, 
            access_level,
            document_sections=sections_objects,
            document_metadata=document_metadata,
            structured_data=structured_data
        )
        
        logger.info(f"Created {len(chunks_data)} semantic chunks for document {document_id}")
        
        # ИСПРАВЛЕНИЕ: Обновляем метаданные чанков с названием документа из БД
        for chunk in chunks_data:
            chunk["metadata"]["doc_title"] = db_document_title
            chunk["metadata"]["document_title"] = db_document_title  # ДОБАВЛЯЕМ для совместимости
            
            # Добавляем информацию о структурированных данных
            if structured_data:
                chunk["metadata"]["has_tables"] = len(structured_data.get("tables", [])) > 0
                chunk["metadata"]["content_parts_count"] = len(structured_data.get("content_parts", []))
        
        # 4. ЭТАП 2: Извлечение ключевых слов для каждого чанка
        logger.info(f"Starting keyword extraction for {len(chunks_data)} chunks")
        all_chunks_keywords = []
        
        for i, chunk in enumerate(chunks_data):
            chunk_keywords = keyword_service.extract_keywords(chunk["text"], chunk_index=i)
            all_chunks_keywords.append(chunk_keywords)
            
            # Обогащаем метаданные чанка ключевыми словами
            chunk["metadata"].update({
                "semantic_keywords": chunk_keywords["semantic_keywords"],
                "technical_keywords": chunk_keywords["technical_keywords"],
                "all_keywords": chunk_keywords["all_keywords"]
            })
        
        # Создаем сводку ключевых слов для всего документа
        document_keywords_summary = keyword_service.get_document_keywords_summary(all_chunks_keywords)
        
        logger.info(f"Keyword extraction completed for document {document_id}: "
                   f"{len(document_keywords_summary['document_semantic_keywords'])} semantic, "
                   f"{len(document_keywords_summary['document_technical_keywords'])} technical keywords")
        
        # 5. Создание эмбеддинга С ПРЕФИКСОМ и метриками
        chunk_texts = [chunk["text"] for chunk in chunks_data]
        embedding_result = embedding_service.generate_batch_embeddings(chunk_texts, is_query=False)
        embeddings = embedding_result["embeddings"]
        embedding_metrics = embedding_result["metrics"]
        
        logger.info(f"Generated {len(embeddings)} embeddings for document {document_id}: "
                   f"{embedding_metrics['embedding_time_ms']:.1f}ms, "
                   f"{embedding_metrics['total_tokens']} tokens")
        
        # 6. Сохранение в ChromaDB и PostgreSQL
        chromadb_result = database_service.save_chunks_to_chromadb(chunks_data, embeddings)
        
        if not chromadb_result["success"]:
            raise ValueError("Failed to save chunks to ChromaDB")
        
        # Сохранение в PostgreSQL
        postgres_result = database_service.save_chunks_to_postgres(chunks_data)
        
        if not postgres_result["success"]:
            raise ValueError(f"Failed to save chunks to PostgreSQL: {postgres_result.get('error', 'Unknown error')}")
        
        # Получение расширенной статистики
        chunking_stats = chunking_service.get_chunking_stats(chunks_data)
        
        result = {
            "success": True,
            "document_id": document_id,
            "text_length": len(text),
            "chunks_created": len(chunks_data),
            "chunks_saved": chromadb_result["chunks_saved"],
            "chunking_stats": chunking_stats,
            "embedding_model": embedding_service.get_model_info(),
            "embedding_metrics": embedding_metrics,
            "document_keywords": document_keywords_summary,
            "keywords_extracted": True,
            
            # Новые метаданные
            "document_metadata": document_metadata,
            "document_sections_count": len(document_sections),
            "structured_data": {
                "tables_count": structured_data.get("tables", []) if structured_data else 0,
                "content_parts_count": len(structured_data.get("content_parts", [])) if structured_data else 0,
                "document_properties": structured_data.get("document_properties", {}) if structured_data else {}
            },
            "processing_type": "semantic_enhanced"
        }
        
        # Обновляем статус документа в PostgreSQL с дополнительными метаданными
        try:
            database_service.update_document_status(document_id, "completed", len(chunks_data))
            logger.info(f"Document status updated to COMPLETED for document_id: {document_id}")
        except Exception as status_error:
            logger.error(f"Failed to update document status: {str(status_error)}")
        
        logger.info(f"Enhanced document processing completed for document_id: {document_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Enhanced document processing failed for document_id: {document_id}, error: {str(exc)}")
        
        # Попытка очистки при ошибке
        try:
            database_service.delete_document_chunks(document_id)
        except:
            pass
        
        self.retry(countdown=60, max_retries=3, exc=exc)

@celery_app.task(bind=True)
def query_knowledge_base(self, query: str, access_level: int, top_k: int = 30) -> Dict[str, Any]:
    """
    Поиск в базе знаний с использованием RAG
    
    Args:
        query: Поисковый запрос
        access_level: Уровень доступа пользователя
        top_k: Количество результатов
        
    Returns:
        Результаты поиска
    """
    try:
        logger.info(f"Starting knowledge base query with access level: {access_level}")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # Генерация эмбеддинга запроса С ПРЕФИКСОМ и метриками
        query_embedding_result = embedding_service.generate_query_embedding(query)
        query_embedding = query_embedding_result["embedding"]
        query_embedding_metrics = query_embedding_result["metrics"]
        
        logger.info(f"Query embedding generated: {query_embedding_metrics['embedding_time_ms']:.1f}ms, "
                   f"{query_embedding_metrics['tokens_in']} tokens")
        
        # Поиск в ChromaDB с фильтрацией по access_level
        search_result = database_service.query_chromadb(query_embedding, access_level, top_k)
        
        if not search_result["success"]:
            raise ValueError("ChromaDB query failed")
        
        results = search_result["results"]
        
        # Форматирование результатов
        formatted_results = []
        if results["documents"] and len(results["documents"]) > 0:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0], 
                results["distances"][0]
            )):
                formatted_results.append({
                    "text": doc,
                    "metadata": metadata,
                    "similarity_score": 1 - distance,  # Конвертация distance в similarity
                    "rank": i + 1
                })
        
        result = {
            "success": True,
            "query": query,
            "access_level": access_level,
            "total_found": len(formatted_results),
            "results": formatted_results,
            "embedding_model": embedding_service.get_model_info(),
            "query_embedding_metrics": query_embedding_metrics
        }
        
        logger.info(f"Knowledge base query completed, found {len(formatted_results)} results")
        return result
        
    except Exception as exc:
        logger.error(f"Knowledge base query failed for query: {query}, error: {str(exc)}")
        self.retry(countdown=30, max_retries=2, exc=exc)

@celery_app.task
def delete_document(document_id: str) -> Dict[str, Any]:
    """
    Удаление документа из ChromaDB
    
    Args:
        document_id: ID документа
        
    Returns:
        Результат операции
    """
    try:
        logger.info(f"Starting document deletion for document_id: {document_id}")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        result = database_service.delete_document_chunks(document_id)
        
        logger.info(f"Document deletion completed for document_id: {document_id}")
        return result
        
    except Exception as e:
        logger.error(f"Document deletion failed for document_id: {document_id}, error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@celery_app.task
def health_check() -> Dict[str, Any]:
    """
    Проверка здоровья worker и всех сервисов
    
    Returns:
        Статус здоровья
    """
    try:
        # ИСПРАВЛЕНИЕ: Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # Проверка ChromaDB
        chromadb_status = database_service.health_check()
        
        # Проверка модели эмбеддингов
        embedding_info = embedding_service.get_model_info()
        
        # НОВОЕ: Проверка сервиса ключевых слов
        keyword_health = keyword_service.health_check()
        
        # Статистика коллекции
        collection_stats = database_service.get_collection_stats()
        
        return {
            "status": "healthy",
            "worker": "knowledge_base_worker",
            "chromadb": chromadb_status,
            "embedding_service": {
                "status": "healthy",
                "model_info": embedding_info
            },
            "keyword_service": keyword_health,
            "collection_stats": collection_stats,
            "supported_extensions": list(PROCESSORS.keys())
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@celery_app.task(bind=True)
def rag_query(self, query: str, access_level: int, chat_context: str = None) -> Dict[str, Any]:
    """
    RAG Pipeline согласно требованиям:
    1. Query → Embedding (multilingual-e5-large) с контекстом чата
    2. ChromaDB search (top 30)
    3. Filter by access_level
    4. Rerank with cross-encoder (top 10)
    5. Build context with metadata
    
    Args:
        query: Поисковый запрос
        access_level: Уровень доступа пользователя (КРИТИЧНО!)
        chat_context: Контекст предыдущего диалога для улучшения поиска
        
    Returns:
        Контекст для отправки в Ollama
    """
    try:
        logger.info(f"Starting RAG query processing: {query[:100]}...")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # 1. Query → Embedding (multilingual-e5-large-instruct) БЕЗ контекста чата
        # ИСПРАВЛЕНИЕ: Контекст чата НЕ добавляем к embedding (может ухудшить поиск)
        # Вместо этого используем контекст для понижения порогов релевантности
        
        query_embedding_result = embedding_service.generate_query_embedding(query)
        query_embedding = query_embedding_result["embedding"]
        query_embedding_metrics = query_embedding_result["metrics"]
        
        logger.info(f"Query embedding generated: {query_embedding_metrics['embedding_time_ms']:.1f}ms, "
                   f"{query_embedding_metrics['tokens_in']} tokens, instruct format: {query_embedding_metrics['instruct_format']}, "
                   f"has_chat_context: {bool(chat_context)}")
        
        # 2. ChromaDB search (top 30) + 3. Filter by access_level
        search_result = database_service.query_chromadb(
            query_embedding, 
            access_level, 
            top_k=30  # КОНСТАНТА согласно требованиям
        )
        
        if not search_result["success"]:
            raise ValueError("ChromaDB query failed")
        
        results = search_result["results"]
        search_time_ms = search_result.get("search_time_ms", 0)
        
        logger.info(f"ChromaDB search completed in {search_time_ms:.1f}ms")
        
        if not results["documents"] or len(results["documents"][0]) == 0:
            logger.warning(f"No documents found for access level {access_level}")
            return {
                "success": True,
                "context": "",
                "sources": [],
                "total_found": 0,
                "access_level": access_level
            }
        
        # Подготовка документов для реранжирования
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]
        
        logger.info(f"Found {len(documents)} documents from ChromaDB")
        
        # 4. Rerank with cross-encoder (top 10)
        reranked_results = reranking_service.rerank_results(
            query, 
            documents, 
            top_k=10  # КОНСТАНТА согласно требованиям
        )
        
        logger.info(f"Reranked to top {len(reranked_results)} results")
        
        # УБИРАЕМ ДВОЙНУЮ ФИЛЬТРАЦИЮ: теперь фильтрация происходит только в SearchService
        # Используем все результаты реранжирования без дополнительной фильтрации
        if not reranked_results:
            logger.info("No reranked results found")
            return {
                "success": True,
                "context": "",
                "sources": [],
                "total_found": len(documents),
                "reranked_count": 0,
                "access_level": access_level,
                "relevance_filtered": True,
                "reason": "No results after reranking"
            }
        
        # Используем все результаты реранжирования (фильтрация уже произошла в reranking_service)
        filtered_results = reranked_results
        best_score = reranked_results[0]["score"] if reranked_results else 0
        
        logger.info(f"Using {len(filtered_results)} reranked results (best score: {best_score:.3f})")
        
        # 5. Build context with metadata (только для релевантных результатов)
        context_parts = []
        sources = []
        
        for i, rerank_result in enumerate(filtered_results):
            original_index = rerank_result["index"]
            metadata = metadatas[original_index]
            document_text = rerank_result["document"]
            
            # Формирование источника
            source_info = {
                "chunk_id": f"{metadata.get('doc_id', 'unknown')}_{metadata.get('chunk_index', i)}",
                "document_title": metadata.get("doc_title", "Неизвестный документ"),
                "chunk_index": metadata.get("chunk_index", i),
                "access_level": metadata.get("access_level", access_level),
                "similarity_score": 1 - distances[original_index],
                "rerank_score": rerank_result["score"],
                "text": document_text  # ИСПРАВЛЕНО: Не обрезаем текст источника
            }
            sources.append(source_info)
            
            # Формирование контекста с названием документа для промпта
            doc_title = source_info['document_title']
            context_part = f"[Источник {i + 1}: {doc_title}]\n{document_text}\n"
            context_parts.append(context_part)
        
        context = "\n".join(context_parts)
        
        result = {
            "success": True,
            "query": query,
            "context": context,
            "sources": sources,
            "total_found": len(documents),
            "reranked_count": len(reranked_results),
            "filtered_count": len(filtered_results),
            "access_level": access_level,
            "best_relevance_score": best_score,
            "relevance_filtered": False,
            "embedding_model": embedding_service.get_model_info(),
            "reranking_model": reranking_service.get_model_info(),
            "query_embedding_metrics": query_embedding_metrics,
            "search_time_ms": search_time_ms
        }
        
        logger.info(f"RAG query processing completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"RAG query processing failed: {str(exc)}")
        self.retry(countdown=30, max_retries=2, exc=exc)

@celery_app.task
def generate_query_embedding_task(query: str) -> Dict[str, Any]:
    """
    Генерация эмбеддинга для запроса
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Эмбеддинг запроса
    """
    try:
        # ИСПРАВЛЕНИЕ: Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        embedding_result = embedding_service.generate_query_embedding(query)
        
        return {
            "success": True,
            "embedding": embedding_result["embedding"],
            "query": query,
            "model_info": embedding_service.get_model_info(),
            "metrics": embedding_result["metrics"]
        }
        
    except Exception as e:
        logger.error(f"Error generating query embedding: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@celery_app.task
def rerank_documents_task(query: str, documents: List[str], top_k: int = 10) -> Dict[str, Any]:
    """
    Реранжирование документов
    
    Args:
        query: Поисковый запрос
        documents: Список документов
        top_k: Количество топ результатов
        
    Returns:
        Реранжированные результаты
    """
    try:
        # ИСПРАВЛЕНИЕ: Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service = get_services()
        
        results = reranking_service.rerank_results(query, documents, top_k)
        
        return {
            "success": True,
            "results": results,
            "query": query,
            "total_documents": len(documents),
            "returned_count": len(results),
            "model_info": reranking_service.get_model_info()
        }
        
    except Exception as e:
        logger.error(f"Error reranking documents: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@celery_app.task(bind=True)
def extract_keywords_for_existing_chunks(self, document_id: str = None) -> Dict[str, Any]:
    """
    ЭТАП 2: Извлечение ключевых слов для существующих чанков в ChromaDB и PostgreSQL.
    Используется для обновления старых документов новой функциональностью.
    
    Args:
        document_id: ID конкретного документа (опционально, если None - обрабатываются все)
        
    Returns:
        Результат обработки
    """
    try:
        logger.info(f"Starting keyword extraction for existing chunks, document_id: {document_id}")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service = get_services()
        
        # Получаем чанки из ChromaDB
        if document_id:
            # Для конкретного документа
            filter_condition = {"doc_id": document_id}
        else:
            # Для всех документов без ключевых слов
            filter_condition = {}
        
        # Получаем все чанки
        collection = database_service.get_collection()
        all_chunks = collection.get(
            where=filter_condition,
            include=["documents", "metadatas"]
        )
        
        if not all_chunks["documents"]:
            logger.info("No chunks found for keyword extraction")
            return {
                "success": True,
                "processed_chunks": 0,
                "message": "No chunks found"
            }
        
        processed_count = 0
        postgres_updates = []
        
        # Обрабатываем каждый чанк
        for i, (chunk_id, document_text, metadata) in enumerate(zip(
            all_chunks["ids"],
            all_chunks["documents"], 
            all_chunks["metadatas"]
        )):
            # Проверяем, есть ли уже ключевые слова
            if metadata.get("all_keywords"):
                logger.debug(f"Chunk {chunk_id} already has keywords, skipping")
                continue
            
            # Извлекаем ключевые слова
            chunk_keywords = keyword_service.extract_keywords(document_text, chunk_index=i)
            
            # Обновляем метаданные
            updated_metadata = metadata.copy()
            updated_metadata.update({
                "semantic_keywords": chunk_keywords["semantic_keywords"],
                "technical_keywords": chunk_keywords["technical_keywords"],
                "all_keywords": chunk_keywords["all_keywords"]
            })
            
            # Обновляем чанк в ChromaDB
            collection.update(
                ids=[chunk_id],
                metadatas=[updated_metadata]
            )
            
            # ЭТАП 2: Подготавливаем данные для обновления PostgreSQL
            postgres_updates.append((
                json.dumps(updated_metadata),  # Новые метаданные с ключевыми словами
                chunk_id  # ID чанка для WHERE условия
            ))
            
            processed_count += 1
            
            if processed_count % 10 == 0:
                logger.info(f"Processed {processed_count} chunks for keyword extraction")
        
        # ЭТАП 2: Массовое обновление PostgreSQL с ключевыми словами
        if postgres_updates:
            try:
                import psycopg2
                database_url = os.getenv('DATABASE_URL')
                if database_url:
                    conn = psycopg2.connect(database_url)
                    cursor = conn.cursor()
                    
                    # Массовое обновление метаданных в PostgreSQL
                    cursor.executemany(
                        "UPDATE chunks SET metadata = %s WHERE id = %s",
                        postgres_updates
                    )
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    logger.info(f"Updated {len(postgres_updates)} chunks in PostgreSQL with keywords")
                else:
                    logger.warning("DATABASE_URL not found, skipping PostgreSQL update")
            except Exception as postgres_error:
                logger.error(f"Error updating PostgreSQL with keywords: {str(postgres_error)}")
                # Не прерываем выполнение, так как ChromaDB уже обновлен
        
        result = {
            "success": True,
            "document_id": document_id,
            "total_chunks": len(all_chunks["documents"]),
            "processed_chunks": processed_count,
            "skipped_chunks": len(all_chunks["documents"]) - processed_count,
            "postgres_updated": len(postgres_updates)
        }
        
        logger.info(f"Keyword extraction completed for existing chunks: {processed_count} processed, {len(postgres_updates)} updated in PostgreSQL")
        return result
        
    except Exception as exc:
        logger.error(f"Keyword extraction for existing chunks failed: {str(exc)}")
        self.retry(countdown=60, max_retries=2, exc=exc)

@celery_app.task(bind=True)
def hybrid_search(
    self, 
    query: str, 
    access_level: int, 
    top_k: int = 30,
    rerank_top_k: int = 10,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> Dict[str, Any]:
    """
    ЭТАП 3: Гибридный поиск с векторным поиском + BM25 + RRF fusion
    
    Args:
        query: Поисковый запрос
        access_level: Уровень доступа пользователя
        top_k: Количество результатов для каждого метода
        rerank_top_k: Финальное количество результатов
        vector_weight: Вес векторного поиска (70%)
        bm25_weight: Вес BM25 поиска (30%)
        
    Returns:
        Результаты гибридного поиска
    """
    try:
        logger.info(f"Starting hybrid search: '{query[:100]}...'")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # Выполняем гибридный поиск
        result = search_service.hybrid_search(
            query, 
            access_level, 
            top_k, 
            rerank_top_k, 
            vector_weight, 
            bm25_weight
        )
        
        # КРИТИЧНО: УБИРАЕМ СТАРУЮ ФИЛЬТРАЦИЮ - теперь SearchService сам фильтрует адаптивно
        # SearchService уже применяет адаптивные пороги на шкале 0-10 с экспоненциальным усилением
        
        if result["success"] and result.get("results"):
            reranked_results = result["results"]
            
            # Формируем контекст только из результатов, которые прошли фильтрацию в SearchService
            context_parts = []
            sources = []
            
            for i, search_result in enumerate(reranked_results):
                metadata = search_result.get("metadata", {})
                
                # Формирование источника
                source_info = {
                    "chunk_id": search_result.get("id"),
                    "document_title": metadata.get("doc_title", "Неизвестный документ"),
                    "chunk_index": metadata.get("chunk_index", i),
                    "access_level": metadata.get("access_level", access_level),
                    "similarity_score": search_result.get("score", 0),
                    "rerank_score": search_result.get("rerank_score", 0),
                    "text": search_result.get("content", "")
                }
                sources.append(source_info)
                
                # Формирование контекста
                doc_title = source_info['document_title']
                context_part = f"[Источник {i + 1}: {doc_title}]\n{source_info['text']}\n"
                context_parts.append(context_part)
            
            context = "\n".join(context_parts)
            
            # Обновляем результат с контекстом и источниками
            result.update({
                "context": context,
                "sources": sources,
                "filtered_count": len(reranked_results),
                "access_level": access_level,
                "best_relevance_score": reranked_results[0].get("rerank_score", 0) if reranked_results else 0,
                "relevance_filtered": len(reranked_results) == 0,
                "reason": "Results processed by adaptive filtering in SearchService"
            })
        else:
            # Если нет результатов от SearchService - значит все отфильтровано
            result.update({
                "context": "",
                "sources": [],
                "filtered_count": 0,
                "access_level": access_level,
                "relevance_filtered": True,
                "reason": "All results filtered by SearchService adaptive thresholds"
            })
        
        logger.info(f"Hybrid search completed successfully with relevance filtering")
        return result
        
    except Exception as exc:
        logger.error(f"Hybrid search failed: {str(exc)}")
        self.retry(countdown=30, max_retries=2, exc=exc)

@celery_app.task(bind=True)
def batch_hybrid_search(
    self,
    queries: List[str],
    access_level: int,
    top_k: int = 30,
    rerank_top_k: int = 10,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> Dict[str, Any]:
    """
    T1.6: Batch гибридный поиск для множественных запросов
    
    Args:
        queries: Список поисковых запросов
        access_level: Уровень доступа пользователя
        top_k: Количество результатов для каждого метода
        rerank_top_k: Финальное количество результатов
        vector_weight: Вес векторного поиска (70%)
        bm25_weight: Вес BM25 поиска (30%)
        
    Returns:
        Результаты batch поиска
    """
    try:
        logger.info(f"Starting batch hybrid search for {len(queries)} queries")
        
        # Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        # Выполняем batch гибридный поиск
        result = search_service.batch_hybrid_search(
            queries,
            access_level,
            top_k,
            rerank_top_k,
            vector_weight,
            bm25_weight
        )
        
        logger.info(f"Batch hybrid search completed successfully: {result['processed_queries']} queries, {result['cache_hits']} cache hits")
        return result
        
    except Exception as exc:
        logger.error(f"Batch hybrid search failed: {str(exc)}")
        self.retry(countdown=30, max_retries=2, exc=exc)

@celery_app.task
def get_processing_stats() -> Dict[str, Any]:
    """
    Получение статистики обработки документов
    
    Returns:
        Статистика
    """
    try:
        # ИСПРАВЛЕНИЕ: Получаем инициализированные сервисы
        chunking_service, embedding_service, database_service, reranking_service, keyword_service, search_service = get_services()
        
        collection_stats = database_service.get_collection_stats()
        embedding_info = embedding_service.get_model_info()
        reranking_info = reranking_service.get_model_info()
        keyword_info = keyword_service.get_model_info()
        search_stats = search_service.get_search_stats()
        
        return {
            "collection_stats": collection_stats,
            "embedding_model": embedding_info,
            "reranking_model": reranking_info,
            "keyword_service": keyword_info,
            "search_service": search_stats,
            "supported_processors": {
                ext: processor.__class__.__name__ 
                for ext, processor in PROCESSORS.items()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting processing stats: {str(e)}")
        return {
            "error": str(e)
        }
