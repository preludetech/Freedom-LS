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
DO_QA = FLS_DEV / "commands/do_qa.md"
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
        "Bash(git -C * diff*)",
        "Bash(git switch *)",
        "Bash(git -C * fetch origin main)",
        "Bash(git -C * submodule status*)",
        "Bash(git -C * symbolic-ref *)",
        "Bash(git -C * remote get-url *)",
        "Bash(git -C * add *)",
        "Bash(uv run --directory * pytest*)",
        "Bash(uv run --directory * python manage.py migrate --check*)",
        "Bash(git -C * submodule update*)",
        "Bash(uv run --directory * python manage.py check*)",
        "Bash(uv run --directory * python manage.py makemigrations --check*)",
        "Bash(uv run --directory * git commit *)",
        "Bash(uv sync --directory *)",
        "Bash(npm --prefix * run tailwind_build*)",
        "Bash(uv run --directory * python manage.py runserver*)",
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


@pytest.mark.parametrize(
    "entry",
    [
        "Bash(git -C * push --force*)",
        "Bash(git -C * commit --no-verify*)",
        "Bash(uv run --directory * git commit --no-verify*)",
    ],
)
def test_deny_list_blocks_force_push_and_no_verify_in_projects(entry: str) -> None:
    deny = json.loads(SETTINGS.read_text())["permissions"]["deny"]

    assert entry in deny


@pytest.mark.parametrize(
    "spelled",
    [
        "-rf",
        "Update FLS:",
        "integrated",
        "blocked-on-fix",
        "blocked-on-spec",
        "skipped",
        "delete_sdd_work_files.sh",
        "update_concrete_workarounds_",
        "update_concrete_specdiff_",
    ],
)
def test_loop_names_the_gate_flags_and_every_cell_result(spelled: str) -> None:
    text = COMMAND.read_text()

    assert spelled in text


@pytest.mark.parametrize(
    "spelled",
    [
        "land_on_main.sh land",
        "rebase origin/main",
        "git switch main",
        "git branch -d fix/",
        "idea_standard.md",
        "blocked-on-spec",
        "parked on",
        "Update FLS: <spec>, <spec>",
    ],
)
def test_failure_handling_names_every_path(spelled: str) -> None:
    text = COMMAND.read_text()

    assert spelled in text


def project_root_section() -> str:
    text = DO_QA.read_text()
    start = text.index("## Project-root mode")
    ends = [m.start() for m in re.finditer(r"^(## |---)", text[start + 1 :], re.M)]
    return text[start : start + 1 + ends[0]] if ends else text[start:]


@pytest.mark.parametrize(
    "heading",
    ["Inputs from the caller: `project-root:", "## Project-root mode"],
)
def test_do_qa_declares_the_project_root_inputs_and_section(heading: str) -> None:
    assert heading in DO_QA.read_text()


def test_project_root_bullets_never_change_directory() -> None:
    fragments = code_fragments(project_root_section())

    assert [f for f in fragments if re.search(r"\bcd\s", f)] == []


def test_project_root_manage_and_pytest_forms_carry_directory() -> None:
    bullets = re.findall(r"^- .*(?:\n  .*)*", project_root_section(), re.M)

    assert [
        b
        for b in bullets
        if re.search(r"manage\.py|pytest", b) and "--directory" not in b
    ] == []
