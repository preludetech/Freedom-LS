"""The sdd command files ask for the full tier twice: after the last batch and before landing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.plugin_markdown import code_fragments

pytestmark = pytest.mark.dev_tooling

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "claude_plugins/sdd/commands"
RESOURCES = ROOT / "claude_plugins/sdd/resources"
TIER_FULL = re.compile(r"<tier>`?:? *`full`")
TIER_CHECKPOINT = re.compile(r"<tier>`?:? *`checkpoint`")


@pytest.mark.parametrize("name", ["do_qa.md", "qa_fix.md"])
def test_qa_commands_never_ask_for_the_full_tier(name: str) -> None:
    lines = (COMMANDS / name).read_text().splitlines()

    assert [line for line in lines if TIER_FULL.search(line)] == []


@pytest.mark.parametrize(
    "path",
    [
        COMMANDS / "do_qa.md",
        COMMANDS / "qa_fix.md",
        RESOURCES / "do_qa_fix_loop.md",
    ],
    ids=lambda path: path.name,
)
def test_qa_files_never_ask_for_the_checkpoint_tier(path: Path) -> None:
    lines = path.read_text().splitlines()

    assert [line for line in lines if TIER_CHECKPOINT.search(line)] == []


def test_implement_plan_asks_for_the_full_tier_once() -> None:
    text = (COMMANDS / "implement_plan.md").read_text()

    assert len(TIER_FULL.findall(text)) == 1


def test_plan_from_spec_does_not_promise_the_full_suite() -> None:
    assert "full test suite passing" not in (COMMANDS / "plan_from_spec.md").read_text()


def test_finish_worktree_asks_for_the_full_tier_once() -> None:
    text = (COMMANDS / "finish_worktree.md").read_text()

    assert len(TIER_FULL.findall(text)) == 1


def test_finish_worktree_step_one_is_the_full_tier() -> None:
    lines = (COMMANDS / "finish_worktree.md").read_text().splitlines()

    assert "# Step 1: Full tier" in lines


@pytest.mark.parametrize("wording", ["gh pr view", "changes requested"])
def test_finish_worktree_does_not_check_the_pull_request(wording: str) -> None:
    assert wording not in (COMMANDS / "finish_worktree.md").read_text()


@pytest.mark.parametrize(
    "wording",
    [
        "origin/main moved 5 times in a row",
        "force-push needed:",
        "stale lease",
        "rebase_auto_resolve.md",
        "status: ok|failed|blocked|paused",
    ],
)
def test_finish_worktree_spells_the_wording(wording: str) -> None:
    assert wording in (COMMANDS / "finish_worktree.md").read_text()


def test_finish_worktree_allows_asking_the_user() -> None:
    text = (COMMANDS / "finish_worktree.md").read_text()
    frontmatter = text.split("---")[1]
    allowed = next(
        line for line in frontmatter.splitlines() if line.startswith("allowed-tools:")
    )

    assert "AskUserQuestion" in allowed.split(": ", 1)[1].split(", ")


@pytest.mark.parametrize(
    "wording",
    [
        "Commit and push them to main for me",
        "I'll commit main, then continue",
        "main worktree has uncommitted changes:",
    ],
)
def test_finish_worktree_spells_the_dirty_main_wording(wording: str) -> None:
    assert wording in (COMMANDS / "finish_worktree.md").read_text()


@pytest.mark.parametrize("forbidden", ["stash", "--no-verify"])
def test_finish_worktree_runs_no_git_command_with(forbidden: str) -> None:
    fragments = code_fragments((COMMANDS / "finish_worktree.md").read_text())

    assert [f for f in fragments if "git" in f and forbidden in f] == []


@pytest.mark.parametrize(
    "wording",
    ["general-purpose", "Flaky test guide", "fix flaky test", "not fixed:"],
)
def test_finish_worktree_spells_the_flaky_test_wording(wording: str) -> None:
    assert wording in (COMMANDS / "finish_worktree.md").read_text()


def test_init_template_holds_the_flaky_test_guide_key_under_test_hooks() -> None:
    text = (COMMANDS / "init.md").read_text()
    template = text.split("## Test Hooks\n", 1)[1].split("\n   ## ", 1)[0]

    assert "- Flaky test guide:" in template


def test_configured_flaky_test_guide_exists() -> None:
    config = (ROOT / ".claude/sdd/config.md").read_text()
    match = re.search(r"^- Flaky test guide: *(\S+)$", config, re.MULTILINE)

    assert match is not None
    assert (ROOT / match.group(1)).is_file()
