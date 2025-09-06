import chromadb

# Подключение к ChromaDB
client = chromadb.HttpClient(host='chromadb', port=8000)
collection = client.get_collection("documents")

# Получение чанка 0
chunk_0 = collection.get(
    where={"chunk_index": 0},
    include=["documents", "metadatas"]
)

if chunk_0['documents']:
    print("=== ПОЛНОЕ СОДЕРЖИМОЕ ЧАНКА 0 ===")
    content = chunk_0['documents'][0]
    print(content)
    print(f"\nДлина чанка: {len(content)} символов")
    print("\n" + "="*60)
    
    # Ищем ключевые фразы
    key_phrases = ["2.3.6", "2.3.7", "копирайтер", "должностной инструкции", "ПРИКАЗЫВАЮ"]
    
    print("ПОИСК КЛЮЧЕВЫХ ФРАЗ:")
    for phrase in key_phrases:
        if phrase in content:
            print(f"✅ '{phrase}' найден в чанке 0")
            # Показываем контекст вокруг найденной фразы
            index = content.find(phrase)
            start = max(0, index - 50)
            end = min(len(content), index + 100)
            context = content[start:end]
            print(f"   Контекст: ...{context}...")
        else:
            print(f"❌ '{phrase}' НЕ найден в чанке 0")
    
else:
    print("Чанк 0 не найден")
