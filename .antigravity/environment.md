# ARNI v1.4 – Entwicklungsumgebung

> **CRITICAL:** Wir entwickeln REMOTE auf einem VPS.

## VPS-Konfiguration
- **IP:** `185.209.228.251`
- **User:** `root`
- **Port:** `22`
- **OS:** Linux (Debian/Ubuntu)

## Netzwerk-Regeln

| Kontext | Adresse | Grund |
|---------|---------|-------|
| **HTTP-Endpunkte** (curl, Browser) | `185.209.228.251` | Externer Zugriff auf den VPS |
| **Redis** (Gateway ↔ Redis) | `127.0.0.1` | Beide auf demselben VPS, interner Traffic |
| **Docker intern** | Service-Name (`redis`) | Docker-DNS löst Container-intern auf |

## Beispiele
```bash
# HTTP-Tests immer über VPS-IP:
curl http://185.209.228.251:8000/health

# Redis intern (gleicher VPS):
redis-cli -h 127.0.0.1 ping

# NIEMALS:
# curl http://localhost:8000/...   ❌
```
