#!/bin/bash
set -e

ARIIA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ARIIA_DIR"

# Load .env
set -a
source .env
set +a

echo "🚀 ARIIA v1.4 – Production Launch"
echo "   Mode: $BRIDGE_MODE | Bridge: :${BRIDGE_PORT} | Gateway: :8000"
echo ""

# ─── Pre-flight ───
echo "🔍 Pre-flight checks..."
source .venv/bin/activate
python -c "import fastapi, redis, structlog; print('  ✅ Python deps OK')"
node -e "require('@whiskeysockets/baileys'); console.log('  ✅ Node deps OK')" 2>/dev/null || echo "  ⚠️  Node deps missing – run: cd app/integrations/whatsapp_web && npm i"
redis-cli ping > /dev/null 2>&1 && echo "  ✅ Redis OK" || echo "  ❌ Redis not running!"
echo ""

# ─── Stop existing processes ───
echo "🛑 Stopping existing processes..."
pkill -f "uvicorn app.gateway" 2>/dev/null || true
pkill -f "node.*index.js" 2>/dev/null || true
sleep 1

# ─── Start WhatsApp Bridge ───
echo "🌉 Starting WhatsApp Bridge..."
cd app/integrations/whatsapp_web
node index.js >> "$ARIIA_DIR/bridge.log" 2>&1 &
BRIDGE_PID=$!
cd "$ARIIA_DIR"
echo "   PID: $BRIDGE_PID"

# Wait for bridge
sleep 2
if kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "   ✅ Bridge running"
else
    echo "   ❌ Bridge failed to start – check bridge.log"
fi

# ─── Start Gateway ───
echo "⚡ Starting ARIIA Gateway..."
exec uvicorn app.gateway.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
