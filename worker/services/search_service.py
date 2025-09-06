"""
Сервис гибридного поиска: векторный поиск + BM25 + RRF fusion
ЭТАП 3: Внедрение гибридного поиска согласно требованиям
T1.4: Добавлено кэширование поисковых запросов
"""

import time
import logging
import re
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
import structlog
import pymorphy3
from .cache_service import get_cache_service
from .query_expansion_service import get_query_expansion_service

logger = structlog.get_logger(__name__)

class SearchService:
    """
    Сервис гибридного поиска с векторным поиском и BM25
    """
    
    def __init__(self, database_service, embedding_service, reranking_service):
        """
        Инициализация сервиса поиска
        
        Args:
            database_service: Сервис для работы с ChromaDB
            embedding_service: Сервис эмбеддингов
            reranking_service: Сервис реранжирования
        """
        self.database_service = database_service
        self.embedding_service = embedding_service
        self.reranking_service = reranking_service
        self.collection = database_service.get_collection()
        
        # T1.4: Инициализация кэш-сервиса
        self.cache_service = get_cache_service()
        
        # R5.5: Инициализация сервиса расширения запросов
        self.query_expansion_service = get_query_expansion_service()
        
        # R5.4: Инициализация морфологического анализатора
        self.morph = pymorphy3.MorphAnalyzer()
        
        # BM25 будет инициализирован при первом использовании
        self.bm25 = None
        self.bm25_docs = None
        self.bm25_ids = None
        self.bm25_metadatas = None
        self._bm25_initialized = False
        
        logger.info("SearchService инициализирован с кэшированием, расширением запросов и морфологическим анализом")
    
    def _improved_tokenize(self, text: str) -> List[str]:
        """
        R5.4: Правильная токенизация для русского языка с pymorphy2
        
        Args:
            text: Текст для токенизации
            
        Returns:
            Список лемматизированных токенов
        """
        try:
            # Русские стоп-слова (лемматизированные)
            russian_stop_words = {
                'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'её', 'мне', 'быть', 'вот', 'от', 'меня', 'ещё', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или', 'ни', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничто', 'ей', 'мочь', 'они', 'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'сам', 'чтобы', 'без', 'будто', 'чего', 'раз', 'тоже', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'тот', 'потому', 'какой', 'совсем', 'здесь', 'один', 'почти', 'мой', 'тем', 'сейчас', 'куда', 'зачем', 'весь', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть', 'после', 'над', 'большой', 'через', 'этот', 'наш', 'про', 'весь', 'какой', 'много', 'разве', 'три', 'мой', 'впрочем', 'хороший', 'свой', 'перед', 'иногда', 'лучше', 'чуть', 'нельзя', 'такой', 'более', 'всегда', 'конечно', 'между'
            }
            
            # Приводим к нижнему регистру
            text = text.lower()
            
            # Сохраняем важные числа и даты (не нормализуем годы)
            # Нормализуем только общие числа, но сохраняем годы
            text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', 'DATE', text)  # Даты YYYY-MM-DD
            text = re.sub(r'\b\d{2}\.\d{2}\.\d{4}\b', 'DATE', text)  # Даты DD.MM.YYYY
            text = re.sub(r'\b(?!(?:19|20)\d{2}\b)\d+\.\d+\b', 'NUMBER', text)  # Десятичные числа (кроме годов)
            
            # Правильная токенизация с дефисами и составными словами
            tokens = re.findall(r'[\w-]+', text)
            
            # Лемматизация и фильтрация
            lemmatized_tokens = []
            for token in tokens:
                # Пропускаем слишком короткие токены
                if len(token) < 2:
                    continue
                
                # Обрабатываем составные слова с дефисом
                if '-' in token and len(token) > 3:
                    # Разбиваем составное слово и лемматизируем каждую часть
                    parts = token.split('-')
                    for part in parts:
                        if len(part) >= 2:
                            parsed = self.morph.parse(part)[0]
                            lemma = parsed.normal_form
                            if lemma not in russian_stop_words and not lemma.isdigit():
                                lemmatized_tokens.append(lemma)
                else:
                    # Лемматизация обычных слов
                    parsed = self.morph.parse(token)[0]
                    lemma = parsed.normal_form
                    
                    # Пропускаем стоп-слова и чисто цифровые токены
                    if lemma not in russian_stop_words and not lemma.isdigit():
                        # Сохраняем важные токены как есть
                        if token in ['DATE', 'NUMBER'] or re.match(r'^\d{4}$', token):  # Годы
                            lemmatized_tokens.append(token)
                        else:
                            lemmatized_tokens.append(lemma)
            
            return lemmatized_tokens
            
        except Exception as e:
            logger.error("Ошибка морфологической токенизации", error=str(e))
            # Fallback к простой токенизации
            return [token for token in text.lower().split() if len(token) > 2]
    
    def _ensure_bm25_initialized(self, access_level: int):
        """
        Ленивая инициализация BM25 индекса с кэшированием
        T1.3: Добавлено кэширование BM25 индекса в Redis
        
        Args:
            access_level: Уровень доступа пользователя
        """
        try:
            if self._bm25_initialized:
                return
            
            logger.info(f"Инициализация BM25 индекса для access_level <= {access_level}")
            start_time = time.time()
            
            # T1.3: Проверяем кэш перед созданием индекса
            cached_bm25 = self.cache_service.get_cached_bm25_index(access_level)
            
            if cached_bm25:
                # Восстанавливаем из кэша
                self.bm25 = cached_bm25.get('bm25_index')
                self.bm25_docs = cached_bm25.get('docs', [])
                self.bm25_metadatas = cached_bm25.get('metadatas', [])
                self.bm25_ids = cached_bm25.get('ids', [])
                
                cache_time = (time.time() - start_time) * 1000
                self._bm25_initialized = True
                
                logger.info(f"BM25 индекс загружен из кэша за {cache_time:.1f}ms для {len(self.bm25_docs)} документов")
                return
            
            # Создаём индекс с нуля
            # Получаем все документы с фильтрацией по access_level
            all_docs = self.collection.get(
                where={"access_level": {"$lte": access_level}},
                include=['documents', 'metadatas']
            )
            
            if not all_docs['documents']:
                logger.warning("Нет документов для инициализации BM25")
                self.bm25 = None
                return
            
            # R5.4: Токенизация документов для BM25 с улучшенной обработкой
            tokenized_docs = []
            for doc in all_docs['documents']:
                # Используем улучшенную токенизацию
                tokens = self._improved_tokenize(doc)
                tokenized_docs.append(tokens)
            
            # Создание BM25 индекса
            self.bm25 = BM25Okapi(tokenized_docs)
            self.bm25_docs = all_docs['documents']
            self.bm25_metadatas = all_docs['metadatas']
            
            # Генерируем IDs на основе метаданных
            self.bm25_ids = []
            for i, metadata in enumerate(self.bm25_metadatas):
                doc_id = metadata.get('doc_id', f'unknown_{i}')
                chunk_index = metadata.get('chunk_index', i)
                self.bm25_ids.append(f"{doc_id}_{chunk_index}")
            
            init_time = (time.time() - start_time) * 1000
            
            # T1.3: Кэшируем созданный индекс
            bm25_cache_data = {
                'bm25_index': self.bm25,
                'docs': self.bm25_docs,
                'metadatas': self.bm25_metadatas,
                'ids': self.bm25_ids,
                'access_level': access_level,
                'created_at': time.time()
            }
            
            self.cache_service.cache_bm25_index(access_level, bm25_cache_data)
            
            self._bm25_initialized = True
            logger.info(f"BM25 индекс создан и закэширован за {init_time:.1f}ms для {len(tokenized_docs)} документов")
            
        except Exception as e:
            logger.error("ОШИБКА инициализации BM25", error=str(e))
            self.bm25 = None
    
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
        T1.4: Добавлено кэширование результатов поиска
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа пользователя
            top_k: Количество результатов для каждого метода
            rerank_top_k: Финальное количество результатов после реранжирования
            vector_weight: Вес векторного поиска (по умолчанию 70%)
            bm25_weight: Вес BM25 поиска (по умолчанию 30%)
            
        Returns:
            Результаты гибридного поиска
        """
        start_time = time.time()
        
        try:
            logger.info(f"Начинаем гибридный поиск: '{query[:100]}...'")
            
            # T1.4: Проверяем кэш перед выполнением поиска
            search_params = {
                "top_k": top_k,
                "rerank_top_k": rerank_top_k,
                "vector_weight": vector_weight,
                "bm25_weight": bm25_weight
            }
            
            cached_result = self.cache_service.get_cached_search_results(
                query, access_level, search_params
            )
            
            if cached_result:
                cache_time = (time.time() - start_time) * 1000
                logger.info(f"Возвращаем результат из кэша за {cache_time:.1f}ms")
                return cached_result
            
            # Инициализируем BM25 если нужно
            self._ensure_bm25_initialized(access_level)
            
            # 1. Векторный поиск (семантический) с метриками
            vector_results, embedding_metrics = self._vector_search(query, access_level, top_k)
            
            # 2. BM25 поиск (лексический)
            bm25_results = self._bm25_search(query, access_level, top_k)
            
            # 3. Reciprocal Rank Fusion (RRF)
            fused_results = self._rrf_fusion(
                vector_results, 
                bm25_results, 
                vector_weight, 
                bm25_weight
            )
            
            # 4. Реранжирование топ результатов
            if len(fused_results) > 0 and rerank_top_k > 0:
                reranked_results = self._rerank_results(query, fused_results, rerank_top_k)
            else:
                reranked_results = fused_results[:rerank_top_k]
            
            search_time = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "query": query,
                "access_level": access_level,
                "search_method": "hybrid",
                "vector_results_count": len(vector_results),
                "bm25_results_count": len(bm25_results),
                "fused_results_count": len(fused_results),
                "final_results_count": len(reranked_results),
                "results": reranked_results,
                "weights": {
                    "vector": vector_weight,
                    "bm25": bm25_weight
                },
                "search_time_ms": search_time,
                "from_cache": False,
                # Добавляем метрики эмбеддингов
                "embedding_time_ms": embedding_metrics.get("embedding_time_ms", 0),
                "embedding_tokens": embedding_metrics.get("tokens_in", 0),
                "embedding_model": embedding_metrics.get("model", "multilingual-e5-large-instruct")
            }
            
            # T1.4: Кэшируем результат для будущих запросов
            self.cache_service.cache_search_results(
                query, access_level, result, search_params
            )
            
            logger.info(f"Гибридный поиск завершен за {search_time:.1f}ms: "
                       f"{len(vector_results)} векторных + {len(bm25_results)} BM25 → "
                       f"{len(fused_results)} объединенных → {len(reranked_results)} финальных")
            
            return result
            
        except Exception as e:
            search_time = (time.time() - start_time) * 1000
            logger.error("ОШИБКА гибридного поиска", 
                        error=str(e), 
                        search_time_ms=search_time)
            raise e
    
    def _vector_search(self, query: str, access_level: int, top_k: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Векторный (семантический) поиск через ChromaDB
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа
            top_k: Количество результатов
            
        Returns:
            Кортеж: (результаты векторного поиска, метрики эмбеддингов)
        """
        try:
            # Генерируем эмбеддинг запроса
            query_embedding_result = self.embedding_service.generate_query_embedding(query)
            query_embedding = query_embedding_result["embedding"]
            embedding_metrics = query_embedding_result["metrics"]
            
            # Поиск в ChromaDB
            search_result = self.database_service.query_chromadb(
                query_embedding, 
                access_level, 
                top_k
            )
            
            if not search_result["success"]:
                return [], embedding_metrics
            
            results = search_result["results"]
            
            # Форматируем результаты
            vector_results = []
            if results["documents"] and len(results["documents"]) > 0:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0], 
                    results["distances"][0]
                )):
                    vector_results.append({
                        "id": f"{metadata.get('doc_id', 'unknown')}_{metadata.get('chunk_index', i)}",
                        "content": doc,
                        "metadata": metadata,
                        "score": 1 - distance,  # Конвертация distance в similarity
                        "type": "vector",
                        "rank": i + 1
                    })
            
            logger.debug(f"Векторный поиск: найдено {len(vector_results)} результатов")
            return vector_results, embedding_metrics
            
        except Exception as e:
            logger.error("ОШИБКА векторного поиска", error=str(e))
            return [], {}
    
    def _bm25_search(self, query: str, access_level: int, top_k: int) -> List[Dict[str, Any]]:
        """
        R5.5: BM25 (лексический) поиск с расширением запросов
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа
            top_k: Количество результатов
            
        Returns:
            Результаты BM25 поиска
        """
        try:
            if self.bm25 is None:
                logger.warning("BM25 индекс не инициализирован")
                return []
            
            # R5.5: Расширяем запрос синонимами для BM25
            expansion_result = self.query_expansion_service.expand_query_smart(query)
            expanded_query = expansion_result["expanded_query"]
            
            # Логируем расширение если оно произошло
            if expansion_result["expansion_applied"]:
                logger.debug(f"BM25 query expanded: '{query}' -> '{expanded_query}' "
                           f"(+{expansion_result['synonyms_added']} synonyms)")
            
            # R5.4: Токенизация расширенного запроса с улучшенной обработкой
            tokenized_query = self._improved_tokenize(expanded_query)
            
            # Получение BM25 скоров
            scores = self.bm25.get_scores(tokenized_query)
            
            # Создание результатов с фильтрацией по access_level
            bm25_results = []
            for i, score in enumerate(scores):
                if i < len(self.bm25_metadatas):
                    metadata = self.bm25_metadatas[i]
                    
                    # Проверяем access_level
                    if metadata.get('access_level', 0) <= access_level:
                        bm25_results.append({
                            "id": self.bm25_ids[i],
                            "content": self.bm25_docs[i],
                            "metadata": metadata,
                            "score": float(score),
                            "type": "bm25",
                            "rank": len(bm25_results) + 1,
                            # R5.5: Добавляем информацию о расширении
                            "query_expansion": {
                                "original_query": query,
                                "expanded_query": expanded_query,
                                "expansion_applied": expansion_result["expansion_applied"],
                                "synonyms_added": expansion_result["synonyms_added"]
                            }
                        })
            
            # Сортируем по скору и берем топ
            bm25_results.sort(key=lambda x: x["score"], reverse=True)
            bm25_results = bm25_results[:top_k]
            
            logger.debug(f"BM25 поиск: найдено {len(bm25_results)} результатов "
                        f"(expansion: {expansion_result['expansion_applied']})")
            return bm25_results
            
        except Exception as e:
            logger.error("ОШИБКА BM25 поиска", error=str(e))
            return []
    
    def _rrf_fusion(
        self, 
        vector_results: List[Dict[str, Any]], 
        bm25_results: List[Dict[str, Any]],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion для объединения результатов
        
        Args:
            vector_results: Результаты векторного поиска
            bm25_results: Результаты BM25 поиска
            vector_weight: Вес векторного поиска
            bm25_weight: Вес BM25 поиска
            k: Параметр RRF (обычно 60)
            
        Returns:
            Объединенные и отсортированные результаты
        """
        try:
            rrf_scores = {}
            all_docs = {}
            
            # Обрабатываем векторные результаты
            for rank, result in enumerate(vector_results):
                doc_id = result['id']
                rrf_score = vector_weight * (1.0 / (k + rank + 1))
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score
                all_docs[doc_id] = result
            
            # Обрабатываем BM25 результаты
            for rank, result in enumerate(bm25_results):
                doc_id = result['id']
                rrf_score = bm25_weight * (1.0 / (k + rank + 1))
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + rrf_score
                
                # Если документ еще не был добавлен из векторного поиска
                if doc_id not in all_docs:
                    all_docs[doc_id] = result
            
            # Сортируем по RRF скору
            sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Формируем финальные результаты
            fused_results = []
            for rank, (doc_id, rrf_score) in enumerate(sorted_docs):
                if doc_id in all_docs:
                    result = all_docs[doc_id].copy()
                    result.update({
                        "rrf_score": float(rrf_score),
                        "type": "hybrid",
                        "rank": rank + 1
                    })
                    fused_results.append(result)
            
            logger.debug(f"RRF fusion: объединено {len(fused_results)} уникальных документов")
            return fused_results
            
        except Exception as e:
            logger.error("ОШИБКА RRF fusion", error=str(e))
            # Возвращаем векторные результаты как fallback
            return vector_results
    
    def _rerank_results(
        self, 
        query: str, 
        results: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Реранжирование результатов с помощью cross-encoder С ФИЛЬТРАЦИЕЙ ПО РЕЛЕВАНТНОСТИ
        
        Args:
            query: Поисковый запрос
            results: Результаты для реранжирования
            top_k: Количество финальных результатов
            
        Returns:
            Реранжированные результаты (только релевантные)
        """
        try:
            if not results:
                return []
            
            # Извлекаем тексты документов
            documents = [result["content"] for result in results]
            
            # Реранжируем с помощью cross-encoder
            reranked = self.reranking_service.rerank_results(query, documents, top_k)
            
            # Сопоставляем реранжированные результаты с оригинальными СНАЧАЛА
            all_reranked_results = []
            for rerank_result in reranked:
                original_index = rerank_result["index"]
                if original_index < len(results):
                    result = results[original_index].copy()
                    result.update({
                        "rerank_score": rerank_result["score"],
                        "final_rank": len(all_reranked_results) + 1
                    })
                    all_reranked_results.append(result)
            
            if not all_reranked_results:
                logger.debug(f"Реранжирование: нет результатов")
                return []
            
            # КРИТИЧНО: АДАПТИВНЫЕ ПОРОГИ для экспоненциально усиленных скоров (шкала 0-10)
            # Анализируем разброс скоров для установки динамического порога
            scores = [r["rerank_score"] for r in all_reranked_results]
            best_score = max(scores) if scores else 0
            worst_score = min(scores) if scores else 0
            score_range = best_score - worst_score
            
            # Если разброс большой (> 2.0) - используем относительный порог
            # Если разброс маленький (< 1.0) - используем строгий абсолютный порог
            if score_range > 2.0:
                # Большой разброс - берем только топ результаты (80% от лучшего)
                HIGH_RELEVANCE_THRESHOLD = best_score * 0.8
                GENERAL_CHAT_THRESHOLD = best_score * 0.4
            elif score_range > 1.0:
                # Средний разброс - умеренные пороги (70% от лучшего)
                HIGH_RELEVANCE_THRESHOLD = best_score * 0.7
                GENERAL_CHAT_THRESHOLD = best_score * 0.3
            else:
                # Малый разброс - очень строгие абсолютные пороги (берем только лучший результат)
                HIGH_RELEVANCE_THRESHOLD = best_score - 0.1  # Практически только лучший
                GENERAL_CHAT_THRESHOLD = best_score * 0.5
            
            logger.info(f"Adaptive thresholds: best={best_score:.3f}, worst={worst_score:.3f}, range={score_range:.3f}, high={HIGH_RELEVANCE_THRESHOLD:.3f}, general={GENERAL_CHAT_THRESHOLD:.3f}")
            
            logger.debug(f"Реранжирование: лучший скор {best_score:.3f}, high порог {HIGH_RELEVANCE_THRESHOLD:.3f}, general порог {GENERAL_CHAT_THRESHOLD:.3f}")
            
            # Если лучший результат имеет очень низкую релевантность - это общий чат
            if best_score < GENERAL_CHAT_THRESHOLD:
                logger.info(f"SearchService: Query appears to be general chat (best score: {best_score:.3f})")
                return []  # Возвращаем пустой массив
            
            # СТРОГАЯ ФИЛЬТРАЦИЯ: Берем только результаты выше порога
            filtered_results = [r for r in all_reranked_results if r["rerank_score"] >= HIGH_RELEVANCE_THRESHOLD]
            
            if not filtered_results:
                logger.info(f"SearchService: No results above {HIGH_RELEVANCE_THRESHOLD:.1%} relevance threshold (best: {best_score:.3f})")
                return []  # Возвращаем пустой массив
            
            logger.debug(f"Реранжирование: {len(results)} → {len(all_reranked_results)} → {len(filtered_results)} (отфильтровано)")
            return filtered_results
            
        except Exception as e:
            logger.error("ОШИБКА реранжирования", error=str(e))
            # Возвращаем оригинальные результаты как fallback
            return results[:top_k]
    
    def get_search_stats(self) -> Dict[str, Any]:
        """
        Получить статистику поискового индекса
        
        Returns:
            Статистика поиска
        """
        try:
            collection_stats = self.database_service.get_collection_stats()
            
            return {
                "bm25_initialized": self._bm25_initialized,
                "bm25_docs_count": len(self.bm25_docs) if self.bm25_docs else 0,
                "collection_stats": collection_stats,
                "search_methods": ["vector", "bm25", "hybrid"],
                "default_weights": {
                    "vector": 0.7,
                    "bm25": 0.3
                }
            }
            
        except Exception as e:
            logger.error("ОШИБКА получения статистики поиска", error=str(e))
            return {
                "error": str(e)
            }
    
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
        T1.6: Batch обработка множественных поисковых запросов
        
        Args:
            queries: Список поисковых запросов
            access_level: Уровень доступа пользователя
            top_k: Количество результатов для каждого метода
            rerank_top_k: Финальное количество результатов после реранжирования
            vector_weight: Вес векторного поиска
            bm25_weight: Вес BM25 поиска
            
        Returns:
            Результаты batch поиска
        """
        start_time = time.time()
        
        try:
            logger.info(f"Начинаем batch поиск для {len(queries)} запросов")
            
            # Инициализируем BM25 один раз для всех запросов
            self._ensure_bm25_initialized(access_level)
            
            batch_results = []
            cache_hits = 0
            
            # Обрабатываем каждый запрос
            for i, query in enumerate(queries):
                try:
                    # Проверяем кэш для каждого запроса
                    search_params = {
                        "top_k": top_k,
                        "rerank_top_k": rerank_top_k,
                        "vector_weight": vector_weight,
                        "bm25_weight": bm25_weight
                    }
                    
                    cached_result = self.cache_service.get_cached_search_results(
                        query, access_level, search_params
                    )
                    
                    if cached_result:
                        cache_hits += 1
                        batch_results.append({
                            "query_index": i,
                            "query": query,
                            "result": cached_result
                        })
                    else:
                        # Выполняем поиск без кэширования (будет закэшировано в hybrid_search)
                        result = self.hybrid_search(
                            query, access_level, top_k, rerank_top_k, 
                            vector_weight, bm25_weight
                        )
                        
                        batch_results.append({
                            "query_index": i,
                            "query": query,
                            "result": result
                        })
                        
                except Exception as query_error:
                    logger.error(f"Ошибка обработки запроса {i}: {query}", error=str(query_error))
                    batch_results.append({
                        "query_index": i,
                        "query": query,
                        "result": {
                            "success": False,
                            "error": str(query_error)
                        }
                    })
            
            batch_time = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "batch_size": len(queries),
                "processed_queries": len(batch_results),
                "cache_hits": cache_hits,
                "cache_hit_rate": cache_hits / len(queries) if queries else 0,
                "results": batch_results,
                "batch_time_ms": batch_time,
                "average_time_per_query_ms": batch_time / len(queries) if queries else 0
            }
            
            logger.info(f"Batch поиск завершен за {batch_time:.1f}ms: "
                       f"{len(queries)} запросов, {cache_hits} из кэша")
            
            return result
            
        except Exception as e:
            batch_time = (time.time() - start_time) * 1000
            logger.error("ОШИБКА batch поиска", 
                        error=str(e), 
                        batch_time_ms=batch_time)
            raise e
    
    def reinitialize_bm25(self, access_level: int) -> Dict[str, Any]:
        """
        Переинициализация BM25 индекса (например, после добавления новых документов)
        T1.3: Добавлена инвалидация кэша при переинициализации
        
        Args:
            access_level: Уровень доступа пользователя
            
        Returns:
            Результат переинициализации
        """
        try:
            logger.info("Переинициализация BM25 индекса")
            
            # T1.3: Инвалидируем все кэши перед переинициализацией
            self.cache_service.invalidate_bm25_cache()  # Все BM25 кэши
            self.cache_service.invalidate_search_cache()  # Все поисковые кэши
            
            self._bm25_initialized = False
            self.bm25 = None
            self.bm25_docs = None
            self.bm25_ids = None
            self.bm25_metadatas = None
            
            self._ensure_bm25_initialized(access_level)
            
            return {
                "success": True,
                "bm25_docs_count": len(self.bm25_docs) if self.bm25_docs else 0,
                "message": "BM25 индекс переинициализирован, кэши очищены"
            }
            
        except Exception as e:
            logger.error("ОШИБКА переинициализации BM25", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }


# Глобальный экземпляр сервиса поиска
_search_service_instance = None

def get_search_service(database_service, embedding_service, reranking_service) -> SearchService:
    """
    Получить глобальный экземпляр SearchService (singleton pattern)
    
    Args:
        database_service: Сервис базы данных
        embedding_service: Сервис эмбеддингов
        reranking_service: Сервис реранжирования (может быть LocalRerankingService)
        
    Returns:
        Экземпляр SearchService
    """
    global _search_service_instance
    
    if _search_service_instance is None:
        _search_service_instance = SearchService(
            database_service, 
            embedding_service, 
            reranking_service
        )
    
    return _search_service_instance
