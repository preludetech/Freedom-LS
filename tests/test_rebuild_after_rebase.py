"""Tests for the rebuild script the fls-dev plugin runs after every rebase.

This test assumes `claude_plugins/` and `.claude/fls-dev/scripts/` sit at the project
root, so it exercises both the plugin's own
`claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` and the generated wrapper at
`.claude/fls-dev/scripts/rebuild_after_rebase.sh`. No database is needed: `uv`, `npm`, `git`
and `psql` are replaced with stub executables that only log their own invocation, so the real
`uv sync` / `npm i` / `npm run tailwind_build` / `dev_db_init.sh` never runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)
WRAPPER_SCRIPT = (
    REPO_ROOT / ".claude" / "fls-dev" / "scripts" / "rebuild_after_rebase.sh"
)

SKIPPED_LINK_LOG = [
    "uv sync",
    "git branch --show-current",
    "npm i",
    "npm run tailwind_build",
]


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "uv", exit_var="STUB_UV_EXIT_CODE")
    write_stub(bin_dir / "npm", exit_var="STUB_NPM_EXIT_CODE")
    write_stub(
        bin_dir / "git", exit_var="STUB_GIT_EXIT_CODE", output_var="STUB_GIT_OUTPUT"
    )
    write_stub(
        bin_dir / "psql",
        exit_var="STUB_PSQL_EXIT_CODE",
        output_var="STUB_PSQL_OUTPUT",
        capture_stdin=True,
    )
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


@pytest.fixture
def empty_package_repo(tmp_path: Path) -> Path:
    """A package repo directory with no worktrees, so the link step is skipped."""
    repo = tmp_path / "package_repo"
    repo.mkdir()
    return repo


def test_plugin_script_runs_sync_install_and_tailwind_build_in_order(
    stub_tools: StubTools, tmp_path: Path, empty_package_repo: Path
) -> None:
    # Arrange
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=empty_package_repo, STUB_GIT_OUTPUT="some_branch"
    )

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, child_env)

    # Assert
    log_lines = stub_tools.log_lines()
    assert result.returncode == 0
    assert log_lines[:4] == SKIPPED_LINK_LOG
    assert log_lines[4].startswith("psql ")


def test_failing_npm_i_stops_the_script_before_tailwind_build(
    stub_tools: StubTools, tmp_path: Path, empty_package_repo: Path
) -> None:
    # Arrange
    child_env = stub_tools.env(
        STUB_NPM_EXIT_CODE=7,
        PANEL_FRAMEWORK_REPO=empty_package_repo,
        STUB_GIT_OUTPUT="some_branch",
    )

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, child_env)

    # Assert
    assert result.returncode == 7
    assert stub_tools.log_lines() == ["uv sync", "git branch --show-current", "npm i"]
    assert not any(line.startswith("psql") for line in stub_tools.log_lines())


def test_failing_psql_stops_the_script_with_that_exit_code(
    stub_tools: StubTools, tmp_path: Path, empty_package_repo: Path
) -> None:
    # Arrange
    child_env = stub_tools.env(
        STUB_PSQL_EXIT_CODE=3,
        PANEL_FRAMEWORK_REPO=empty_package_repo,
        STUB_GIT_OUTPUT="some_branch",
    )

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, child_env)

    # Assert
    assert result.returncode == 3
    assert stub_tools.log_lines()[:4] == SKIPPED_LINK_LOG


def test_wrapper_script_produces_the_same_log(
    stub_tools: StubTools, tmp_path: Path, empty_package_repo: Path
) -> None:
    # Arrange
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=empty_package_repo, STUB_GIT_OUTPUT="some_branch"
    )

    # Act
    result = run_script(WRAPPER_SCRIPT, tmp_path, child_env)

    # Assert
    log_lines = stub_tools.log_lines()
    assert result.returncode == 0
    assert log_lines[:4] == SKIPPED_LINK_LOG
    assert log_lines[4].startswith("psql ")


def test_linked_package_worktree_is_installed_between_sync_and_npm(
    stub_tools: StubTools, tmp_path: Path, empty_package_repo: Path
) -> None:
    # Arrange
    package_dir = tmp_path / "package_worktree"
    package_dir.mkdir()
    (package_dir / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=empty_package_repo,
        PANEL_FRAMEWORK_DIR=package_dir,
        STUB_GIT_OUTPUT="some_branch",
    )

    # Act
    result = run_script(PLUGIN_SCRIPT, tmp_path, child_env)

    # Assert
    assert result.returncode == 0
    assert stub_tools.log_lines()[:4] == [
        "uv sync",
        f"uv pip install --no-deps -e {package_dir}",
        "npm i",
        "npm run tailwind_build",
    ]
