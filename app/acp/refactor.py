"""ARIIA v1.4 – Refactoring Engine.

@BACKEND: Sprint 6a, Task 6a.3
Simple static analysis and auto-refactoring suggestions.
Uses AST to find issues (missing docs, long functions).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from app.acp.sandbox import Sandbox

logger = structlog.get_logger()


@dataclass
class CodeIssue:
    """Identified code quality issue."""
    file_path: str
    line_number: int
    issue_type: str
    message: str
    severity: str = "warning"


@dataclass
class RefactorProposal:
    """Proposed refactoring changes."""
    file_path: str
    description: str
    diff: str  # unified diff format


class RefactoringEngine:
    """Static analysis and refactoring engine.

    Capabilities:
    - Parse Python code via AST
    - Identify missing docstrings
    - Identify long functions (> 50 lines)
    - Suggest fixes (Stub for now: only identifies issues)
    """

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    def analyze_file(self, file_path: str) -> list[CodeIssue]:
        """Analyze a file for code quality issues."""
        try:
            content = self._sandbox.read_file(file_path)
            tree = ast.parse(content)
            issues = []

            for node in ast.walk(tree):
                # 1. Check for missing docstrings
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    if not self._has_docstring(node):
                        issues.append(
                            CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="missing_docstring",
                                message=f"Missing docstring in {node.name}",
                            )
                        )

                # 2. Check function length
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = node.end_lineno - node.lineno
                    if length > 50:
                        issues.append(
                            CodeIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="function_too_long",
                                message=f"Function {node.name} is too long ({length} lines)",
                                severity="info",
                            )
                        )

            return issues

        except SyntaxError as e:
            return [
                CodeIssue(
                    file_path=file_path,
                    line_number=e.lineno or 0,
                    issue_type="syntax_error",
                    message=f"Syntax error: {e.msg}",
                    severity="error",
                )
            ]
        except Exception as e:
            logger.error("refactor.analysis_failed", file=file_path, error=str(e))
            return []

    def _has_docstring(self, node: ast.AST) -> bool:
        """Check if AST node has a docstring."""
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)):
            return False
        return ast.get_docstring(node) is not None
