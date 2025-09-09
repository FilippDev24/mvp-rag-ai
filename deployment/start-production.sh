#!/bin/bash

# 🚀 ПРОДАКШН ЗАПУСК RAG СЕРВИСА С vLLM
# Специализированный скрипт для Ubuntu сервера с GPU поддержкой

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
║                🚀 RAG PRODUCTION DEPLOYMENT                  ║
║                   Ubuntu + GPU + vLLM                       ║
║                                                              ║
║  🐳 Docker orchestration with GPU support                   ║
║  🤖 vLLM gpt-oss-20b model integration                      ║
║  🔧 ML services on host for optimal performance             ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Определение режима запуска
USE_VLLM_CONTAINER=false
FORCE_REBUILD=false
SKIP_ML_SERVICES=false
SKIP_DOCKER=false
VERBOSE=false
CHECK_GPU=true
CLEANUP_DOCKER=false
AGGRESSIVE_CLEANUP=false

# Парсинг аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        --vllm-container)
            USE_VLLM_CONTAINER=true
            shift
            ;;
        --vllm-host)
            USE_VLLM_CONTAINER=false
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
        --skip-gpu-check)
            CHECK_GPU=false
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
            echo "  --vllm-container        Run vLLM inside Docker container (requires GPU)"
            echo "  --vllm-host             Run vLLM on host (default, more stable)"
            echo "  --rebuild               Force rebuild Docker images"
            echo "  --skip-ml               Skip ML services startup"
            echo "  --skip-docker           Skip Docker services startup"
            echo "  --skip-gpu-check        Skip GPU availability check"
            echo "  --cleanup               Clean Docker system before start"
            echo "  --cleanup-aggressive    Aggressive Docker cleanup (includes volumes)"
            echo "  --verbose, -v           Verbose output"
            echo "  --help, -h              Show this help message"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0                      # Standard production deployment"
            echo "  $0 --vllm-container     # Run vLLM in Docker (GPU required)"
            echo "  $0 --rebuild            # Force rebuild all images"
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

echo -e "${BLUE}🖥️  Platform: Ubuntu Linux (Production)${NC}"
echo -e "${BLUE}🎯 vLLM Mode: $([[ $USE_VLLM_CONTAINER == true ]] && echo "Docker Container" || echo "Host Process")${NC}"
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
    
    if command -v ss >/dev/null 2>&1; then
        if ss -tuln | grep ":$port " >/dev/null 2>&1; then
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
log_step "Checking production system requirements..."

REQUIREMENTS_OK=true

# Проверка Ubuntu
if [ ! -f /etc/os-release ] || ! grep -q "Ubuntu" /etc/os-release; then
    log_warning "This script is optimized for Ubuntu Linux"
fi

# Проверка Docker
if ! check_command docker; then
    log_error "Docker is required. Install with: curl -fsSL https://get.docker.com | sh"
    REQUIREMENTS_OK=false
fi

# Проверка Docker Compose
if ! check_command docker-compose && ! docker compose version &> /dev/null; then
    log_error "Docker Compose is required"
    REQUIREMENTS_OK=false
fi

# Проверка NVIDIA Docker (если используем vLLM в контейнере)
if [ $USE_VLLM_CONTAINER = true ] && [ $CHECK_GPU = true ]; then
    if ! command -v nvidia-docker &> /dev/null && ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        log_error "NVIDIA Docker runtime is required for vLLM container"
        log_info "Install with: distribution=\$(. /etc/os-release;echo \$ID\$VERSION_ID) && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - && curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list && sudo apt-get update && sudo apt-get install -y nvidia-docker2 && sudo systemctl restart docker"
        REQUIREMENTS_OK=false
    else
        log_success "NVIDIA Docker runtime is available"
    fi
fi

# Проверка GPU (если нужно)
if [ $CHECK_GPU = true ]; then
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo "")
        if [ -n "$GPU_INFO" ]; then
            log_success "GPU detected: $GPU_INFO"
        else
            log_warning "nvidia-smi available but no GPU detected"
        fi
    else
        log_warning "nvidia-smi not found - GPU support may be limited"
    fi
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
    log_error "curl is required for health checks"
    REQUIREMENTS_OK=false
fi

if [ $REQUIREMENTS_OK = false ]; then
    log_error "System requirements not met. Please install missing components."
    exit 1
fi

# Проверка .env файла
ENV_FILE=".env.prod"
if [ ! -f "$ENV_FILE" ]; then
    log_error "Production environment file not found: $ENV_FILE"
    log_info "Copy and configure: cp .env.prod.example .env.prod"
    exit 1
fi

# Docker очистка (если требуется)
if [ $CLEANUP_DOCKER = true ]; then
    log_step "Cleaning Docker system before production start..."
    
    if [ -f "../cleanup-docker.sh" ]; then
        cd ..
        chmod +x cleanup-docker.sh
        if [ $AGGRESSIVE_CLEANUP = true ]; then
            ./cleanup-docker.sh --aggressive --force
        else
            ./cleanup-docker.sh --force
        fi
        cd deployment
        log_success "Docker cleanup completed"
    else
        log_warning "../cleanup-docker.sh not found, skipping cleanup"
    fi
    
    echo ""
fi

# Создание директорий
log_step "Creating required directories..."
mkdir -p ../backend/logs
mkdir -p ../backend/uploads
mkdir -p ../worker/uploads
mkdir -p ../logs
log_success "Directories created"

