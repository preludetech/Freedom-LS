"""Tests for `claude_plugins/django-stack/scripts/run_tests.py`.

The runner is started as a subprocess with `cwd=tmp_path`. `pytest` is replaced with a stub
executable on a temporary `PATH` that logs its argv, so no real test run starts. Free memory
comes from a fake meminfo file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.stub_tools import StubTools, write_stub

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "run_tests.py"


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_stub(bin_dir / "pytest", exit_var="STUB_PYTEST_EXIT_CODE")
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def write_meminfo(tmp_path: Path, available_mb: int) -> Path:
    path = tmp_path / "meminfo"
    path.write_text(
        f"MemTotal:       99999999 kB\nMemAvailable:   {available_mb * 1024} kB\n",
        encoding="utf-8",
    )
    return path


def run_runner(
    stub_tools: StubTools,
    tmp_path: Path,
    args: list[str],
    **variables: str | int,
) -> subprocess.CompletedProcess[str]:
    """Run the runner with a clean `DS_TEST_*` environment plus `variables`."""
    settings = {"DS_TEST_TIME_SCALE": 0, **variables}
    environment = stub_tools.env(TMPDIR=str(tmp_path), **settings)
    for name in [n for n in environment if n.startswith("DS_TEST_")]:
        if name not in settings:
            del environment[name]
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def logged_tokens(stub_tools: StubTools) -> list[str]:
    (logged,) = stub_tools.log_lines()
    return logged.split()


@pytest.mark.parametrize(
    ("available_mb", "expected_workers"),
    [
        (4096, "2"),
        (3071, "1"),
        (100, "1"),
    ],
)
def test_worker_count_follows_free_memory(
    stub_tools: StubTools,
    tmp_path: Path,
    available_mb: int,
    expected_workers: str,
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, available_mb)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert result.returncode == 0
    assert logged_tokens(stub_tools)[-2:] == ["-n", expected_workers]


def test_worker_count_is_capped_by_the_cpu_count_when_memory_is_plentiful(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 10_000_000)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert logged_tokens(stub_tools)[-2:] == ["-n", str(os.cpu_count() or 1)]


def test_ram_line_reports_available_memory_and_worker_count(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert "ram: MemAvailable 4096 MB, xdist workers -n 2" in result.stdout.splitlines()


@pytest.mark.parametrize(
    "argv",
    [["pytest", "tests/a.py"], ["pytest", "-x", "--no-cov"]],
)
def test_command_without_a_worker_option_gets_none(
    stub_tools: StubTools, tmp_path: Path, argv: list[str]
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(stub_tools, tmp_path, argv, DS_TEST_MEMINFO_PATH=str(meminfo))

    # Assert
    assert logged_tokens(stub_tools) == argv


def test_command_with_an_attached_worker_option_gets_the_runner_count_appended(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-nauto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert logged_tokens(stub_tools) == ["pytest", "-nauto", "-n", "2"]


def test_runner_exits_with_the_exit_code_of_the_command(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_EXIT_CODE=1,
    )

    # Assert
    assert result.returncode == 1


@pytest.mark.parametrize("guard", ["on", "off"])
@pytest.mark.parametrize(
    "argv",
    [
        ["rm", "-rf", "x"],
        ["bash", "-c", "pytest"],
        ["/tmp/x/pytest"],  # noqa: S108
        ["uv", "run", "--with", "p", "pytest"],
        [],
    ],
)
def test_command_that_is_not_pytest_exits_2_and_runs_nothing(
    stub_tools: StubTools, tmp_path: Path, argv: list[str], guard: str
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        argv,
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MEMORY_GUARD=guard,
    )

    # Assert
    assert result.returncode == 2
    assert stub_tools.log_lines() == []
    assert "uv run --directory <dir> pytest" in result.stderr


def test_guard_off_passes_the_command_through_unchanged_without_a_ram_line(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto", "-k", "ab"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MEMORY_GUARD="off",
    )

    # Assert
    assert logged_tokens(stub_tools) == ["pytest", "-n", "auto", "-k", "ab"]
    assert "ram:" not in result.stdout


def test_missing_meminfo_runs_the_command_as_given_and_says_so(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    missing = tmp_path / "no_such_meminfo"

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(missing),
    )

    # Assert
    assert logged_tokens(stub_tools) == ["pytest", "-n", "auto"]
    assert (
        "ram: no /proc/meminfo on this platform; running the command as given"
        in result.stdout.splitlines()
    )
