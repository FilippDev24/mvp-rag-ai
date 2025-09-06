#!/usr/bin/env python3
"""
Тест производительности локального сервера реранжирования
Сравнивает производительность Docker vs Native Apple Silicon
"""

import time
import requests
import json
from typing import List, Dict, Any

def test_local_reranker_performance():
    """Тест производительности локального сервера реранжирования"""
    
    # URL локального сервера
    base_url = "http://127.0.0.1:8002"
    
    # Тестовые данные
    test_query = "Как изменить должностную инструкцию копирайтера?"
    test_documents = [
        "Должностная инструкция копирайтера включает создание текстового контента для различных маркетинговых материалов.",
        "Для изменения должностной инструкции необходимо подготовить приказ об изменении должностной инструкции.",
        "Копирайтер отвечает за написание рекламных текстов, статей для блога и социальных сетей.",
        "Процедура изменения должностной инструкции требует согласования с HR-отделом и руководством.",
        "В обязанности копирайтера входит проведение исследований целевой аудитории и конкурентов.",
        "Приказ об изменении должностной инструкции должен содержать конкретные изменения и дату вступления в силу.",
        "Копирайтер должен владеть навыками SEO-оптимизации и работы с контент-менеджментом.",
        "Изменения в должностной инструкции могут касаться расширения обязанностей или изменения требований.",
        "Копирайтер работает с различными форматами контента: статьи, посты, email-рассылки, лендинги.",
        "Утверждение изменений должностной инструкции происходит через подписание приказа руководителем."
    ]
    
    print("🚀 Тестирование производительности локального сервера реранжирования")
    print(f"📍 URL: {base_url}")
    print(f"🎯 Тестовых документов: {len(test_documents)}")
    print("=" * 80)
    
    # 1. Проверка здоровья сервера
    print("1️⃣ Проверка здоровья сервера...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Сервер здоров: {health_data['device']} ({health_data['torch_version']})")
        else:
            print(f"❌ Сервер недоступен: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Ошибка подключения: {str(e)}")
        print("🔧 Убедитесь, что локальный сервер запущен: python local_reranker_server.py")
        return
    
    # 2. Получение информации о модели
    print("\n2️⃣ Информация о модели...")
    try:
        response = requests.get(f"{base_url}/model-info", timeout=5)
        if response.status_code == 200:
            model_info = response.json()
            print(f"📋 Модель: {model_info['model_name']}")
            print(f"🖥️  Устройство: {model_info['device']}")
            print(f"⚡ Ожидаемая производительность: {model_info['expected_performance']}")
        else:
            print(f"⚠️  Не удалось получить информацию о модели: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Ошибка получения информации о модели: {str(e)}")
    
    # 3. Тест производительности с разным количеством документов
    print("\n3️⃣ Тесты производительности...")
    test_sizes = [5, 10, 20, 30]
    
    results = []
    
    for size in test_sizes:
        print(f"\n📊 Тест с {size} документами:")
        
        # Берем первые N документов
        docs_subset = test_documents[:size]
        
        # Выполняем несколько прогонов для усреднения
        times = []
        server_times = []
        
        for run in range(3):
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{base_url}/rerank",
                    json={
                        "query": test_query,
                        "documents": docs_subset,
                        "top_k": min(10, size)
                    },
                    timeout=30
                )
                
                total_time = time.time() - start_time
                
                if response.status_code == 200:
                    result_data = response.json()
                    server_processing_time = result_data.get("processing_time_ms", 0)
                    device_used = result_data.get("device_used", "unknown")
                    
                    times.append(total_time * 1000)  # в миллисекундах
                    server_times.append(server_processing_time)
                    
                    print(f"   Прогон {run + 1}: {total_time * 1000:.1f}ms (сервер: {server_processing_time:.1f}ms, устройство: {device_used})")
                else:
                    print(f"   ❌ Прогон {run + 1} неудачен: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Прогон {run + 1} ошибка: {str(e)}")
        
        if times:
            avg_total = sum(times) / len(times)
            avg_server = sum(server_times) / len(server_times)
            min_time = min(times)
            max_time = max(times)
            
            results.append({
                "documents": size,
                "avg_total_ms": avg_total,
                "avg_server_ms": avg_server,
                "min_ms": min_time,
                "max_ms": max_time,
                "time_per_doc_ms": avg_server / size
            })
            
            print(f"   📈 Среднее время: {avg_total:.1f}ms (сервер: {avg_server:.1f}ms)")
            print(f"   📈 Время на документ: {avg_server / size:.1f}ms")
            print(f"   📈 Диапазон: {min_time:.1f}ms - {max_time:.1f}ms")
    
    # 4. Итоговая статистика
    print("\n" + "=" * 80)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("=" * 80)
    
    if results:
        print(f"{'Документов':<12} {'Среднее (ms)':<15} {'Сервер (ms)':<15} {'На документ (ms)':<18} {'Оценка'}")
        print("-" * 80)
        
        for result in results:
            # Оценка производительности
            if result["avg_server_ms"] < 300:
                rating = "🚀 ОТЛИЧНО"
            elif result["avg_server_ms"] < 1000:
                rating = "✅ ХОРОШО"
            elif result["avg_server_ms"] < 5000:
                rating = "⚠️  СРЕДНЕ"
            else:
                rating = "❌ МЕДЛЕННО"
            
            print(f"{result['documents']:<12} {result['avg_total_ms']:<15.1f} {result['avg_server_ms']:<15.1f} {result['time_per_doc_ms']:<18.1f} {rating}")
        
        # Лучший результат
        best_result = min(results, key=lambda x: x["avg_server_ms"])
        print(f"\n🏆 Лучший результат: {best_result['avg_server_ms']:.1f}ms для {best_result['documents']} документов")
        
        # Сравнение с ожиданиями
        expected_max = 300  # 300ms для Apple Silicon M4 Pro
        if best_result["avg_server_ms"] <= expected_max:
            improvement = 15000 / best_result["avg_server_ms"]  # Сравнение с 15 секундами в Docker
            print(f"🎯 ЦЕЛЬ ДОСТИГНУТА! Ускорение в {improvement:.0f}x по сравнению с Docker")
        else:
            print(f"⚠️  Производительность ниже ожидаемой ({expected_max}ms)")
    
    print("\n" + "=" * 80)
    print("✅ Тестирование завершено!")

if __name__ == "__main__":
    test_local_reranker_performance()
