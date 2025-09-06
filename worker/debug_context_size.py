import chromadb

# Подключение к ChromaDB
client = chromadb.HttpClient(host='chromadb', port=8000)
collection = client.get_collection("documents")

# Получение чанка 0 (который проходит фильтрацию)
chunk_0 = collection.get(
    where={"chunk_index": 0},
    include=["documents", "metadatas"]
)

if chunk_0['documents']:
    content = chunk_0['documents'][0]
    
    print("=== АНАЛИЗ РАЗМЕРА КОНТЕКСТА ===")
    print(f"Длина чанка 0: {len(content)} символов")
    print(f"Примерное количество токенов: {len(content) // 4} токенов")  # Приблизительно 4 символа = 1 токен
    
    # Проверим что именно отправляется в LLM
    context_for_llm = f"[Источник 1: Приказ_об_изменении_должностной_инструкции_копирайтера]\n{content}\n"
    
    print(f"\nПолный контекст для LLM:")
    print(f"Длина: {len(context_for_llm)} символов")
    print(f"Примерное количество токенов: {len(context_for_llm) // 4} токенов")
    
    print(f"\nПервые 300 символов контекста:")
    print(context_for_llm[:300])
    print("...")
    print(f"\nПоследние 300 символов контекста:")
    print(context_for_llm[-300:])
    
    # Проверим настройки chunking
    print(f"\n=== НАСТРОЙКИ CHUNKING ===")
    print("Из chunking_service.py:")
    print("CHUNK_SIZE = 1000")
    print("CHUNK_OVERLAP = 100") 
    print("MIN_CHUNK_SIZE = 200")
    
    print(f"\n=== РЕКОМЕНДАЦИИ ===")
    if len(content) > 800:
        print("⚠️  Чанк большой (>800 символов)")
        print("💡 Рекомендация: Уменьшить CHUNK_SIZE до 600-800")
    else:
        print("✅ Размер чанка оптимальный")
        
    if len(context_for_llm) > 2000:
        print("⚠️  Контекст для LLM большой (>2000 символов)")
        print("💡 Рекомендация: Обрезать контекст до 1500 символов")
    else:
        print("✅ Размер контекста для LLM приемлемый")

else:
    print("Чанк 0 не найден")
