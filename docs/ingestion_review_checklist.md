# Ingestion Pipeline – Code Review Checkliste

## Security
- [ ] Kein file.read() ohne size-Limit im Upload-Handler
- [ ] MIME-Type-Whitelist validiert (nicht nur Extension)
- [ ] S3-Keys enthalten tenant_slug (Tenant-Isolation)
- [ ] Alle DB-Queries mit tenant_id gefiltert
- [ ] Keine Secrets hardcodiert (MINIO_ACCESS_KEY, OPENAI_API_KEY aus env)
- [ ] DLQ-Endpoint erfordert system_admin

## Performance & Stability
- [ ] Kein vollständiges In-Memory-Laden (kein data = file.read() für >1MB)
- [ ] Parser nutzen Iteratoren/Generatoren
- [ ] TempFiles werden in finally-Block gelöscht
- [ ] asyncio.Semaphore begrenzt parallele Embedding-Requests
- [ ] ChromaDB-Upsert ist idempotent (sha256-basierte IDs)

## Error Handling
- [ ] Alle 3 Error-Kategorien implementiert (sofort-DLQ, retry, sofort-retry)
- [ ] Backoff-Zeiten konfiguriert (2^n * 30s)
- [ ] DLQ-Eintrag bei max_attempts überschritten
- [ ] TempFile-Cleanup auch bei Exceptions (finally)

## Observability
- [ ] Strukturiertes Logging (structlog) in allen Worker-Steps
- [ ] Redis-Events für SSE publiziert
- [ ] Job-Progress in PostgreSQL aktualisiert
- [ ] Fehler-Kategorie in error_category Spalte gespeichert

## Tests
- [ ] Upload 200/202 mit job_id
- [ ] 413 bei >50MB
- [ ] 415 bei nicht-unterstütztem MIME
- [ ] Parser liefern non-empty Chunks
- [ ] Chunker überschreitet Token-Target nicht signifikant
- [ ] Retry-Logik respektiert max_attempts
- [ ] Tenant-Isolation: verschiedene Collection-Namen
- [ ] DLQ nur für system_admin
- [ ] Bestehende Tests noch grün (Health, Auth, Webhook)
