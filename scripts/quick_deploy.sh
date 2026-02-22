#!/bin/bash

echo "⚡ Starting Quick Deploy (Code Update Only)..."

# Usage: ./quick_deploy.sh [clean]

# 0. Clean Install Option (Fixes dependency corruption)
if [ "$1" == "clean" ]; then
    echo "🧹 Cleaning frontend dependencies (fresh start)..."
    rm -rf frontend/node_modules frontend/.next frontend/package-lock.json
fi

# 1. Ensure clean slate (Kill potential stale runners on host)
pkill -f telegram_polling_worker.py || true

# 2. Reset Frontend Volume (Commented out aggressive reset, trying manual install via run)
# echo "🧹 Cleaning broken frontend volumes..."
# docker compose rm -s -f -v ariia_frontend || true

# 3. Create containers (but don't start frontend yet if we need manual install)
# Actually just run `docker compose up -d` for backend/db, then frontend manual step.
# For simplicity, we run `up -d` then `run npm install` then restart frontend.

# 3. Start Services
echo "🚀 Starting Services..."
# Frontend: -V verwirft anonyme Volumes (node_modules/.next) komplett, damit
# npm install sauber in eine leere Directory schreiben kann
docker compose up -d --force-recreate -V ariia-frontend

# Backend: normal starten/aktualisieren (kein Rebuild nötig für Hot Reload)
docker compose up -d ariia-core ariia-telegram redis qdrant

echo "✅ Quick Deploy Complete!"
echo "   Backend regenerated in < 5 seconds."
echo "   Frontend is performing a clean install (may take 1-2 mins to start)."
echo "   Check logs with: docker compose logs -f ariia-frontend"
