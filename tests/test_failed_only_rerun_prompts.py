"""The test-tier helper takes and returns the failed set; the commands that fix a failed run re-run only that set.

`run_test_tier.md` runs the tier definition's failed-only re-run when it is given a failed set,
and returns the failed set of a failed run. Callers that name neither re-run keep the whole-tier
re-run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_rebase_prompts import rebase_command_path

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD = REPO_ROOT / "claude_plugins/sdd"
RUN_TEST_TIER = SDD / "commands/protected/run_test_tier.md"


def test_run_test_tier_names_the_failed_only_rerun() -> None:
    assert "failed-only re-run" in RUN_TEST_TIER.read_text()


def test_run_test_tier_names_the_failed_input() -> None:
    assert "`<failed>`" in RUN_TEST_TIER.read_text()


def test_run_test_tier_names_the_failed_return_field() -> None:
    assert "failed: <" in RUN_TEST_TIER.read_text()


IMPLEMENT_PLAN = SDD / "commands/implement_plan.md"


def test_implement_plan_names_the_failed_only_rerun() -> None:
    assert "failed-only re-run" in IMPLEMENT_PLAN.read_text()


def test_implement_plan_passes_failed_to_the_helper() -> None:
    assert "`<failed>`" in IMPLEMENT_PLAN.read_text()


TEST_TIERS = REPO_ROOT / "claude_plugins/django-stack/resources/test_tiers.md"
FAILS_HEADING = "When a targeted run or full run fails"


def test_rebase_command_names_the_failed_only_rerun() -> None:
    assert "failed-only re-run" in rebase_command_path().read_text()


def test_rebase_command_names_the_whole_tier_rerun() -> None:
    assert "whole-tier re-run" in rebase_command_path().read_text()


@pytest.mark.parametrize(
    "path",
    [SDD / "agents/qa-bugfixer.md", SDD / "commands/finish_worktree.md"],
    ids=lambda path: path.name,
)
def test_whole_tier_callers_do_not_name_the_failed_only_rerun(path: Path) -> None:
    assert "failed-only re-run" not in path.read_text()


@pytest.mark.parametrize(
    "path",
    [IMPLEMENT_PLAN, rebase_command_path(), SDD / "agents/qa-bugfixer.md"],
    ids=lambda path: path.name,
)
def test_caller_pointer_names_a_heading_in_the_tier_definition(path: Path) -> None:
    assert FAILS_HEADING in path.read_text()
    assert f"## {FAILS_HEADING}" in TEST_TIERS.read_text()
