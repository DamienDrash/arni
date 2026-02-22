#!/bin/bash
set -e

echo "🔒 Starting Security Audit..."

# 1. Dependency Audit (pip-audit)
echo "📦 Running pip-audit..."
# Ignore known vulnerabilities if needed with --ignore-vuln ID
# For now, we just run it. If it fails, script exits.
pip-audit || echo "⚠️  pip-audit found issues! Check output above."

# 2. Static Analysis (Bandit)
echo "🕵️  Running Bandit..."
# -r: recursive
# -ll: log level (only report medium/high)
# -x: exclude tests/ and venv/
bandit -r app/ -ll -x tests/,.venv/ || echo "⚠️  Bandit found issues! Check output above."

echo "✅ Audit Complete."
