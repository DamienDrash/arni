"""ARIIA – Architecture Guardrail Tests (Epic 2).

These tests ensure we do not introduce new architectural violations during
the Domain-Driven Modular Monolith refactoring. They parse the Python AST to
detect anti-patterns like direct SessionLocal() calls or importing from
core.models in new domain modules.
"""

import ast
import os
from pathlib import Path

import pytest

# The current backend root
APP_DIR = Path(__file__).parent.parent.parent / "app"

BASELINE_CORE_MODELS_IMPORTS = 0  # Epic 7.3 complete: no productive app.core.models imports remain in app/
ALLOWED_SESSIONLOCAL_FILES = {
    (APP_DIR / "core" / "db.py").resolve(),
    (APP_DIR / "shared" / "db.py").resolve(),
}
ALLOWED_COMPAT_ENTRYPOINTS = {
    (APP_DIR / "gateway" / "main.py").resolve(),
    (APP_DIR / "worker" / "main.py").resolve(),
}


def get_python_files(directory: Path) -> list[Path]:
    """Return all .py files in the given directory recursively."""
    files = []
    for root, _, filenames in os.walk(directory):
        for name in filenames:
            if name.endswith(".py") and name != "__init__.py":
                files.append(Path(root) / name)
    return files


class ArchitectureViolationVisitor(ast.NodeVisitor):
    """AST Visitor to find specific architecture violations in a file."""
    
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.session_local_calls = 0
        self.core_models_imports = 0

    def visit_Call(self, node: ast.Call) -> None:
        # Detect `SessionLocal()` calls
        if isinstance(node.func, ast.Name) and node.func.id == "SessionLocal":
            self.session_local_calls += 1
        
        # Also detect `app.core.db.SessionLocal()` 
        if isinstance(node.func, ast.Attribute) and node.func.attr == "SessionLocal":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "db":
                self.session_local_calls += 1
                
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # Detect `from app.core.models import ...` or `from app.core import models`
        if node.module == "app.core.models":
            self.core_models_imports += 1
        elif node.module == "app.core" and any(alias.name == "models" for alias in node.names):
            self.core_models_imports += 1
            
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        # Detect `import app.core.models`
        for alias in node.names:
            if alias.name == "app.core.models":
                self.core_models_imports += 1
                
        self.generic_visit(node)


def test_guardrail_session_local_restricted_to_db_layers() -> None:
    """ENSURE SessionLocal is only referenced inside the intentional DB layers."""
    violations: list[str] = []
    py_files = get_python_files(APP_DIR)

    for py_file in py_files:
        resolved = py_file.resolve()
        if resolved in ALLOWED_SESSIONLOCAL_FILES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            if "SessionLocal" in content:
                violations.append(str(py_file.relative_to(APP_DIR.parent)))
        except SyntaxError:
            pass  # Ignore invalid python files during active development

    assert not violations, (
        "Architecture Violation: SessionLocal is only allowed in "
        "`app/core/db.py` and `app/shared/db.py`. Found forbidden references in: "
        + ", ".join(sorted(violations))
    )


def test_guardrail_core_models_no_new_imports() -> None:
    """ENSURE no new files import directly from `app.core.models`.
    
    Refactoring Goal (Epic 7): Split models into domain-specific files and 
    use cross-domain query services instead of direct ORM imports.
    """
    total_imports = 0
    py_files = get_python_files(APP_DIR)
    
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            visitor = ArchitectureViolationVisitor(py_file)
            visitor.visit(tree)
            total_imports += visitor.core_models_imports
        except SyntaxError:
            pass
            
    # For this test, we just want to ensure it runs and tracks the number.
    # We will print the current baseline so it can be updated.
    
    assert total_imports <= BASELINE_CORE_MODELS_IMPORTS, (
        f"Architecture Violation: Found {total_imports} imports from app.core.models, "
        f"which exceeds the baseline of {BASELINE_CORE_MODELS_IMPORTS}. "
        f"Do not couple new domain logic to the monolithic models file."
    )


def test_guardrail_legacy_compat_entrypoints_do_not_spread() -> None:
    """ENSURE new top-level compatibility shims are not introduced silently."""
    violations: list[str] = []
    py_files = get_python_files(APP_DIR)

    for py_file in py_files:
        resolved = py_file.resolve()
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        header = content[:400].lower()
        if "compatibility shim" in header or "compatibility wrapper" in header:
            if resolved not in ALLOWED_COMPAT_ENTRYPOINTS:
                violations.append(str(py_file.relative_to(APP_DIR.parent)))

    assert not violations, (
        "Architecture Violation: New compatibility entrypoints were introduced outside the "
        "approved shim allowlist: " + ", ".join(sorted(violations))
    )
