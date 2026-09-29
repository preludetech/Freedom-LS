"""Tests for the fls-dev plugin's dev-database maintenance scripts.

This test assumes `claude_plugins/` sits at the project root. No database is needed:
`psql` is replaced with a stub executable that logs its own invocation and, when asked,
prints a canned result set, so the real dev Postgres server is never touched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.stub_tools import StubTools, run_script, write_stub

REPO_ROOT = Path(__file__).resolve().parents[1]
DELETE_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "dev_db_delete.sh"
)

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


@pytest.fixture
def repo_on_branch(tmp_path: Path) -> Path:
    env = {**os.environ, **GIT_ENV_OVERRIDES, "HOME": str(tmp_path)}
    subprocess.run(  # noqa: S603
        ["git", "init", "-q", "-b", "feature/x", str(tmp_path)],  # noqa: S607
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return tmp_path


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(
        bin_dir / "psql",
        exit_var="STUB_PSQL_EXIT_CODE",
        output_var="STUB_PSQL_OUTPUT",
        capture_stdin=True,
    )
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


@pytest.mark.parametrize(
    "worker_db", ["test_db_feature_x_gw0", "test_db_feature_x_gw1"]
)
def test_worker_test_databases_are_dropped_with_force(
    stub_tools: StubTools, repo_on_branch: Path, worker_db: str
) -> None:
    # Arrange
    env = stub_tools.env(
        STUB_PSQL_OUTPUT="test_db_feature_x_gw0\ntest_db_feature_x_gw1",
        **GIT_ENV_OVERRIDES,
    )

    # Act
    result = run_script(DELETE_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    assert (
        f"DROP DATABASE IF EXISTS {worker_db} WITH (FORCE);"
        in stub_tools.log_file.read_text()
    )


@pytest.mark.parametrize("db_name", ["db_feature_x", "test_db_feature_x"])
def test_branch_databases_are_dropped_with_force(
    stub_tools: StubTools, repo_on_branch: Path, db_name: str
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(DELETE_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    assert (
        f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE);"
        in stub_tools.log_file.read_text()
    )


def test_failing_psql_stops_the_script_before_any_drop_runs(
    stub_tools: StubTools, repo_on_branch: Path
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PSQL_EXIT_CODE=1, **GIT_ENV_OVERRIDES)

    # Act
    result = run_script(DELETE_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 1
    assert "DROP DATABASE" not in stub_tools.log_file.read_text()
