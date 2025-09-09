#!/bin/bash

# 🛑 УНИВЕРСАЛЬНАЯ ОСТАНОВКА RAG СЕРВИСА
# Останавливает все компоненты системы (Docker + ML сервисы)

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
echo -e "${RED}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                    🛑 RAG KNOWLEDGE BASE                     ║
║                   Universal Stop Script                     ║
║                                                              ║
║  🔄 Graceful shutdown of all services                       ║
║  🐳 Docker containers cleanup                               ║
║  🤖 ML services termination                                 ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Определение режима остановки
FORCE_KILL=false
CLEAN_VOLUMES=false
CLEAN_IMAGES=false
VERBOSE=false

# Парсинг аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_KILL=true
            shift
            ;;
        --clean-volumes)
            CLEAN_VOLUMES=true
            shift
            ;;
        --clean-images)
            CLEAN_IMAGES=true
            shift
            ;;
        --clean-all)
            CLEAN_VOLUMES=true
            CLEAN_IMAGES=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
            echo ""
            echo -e "${YELLOW}Options:${NC}"
            echo "  --force, -f             Force kill all processes"
            echo "  --clean-volumes         Remove Docker volumes (data will be lost!)"
            echo "  --clean-images          Remove Docker images"
            echo "  --clean-all             Remove volumes and images"
            echo "  --verbose, -v           Verbose output"
            echo "  --help, -h              Show this help message"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0                      # Graceful shutdown"
            echo "  $0 --force              # Force kill all processes"
            echo "  $0 --clean-all          # Clean shutdown with data cleanup"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🛑 Stopping RAG Knowledge Base...${NC}"
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

# Функция для остановки процесса по PID файлу
stop_service_by_pid() {
    local service_name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log_step "Stopping $service_name (PID: $pid)..."
            
            if [ $FORCE_KILL = true ]; then
                kill -9 "$pid" 2>/dev/null || true
            else
                kill -TERM "$pid" 2>/dev/null || true
                # Ждем 5 секунд для graceful shutdown
                sleep 5
                if kill -0 "$pid" 2>/dev/null; then
                    log_warning "$service_name didn't stop gracefully, force killing..."
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
            
            # Удаляем PID файл
            rm -f "$pid_file"
            log_success "$service_name stopped"
        else
            log_info "$service_name was not running"
            rm -f "$pid_file"
        fi
    else
        log_info "$service_name PID file not found"
    fi
}

# Функция для остановки процесса по порту
stop_service_by_port() {
    local service_name=$1
    local port=$2
    
    if command -v lsof >/dev/null 2>&1; then
        local pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log_step "Stopping $service_name on port $port (PID: $pid)..."
            
            if [ $FORCE_KILL = true ]; then
                kill -9 $pid 2>/dev/null || true
            else
                kill -TERM $pid 2>/dev/null || true
                sleep 3
                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid 2>/dev/null || true
                fi
            fi
            
            log_success "$service_name stopped"
        else
            log_info "$service_name was not running on port $port"
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep ":$port " >/dev/null 2>&1; then
            log_warning "Process found on port $port but cannot determine PID (lsof not available)"
        else
            log_info "$service_name was not running on port $port"
        fi
    fi
}

# Остановка ML сервисов
log_step "Stopping ML services..."

# Остановка по PID файлам
if [ -d "logs" ]; then
    stop_service_by_pid "Embedding Service" "logs/embedding_service.pid"
    stop_service_by_pid "Reranker Service" "logs/reranker_service.pid"
fi

# Остановка по портам (на случай если PID файлы не найдены)
stop_service_by_port "Embedding Service" 8003
stop_service_by_port "Reranker Service" 8002

# Остановка vLLM/Ollama если запущены
stop_service_by_port "vLLM/Ollama" 8000
stop_service_by_port "Ollama" 11434

log_success "ML services stopped"

# Остановка Docker сервисов
log_step "Stopping Docker services..."

# Определяем команду docker-compose
DOCKER_COMPOSE_CMD="docker-compose"
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    log_warning "Neither 'docker-compose' nor 'docker compose' is available"
fi

# Остановка локальных сервисов
if [ -f "docker-compose.yml" ]; then
    log_step "Stopping local Docker services..."
    if [ $VERBOSE = true ]; then
        $DOCKER_COMPOSE_CMD -f docker-compose.yml down --remove-orphans
    else
        $DOCKER_COMPOSE_CMD -f docker-compose.yml down --remove-orphans > /dev/null 2>&1
    fi
    log_success "Local Docker services stopped"
