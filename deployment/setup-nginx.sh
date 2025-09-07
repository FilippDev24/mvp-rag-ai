#!/bin/bash

# Скрипт установки и настройки nginx для RAG AI системы

set -e

echo "🚀 Установка и настройка nginx для RAG AI системы"
echo "=================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Обновление пакетов...${NC}"
apt update

echo -e "${BLUE}📦 Установка nginx...${NC}"
apt install nginx -y

echo -e "${BLUE}🔧 Настройка nginx конфигурации...${NC}"

# Копирование конфигурации
cp nginx-rag-ai.conf /etc/nginx/sites-available/rag-ai

# Активация конфигурации
ln -sf /etc/nginx/sites-available/rag-ai /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

echo -e "${BLUE}✅ Проверка конфигурации nginx...${NC}"
nginx -t

echo -e "${BLUE}🚀 Запуск nginx...${NC}"
systemctl enable nginx
systemctl start nginx

echo -e "${GREEN}✅ nginx успешно установлен и настроен!${NC}"
echo -e "${BLUE}📋 Статус nginx:${NC}"
systemctl status nginx --no-pager

echo -e "${BLUE}=================================================="
echo -e "${GREEN}🎉 nginx настроен для RAG AI системы!${NC}"
echo -e "${BLUE}🌐 Доступ к системе: http://89.169.150.113${NC}"
echo -e "${BLUE}📊 API доступен по: http://89.169.150.113/api${NC}"
echo -e "${BLUE}🏥 Health check: http://89.169.150.113/health${NC}"
echo -e "${BLUE}==================================================${NC}"
