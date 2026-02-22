#!/bin/bash
set -e

echo "🔄 Restarting ARNI Gateway for Verification..."
pkill -f uvicorn || true

source .venv/bin/activate
nohup uvicorn app.gateway.main:app --port 8000 > /dev/null 2>&1 &
SERVER_PID=$!

echo "⏳ Waiting for startup..."
sleep 5

echo "🔍 Checking /metrics..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/metrics)

if [ "$response" == "200" ]; then
    echo "✅ Metrics Endpoint OK (200)"
    curl -s http://localhost:8000/metrics | head -n 5
else
    echo "❌ Metrics Endpoint Failed ($response)"
    kill $SERVER_PID
    exit 1
fi

echo "🛑 Stopping server..."
kill $SERVER_PID
