import chromadb
import os

# Подключение к ChromaDB
chroma_host = 'localhost'
chroma_port = '8012'

client = chromadb.HttpClient(
    host=chroma_host,
    port=int(chroma_port)
)

# Получение коллекции
collection = client.get_collection("documents")

# Получение всех чанков
all_chunks = collection.get(include=["documents", "metadatas"])

print(f"Всего чанков в ChromaDB: {len(all_chunks['ids'])}")
print(f"IDs чанков: {all_chunks['ids']}")

# Проверим метаданные
for i, (chunk_id, metadata) in enumerate(zip(all_chunks['ids'], all_chunks['metadatas'])):
    print(f"\nЧанк {i+1}: {chunk_id}")
    print(f"doc_id: {metadata.get('doc_id')}")
    print(f"chunk_index: {metadata.get('chunk_index')}")
    print(f"doc_title: {metadata.get('doc_title')}")
    print(f"Первые 100 символов: {all_chunks['documents'][i][:100]}...")
