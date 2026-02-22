#!/bin/bash
echo "🚀 Starting Arni Dashboard..."

# 1. Start Backend (Background)
echo "🔌 Starting Backend (Port 8000)..."
cd /root/.openclaw/workspace/arni
source .venv/bin/activate
uvicorn app.gateway.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 2. Start Frontend (Foreground)
echo "💻 Starting Frontend (Port 3000)..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo "✅ Arni is Live!"
echo "👉 Dashboard: http://localhost:3000/arni"
echo "👉 Backend:   http://localhost:8000"

# Trap Ctrl+C to kill both
trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT

wait
