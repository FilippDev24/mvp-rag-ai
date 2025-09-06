#!/bin/bash

# Скрипт остановки локальных ML-сервисов

set -e

echo "🛑 Stopping Local ML Services for Knowledge Base RAG MVP"
echo "=================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для остановки сервиса по PID файлу
stop_service() {
    local service_name=$1
    local pid_file="${service_name,,}_service.pid"
    local port=$2
    
    echo -e "${BLUE}🔄 Stopping $service_name...${NC}"
    
    # Проверяем наличие PID файла
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        
        # Проверяем, что процесс еще запущен
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${YELLOW}📋 Found $service_name process (PID: $pid)${NC}"
            
            # Отправляем SIGTERM
            kill $pid
            
            # Ждем завершения процесса
            local count=0
            while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
                sleep 1
                count=$((count + 1))
                echo -e "${YELLOW}⏳ Waiting for $service_name to stop... ($count/10)${NC}"
            done
            
            # Если процесс все еще запущен, принудительно завершаем
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️  Force killing $service_name process${NC}"
                kill -9 $pid
                sleep 1
            fi
            
            # Проверяем результат
            if ! ps -p $pid > /dev/null 2>&1; then
                echo -e "${GREEN}✅ $service_name stopped successfully${NC}"
                rm -f "$pid_file"
            else
                echo -e "${RED}❌ Failed to stop $service_name${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  $service_name process not found (PID: $pid)${NC}"
            rm -f "$pid_file"
        fi
    else
        echo -e "${YELLOW}⚠️  No PID file found for $service_name${NC}"
    fi
    
    # Дополнительная проверка по порту
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Port $port is still in use, trying to kill process...${NC}"
        local port_pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        if [ ! -z "$port_pid" ]; then
            kill $port_pid 2>/dev/null || kill -9 $port_pid 2>/dev/null
            sleep 1
            
            if ! lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
                echo -e "${GREEN}✅ Port $port freed${NC}"
            else
                echo -e "${RED}❌ Port $port is still in use${NC}"
            fi
        fi
    else
        echo -e "${GREEN}✅ Port $port is free${NC}"
    fi
}

# Остановка сервисов
EMBEDDING_PORT=8003
RERANKER_PORT=8002

stop_service "Embedding" $EMBEDDING_PORT
stop_service "Reranker" $RERANKER_PORT

# Очистка логов (опционально)
echo -e "${BLUE}🧹 Cleaning up...${NC}"

if [ -f "embedding_service.log" ]; then
    echo -e "${YELLOW}📋 Embedding service log size: $(du -h embedding_service.log | cut -f1)${NC}"
    echo -e "${BLUE}💡 To view logs: cat embedding_service.log${NC}"
fi

if [ -f "reranker_service.log" ]; then
    echo -e "${YELLOW}📋 Reranker service log size: $(du -h reranker_service.log | cut -f1)${NC}"
    echo -e "${BLUE}💡 To view logs: cat reranker_service.log${NC}"
fi

# Итоговый статус
echo -e "${BLUE}=================================================="
echo -e "🎯 Final Status:"
echo -e "=================================================="

# Проверка портов
if ! lsof -Pi :$EMBEDDING_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Embedding Service (port $EMBEDDING_PORT): Stopped${NC}"
else
    echo -e "${RED}❌ Embedding Service (port $EMBEDDING_PORT): Still running${NC}"
fi

if ! lsof -Pi :$RERANKER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Reranker Service (port $RERANKER_PORT): Stopped${NC}"
else
    echo -e "${RED}❌ Reranker Service (port $RERANKER_PORT): Still running${NC}"
fi

echo -e "${BLUE}=================================================="
echo -e "${GREEN}🎉 ML Services shutdown completed!${NC}"
echo -e "${BLUE}💡 To start services again, run: ./start_ml_services.sh${NC}"
echo -e "${BLUE}=================================================="
