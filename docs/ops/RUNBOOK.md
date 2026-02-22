# ARNI v1.4 Runbook (Ops)

> **Status:** Draft | **Updated:** 2026-02-14

This document describes operational procedures for maintaining the ARNI Gateway.

## 🚨 Incident Response

### 1. Redis is Down
**Symptoms:** Logs show `arni.gateway.redis_unavailable`, Agents not responding.
**Action:**
```bash
# Check status
systemctl status redis-server

# Restart
sudo systemctl restart redis-server

# Verify logs
tail -f logs/arni.log | grep "redis"
```

### 2. High Latency (>500ms)
**Symptoms:** Users complain about slow replies. Locust test fails.
**Check:**
- **CPU/RAM:** `htop`
- **OpenAI:** Check status.openai.com
- **Logs:** `grep "llm.openai_failed" logs/arni.log` (Is system flapping to Ollama?)

### 3. Application Crash
**Symptoms:** 502 Bad Gateway (if Nginx), or Connection Refused.
**Action:**
```bash
# Check service
./scripts/check_health.sh

# Restart
./scripts/launch.sh
```

---

## 🔄 Maintenance

### Backup Database
The SQLite DB is at `data/memory.db`.
```bash
cp data/memory.db backups/memory_$(date +%F).db
```

### Update Application
```bash
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
./scripts/audit.sh
./scripts/launch.sh
```

### Rotate Secrets
1. Update `.env`
2. Restart application: `pkill -f uvicorn && ./scripts/launch.sh`
