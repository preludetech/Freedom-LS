"""Tests for the generated `select_tests.sh` wrapper.

`uv` is replaced with a stub executable that only logs its own invocation, so the
real selection script never runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    REPO_ROOT
    / "claude_plugins"
    / "django-stack"
    / "templates"
    / "wrapper_scripts"
    / "select_tests.sh"
)
WRAPPER = REPO_ROOT / ".claude" / "ds" / "scripts" / "select_tests.sh"
PLUGIN_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "select_tests.py"
)


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "uv", exit_var="STUB_UV_EXIT_CODE")
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def test_wrapper_runs_the_plugin_script_with_its_arguments_through_uv(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    environment = stub_tools.env()

    # Act
    result = run_script(WRAPPER, tmp_path, environment, args=["a.py", "b.py"])

    # Assert
    (logged,) = stub_tools.log_lines()
    command, subcommand, interpreter, script, *arguments = logged.split()
    assert result.returncode == 0
    assert [command, subcommand, interpreter] == ["uv", "run", "python"]
    assert os.path.normpath(script) == str(PLUGIN_SCRIPT)
    assert arguments == ["a.py", "b.py"]


def test_wrapper_exits_with_the_exit_code_of_uv(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    environment = stub_tools.env(STUB_UV_EXIT_CODE=2)

    # Act
    result = run_script(WRAPPER, tmp_path, environment)

    # Assert
    assert result.returncode == 2


def test_template_differs_from_the_generated_wrapper_only_on_the_plugins_root_line() -> (
    None
):
    # Arrange
    template_lines = TEMPLATE.read_text().splitlines()
    wrapper_lines = WRAPPER.read_text().splitlines()

    # Act
    differing = [
        (t, w) for t, w in zip(template_lines, wrapper_lines, strict=True) if t != w
    ]

    # Assert
    assert differing == [('PLUGINS_ROOT="__PLUGINS_ROOT__"', 'PLUGINS_ROOT="."')]
