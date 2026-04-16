"""ARIIA v2.0 – Resilient Librarian.

Replaces the fragile Librarian with a robust background worker that:
- Reads tasks from a Redis Stream (not Pub/Sub)
- Tracks job status (pending → running → completed/failed)
- Retries with exponential backoff
- Falls back to raw chat history on repeated failures
- Stores episodic memories in the vector DB

Architecture:
    Redis Stream (ariia:stream:librarian) → LibrarianWorker → Vector DB
    Failed jobs → retry (up to MAX_RETRIES) → fallback summary → DLQ
"""
from __future__ import annotations

import asyncio
import json
import time
import structlog
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from app.domains.support.models import ChatMessage, ChatSession
from app.shared.db import open_session

logger = structlog.get_logger()


# ─── Configuration ────────────────────────────────────────────────────────────

MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds
BACKOFF_MAX = 60  # seconds
JOB_TTL_HOURS = 168  # 7 days
BATCH_SIZE = 10
SESSION_AGE_HOURS = 24  # Archive sessions older than this


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    FALLBACK = "fallback"  # Completed with fallback summary


@dataclass
class ArchivalJob:
    """A single archival job for the Librarian."""
    job_id: str
    member_id: str
    tenant_id: int
    session_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    retry_count: int = 0
    last_error: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "member_id": self.member_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArchivalJob":
        return cls(
            job_id=data.get("job_id", ""),
            member_id=data.get("member_id", ""),
            tenant_id=int(data.get("tenant_id", 0)),
            session_id=data.get("session_id"),
            status=JobStatus(data.get("status", "pending")),
            retry_count=int(data.get("retry_count", 0)),
            last_error=data.get("last_error", ""),
            created_at=float(data.get("created_at", time.time())),
            started_at=float(data["started_at"]) if data.get("started_at") else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") else None,
            summary=data.get("summary", ""),
        )


# ─── Summarization Strategies ────────────────────────────────────────────────

LIBRARIAN_PROMPT = """Du bist der Bibliothekar von ARIIA. Deine Aufgabe ist es, einen abgeschlossenen Chat-Verlauf 
in eine kompakte, narrative Zusammenfassung (Episode) zu verwandeln.

KONTEXT:
Mitglied: {member_id}
Mandant: {tenant_id}

Chat-Verlauf:
{chat_text}

ZIEL:
Schreibe eine kurze Zusammenfassung in der 3. Person. Fokussiere auf:
- Hauptanliegen des Mitglieds
- Getroffene Entscheidungen oder Aktionen
- Offene Punkte oder Follow-ups
- Emotionaler Zustand / Zufriedenheit

Beispiel: "Am 23.02. fragte das Mitglied nach Marathon-Tipps und klagte über Knieprobleme. 
Der Bot empfahl eine Pause und schlug einen Arztbesuch vor. Das Mitglied war dankbar."
"""


class SummarizationStrategy:
    """Base class for summarization strategies."""

    async def summarize(
        self,
        member_id: str,
        tenant_id: int,
        messages: list[dict],
    ) -> str:
        raise NotImplementedError


class LLMSummarization(SummarizationStrategy):
    """Primary strategy: Use LLM for intelligent summarization."""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def _get_llm(self):
        if self._llm is None:
            from app.swarm.llm import LLMClient
            from config.settings import get_settings
            self._llm = LLMClient(get_settings().openai_api_key)
        return self._llm

    async def summarize(
        self,
        member_id: str,
        tenant_id: int,
        messages: list[dict],
    ) -> str:
        chat_text = "\n".join(
            [f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages]
        )

        llm = self._get_llm()
        summary = await llm.chat(
            messages=[{
                "role": "system",
                "content": LIBRARIAN_PROMPT.format(
                    member_id=member_id,
                    tenant_id=tenant_id,
                    chat_text=chat_text,
                ),
            }],
            model="gpt-4o-mini",
            temperature=0.3,
        )
        return summary


