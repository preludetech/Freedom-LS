"""FLS names the installed `panel_framework` package, never the old in-tree app.

Only the migration that drops the legacy rows and the tests and helpers that exercise it
may spell the old import path or the `freedom_ls_panel_framework` app label.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCHED_ROOTS = (
    "freedom_ls",
    "config",
    "claude_plugins",
    "test_organisation",
    "docs",
    ".claude/skills",
)
OLD_NAME = re.compile(
    r"freedom_ls\.panel_framework|freedom_ls/panel_framework|freedom_ls_panel_framework"
)
ALLOWED = {
    "freedom_ls/educator_interface/migrations/0004_drop_legacy_panel_framework.py",
    "freedom_ls/educator_interface/tests/migrations/test_0004_drop_legacy_panel_framework.py",
    "freedom_ls/educator_interface/tests/migrations/legacy_rows.py",
    "tests/test_panel_framework_references.py",
}
SEARCHED_SUFFIXES = {".py", ".md", ".html", ".txt", ".toml", ".yml", ".yaml", ".json"}


def _files_naming_the_old_app() -> set[str]:
    candidates = [
        path
        for root in SEARCHED_ROOTS
        for path in (REPO_ROOT / root).rglob("*")
        if path.is_file() and path.suffix in SEARCHED_SUFFIXES
    ]
    candidates.append(Path(__file__))
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for path in candidates
        if OLD_NAME.search(path.read_text(encoding="utf-8", errors="ignore"))
    }


def test_only_the_legacy_cleanup_names_the_old_app() -> None:
    assert _files_naming_the_old_app() == ALLOWED
