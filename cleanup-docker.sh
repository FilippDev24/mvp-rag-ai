#!/bin/bash

# 🧹 ГЛУБОКАЯ ОЧИСТКА DOCKER СИСТЕМЫ
# Удаляет неиспользуемые контейнеры, образы, volumes и networks
# Освобождает место на диске и решает проблемы с "мусорными" контейнерами

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
║                    🧹 DOCKER CLEANUP                        ║
║                 Deep System Cleaning                        ║
║                                                              ║
║  🗑️  Remove unused containers, images, volumes              ║
║  💾 Free up disk space                                      ║
║  🔧 Fix Docker system issues                                ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Параметры очистки
CLEAN_CONTAINERS=true
CLEAN_IMAGES=true
CLEAN_VOLUMES=false
CLEAN_NETWORKS=true
CLEAN_BUILD_CACHE=true
FORCE_CLEAN=false
AGGRESSIVE_CLEAN=false
DRY_RUN=false

# Парсинг аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        --containers-only)
            CLEAN_CONTAINERS=true
            CLEAN_IMAGES=false
            CLEAN_VOLUMES=false
            CLEAN_NETWORKS=false
            CLEAN_BUILD_CACHE=false
            shift
            ;;
        --images-only)
            CLEAN_CONTAINERS=false
            CLEAN_IMAGES=true
            CLEAN_VOLUMES=false
            CLEAN_NETWORKS=false
            CLEAN_BUILD_CACHE=false
            shift
            ;;
        --include-volumes)
            CLEAN_VOLUMES=true
            shift
            ;;
        --aggressive)
            AGGRESSIVE_CLEAN=true
            CLEAN_VOLUMES=true
            shift
            ;;
        --force|-f)
            FORCE_CLEAN=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
            echo ""
            echo -e "${YELLOW}Options:${NC}"
            echo "  --containers-only       Clean only containers"
            echo "  --images-only           Clean only images"
            echo "  --include-volumes       Also clean volumes (DATA WILL BE LOST!)"
            echo "  --aggressive            Aggressive cleanup (includes volumes)"
            echo "  --force, -f             Skip confirmation prompts"
            echo "  --dry-run               Show what would be cleaned without doing it"
            echo "  --help, -h              Show this help message"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0                      # Standard cleanup (safe)"
            echo "  $0 --aggressive         # Deep cleanup including volumes"
            echo "  $0 --dry-run            # Preview cleanup actions"
            echo "  $0 --containers-only    # Clean only containers"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🧹 Docker Cleanup Configuration:${NC}"
echo "  • Clean containers: $([[ $CLEAN_CONTAINERS == true ]] && echo "✅" || echo "❌")"
echo "  • Clean images: $([[ $CLEAN_IMAGES == true ]] && echo "✅" || echo "❌")"
echo "  • Clean volumes: $([[ $CLEAN_VOLUMES == true ]] && echo "⚠️  YES (DATA LOSS!)" || echo "❌")"
echo "  • Clean networks: $([[ $CLEAN_NETWORKS == true ]] && echo "✅" || echo "❌")"
echo "  • Clean build cache: $([[ $CLEAN_BUILD_CACHE == true ]] && echo "✅" || echo "❌")"
echo "  • Dry run: $([[ $DRY_RUN == true ]] && echo "✅" || echo "❌")"
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

