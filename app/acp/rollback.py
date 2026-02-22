"""ARNI v1.4 – Rollback Manager.

@DEVOPS: Sprint 6a, Task 6a.4
Git-based safety net for self-improvement tasks.
Creates checkpoints before refactoring and reverts on failure.
"""

from __future__ import annotations

import time
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger()


class RollbackError(Exception):
    """Raised when rollback operations fail."""
    pass


class RollbackManager:
    """Manages git checkpoints for safe self-refactoring.

    Workflow:
    1. create_checkpoint("refactor-xyz") → git tag / branch
    2. Apply changes
    3. Run tests
    4. If failure: revert_to("refactor-xyz") → git reset --hard
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()

    def _git(self, args: list[str]) -> str:
        """Execute git command in root dir."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error("rollback.git_error", cmd=args, stderr=e.stderr)
            raise RollbackError(f"Git command failed: {e.stderr}") from e

    def create_checkpoint(self, name: str) -> str:
        """Create a safety checkpoint (git tag).

        Args:
            name: Checkpoint identifier (e.g. "pre-refactor-login").

        Returns:
            Tag name created.
        """
        timestamp = int(time.time())
        tag_name = f"checkpoint/{name}-{timestamp}"
        
        # Ensure clean state (optional, but safer)
        # self._git(["stash"]) 
        
        # Create tag
        self._git(["tag", "-a", tag_name, "-m", f"Checkpoint: {name}"])
        logger.info("rollback.checkpoint_created", tag=tag_name)
        return tag_name

    def revert_to(self, tag_name: str) -> None:
        """Revert workspace to a specific checkpoint.

        WARNING: This performs `git reset --hard`!
        Uncommitted changes since checkpoint will be lost.

        Args:
            tag_name: Checkpoint tag to revert to.
        """
        logger.warning("rollback.reverting", tag=tag_name)
        
        # 1. Hard reset to tag
        self._git(["reset", "--hard", tag_name])
        
        # 2. Clean untracked files (new files created during failed refactor)
        self._git(["clean", "-fd"])
        
        logger.info("rollback.revert_complete", tag=tag_name)

    def cleanup_checkpoint(self, tag_name: str) -> None:
        """Delete a checkpoint tag (after successful operation)."""
        self._git(["tag", "-d", tag_name])
        logger.info("rollback.checkpoint_deleted", tag=tag_name)
