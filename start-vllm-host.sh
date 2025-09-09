#!/bin/bash

# 🚀 ЗАПУСК vLLM НА ХОСТЕ ДЛЯ gpt-oss-20b
# Скрипт для запуска vLLM сервера на Ubuntu с GPU

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting vLLM Host Service for gpt-oss-20b${NC}"
echo "=============================================="

# Параметры по умолчанию (МАКСИМАЛЬНО ОПТИМИЗИРОВАННЫЕ для A100)
MODEL_NAME="openai/gpt-oss-20b"
HOST="0.0.0.0"
PORT="8000"
DTYPE="bfloat16"
MAX_MODEL_LEN="16384"
GPU_MEMORY_UTILIZATION="0.90"
TENSOR_PARALLEL_SIZE="1"
BLOCK_SIZE="16"
SWAP_SPACE="4"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL_NAME="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --dtype)
            DTYPE="$2"
            shift 2
            ;;
        --max-len)
            MAX_MODEL_LEN="$2"
            shift 2
            ;;
        --gpu-memory)
            GPU_MEMORY_UTILIZATION="$2"
            shift 2
            ;;
        --tensor-parallel)
            TENSOR_PARALLEL_SIZE="$2"
            shift 2
            ;;
        --block-size)
            BLOCK_SIZE="$2"
            shift 2
            ;;
        --swap-space)
            SWAP_SPACE="$2"
            shift 2
            ;;
        --help|-h)
            echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
            echo ""
            echo -e "${YELLOW}Options:${NC}"
            echo "  --model MODEL           Model name (default: openai/gpt-oss-20b)"
            echo "  --port PORT             Port to bind (default: 8000)"
            echo "  --host HOST             Host to bind (default: 0.0.0.0)"
            echo "  --dtype DTYPE           Data type (default: bfloat16)"
            echo "  --max-len LENGTH        Max model length (default: 16384)"
            echo "  --gpu-memory RATIO      GPU memory utilization (default: 0.90)"
            echo "  --tensor-parallel SIZE  Tensor parallel size (default: 1)"
            echo "  --block-size SIZE       Block size for attention (default: 16)"
            echo "  --swap-space GB         CPU swap space in GB (default: 4)"
            echo "  --help, -h              Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Проверка системы
echo -e "${BLUE}🔍 Checking system requirements...${NC}"

# Проверка NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}❌ nvidia-smi not found. GPU required for vLLM.${NC}"
    exit 1
fi

GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo "")
if [ -z "$GPU_INFO" ]; then
    echo -e "${RED}❌ No GPU detected${NC}"
    exit 1
fi

echo -e "${GREEN}✅ GPU detected: $GPU_INFO${NC}"

# Проверка Python и vLLM
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

if ! python3 -c "import vllm" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  vLLM not installed. Installing...${NC}"
    pip install vllm
fi

echo -e "${GREEN}✅ vLLM is available${NC}"

# Проверка порта
if command -v lsof >/dev/null 2>&1; then
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}❌ Port $PORT is already in use${NC}"
        echo "Stop the existing service or use a different port"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Port $PORT is available${NC}"

# Создание директории для логов
mkdir -p logs

# Показываем конфигурацию
echo ""
echo -e "${BLUE}📋 vLLM Configuration:${NC}"
echo "  Model: $MODEL_NAME"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Data Type: $DTYPE"
echo "  Max Model Length: $MAX_MODEL_LEN"
echo "  GPU Memory Utilization: $GPU_MEMORY_UTILIZATION"
echo "  Tensor Parallel Size: $TENSOR_PARALLEL_SIZE"
echo "  Block Size: $BLOCK_SIZE"
echo "  Swap Space: ${SWAP_SPACE}GB"
echo ""

# Запуск vLLM
echo -e "${BLUE}🚀 Starting vLLM server...${NC}"

# Установка переменных окружения для HuggingFace кэша
export HF_HOME="/opt/llm-cache"
export TRANSFORMERS_CACHE="/opt/llm-cache"
export HF_HUB_CACHE="/opt/llm-cache/hub"

