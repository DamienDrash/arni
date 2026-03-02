"""Enterprise Knowledge Graph store – Neo4j abstraction layer.

Provides CRUD operations for the knowledge graph including nodes
(Tenant, Member, Fact, KnowledgeChunk, Conversation, Campaign, Entity)
and edges (relationships between them).

Falls back gracefully to an in-memory graph when Neo4j is unavailable,
ensuring the platform can run in development without external dependencies.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog

from app.memory_platform.config import get_config

logger = structlog.get_logger()


class GraphStore:
    """Abstraction over Neo4j for the Enterprise Knowledge Graph.

    Automatically falls back to an in-memory graph when Neo4j is not
    reachable, enabling local development and testing.
    """

    def __init__(self) -> None:
        self._driver: Any = None
        self._in_memory: bool = False
        self._mem_nodes: dict[str, dict[str, Any]] = {}
        self._mem_edges: list[dict[str, Any]] = []
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Connect to Neo4j or fall back to in-memory mode."""
        if self._initialised:
            return

        cfg = get_config().neo4j
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

            self._driver = AsyncGraphDatabase.driver(
                cfg.uri,
                auth=(cfg.user, cfg.password),
                max_connection_pool_size=cfg.max_connection_pool_size,
            )
            # Verify connectivity
            async with self._driver.session(database=cfg.database) as session:
                await session.run("RETURN 1")
            logger.info("graph_store.neo4j_connected", uri=cfg.uri)
            await self._ensure_schema()
        except Exception as exc:
            logger.warning(
                "graph_store.neo4j_unavailable_fallback_to_memory",
                error=str(exc),
            )
            self._in_memory = True
            self._driver = None

        self._initialised = True

    async def close(self) -> None:
        """Close the Neo4j driver."""
        if self._driver:
            await self._driver.close()

    # ── Schema ───────────────────────────────────────────────────────

    async def _ensure_schema(self) -> None:
        """Create constraints and indexes in Neo4j."""
        cfg = get_config().neo4j
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tenant) REQUIRE t.tenant_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Member) REQUIRE m.member_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (k:KnowledgeChunk) REQUIRE k.chunk_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Conversation) REQUIRE c.conversation_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (f:Fact) ON (f.tenant_id)",
            "CREATE INDEX IF NOT EXISTS FOR (f:Fact) ON (f.fact_type)",
            "CREATE INDEX IF NOT EXISTS FOR (f:Fact) ON (f.member_id)",
            "CREATE INDEX IF NOT EXISTS FOR (k:KnowledgeChunk) ON (k.tenant_id)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Member) ON (m.tenant_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.tenant_id)",
            "CREATE FULLTEXT INDEX fact_content IF NOT EXISTS FOR (f:Fact) ON EACH [f.subject, f.predicate, f.value]",
        ]
        try:
            async with self._driver.session(database=cfg.database) as session:
                for stmt in constraints + indexes:
                    await session.run(stmt)
            logger.info("graph_store.schema_ensured")
        except Exception as exc:
            logger.error("graph_store.schema_error", error=str(exc))

    # ── Node Operations ──────────────────────────────────────────────

    async def upsert_node(
        self,
        label: str,
        key_field: str,
        key_value: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update a node with the given label and properties."""
        if self._in_memory:
            node_key = f"{label}:{key_value}"
            existing = self._mem_nodes.get(node_key, {})
            existing.update(properties)
            existing[key_field] = key_value
            existing["_label"] = label
            self._mem_nodes[node_key] = existing
            return existing

        cfg = get_config().neo4j
        props_str = ", ".join(f"n.{k} = ${k}" for k in properties)
        query = f"""
        MERGE (n:{label} {{{key_field}: ${key_field}}})
        SET {props_str}
        RETURN n
        """
        params = {key_field: key_value, **properties}
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(query, params)
                record = await result.single()
                return dict(record["n"]) if record else {}
        except Exception as exc:
            logger.error("graph_store.upsert_node_error", label=label, error=str(exc))
            return {}

    async def get_node(
        self,
        label: str,
        key_field: str,
        key_value: str,
    ) -> dict[str, Any] | None:
        """Retrieve a single node by its key."""
        if self._in_memory:
            return self._mem_nodes.get(f"{label}:{key_value}")

        cfg = get_config().neo4j
        query = f"MATCH (n:{label} {{{key_field}: $val}}) RETURN n LIMIT 1"
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(query, {"val": key_value})
                record = await result.single()
                return dict(record["n"]) if record else None
        except Exception as exc:
            logger.error("graph_store.get_node_error", error=str(exc))
            return None

    async def query_nodes(
        self,
        label: str,
        filters: dict[str, Any],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query nodes by label and property filters."""
        if self._in_memory:
            results = []
            for node in self._mem_nodes.values():
                if node.get("_label") != label:
                    continue
                match = all(node.get(k) == v for k, v in filters.items())
                if match:
                    results.append(node)
                if len(results) >= limit:
                    break
            return results

        cfg = get_config().neo4j
        where_parts = [f"n.{k} = ${k}" for k in filters]
        where_clause = " AND ".join(where_parts) if where_parts else "TRUE"
        query = f"MATCH (n:{label}) WHERE {where_clause} RETURN n LIMIT $limit"
        params = {**filters, "limit": limit}
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(query, params)
                records = await result.data()
                return [dict(r["n"]) for r in records]
        except Exception as exc:
            logger.error("graph_store.query_nodes_error", error=str(exc))
            return []

    async def delete_node(
        self,
        label: str,
        key_field: str,
        key_value: str,
    ) -> bool:
        """Delete a node and its relationships."""
        if self._in_memory:
            node_key = f"{label}:{key_value}"
            if node_key in self._mem_nodes:
                del self._mem_nodes[node_key]
                self._mem_edges = [
                    e for e in self._mem_edges
                    if e.get("source") != node_key and e.get("target") != node_key
                ]
                return True
            return False

        cfg = get_config().neo4j
        query = f"MATCH (n:{label} {{{key_field}: $val}}) DETACH DELETE n"
        try:
            async with self._driver.session(database=cfg.database) as session:
                await session.run(query, {"val": key_value})
                return True
        except Exception as exc:
            logger.error("graph_store.delete_node_error", error=str(exc))
            return False

    # ── Relationship Operations ──────────────────────────────────────

    async def create_relationship(
        self,
        source_label: str,
        source_key: str,
        source_value: str,
        target_label: str,
        target_key: str,
        target_value: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """Create a relationship between two nodes."""
        properties = properties or {}

        if self._in_memory:
            self._mem_edges.append({
                "source": f"{source_label}:{source_value}",
                "target": f"{target_label}:{target_value}",
                "type": rel_type,
                "properties": properties,
            })
            return True

        cfg = get_config().neo4j
        props_str = ""
        if properties:
            props_str = " {" + ", ".join(f"{k}: ${k}" for k in properties) + "}"
        query = f"""
        MATCH (a:{source_label} {{{source_key}: $src_val}})
        MATCH (b:{target_label} {{{target_key}: $tgt_val}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $props
        RETURN r
        """
        params = {"src_val": source_value, "tgt_val": target_value, "props": properties}
        try:
            async with self._driver.session(database=cfg.database) as session:
                await session.run(query, params)
                return True
        except Exception as exc:
            logger.error("graph_store.create_rel_error", error=str(exc))
            return False

    async def get_member_facts(
        self,
        tenant_id: int,
        member_id: str,
        fact_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get all facts associated with a member."""
        if self._in_memory:
            results = []
            for node in self._mem_nodes.values():
                if node.get("_label") != "Fact":
                    continue
                if node.get("tenant_id") != tenant_id:
                    continue
                if node.get("member_id") != member_id:
                    continue
                if fact_types and node.get("fact_type") not in fact_types:
                    continue
                results.append(node)
                if len(results) >= limit:
                    break
            return results

        cfg = get_config().neo4j
        type_filter = ""
        if fact_types:
            type_filter = "AND f.fact_type IN $fact_types"
        query = f"""
        MATCH (f:Fact)
        WHERE f.tenant_id = $tenant_id AND f.member_id = $member_id {type_filter}
        RETURN f
        ORDER BY f.confidence DESC, f.updated_at DESC
        LIMIT $limit
        """
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "member_id": member_id,
            "limit": limit,
        }
        if fact_types:
            params["fact_types"] = fact_types
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(query, params)
                records = await result.data()
                return [dict(r["f"]) for r in records]
        except Exception as exc:
            logger.error("graph_store.get_member_facts_error", error=str(exc))
            return []

    async def fulltext_search(
        self,
        tenant_id: int,
        query_text: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search across facts in the graph."""
        if self._in_memory:
            query_lower = query_text.lower()
            results = []
            for node in self._mem_nodes.values():
                if node.get("_label") != "Fact":
                    continue
                if node.get("tenant_id") != tenant_id:
                    continue
                searchable = f"{node.get('subject', '')} {node.get('predicate', '')} {node.get('value', '')}".lower()
                if query_lower in searchable:
                    results.append(node)
                if len(results) >= limit:
                    break
            return results

        cfg = get_config().neo4j
        query = """
        CALL db.index.fulltext.queryNodes('fact_content', $query_text)
        YIELD node, score
        WHERE node.tenant_id = $tenant_id
        RETURN node, score
        ORDER BY score DESC
        LIMIT $limit
        """
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(
                    query,
                    {"query_text": query_text, "tenant_id": tenant_id, "limit": limit},
                )
                records = await result.data()
                return [
                    {**dict(r["node"]), "_score": r["score"]}
                    for r in records
                ]
        except Exception as exc:
            logger.error("graph_store.fulltext_search_error", error=str(exc))
            return []

    # ── Stats ────────────────────────────────────────────────────────

    async def get_stats(self, tenant_id: int) -> dict[str, Any]:
        """Return graph statistics for a tenant."""
        if self._in_memory:
            counts: dict[str, int] = defaultdict(int)
            for node in self._mem_nodes.values():
                if node.get("tenant_id") == tenant_id:
                    counts[node.get("_label", "unknown")] += 1
            return {
                "mode": "in_memory",
                "node_counts": dict(counts),
                "edge_count": len([
                    e for e in self._mem_edges
                    if any(
                        self._mem_nodes.get(e["source"], {}).get("tenant_id") == tenant_id
                        for _ in [None]
                    )
                ]),
            }

        cfg = get_config().neo4j
        query = """
        MATCH (n)
        WHERE n.tenant_id = $tenant_id
        RETURN labels(n)[0] AS label, count(n) AS cnt
        """
        try:
            async with self._driver.session(database=cfg.database) as session:
                result = await session.run(query, {"tenant_id": tenant_id})
                records = await result.data()
                return {
                    "mode": "neo4j",
                    "node_counts": {r["label"]: r["cnt"] for r in records},
                }
        except Exception as exc:
            logger.error("graph_store.stats_error", error=str(exc))
            return {"mode": "error", "error": str(exc)}


# ── Singleton ────────────────────────────────────────────────────────

_store: GraphStore | None = None


def get_graph_store() -> GraphStore:
    """Return the singleton graph store instance."""
    global _store
    if _store is None:
        _store = GraphStore()
    return _store