class FallbackSummarization(SummarizationStrategy):
    """Fallback strategy: Extract key facts without LLM.

    Used when the LLM is unavailable after max retries.
    Creates a structured summary from the raw chat history.
    """

    async def summarize(
        self,
        member_id: str,
        tenant_id: int,
        messages: list[dict],
    ) -> str:
        if not messages:
            return f"[FALLBACK] Keine Nachrichten für Mitglied {member_id}."

        # Extract basic statistics
        user_msgs = [m for m in messages if m.get("role") == "user"]
        bot_msgs = [m for m in messages if m.get("role") in ("assistant", "bot")]
        total = len(messages)

        # Get first and last user messages
        first_msg = user_msgs[0]["content"][:200] if user_msgs else "N/A"
        last_msg = user_msgs[-1]["content"][:200] if user_msgs else "N/A"

        # Build structured fallback summary
        date_str = datetime.now().strftime("%Y-%m-%d")
        summary = (
            f"[FALLBACK {date_str}] Session mit Mitglied {member_id}: "
            f"{total} Nachrichten ({len(user_msgs)} vom Nutzer, {len(bot_msgs)} vom Bot). "
            f"Erste Nachricht: \"{first_msg}\". "
            f"Letzte Nachricht: \"{last_msg}\"."
        )
        return summary


# ─── Librarian Worker ─────────────────────────────────────────────────────────

