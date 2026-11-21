import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2]
APP_PACKAGE = "freedom_ls.icons"


def _is_foreign(module: str) -> bool:
    if module != "freedom_ls" and not module.startswith("freedom_ls."):
        return False
    return module != APP_PACKAGE and not module.startswith(APP_PACKAGE + ".")


def foreign_imports(path: Path) -> list[str]:
    """Each import in `path` of a freedom_ls module outside the icons app,
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


def base_dir_reads(path: Path) -> list[str]:
    """Each read of a BASE_DIR setting in `path`, as "<path>:<line>: <form>".

    A host's BASE_DIR is not the icons app's to read: the app finds its own data
    from its own location.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Name) and node.id == "BASE_DIR":
            found.append(f"{path}:{node.lineno}: BASE_DIR")
        elif isinstance(node, ast.Attribute) and node.attr == "BASE_DIR":
            found.append(f"{path}:{node.lineno}: .BASE_DIR")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "BASE_DIR"
        ):
            found.append(f"{path}:{node.lineno}: getattr(..., 'BASE_DIR')")
    return found


def app_files() -> list[Path]:
    """Every .py file under the icons app, its tests and this guard included."""
    return sorted(APP_ROOT.rglob("*.py"))


def _relative_ids(paths: list[Path]) -> list[str]:
    return [str(path.relative_to(APP_ROOT)) for path in paths]


@pytest.mark.parametrize("path", app_files(), ids=_relative_ids(app_files()))
def test_an_app_file_imports_no_other_freedom_ls_module(path: Path) -> None:
    assert foreign_imports(path) == []


@pytest.mark.parametrize("path", app_files(), ids=_relative_ids(app_files()))
def test_an_app_file_never_reads_base_dir(path: Path) -> None:
    assert base_dir_reads(path) == []


@pytest.mark.parametrize(
    ("source", "reported"),
    [
        ("from freedom_ls.base import csv_safety\n", True),
        ("import freedom_ls.base.csv_safety\n", True),
        ("import freedom_ls\n", True),
        ("from freedom_ls.icons import config\n", False),
        ("from . import helpers\n", False),
        ("import freedom_ls_other\n", False),
    ],
)
def test_foreign_imports_reports_only_modules_outside_the_icons_app(
    tmp_path: Path, source: str, reported: bool
) -> None:
    # Arrange
    module = tmp_path / "module.py"
    module.write_text("x = 1\n" + source)

    # Act
    found = foreign_imports(module)

    # Assert
    assert bool(found) is reported
    assert all(line.startswith(f"{module}:2: ") for line in found)


@pytest.mark.parametrize(
    ("source", "reported"),
    [
        ("path = BASE_DIR / 'x'\n", True),
        ("path = settings.BASE_DIR\n", True),
        ("path = getattr(settings, 'BASE_DIR')\n", True),
        ("path = getattr(settings, 'BASE_DIR', None)\n", True),
        ("path = getattr(settings, name)\n", False),
        ("path = settings.SEMANTIC_ICONS_ICONIFY_DIR\n", False),
    ],
)
def test_base_dir_reads_reports_each_way_of_reading_base_dir(
    tmp_path: Path, source: str, reported: bool
) -> None:
    # Arrange
    module = tmp_path / "module.py"
    module.write_text("x = 1\n" + source)

    # Act
    found = base_dir_reads(module)

    # Assert
    assert bool(found) is reported
    assert all(line.startswith(f"{module}:2: ") for line in found)
