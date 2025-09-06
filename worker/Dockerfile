FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip first
RUN pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "from celery_app import celery_app; celery_app.control.inspect().stats()" || exit 1

# Start Celery worker
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
