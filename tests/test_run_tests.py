"""Tests for `claude_plugins/django-stack/scripts/run_tests.py`.

The runner is started as a subprocess with `cwd=tmp_path`. `pytest` is replaced with a stub
executable on a temporary `PATH` that logs its argv, so no real test run starts. Free memory
comes from a fake meminfo file.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
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
    settings = {
        "DS_TEST_TIME_SCALE": 0,
        "DS_TEST_PSI_PATH": str(tmp_path / "no_such_psi"),
        **variables,
    }
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
    assert (
        "ram: MemAvailable 4096 MB, PSI n/a, xdist workers -n 2"
        in result.stdout.splitlines()
    )


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


def write_pyproject(tmp_path: Path, memory_table: str) -> None:
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.test_tiers.memory]\n{memory_table}\n", encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("table", "variables", "expected_workers", "expected_source"),
    [
        ("max_workers = 3", {}, "3", "max_workers=3 from pyproject"),
        (
            "max_workers = 3",
            {"DS_TEST_MAX_WORKERS": 2},
            "2",
            "max_workers=2 from env",
        ),
        (
            "max_workers = 8\nreserve_mb = 8192",
            {},
            "2",
            "reserve_mb=8192 from pyproject",
        ),
        (
            "max_workers = 8\nreserve_mb = 0",
            {"DS_TEST_RESERVE_MB": 9216},
            "1",
            "reserve_mb=9216 from env",
        ),
    ],
)
def test_env_beats_pyproject_which_beats_the_default(
    stub_tools: StubTools,
    tmp_path: Path,
    table: str,
    variables: dict[str, int],
    expected_workers: str,
    expected_source: str,
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 10_240)
    write_pyproject(tmp_path, table)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        **variables,
    )

    # Assert
    assert logged_tokens(stub_tools)[-2:] == ["-n", expected_workers]
    assert expected_source in result.stdout


def test_ram_line_names_only_settings_that_are_not_the_default(
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
        DS_TEST_MAX_WORKERS=4,
    )

    # Assert
    assert (
        "ram: MemAvailable 4096 MB, PSI n/a, xdist workers -n 2 (max_workers=4 from env)"
        in result.stdout.splitlines()
    )


@pytest.mark.parametrize(
    ("table", "expected_message"),
    [
        (
            'per_worker_mb = "big"',
            "[tool.test_tiers.memory] 'per_worker_mb' must be an integer",
        ),
        (
            "max_workers = true",
            "[tool.test_tiers.memory] 'max_workers' must be an integer",
        ),
        (
            "max_workers = 0",
            "[tool.test_tiers.memory] 'max_workers' must be at least 1",
        ),
        ('psi_some_avg10_limit = "x"', "'psi_some_avg10_limit' must be a number"),
        ("bogus = 1", "[tool.test_tiers.memory] unknown key 'bogus'"),
    ],
)
def test_bad_pyproject_memory_table_exits_2_and_names_the_key(
    stub_tools: StubTools, tmp_path: Path, table: str, expected_message: str
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)
    write_pyproject(tmp_path, table)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert result.returncode == 2
    assert expected_message in result.stderr
    assert stub_tools.log_lines() == []


def test_memory_that_is_not_a_table_exits_2(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        "[tool.test_tiers]\nmemory = 3\n", encoding="utf-8"
    )

    # Act
    result = run_runner(stub_tools, tmp_path, ["pytest"])

    # Assert
    assert result.returncode == 2
    assert "[tool.test_tiers] 'memory' must be a table" in result.stderr


def test_malformed_pyproject_exits_2(stub_tools: StubTools, tmp_path: Path) -> None:
    # Arrange
    (tmp_path / "pyproject.toml").write_text("[tool\n", encoding="utf-8")

    # Act
    result = run_runner(stub_tools, tmp_path, ["pytest"])

    # Assert
    assert result.returncode == 2
    assert stub_tools.log_lines() == []


@pytest.mark.parametrize(
    ("variable", "expected_message"),
    [
        ("DS_TEST_RESERVE_MB", "DS_TEST_RESERVE_MB must be an integer"),
        ("DS_TEST_PSI_LIMIT", "DS_TEST_PSI_LIMIT must be a number"),
    ],
)
def test_non_numeric_env_var_exits_2_and_names_the_variable(
    stub_tools: StubTools, tmp_path: Path, variable: str, expected_message: str
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        **{variable: "lots"},
    )

    # Assert
    assert result.returncode == 2
    assert expected_message in result.stderr


@pytest.mark.parametrize(
    ("available_mb", "expected"),
    [
        (10_240, "8\n"),
        (2_100, "1\n"),
        (500, "1\n"),
    ],
)
def test_capacity_is_the_units_that_fit_after_the_reserve(
    stub_tools: StubTools, tmp_path: Path, available_mb: int, expected: str
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, available_mb)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["--capacity", "1000"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
    )

    # Assert
    assert result.returncode == 0
    assert result.stdout == expected


def test_capacity_without_meminfo_prints_999(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    missing = tmp_path / "no_such_meminfo"

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["--capacity", "1000"],
        DS_TEST_MEMINFO_PATH=str(missing),
    )

    # Assert
    assert result.stdout == "999\n"


@pytest.mark.parametrize("unit", ["0", "-5", "abc", "1.5"])
def test_capacity_unit_that_is_not_a_positive_integer_exits_2(
    stub_tools: StubTools, tmp_path: Path, unit: str
) -> None:
    # Act
    result = run_runner(stub_tools, tmp_path, ["--capacity", unit])

    # Assert
    assert result.returncode == 2
    assert result.stdout == ""


def test_capacity_without_a_unit_exits_2(stub_tools: StubTools, tmp_path: Path) -> None:
    # Act
    result = run_runner(stub_tools, tmp_path, ["--capacity"])

    # Assert
    assert result.returncode == 2


def write_psi(tmp_path: Path, some_avg10: float) -> Path:
    path = tmp_path / "psi"
    path.write_text(
        f"some avg10={some_avg10:.2f} avg60=0.00 avg300=0.00 total=0\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
        encoding="utf-8",
    )
    return path


def waiting_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if "waiting for memory" in line]


def test_memory_too_low_for_one_worker_waits_then_runs_with_one_worker(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 100)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_WAIT_TIMEOUT_S=100,
        DS_TEST_TIME_SCALE=0.01,
    )

    # Assert
    lines = result.stdout.splitlines()
    assert lines[0] == "ram: waiting for memory (MemAvailable 100 MB, PSI n/a)"
    assert len(waiting_lines(result)) >= 2
    assert "ram: still short after 100 s; running with -n 1" in lines
    assert logged_tokens(stub_tools)[-2:] == ["-n", "1"]


def test_pressure_above_the_limit_waits_even_with_plenty_of_memory(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)
    psi = write_psi(tmp_path, 25.0)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_PSI_PATH=str(psi),
        DS_TEST_WAIT_TIMEOUT_S=1,
        DS_TEST_TIME_SCALE=0.1,
    )

    # Assert
    assert "ram: waiting for memory (MemAvailable 4096 MB, PSI 25.0)" in result.stdout
    assert logged_tokens(stub_tools)[-2:] == ["-n", "1"]


def test_pressure_under_the_limit_does_not_wait(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)
    psi = write_psi(tmp_path, 3.0)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_PSI_PATH=str(psi),
        DS_TEST_WAIT_TIMEOUT_S=1,
        DS_TEST_TIME_SCALE=0.1,
    )

    # Assert
    assert waiting_lines(result) == []
    assert "ram: MemAvailable 4096 MB, PSI 3.0, xdist workers -n 2" in result.stdout


def test_missing_pressure_file_does_not_wait(
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
        DS_TEST_WAIT_TIMEOUT_S=1,
        DS_TEST_TIME_SCALE=0.1,
    )

    # Assert
    assert waiting_lines(result) == []
    assert logged_tokens(stub_tools)[-2:] == ["-n", "2"]


def test_memory_that_becomes_sufficient_ends_the_wait_with_the_sized_count(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 100)

    def free_memory() -> None:
        time.sleep(0.3)
        # Replaced atomically so the runner never reads a half-written file.
        replacement = tmp_path / "meminfo_new"
        replacement.write_text(
            f"MemTotal:       99999999 kB\nMemAvailable:   {4096 * 1024} kB\n",
            encoding="utf-8",
        )
        replacement.replace(meminfo)

    thread = threading.Thread(target=free_memory)

    # Act
    thread.start()
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_WAIT_TIMEOUT_S=100,
        DS_TEST_TIME_SCALE=0.01,
    )
    thread.join()

    # Assert
    lines = result.stdout.splitlines()
    assert "ram: waiting for memory (MemAvailable 100 MB, PSI n/a)" in lines
    assert any(line.startswith("ram: wait over after") for line in lines)
    assert logged_tokens(stub_tools)[-2:] == ["-n", "2"]
