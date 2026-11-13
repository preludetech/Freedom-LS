"""A host imports only names a framework module lists in `__all__`."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

FRAMEWORK = "freedom_ls.panel_framework"
FREEDOM_LS = Path(__file__).resolve().parents[3]
PUBLIC_MODULES = [
    "actions",
    "bulk_actions",
    "bulk_runs",
    "config",
    "context",
    "errors",
    "events",
    "filters",
    "forms",
    "housekeeping",
    "lazy_panels",
    "models",
    "panels",
    "quick_view",
    "reference",
    "run_records",
    "tables",
    "views",
]


def _host_files() -> list[Path]:
    framework_dir = FREEDOM_LS / "panel_framework"
    return [
        path for path in FREEDOM_LS.rglob("*.py") if framework_dir not in path.parents
    ]


def _framework_imports(path: Path) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return [
        (node.module.removeprefix(f"{FRAMEWORK}."), alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith(f"{FRAMEWORK}.")
        for alias in node.names
    ]


def _is_public(module: str, name: str) -> bool:
    exported = getattr(
        importlib.import_module(f"{FRAMEWORK}.{module}"), "__all__", None
    )
    return exported is not None and name in exported


def test_hosts_import_only_public_names() -> None:
    private = [
        f"{path.relative_to(FREEDOM_LS)} imports {name} from {module}"
        for path in _host_files()
        for module, name in _framework_imports(path)
        if not _is_public(module, name)
    ]

    assert private == []


@pytest.mark.parametrize("module", PUBLIC_MODULES)
def test_every_public_name_exists(module: str) -> None:
    imported = importlib.import_module(f"{FRAMEWORK}.{module}")

    assert [name for name in imported.__all__ if not hasattr(imported, name)] == []
