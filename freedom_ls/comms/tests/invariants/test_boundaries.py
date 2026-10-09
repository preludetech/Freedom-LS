"""comms runtime modules never import the apps built on top of it or the apps
that would couple its delivery seam to one consumer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import freedom_ls.comms

FORBIDDEN_APPS = (
    "freedom_ls.webhooks",
    "freedom_ls.learner_management",
    "freedom_ls.organisations",
    "freedom_ls.role_based_permissions",
    "freedom_ls.messaging_policy",
)


def _imported_modules(path: Path) -> set[str]:
    """Every module an Import or ImportFrom statement in this file names."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _runtime_files() -> list[Path]:
    comms_dir = Path(freedom_ls.comms.__file__).parent
    return [
        path
        for path in comms_dir.rglob("*.py")
        if "migrations" not in path.parts and "tests" not in path.parts
    ]


@pytest.mark.parametrize("app", FORBIDDEN_APPS)
def test_no_runtime_module_under_comms_imports(app: str) -> None:
    # Import statements, not text: the MESSAGING_POLICY default is a dotted string
    # that names the messaging_policy app without importing it.
    offenders = [
        str(path)
        for path in _runtime_files()
        if any(m == app or m.startswith(f"{app}.") for m in _imported_modules(path))
    ]

    assert not offenders, f"These files import {app}: {offenders}"
