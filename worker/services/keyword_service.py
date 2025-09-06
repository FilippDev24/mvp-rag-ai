"""
Сервис для извлечения ключевых слов из текста.
Использует KeyBERT с совместимой моделью и regex для технических терминов.
"""

import re
import logging
import time
from typing import List, Dict, Set, Tuple, Optional
from keybert import KeyBERT
import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

class KeywordService:
    """Сервис для извлечения ключевых слов из документов."""
    
    def __init__(self):
        """Инициализация сервиса без загрузки модели."""
        self.keybert = None
        self._model_loaded = False
        self._load_timeout = 300  # 5 минут timeout для загрузки модели
        logger.info("KeywordService инициализирован (модель будет загружена при первом использовании)")
    
    def _ensure_keybert_loaded(self):
        """
        Ленивая загрузка KeyBERT модели с timeout и proper error handling.
        КРИТИЧНО: Используем совместимую с KeyBERT модель, НЕ instruct модель.
        """
        if self._model_loaded and self.keybert is not None:
            return
            
        start_time = time.time()
        
        try:
            logger.info("Загрузка модели для KeyBERT...")
            
            # ИСПРАВЛЕНИЕ: Используем совместимую модель для KeyBERT
            # НЕ используем instruct модель, так как KeyBERT её не поддерживает
            model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
            
            # Загружаем модель с timeout
            sentence_model = SentenceTransformer(model_name, device='cpu')
            self.keybert = KeyBERT(model=sentence_model)
            
            load_time = time.time() - start_time
            
            if load_time > self._load_timeout:
                raise TimeoutError(f"Model loading exceeded timeout of {self._load_timeout}s")
            
            self._model_loaded = True
            logger.info(f"KeyBERT модель загружена успешно за {load_time:.1f}s", 
                       model=model_name)
            
        except Exception as e:
            logger.error("КРИТИЧЕСКАЯ ОШИБКА загрузки KeyBERT модели", 
                        error=str(e), 
                        load_time=time.time() - start_time)
            # НЕ поднимаем исключение - возвращаем пустые ключевые слова
            self.keybert = None
            self._model_loaded = False
    
    def extract_keywords(self, text: str, chunk_index: int = 0) -> Dict[str, List[str]]:
        """
        Извлекает ключевые слова из текста с proper error handling.
        
        Args:
            text: Текст для анализа
            chunk_index: Индекс чанка для логирования
            
        Returns:
            Dict с семантическими и техническими ключевыми словами
        """
        start_time = time.time()
        
        try:
            logger.info(f"Извлечение ключевых слов для чанка {chunk_index}")
            
            # Проверяем длину текста
            if len(text.strip()) < 50:
                logger.warning(f"Текст слишком короткий для извлечения ключевых слов: {len(text)} символов")
                return {
                    'semantic_keywords': [],
                    'technical_keywords': [],
                    'all_keywords': []
                }
            
            # Семантические ключевые слова через KeyBERT (с fallback)
            semantic_keywords = self._extract_semantic_keywords(text)
            
            # Технические термины через regex (всегда работает)
            technical_keywords = self._extract_technical_terms(text)
            
            # Объединение и дедупликация
            all_keywords = list(set(semantic_keywords + technical_keywords))
            
            result = {
                'semantic_keywords': semantic_keywords,
                'technical_keywords': technical_keywords,
                'all_keywords': all_keywords[:20]  # Ограничиваем до 20 ключевых слов
            }
            
            extraction_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"Ключевые слова извлечены для чанка {chunk_index}",
                semantic_count=len(semantic_keywords),
                technical_count=len(technical_keywords),
                total_count=len(all_keywords),
                extraction_time_ms=extraction_time
            )
            
            return result
            
        except Exception as e:
            extraction_time = (time.time() - start_time) * 1000
            logger.error(f"ОШИБКА извлечения ключевых слов для чанка {chunk_index}", 
                        error=str(e), 
                        extraction_time_ms=extraction_time)
            
            # Возвращаем хотя бы технические термины
            try:
                technical_keywords = self._extract_technical_terms(text)
                return {
                    'semantic_keywords': [],
                    'technical_keywords': technical_keywords,
                    'all_keywords': technical_keywords
                }
            except:
                return {
                    'semantic_keywords': [],
                    'technical_keywords': [],
                    'all_keywords': []
                }
    
    def _extract_semantic_keywords(self, text: str) -> List[str]:
        """
        Извлекает семантические ключевые слова с помощью KeyBERT.
        ИСПРАВЛЕНИЕ: Добавлен timeout и fallback при ошибках.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список семантических ключевых слов
        """
        try:
            # Убеждаемся, что KeyBERT загружен
            self._ensure_keybert_loaded()
            
            # Если модель не загрузилась - возвращаем пустой список
            if not self._model_loaded or self.keybert is None:
                logger.warning("KeyBERT модель недоступна, пропускаем семантические ключевые слова")
                return []
            
            # Ограничиваем длину текста для KeyBERT
            max_text_length = 2000
            if len(text) > max_text_length:
                text = text[:max_text_length] + "..."
                logger.debug(f"Текст обрезан до {max_text_length} символов для KeyBERT")
            
            # Параметры для KeyBERT с timeout
            start_time = time.time()
            
            # ИСПРАВЛЕНИЕ: Правильные параметры KeyBERT согласно документации
            keywords = self.keybert.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 2),  # Униграммы и биграммы
                stop_words=None,               # НЕ 'russian' - не работает!
                use_mmr=True,                  # Maximal Marginal Relevance
                diversity=0.5,                 # Баланс релевантность/разнообразие
                nr_candidates=20,              # Количество кандидатов для MMR
                top_n=10                       # НЕ top_k! Правильный параметр top_n
            )
            
            keybert_time = (time.time() - start_time) * 1000
            
            # Проверяем timeout
            if keybert_time > 30000:  # 30 секунд
                logger.warning(f"KeyBERT обработка заняла слишком много времени: {keybert_time:.1f}ms")
            
            # KeyBERT возвращает список кортежей (keyword, score)
            # ИСПРАВЛЕНИЕ: Простая и эффективная фильтрация
            semantic_keywords = []
            
            # Русские стоп-слова для фильтрации
            russian_stop_words = {
                'это', 'для', 'или', 'как', 'что', 'так', 'все', 'еще', 'уже', 'его', 'ее', 
                'их', 'они', 'она', 'оно', 'мы', 'вы', 'ты', 'я', 'он', 'при', 'под', 'над',
                'дата', 'года', 'год', 'лет', 'день', 'время', 'место', 'номер', 'пункт'
            }
            
            for keyword, score in keywords:
                cleaned_keyword = keyword.strip().lower()
                
                # Простая и понятная фильтрация
                if (len(cleaned_keyword) >= 3 and                      # Минимум 3 символа
                    score > 0.3 and                                    # Высокий порог релевантности
                    cleaned_keyword not in russian_stop_words and      # Не стоп-слово
                    not re.match(r'^\d+', cleaned_keyword) and         # Не начинается с цифры
                    '___' not in cleaned_keyword and                   # Нет подчеркиваний
                    len(cleaned_keyword.split()) <= 2):               # Максимум 2 слова
                    semantic_keywords.append(cleaned_keyword)
            
            logger.debug(f"KeyBERT обработка завершена за {keybert_time:.1f}ms, найдено {len(semantic_keywords)} ключевых слов")
            
            return semantic_keywords[:10]  # Ограничиваем до 10
            
        except Exception as e:
            logger.error("ОШИБКА извлечения семантических ключевых слов", error=str(e))
            # НЕ поднимаем исключение - возвращаем пустой список
            return []
    
    def _extract_technical_terms(self, text: str) -> List[str]:
        """
        Извлекает технические термины с помощью regex паттернов.
        Этот метод всегда работает, даже если KeyBERT недоступен.
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список технических терминов
        """
        try:
            technical_terms = set()
            
            # Паттерны для технических терминов
            patterns = {
                # Программирование
                'programming_languages': r'\b(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|SQL)\b',
                'frameworks': r'\b(?:React|Vue|Angular|Django|Flask|Express|Spring|Laravel|Rails|ASP\.NET|FastAPI|Celery)\b',
                'databases': r'\b(?:PostgreSQL|MySQL|MongoDB|Redis|SQLite|Oracle|SQL Server|ChromaDB|Elasticsearch|Prisma)\b',
                'technologies': r'\b(?:Docker|Kubernetes|AWS|Azure|GCP|API|REST|GraphQL|JWT|OAuth|SSL|TLS|RAG|LLM|AI|ML)\b',
                
                # Файлы и форматы
                'file_extensions': r'\b\w+\.(?:pdf|docx?|xlsx?|pptx?|csv|json|xml|html|css|js|ts|py|java|cpp|sql|md|txt)\b',
                'protocols': r'\b(?:HTTP|HTTPS|FTP|SMTP|TCP|UDP|WebSocket|SSE)\b',
                
                # Числовые значения и единицы
                'numbers_with_units': r'\b\d+(?:\.\d+)?\s*(?:MB|GB|TB|KB|ms|sec|min|hour|%|px|em|rem)\b',
                'versions': r'\bv?\d+\.\d+(?:\.\d+)?(?:-\w+)?\b',
                
                # Специальные термины
                'ai_ml_terms': r'\b(?:embedding|vector|neural|model|algorithm|dataset|transformer|BERT|GPT|LLM|NLP|RAG)\b',
                'business_terms': r'\b(?:SaaS|B2B|B2C|MVP|ROI|KPI|CRM|ERP|UI|UX|API)\b',
                
                # Системные термины
                'system_terms': r'\b(?:server|client|backend|frontend|database|cache|queue|worker|service|middleware)\b'
            }
            
            for category, pattern in patterns.items():
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Нормализация: приводим к нижнему регистру, кроме аббревиатур
                    if match.isupper() and len(match) <= 5:
                        technical_terms.add(match.upper())
                    else:
                        technical_terms.add(match.lower())
            
            # Дополнительные паттерны для специфических терминов (ИСПРАВЛЕНО)
            additional_patterns = [
                # Функции и методы
                r'\b\w+\(\)',       # function()
                # Классы (CamelCase) - только осмысленные
                r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b'
            ]
            
            for pattern in additional_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    # ИСПРАВЛЕНИЕ: Фильтруем мусорные термины
                    if (len(match) > 2 and 
                        match not in ['THE', 'AND', 'FOR', 'WITH', 'BUT', 'NOT'] and
                        not match.startswith('_') and  # Убираем подчеркивания
                        not match.endswith('_') and
                        '_' not in match or match.count('_') <= 1):  # Максимум одно подчеркивание
                        technical_terms.add(match)
            
            # ИСПРАВЛЕНИЕ: Фильтруем результаты от мусора
            filtered_terms = []
            for term in technical_terms:
                # Убираем термины состоящие только из символов и цифр
                if (len(term) >= 3 and 
                    not re.match(r'^[_\-\.]+$', term) and  # Только символы
                    not re.match(r'^[\d\.]+$', term) and   # Только цифры
                    term.count('_') < len(term) // 2):     # Не больше половины подчеркиваний
                    filtered_terms.append(term)
            
            result = filtered_terms[:10]  # Ограничиваем до 10
            logger.debug(f"Извлечено {len(result)} технических терминов: {result}")
            
            return result
            
        except Exception as e:
            logger.error("ОШИБКА извлечения технических терминов", error=str(e))
            return []
    
    def extract_keywords_batch(self, texts: List[str]) -> List[Dict[str, List[str]]]:
        """
        Извлекает ключевые слова для батча текстов с улучшенной обработкой ошибок.
        
        Args:
            texts: Список текстов для анализа
            
        Returns:
            Список словарей с ключевыми словами для каждого текста
        """
        results = []
        
        logger.info(f"Начинаем batch извлечение ключевых слов для {len(texts)} текстов")
        
        for i, text in enumerate(texts):
            try:
                keywords = self.extract_keywords(text, chunk_index=i)
                results.append(keywords)
            except Exception as e:
                logger.error(f"Ошибка обработки текста {i} в batch", error=str(e))
                # Добавляем пустой результат вместо прерывания всего batch
                results.append({
                    'semantic_keywords': [],
                    'technical_keywords': [],
                    'all_keywords': []
                })
        
        logger.info(f"Batch извлечение завершено: {len(results)} результатов")
        return results
    
    def get_document_keywords_summary(self, all_chunks_keywords: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """
        Создает сводку ключевых слов для всего документа.
        
        Args:
            all_chunks_keywords: Ключевые слова всех чанков документа
            
        Returns:
            Сводка ключевых слов документа
        """
        try:
            semantic_counter = {}
            technical_counter = {}
            
            # Подсчитываем частоту ключевых слов по всем чанкам
            for chunk_keywords in all_chunks_keywords:
                for keyword in chunk_keywords.get('semantic_keywords', []):
                    semantic_counter[keyword] = semantic_counter.get(keyword, 0) + 1
                
                for keyword in chunk_keywords.get('technical_keywords', []):
                    technical_counter[keyword] = technical_counter.get(keyword, 0) + 1
            
            # Сортируем по частоте и берем топ
            top_semantic = sorted(
                semantic_counter.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:15]
            
            top_technical = sorted(
                technical_counter.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:15]
            
            result = {
                'document_semantic_keywords': [kw for kw, _ in top_semantic],
                'document_technical_keywords': [kw for kw, _ in top_technical],
                'document_all_keywords': [kw for kw, _ in (top_semantic + top_technical)][:20]
            }
            
            logger.info(f"Создана сводка ключевых слов документа: "
                       f"{len(result['document_semantic_keywords'])} семантических, "
                       f"{len(result['document_technical_keywords'])} технических")
            
            return result
            
        except Exception as e:
            logger.error("ОШИБКА создания сводки ключевых слов документа", error=str(e))
            return {
                'document_semantic_keywords': [],
                'document_technical_keywords': [],
                'document_all_keywords': []
            }
    
    def get_model_info(self) -> Dict[str, any]:
        """Получить информацию о модели KeyBERT."""
        return {
            "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
            "model_loaded": self._model_loaded,
            "keybert_available": self.keybert is not None,
            "supports_multilingual": True,
            "max_keywords_per_chunk": 10,
            "max_keywords_per_document": 20
        }
    
    def health_check(self) -> Dict[str, any]:
        """Проверка здоровья сервиса ключевых слов."""
        try:
            # Тестируем на простом тексте
            test_text = "Python programming language machine learning artificial intelligence"
            test_result = self.extract_keywords(test_text, chunk_index=-1)
            
            return {
                "status": "healthy",
                "model_loaded": self._model_loaded,
                "keybert_available": self.keybert is not None,
                "test_extraction_successful": len(test_result['all_keywords']) > 0,
                "test_keywords_count": len(test_result['all_keywords'])
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model_loaded": self._model_loaded,
                "keybert_available": self.keybert is not None
            }


# Глобальный экземпляр сервиса с lazy loading
_keyword_service_instance = None

def get_keyword_service() -> KeywordService:
    """
    Получить глобальный экземпляр KeywordService (singleton pattern).
    ИСПРАВЛЕНИЕ: Убираем глобальные None переменные.
    """
    global _keyword_service_instance
    
    if _keyword_service_instance is None:
        _keyword_service_instance = KeywordService()
    
    return _keyword_service_instance
