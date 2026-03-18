"""ARIIA v2.0 – Embedding Service mit Tenant-Rate-Limiting.

Plan-basierte Provider-Auswahl und asyncio.Semaphore pro Tenant-Tier.
Batching: 100 Chunks/Request. Retry via exponential backoff.
"""
from __future__ import annotations
import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()

# Embedding-Dimensionen pro Modell
MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Plan → Modell Mapping
PLAN_EMBEDDING_MODEL = {
    "trial":      "text-embedding-3-small",
    "starter":    "text-embedding-3-small",
    "pro":        "text-embedding-3-large",
    "business":   "text-embedding-3-large",
    "enterprise": "text-embedding-3-large",
}

# Plan → max. parallele Embedding-Requests
PLAN_CONCURRENCY = {
    "trial":      1,
    "starter":    1,
    "pro":        3,
    "business":   5,
    "enterprise": 10,
}

BATCH_SIZE = 100  # Chunks pro OpenAI-Request


@dataclass
class EmbeddedChunk:
    """Chunk mit Embedding-Vektor."""
    text: str
    chunk_index: int
    page_num: Optional[int]
    section: Optional[str]
    char_offset: int
    token_count: int
    embedding: list[float]
    model_used: str
    source_metadata: dict


class TenantEmbeddingRateLimiter:
    """Pro-Tenant asyncio.Semaphore verhindert noisy-neighbor-Effekte."""

    _semaphores: dict[int, asyncio.Semaphore] = {}
    _plan_cache: dict[int, str] = {}

    @classmethod
    def _get_semaphore(cls, tenant_id: int, plan_slug: str) -> asyncio.Semaphore:
        if tenant_id not in cls._semaphores:
            concurrency = PLAN_CONCURRENCY.get(plan_slug, 1)
            cls._semaphores[tenant_id] = asyncio.Semaphore(concurrency)
            logger.debug(
                "embedding.semaphore_created",
                tenant_id=tenant_id,
                plan=plan_slug,
                concurrency=concurrency,
            )
        return cls._semaphores[tenant_id]

    @classmethod
    def get(cls, tenant_id: int, plan_slug: str) -> asyncio.Semaphore:
        return cls._get_semaphore(tenant_id, plan_slug)


class EmbeddingService:
    """Async Embedding-Service mit Batching, Rate-Limiting und Retry."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def embed_chunks(
        self,
        chunks,  # list[SemanticChunk]
        tenant_id: int,
        plan_slug: str,
        job_id: str,
    ) -> list[EmbeddedChunk]:
        """Embed alle Chunks mit Plan-basiertem Modell und Rate-Limiting."""
        model = PLAN_EMBEDDING_MODEL.get(plan_slug, "text-embedding-3-small")
        semaphore = TenantEmbeddingRateLimiter.get(tenant_id, plan_slug)

        embedded = []
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1

            async with semaphore:
                vectors = await self._embed_batch_with_retry(
                    texts=[c.text for c in batch],
                    model=model,
                    job_id=job_id,
                    batch_num=batch_num,
                    total_batches=total_batches,
                )

            for chunk, vector in zip(batch, vectors):
                embedded.append(EmbeddedChunk(
                    text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    page_num=chunk.page_num,
                    section=chunk.section,
                    char_offset=chunk.char_offset,
                    token_count=chunk.token_count,
                    embedding=vector,
                    model_used=model,
                    source_metadata=chunk.source_metadata,
                ))

        logger.info(
            "embedding.completed",
            job_id=job_id,
            tenant_id=tenant_id,
            total_chunks=len(embedded),
            model=model,
        )
        return embedded

    async def _embed_batch_with_retry(
        self,
        texts: list[str],
        model: str,
        job_id: str,
        batch_num: int,
        total_batches: int,
        max_retries: int = 3,
    ) -> list[list[float]]:
        """Einzelner Batch mit exponential-backoff Retry."""
        last_error = None

        for attempt in range(max_retries):
            try:
                t0 = time.monotonic()
                response = await self._client.post(
                    "https://api.openai.com/v1/embeddings",
                    json={"model": model, "input": texts},
                )
                latency_ms = (time.monotonic() - t0) * 1000

                if response.status_code == 429:
                    # Rate limit: backoff
                    retry_after = int(response.headers.get("retry-after", 2 ** attempt))
                    logger.warning(
                        "embedding.rate_limited",
                        job_id=job_id,
                        retry_after=retry_after,
                        attempt=attempt,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                logger.debug(
                    "embedding.batch_complete",
                    job_id=job_id,
                    batch=f"{batch_num}/{total_batches}",
                    latency_ms=round(latency_ms, 1),
                    tokens=data.get("usage", {}).get("total_tokens", 0),
                )

                return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning(
                    "embedding.network_error",
                    job_id=job_id,
                    attempt=attempt,
                    wait_s=wait,
                    error=str(e),
                )
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 401, 403):
                    # Nicht retry-bar
                    raise
                last_error = e
                await asyncio.sleep(2 ** attempt * 2)

        raise RuntimeError(f"Embedding nach {max_retries} Versuchen fehlgeschlagen: {last_error}")


def get_embedding_service() -> EmbeddingService:
    """Factory: EmbeddingService mit API-Key aus Settings."""
    from config.settings import get_settings
    settings = get_settings()
    return EmbeddingService(api_key=settings.openai_api_key)
