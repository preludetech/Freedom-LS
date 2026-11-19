"""The sdd command files ask for the full tier only at the end of an implementation run."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

COMMANDS = Path(__file__).resolve().parents[1] / "claude_plugins/sdd/commands"
TIER_FULL = re.compile(r"<tier>`?:? *`full`")


@pytest.mark.parametrize("name", ["do_qa.md", "qa_fix.md"])
def test_qa_commands_never_ask_for_the_full_tier(name: str) -> None:
    lines = (COMMANDS / name).read_text().splitlines()

    assert [line for line in lines if TIER_FULL.search(line)] == []


def test_implement_plan_asks_for_the_full_tier_once() -> None:
    text = (COMMANDS / "implement_plan.md").read_text()

    assert len(TIER_FULL.findall(text)) == 1


def test_plan_from_spec_does_not_promise_the_full_suite() -> None:
    assert "full test suite passing" not in (COMMANDS / "plan_from_spec.md").read_text()
