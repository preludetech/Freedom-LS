"""The test helper takes and returns the failed set; the commands that fix a failed run re-run only that set.

`run_tests.md` passes a `failed` request to the project's test runner and returns the failed set
of a failed run. The runner maps that request onto the tier definition's failed-only re-run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_rebase_prompts import rebase_command_path

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD = REPO_ROOT / "claude_plugins/sdd"
RUN_TESTS = SDD / "commands/protected/run_tests.md"
TEST_RUNNER = REPO_ROOT / "claude_plugins/django-stack/resources/test_runner.md"
RUN_FAILS_HEADING = "When a run fails"


def test_test_runner_maps_the_failed_request_onto_the_failed_only_rerun() -> None:
    assert "Failed-only re-run" in TEST_RUNNER.read_text()


def test_run_tests_names_the_failed_input() -> None:
    assert "`<failed>`" in RUN_TESTS.read_text()


def test_run_tests_names_the_failed_return_field() -> None:
    assert "failed: <" in RUN_TESTS.read_text()


IMPLEMENT_PLAN = SDD / "commands/implement_plan.md"


def test_implement_plan_makes_the_failed_request() -> None:
    assert "request `failed`" in IMPLEMENT_PLAN.read_text()


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


def test_rebase_command_pointer_names_a_heading_in_the_tier_definition() -> None:
    assert FAILS_HEADING in rebase_command_path().read_text()
    assert f"## {FAILS_HEADING}" in TEST_TIERS.read_text()


@pytest.mark.parametrize(
    "path",
    [IMPLEMENT_PLAN, SDD / "agents/qa-bugfixer.md", SDD / "commands/hotfix.md"],
    ids=lambda path: path.name,
)
def test_caller_pointer_names_a_heading_in_run_tests(path: Path) -> None:
    assert RUN_FAILS_HEADING in path.read_text()
    assert f"## {RUN_FAILS_HEADING}" in RUN_TESTS.read_text()
