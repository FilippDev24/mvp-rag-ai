import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Celery instance
celery_app = Celery(
    'knowledge_base_worker',
    broker=os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/0')),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['tasks']
)

# КРИТИЧНО: Явно устанавливаем result_backend из переменной окружения
celery_app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # ИСПРАВЛЕНИЕ: Добавляем настройки для предотвращения зависания
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    result_expires=3600,  # Результаты хранятся 1 час
)

# Explicit queue declarations
celery_app.conf.task_queues = {
    'celery': {
        'exchange': 'celery',
        'exchange_type': 'direct',
        'routing_key': 'celery',
    },
    'document_processing': {
        'exchange': 'document_processing',
        'exchange_type': 'direct',
        'routing_key': 'document_processing',
    },
    'embeddings': {
        'exchange': 'embeddings',
        'exchange_type': 'direct',
        'routing_key': 'embeddings',
    },
    'queries': {
        'exchange': 'queries',
        'exchange_type': 'direct',
        'routing_key': 'queries',
    },
}

# Task routing
celery_app.conf.task_routes = {
    'tasks.process_document': {'queue': 'document_processing'},
    'tasks.delete_document': {'queue': 'document_processing'},
    'tasks.extract_keywords_for_existing_chunks': {'queue': 'document_processing'},
    'tasks.health_check': {'queue': 'document_processing'},
    'tasks.generate_embeddings': {'queue': 'embeddings'},
    'tasks.query_knowledge_base': {'queue': 'queries'},
    'tasks.rag_query': {'queue': 'queries'},
    'tasks.hybrid_search': {'queue': 'queries'},
    'tasks.rerank_documents_task': {'queue': 'queries'},
}

if __name__ == '__main__':
    celery_app.start()
