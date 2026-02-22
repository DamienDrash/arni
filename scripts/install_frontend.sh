#!/bin/bash
echo "📦 Installing Frontend Dependencies (inside container)..."

# Run npm install in a temporary container, mounting the volume
# This ensures node_modules are built for the container's architecture (Alpine)
docker compose run --rm --entrypoint "npm install" ariia_frontend

if [ $? -eq 0 ]; then
    echo "✅ Dependencies Installed!"
else
    echo "❌ Install Failed"
    exit 1
fi
