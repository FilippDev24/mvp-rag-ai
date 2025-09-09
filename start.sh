#!/bin/bash

# 🚀 УНИВЕРСАЛЬНЫЙ ЗАПУСК RAG СЕРВИСА В ОДИН КЛИК
# Автоматически определяет окружение (локальное/продакшен) и запускает все компоненты
# Поддерживает macOS (Apple Silicon/Intel) и Ubuntu Linux

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ASCII Art заголовок
echo -e "${CYAN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                    🤖 RAG KNOWLEDGE BASE                     ║
║                   Universal Startup Script                   ║
║                                                              ║
║  🚀 One-click deployment for Local & Production             ║
║  🔧 Auto-detects platform (macOS/Ubuntu)                    ║
║  🐳 Docker + ML Services orchestration                      ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Определение режима запуска
ENVIRONMENT="local"
FORCE_REBUILD=false
SKIP_ML_SERVICES=false
SKIP_DOCKER=false
VERBOSE=false
CLEANUP_DOCKER=false
AGGRESSIVE_CLEANUP=false

# Парсинг аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod|--production)
            ENVIRONMENT="production"
            shift
            ;;
        --local|--dev|--development)
            ENVIRONMENT="local"
            shift
            ;;
        --rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --skip-ml)
            SKIP_ML_SERVICES=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --cleanup)
            CLEANUP_DOCKER=true
            shift
            ;;
        --cleanup-aggressive)
            CLEANUP_DOCKER=true
            AGGRESSIVE_CLEANUP=true
            shift
            ;;
        --help|-h)
            echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
            echo ""
            echo -e "${YELLOW}Options:${NC}"
            echo "  --prod, --production    Run in production mode"
            echo "  --local, --dev          Run in local development mode (default)"
            echo "  --rebuild               Force rebuild Docker images"
            echo "  --skip-ml               Skip ML services startup"
            echo "  --skip-docker           Skip Docker services startup"
            echo "  --cleanup               Clean Docker system before start"
            echo "  --cleanup-aggressive    Aggressive Docker cleanup (includes volumes)"
            echo "  --verbose, -v           Verbose output"
            echo "  --help, -h              Show this help message"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0                      # Local development"
            echo "  $0 --prod               # Production deployment"
            echo "  $0 --local --rebuild    # Local with rebuild"
            echo "  $0 --prod --skip-ml     # Production without ML services"
            echo "  $0 --cleanup            # Clean Docker before start"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Определение платформы
if command -v uname >/dev/null 2>&1; then
    PLATFORM=$(uname -s)
    ARCHITECTURE=$(uname -m)
else
    PLATFORM="Linux"
    ARCHITECTURE="x86_64"
fi

echo -e "${BLUE}🖥️  Platform: $PLATFORM $ARCHITECTURE${NC}"
echo -e "${BLUE}🎯 Environment: $ENVIRONMENT${NC}"
echo -e "${BLUE}📅 Started at: $(date)${NC}"
echo ""

# Функции для логирования
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${PURPLE}🔄 $1${NC}"
}

# Функция для проверки команд
check_command() {
    if command -v $1 &> /dev/null; then
        log_success "$1 is available"
        return 0
    else
        log_error "$1 is not installed"
        return 1
    fi
}

# Функция для проверки порта
check_port() {
    local port=$1
    local service_name=$2
    
    if command -v lsof >/dev/null 2>&1; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_warning "Port $port is already in use ($service_name may be running)"
            return 1
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep ":$port " >/dev/null 2>&1; then
            log_warning "Port $port is already in use ($service_name may be running)"
            return 1
        fi
    fi
    return 0
}

# Функция для ожидания готовности сервиса
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    log_step "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi
        
        if [ $VERBOSE = true ]; then
            echo -n "."
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "$service_name failed to start within $((max_attempts * 2)) seconds"
    return 1
}

# Проверка системных требований
log_step "Checking system requirements..."

REQUIREMENTS_OK=true

# Проверка Docker
if ! check_command docker; then
    log_error "Docker is required. Install from https://docker.com"
    REQUIREMENTS_OK=false
fi

if ! check_command docker-compose; then
    log_error "Docker Compose is required"
    REQUIREMENTS_OK=false
fi

# Проверка Python для ML сервисов
if [ $SKIP_ML_SERVICES = false ]; then
    if ! check_command python3; then
        log_error "Python 3 is required for ML services"
        REQUIREMENTS_OK=false
    fi
fi

