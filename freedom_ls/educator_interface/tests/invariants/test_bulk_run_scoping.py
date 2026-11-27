"""Every read of a bulk-action run in production code names a site.

`BulkActionRun.objects` filters by no site, so a bare `.filter()` or `.all()`
on it would read every tenant's runs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from django.contrib.sites.models import Site

# The manager methods that name a site themselves. Anything else on `objects` reads every site's runs.
SCOPED = ("for_site", "for_request", "create")
# Managers with no for_site or for_request: any use of them is reported.
UNSCOPED_MANAGERS = ("_default_manager", "_base_manager")
ALLOWED: set[tuple[str, str]] = set()

PACKAGE_ROOT = Path(__file__).parents[3]
EXCLUDED_DIRECTORIES = {"tests", "migrations"}


def _is_run_model(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "BulkActionRun"


def unscoped_run_reads(path: Path) -> list[str]:
    """Each read of `BulkActionRun` in `path` that does not name a site, as
    "<path>:<line>: <what>": a method on `objects` other than SCOPED, `objects`
    itself kept for later, or any use of an UNSCOPED_MANAGERS manager."""
    tree = ast.parse(path.read_text())
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not _is_run_model(node.value):
            continue
        if node.attr in UNSCOPED_MANAGERS:
            found.append(f"{path}:{node.lineno}: {node.attr}")
        elif node.attr == "objects":
            method = parents.get(node)
            if not isinstance(method, ast.Attribute):
                found.append(f"{path}:{node.lineno}: objects")
            elif method.attr not in SCOPED:
                found.append(f"{path}:{node.lineno}: {method.attr}")
    return found


def _allowed(path: Path, read: str) -> bool:
    relative = path.relative_to(PACKAGE_ROOT).as_posix()
    return (relative, read.split(": ")[-1]) in ALLOWED


def production_files() -> list[Path]:
    """Every .py file under freedom_ls/, minus tests/ and migrations/ directories."""
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if not EXCLUDED_DIRECTORIES & set(path.relative_to(PACKAGE_ROOT).parts)
    ]


def test_no_production_code_reads_runs_across_sites() -> None:
    reads = [
        read
        for path in production_files()
        for read in unscoped_run_reads(path)
        if not _allowed(path, read)
    ]

    assert reads == []


@pytest.mark.parametrize(
    ("source", "method"),
    [
        ("BulkActionRun.objects.filter(pk=1)", "filter"),
        ("BulkActionRun.objects.get(pk=1)", "get"),
        ("BulkActionRun.objects.all()", "all"),
        ("runs = BulkActionRun.objects", "objects"),
        ("BulkActionRun._default_manager.filter(pk=1)", "_default_manager"),
        ("BulkActionRun._base_manager.filter(pk=1)", "_base_manager"),
    ],
)
def test_an_unscoped_read_is_reported(tmp_path: Path, source: str, method: str) -> None:
    module = tmp_path / "reads.py"
    module.write_text(f"{source}\n")

    assert unscoped_run_reads(module) == [f"{module}:1: {method}"]


@pytest.mark.parametrize(
    "source",
    [
        "BulkActionRun.objects.for_request(request).filter()",
        "BulkActionRun.objects.for_site(1)",
        "BulkActionRun.objects.create(site=site)",
    ],
)
def test_a_scoped_read_is_not_reported(tmp_path: Path, source: str) -> None:
    module = tmp_path / "reads.py"
    module.write_text(f"{source}\n")

    assert unscoped_run_reads(module) == []


def test_a_site_has_no_reverse_accessor_to_its_runs() -> None:
    assert not hasattr(Site, "bulkactionrun_set")
