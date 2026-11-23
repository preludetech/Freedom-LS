"""The sdd plugin names no tool a project could swap out.

sdd is copied into projects that test, lint, build and deploy in their own way. It reaches a
project's tools only through the hook keys in `.claude/sdd/config.md`, so a test runner, language
tool, framework, CI service or another plugin's path in its files is a defect.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD = REPO_ROOT / "claude_plugins/sdd"
TEXT_SUFFIXES = frozenset({".md", ".py", ".sh", ".js", ".jsx", ".json", ".svg"})

BANNED = {
    "pytest": re.compile(r"pytest", re.IGNORECASE),
    "uv": re.compile(r"\buv (?:run|add|sync|pip)\b"),
    "manage.py": re.compile(r"manage\.py"),
    "django": re.compile(r"django", re.IGNORECASE),
    "ruff": re.compile(r"\bruff\b", re.IGNORECASE),
    "mypy": re.compile(r"\bmypy\b", re.IGNORECASE),
    "xdist": re.compile(r"xdist", re.IGNORECASE),
    "pyproject": re.compile(r"pyproject", re.IGNORECASE),
    "GitHub Actions": re.compile(r"github actions", re.IGNORECASE),
    "node id": re.compile(r"\bnode[ _-]?ids?\b", re.IGNORECASE),
    "selector flag": re.compile(r"--(?:working-tree|range|upstream-range|wide)\b"),
    "test tier": re.compile(
        r"test tiers?\b|tier definition|run_test_tier", re.IGNORECASE
    ),
    "full-run record": re.compile(r"full_run_record|full-run record", re.IGNORECASE),
    "another plugin's path": re.compile(r"claude_plugins/(?!sdd\b)[\w-]+"),
    "another plugin's skill": re.compile(r"\b(?:ds|fls-dev):[a-z]"),
}

# A file that still names a tool, and why. An entry whose file is clean fails the test.
EXCEPTIONS: dict[str, str] = {}


def banned_names(text: str) -> list[str]:
    return [name for name, pattern in BANNED.items() if pattern.search(text)]


def sdd_text_files() -> list[Path]:
    return sorted(
        path
        for path in SDD.rglob("*")
        if path.is_file()
        and path.suffix in TEXT_SUFFIXES
        and "__pycache__" not in path.parts
    )


def files_naming_a_tool() -> dict[str, list[str]]:
    found = {
        path.relative_to(SDD).as_posix(): banned_names(path.read_text(encoding="utf-8"))
        for path in sdd_text_files()
    }
    return {name: names for name, names in found.items() if names}


def test_no_sdd_file_names_a_project_tool() -> None:
    found = files_naming_a_tool()

    assert {
        name: names for name, names in found.items() if name not in EXCEPTIONS
    } == {}


def test_every_exception_still_names_a_tool() -> None:
    assert sorted(EXCEPTIONS) == sorted(
        name for name in files_naming_a_tool() if name in EXCEPTIONS
    )


@pytest.mark.parametrize(
    "text",
    [
        "run `uv run pytest`",
        "the final pytest summary line",
        "by node ID, three times",
        "claude_plugins/django-stack/resources/test_tiers.md",
        "the `targeted` test tier",
        "use the ds:testing skill",
        "`<diff>`: `--working-tree`",
    ],
)
def test_banned_names_catches_a_tool_name(text: str) -> None:
    assert banned_names(text) != []


@pytest.mark.parametrize(
    "text",
    [
        "claude_plugins/sdd/commands/protected/run_tests.md",
        "follow the `Test runner` hook with the request `change`",
        "each agent's `model:` frontmatter sets its tier",
        "the test ids the runner returned",
    ],
)
def test_banned_names_passes_neutral_wording(text: str) -> None:
    assert banned_names(text) == []
