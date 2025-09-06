#!/usr/bin/env python3
"""
Инструмент диагностики поиска и ранжирования
Позволяет быстро проверить настройки и найти причины нерелевантных результатов
"""

import os
import sys
import json
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import argparse

# Добавляем путь к worker модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database_service import DatabaseService
from services.embedding_service import EmbeddingService
from services.search_service import get_search_service
from services.local_reranking_service import LocalRerankingService
from services.reranking_service import RerankingService

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DiagnosticResult:
    """Результат диагностики"""
    query: str
    access_level: int
    vector_results: List[Dict]
    bm25_results: List[Dict]
    fused_results: List[Dict]
    reranked_results: List[Dict]
    rerank_scores: List[float]
    thresholds: Dict[str, float]
    diagnostics: Dict[str, Any]

class SearchDiagnostics:
    """Класс для диагностики поиска и ранжирования"""
    
    def __init__(self):
        """Инициализация диагностического инструмента"""
        self.database_service = None
        self.embedding_service = None
        self.search_service = None
        self.reranking_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Инициализация всех сервисов"""
        try:
            logger.info("🔧 Инициализация сервисов...")
            
            # Инициализация сервисов (как в tasks.py)
            self.database_service = DatabaseService()
            self.embedding_service = EmbeddingService()
            
            # Выбираем локальный или обычный реранжер
            try:
                self.reranking_service = LocalRerankingService()
                logger.info("✅ Используем LocalRerankingService")
            except Exception as e:
                logger.warning(f"⚠️  LocalRerankingService недоступен: {e}")
                self.reranking_service = RerankingService()
                logger.info("✅ Используем RerankingService")
            
            self.search_service = get_search_service(
                self.database_service,
                self.embedding_service, 
                self.reranking_service
            )
            
            logger.info("✅ Все сервисы инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервисов: {e}")
            raise
    
    def diagnose_query(
        self, 
        query: str, 
        access_level: int = 100,
        top_k: int = 30,
        rerank_top_k: int = 10
    ) -> DiagnosticResult:
        """
        Полная диагностика поискового запроса
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа
            top_k: Количество результатов для каждого метода
            rerank_top_k: Количество результатов после реранжирования
            
        Returns:
            Результат диагностики
        """
        logger.info(f"🔍 Диагностика запроса: '{query}'")
        
        # Инициализируем BM25 если нужно
        self.search_service._ensure_bm25_initialized(access_level)
        
        # 1. Векторный поиск
        logger.info("📊 Выполняем векторный поиск...")
        vector_results, embedding_metrics = self.search_service._vector_search(query, access_level, top_k)
        
        # 2. BM25 поиск
        logger.info("📝 Выполняем BM25 поиск...")
        bm25_results = self.search_service._bm25_search(query, access_level, top_k)
        
        # 3. RRF Fusion
        logger.info("🔀 Выполняем RRF fusion...")
        fused_results = self.search_service._rrf_fusion(vector_results, bm25_results)
        
        # 4. Реранжирование с детальной диагностикой
        logger.info("🎯 Выполняем реранжирование...")
        reranked_results, rerank_diagnostics = self._detailed_rerank(query, fused_results, rerank_top_k)
        
        # 5. Анализ результатов
        diagnostics = self._analyze_results(
            query, vector_results, bm25_results, fused_results, 
            reranked_results, rerank_diagnostics
        )
        
        return DiagnosticResult(
            query=query,
            access_level=access_level,
            vector_results=vector_results,
            bm25_results=bm25_results,
            fused_results=fused_results,
            reranked_results=reranked_results,
            rerank_scores=rerank_diagnostics.get('scores', []),
            thresholds=rerank_diagnostics.get('thresholds', {}),
            diagnostics=diagnostics
        )
    
    def _detailed_rerank(self, query: str, results: List[Dict], top_k: int) -> tuple:
        """Детальное реранжирование с диагностикой"""
        if not results:
            return [], {}
        
        # Извлекаем тексты документов
        documents = [result["content"] for result in results]
        
        # Реранжируем
        reranked = self.reranking_service.rerank_results(query, documents, top_k)
        
        # Сопоставляем с оригинальными результатами
        all_reranked_results = []
        scores = []
        
        for rerank_result in reranked:
            original_index = rerank_result["index"]
            if original_index < len(results):
                result = results[original_index].copy()
                result.update({
                    "rerank_score": rerank_result["score"],
                    "raw_logit": rerank_result.get("raw_logit", 0),
                    "final_rank": len(all_reranked_results) + 1
                })
                all_reranked_results.append(result)
                scores.append(rerank_result["score"])
        
        # Анализируем пороги (копируем логику из search_service)
        if scores:
            best_score = max(scores)
            worst_score = min(scores)
            score_range = best_score - worst_score
            
            if score_range > 2.0:
                high_threshold = best_score * 0.8
                general_threshold = best_score * 0.4
            elif score_range > 1.0:
                high_threshold = best_score * 0.7
                general_threshold = best_score * 0.3
            else:
                high_threshold = best_score - 0.1
                general_threshold = best_score * 0.5
        else:
            high_threshold = 0
            general_threshold = 0
            best_score = 0
            worst_score = 0
            score_range = 0
        
        # Фильтруем по порогам
        filtered_results = [r for r in all_reranked_results if r["rerank_score"] >= high_threshold]
        
        diagnostics = {
            'scores': scores,
            'best_score': best_score,
            'worst_score': worst_score,
            'score_range': score_range,
            'thresholds': {
                'high_relevance': high_threshold,
                'general_chat': general_threshold
            },
            'total_results': len(all_reranked_results),
            'filtered_results': len(filtered_results),
            'filtered_out': len(all_reranked_results) - len(filtered_results)
        }
        
        return filtered_results, diagnostics
    
    def _analyze_results(
        self, 
        query: str, 
        vector_results: List[Dict], 
        bm25_results: List[Dict],
        fused_results: List[Dict], 
        reranked_results: List[Dict],
        rerank_diagnostics: Dict
    ) -> Dict[str, Any]:
        """Анализ результатов поиска"""
        
        # Анализ пересечений
        vector_ids = {r['id'] for r in vector_results}
        bm25_ids = {r['id'] for r in bm25_results}
        intersection = vector_ids & bm25_ids
        
        # Анализ качества результатов
        quality_analysis = self._analyze_quality(query, reranked_results)
        
        return {
            'query_analysis': {
                'length': len(query),
                'words': len(query.split()),
                'has_numbers': any(c.isdigit() for c in query),
                'has_dates': self._has_dates(query),
                'language': 'ru' if any(ord(c) > 127 for c in query) else 'en'
            },
            'search_results': {
                'vector_count': len(vector_results),
                'bm25_count': len(bm25_results),
                'intersection_count': len(intersection),
                'intersection_ratio': len(intersection) / max(len(vector_ids), 1),
                'fused_count': len(fused_results),
                'final_count': len(reranked_results)
            },
            'reranking': rerank_diagnostics,
            'quality': quality_analysis,
            'recommendations': self._generate_recommendations(
                query, vector_results, bm25_results, reranked_results, rerank_diagnostics
            )
        }
    
    def _analyze_quality(self, query: str, results: List[Dict]) -> Dict[str, Any]:
        """Анализ качества результатов"""
        if not results:
            return {'status': 'no_results', 'issues': ['Нет результатов']}
        
        issues = []
        
        # Проверяем скоры реранжирования
        scores = [r.get('rerank_score', 0) for r in results]
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score < 3.0:
                issues.append(f'Низкие скоры реранжирования (макс: {max_score:.2f})')
            
            if avg_score < 2.0:
                issues.append(f'Низкий средний скор ({avg_score:.2f})')
            
            if max_score - min_score < 0.5:
                issues.append('Малый разброс скоров - возможно плохое различение')
        
        # Проверяем содержимое результатов
        query_words = set(query.lower().split())
        for i, result in enumerate(results[:3]):  # Проверяем топ-3
            content = result.get('content', '').lower()
            content_words = set(content.split())
            
            overlap = len(query_words & content_words)
            if overlap == 0:
                issues.append(f'Результат #{i+1} не содержит слов из запроса')
        
        status = 'good' if not issues else 'issues_found'
        
        return {
            'status': status,
            'issues': issues,
            'scores_stats': {
                'min': min(scores) if scores else 0,
                'max': max(scores) if scores else 0,
                'avg': sum(scores) / len(scores) if scores else 0,
                'count': len(scores)
            }
        }
    
    def _has_dates(self, text: str) -> bool:
        """Проверка наличия дат в тексте"""
        import re
        date_patterns = [
            r'\d{2}\.\d{2}\.\d{4}',  # DD.MM.YYYY
            r'\d{4}-\d{2}-\d{2}',   # YYYY-MM-DD
            r'\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in date_patterns)
    
    def _generate_recommendations(
        self, 
        query: str, 
        vector_results: List[Dict], 
        bm25_results: List[Dict],
        reranked_results: List[Dict], 
        rerank_diagnostics: Dict
    ) -> List[str]:
        """Генерация рекомендаций по улучшению"""
        recommendations = []
        
        # Анализ порогов
        thresholds = rerank_diagnostics.get('thresholds', {})
        best_score = rerank_diagnostics.get('best_score', 0)
        
        if best_score < 2.0:
            recommendations.append('🔴 КРИТИЧНО: Очень низкие скоры реранжирования - возможно запрос не связан с документами')
        elif best_score < 4.0:
            recommendations.append('🟡 ВНИМАНИЕ: Низкие скоры реранжирования - проверьте релевантность документов')
        
        # Анализ фильтрации
        filtered_out = rerank_diagnostics.get('filtered_out', 0)
        total_results = rerank_diagnostics.get('total_results', 0)
        
        if filtered_out > 0:
            filter_ratio = filtered_out / max(total_results, 1)
            if filter_ratio > 0.8:
                recommendations.append(f'⚠️  Отфильтровано {filtered_out}/{total_results} результатов - возможно слишком строгие пороги')
        
        # Анализ пересечений
        vector_count = len(vector_results)
        bm25_count = len(bm25_results)
        
        if vector_count == 0:
            recommendations.append('🔴 Векторный поиск не дал результатов - проверьте эмбеддинги')
        
        if bm25_count == 0:
            recommendations.append('🔴 BM25 поиск не дал результатов - проверьте токенизацию')
        
        # Анализ качества запроса
        if len(query.split()) < 3:
            recommendations.append('💡 Короткий запрос - рассмотрите расширение запроса')
        
        return recommendations
    
    def test_problematic_query(self, query: str = "Пришли почту Антона") -> DiagnosticResult:
        """Тест проблемного запроса из примера"""
        logger.info(f"🧪 Тестируем проблемный запрос: '{query}'")
        return self.diagnose_query(query, access_level=100)
    
    def print_diagnostic_report(self, result: DiagnosticResult):
        """Печать детального отчета диагностики"""
        print("\n" + "="*80)
        print(f"🔍 ДИАГНОСТИЧЕСКИЙ ОТЧЕТ")
        print("="*80)
        print(f"Запрос: '{result.query}'")
        print(f"Уровень доступа: {result.access_level}")
        print()
        
        # Результаты поиска
        print("📊 РЕЗУЛЬТАТЫ ПОИСКА:")
        print(f"  Векторный поиск: {len(result.vector_results)} результатов")
        print(f"  BM25 поиск: {len(result.bm25_results)} результатов")
        print(f"  После fusion: {len(result.fused_results)} результатов")
        print(f"  После реранжирования: {len(result.reranked_results)} результатов")
        print()
        
        # Скоры реранжирования
        if result.rerank_scores:
            print("🎯 СКОРЫ РЕРАНЖИРОВАНИЯ:")
            print(f"  Лучший: {max(result.rerank_scores):.3f}")
            print(f"  Худший: {min(result.rerank_scores):.3f}")
            print(f"  Средний: {sum(result.rerank_scores)/len(result.rerank_scores):.3f}")
            print(f"  Разброс: {max(result.rerank_scores) - min(result.rerank_scores):.3f}")
            print()
        
        # Пороги
        thresholds = result.thresholds
        print("🚪 ПОРОГИ ФИЛЬТРАЦИИ:")
        print(f"  Высокая релевантность: {thresholds.get('high_relevance', 0):.3f}")
        print(f"  Общий чат: {thresholds.get('general_chat', 0):.3f}")
        print()
        
        # Топ результаты
        print("🏆 ТОП РЕЗУЛЬТАТЫ:")
        for i, result_item in enumerate(result.reranked_results[:3]):
            print(f"  #{i+1} (скор: {result_item.get('rerank_score', 0):.3f})")
            content = result_item.get('content', '')[:100] + '...' if len(result_item.get('content', '')) > 100 else result_item.get('content', '')
            print(f"      {content}")
            print()
        
        # Рекомендации
        recommendations = result.diagnostics.get('recommendations', [])
        if recommendations:
            print("💡 РЕКОМЕНДАЦИИ:")
            for rec in recommendations:
                print(f"  {rec}")
            print()
        
        # Проблемы качества
        quality = result.diagnostics.get('quality', {})
        issues = quality.get('issues', [])
        if issues:
            print("⚠️  ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:")
            for issue in issues:
                print(f"  • {issue}")
            print()

def main():
    """Главная функция для запуска диагностики"""
    parser = argparse.ArgumentParser(description='Диагностика поиска и ранжирования')
    parser.add_argument('--query', '-q', type=str, help='Поисковый запрос для диагностики')
    parser.add_argument('--access-level', '-a', type=int, default=100, help='Уровень доступа (по умолчанию 100)')
    parser.add_argument('--test-problematic', '-t', action='store_true', help='Тест проблемного запроса из примера')
    parser.add_argument('--json', '-j', action='store_true', help='Вывод в JSON формате')
    
    args = parser.parse_args()
    
    try:
        diagnostics = SearchDiagnostics()
        
        if args.test_problematic:
            result = diagnostics.test_problematic_query()
        elif args.query:
            result = diagnostics.diagnose_query(args.query, args.access_level)
        else:
            # Интерактивный режим
            query = input("Введите поисковый запрос: ").strip()
            if not query:
                print("Пустой запрос. Выход.")
                return
            result = diagnostics.diagnose_query(query, args.access_level)
        
        if args.json:
            # Вывод в JSON (для программного использования)
            output = {
                'query': result.query,
                'access_level': result.access_level,
                'results_count': len(result.reranked_results),
                'rerank_scores': result.rerank_scores,
                'thresholds': result.thresholds,
                'diagnostics': result.diagnostics
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            # Человекочитаемый отчет
            diagnostics.print_diagnostic_report(result)
        
    except Exception as e:
        logger.error(f"❌ Ошибка диагностики: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
