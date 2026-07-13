"""Architecture tests that prevent forbidden framework and model dependencies."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "vinami"
CONTEXTS = (
    "patient",
    "clinical_case",
    "triage",
    "ecg",
    "troponin",
    "reasoning",
    "workflow",
    "alerts",
    "timeline",
    "audit",
    "model_registry",
    "identity",
)
LAYERS = ("domain", "application", "ports", "adapters", "api")


def imports_in(path: Path) -> set[str]:
    """Collect imported module roots without importing application code."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def python_files(path: Path) -> list[Path]:
    """Return tracked Python files in one architecture layer."""
    return sorted(path.rglob("*.py"))


def assert_no_imports(
    paths: list[Path],
    forbidden_roots: set[str],
    forbidden_prefixes: tuple[str, ...] = (),
    forbidden_fragments: tuple[str, ...] = (),
) -> None:
    """Fail with a direct file/module explanation for every prohibited import."""
    violations: list[str] = []
    for path in paths:
        for module in imports_in(path):
            if (
                module.split(".")[0] in forbidden_roots
                or module.startswith(forbidden_prefixes)
                or any(fragment in module for fragment in forbidden_fragments)
            ):
                violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")
    assert not violations, "\n".join(violations)


def test_all_context_layers_are_importable_packages() -> None:
    """Keep each bounded-context/layer boundary materialized in the repository."""
    for context in CONTEXTS:
        for layer in LAYERS:
            importlib.import_module(f"vinami.{context}.{layer}")


def test_domain_does_not_import_framework_or_infrastructure() -> None:
    """Domain code remains independent of delivery, ORM, and model runtimes."""
    domain_files = [
        path for context in CONTEXTS for path in python_files(SOURCE_ROOT / context / "domain")
    ]
    assert_no_imports(
        domain_files,
        {"fastapi", "sqlalchemy", "streamlit", "torch", "timm", "onnxruntime", "redis"},
        ("vinami.shared.database", "vinami.shared.container"),
        (".adapters", ".api"),
    )


def test_application_does_not_import_streamlit() -> None:
    """Application layer cannot acquire UI dependencies."""
    application_files = [
        path for context in CONTEXTS for path in python_files(SOURCE_ROOT / context / "application")
    ]
    assert_no_imports(application_files, {"streamlit"})


def test_dashboard_does_not_import_database_sessions() -> None:
    """The UI must remain an API client rather than a second database access path."""
    assert_no_imports(
        python_files(PROJECT_ROOT / "apps" / "dashboard"),
        {"sqlalchemy"},
        ("vinami.shared.database",),
    )


def test_workflow_does_not_import_model_implementations() -> None:
    """Workflow code cannot depend on model runtimes or provider implementations."""
    assert_no_imports(
        python_files(SOURCE_ROOT / "workflow"),
        {"torch", "timm", "onnxruntime", "tensorflow"},
        ("vinami.ecg.adapters",),
    )


def test_api_routers_do_not_import_orm_sessions_or_infrastructure_records() -> None:
    """R1 delivery code may call handlers but cannot become a second persistence layer."""
    assert_no_imports(
        [PROJECT_ROOT / "apps" / "api" / "lifecycle.py"],
        {"sqlalchemy"},
        ("vinami.shared.database",),
        (".adapters",),
    )


def test_r1_application_handlers_do_not_import_delivery_or_model_runtimes() -> None:
    """The lifecycle application path remains transport and AI implementation independent."""
    files = [
        SOURCE_ROOT / "patient" / "application" / "lifecycle.py",
        SOURCE_ROOT / "clinical_case" / "application" / "lifecycle.py",
    ]
    assert_no_imports(
        files,
        {"fastapi", "streamlit", "sqlalchemy", "torch", "timm", "onnxruntime"},
    )


def test_domain_does_not_import_another_context_domain() -> None:
    """Context domains communicate through IDs, events, and shared value objects only."""
    violations: list[str] = []
    for context in CONTEXTS:
        for path in python_files(SOURCE_ROOT / context / "domain"):
            for module in imports_in(path):
                for other_context in CONTEXTS:
                    if other_context != context and module.startswith(
                        f"vinami.{other_context}.domain"
                    ):
                        violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")
    assert not violations, "\n".join(violations)
