from flask import Flask, request, jsonify
import logging
from celery.result import AsyncResult
from celery_app import celery_app
from tasks import rag_query, generate_query_embedding_task, rerank_documents_task, health_check

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        result = health_check.delay()
        health_status = result.get(timeout=10)
        return jsonify(health_status), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/api/tasks/rag_query', methods=['POST'])
def create_rag_query_task():
    """Create RAG query task согласно требованиям ТЗ"""
    try:
        data = request.get_json()
        
        if not data or 'query' not in data or 'access_level' not in data:
            return jsonify({
                "error": "Missing required fields: query, access_level"
            }), 400
        
        query = data['query']
        access_level = data['access_level']
        
        # КРИТИЧНО: Валидация access_level согласно ТЗ
        if not isinstance(access_level, int) or access_level < 1 or access_level > 100:
            return jsonify({
                "error": "Invalid access_level. Must be integer between 1 and 100"
            }), 400
        
        # Создание задачи Celery
        task = rag_query.delay(query, access_level)
        
        return jsonify({
            "task_id": task.id,
            "status": "PENDING"
        }), 202
        
    except Exception as e:
        logger.error(f"Error creating RAG query task: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/tasks/<task_id>/result', methods=['GET'])
def get_task_result(task_id):
    """Get task result"""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state == 'PENDING':
            return jsonify({
                "task_id": task_id,
                "state": "PENDING",
                "info": "Task is waiting to be processed"
            }), 200
        elif result.state == 'SUCCESS':
            return jsonify({
                "task_id": task_id,
                "state": "SUCCESS",
                "result": result.result
            }), 200
        elif result.state == 'FAILURE':
            return jsonify({
                "task_id": task_id,
                "state": "FAILURE",
                "info": str(result.info)
            }), 200
        else:
            return jsonify({
                "task_id": task_id,
                "state": result.state,
                "info": str(result.info) if result.info else None
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting task result: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)
