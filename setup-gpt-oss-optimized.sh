#!/bin/bash

# Скрипт для настройки оптимизированной модели gpt-oss-20b для M4 Pro
echo "🚀 Настройка оптимизированной модели gpt-oss-20b для M4 Pro..."

# Настройка переменных окружения Ollama для максимальной производительности
echo "⚙️ Настройка переменных окружения Ollama..."

# Flash Attention для снижения потребления памяти
launchctl setenv OLLAMA_FLASH_ATTENTION 1

# KV-кэш квантование для экономии памяти на длинных контекстах
launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0

# Конкурентность для RAG (2 параллельных запроса безопасно для 48GB)
launchctl setenv OLLAMA_NUM_PARALLEL 2

# Максимум 2 модели в памяти (LLM + реранкер)
launchctl setenv OLLAMA_MAX_LOADED_MODELS 2

echo "✅ Переменные окружения настроены:"
echo "   OLLAMA_FLASH_ATTENTION=1"
echo "   OLLAMA_KV_CACHE_TYPE=q8_0"
echo "   OLLAMA_NUM_PARALLEL=2"
echo "   OLLAMA_MAX_LOADED_MODELS=2"

# Проверяем, что переменные установлены
echo ""
echo "🔍 Проверка переменных окружения:"
echo "OLLAMA_FLASH_ATTENTION: $(launchctl getenv OLLAMA_FLASH_ATTENTION)"
echo "OLLAMA_KV_CACHE_TYPE: $(launchctl getenv OLLAMA_KV_CACHE_TYPE)"
echo "OLLAMA_NUM_PARALLEL: $(launchctl getenv OLLAMA_NUM_PARALLEL)"
echo "OLLAMA_MAX_LOADED_MODELS: $(launchctl getenv OLLAMA_MAX_LOADED_MODELS)"

# Проверяем, что Ollama запущен
echo ""
echo "🔍 Проверка доступности Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama доступен на localhost:11434"
else
    echo "❌ Ollama недоступен. Запустите Ollama и попробуйте снова."
    echo "   Команда: ollama serve"
    exit 1
fi

# Проверяем, есть ли базовая модель gpt-oss:20b
echo ""
echo "📥 Проверка базовой модели gpt-oss:20b..."
if ollama list | grep -q "gpt-oss:20b"; then
    echo "✅ Базовая модель gpt-oss:20b найдена"
else
    echo "📥 Скачивание базовой модели gpt-oss:20b..."
    ollama pull gpt-oss:20b
    
    if [ $? -eq 0 ]; then
        echo "✅ Модель gpt-oss:20b успешно скачана"
    else
        echo "❌ Ошибка при скачивании модели gpt-oss:20b"
        exit 1
    fi
fi

# Создаем оптимизированную модель
echo ""
echo "🔧 Создание оптимизированной модели gpt-oss-rag-optimized..."
ollama create gpt-oss-rag-optimized -f Modelfile-gpt-oss-optimized

if [ $? -eq 0 ]; then
    echo "✅ Модель gpt-oss-rag-optimized создана успешно"
else
    echo "❌ Ошибка при создании оптимизированной модели"
    exit 1
fi

# Проверяем созданную модель
echo ""
echo "📋 Список доступных моделей:"
ollama list

# Тестируем модель
echo ""
echo "🧪 Тестирование оптимизированной модели..."
echo "Отправляем тестовый запрос..."

start_time=$(date +%s%N)
test_response=$(ollama run gpt-oss-rag-optimized "Привет! Как дела?" 2>&1)
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))

echo "Ответ модели: $test_response"
echo "⚡ Время ответа: ${duration}ms"

# Оценка производительности
if [ $duration -lt 2000 ]; then
    echo "🚀 ОТЛИЧНО! Модель работает очень быстро (< 2 сек)"
elif [ $duration -lt 5000 ]; then
    echo "✅ ХОРОШО! Модель работает быстро (< 5 сек)"
elif [ $duration -lt 10000 ]; then
    echo "⚠️  ПРИЕМЛЕМО! Модель работает нормально (< 10 сек)"
else
    echo "🐌 МЕДЛЕННО! Возможно, нужна дополнительная оптимизация"
fi

# Тест с более сложным запросом для проверки контекста
echo ""
echo "🧪 Тестирование с длинным контекстом..."
start_time=$(date +%s%N)
complex_response=$(ollama run gpt-oss-rag-optimized "Объясни принципы работы RAG-системы и её преимущества для корпоративного использования. Расскажи про эмбеддинги, векторные базы данных и реранжирование результатов." 2>&1)
end_time=$(date +%s%N)
complex_duration=$(( (end_time - start_time) / 1000000 ))

echo "⚡ Время ответа на сложный запрос: ${complex_duration}ms"

if [ $complex_duration -lt 10000 ]; then
    echo "🚀 ОТЛИЧНО! Модель быстро обрабатывает сложные запросы"
elif [ $complex_duration -lt 20000 ]; then
    echo "✅ ХОРОШО! Модель справляется со сложными запросами"
else
    echo "⚠️  Сложные запросы обрабатываются медленно"
fi

echo ""
echo "🎉 НАСТРОЙКА ЗАВЕРШЕНА!"
echo ""
echo "📊 ОЖИДАЕМАЯ ПРОИЗВОДИТЕЛЬНОСТЬ НА M4 PRO (48GB RAM):"
echo "   • Первый токен: 50-150ms"
echo "   • Скорость генерации: 25-35 токенов/сек"
echo "   • RAM использование: 12-15GB"
echo "   • Контекст: до 32k токенов"
echo "   • Параллельные запросы: 2"
echo ""
echo "🔧 СЛЕДУЮЩИЕ ШАГИ:"
echo "   1. Перезапустите Ollama для применения переменных окружения"
echo "   2. Запустите систему: docker-compose up -d"
echo "   3. Проверьте работу через API: curl http://localhost:8014/api/health"
echo "   4. Откройте фронтенд: http://localhost:8015"
echo ""
echo "💡 МОНИТОРИНГ:"
echo "   • Использование памяти: Activity Monitor -> Memory"
echo "   • Логи Ollama: ollama logs"
echo "   • API статус: curl http://localhost:11434/api/tags"
echo ""
echo "⚠️  ВАЖНО: Для применения переменных окружения может потребоваться:"
echo "   • Перезапуск Ollama: killall ollama && ollama serve"
echo "   • Или перезагрузка системы"
