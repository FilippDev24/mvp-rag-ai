# 🚀 RAG Knowledge Base - Быстрый старт

## 📋 Команды для запуска

### 🖥️ Локальная разработка
```bash
# Стандартный запуск
./start.sh

# С очисткой Docker
./start.sh --cleanup

# С пересборкой образов
./start.sh --rebuild

# Остановка
./stop.sh
```

### 🏭 Продакшн (Ubuntu + GPU)
```bash
# 1. Запуск vLLM на хосте
./start-vllm-host.sh

# 2. Запуск всех сервисов
cd deployment
./start-production.sh

# Или все в одном с очисткой
./start-production.sh --cleanup
```

### 🧹 Очистка Docker
```bash
# Безопасная очистка
./cleanup-docker.sh

# Агрессивная (удаляет данные!)
./cleanup-docker.sh --aggressive

# Предварительный просмотр
./cleanup-docker.sh --dry-run
```

## 🌐 Доступные сервисы

### Локально
- **Frontend**: http://localhost:8015
- **Backend API**: http://localhost:8014
- **Embedding**: http://localhost:8003
- **Reranker**: http://localhost:8002
- **Ollama**: http://localhost:11434

### Продакшн
- **Frontend**: http://your-server:3000
- **Backend API**: http://your-server:3001
- **vLLM**: http://your-server:8000
- **ChromaDB**: http://your-server:8012

## 🔧 Диагностика

```bash
# Проверка статуса
docker-compose ps

# Логи сервисов
docker-compose logs -f backend
docker-compose logs -f worker

# Проверка ML сервисов
curl http://localhost:8003/health
curl http://localhost:8002/health

# Проверка API
curl http://localhost:8014/api/health
```

## ⚡ Быстрые решения проблем

### Порты заняты
```bash
./stop.sh --force
./cleanup-docker.sh
```

### Docker проблемы
```bash
./cleanup-docker.sh --aggressive
./start.sh --rebuild
```

### ML сервисы не работают
```bash
rm -rf venv_*
./start_ml_services.sh
```

### GPU не определяется
```bash
nvidia-smi
sudo systemctl restart docker
```

## 📁 Важные файлы

- `.env` - локальные настройки
- `deployment/.env.prod` - продакшн настройки
- `logs/` - логи ML сервисов
- `backend/logs/` - логи backend
- `backend/uploads/` - загруженные файлы

## 🆘 Экстренная остановка

```bash
# Остановить все
./stop.sh --force

# Полная очистка
./cleanup-docker.sh --aggressive --force

# Убить все процессы на портах
sudo lsof -ti:8000,8002,8003,8014,8015 | xargs -r kill -9
```

---
**💡 Подробная документация в [README.md](README.md)**
