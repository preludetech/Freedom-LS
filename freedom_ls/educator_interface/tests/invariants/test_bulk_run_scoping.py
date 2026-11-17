"""Every read of a bulk-action run in production code names a site.

`BulkActionRun.objects` filters by no site, so a bare `.filter()` or `.all()`
on it would read every tenant's runs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# The manager methods that name a site themselves. Anything else on `objects` reads every site's runs.
SCOPED = ("for_site", "for_request", "create")

PACKAGE_ROOT = Path(__file__).parents[3]
EXCLUDED_DIRECTORIES = {"tests", "migrations"}


def unscoped_run_reads(path: Path) -> list[str]:
    """Each `BulkActionRun.objects.<method>` in `path` whose method does not
    scope the read to a site, as "<path>:<line>: <method>"."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Attribute) or node.attr in SCOPED:
            continue
        manager = node.value
        if (
            isinstance(manager, ast.Attribute)
            and manager.attr == "objects"
            and isinstance(manager.value, ast.Name)
            and manager.value.id == "BulkActionRun"
        ):
            found.append(f"{path}:{node.lineno}: {node.attr}")
    return found


def production_files() -> list[Path]:
    """Every .py file under freedom_ls/, minus tests/ and migrations/ directories."""
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if not EXCLUDED_DIRECTORIES & set(path.relative_to(PACKAGE_ROOT).parts)
    ]


def test_no_production_code_reads_runs_across_sites() -> None:
    reads = [read for path in production_files() for read in unscoped_run_reads(path)]

    assert reads == []


@pytest.mark.parametrize(
    ("source", "method"),
    [
        ("BulkActionRun.objects.filter(pk=1)", "filter"),
        ("BulkActionRun.objects.get(pk=1)", "get"),
        ("BulkActionRun.objects.all()", "all"),
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
        "BulkActionRun._base_manager.filter()",
    ],
)
def test_a_scoped_read_is_not_reported(tmp_path: Path, source: str) -> None:
    module = tmp_path / "reads.py"
    module.write_text(f"{source}\n")

    assert unscoped_run_reads(module) == []
