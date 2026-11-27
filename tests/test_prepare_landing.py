"""Tests for the wrapper that rebuilds, then checks the installed panel framework pin.

The wrapper runs inside a throwaway project tree. The plugin's rebuild script and the
venv's interpreter are stub executables that log their arguments, so no install or git
command runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    REPO_ROOT
    / "claude_plugins"
    / "fls-dev"
    / "templates"
    / "wrapper_scripts"
    / "prepare_landing.sh"
)
WRAPPER = REPO_ROOT / ".claude" / "fls-dev" / "scripts" / "prepare_landing.sh"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    wrapper = root / ".claude" / "fls-dev" / "scripts" / "prepare_landing.sh"
    wrapper.parent.mkdir(parents=True)
    shutil.copy(WRAPPER, wrapper)
    scripts = root / "claude_plugins" / "fls-dev" / "scripts"
    scripts.mkdir(parents=True)
    write_stub(scripts / "rebuild_after_rebase.sh", exit_var="STUB_REBUILD_EXIT_CODE")
    (scripts / "check_panel_framework_pin.py").write_text("")
    (root / "uv.lock").write_text("")
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    write_stub(venv_bin / "python", exit_var="STUB_CHECK_EXIT_CODE")
    return root


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "uv", exit_var="STUB_UV_EXIT_CODE")
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def _wrapper(project: Path) -> Path:
    return project / ".claude" / "fls-dev" / "scripts" / "prepare_landing.sh"


def test_rebuild_runs_first_with_the_wrappers_arguments(
    project: Path, stub_tools: StubTools
) -> None:
    # Act
    result = run_script(
        _wrapper(project), project, stub_tools.env(), args=["--one", "two"]
    )

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines()[0] == "rebuild_after_rebase.sh --one two"


def test_venv_python_runs_the_pin_check_against_the_project_lock(
    project: Path, stub_tools: StubTools
) -> None:
    # Arrange
    check_script = (
        project
        / "claude_plugins"
        / "fls-dev"
        / "scripts"
        / "check_panel_framework_pin.py"
    )

    # Act
    run_script(_wrapper(project), project, stub_tools.env())

    # Assert
    interpreter, _, arguments = stub_tools.log_lines()[1].partition(" ")
    logged_script, _, logged_lock = arguments.partition(" --lock ")
    assert interpreter == "python"
    assert Path(logged_script).resolve() == check_script.resolve()
    assert Path(logged_lock).resolve() == (project / "uv.lock").resolve()


def test_failing_rebuild_stops_before_the_check(
    project: Path, stub_tools: StubTools
) -> None:
    # Act
    result = run_script(
        _wrapper(project), project, stub_tools.env(STUB_REBUILD_EXIT_CODE=3)
    )

    # Assert
    assert result.returncode == 3
    assert stub_tools.log_lines() == ["rebuild_after_rebase.sh "]


def test_failing_check_sets_the_wrappers_exit_code(
    project: Path, stub_tools: StubTools
) -> None:
    # Act
    result = run_script(
        _wrapper(project), project, stub_tools.env(STUB_CHECK_EXIT_CODE=7)
    )

    # Assert
    assert result.returncode == 7


def test_log_holds_no_uv_run(project: Path, stub_tools: StubTools) -> None:
    # Act
    run_script(_wrapper(project), project, stub_tools.env())

    # Assert
    assert not [line for line in stub_tools.log_lines() if line.startswith("uv")]


def test_template_and_wrapper_differ_only_in_plugins_root() -> None:
    # Arrange
    template = TEMPLATE.read_text().replace(
        'PLUGINS_ROOT="__PLUGINS_ROOT__"', 'PLUGINS_ROOT="."'
    )

    # Assert
    assert template == WRAPPER.read_text()
