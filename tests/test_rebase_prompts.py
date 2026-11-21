"""The Rebase command and the helper that calls it spell the rebase's scope, auto-resolve list and push refusals."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.plugin_markdown import code_fragments

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD = REPO_ROOT / "claude_plugins/sdd"
PRE_STEP_REBASE = SDD / "commands/protected/pre_step_rebase.md"
AUTO_RESOLVE = SDD / "resources/rebase_auto_resolve.md"


def rebase_command_path() -> Path:
    config = (REPO_ROOT / ".claude/sdd/config.md").read_text()
    match = re.search(r"^- Rebase command: (\S+)$", config, re.MULTILINE)
    assert match is not None
    return REPO_ROOT / match.group(1)


def test_pre_commit_runs_on_the_branch_changes_only() -> None:
    fragments = code_fragments(rebase_command_path().read_text())

    assert "uv run pre-commit run --from-ref origin/main --to-ref HEAD" in fragments
    assert not [f for f in fragments if "--all-files" in f]


def test_rebase_targeted_run_passes_mains_changes_as_the_upstream_range() -> None:
    fragments = code_fragments(rebase_command_path().read_text())

    assert [f for f in fragments if "--upstream-range $OLD_BASE..origin/main" in f]


def test_rebase_targeted_run_does_not_pass_mains_changes_as_a_plain_range() -> None:
    fragments = code_fragments(rebase_command_path().read_text())

    assert not [f for f in fragments if "--range $OLD_BASE..origin/main" in f]


@pytest.mark.parametrize("reason", ["push rejected: stale lease", "force-push needed:"])
def test_rebase_command_spells_the_push_refusal_reason(reason: str) -> None:
    assert reason in rebase_command_path().read_text()


def test_pre_step_rebase_names_the_auto_resolve_list() -> None:
    assert "rebase_auto_resolve.md" in PRE_STEP_REBASE.read_text()


@pytest.mark.parametrize(
    ("prefix", "side"),
    [
        ("`spec_dd/1. next/roadmap.md`", "roadmap.py"),
        ("`<own-spec-dir>/`", "theirs"),
        ("`spec_dd/`", "ours"),
    ],
)
def test_auto_resolve_list_holds_each_entry(prefix: str, side: str) -> None:
    text = AUTO_RESOLVE.read_text()

    assert prefix in text
    assert side in text


UPSTREAM_REVIEW = SDD / "resources/upstream_change_review.md"


def test_pre_step_rebase_names_the_upstream_change_review() -> None:
    assert "upstream_change_review.md" in PRE_STEP_REBASE.read_text()


@pytest.mark.parametrize(
    "text", ["upstream_change_scan.sh", "direction:", "sdd:sdd-worker"]
)
def test_upstream_change_text_lives_only_in_the_review_resource(text: str) -> None:
    assert text not in PRE_STEP_REBASE.read_text()
    assert text in UPSTREAM_REVIEW.read_text()


def test_auto_resolve_list_prefixes_its_script_path_with_the_plugins_root() -> None:
    assert "`<PLUGINS_ROOT>/`" in AUTO_RESOLVE.read_text()