class LibrarianWorker:
    """Resilient background worker for session archival.

    Features:
    - Exponential backoff retry (2s, 4s, 8s up to 60s)
    - Job status tracking in Redis
    - Fallback summarization on permanent failure
    - Batch processing of stale sessions
    - Metrics and logging for observability
    """

    def __init__(
        self,
        primary_strategy: Optional[SummarizationStrategy] = None,
        fallback_strategy: Optional[SummarizationStrategy] = None,
        max_retries: int = MAX_RETRIES,
        backoff_base: float = BACKOFF_BASE,
        backoff_max: float = BACKOFF_MAX,
    ):
        self._primary = primary_strategy or LLMSummarization()
        self._fallback = fallback_strategy or FallbackSummarization()
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._jobs: dict[str, ArchivalJob] = {}
        self._metrics = {
            "total_processed": 0,
            "successful": 0,
            "fallback_used": 0,
            "failed": 0,
            "total_retries": 0,
        }

    @staticmethod
    def _session_message_identifiers(session: Any) -> list[str]:
        identifiers: list[str] = []
        user_id = getattr(session, "user_id", None)
        session_id = getattr(session, "id", None)
        if user_id:
            identifiers.append(str(user_id))
        if session_id is not None:
            session_id_str = str(session_id)
            if session_id_str not in identifiers:
                identifiers.append(session_id_str)
        return identifiers

    # ─── Job Management ───────────────────────────────────────────────

    def create_job(
        self,
        member_id: str,
        tenant_id: int,
        session_id: Optional[str] = None,
    ) -> ArchivalJob:
        """Create a new archival job."""
        import uuid
        job_id = f"lib-{uuid.uuid4().hex[:12]}"
        job = ArchivalJob(
            job_id=job_id,
            member_id=member_id,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        self._jobs[job_id] = job

        logger.info(
            "librarian.job_created",
            job_id=job_id,
            member_id=member_id,
            tenant_id=tenant_id,
        )
        return job

    def get_job(self, job_id: str) -> Optional[ArchivalJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_jobs_by_status(self, status: JobStatus) -> list[ArchivalJob]:
        """Get all jobs with a given status."""
        return [j for j in self._jobs.values() if j.status == status]

    def get_metrics(self) -> dict:
        """Get worker metrics."""
        return {
            **self._metrics,
            "pending_jobs": len(self.get_jobs_by_status(JobStatus.PENDING)),
            "running_jobs": len(self.get_jobs_by_status(JobStatus.RUNNING)),
        }

    # ─── Core Processing ──────────────────────────────────────────────

    async def process_job(
        self,
        job: ArchivalJob,
        messages: list[dict],
    ) -> ArchivalJob:
        """Process a single archival job with retry logic.

        Args:
            job: The archival job to process.
            messages: Chat messages to summarize.

        Returns:
            Updated job with final status.
        """
        job.status = JobStatus.RUNNING
        job.started_at = time.time()

        logger.info(
            "librarian.job_started",
            job_id=job.job_id,
            member_id=job.member_id,
            retry_count=job.retry_count,
        )

        # Try primary strategy with retries
        while job.retry_count <= self._max_retries:
            try:
                summary = await self._primary.summarize(
                    job.member_id, job.tenant_id, messages,
                )
                job.summary = summary
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                self._metrics["successful"] += 1
                self._metrics["total_processed"] += 1

                logger.info(
                    "librarian.job_completed",
                    job_id=job.job_id,
                    member_id=job.member_id,
                    duration_s=round(job.completed_at - job.started_at, 2),
                )
                return job

            except Exception as e:
                job.retry_count += 1
                job.last_error = str(e)
                self._metrics["total_retries"] += 1

                logger.warning(
                    "librarian.job_retry",
                    job_id=job.job_id,
                    retry_count=job.retry_count,
                    max_retries=self._max_retries,
                    error=str(e),
                )

                if job.retry_count <= self._max_retries:
                    # Exponential backoff
                    delay = min(
                        self._backoff_base ** job.retry_count,
                        self._backoff_max,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted – use fallback
        try:
            logger.warning(
                "librarian.using_fallback",
                job_id=job.job_id,
                member_id=job.member_id,
            )

            summary = await self._fallback.summarize(
                job.member_id, job.tenant_id, messages,
            )
            job.summary = summary
            job.status = JobStatus.FALLBACK
            job.completed_at = time.time()
            self._metrics["fallback_used"] += 1
            self._metrics["total_processed"] += 1

            logger.info(
                "librarian.job_fallback_completed",
                job_id=job.job_id,
                member_id=job.member_id,
            )
            return job

        except Exception as e:
            job.status = JobStatus.FAILED
            job.last_error = f"Fallback also failed: {str(e)}"
            job.completed_at = time.time()
            self._metrics["failed"] += 1
            self._metrics["total_processed"] += 1

            logger.error(
                "librarian.job_failed",
                job_id=job.job_id,
                member_id=job.member_id,
                error=str(e),
            )
            return job

    async def store_summary(
        self,
        job: ArchivalJob,
    ) -> bool:
        """Store the job's summary in the vector database.

        Args:
            job: Completed job with summary.

        Returns:
            True if stored successfully.
        """
        if not job.summary:
            return False

        try:
            from app.memory.member_memory_analyzer import _index_member_memory

            date_str = datetime.now().strftime("%Y-%m-%d")
            prefix = "[EPISODE" if job.status == JobStatus.COMPLETED else "[FALLBACK-EPISODE"
            episodic_fact = f"{prefix} {date_str}]: {job.summary}"

            await _index_member_memory(job.member_id, job.tenant_id, episodic_fact)

            logger.info(
                "librarian.summary_stored",
                job_id=job.job_id,
                member_id=job.member_id,
                type=job.status.value,
            )
            return True

        except Exception as e:
            logger.error(
                "librarian.store_failed",
                job_id=job.job_id,
                error=str(e),
            )
            return False

    # ─── Batch Processing ─────────────────────────────────────────────

    async def scan_stale_sessions(
        self,
        age_hours: int = SESSION_AGE_HOURS,
    ) -> list[dict]:
        """Scan for sessions that need archival.

        Returns a list of session info dicts for sessions older than age_hours
        that haven't been archived yet.
        """
        try:
            db = open_session()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=age_hours)
                sessions = db.query(ChatSession).filter(
                    ChatSession.last_message_at < cutoff,
                    ChatSession.is_active == True,
                ).order_by(
                    ChatSession.id.desc(),
                    ChatSession.last_message_at.desc(),
                ).limit(BATCH_SIZE).all()

                results = []
                for sess in sessions:
                    session_identifiers = self._session_message_identifiers(sess)
                    msgs = db.query(ChatMessage).filter(
                        ChatMessage.tenant_id == sess.tenant_id,
                        ChatMessage.session_id.in_(session_identifiers),
                    ).order_by(ChatMessage.timestamp.asc()).all()

                    if msgs:
                        results.append({
                            "chat_session_id": sess.id,
                            "session_id": sess.user_id,
                            "member_id": sess.member_id or sess.user_id,
                            "tenant_id": sess.tenant_id,
                            "messages": [
                                {"role": m.role, "content": m.content}
                                for m in msgs
                            ],
                            "message_count": len(msgs),
                        })

                return results

            finally:
                db.close()

        except Exception as e:
            logger.error("librarian.scan_failed", error=str(e))
            return []

    async def run_archival_cycle(self) -> dict:
        """Run a complete archival cycle.

        Scans for stale sessions, creates jobs, processes them,
        and stores the results.

        Returns:
            Summary of the cycle results.
        """
        cycle_start = time.time()
        results = {
            "sessions_found": 0,
            "completed": 0,
            "fallback": 0,
            "failed": 0,
        }

        try:
            stale_sessions = await self.scan_stale_sessions()
            results["sessions_found"] = len(stale_sessions)

            for session_info in stale_sessions:
                job = self.create_job(
                    member_id=session_info["member_id"],
                    tenant_id=session_info["tenant_id"],
                    session_id=session_info["session_id"],
                )

                job = await self.process_job(job, session_info["messages"])

                if job.status in (JobStatus.COMPLETED, JobStatus.FALLBACK):
                    await self.store_summary(job)

                    # Mark session as archived
                    try:
                        db = open_session()
                        try:
                            chat_session_id = session_info.get("chat_session_id")
                            if chat_session_id is not None:
                                sess = db.query(ChatSession).filter(
                                    ChatSession.id == chat_session_id,
                                ).first()
                            else:
                                sess = db.query(ChatSession).filter(
                                    ChatSession.user_id == session_info["session_id"],
                                ).first()
                            if sess:
                                sess.is_active = False
                                db.commit()
                        finally:
                            db.close()
                    except Exception:
                        pass

                if job.status == JobStatus.COMPLETED:
                    results["completed"] += 1
                elif job.status == JobStatus.FALLBACK:
                    results["fallback"] += 1
                else:
                    results["failed"] += 1

            results["duration_s"] = round(time.time() - cycle_start, 2)

            logger.info(
                "librarian.cycle_complete",
                **results,
            )

        except Exception as e:
            logger.error("librarian.cycle_failed", error=str(e))
            results["error"] = str(e)

        return results

    # ─── Stream Handler ───────────────────────────────────────────────

    async def handle_stream_message(self, message) -> None:
        """Handle a message from the Redis Stream.

        Expected payload:
        {
            "member_id": "...",
            "tenant_id": 1,
            "session_id": "...",
            "messages": [{"role": "...", "content": "..."}]
        }
        """
        payload = message.payload if hasattr(message, "payload") else message

        member_id = payload.get("member_id", "unknown")
        tenant_id = int(payload.get("tenant_id", 0))
        session_id = payload.get("session_id")
        messages = payload.get("messages", [])

        if not messages:
            logger.warning("librarian.empty_messages", member_id=member_id)
            return

        job = self.create_job(member_id, tenant_id, session_id)
        job = await self.process_job(job, messages)

        if job.status in (JobStatus.COMPLETED, JobStatus.FALLBACK):
            await self.store_summary(job)
