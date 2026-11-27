"""Tests for the script that links a panel framework package worktree into the environment.

`uv` and `git` are stub executables on `PATH` that log their invocation, so no real install
runs and the package repo is never touched. Each case sources the script in a subshell that
then echoes `UV_NO_SYNC`, which shows whether the export reached the caller.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.stub_tools import StubTools, write_stub

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "link_panel_framework.sh"
)
BRANCH = "some_branch"


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "uv", exit_var="STUB_UV_EXIT_CODE")
    write_stub(
        bin_dir / "git", exit_var="STUB_GIT_EXIT_CODE", output_var="STUB_GIT_OUTPUT"
    )
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


@pytest.fixture
def package_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "package_repo"
    repo.mkdir()
    return repo


def source_link_script(
    child_env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            "/bin/sh",
            "-eu",
            "-c",
            '. "$1"; echo "after:${UV_NO_SYNC:-unset}"',
            "sh",
            str(LINK_SCRIPT),
        ],
        cwd=cwd,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )


def make_package_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text("[project]\nname = 'django-panel-framework'\n")
    return path


@pytest.mark.parametrize("create_directory", [False, True])
def test_missing_worktree_or_pyproject_is_skipped_with_a_message(
    stub_tools: StubTools, package_repo: Path, tmp_path: Path, create_directory: bool
) -> None:
    # Arrange
    package_dir = package_repo / BRANCH
    if create_directory:
        package_dir.mkdir()
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=package_repo, STUB_GIT_OUTPUT=BRANCH
    )

    # Act
    result = source_link_script(child_env, tmp_path)

    # Assert
    assert result.returncode == 0
    assert str(package_dir) in result.stdout
    assert "after:unset" in result.stdout
    assert not any(line.startswith("uv pip") for line in stub_tools.log_lines())


def test_package_worktree_named_after_the_branch_is_installed_editable(
    stub_tools: StubTools, package_repo: Path, tmp_path: Path
) -> None:
    # Arrange
    package_dir = make_package_dir(package_repo / BRANCH)
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=package_repo, STUB_GIT_OUTPUT=BRANCH
    )

    # Act
    result = source_link_script(child_env, tmp_path)

    # Assert
    assert result.returncode == 0
    assert f"uv pip install --no-deps -e {package_dir}" in stub_tools.log_lines()
    assert "after:1" in result.stdout


def test_panel_framework_dir_overrides_the_branch_path(
    stub_tools: StubTools, package_repo: Path, tmp_path: Path
) -> None:
    # Arrange
    other_dir = make_package_dir(tmp_path / "elsewhere")
    child_env = stub_tools.env(
        PANEL_FRAMEWORK_REPO=package_repo,
        PANEL_FRAMEWORK_DIR=other_dir,
        STUB_GIT_OUTPUT=BRANCH,
    )

    # Act
    result = source_link_script(child_env, tmp_path)

    # Assert
    assert result.returncode == 0
    assert f"uv pip install --no-deps -e {other_dir}" in stub_tools.log_lines()
    assert "after:1" in result.stdout