# Функция для выполнения команд с проверкой dry-run
execute_command() {
    local cmd="$1"
    local description="$2"
    
    if [ $DRY_RUN = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would execute: $cmd${NC}"
        return 0
    fi
    
    log_step "$description"
    if eval "$cmd" 2>/dev/null; then
        log_success "$description completed"
        return 0
    else
        log_warning "$description failed or nothing to clean"
        return 1
    fi
}

# Функция для получения размера до и после
get_docker_size() {
    docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null || echo "Unable to get Docker size info"
}

# Проверка Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker daemon is not running"
    exit 1
fi

log_success "Docker is available and running"

# Показываем текущее состояние системы
echo ""
log_step "Current Docker system usage:"
get_docker_size
echo ""

# Предупреждение о volumes
if [ $CLEAN_VOLUMES = true ] && [ $FORCE_CLEAN = false ]; then
    log_warning "⚠️  VOLUME CLEANUP ENABLED - THIS WILL DELETE ALL DATA!"
    log_warning "This includes databases, uploaded files, and other persistent data"
    echo ""
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Cleanup cancelled by user"
        exit 0
    fi
fi

# Общее предупреждение
if [ $FORCE_CLEAN = false ] && [ $DRY_RUN = false ]; then
    echo ""
    log_warning "This will clean up Docker system components"
    read -p "Continue with cleanup? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled by user"
        exit 0
    fi
fi

echo ""
log_step "Starting Docker cleanup process..."

# 1. Остановка всех контейнеров проекта
log_step "Stopping project containers..."
if [ $DRY_RUN = false ]; then
    # Останавливаем контейнеры нашего проекта
    docker ps -q --filter "name=kb_" | xargs -r docker stop 2>/dev/null || true
    
    # Останавливаем через docker-compose если файлы существуют
    if [ -f "docker-compose.yml" ]; then
        docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true
    fi
    
    if [ -f "deployment/docker-compose.prod.yml" ]; then
        cd deployment 2>/dev/null && docker-compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null && cd .. || true
    fi
    
    if [ -f "deployment/docker-compose.vllm.yml" ]; then
        cd deployment 2>/dev/null && docker-compose -f docker-compose.vllm.yml down --remove-orphans 2>/dev/null && cd .. || true
    fi
fi

# 2. Очистка контейнеров
if [ $CLEAN_CONTAINERS = true ]; then
    echo ""
    log_step "Cleaning containers..."
    
    # Удаляем остановленные контейнеры
    execute_command "docker container prune -f" "Removing stopped containers"
    
    if [ $AGGRESSIVE_CLEAN = true ]; then
        # Агрессивная очистка - удаляем ВСЕ контейнеры
        execute_command "docker ps -aq | xargs -r docker rm -f" "Force removing all containers"
    fi
fi

# 3. Очистка образов
if [ $CLEAN_IMAGES = true ]; then
    echo ""
    log_step "Cleaning images..."
    
    # Удаляем неиспользуемые образы
    execute_command "docker image prune -f" "Removing dangling images"
    
    if [ $AGGRESSIVE_CLEAN = true ]; then
        # Удаляем все неиспользуемые образы
        execute_command "docker image prune -a -f" "Removing all unused images"
        
        # Удаляем образы нашего проекта (если они не используются)
        if [ $DRY_RUN = false ]; then
            docker images | grep -E "(kb_|knowledge|mvp-rag)" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
        fi
    fi
fi

# 4. Очистка volumes
if [ $CLEAN_VOLUMES = true ]; then
    echo ""
    log_warning "Cleaning volumes (DATA WILL BE LOST!)..."
    
    # Удаляем неиспользуемые volumes
    execute_command "docker volume prune -f" "Removing unused volumes"
    
    if [ $AGGRESSIVE_CLEAN = true ]; then
        # Удаляем volumes нашего проекта
        if [ $DRY_RUN = false ]; then
            docker volume ls -q | grep -E "(kb_|knowledge|postgres|redis|chromadb)" | xargs -r docker volume rm -f 2>/dev/null || true
        fi
    fi
fi

# 5. Очистка networks
if [ $CLEAN_NETWORKS = true ]; then
    echo ""
    log_step "Cleaning networks..."
    
    # Удаляем неиспользуемые сети
    execute_command "docker network prune -f" "Removing unused networks"
fi

# 6. Очистка build cache
if [ $CLEAN_BUILD_CACHE = true ]; then
    echo ""
    log_step "Cleaning build cache..."
    
    # Очищаем build cache
    execute_command "docker builder prune -f" "Removing build cache"
    
    if [ $AGGRESSIVE_CLEAN = true ]; then
        # Агрессивная очистка build cache
        execute_command "docker builder prune -a -f" "Removing all build cache"
    fi
fi

# 7. Общая системная очистка
echo ""
log_step "Final system cleanup..."
execute_command "docker system prune -f" "Final system cleanup"

if [ $AGGRESSIVE_CLEAN = true ]; then
    execute_command "docker system prune -a -f" "Aggressive system cleanup"
fi

# 8. Очистка логов Docker (если возможно)
if [ $AGGRESSIVE_CLEAN = true ] && [ $DRY_RUN = false ]; then
    log_step "Cleaning Docker logs..."
    
    # Очищаем логи контейнеров (требует sudo на некоторых системах)
    if [ -d "/var/lib/docker/containers" ]; then
        find /var/lib/docker/containers -name "*.log" -exec truncate -s 0 {} \; 2>/dev/null || true
    fi
fi

# Показываем результат
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                    🎉 CLEANUP COMPLETE                      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $DRY_RUN = false ]; then
    log_step "Docker system usage after cleanup:"
    get_docker_size
    echo ""
    
    log_success "Docker cleanup completed successfully!"
    
    # Показываем освобожденное место
    log_info "Disk space has been freed up"
    log_info "You can now restart your services with clean Docker environment"
else
    log_info "Dry run completed - no actual changes were made"
fi

echo ""
echo -e "${BLUE}🛠️  Next Steps:${NC}"
echo "   • Restart services:   ./start.sh"
echo "   • Check disk usage:   df -h"
echo "   • Monitor Docker:     docker system df"
echo ""

# Полезная статистика
if [ $DRY_RUN = false ]; then
    echo -e "${BLUE}📊 Cleanup Summary:${NC}"
    echo "   • Containers cleaned: $([[ $CLEAN_CONTAINERS == true ]] && echo "✅" || echo "❌")"
    echo "   • Images cleaned: $([[ $CLEAN_IMAGES == true ]] && echo "✅" || echo "❌")"
    echo "   • Volumes cleaned: $([[ $CLEAN_VOLUMES == true ]] && echo "⚠️  YES" || echo "❌")"
    echo "   • Networks cleaned: $([[ $CLEAN_NETWORKS == true ]] && echo "✅" || echo "❌")"
    echo "   • Build cache cleaned: $([[ $CLEAN_BUILD_CACHE == true ]] && echo "✅" || echo "❌")"
    echo ""
fi

log_success "System is now clean and ready for fresh deployment!"
