"""Tests for the rebuild script the fls-dev plugin runs after every rebase.

This test assumes `claude_plugins/` and `.claude/fls-dev/scripts/` sit at the project
root, so it exercises both the plugin's own
`claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` and the generated wrapper at
`.claude/fls-dev/scripts/rebuild_after_rebase.sh`. No database is needed: `uv` and `npm`
are replaced with stub executables that only log their own invocation, so the real
`uv sync` / `npm i` / `npm run tailwind_build` never runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)
WRAPPER_SCRIPT = (
    REPO_ROOT / ".claude" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "uv", exit_var="STUB_UV_EXIT_CODE")
    write_stub(bin_dir / "npm", exit_var="STUB_NPM_EXIT_CODE")
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def test_plugin_script_runs_sync_install_and_tailwind_build_in_order(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env()

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines() == ["uv sync", "npm i", "npm run tailwind_build"]


def test_failing_npm_i_stops_the_script_before_tailwind_build(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_NPM_EXIT_CODE=7)

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 7
    assert stub_tools.log_lines() == ["uv sync", "npm i"]


def test_wrapper_script_produces_the_same_log(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env()

    # Act
    result = run_script(WRAPPER_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines() == ["uv sync", "npm i", "npm run tailwind_build"]