fi

# Остановка продакшн сервисов
if [ -f "deployment/docker-compose.prod.yml" ]; then
    log_step "Stopping production Docker services..."
    cd deployment
    if [ $VERBOSE = true ]; then
        $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down --remove-orphans
    else
        $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down --remove-orphans > /dev/null 2>&1
    fi
    cd ..
    log_success "Production Docker services stopped"
fi

# Очистка volumes если требуется
if [ $CLEAN_VOLUMES = true ]; then
    log_step "Cleaning Docker volumes..."
    log_warning "This will delete all data! Continuing in 5 seconds..."
    sleep 5
    
    # Удаляем volumes для локального окружения
    if [ -f "docker-compose.yml" ]; then
        if [ $VERBOSE = true ]; then
            $DOCKER_COMPOSE_CMD -f docker-compose.yml down -v
        else
            $DOCKER_COMPOSE_CMD -f docker-compose.yml down -v > /dev/null 2>&1
        fi
    fi
    
    # Удаляем volumes для продакшн окружения
    if [ -f "deployment/docker-compose.prod.yml" ]; then
        cd deployment
        if [ $VERBOSE = true ]; then
            $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down -v
        else
            $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down -v > /dev/null 2>&1
        fi
        cd ..
    fi
    
    log_success "Docker volumes cleaned"
fi

# Очистка images если требуется
if [ $CLEAN_IMAGES = true ]; then
    log_step "Cleaning Docker images..."
    
    # Удаляем образы проекта
    docker images | grep -E "(kb_|knowledge)" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
    
    # Очистка неиспользуемых образов
    docker image prune -f > /dev/null 2>&1 || true
    
    log_success "Docker images cleaned"
fi

# Очистка временных файлов
log_step "Cleaning temporary files..."

# Удаляем логи ML сервисов
if [ -d "logs" ]; then
    rm -f logs/*.log
    rm -f logs/*.pid
fi

# Удаляем информацию о запуске
rm -f .startup_info

# Очистка Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

log_success "Temporary files cleaned"

# Проверка что все процессы остановлены
log_step "Verifying all services are stopped..."

SERVICES_RUNNING=false

# Проверяем порты
PORTS_TO_CHECK=(8000 8002 8003 8010 8011 8012 8014 8015 3000 3001 5432 6379 11434)

for port in "${PORTS_TO_CHECK[@]}"; do
    if command -v lsof >/dev/null 2>&1; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_warning "Port $port is still in use"
            SERVICES_RUNNING=true
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep ":$port " >/dev/null 2>&1; then
            log_warning "Port $port is still in use"
            SERVICES_RUNNING=true
        fi
    fi
done

# Проверяем Docker контейнеры
RUNNING_CONTAINERS=$(docker ps -q --filter "name=kb_" 2>/dev/null || true)
if [ -n "$RUNNING_CONTAINERS" ]; then
    log_warning "Some Docker containers are still running:"
    docker ps --filter "name=kb_" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true
    SERVICES_RUNNING=true
fi

if [ $SERVICES_RUNNING = false ]; then
    log_success "All services verified as stopped"
else
    log_warning "Some services may still be running"
    if [ $FORCE_KILL = false ]; then
        log_info "Use --force flag to force kill remaining processes"
    fi
fi

# Финальное сообщение
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    🛑 SHUTDOWN COMPLETE                     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_success "RAG Knowledge Base has been stopped!"
echo ""

# Показываем статистику
echo -e "${BLUE}📊 Shutdown Summary:${NC}"
echo "   • ML Services:        Stopped"
echo "   • Docker Services:    Stopped"
if [ $CLEAN_VOLUMES = true ]; then
    echo "   • Data Volumes:       Cleaned"
fi
if [ $CLEAN_IMAGES = true ]; then
    echo "   • Docker Images:      Cleaned"
fi
echo "   • Temporary Files:    Cleaned"
echo ""

# Полезные команды
echo -e "${BLUE}🛠️  Next Steps:${NC}"
echo "   • Start again:        ./start.sh"
echo "   • Start production:   ./start.sh --prod"
echo "   • View Docker status: docker ps -a"
echo "   • Clean everything:   ./stop.sh --clean-all"
echo ""

echo -e "${GREEN}✨ System is now clean and ready for restart!${NC}"
echo ""
