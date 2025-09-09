#!/bin/bash

# Универсальный скрипт запуска локальных ML-сервисов
# Автоматически определяет платформу (macOS/Ubuntu) и запускает соответствующие сервисы
# Запускает embedding и reranker сервисы НА ХОСТЕ (не в Docker)

set -e

echo "🚀 Starting Universal ML Services for Knowledge Base RAG MVP"
echo "============================================================"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Определение платформы
if command -v uname >/dev/null 2>&1; then
    PLATFORM=$(uname -s)
    ARCHITECTURE=$(uname -m)
else
    # Альтернативные способы определения платформы
    if [ -f /etc/os-release ]; then
        PLATFORM="Linux"
        ARCHITECTURE="x86_64"
    else
        PLATFORM="Unknown"
        ARCHITECTURE="Unknown"
    fi
fi

echo -e "${BLUE}🖥️  Platform: $PLATFORM $ARCHITECTURE${NC}"

if [[ "$PLATFORM" == "Darwin" && "$ARCHITECTURE" == "arm64" ]]; then
    echo -e "${GREEN}🍎 Detected Apple Silicon - optimizing for MPS${NC}"
    IS_APPLE_SILICON=true
elif [[ "$PLATFORM" == "Linux" ]] || [[ "$PLATFORM" == "Unknown" ]]; then
    echo -e "${GREEN}🐧 Detected Linux - optimizing for CUDA/CPU${NC}"
    IS_UBUNTU=true
else
    echo -e "${YELLOW}⚠️  Unknown platform - using default settings${NC}"
fi

# Функция для проверки доступности порта
check_port() {
    local port=$1
    local service_name=$2
    
    if command -v lsof >/dev/null 2>&1; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Port $port is already in use (possibly $service_name is already running)${NC}"
            return 1
        else
            echo -e "${GREEN}✅ Port $port is available${NC}"
            return 0
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep ":$port " >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Port $port is already in use (possibly $service_name is already running)${NC}"
            return 1
        else
            echo -e "${GREEN}✅ Port $port is available${NC}"
            return 0
        fi
    else
        echo -e "${YELLOW}⚠️  Cannot check port $port (lsof/netstat not available)${NC}"
        return 0
    fi
}

# Функция для проверки Python окружения
check_python_env() {
    local env_path=$1
    local service_name=$2
    
    if [ ! -d "$env_path" ]; then
        echo -e "${RED}❌ Virtual environment not found: $env_path${NC}"
        echo -e "${BLUE}💡 Create it with: python3 -m venv $env_path${NC}"
        return 1
    fi
    
    if [ ! -f "$env_path/bin/activate" ]; then
        echo -e "${RED}❌ Invalid virtual environment: $env_path${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Virtual environment found for $service_name${NC}"
    return 0
}

# Проверка системных требований
echo -e "${BLUE}🔍 Checking system requirements...${NC}"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3 is available: $(python3 --version)${NC}"

# Проверка портов
echo -e "${BLUE}🔍 Checking ports availability...${NC}"

EMBEDDING_PORT=8003
RERANKER_PORT=8002

set +e  # Временно отключаем set -e
check_port $EMBEDDING_PORT "Embedding Service"
EMBEDDING_PORT_AVAILABLE=$?

check_port $RERANKER_PORT "Reranker Service"
RERANKER_PORT_AVAILABLE=$?
set -e  # Включаем обратно set -e

# Если хотя бы один сервис уже запущен, пропускаем весь запуск ML сервисов
if [ $EMBEDDING_PORT_AVAILABLE -ne 0 ] || [ $RERANKER_PORT_AVAILABLE -ne 0 ]; then
    echo -e "${GREEN}✅ ML services are already running, skipping startup${NC}"
    echo -e "${BLUE}🎯 ML Services Status:${NC}"
    if [ $EMBEDDING_PORT_AVAILABLE -ne 0 ]; then
        echo -e "${GREEN}✅ Embedding Service: Already running on port $EMBEDDING_PORT${NC}"
    fi
    if [ $RERANKER_PORT_AVAILABLE -ne 0 ]; then
        echo -e "${GREEN}✅ Reranker Service: Already running on port $RERANKER_PORT${NC}"
    fi
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${GREEN}🎉 ML Services check completed - services are ready!${NC}"
    echo -e "${BLUE}============================================================${NC}"
    exit 0
fi

# Проверка виртуальных окружений
echo -e "${BLUE}🔍 Checking virtual environments...${NC}"

EMBEDDING_VENV="venv_embedding"
RERANKER_VENV="venv_reranker"

