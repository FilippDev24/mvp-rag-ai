import chromadb

# Подключение к ChromaDB
client = chromadb.HttpClient(host='chromadb', port=8000)
collection = client.get_collection("documents")

# Получение всех чанков
all_chunks = collection.get()
print(f"Найдено чанков: {len(all_chunks['ids'])}")

if all_chunks['ids']:
    # Удаляем все чанки
    collection.delete(ids=all_chunks['ids'])
    print(f"Удалено {len(all_chunks['ids'])} чанков")
    
    # Проверяем
    remaining = collection.get()
    print(f"Осталось: {len(remaining['ids'])}")
else:
    print("Чанки не найдены")
