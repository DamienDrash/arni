"""Tests for ACP Pipeline (Sprint 6a)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.acp.sandbox import Sandbox, SandboxViolation
from app.acp.rollback import RollbackManager
from app.acp.refactor import RefactoringEngine


class TestSandbox:
    @pytest.fixture
    def sandbox(self, tmp_path):
        return Sandbox(tmp_path)

    def test_validate_path_inside_root(self, sandbox, tmp_path):
        """Path inside root should be valid."""
        p = sandbox.validate_path("test.txt")
        assert p == tmp_path / "test.txt"

    def test_validate_path_outside_root(self, sandbox):
        """Path attempting traversal should fail."""
        with pytest.raises(SandboxViolation):
            sandbox.validate_path("../../../etc/passwd")

    def test_forbidden_path_access(self, sandbox):
        """Access to .env or .git should be forbidden."""
        with pytest.raises(SandboxViolation):
            sandbox.validate_path(".env")
        with pytest.raises(SandboxViolation):
            sandbox.validate_path(".git/config")

    def test_write_restriction(self, sandbox):
        """Write should only be allowed in specific dirs."""
        # 'app' is allowed
        p = sandbox.validate_path("app/test.py", allow_write=True)
        assert p.name == "test.py"
        
        # 'random_dir' is not allowed for write
        with pytest.raises(SandboxViolation):
            sandbox.validate_path("random_dir/test.py", allow_write=True)

    def test_run_safe_command(self, sandbox):
        """Safe commands should execute."""
        code, stdout, _ = sandbox.run_safe(["echo", "hello"])
        assert code == 0
        assert "hello" in stdout

    def test_read_write_file(self, sandbox):
        """File I/O should work within constraints."""
        sandbox.write_file("app/test.txt", "content")
        assert sandbox.read_file("app/test.txt") == "content"


class TestRollback:
    @patch("subprocess.run")
    def test_create_checkpoint(self, mock_run, tmp_path):
        """Should call git tag."""
        manager = RollbackManager(tmp_path)
        mock_run.return_value.stdout = "v1"
        
        tag = manager.create_checkpoint("test")
        assert "checkpoint/test" in tag
        assert mock_run.call_count >= 1

    @patch("subprocess.run")
    def test_revert(self, mock_run, tmp_path):
        """Should call git reset --hard."""
        manager = RollbackManager(tmp_path)
        manager.revert_to("tag-1")
        
        # Verify reset --hard was called
        args_list = [call.args[0] for call in mock_run.call_args_list]
        assert any("reset" in args and "--hard" in args for args in args_list)
        assert any("clean" in args for args in args_list)


class TestRefactor:
    @pytest.fixture
    def engine(self, tmp_path):
        sandbox = Sandbox(tmp_path)
        return RefactoringEngine(sandbox)

    def test_analyze_missing_docstring(self, engine, tmp_path):
        """Should detect missing docstring."""
        code = "def foo():\n    pass"
        p = tmp_path / "app/code.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code)

        issues = engine.analyze_file("app/code.py")
        assert len(issues) == 1
        assert issues[0].issue_type == "missing_docstring"

    def test_analyze_long_function(self, engine, tmp_path):
        """Should detect long function."""
        # 60 lines
        body = "\n".join(["    pass" for _ in range(60)])
        code = f"def long_foo():\n{body}"
        
        p = tmp_path / "app/long.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code)

        issues = engine.analyze_file("app/long.py")
        assert len(issues) == 2 # missing docstring + too long
        types = [i.issue_type for i in issues]
        assert "function_too_long" in types
