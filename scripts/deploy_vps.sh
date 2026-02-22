#!/bin/bash
set -e

echo "🚀 Starting ARIIA VPS Deployment..."

# 0. Check & Install Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker installed."
else
    echo "✅ Docker is already installed."
fi

# Ensure Docker Compose plugin
if ! docker compose version &> /dev/null; then
    echo "🛠️ Installing Docker Compose Plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

# 1. Stop Legacy System (Best Effort)
echo "🛑 Checking for legacy processes..."
PIDS=$(pgrep -f "python.*app.gateway.main") || true
if [ -n "$PIDS" ]; then
    echo "Found old Ariia process(es): $PIDS. Stopping..."
    kill $PIDS
    sleep 2
else
    echo "No legacy Python process found."
fi

# Stop conflicting system services (Redis default port 6379)
if systemctl is-active --quiet redis-server; then
    echo "🛑 Stopping system Redis to free port 6379 for Docker..."
    sudo systemctl stop redis-server
    sudo systemctl disable redis-server
elif systemctl is-active --quiet redis; then
     echo "🛑 Stopping system Redis (redis) to free port 6379..."
     sudo systemctl stop redis
     sudo systemctl disable redis
fi

# Ensure .env has LangFuse keys if missing (One-time Patch)
grep -q "LANGFUSE_SECRET_KEY" .env || echo 'LANGFUSE_SECRET_KEY="sk-lf-e1bb9cbb-b835-447a-9876-38ab6a22cc37"' >> .env
grep -q "LANGFUSE_PUBLIC_KEY" .env || echo 'LANGFUSE_PUBLIC_KEY="pk-lf-a38f140a-fd48-4b42-bfe3-04f6bfe0f1fe"' >> .env
grep -q "LANGFUSE_HOST" .env || echo 'LANGFUSE_HOST="https://cloud.langfuse.com"' >> .env

# 2. Pull & Build Docker Stack
echo "🐳 Building Docker Containers..."

# Fix for "parent snapshot does not exist" error (Corrupted Cache)
echo "🧹 Pruning Docker Builder Cache to prevent corruption..."
docker builder prune -f

# Load secrets from .env
if [ -f .env ]; then
    echo "🔐 Loading .env configuration..."
    set -a
    source .env
    set +a
else
    echo "⚠️ .env file not found! Secrets may be missing."
fi

docker compose down --remove-orphans || true
docker compose up -d --build

# 3. Wait for Health
echo "⏳ Waiting for services to be healthy..."
sleep 10
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "✅ ARIIA Core is Up!"
else
    echo "⚠️ Health check failed or timed out. Check logs with: docker compose logs -f ariia-core"
fi

echo "✅ Deployment Complete. Ariia is running on port 8000."
echo "🌍 External Access: Ensure your reverse proxy points services.frigew.ski -> localhost:8000"
