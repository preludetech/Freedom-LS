"""The sdd command files request the whole suite once, after the last batch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.plugin_markdown import code_fragments

pytestmark = pytest.mark.dev_tooling

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "claude_plugins/sdd/commands"
RESOURCES = ROOT / "claude_plugins/sdd/resources"
TEST_TIERS = ROOT / "claude_plugins/django-stack/resources/test_tiers.md"
TEST_RUNNER = ROOT / "claude_plugins/django-stack/resources/test_runner.md"
RUN_TESTS = COMMANDS / "protected/run_tests.md"
REQUEST_EVERYTHING = re.compile(r"request `everything`")
REQUEST_BEFORE_LANDING = re.compile(r"request `before landing`")


@pytest.mark.parametrize("name", ["do_qa.md", "qa_fix.md"])
def test_qa_commands_never_request_the_whole_suite(name: str) -> None:
    lines = (COMMANDS / name).read_text().splitlines()

    assert [line for line in lines if REQUEST_EVERYTHING.search(line)] == []


@pytest.mark.parametrize(
    "path",
    [
        COMMANDS / "do_qa.md",
        COMMANDS / "qa_fix.md",
        RESOURCES / "do_qa_fix_loop.md",
    ],
    ids=lambda path: path.name,
)
def test_qa_files_never_request_the_landing_run(path: Path) -> None:
    lines = path.read_text().splitlines()

    assert [line for line in lines if REQUEST_BEFORE_LANDING.search(line)] == []


def test_implement_plan_requests_the_whole_suite_once() -> None:
    text = (COMMANDS / "implement_plan.md").read_text()

    assert len(REQUEST_EVERYTHING.findall(text)) == 1


def test_plan_from_spec_does_not_promise_the_full_suite() -> None:
    assert "full test suite passing" not in (COMMANDS / "plan_from_spec.md").read_text()


def test_finish_worktree_never_requests_the_whole_suite() -> None:
    text = (COMMANDS / "finish_worktree.md").read_text()

    assert REQUEST_EVERYTHING.findall(text) == []


def test_finish_worktree_requests_the_landing_run() -> None:
    text = (COMMANDS / "finish_worktree.md").read_text()

    assert REQUEST_BEFORE_LANDING.search(text) is not None


def test_finish_worktree_step_one_is_the_landing_run() -> None:
    lines = (COMMANDS / "finish_worktree.md").read_text().splitlines()

    assert "# Step 1: Landing run" in lines


def test_implement_plan_is_the_only_command_that_requests_the_whole_suite() -> None:
    requesting = {
        str(path.relative_to(COMMANDS))
        for path in COMMANDS.rglob("*.md")
        if path.name != "README.md"
        and path != RUN_TESTS
        and REQUEST_EVERYTHING.search(path.read_text())
    }

    assert requesting == {"implement_plan.md"}


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


def test_run_tests_blocks_when_the_project_names_no_test_runner() -> None:
    assert (
        "status: blocked · reason: no Test runner hook in .claude/sdd/config.md"
        in RUN_TESTS.read_text()
    )


def test_run_tests_spells_out_no_command() -> None:
    fragments = code_fragments(RUN_TESTS.read_text())

    assert [f for f in fragments if re.match(r"\S+\.(sh|py)\b|\w+ run\b", f)] == []


def test_configured_test_runner_exists() -> None:
    config = (ROOT / ".claude/sdd/config.md").read_text()
    match = re.search(r"^- Test runner: *(\S+)$", config, re.MULTILINE)

    assert match is not None
    assert (ROOT / match.group(1)).is_file()


@pytest.mark.parametrize(
    "request_name", ["change", "everything", "before landing", "one test", "failed"]
)
def test_test_runner_handles_every_request_run_tests_lists(request_name: str) -> None:
    row = f"| `{request_name}` |"

    assert row in RUN_TESTS.read_text()
    assert row in TEST_RUNNER.read_text()


def test_test_runner_calls_the_record_script_through_its_wrapper() -> None:
    fragments = code_fragments(TEST_RUNNER.read_text())

    assert [
        f
        for f in fragments
        if "full_run_record" in f and ".claude/ds/scripts/full_run_record.sh" not in f
    ] == []
    assert any(
        f.startswith(".claude/ds/scripts/full_run_record.sh write") for f in fragments
    )


def test_tier_definition_tells_a_checkpoint_to_select_wide() -> None:
    text = TEST_TIERS.read_text()
    targeted = text.split("- **targeted.**", 1)[1].split("- **full.**", 1)[0]

    assert ".claude/ds/scripts/select_tests.sh --wide <diff arguments>" in targeted
    assert "checkpoint" in targeted
