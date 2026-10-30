"""The update_concrete_projects command, its config template and the settings it relies on."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.plugin_markdown import code_fragments

REPO_ROOT = Path(__file__).resolve().parents[1]
FLS_DEV = REPO_ROOT / "claude_plugins/fls-dev"
COMMAND = FLS_DEV / "commands/update_concrete_projects.md"
CONFIG_TEMPLATE = FLS_DEV / "templates/config.local.md"
SETTINGS = REPO_ROOT / ".claude/settings.json"
COMMAND_FORM_SOURCES = [
    COMMAND,
    FLS_DEV / "resources/concrete_spec_integration.md",
    FLS_DEV / "commands/do_qa.md",
]


def allow_pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """An inner `*` stands for one placeholder word, a trailing `*` for the rest of the line."""
    trailing = pattern.endswith("*")
    body = pattern.removesuffix("*")
    regex = r"\S+".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + (".*" if trailing else ""))


def first_lines_of_command_forms() -> list[str]:
    return [
        fragment.splitlines()[0]
        for path in COMMAND_FORM_SOURCES
        for fragment in code_fragments(path.read_text())
        if fragment.strip()
    ]


def test_config_local_template_has_an_empty_concrete_projects_section() -> None:
    lines = CONFIG_TEMPLATE.read_text().splitlines()

    assert "## Concrete Projects" in lines
    assert not [line for line in lines if line.startswith("- /")]


@pytest.mark.parametrize(
    "entry",
    [
        "Bash(git -C * status*)",
        "Bash(git -C * rev-parse *)",
        "Bash(git -C * log*)",
        "Bash(git -C * fetch origin main)",
        "Bash(git -C * submodule status*)",
        "Bash(git -C * symbolic-ref *)",
        "Bash(git -C * remote get-url *)",
        "Bash(git -C * add *)",
        "Bash(uv run --directory * pytest*)",
        "Bash(uv run --directory * python manage.py migrate --check*)",
    ],
)
def test_every_new_allow_verb_matches_a_spelled_command_form(entry: str) -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    pattern = allow_pattern_to_regex(entry.removeprefix("Bash(").removesuffix(")"))

    assert entry in allow
    assert any(pattern.fullmatch(line) for line in first_lines_of_command_forms())


@pytest.mark.parametrize(
    "spelled",
    [
        "--show-toplevel",
        "remote get-url origin",
        "merge-base --is-ancestor",
        "additionalDirectories",
        "migrate --check",
        "--diff-filter=A",
        "--grep='^Update FLS: '",
        "needs: Concrete Projects in .claude/fls-dev/config.local.md",
    ],
)
def test_command_spells_every_preflight_check_and_the_pending_spec_log(
    spelled: str,
) -> None:
    text = COMMAND.read_text()

    assert spelled in text
