"""ARIIA v1.4 – Long-Term Knowledge Store.

@BACKEND: Sprint 4, Task 4.5
Manages per-member knowledge files in data/knowledge/members/{id}.md.
"""

from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger()

DEFAULT_KNOWLEDGE_DIR = "data/knowledge/members"


class KnowledgeStore:
    """Persistent per-member knowledge as Markdown files.

    Each member gets a file: data/knowledge/members/{user_id}.md
    Facts are appended with timestamps for audit trail.
    """

    def __init__(self, base_dir: str = DEFAULT_KNOWLEDGE_DIR) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _user_path(self, user_id: str) -> Path:
        """Get the knowledge file path for a user."""
        safe_id = user_id.replace("/", "_").replace("\\", "_")
        return self._base_dir / f"{safe_id}.md"

    def append_facts(self, user_id: str, facts: list[str]) -> int:
        """Append extracted facts to a member's knowledge file.

        Args:
            user_id: Member identifier.
            facts: List of fact strings to store.

        Returns:
            Number of facts appended.
        """
        if not facts:
            return 0

        path = self._user_path(user_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Create file with header if new
        if not path.exists():
            path.write_text(
                f"# Mitglied: {user_id}\n\n"
                f"> Erstellt: {now} | Auto-generiert durch Silent Flush\n\n"
                f"---\n\n"
            )

        # Append facts
        with path.open("a") as f:
            f.write(f"### {now}\n")
            for fact in facts:
                f.write(f"- {fact}\n")
            f.write("\n")

        logger.info("knowledge.facts_appended", user_id=user_id, count=len(facts))
        return len(facts)

    def get_facts(self, user_id: str) -> str:
        """Read all knowledge for a member.

        Args:
            user_id: Member identifier.

        Returns:
            Markdown content or empty string if no file exists.
        """
        path = self._user_path(user_id)
        if path.exists():
            return path.read_text()
        return ""

    def has_knowledge(self, user_id: str) -> bool:
        """Check if a member has a knowledge file."""
        return self._user_path(user_id).exists()

    def delete_member(self, user_id: str) -> bool:
        """Delete all knowledge for a member (GDPR Art. 17).

        Returns:
            True if file existed and was deleted.
        """
        path = self._user_path(user_id)
        if path.exists():
            path.unlink()
            logger.info("knowledge.deleted", user_id=user_id, reason="art17_erasure")
            return True
        return False

    def list_members(self) -> list[str]:
        """List all member IDs with knowledge files."""
        return [p.stem for p in self._base_dir.glob("*.md")]
