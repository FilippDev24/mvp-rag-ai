FROM node:18-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Prisma CLI globally
RUN npm install -g prisma

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install all dependencies (including dev)
RUN npm install

# Copy source code
COPY src/ ./src/
COPY prisma/ ./prisma/

# Generate Prisma client
RUN npx prisma generate

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3001/health || exit 1

# Set environment variables for Docker
ENV REDIS_URL=redis://redis:6379
ENV DATABASE_URL=postgresql://admin:password@postgres:5432/knowledge_base

# Start development server with hot reload
CMD ["npm", "run", "dev"]
