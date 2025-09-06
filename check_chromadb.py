#!/usr/bin/env python3
import chromadb
import json

try:
    # Подключение к ChromaDB
    client = chromadb.HttpClient(host="localhost", port=8012)
    
    print("=== CHROMADB CONNECTION ===")
    print(f"ChromaDB heartbeat: {client.heartbeat()}")
    
    # Получение коллекций
    collections = client.list_collections()
    print(f"\n=== COLLECTIONS ({len(collections)}) ===")
    for collection in collections:
        print(f"Collection: {collection.name}")
    
    # Проверка коллекции documents
    if collections:
        collection = client.get_collection("documents")
        count = collection.count()
        print(f"\n=== COLLECTION 'documents' ===")
        print(f"Total chunks: {count}")
        
        if count > 0:
            # Получаем первые 5 чанков для проверки
            sample = collection.get(limit=5, include=['documents', 'metadatas'])
            print(f"\n=== SAMPLE CHUNKS ===")
            for i, (doc_id, doc, metadata) in enumerate(zip(sample['ids'], sample['documents'], sample['metadatas'])):
                print(f"\nChunk {i+1}:")
                print(f"  ID: {doc_id}")
                print(f"  Content: {doc[:100]}...")
                print(f"  Doc ID: {metadata.get('doc_id', 'N/A')}")
                print(f"  Access Level: {metadata.get('access_level', 'N/A')}")
                print(f"  Doc Title: {metadata.get('doc_title', 'N/A')}")
            
            # Поиск чанков для документа копирайтера
            print(f"\n=== SEARCH FOR COPYWRITER DOCUMENT ===")
            copywriter_chunks = collection.get(
                where={"doc_id": "aadb4de6-e6e5-4133-84e2-df1aa2f89166"},
                include=['documents', 'metadatas']
            )
            print(f"Found {len(copywriter_chunks['ids'])} chunks for copywriter document")
            
            if copywriter_chunks['ids']:
                for i, (doc_id, doc, metadata) in enumerate(zip(copywriter_chunks['ids'], copywriter_chunks['documents'], copywriter_chunks['metadatas'])):
                    print(f"\nCopywriter Chunk {i+1}:")
                    print(f"  ID: {doc_id}")
                    print(f"  Content: {doc[:150]}...")
                    print(f"  Access Level: {metadata.get('access_level', 'N/A')}")
    else:
        print("No collections found!")

except Exception as e:
    print(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
