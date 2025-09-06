#!/usr/bin/env python3
"""
Простой HTTP сервер для gpt-oss-20b через Transformers
Совместим с OpenAI API для базовых запросов
"""

import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from flask import Flask, request, jsonify
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для модели
model = None
tokenizer = None

def load_model():
    """Загрузка модели gpt-oss-20b"""
    global model, tokenizer
    
    # Используем основную модель для токенизатора
    tokenizer_path = "openai/gpt-oss-20b"
    model_path = "/tmp/gpt-oss-20b/original"
    
    logger.info(f"Загружаем токенизатор из {tokenizer_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path,
        trust_remote_code=True,
        use_fast=False  # Используем медленный токенизатор
    )
    
    logger.info(f"Загружаем модель из {model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    
    logger.info("✅ Модель загружена успешно!")
    logger.info(f"Устройство: {model.device}")
    logger.info(f"Память GPU: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")

@app.route('/v1/models', methods=['GET'])
def list_models():
    """Список доступных моделей"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "openai/gpt-oss-20b",
                "object": "model",
                "created": 1234567890,
                "owned_by": "openai"
            }
        ]
    })

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """OpenAI-совместимый endpoint для чата"""
    try:
        data = request.json
        messages = data.get('messages', [])
        max_tokens = data.get('max_tokens', 512)
        temperature = data.get('temperature', 0.7)
        
        # Формируем промпт из сообщений
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                prompt += f"User: {content}\n"
            elif role == 'assistant':
                prompt += f"Assistant: {content}\n"
        
        prompt += "Assistant:"
        
        # Токенизация
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Генерация
        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        # Декодирование ответа
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        return jsonify({
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.strip()
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": inputs.input_ids.shape[1],
                "completion_tokens": len(tokenizer.encode(response)),
                "total_tokens": inputs.input_ids.shape[1] + len(tokenizer.encode(response))
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok", "model_loaded": model is not None})

if __name__ == '__main__':
    logger.info("🚀 Запуск сервера gpt-oss-20b")
    
    # Загружаем модель
    load_model()
    
    # Запускаем сервер
    app.run(host='0.0.0.0', port=8000, debug=False)
