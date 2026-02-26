# Domain-Umzug: ariia.ai

## Übersicht

Die ARIIA-Plattform wird von `services.frigew.ski` auf `ariia.ai` umgezogen.

## DNS-Einstellungen (bereits erledigt)

| Typ | Name | Wert |
|-----|------|------|
| A | ariia.ai | 185.209.228.251 |
| AAAA | ariia.ai | 2a02:c207:3018:9295::1 |

### Empfohlene zusätzliche DNS-Einträge

| Typ | Name | Wert | Zweck |
|-----|------|------|-------|
| A | www.ariia.ai | 185.209.228.251 | www-Redirect |
| AAAA | www.ariia.ai | 2a02:c207:3018:9295::1 | www-Redirect |
| A | api.ariia.ai | 185.209.228.251 | Zukünftig: API-Subdomain |
| CNAME | app.ariia.ai | ariia.ai | Zukünftig: App-Subdomain |

## Schritte auf dem Server

### 1. SSL-Zertifikat erstellen

```bash
# Certbot für ariia.ai + www.ariia.ai
sudo certbot certonly --nginx -d ariia.ai -d www.ariia.ai
```

### 2. Nginx-Konfiguration deployen

```bash
# Neue Config kopieren
sudo cp /root/.openclaw/workspace/arni/deploy/nginx-ariia.ai.conf /etc/nginx/sites-available/ariia.ai

# Symlink erstellen
sudo ln -sf /etc/nginx/sites-available/ariia.ai /etc/nginx/sites-enabled/ariia.ai

# Nginx testen und neuladen
sudo nginx -t && sudo systemctl reload nginx
```

### 3. CORS-Origins aktualisieren

In `/root/.openclaw/workspace/arni/.env`:
```
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://services.frigew.ski,https://ariia.ai
```

### 4. Backend Container neustarten

```bash
cd /root/.openclaw/workspace/arni
docker compose restart ariia-core
```

### 5. Alte Domain als Redirect beibehalten (optional)

Die `services.frigew.ski` Config kann auf einen Redirect zu `ariia.ai` umgestellt werden.

## Subdomain-Strategie (Empfehlung)

| Subdomain | Zweck | Priorität |
|-----------|-------|-----------|
| ariia.ai | Hauptdomain (Dashboard + Landing) | Sofort |
| www.ariia.ai | Redirect auf ariia.ai | Sofort |
| api.ariia.ai | Öffentliche API (zukünftig) | Später |
| app.ariia.ai | Tenant-Dashboard (wenn basePath entfernt) | Später |
| docs.ariia.ai | API-Dokumentation | Später |

## Verifizierung

Nach dem Umzug:
1. `https://ariia.ai/ariia/login` sollte die Login-Seite zeigen
2. `https://ariia.ai/` sollte auf `/ariia/dashboard` redirecten
3. WebSocket unter `wss://ariia.ai/ws` sollte funktionieren
4. WhatsApp Webhook unter `https://ariia.ai/webhook/whatsapp` erreichbar
