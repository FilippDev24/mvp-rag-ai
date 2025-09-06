#!/usr/bin/env python3
"""
Анализатор утечки нерелевантных результатов в контекст LLM
Находит точное место, где нерелевантные чанки проходят фильтрацию
"""

import os
import sys
import json
import time
import logging
from typing import List, Dict, Any, Optional, Set
import re
import numpy as np

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

class ContextLeakAnalyzer:
    """
    Анализатор утечки нерелевантных результатов в контекст LLM
    """
    
    def __init__(self):
        """Инициализация анализатора"""
        self.database_service = None
        self.embedding_service = None
        self.search_service = None
        self.reranking_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Инициализация всех сервисов"""
        try:
            logger.info("🔧 Инициализация сервисов...")
            
            self.database_service = DatabaseService()
            self.embedding_service = EmbeddingService()
            
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
    
    def analyze_context_leak(
        self, 
        query: str, 
        access_level: int = 100,
        expected_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """
        Полный анализ утечки контекста
        
        Args:
            query: Поисковый запрос
            access_level: Уровень доступа
            expected_keywords: Ожидаемые ключевые слова в релевантных результатах
            
        Returns:
            Детальный анализ утечки
        """
        logger.info(f"🔍 Анализ утечки контекста для запроса: '{query}'")
        
        if expected_keywords is None:
            expected_keywords = query.lower().split()
        
        # Инициализируем BM25 если нужно
        self.search_service._ensure_bm25_initialized(access_level)
        
        # 1. Векторный поиск
        logger.info("📊 Этап 1: Векторный поиск...")
        vector_results, embedding_metrics = self.search_service._vector_search(query, access_level, 30)
        vector_analysis = self._analyze_relevance(vector_results, expected_keywords, "Векторный поиск")
        
        # 2. BM25 поиск
        logger.info("📝 Этап 2: BM25 поиск...")
        bm25_results = self.search_service._bm25_search(query, access_level, 30)
        bm25_analysis = self._analyze_relevance(bm25_results, expected_keywords, "BM25 поиск")
        
        # 3. RRF Fusion
        logger.info("🔀 Этап 3: RRF fusion...")
        fused_results = self.search_service._rrf_fusion(vector_results, bm25_results)
        fusion_analysis = self._analyze_relevance(fused_results, expected_keywords, "RRF Fusion")
        
        # 4. Реранжирование БЕЗ фильтрации
        logger.info("🎯 Этап 4: Реранжирование (без фильтрации)...")
        documents = [result["content"] for result in fused_results]
        raw_reranked = self.reranking_service.rerank_results(query, documents, len(documents))
        
        # Сопоставляем с оригинальными результатами
        all_reranked_results = []
        for rerank_result in raw_reranked:
            original_index = rerank_result["index"]
            if original_index < len(fused_results):
                result = fused_results[original_index].copy()
                result.update({
                    "rerank_score": rerank_result["score"],
                    "raw_logit": rerank_result.get("raw_logit", 0),
                })
                all_reranked_results.append(result)
        
        rerank_analysis = self._analyze_relevance(all_reranked_results, expected_keywords, "Реранжирование (все)")
        
        # 5. Применение порогов фильтрации (как в search_service)
        logger.info("🚪 Этап 5: Применение порогов фильтрации...")
        scores = [r["rerank_score"] for r in all_reranked_results]
        
        if scores:
            best_score = max(scores)
            worst_score = min(scores)
            score_range = best_score - worst_score
            
            # Копируем логику из search_service
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
        filter_analysis = self._analyze_relevance(filtered_results, expected_keywords, "После фильтрации")
        
        # 6. Анализ утечки
        leak_analysis = self._detect_leaks(
            query, expected_keywords, vector_analysis, bm25_analysis, 
            fusion_analysis, rerank_analysis, filter_analysis,
            {
                'best_score': best_score,
                'worst_score': worst_score,
                'score_range': score_range,
                'high_threshold': high_threshold,
                'general_threshold': general_threshold
            }
        )
        
        return {
            'query': query,
            'expected_keywords': expected_keywords,
            'stages': {
                'vector': vector_analysis,
                'bm25': bm25_analysis,
                'fusion': fusion_analysis,
                'rerank_all': rerank_analysis,
                'filtered': filter_analysis
            },
            'thresholds': {
                'best_score': best_score,
                'worst_score': worst_score,
                'score_range': score_range,
                'high_threshold': high_threshold,
                'general_threshold': general_threshold
            },
            'leak_analysis': leak_analysis,
            'final_context_results': filtered_results
        }
    
    def _analyze_relevance(
        self, 
        results: List[Dict], 
        expected_keywords: List[str], 
        stage_name: str
    ) -> Dict[str, Any]:
        """Анализ релевантности результатов на каждом этапе"""
        
        if not results:
            return {
                'stage': stage_name,
                'total_results': 0,
                'relevant_results': 0,
                'irrelevant_results': 0,
                'relevance_ratio': 0.0,
                'results_details': []
            }
        
        relevant_count = 0
        irrelevant_count = 0
        results_details = []
        
        for i, result in enumerate(results):
            content = result.get('content', '').lower()
            metadata = result.get('metadata', {})
            
            # Проверяем наличие ожидаемых ключевых слов
            keyword_matches = []
            for keyword in expected_keywords:
                if keyword.lower() in content:
                    keyword_matches.append(keyword)
            
            is_relevant = len(keyword_matches) > 0
            
            if is_relevant:
                relevant_count += 1
            else:
                irrelevant_count += 1
            
            result_detail = {
                'rank': i + 1,
                'id': result.get('id', 'unknown'),
                'document_title': metadata.get('doc_title', 'Неизвестно'),
                'content_preview': content[:200] + '...' if len(content) > 200 else content,
                'is_relevant': is_relevant,
                'keyword_matches': keyword_matches,
                'score': result.get('score', 0),
                'rerank_score': result.get('rerank_score', 0),
                'raw_logit': result.get('raw_logit', 0)
            }
            results_details.append(result_detail)
        
        return {
            'stage': stage_name,
            'total_results': len(results),
            'relevant_results': relevant_count,
            'irrelevant_results': irrelevant_count,
            'relevance_ratio': relevant_count / len(results) if results else 0.0,
            'results_details': results_details
        }
    
    def _detect_leaks(
        self, 
        query: str,
        expected_keywords: List[str],
        vector_analysis: Dict,
        bm25_analysis: Dict,
        fusion_analysis: Dict,
        rerank_analysis: Dict,
        filter_analysis: Dict,
        thresholds: Dict
    ) -> Dict[str, Any]:
        """Обнаружение утечек нерелевантных результатов"""
        
        leaks = []
        warnings = []
        critical_issues = []
        
        # 1. Проверяем утечку на этапе векторного поиска
        if vector_analysis['irrelevant_results'] > vector_analysis['relevant_results']:
            leaks.append({
                'stage': 'vector_search',
                'issue': 'Векторный поиск возвращает больше нерелевантных результатов',
                'irrelevant_count': vector_analysis['irrelevant_results'],
                'relevant_count': vector_analysis['relevant_results'],
                'severity': 'high'
            })
        
        # 2. Проверяем утечку на этапе BM25
        if bm25_analysis['irrelevant_results'] > bm25_analysis['relevant_results']:
            leaks.append({
                'stage': 'bm25_search',
                'issue': 'BM25 поиск возвращает больше нерелевантных результатов',
                'irrelevant_count': bm25_analysis['irrelevant_results'],
                'relevant_count': bm25_analysis['relevant_results'],
                'severity': 'high'
            })
        
        # 3. Проверяем утечку после fusion
        if fusion_analysis['irrelevant_results'] > fusion_analysis['relevant_results']:
            leaks.append({
                'stage': 'rrf_fusion',
                'issue': 'RRF Fusion не улучшает релевантность',
                'irrelevant_count': fusion_analysis['irrelevant_results'],
                'relevant_count': fusion_analysis['relevant_results'],
                'severity': 'medium'
            })
        
        # 4. КРИТИЧНО: Проверяем утечку после реранжирования
        if rerank_analysis['irrelevant_results'] > 0:
            # Находим нерелевантные результаты с высокими скорами
            high_score_irrelevant = [
                r for r in rerank_analysis['results_details'] 
                if not r['is_relevant'] and r['rerank_score'] > 5.0
            ]
            
            if high_score_irrelevant:
                critical_issues.append({
                    'stage': 'reranking',
                    'issue': 'Реранжер дает высокие скоры нерелевантным результатам',
                    'high_score_irrelevant': high_score_irrelevant,
                    'severity': 'critical'
                })
        
        # 5. КРИТИЧНО: Проверяем финальную утечку в контекст
        if filter_analysis['irrelevant_results'] > 0:
            final_irrelevant = [
                r for r in filter_analysis['results_details'] 
                if not r['is_relevant']
            ]
            
            critical_issues.append({
                'stage': 'final_context',
                'issue': 'УТЕЧКА: Нерелевантные результаты попадают в финальный контекст LLM',
                'leaked_results': final_irrelevant,
                'severity': 'critical'
            })
        
        # 6. Проверяем пороги фильтрации
        if thresholds['score_range'] < 1.0:
            warnings.append({
                'stage': 'threshold_calculation',
                'issue': 'Малый разброс скоров может приводить к неправильной фильтрации',
                'score_range': thresholds['score_range'],
                'severity': 'medium'
            })
        
        # 7. Проверяем адаптивность порогов
        if thresholds['high_threshold'] < 3.0:
            warnings.append({
                'stage': 'adaptive_thresholds',
                'issue': 'Слишком низкие адаптивные пороги',
                'high_threshold': thresholds['high_threshold'],
                'severity': 'medium'
            })
        
        return {
            'total_leaks': len(leaks),
            'total_warnings': len(warnings),
            'total_critical': len(critical_issues),
            'leaks': leaks,
            'warnings': warnings,
            'critical_issues': critical_issues,
            'leak_summary': self._generate_leak_summary(leaks, warnings, critical_issues)
        }
    
    def _generate_leak_summary(
        self, 
        leaks: List[Dict], 
        warnings: List[Dict], 
        critical_issues: List[Dict]
    ) -> str:
        """Генерация краткого резюме утечек"""
        
        if critical_issues:
            return f"🔴 КРИТИЧЕСКАЯ УТЕЧКА: {len(critical_issues)} критических проблем обнаружено"
        elif leaks:
            return f"🟡 УТЕЧКА ОБНАРУЖЕНА: {len(leaks)} проблем с релевантностью"
        elif warnings:
            return f"🟡 ПРЕДУПРЕЖДЕНИЯ: {len(warnings)} потенциальных проблем"
        else:
            return "✅ УТЕЧЕК НЕ ОБНАРУЖЕНО: Система фильтрации работает корректно"
    
    def print_leak_report(self, analysis: Dict[str, Any]):
        """Печать детального отчета об утечках"""
        
        print("\n" + "="*80)
        print("🔍 ОТЧЕТ ОБ УТЕЧКЕ НЕРЕЛЕВАНТНЫХ РЕЗУЛЬТАТОВ")
        print("="*80)
        print(f"Запрос: '{analysis['query']}'")
        print(f"Ожидаемые ключевые слова: {analysis['expected_keywords']}")
        print()
        
        # Резюме по этапам
        print("📊 АНАЛИЗ ПО ЭТАПАМ:")
        for stage_name, stage_data in analysis['stages'].items():
            relevance_pct = stage_data['relevance_ratio'] * 100
            print(f"  {stage_data['stage']}: {stage_data['relevant_results']}/{stage_data['total_results']} релевантных ({relevance_pct:.1f}%)")
        print()
        
        # Пороги
        thresholds = analysis['thresholds']
        print("🚪 ПОРОГИ ФИЛЬТРАЦИИ:")
        print(f"  Лучший скор: {thresholds['best_score']:.3f}")
        print(f"  Худший скор: {thresholds['worst_score']:.3f}")
        print(f"  Разброс: {thresholds['score_range']:.3f}")
        print(f"  Порог высокой релевантности: {thresholds['high_threshold']:.3f}")
        print(f"  Порог общего чата: {thresholds['general_threshold']:.3f}")
        print()
        
        # Анализ утечек
        leak_analysis = analysis['leak_analysis']
        print("🚨 АНАЛИЗ УТЕЧЕК:")
        print(f"  {leak_analysis['leak_summary']}")
        print(f"  Критических проблем: {leak_analysis['total_critical']}")
        print(f"  Утечек: {leak_analysis['total_leaks']}")
        print(f"  Предупреждений: {leak_analysis['total_warnings']}")
        print()
        
        # Критические проблемы
        if leak_analysis['critical_issues']:
            print("🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for issue in leak_analysis['critical_issues']:
                print(f"  • {issue['issue']} (этап: {issue['stage']})")
                if 'leaked_results' in issue:
                    for leaked in issue['leaked_results'][:3]:  # Показываем первые 3
                        print(f"    - Ранг #{leaked['rank']}: {leaked['content_preview'][:100]}...")
            print()
        
        # Утечки
        if leak_analysis['leaks']:
            print("🟡 ОБНАРУЖЕННЫЕ УТЕЧКИ:")
            for leak in leak_analysis['leaks']:
                print(f"  • {leak['issue']} (этап: {leak['stage']})")
                print(f"    Нерелевантных: {leak['irrelevant_count']}, Релевантных: {leak['relevant_count']}")
            print()
        
        # Предупреждения
        if leak_analysis['warnings']:
            print("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
            for warning in leak_analysis['warnings']:
                print(f"  • {warning['issue']} (этап: {warning['stage']})")
            print()
        
        # Финальные результаты, попадающие в контекст
        final_results = analysis['final_context_results']
        if final_results:
            print("📋 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ В КОНТЕКСТЕ LLM:")
            for i, result in enumerate(final_results[:5]):  # Показываем первые 5
                metadata = result.get('metadata', {})
                relevance = "✅ Релевантен" if any(kw.lower() in result.get('content', '').lower() for kw in analysis['expected_keywords']) else "❌ Нерелевантен"
                print(f"  #{i+1} (скор: {result.get('rerank_score', 0):.3f}) {relevance}")
                print(f"      Документ: {metadata.get('doc_title', 'Неизвестно')}")
                content_preview = result.get('content', '')[:150] + '...' if len(result.get('content', '')) > 150 else result.get('content', '')
                print(f"      Содержимое: {content_preview}")
                print()

def main():
    """Главная функция для запуска анализа утечек"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Анализ утечки нерелевантных результатов в контекст LLM')
    parser.add_argument('--query', '-q', type=str, default="Пришли почту Антона", help='Поисковый запрос для анализа')
    parser.add_argument('--access-level', '-a', type=int, default=100, help='Уровень доступа')
    parser.add_argument('--keywords', '-k', type=str, nargs='+', help='Ожидаемые ключевые слова (через пробел)')
    parser.add_argument('--json', '-j', action='store_true', help='Вывод в JSON формате')
    
    args = parser.parse_args()
    
    try:
        analyzer = ContextLeakAnalyzer()
        
        expected_keywords = args.keywords if args.keywords else None
        
        analysis = analyzer.analyze_context_leak(
            args.query, 
            args.access_level, 
            expected_keywords
        )
        
        if args.json:
            # Упрощенный JSON вывод
            output = {
                'query': analysis['query'],
                'leak_summary': analysis['leak_analysis']['leak_summary'],
                'critical_issues_count': analysis['leak_analysis']['total_critical'],
                'leaks_count': analysis['leak_analysis']['total_leaks'],
                'final_results_count': len(analysis['final_context_results']),
                'relevance_by_stage': {
                    stage: data['relevance_ratio'] 
                    for stage, data in analysis['stages'].items()
                }
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            analyzer.print_leak_report(analysis)
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа утечек: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
