import chromadb
import numpy as np
from services.embedding_service import EmbeddingService
from services.reranking_service import RerankingService

# Подключение к ChromaDB
client = chromadb.HttpClient(host='chromadb', port=8000)
collection = client.get_collection("documents")

# Получение всех чанков
all_chunks = collection.get(include=["documents", "metadatas"])

if not all_chunks['documents']:
    print("Нет чанков в ChromaDB")
    exit()

print(f"Найдено {len(all_chunks['documents'])} чанков")

# Инициализация сервисов
embedding_service = EmbeddingService()
reranking_service = RerankingService()

# Тестовый запрос
query = "Какие изменения коснулись копирайтера в должностной?"

print(f"\nЗапрос: {query}")
print("="*60)

# 1. Генерация эмбеддинга запроса
query_result = embedding_service.generate_query_embedding(query)
query_embedding = query_result["embedding"]

print(f"Эмбеддинг запроса сгенерирован: {len(query_embedding)} размерность")

# 2. Векторный поиск
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    include=["documents", "metadatas", "distances"]
)

print(f"\nВекторный поиск:")
for i, (doc, metadata, distance) in enumerate(zip(
    results['documents'][0], 
    results['metadatas'][0], 
    results['distances'][0]
)):
    similarity = 1 - distance
    chunk_index = metadata.get('chunk_index', i)
    print(f"Чанк {chunk_index}: similarity = {similarity:.3f} (distance = {distance:.3f})")
    print(f"  Первые 150 символов: {doc[:150]}...")
    print()

# 3. Реранжирование
documents = results['documents'][0]
reranked = reranking_service.rerank_results(query, documents, top_k=10)

print(f"Реранжирование:")
for result in reranked:
    original_index = result['index']
    metadata = results['metadatas'][0][original_index]
    chunk_index = metadata.get('chunk_index', original_index)
    print(f"Чанк {chunk_index}: rerank_score = {result['score']:.3f}")
    print(f"  Первые 150 символов: {result['document'][:150]}...")
    print()

# 4. Проверка порогов
print("АНАЛИЗ ПОРОГОВ:")
print(f"Текущий HIGH_RELEVANCE_THRESHOLD = 0.35 (BGE-reranker-v2-m3)")
print(f"Модель: BAAI/bge-reranker-v2-m3 (мультиязычная)")
print()

for result in reranked:
    score = result['score']
    original_index = result['index']
    metadata = results['metadatas'][0][original_index]
    chunk_index = metadata.get('chunk_index', original_index)
    
    if score >= 0.35:
        status = "✅ ПРОХОДИТ текущий порог 0.35"
    elif score >= 0.25:
        status = "⚠️  ПРОХОДИТ минимальный порог 0.25"
    else:
        status = "❌ НЕ ПРОХОДИТ даже 0.25"
    
    print(f"Чанк {chunk_index}: {score:.3f} - {status}")