# Проверка curl
if ! check_command curl; then
    log_warning "curl is recommended for health checks"
fi

if [ $REQUIREMENTS_OK = false ]; then
    log_error "System requirements not met. Please install missing components."
    exit 1
fi

# Создание .env файла если не существует
if [ $ENVIRONMENT = "production" ]; then
    ENV_FILE="deployment/.env.prod"
    COMPOSE_FILE="deployment/docker-compose.prod.yml"
else
    ENV_FILE=".env"
    COMPOSE_FILE="docker-compose.yml"
    
    if [ ! -f "$ENV_FILE" ]; then
        log_step "Creating local .env file from template..."
        cp .env.example .env
        log_success "Created .env file. Please review and update if needed."
    fi
fi

if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
    exit 1
fi

# Docker очистка (если требуется)
if [ $CLEANUP_DOCKER = true ]; then
    log_step "Cleaning Docker system before start..."
    
    if [ -f "cleanup-docker.sh" ]; then
        chmod +x cleanup-docker.sh
        if [ $AGGRESSIVE_CLEANUP = true ]; then
            ./cleanup-docker.sh --aggressive --force
        else
            ./cleanup-docker.sh --force
        fi
        log_success "Docker cleanup completed"
    else
        log_warning "cleanup-docker.sh not found, skipping cleanup"
    fi
    
    echo ""
fi

# Создание директорий
log_step "Creating required directories..."
mkdir -p backend/logs
mkdir -p backend/uploads
mkdir -p worker/uploads
mkdir -p logs
log_success "Directories created"

# Запуск ML сервисов (если не пропускаем)
if [ $SKIP_ML_SERVICES = false ]; then
    log_step "Starting ML services..."
    
    if [ -f "start_ml_services.sh" ]; then
        chmod +x start_ml_services.sh
        ./start_ml_services.sh
        
        # Ждем готовности ML сервисов
        sleep 5
        
        # Проверяем embedding service
        if check_port 8003 "Embedding Service"; then
            log_warning "Embedding service may not be running"
        else
            wait_for_service "http://127.0.0.1:8003/health" "Embedding Service" 15
        fi
        
        # Проверяем reranker service
        if check_port 8002 "Reranker Service"; then
            log_warning "Reranker service may not be running"
        else
            wait_for_service "http://127.0.0.1:8002/health" "Reranker Service" 15
        fi
        
    else
        log_warning "start_ml_services.sh not found, skipping ML services"
    fi
else
    log_info "Skipping ML services startup (--skip-ml flag)"
fi

# Запуск Docker сервисов (если не пропускаем)
if [ $SKIP_DOCKER = false ]; then
    log_step "Starting Docker services..."
    
    # Определяем команду docker-compose
    DOCKER_COMPOSE_CMD="docker-compose"
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        log_error "Neither 'docker-compose' nor 'docker compose' is available"
        exit 1
    fi
    
    # Переходим в нужную директорию для продакшена
    if [ $ENVIRONMENT = "production" ]; then
        cd deployment
        COMPOSE_FILE="docker-compose.prod.yml"
    else
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Останавливаем существующие контейнеры
    log_step "Stopping existing containers..."
    $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE down --remove-orphans
    
    # Пересборка образов если требуется
    if [ $FORCE_REBUILD = true ]; then
        log_step "Rebuilding Docker images..."
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE build --no-cache
    fi
    
    # Запуск сервисов
    log_step "Starting Docker services..."
    if [ $VERBOSE = true ]; then
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d
    else
        $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE up -d > /dev/null 2>&1
    fi
    
    # Возвращаемся в корневую директорию
    if [ $ENVIRONMENT = "production" ]; then
        cd ..
    fi
    
    log_success "Docker services started"
    
    # Ждем готовности основных сервисов
    log_step "Waiting for services to be ready..."
    
    # Определяем порты в зависимости от окружения
    if [ $ENVIRONMENT = "production" ]; then
        BACKEND_PORT=3001
        FRONTEND_PORT=3000
        POSTGRES_PORT=5432
        REDIS_PORT=6379
        CHROMADB_PORT=8012
    else
        BACKEND_PORT=8014
        FRONTEND_PORT=8015
        POSTGRES_PORT=8010
        REDIS_PORT=8011
        CHROMADB_PORT=8012
    fi
    
    # Проверяем PostgreSQL (не через HTTP, а через порт)
    log_step "Checking PostgreSQL connection..."
    if command -v nc >/dev/null 2>&1; then
        if nc -z 127.0.0.1 $POSTGRES_PORT 2>/dev/null; then
            log_success "PostgreSQL is ready!"
        else
            log_warning "PostgreSQL may not be ready yet"
        fi
    else
        log_info "PostgreSQL check skipped (nc not available)"
    fi
    
    # Проверяем Redis (не через HTTP, а через порт)
    log_step "Checking Redis connection..."
    if command -v nc >/dev/null 2>&1; then
        if nc -z 127.0.0.1 $REDIS_PORT 2>/dev/null; then
            log_success "Redis is ready!"
        else
            log_warning "Redis may not be ready yet"
        fi
    else
        log_info "Redis check skipped (nc not available)"
    fi
    
    # Ждем ChromaDB
    wait_for_service "http://127.0.0.1:$CHROMADB_PORT/api/v1/heartbeat" "ChromaDB" 20
    
    # Ждем Backend
    wait_for_service "http://127.0.0.1:$BACKEND_PORT/api/health" "Backend API" 30
    
    # Ждем Frontend
    wait_for_service "http://127.0.0.1:$FRONTEND_PORT" "Frontend" 20
    
