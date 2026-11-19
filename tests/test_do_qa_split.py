"""`do_qa.md` stays short, and each branch it reads only sometimes lives in its own resource."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

ROOT = Path(__file__).resolve().parents[1]
DO_QA = ROOT / "claude_plugins/sdd/commands/do_qa.md"
BRANCH_FILES = sorted((ROOT / "claude_plugins/sdd/resources").glob("do_qa_*.md"))
NAMED_MARKDOWN_PATHS = sorted(
    set(re.findall(r"claude_plugins/[\w./-]+\.md", DO_QA.read_text()))
)
STEP_HEADING = re.compile(r"^#+ .*\bStep \d+", re.M)


def test_do_qa_has_fewer_than_500_lines() -> None:
    assert len(DO_QA.read_text().splitlines()) < 500


def test_do_qa_has_branch_files_to_name() -> None:
    assert BRANCH_FILES


@pytest.mark.parametrize("branch_file", BRANCH_FILES, ids=lambda p: p.name)
def test_do_qa_names_each_branch_file(branch_file: Path) -> None:
    assert f"claude_plugins/sdd/resources/{branch_file.name}" in DO_QA.read_text()


@pytest.mark.parametrize("branch_file", BRANCH_FILES, ids=lambda p: p.name)
def test_branch_file_holds_no_step_heading(branch_file: Path) -> None:
    assert STEP_HEADING.findall(branch_file.read_text()) == []


@pytest.mark.parametrize("path", NAMED_MARKDOWN_PATHS)
def test_every_markdown_path_do_qa_names_exists(path: str) -> None:
    assert (ROOT / path).is_file()


@pytest.mark.parametrize("number", range(0, 18))
def test_do_qa_keeps_each_step_heading(number: int) -> None:
    assert re.search(rf"^## Step {number}: ", DO_QA.read_text(), re.M)
