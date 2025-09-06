#!/usr/bin/env python3
"""
Демонстрация формата чанков, которые попадают в ИИ
"""

import os
import sys
import json
from typing import Dict, Any, List

# Добавляем путь к worker в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.document_analyzer import DocumentStructureAnalyzer
from services.chunking_service import SemanticChunkingService
from processors.docx_processor import DocxProcessor

def demonstrate_chunk_format():
    """Демонстрация того, как чанки выглядят для ИИ"""
    
    # Путь к тестовому документу
    test_file = "../Приказ_об_изменении_должностной_инструкции_копирайтера.docx"
    
    if not os.path.exists(test_file):
        test_file = "test_document.docx"
    
    if not os.path.exists(test_file):
        print("❌ Тестовый документ не найден!")
        return
    
    print("🔍 ДЕМОНСТРАЦИЯ: Как информация попадает в ИИ")
    print("=" * 60)
    
    try:
        # 1. Обработка документа
        processor = DocxProcessor()
        result = processor.process_document(test_file, "demo_doc", 50)
        
        if not result["success"]:
            print(f"❌ Ошибка обработки: {result['error']}")
            return
        
        # 2. Семантический chunking
        chunking_service = SemanticChunkingService()
        
        # Преобразуем секции в объекты
        from services.document_analyzer import DocumentSection
        sections_objects = []
        for section_data in result["document_sections"]:
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
            result["text"],
            "demo_doc",
            50,
            document_sections=sections_objects,
            document_metadata=result["document_metadata"]
        )
        
        print(f"📄 Документ обработан: {len(chunks_data)} чанков")
        print()
        
        # 3. Показываем, что попадает в ИИ
        print("🤖 ЧТО ВИДИТ ИИ ПРИ ПОИСКЕ:")
        print("=" * 60)
        
        for i, chunk in enumerate(chunks_data[:3]):  # Показываем первые 3 чанка
            print(f"\n📝 ЧАНК {i+1}:")
            print("-" * 40)
            
            # Текст чанка (основное содержимое)
            print("🔤 ТЕКСТ ЧАНКА (то, что ищется):")
            print(f'"{chunk["text"]}"')
            print()
            
            # Метаданные (контекст для ИИ)
            metadata = chunk["metadata"]
            print("📋 МЕТАДАННЫЕ (контекст для ИИ):")
            
            # Структурная информация
            print(f"  📂 Секция: {metadata.get('section_title', 'N/A')}")
            print(f"  🏷️  Тип секции: {metadata.get('section_type', 'N/A')}")
            print(f"  📊 Уровень: {metadata.get('section_level', 'N/A')}")
            print(f"  🧩 Тип чанка: {metadata.get('chunk_type', 'N/A')}")
            print(f"  ✅ Полная секция: {metadata.get('is_complete_section', False)}")
            
            # Информация о документе
            print(f"  📄 Тип документа: {metadata.get('document_type', 'N/A')}")
            print(f"  📋 Название: {metadata.get('document_title', 'N/A')}")
            print(f"  🔢 Номер: {metadata.get('document_number', 'N/A')}")
            print(f"  📅 Дата: {metadata.get('document_date', 'N/A')}")
            print(f"  🏢 Организация: {metadata.get('document_organization', 'N/A')}")
            
            # Технические метаданные
            print(f"  📏 Размер: {metadata.get('char_count', 0)} символов")
            print(f"  🔐 Уровень доступа: {metadata.get('access_level', 'N/A')}")
            print(f"  📍 Позиция: {metadata.get('chunk_index', 0)}/{metadata.get('total_chunks', 0)}")
            
            print()
        
        # 4. Демонстрация контекста для ИИ
        print("\n🎯 КОНТЕКСТ ДЛЯ ИИ ПРИ ОТВЕТЕ:")
        print("=" * 60)
        
        # Симулируем, как формируется контекст для ИИ
        context_parts = []
        for i, chunk in enumerate(chunks_data[:2]):
            metadata = chunk["metadata"]
            doc_title = metadata.get("document_title", "Документ")
            section_title = metadata.get("section_title", "")
            
            # Формат контекста, который видит ИИ
            if section_title and section_title != doc_title:
                context_part = f"[Источник {i+1}: {doc_title} - {section_title}]\n{chunk['text']}"
            else:
                context_part = f"[Источник {i+1}: {doc_title}]\n{chunk['text']}"
            
            context_parts.append(context_part)
        
        full_context = "\n\n".join(context_parts)
        
        print("📝 ИТОГОВЫЙ КОНТЕКСТ:")
        print(f'"""\n{full_context}\n"""')
        
        # 5. Статистика
        print(f"\n📊 СТАТИСТИКА ОБРАБОТКИ:")
        print("=" * 60)
        stats = chunking_service.get_chunking_stats(chunks_data)
        
        print(f"📄 Всего чанков: {stats['total_chunks']}")
        print(f"📏 Средний размер: {stats['avg_chunk_size']:.0f} символов")
        print(f"📐 Размер от {stats['min_chunk_size']} до {stats['max_chunk_size']} символов")
        print(f"📊 Типы чанков: {stats['chunk_types']}")
        print(f"🏷️  Типы секций: {stats['section_types']}")
        print(f"✅ Полных секций: {stats['complete_sections']}")
        print(f"🧩 Частичных секций: {stats['partial_sections']}")
        
        # 6. Пример JSON для API
        print(f"\n🔌 ПРИМЕР JSON ДЛЯ API:")
        print("=" * 60)
        
        example_chunk = chunks_data[0]
        api_format = {
            "chunk_id": f"{example_chunk['metadata']['doc_id']}_{example_chunk['metadata']['chunk_index']}",
            "text": example_chunk["text"][:200] + "..." if len(example_chunk["text"]) > 200 else example_chunk["text"],
            "metadata": {
                "document_type": example_chunk["metadata"].get("document_type"),
                "document_title": example_chunk["metadata"].get("document_title"),
                "section_title": example_chunk["metadata"].get("section_title"),
                "section_type": example_chunk["metadata"].get("section_type"),
                "chunk_type": example_chunk["metadata"].get("chunk_type"),
                "access_level": example_chunk["metadata"].get("access_level"),
                "similarity_score": 0.85,  # Пример скора
                "rerank_score": 0.92       # Пример скора
            }
        }
        
        print(json.dumps(api_format, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demonstrate_chunk_format()
