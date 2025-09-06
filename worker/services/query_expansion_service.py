"""
R5.5: Сервис расширения запросов с синонимами
Простая и эффективная реализация для улучшения полноты поиска
"""

import json
import os
import re
import logging
from typing import List, Dict, Set, Tuple
import structlog

logger = structlog.get_logger(__name__)

class QueryExpansionService:
    """
    R5.5: Сервис для расширения поисковых запросов синонимами
    """
    
    def __init__(self):
        """Инициализация сервиса с загрузкой словаря синонимов"""
        self.synonyms_dict = {}
        self._load_synonyms()
        logger.info("QueryExpansionService инициализирован", 
                   synonyms_loaded=len(self.synonyms_dict))
    
    def _load_synonyms(self):
        """Загрузка словаря синонимов из JSON файла"""
        try:
            synonyms_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'synonyms_ru.json')
            
            if os.path.exists(synonyms_path):
                with open(synonyms_path, 'r', encoding='utf-8') as f:
                    self.synonyms_dict = json.load(f)
                logger.info(f"Словарь синонимов загружен: {len(self.synonyms_dict)} терминов")
            else:
                logger.warning(f"Файл синонимов не найден: {synonyms_path}")
                self.synonyms_dict = {}
                
        except Exception as e:
            logger.error("Ошибка загрузки словаря синонимов", error=str(e))
            self.synonyms_dict = {}
    
    def _extract_terms(self, query: str) -> List[str]:
        """
        Извлечение терминов из запроса для поиска синонимов
        
        Args:
            query: Поисковый запрос
            
        Returns:
            Список терминов для расширения
        """
        # Простая токенизация с сохранением важных терминов
        terms = []
        
        # Извлекаем слова длиной от 2 символов
        words = re.findall(r'\b\w{2,}\b', query.lower())
        
        # Добавляем отдельные слова
        terms.extend(words)
        
        # Ищем составные термины (2-3 слова подряд)
        for i in range(len(words) - 1):
            # Биграммы
            bigram = f"{words[i]} {words[i+1]}"
            terms.append(bigram)
            
            # Триграммы
            if i < len(words) - 2:
                trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
                terms.append(trigram)
        
        return terms
    
    def expand_query(self, query: str, max_synonyms_per_term: int = 2) -> Dict[str, any]:
        """
        R5.5: Расширение запроса синонимами
        
        Args:
            query: Исходный поисковый запрос
            max_synonyms_per_term: Максимум синонимов на термин
            
        Returns:
            Словарь с расширенным запросом и метаданными
        """
        try:
            # Извлекаем термины из запроса
            terms = self._extract_terms(query)
            
            # Находим синонимы
            found_synonyms = {}
            expanded_terms = set()
            
            for term in terms:
                if term in self.synonyms_dict:
                    synonyms = self.synonyms_dict[term][:max_synonyms_per_term]
                    found_synonyms[term] = synonyms
                    expanded_terms.update(synonyms)
            
            # Создаем расширенный запрос
            if expanded_terms:
                # Добавляем синонимы к исходному запросу
                expanded_query = query + " " + " ".join(expanded_terms)
            else:
                expanded_query = query
            
            result = {
                "original_query": query,
                "expanded_query": expanded_query,
                "found_synonyms": found_synonyms,
                "expansion_terms": list(expanded_terms),
                "terms_expanded": len(found_synonyms),
                "synonyms_added": len(expanded_terms),
                "expansion_applied": len(expanded_terms) > 0
            }
            
            if len(expanded_terms) > 0:
                logger.debug(f"Query expanded: '{query}' -> +{len(expanded_terms)} synonyms")
            
            return result
            
        except Exception as e:
            logger.error("Ошибка расширения запроса", error=str(e), query=query)
            return {
                "original_query": query,
                "expanded_query": query,
                "found_synonyms": {},
                "expansion_terms": [],
                "terms_expanded": 0,
                "synonyms_added": 0,
                "expansion_applied": False,
                "error": str(e)
            }
    
    def expand_query_smart(self, query: str, context: str = None) -> Dict[str, any]:
        """
        R5.5: Умное расширение запроса с учетом контекста
        
        Args:
            query: Исходный поисковый запрос
            context: Контекст (например, предыдущие запросы)
            
        Returns:
            Словарь с расширенным запросом и метаданными
        """
        try:
            # Определяем тип запроса для адаптивного расширения
            query_lower = query.lower()
            
            # Для технических запросов - больше синонимов
            if any(tech_term in query_lower for tech_term in 
                   ['api', 'база данных', 'программирование', 'разработка', 'сервер']):
                max_synonyms = 3
            # Для бизнес-запросов - умеренное расширение
            elif any(biz_term in query_lower for biz_term in 
                     ['клиент', 'продажи', 'маркетинг', 'проект', 'документооборот']):
                max_synonyms = 2
            # Для дизайн-запросов - фокус на визуальных терминах
            elif any(design_term in query_lower for design_term in 
                     ['дизайн', 'макет', 'брендинг', 'логотип', 'креатив']):
                max_synonyms = 2
            else:
                max_synonyms = 2  # По умолчанию
            
            # Выполняем расширение
            result = self.expand_query(query, max_synonyms_per_term=max_synonyms)
            result["expansion_strategy"] = "smart"
            result["max_synonyms_used"] = max_synonyms
            
            return result
            
        except Exception as e:
            logger.error("Ошибка умного расширения запроса", error=str(e), query=query)
            # Fallback к обычному расширению
            return self.expand_query(query)
    
    def get_synonyms_for_term(self, term: str) -> List[str]:
        """
        Получить синонимы для конкретного термина
        
        Args:
            term: Термин для поиска синонимов
            
        Returns:
            Список синонимов
        """
        return self.synonyms_dict.get(term.lower(), [])
    
    def add_synonyms(self, term: str, synonyms: List[str]):
        """
        Добавить синонимы для термина (runtime добавление)
        
        Args:
            term: Термин
            synonyms: Список синонимов
        """
        self.synonyms_dict[term.lower()] = synonyms
        logger.debug(f"Добавлены синонимы для '{term}': {synonyms}")
    
    def get_stats(self) -> Dict[str, any]:
        """Получить статистику сервиса"""
        return {
            "total_terms": len(self.synonyms_dict),
            "total_synonyms": sum(len(synonyms) for synonyms in self.synonyms_dict.values()),
            "avg_synonyms_per_term": sum(len(synonyms) for synonyms in self.synonyms_dict.values()) / len(self.synonyms_dict) if self.synonyms_dict else 0,
            "categories": {
                "tech_terms": len([k for k in self.synonyms_dict.keys() if any(tech in k for tech in ['api', 'база', 'программ', 'разработ'])]),
                "business_terms": len([k for k in self.synonyms_dict.keys() if any(biz in k for biz in ['клиент', 'продаж', 'маркетинг'])]),
                "design_terms": len([k for k in self.synonyms_dict.keys() if any(design in k for design in ['дизайн', 'макет', 'бренд'])])
            }
        }
    
    def health_check(self) -> Dict[str, any]:
        """Проверка здоровья сервиса"""
        try:
            # Тестируем расширение на простом запросе
            test_result = self.expand_query("база данных")
            
            return {
                "status": "healthy",
                "synonyms_loaded": len(self.synonyms_dict) > 0,
                "test_expansion_works": test_result["expansion_applied"],
                "total_terms": len(self.synonyms_dict)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "synonyms_loaded": len(self.synonyms_dict) > 0
            }


# Глобальный экземпляр сервиса (singleton pattern)
_query_expansion_service_instance = None

def get_query_expansion_service() -> QueryExpansionService:
    """
    Получить глобальный экземпляр QueryExpansionService (singleton pattern)
    
    Returns:
        Экземпляр QueryExpansionService
    """
    global _query_expansion_service_instance
    
    if _query_expansion_service_instance is None:
        _query_expansion_service_instance = QueryExpansionService()
    
    return _query_expansion_service_instance
