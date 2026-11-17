import ast
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent

# Directories whose tests still exercise the host project's templates.
EXEMPT_DIRECTORIES = ("tests/components", "tests/invariants", "tests/playwright")

FRAMEWORK_PACKAGE = "freedom_ls.panel_framework"


def _is_foreign(module: str) -> bool:
    if module != "freedom_ls" and not module.startswith("freedom_ls."):
        return False
    return module != FRAMEWORK_PACKAGE and not module.startswith(
        FRAMEWORK_PACKAGE + "."
    )


def foreign_imports(path: Path) -> list[str]:
    """Each import in `path` of a freedom_ls module outside the framework,
    as "<path>:<line>: <import>"."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_foreign(alias.name):
                    found.append(f"{path}:{node.lineno}: import {alias.name}")
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and _is_foreign(node.module)
        ):
            found.append(f"{path}:{node.lineno}: from {node.module} import ...")
    return found


def framework_files() -> list[Path]:
    """Every .py file under the framework, minus the exempt directories."""
    exempt = [FRAMEWORK_ROOT / directory for directory in EXEMPT_DIRECTORIES]
    return [
        path
        for path in sorted(FRAMEWORK_ROOT.rglob("*.py"))
        if not any(path.is_relative_to(directory) for directory in exempt)
    ]


def test_the_framework_imports_no_other_freedom_ls_module() -> None:
    found = [line for path in framework_files() for line in foreign_imports(path)]

    assert found == []


@pytest.mark.parametrize(
    ("source", "reported"),
    [
        ("from freedom_ls.base import csv_safety\n", True),
        ("import freedom_ls.base.csv_safety\n", True),
        ("import freedom_ls\n", True),
        ("from freedom_ls.panel_framework import models\n", False),
        ("from . import helpers\n", False),
        ("import freedom_ls_other\n", False),
    ],
)
def test_foreign_imports_reports_only_modules_outside_the_framework(
    tmp_path: Path, source: str, reported: bool
) -> None:
    # Arrange
    module = tmp_path / "module.py"
    module.write_text("x = 1\n" + source)

    # Act
    found = foreign_imports(module)

    # Assert
    if reported:
        assert len(found) == 1
        assert found[0].startswith(f"{module}:2: ")
    else:
        assert found == []


def test_framework_files_cover_migrations_and_tests_but_not_exempt_directories() -> (
    None
):
    files = framework_files()

    assert any("migrations" in path.parts for path in files)
    assert any(path.parent == FRAMEWORK_ROOT / "tests" for path in files)
    for directory in EXEMPT_DIRECTORIES:
        assert not any(
            path.is_relative_to(FRAMEWORK_ROOT / directory) for path in files
        )
