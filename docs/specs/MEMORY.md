# Memory Lifecycle & Data Structure

## 1. Storage Strategy
- **Short-Term (RAM):** Active conversation context (last 20 turns).
- **Mid-Term (Session DB):** SQLite `sessions.db`. Stores conversation history for 90 days.
- **Long-Term (Knowledge):** Markdown files in `data/knowledge/members/{id}.md`.

## 2. Lifecycle Process
1.  **Ingest:** Message enters RAM.
2.  **Compaction:** When Context > 80% limit:
    - Trigger "Silent Flush".
    - Extract facts ("Max has knee injury").
    - Append facts to `data/knowledge/members/Max.md`.
    - Prune RAM context (Keep summary + last 3 messages).
3.  **GraphRAG:**
    - Sync extracted facts to Graph Database (NetworkX/Neo4j) nightly.
    - Node: `(Member:Max) --[HAS_INJURY]--> (Knee)`.

## 3. Schema (SQLite)
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    platform TEXT, -- 'whatsapp', 'telegram'
    user_id TEXT,
    consent_status TEXT, -- 'granted', 'revoked'
    last_interaction DATETIME,
    metadata JSON -- Store temporary state here
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    role TEXT, -- 'user', 'assistant', 'system', 'tool'
    content TEXT,
    timestamp DATETIME
);