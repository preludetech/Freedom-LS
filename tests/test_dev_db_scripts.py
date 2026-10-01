"""Tests for the fls-dev plugin's dev-database maintenance scripts.

This test assumes `claude_plugins/` sits at the project root. No database is needed:
`psql` is replaced with a stub executable that logs its own invocation and, when asked,
prints a canned result set, so the real dev Postgres server is never touched.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from dev_db import server
from tests.stub_tools import StubTools, run_script, write_stub

REPO_ROOT = Path(__file__).resolve().parents[1]
DELETE_SCRIPT = (
    REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "dev_db_delete.sh"
)
INIT_SCRIPT = REPO_ROOT / "claude_plugins" / "fls-dev" / "scripts" / "dev_db_init.sh"

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


def test_summary_line_lists_all_dropped_databases_on_one_line(
    stub_tools: StubTools, repo_on_branch: Path
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
    summary_lines = [
        line for line in result.stdout.splitlines() if line.startswith("Dropped:")
    ]
    assert summary_lines == [
        "Dropped: db_feature_x, test_db_feature_x, "
        "test_db_feature_x_gw0, test_db_feature_x_gw1"
    ]


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


def test_init_creates_fls_dev_role_only_if_missing(
    stub_tools: StubTools, repo_on_branch: Path
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    log = stub_tools.log_file.read_text()
    assert result.returncode == 0
    assert "IF NOT EXISTS" in log
    assert "CREATE ROLE fls_dev LOGIN PASSWORD 'password' CREATEDB" in log
    assert "$$" in log


def test_init_sets_idle_in_transaction_timeout_on_the_role(
    stub_tools: StubTools, repo_on_branch: Path
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    assert (
        "ALTER ROLE fls_dev SET idle_in_transaction_session_timeout = '15min'"
        in stub_tools.log_file.read_text()
    )


@pytest.mark.parametrize("db_name", ["db_feature_x", "test_db_feature_x"])
def test_init_creates_missing_databases_owned_by_fls_dev(
    stub_tools: StubTools, repo_on_branch: Path, db_name: str
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    assert f"CREATE DATABASE {db_name} OWNER fls_dev" in stub_tools.log_file.read_text()


@pytest.mark.parametrize("db_name", ["db_feature_x", "test_db_feature_x"])
def test_init_reassigns_owner_of_existing_databases_to_fls_dev(
    stub_tools: StubTools, repo_on_branch: Path, db_name: str
) -> None:
    # Arrange
    env = stub_tools.env(STUB_PSQL_OUTPUT="1", **GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    log = stub_tools.log_file.read_text()
    assert result.returncode == 0
    assert f"ALTER DATABASE {db_name} OWNER TO fls_dev" in log
    assert "CREATE DATABASE" not in log


def test_init_never_grants_privileges_to_pguser(
    stub_tools: StubTools, repo_on_branch: Path
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    assert "GRANT" not in stub_tools.log_file.read_text()


def test_init_stamps_the_branch_database_with_its_repo_and_worktree(
    stub_tools: StubTools, repo_on_branch: Path
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, repo_on_branch, env)

    # Assert
    assert result.returncode == 0
    match = re.search(
        r"COMMENT ON DATABASE db_feature_x IS '(.*)';",
        stub_tools.log_file.read_text(),
    )
    assert match is not None
    stamp = json.loads(match.group(1))
    assert stamp["repo"] == str(repo_on_branch.resolve() / ".git")
    assert stamp["worktree"] == str(repo_on_branch.resolve())


def test_init_does_not_stamp_the_fallback_database_with_no_branch(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    env = stub_tools.env(**GIT_ENV_OVERRIDES)

    # Act
    result = run_script(INIT_SCRIPT, tmp_path, env)

    # Assert
    assert result.returncode == 0
    assert "COMMENT ON DATABASE" not in stub_tools.log_file.read_text()


def test_log_line_prefix_ends_with_a_space_before_the_log_level() -> None:
    # Arrange
    compose = yaml.safe_load(server.COMPOSE_FILE.read_text())
    command = compose["services"]["postgres"]["command"]

    # Act
    prefix = next(item for item in command if item.startswith("log_line_prefix="))
    value = prefix.removeprefix("log_line_prefix=")

    # Assert
    assert value.endswith(" ")