else
    log_info "Skipping Docker services startup (--skip-docker flag)"
fi

# Финальная проверка статуса
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    🎉 STARTUP COMPLETE                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_success "RAG Knowledge Base is ready!"
echo ""

# Показываем доступные сервисы
echo -e "${BLUE}📋 Available Services:${NC}"
echo ""

if [ $SKIP_ML_SERVICES = false ]; then
    echo -e "${GREEN}🤖 ML Services (Host):${NC}"
    echo "   • Embedding Service:  http://127.0.0.1:8003"
    echo "   • Reranker Service:   http://127.0.0.1:8002"
    if [ $ENVIRONMENT = "production" ]; then
        echo "   • vLLM (gpt-oss-20b): http://127.0.0.1:8000"
    else
        echo "   • Ollama:             http://127.0.0.1:11434"
    fi
    echo ""
fi

if [ $SKIP_DOCKER = false ]; then
    echo -e "${GREEN}🐳 Docker Services:${NC}"
    if [ $ENVIRONMENT = "production" ]; then
        echo "   • Frontend:           http://127.0.0.1:3000"
        echo "   • Backend API:        http://127.0.0.1:3001"
        echo "   • PostgreSQL:         127.0.0.1:5432"
        echo "   • Redis:              127.0.0.1:6379"
        echo "   • ChromaDB:           http://127.0.0.1:8012"
    else
        echo "   • Frontend:           http://127.0.0.1:8015"
        echo "   • Backend API:        http://127.0.0.1:8014"
        echo "   • PostgreSQL:         127.0.0.1:8010"
        echo "   • Redis:              127.0.0.1:8011"
        echo "   • ChromaDB:           http://127.0.0.1:8012"
    fi
    echo ""
fi

# Полезные команды
echo -e "${BLUE}🛠️  Useful Commands:${NC}"
echo "   • View logs:          docker-compose logs -f [service]"
echo "   • Stop all:           ./stop.sh"
echo "   • Restart:            ./start.sh --rebuild"
echo "   • Health check:       curl http://127.0.0.1:$BACKEND_PORT/api/health"
echo ""

# Показываем логи если verbose
if [ $VERBOSE = true ]; then
    echo -e "${BLUE}📋 Service Logs:${NC}"
    if [ $SKIP_ML_SERVICES = false ]; then
        echo "   • ML Services:        tail -f logs/*.log"
    fi
    if [ $SKIP_DOCKER = false ]; then
        echo "   • Docker Services:    docker-compose logs -f"
    fi
    echo ""
fi

# Финальное сообщение
echo -e "${GREEN}🚀 Your RAG Knowledge Base is now running in $ENVIRONMENT mode!${NC}"
echo -e "${BLUE}💡 Open your browser and navigate to the frontend URL above${NC}"
echo ""

# Сохраняем информацию о запуске
cat > .startup_info << EOF
ENVIRONMENT=$ENVIRONMENT
PLATFORM=$PLATFORM
ARCHITECTURE=$ARCHITECTURE
STARTED_AT=$(date)
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
ML_SERVICES_ENABLED=$([[ $SKIP_ML_SERVICES == false ]] && echo "true" || echo "false")
DOCKER_SERVICES_ENABLED=$([[ $SKIP_DOCKER == false ]] && echo "true" || echo "false")
EOF

log_success "Startup information saved to .startup_info"
