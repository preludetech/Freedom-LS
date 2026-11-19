"""Tests for `claude_plugins/sdd/scripts/measure_prompt_size.py`.

The script always measures its own plugin, so each test points `--project-root` at a `tmp_path`
that holds only a `.claude/sdd/config.md`, and reads the table the script prints.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._script_trees import run_script, write_tree

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SDD = REPO_ROOT / "claude_plugins" / "sdd"
SCRIPT = SDD / "scripts" / "measure_prompt_size.py"
COMMANDS = sorted(
    path.name for path in (SDD / "commands").glob("*.md") if path.name != "README.md"
)


def measure(project: Path, config_lines: list[str]) -> str:
    write_tree(
        project,
        {".claude/sdd/config.md": "# Config\n\n## Hooks\n\n" + "\n".join(config_lines)},
    )
    result = run_script(SCRIPT, project, "--project-root", str(project))
    assert result.returncode == 0, result.stderr
    return result.stdout


def row_cells(output: str, file_name: str) -> list[str] | None:
    for line in output.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] == file_name:
            return cells
    return None


def unmeasured(output: str) -> list[str]:
    return output.split("## Unmeasured\n\n", 1)[1].splitlines()


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_file_has_a_row(tmp_path: Path, command: str) -> None:
    output = measure(tmp_path, [])

    assert row_cells(output, f"claude_plugins/sdd/commands/{command}") is not None


def test_commands_readme_has_no_row(tmp_path: Path) -> None:
    output = measure(tmp_path, [])

    assert row_cells(output, "claude_plugins/sdd/commands/README.md") is None


def test_config_value_naming_a_project_file_is_measured(tmp_path: Path) -> None:
    write_tree(tmp_path, {"docs/guide.md": "one two three\nfour five six seven\n"})

    output = measure(tmp_path, ["- Guide: docs/guide.md"])

    # 34 characters at four per token.
    assert row_cells(output, "docs/guide.md") == ["docs/guide.md", "2", "7", "8"]


def test_config_command_value_measures_its_script(tmp_path: Path) -> None:
    write_tree(tmp_path, {"scripts/check.sh": "echo hi\n"})

    output = measure(tmp_path, ["- Capacity: scripts/check.sh --capacity"])

    assert row_cells(output, "scripts/check.sh") is not None


@pytest.mark.parametrize(
    ("line", "listed"),
    [
        ("- Missing: docs/absent.md", "docs/absent.md"),
        ("- Outside: ../x.md", None),
        ("- Skill: ds:app_map", "ds:app_map"),
    ],
)
def test_unmeasurable_config_value_is_listed_as_unmeasured(
    tmp_path: Path, line: str, listed: str | None
) -> None:
    write_tree(tmp_path.parent, {"x.md": "outside the project\n"})
    expected = listed or "../x.md"

    output = measure(tmp_path, [line])

    assert f"- {expected}" in unmeasured(output)


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("- Base URL: http://127.0.0.1:8000", "127.0.0.1"),
        ("- Port: 48213", "48213"),
        ("- Name: plain words", "plain words"),
    ],
)
def test_url_and_plain_word_values_are_ignored(
    tmp_path: Path, line: str, value: str
) -> None:
    output = measure(tmp_path, [line])

    assert value not in output
