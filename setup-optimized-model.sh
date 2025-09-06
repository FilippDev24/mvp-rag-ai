#!/bin/bash

# Скрипт для настройки оптимизированной модели Qwen для M4 Pro
echo "🚀 Настройка оптимизированной модели Qwen для M4 Pro..."

# Проверяем, что Docker запущен
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker не запущен. Запустите Docker Desktop и попробуйте снова."
    exit 1
fi

# Запускаем контейнеры
echo "📦 Запуск контейнеров..."
docker-compose up -d ollama

# Ждем запуска Ollama
echo "⏳ Ожидание запуска Ollama..."
sleep 10

# Проверяем доступность Ollama
echo "🔍 Проверка доступности Ollama..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8013/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama доступен!"
        break
    fi
    echo "⏳ Попытка $attempt/$max_attempts..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "❌ Ollama недоступен после $max_attempts попыток"
    exit 1
fi

# Скачиваем базовую модель Qwen
echo "📥 Скачивание базовой модели Qwen 2.5 8B..."
docker exec kb_ollama ollama pull qwen2.5:8b-instruct-q5_K_M

# Создаем оптимизированную модель
echo "🔧 Создание оптимизированной модели для M4 Pro..."
docker exec -i kb_ollama ollama create qwen-m4-optimized -f - < Modelfile

# Проверяем созданную модель
echo "✅ Проверка созданной модели..."
docker exec kb_ollama ollama list

# Тестируем модель
echo "🧪 Тестирование модели..."
echo "Тестовый запрос к модели..."

test_response=$(docker exec kb_ollama ollama run qwen-m4-optimized "Привет! Как дела?" --verbose 2>&1)
echo "Ответ модели: $test_response"

# Измеряем скорость
echo "⚡ Измерение производительности..."
start_time=$(date +%s%N)
docker exec kb_ollama ollama run qwen-m4-optimized "Объясни квантовые вычисления в 50 словах" > /dev/null 2>&1
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))

echo "🎯 Время генерации: ${duration}ms"

if [ $duration -lt 5000 ]; then
    echo "🚀 ОТЛИЧНО! Модель работает быстро (< 5 сек)"
elif [ $duration -lt 10000 ]; then
    echo "✅ ХОРОШО! Модель работает приемлемо (< 10 сек)"
else
    echo "⚠️  МЕДЛЕННО! Возможно, нужна дополнительная оптимизация"
fi

echo ""
echo "🎉 НАСТРОЙКА ЗАВЕРШЕНА!"
echo ""
echo "📊 ОЖИДАЕМАЯ ПРОИЗВОДИТЕЛЬНОСТЬ НА M4 PRO:"
echo "   • Первый токен: 50-100ms"
echo "   • Скорость генерации: 35-45 токенов/сек"
echo "   • RAM использование: 10-12GB"
echo "   • Throughput (4 параллельных): 100-120 токенов/сек"
echo ""
echo "🔧 СЛЕДУЮЩИЕ ШАГИ:"
echo "   1. Запустите полную систему: docker-compose up -d"
echo "   2. Проверьте работу через API: curl http://localhost:8014/api/health"
echo "   3. Откройте фронтенд: http://localhost:8015"
echo ""
echo "💡 МОНИТОРИНГ:"
echo "   • Логи Ollama: docker logs kb_ollama -f"
echo "   • Использование памяти: docker stats kb_ollama"
echo "   • API статус: curl http://localhost:8013/api/tags"