# Команда запуска с МАКСИМАЛЬНО ОПТИМИЗИРОВАННЫМИ параметрами для производительности
VLLM_CMD="vllm serve /opt/llm-cache/models--openai--gpt-oss-20b/snapshots/6cee5e81ee83917806bbde320786a8fb61efebee \
    --host $HOST \
    --port $PORT \
    --dtype $DTYPE \
    --max-model-len $MAX_MODEL_LEN \
    --gpu-memory-utilization $GPU_MEMORY_UTILIZATION \
    --tensor-parallel-size $TENSOR_PARALLEL_SIZE \
    --block-size $BLOCK_SIZE \
    --swap-space $SWAP_SPACE \
    --max-num-batched-tokens 8192 \
    --max-num-seqs 32 \
    --max-paddings 512 \
    --enable-prefix-caching \
    --enable-chunked-prefill \
    --max-num-on-the-fly-seq-groups 8 \
    --preemption-mode recompute \
    --disable-log-requests \
    --disable-log-stats \
    --trust-remote-code"

echo -e "${YELLOW}Command: $VLLM_CMD${NC}"
echo ""

# Запуск в фоне с логированием
LOG_FILE="logs/vllm_service.log"
PID_FILE="logs/vllm_service.pid"

echo -e "${BLUE}📝 Logs will be written to: $LOG_FILE${NC}"
echo -e "${BLUE}🆔 PID will be saved to: $PID_FILE${NC}"
echo ""

# Запускаем vLLM
nohup $VLLM_CMD > "$LOG_FILE" 2>&1 &
VLLM_PID=$!

# Сохраняем PID
echo $VLLM_PID > "$PID_FILE"

echo -e "${GREEN}✅ vLLM started with PID: $VLLM_PID${NC}"
echo ""

# Ждем инициализации
echo -e "${BLUE}⏳ Waiting for vLLM to initialize...${NC}"
echo "This may take several minutes for model loading..."

# Проверяем готовность сервиса
MAX_ATTEMPTS=60  # 5 минут
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if curl -s "http://$HOST:$PORT/v1/models" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ vLLM is ready and responding!${NC}"
        break
    fi
    
    # Проверяем, что процесс еще жив
    if ! kill -0 $VLLM_PID 2>/dev/null; then
        echo -e "${RED}❌ vLLM process died during startup${NC}"
        echo -e "${BLUE}📋 Check logs: tail -f $LOG_FILE${NC}"
        exit 1
    fi
    
    echo -n "."
    sleep 5
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
    echo -e "${RED}❌ vLLM failed to start within 5 minutes${NC}"
    echo -e "${BLUE}📋 Check logs: tail -f $LOG_FILE${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 vLLM is successfully running!${NC}"
echo ""

# Показываем информацию о сервисе
echo -e "${BLUE}📋 Service Information:${NC}"
echo "  • URL: http://$HOST:$PORT"
echo "  • Models endpoint: http://$HOST:$PORT/v1/models"
echo "  • Chat endpoint: http://$HOST:$PORT/v1/chat/completions"
echo "  • PID: $VLLM_PID"
echo "  • Log file: $LOG_FILE"
echo ""

# Полезные команды
echo -e "${BLUE}�️  Useful Commands:${NC}"
echo "  • View logs: tail -f $LOG_FILE"
echo "  • Check status: curl http://$HOST:$PORT/v1/models"
echo "  • Stop service: kill $VLLM_PID"
echo "  • Monitor GPU: watch -n 1 nvidia-smi"
echo ""

# Тест API
echo -e "${BLUE}🧪 Testing API...${NC}"
if curl -s "http://$HOST:$PORT/v1/models" | grep -q "gpt-oss"; then
    echo -e "${GREEN}✅ API test passed - model is loaded${NC}"
else
    echo -e "${YELLOW}⚠️  API test inconclusive - check manually${NC}"
fi

echo ""
echo -e "${GREEN}🚀 vLLM Host Service is ready for production!${NC}"
echo -e "${BLUE}💡 You can now start your Docker services${NC}"
echo ""

# Сохраняем информацию о запуске
cat > logs/vllm_info.txt << EOF
MODEL_NAME=$MODEL_NAME
HOST=$HOST
PORT=$PORT
DTYPE=$DTYPE
MAX_MODEL_LEN=$MAX_MODEL_LEN
GPU_MEMORY_UTILIZATION=$GPU_MEMORY_UTILIZATION
TENSOR_PARALLEL_SIZE=$TENSOR_PARALLEL_SIZE
BLOCK_SIZE=$BLOCK_SIZE
SWAP_SPACE=$SWAP_SPACE
PID=$VLLM_PID
STARTED_AT=$(date)
LOG_FILE=$LOG_FILE
EOF

echo -e "${BLUE}📄 Service info saved to logs/vllm_info.txt${NC}"
