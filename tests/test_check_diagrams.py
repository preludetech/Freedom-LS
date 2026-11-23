"""Tests for `claude_plugins/sdd/scripts/check_diagrams.py`.

Each fixture diagram under `tests/fixtures/check_diagrams/` is a draw.io export of a few boxes,
so its embedded XML has the shape of a real diagram. The command files are written into
`tmp_path`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests._script_trees import run_script, write_tree

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "sdd" / "scripts" / "check_diagrams.py"
FIXTURES = Path(__file__).parent / "fixtures" / "check_diagrams"
SDD_DIR = REPO_ROOT / "claude_plugins" / "sdd"
DS_DIR = REPO_ROOT / "claude_plugins" / "django-stack"
GUIDE = SDD_DIR / "commands" / "README.md"
DIAGRAMS_DIR = SDD_DIR / "docs" / "diagrams"
EMBED = re.compile(r"\]\(\.\./docs/diagrams/([\w.-]+\.drawio\.svg)\)")

# Collected at import time so each target and each diagram is its own test id.
GUIDE_EMBEDS = EMBED.findall(GUIDE.read_text(encoding="utf-8"))
DIAGRAM_FILES = sorted(path.name for path in DIAGRAMS_DIR.glob("*.drawio.svg"))

COMMAND = """\
# Command

## Step 0: Pre-step rebase

Text.

## Step 1: Resolve the spec directory

Text.
"""


def check(tmp_path: Path, diagram: str, command: str) -> tuple[int, str]:
    write_tree(tmp_path, {"command.md": command})
    result = run_script(
        SCRIPT,
        tmp_path,
        "--diagram",
        str(FIXTURES / f"{diagram}.drawio.svg"),
        "--source",
        str(tmp_path / "command.md"),
    )
    return result.returncode, result.stdout


def test_diagram_covering_every_heading_passes(tmp_path: Path) -> None:
    code, output = check(tmp_path, "covered", COMMAND)

    assert (code, output) == (0, "")


def test_renamed_heading_fails_and_is_named(tmp_path: Path) -> None:
    command = COMMAND.replace("Resolve the spec directory", "Find the spec directory")

    code, output = check(tmp_path, "covered", command)

    assert code == 1
    assert 'no label for "Step 1: Find the spec directory"' in output


def test_label_for_a_step_no_file_has_fails_and_is_named(tmp_path: Path) -> None:
    code, output = check(tmp_path, "step_nine", COMMAND)

    assert code == 1
    assert 'label "Step 9: Invented step" names a step no file has' in output


@pytest.mark.parametrize(
    ("heading", "diagram"),
    [
        ("## Step 0.5: Pre-step rebase", "label_step_0"),
        ("## Step 1", "label_step_10"),
    ],
)
def test_heading_is_not_matched_by_a_label_with_a_longer_number(
    tmp_path: Path, heading: str, diagram: str
) -> None:
    code, output = check(tmp_path, diagram, heading + "\n")

    assert code == 1
    assert f'no label for "{heading.removeprefix("## ")}"' in output


def test_heading_is_matched_by_its_own_decimal_label(tmp_path: Path) -> None:
    code, output = check(tmp_path, "label_step_0_5", "## Step 0.5: Pre-step rebase\n")

    assert (code, output) == (0, "")


def test_heading_inside_a_fenced_block_needs_no_label(tmp_path: Path) -> None:
    command = COMMAND + "\n```\n# Step 7: Only a template\n```\n"

    code, output = check(tmp_path, "covered", command)

    assert (code, output) == (0, "")


def test_heading_inside_an_indented_fenced_block_needs_no_label(tmp_path: Path) -> None:
    command = COMMAND + "\n- An example:\n\n  ```\n# Step 7: Only a template\n  ```\n"

    code, output = check(tmp_path, "covered", command)

    assert (code, output) == (0, "")


def test_label_with_line_break_and_non_breaking_space_matches(tmp_path: Path) -> None:
    code, output = check(tmp_path, "markup", COMMAND)

    assert (code, output) == (0, "")


def test_label_on_a_shape_with_a_link_matches(tmp_path: Path) -> None:
    code, output = check(tmp_path, "linked", COMMAND)

    assert (code, output) == (0, "")


def test_committed_diagrams_match_their_commands() -> None:
    result = run_script(SCRIPT, REPO_ROOT)

    assert (result.returncode, result.stdout) == (0, "")


def test_rebase_command_diagram_matches_its_command() -> None:
    result = run_script(
        SCRIPT,
        REPO_ROOT,
        "--diagram",
        str(DS_DIR / "docs" / "diagrams" / "rebase_main.drawio.svg"),
        "--source",
        str(DS_DIR / "commands" / "rebase_main.md"),
    )

    assert (result.returncode, result.stdout) == (0, "")


def test_usage_error_exits_64(tmp_path: Path) -> None:
    result = run_script(SCRIPT, tmp_path, "--diagram", "only.drawio.svg")

    assert result.returncode == 64


@pytest.mark.parametrize("target", sorted(set(GUIDE_EMBEDS)))
def test_guide_embed_target_exists(target: str) -> None:
    assert (DIAGRAMS_DIR / target).is_file()


@pytest.mark.parametrize("diagram", DIAGRAM_FILES)
def test_guide_embeds_each_diagram_exactly_once(diagram: str) -> None:
    assert GUIDE_EMBEDS.count(diagram) == 1
