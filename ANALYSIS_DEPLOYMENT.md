# Analyse: Deployment, Login/Register, Favicon, GitHub Actions

## 1. GitHub Actions - Fehlerquellen

### CI/CD (ci.yml)
- **Lint (Backend)**: `ruff` findet 2040 Fehler (Whitespace, hardcoded passwords, no-explicit-any)
- Fix: ruff.toml mit Ignore-Rules für bekannte Patterns (S104, S105, W293)

### AI Evaluation Pipeline (eval.yml)
- **Fehler**: `pip install -r requirements.txt` - Datei existiert nicht
- Fix: Pfad auf pyproject.toml umstellen oder requirements.txt generieren

### Frontend Quality (frontend_quality.yml)
- **Fehler**: `npm run lint:strict` findet 235 Probleme (61 errors, 174 warnings)
- Hauptsächlich `@typescript-eslint/no-explicit-any` Fehler
- Fix: eslint-config anpassen oder `any` durch korrekte Typen ersetzen

## 2. Login/Register-Seiten
- Login: Hat eigenes Design (ShieldCheck Icon, Orbs), aber KEIN Navbar/Footer
- Register: Komplett anderes Design (inline styles, Card-basiert), KEIN Navbar/Footer
- Beide wirken wie Fremdkörper zur Landing Page

## 3. Logo/Favicon
- AriiaLogo: Verwendet externe CDN-URLs (manuscdn.com)
- Favicon: icon.svg ist 18MB (!!) - viel zu groß
- favicon.ico: 15KB
- favicon-96x96.png: 16KB
- Neues Logo von User bereitgestellt (3 Varianten)

## 4. Deployment-Prozess
- docker-compose.yml: Frontend nutzt `target: dev` (Development-Stage!)
- Frontend hat Hot-Reload-Volumes (app, components, lib, etc.)
- Backend hat auch Hot-Reload-Volumes (app, config, scripts)
- Kein Multi-Stage Production Build für Frontend
- Bestehende Scripts: deploy_vps.sh, quick_deploy.sh, launch.sh - alle rudimentär
- Kein `dialog`-basiertes GUI, keine CLI-Befehle

## 5. Docker-Optimierung
- Frontend baut ALLES bei jedem Deploy neu (kein Layer-Caching)
- Backend installiert alle Python-Deps bei jedem Build
- Kein selektives Container-Rebuilding
- Keine Backup-Konfiguration