# Создание виртуального окружения для embedding сервиса если не существует
if [ ! -d "$EMBEDDING_VENV" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment for embedding service...${NC}"
    python3 -m venv $EMBEDDING_VENV
    
    echo -e "${YELLOW}📦 Installing embedding service dependencies...${NC}"
    source $EMBEDDING_VENV/bin/activate
    pip install --upgrade pip
    pip install -r requirements_local_embedding.txt
    deactivate
    echo -e "${GREEN}✅ Embedding service environment ready${NC}"
else
    check_python_env $EMBEDDING_VENV "Embedding Service"
fi

# Создание виртуального окружения для reranker сервиса если не существует
if [ ! -d "$RERANKER_VENV" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment for reranker service...${NC}"
    python3 -m venv $RERANKER_VENV
    
    echo -e "${YELLOW}📦 Installing reranker service dependencies...${NC}"
    source $RERANKER_VENV/bin/activate
    pip install --upgrade pip
    pip install -r requirements_local_reranker.txt
    deactivate
    echo -e "${GREEN}✅ Reranker service environment ready${NC}"
    RERANKER_ENV_OK=0
else
    check_python_env $RERANKER_VENV "Reranker Service"
    RERANKER_ENV_OK=$?
fi

# Запуск сервисов
echo -e "${BLUE}🚀 Starting ML services...${NC}"

# Функция для запуска сервиса в фоне
start_service() {
    local service_name=$1
    local venv_path=$2
    local script_path=$3
    local port=$4
    local log_file=$5
    
    echo -e "${YELLOW}🔄 Starting $service_name on port $port...${NC}"
    
    # Создаем директорию для логов если не существует
    mkdir -p logs
    
    # Полные пути к файлам
    local full_log_path="logs/$log_file"
    local pid_file="logs/$(echo $service_name | tr '[:upper:]' '[:lower:]')_service.pid"
    
    # Активируем виртуальное окружение и запускаем сервис
    (
        source $venv_path/bin/activate
        python $script_path > "$full_log_path" 2>&1 &
        echo $! > "$pid_file"
    )
    
    # Ждем инициализации и загрузки модели
    echo -e "${BLUE}⏳ Waiting for $service_name to initialize (loading model...)${NC}"
    local max_attempts=60  # 5 минут на загрузку модели
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        # Проверяем, что процесс еще жив
        local pid=$(cat "$pid_file" 2>/dev/null || echo "")
        if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
            echo -e "${RED}❌ $service_name process died during startup${NC}"
            echo -e "${BLUE}📋 Check logs: $log_file${NC}"
            return 1
        fi
        
        # Проверяем, что порт открыт
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln | grep ":$port " >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name started successfully on port $port${NC}"
            echo -e "${BLUE}📋 Logs: $log_file${NC}"
            return 0
        fi
        
        # Показываем прогресс
        if [ $((attempt % 10)) -eq 0 ]; then
            echo -e "${YELLOW}⏳ Still loading model... ($attempt/${max_attempts})${NC}"
        else
            echo -n "."
        fi
        
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start within $((max_attempts * 5)) seconds${NC}"
    echo -e "${BLUE}📋 Check logs: $log_file${NC}"
    return 1
}

# Запуск Embedding Service
if [ $EMBEDDING_PORT_AVAILABLE -eq 0 ]; then
    start_service "Embedding" $EMBEDDING_VENV "local_embedding_server.py" $EMBEDDING_PORT "embedding_service.log"
    EMBEDDING_STARTED=$?
else
    echo -e "${YELLOW}⏭️  Skipping Embedding Service (port in use)${NC}"
    EMBEDDING_STARTED=0
fi

# Запуск Reranker Service
if [ $RERANKER_PORT_AVAILABLE -eq 0 ] && [ $RERANKER_ENV_OK -eq 0 ]; then
    start_service "Reranker" $RERANKER_VENV "local_reranker_server.py" $RERANKER_PORT "reranker_service.log"
    RERANKER_STARTED=$?
else
    echo -e "${YELLOW}⏭️  Skipping Reranker Service (port in use or env not ready)${NC}"
    RERANKER_STARTED=0
fi

# Итоговый статус
echo -e "${BLUE}============================================================"
echo -e "🎯 ML Services Status ($PLATFORM $ARCHITECTURE):"
echo -e "============================================================${NC}"

if [ $EMBEDDING_STARTED -eq 0 ]; then
    echo -e "${GREEN}✅ Embedding Service: Running on http://0.0.0.0:$EMBEDDING_PORT${NC}"
    echo -e "   📊 Health check: curl http://127.0.0.1:$EMBEDDING_PORT/health"
    echo -e "   📋 Logs: tail -f logs/embedding_service.log"
else
    echo -e "${RED}❌ Embedding Service: Failed to start${NC}"
fi

if [ $RERANKER_STARTED -eq 0 ]; then
    echo -e "${GREEN}✅ Reranker Service: Running on http://0.0.0.0:$RERANKER_PORT${NC}"
    echo -e "   📊 Health check: curl http://127.0.0.1:$RERANKER_PORT/health"
    echo -e "   📋 Logs: tail -f logs/reranker_service.log"
else
    echo -e "${RED}❌ Reranker Service: Failed to start${NC}"
fi

echo -e "${BLUE}============================================================${NC}"

# Проверка здоровья сервисов
echo -e "${BLUE}🔍 Health checks...${NC}"

if [ $EMBEDDING_STARTED -eq 0 ]; then
    sleep 3
    if curl -s http://127.0.0.1:$EMBEDDING_PORT/health > /dev/null; then
        echo -e "${GREEN}✅ Embedding Service health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Embedding Service health check failed (may still be starting)${NC}"
    fi
fi

if [ $RERANKER_STARTED -eq 0 ]; then
    sleep 3
    if curl -s http://127.0.0.1:$RERANKER_PORT/health > /dev/null; then
        echo -e "${GREEN}✅ Reranker Service health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Reranker Service health check failed (may still be starting)${NC}"
    fi
fi

echo -e "${BLUE}============================================================"
echo -e "${GREEN}🎉 Universal ML Services startup completed on $PLATFORM!${NC}"
echo -e "${BLUE}💡 Your gpt-oss-20b model should be running on port 8000${NC}"
echo -e "${BLUE}💡 Now you can start Docker services with:${NC}"
if [ "$IS_UBUNTU" = true ]; then
    echo -e "${BLUE}   cd deployment && docker-compose -f docker-compose.prod.yml up -d${NC}"
else
    echo -e "${BLUE}   docker-compose up -d${NC}"
fi
echo -e "${BLUE}🛑 To stop ML services, run: ./stop_ml_services.sh${NC}"
echo -e "${BLUE}============================================================${NC}"