# Запуск ML сервисов на хосте (если не пропускаем)
if [ $SKIP_ML_SERVICES = false ]; then
    log_step "Starting ML services on host..."
    
    if [ -f "../start_ml_services.sh" ]; then
        cd ..
        chmod +x start_ml_services.sh
        ./start_ml_services.sh
        cd deployment
        
        # Ждем готовности ML сервисов
        sleep 5
        
        # Проверяем embedding service
        wait_for_service "http://127.0.0.1:8003/health" "Embedding Service" 15 || log_warning "Embedding service may not be ready"
        
        # Проверяем reranker service
        wait_for_service "http://127.0.0.1:8002/health" "Reranker Service" 15 || log_warning "Reranker service may not be ready"
        
    else
        log_warning "../start_ml_services.sh not found, skipping ML services"
    fi
else
    log_info "Skipping ML services startup (--skip-ml flag)"
fi

# Запуск vLLM на хосте (если не используем контейнер)
if [ $USE_VLLM_CONTAINER = false ] && [ $SKIP_ML_SERVICES = false ]; then
    log_step "Checking vLLM service on host..."
    
    if check_port 8000 "vLLM"; then
        log_warning "vLLM may not be running on port 8000"
        log_info "Start vLLM manually with your gpt-oss-20b model"
        log_info "Example: vllm serve openai/gpt-oss-20b --dtype bfloat16 --max-model-len 8192 --host 0.0.0.0 --port 8000"
    else
        wait_for_service "http://127.0.0.1:8000/v1/models" "vLLM" 10 || log_warning "vLLM service may not be ready"
    fi
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
    
    # Выбираем compose файл
    if [ $USE_VLLM_CONTAINER = true ]; then
        COMPOSE_FILE="docker-compose.vllm.yml"
        log_info "Using vLLM container configuration"
    else
        COMPOSE_FILE="docker-compose.prod.yml"
        log_info "Using host vLLM configuration"
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
    
    log_success "Docker services started"
    
    # Ждем готовности основных сервисов
    log_step "Waiting for services to be ready..."
    
    # Ждем PostgreSQL
    wait_for_service "http://127.0.0.1:5432" "PostgreSQL" 30 || true
    
    # Ждем Redis
    wait_for_service "http://127.0.0.1:6379" "Redis" 15 || true
    
    # Ждем ChromaDB
    wait_for_service "http://127.0.0.1:8012/api/v1/heartbeat" "ChromaDB" 20
    
    # Ждем vLLM (если в контейнере)
    if [ $USE_VLLM_CONTAINER = true ]; then
        wait_for_service "http://127.0.0.1:8000/v1/models" "vLLM Container" 60
    fi
    
    # Ждем Backend
    wait_for_service "http://127.0.0.1:3001/api/health" "Backend API" 30
    
    # Ждем Frontend
    wait_for_service "http://127.0.0.1:3000" "Frontend" 20
    
else
    log_info "Skipping Docker services startup (--skip-docker flag)"
fi

# Финальная проверка статуса
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                🎉 PRODUCTION DEPLOYMENT COMPLETE            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_success "RAG Knowledge Base is ready in production mode!"
echo ""

# Показываем доступные сервисы
echo -e "${BLUE}📋 Production Services:${NC}"
echo ""

if [ $SKIP_ML_SERVICES = false ]; then
    echo -e "${GREEN}🤖 ML Services (Host):${NC}"
    echo "   • Embedding Service:  http://127.0.0.1:8003"
    echo "   • Reranker Service:   http://127.0.0.1:8002"
    if [ $USE_VLLM_CONTAINER = true ]; then
        echo "   • vLLM (Container):   http://127.0.0.1:8000"
    else
        echo "   • vLLM (Host):        http://127.0.0.1:8000"
    fi
    echo ""
fi

if [ $SKIP_DOCKER = false ]; then
    echo -e "${GREEN}🐳 Docker Services:${NC}"
    echo "   • Frontend:           http://127.0.0.1:3000"
    echo "   • Backend API:        http://127.0.0.1:3001"
    echo "   • PostgreSQL:         127.0.0.1:5432"
    echo "   • Redis:              127.0.0.1:6379"
    echo "   • ChromaDB:           http://127.0.0.1:8012"
    echo ""
fi

# Полезные команды
echo -e "${BLUE}🛠️  Production Commands:${NC}"
echo "   • View logs:          docker-compose -f $COMPOSE_FILE logs -f [service]"
echo "   • Stop all:           ./stop-production.sh"
echo "   • Restart:            ./start-production.sh --rebuild"
echo "   • Health check:       curl http://127.0.0.1:3001/api/health"
echo "   • GPU status:         nvidia-smi"
echo ""

# Мониторинг
echo -e "${BLUE}📊 Monitoring:${NC}"
echo "   • System resources:   htop"
echo "   • GPU usage:          watch -n 1 nvidia-smi"
echo "   • Docker stats:       docker stats"
echo "   • Service logs:       tail -f ../logs/*.log"
echo ""

# Финальное сообщение
echo -e "${GREEN}🚀 Your RAG Knowledge Base is now running in PRODUCTION mode!${NC}"
echo -e "${BLUE}💡 Access the frontend at http://your-server-ip:3000${NC}"
echo -e "${BLUE}🔧 API available at http://your-server-ip:3001${NC}"
echo ""

# Сохраняем информацию о запуске
cat > .production_info << EOF
ENVIRONMENT=production
PLATFORM=Ubuntu Linux
VLLM_MODE=$([[ $USE_VLLM_CONTAINER == true ]] && echo "container" || echo "host")
COMPOSE_FILE=$COMPOSE_FILE
STARTED_AT=$(date)
FRONTEND_URL=http://127.0.0.1:3000
BACKEND_URL=http://127.0.0.1:3001
ML_SERVICES_ENABLED=$([[ $SKIP_ML_SERVICES == false ]] && echo "true" || echo "false")
DOCKER_SERVICES_ENABLED=$([[ $SKIP_DOCKER == false ]] && echo "true" || echo "false")
EOF

log_success "Production deployment information saved to .production_info"
