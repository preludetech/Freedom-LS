"""Tests for `claude_plugins/django-stack/scripts/run_tests.py`.

The runner is started as a subprocess with `cwd=tmp_path`. Most tests replace `pytest` with a
stub executable on a temporary `PATH` that logs its argv and writes the record file's
`finished` line, so no real test run starts. The crash-recovery tests run real pytest against
a throwaway package. Free memory comes from a fake meminfo file.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.stub_tools import StubTools

pytestmark = pytest.mark.dev_tooling

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "run_tests.py"

# Logs its argv, then plays a pytest attempt: it records a `finished` line and exits with
# $STUB_PYTEST_EXIT_CODE. When $STUB_PYTEST_CRASH_FIRST is set, its first call instead kills
# itself by signal after writing what the value names: `uncollected` writes nothing,
# `collected` writes the collected line and one outcome, `truncated` also leaves a partial
# last line.
STUB_PYTEST = r"""#!/bin/sh
printf 'pytest %s\n' "$*" >> "$STUB_LOG_FILE"
for arg in "$@"; do
    case "$arg" in
        --ds-record=*) record="${arg#--ds-record=}" ;;
    esac
done
if [ -n "${STUB_PYTEST_CRASH_FIRST:-}" ] && [ "$(wc -l < "$STUB_LOG_FILE")" -eq 1 ]; then
    if [ "$STUB_PYTEST_CRASH_FIRST" != "uncollected" ]; then
        printf '{"event": "collected", "nodeids": ["t.py::a", "t.py::b"]}\n' >> "$record"
        printf '{"event": "outcome", "nodeid": "t.py::a", "outcome": "passed"}\n' >> "$record"
    fi
    if [ "$STUB_PYTEST_CRASH_FIRST" = "truncated" ]; then
        printf '{"event": "outc' >> "$record"
    fi
    kill -9 $$
fi
printf '{"event": "finished", "exitstatus": 0}\n' >> "$record"
exit "${STUB_PYTEST_EXIT_CODE:-0}"
"""


@pytest.fixture
def stub_tools(tmp_path: Path) -> StubTools:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "pytest"
    stub.write_text(STUB_PYTEST, encoding="utf-8")
    stub.chmod(0o755)
    return StubTools(bin_dir=bin_dir, log_file=tmp_path / "log.txt")


def write_meminfo(tmp_path: Path, available_mb: int) -> Path:
    path = tmp_path / "meminfo"
    path.write_text(
        f"MemTotal:       99999999 kB\nMemAvailable:   {available_mb * 1024} kB\n",
        encoding="utf-8",
    )
    return path


def without_unset_settings(
    variables: dict[str, str], settings: dict[str, str | int]
) -> dict[str, str]:
    """`variables` minus every `DS_TEST_*` entry the test does not set itself."""
    return {
        name: value
        for name, value in variables.items()
        if not name.startswith("DS_TEST_") or name in settings
    }


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
    child_env = without_unset_settings(
        stub_tools.env(TMPDIR=str(tmp_path), **settings), settings
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )


def is_record_option(token: str) -> bool:
    return token in ("-p", "ds_run_record") or token.startswith("--ds-record=")


def call_tokens(logged: str) -> list[str]:
    """One logged pytest call as tokens, without the record-plugin options the runner adds."""
    return [token for token in logged.split() if not is_record_option(token)]


def logged_tokens(stub_tools: StubTools) -> list[str]:
    (logged,) = stub_tools.log_lines()
    return call_tokens(logged)


def runner_worker_count(stub_tools: StubTools) -> str:
    """The value of the last `-n`, which is the one pytest reads."""
    tokens = logged_tokens(stub_tools)
    return tokens[len(tokens) - tokens[::-1].index("-n")]


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
    assert runner_worker_count(stub_tools) == expected_workers


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
    assert runner_worker_count(stub_tools) == str(os.cpu_count() or 1)


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
    assert logged_tokens(stub_tools) == [
        "pytest",
        "-nauto",
        "-n",
        "2",
        "--max-worker-restart=0",
    ]


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
    assert runner_worker_count(stub_tools) == expected_workers
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
    assert runner_worker_count(stub_tools) == "1"


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
    assert runner_worker_count(stub_tools) == "1"


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
    assert runner_worker_count(stub_tools) == "2"


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
    assert runner_worker_count(stub_tools) == "2"


def closing_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return result.stdout.splitlines()[-4:]


def test_run_without_a_crash_ends_with_the_four_closing_lines(
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
    assert [line.split(" ", 2)[:2] for line in closing_lines(result)] == [
        ["run:", "pytest"],
        ["run:", "tests"],
        ["run:", "summary"],
        ["run:", "RESULT"],
    ]


def test_run_without_a_crash_prints_one_record_line_after_the_ram_line(
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
    lines = result.stdout.splitlines()
    assert lines[0].startswith("ram: ")
    assert lines[1].startswith("run: record ")
    assert len([line for line in lines if line.startswith("run: record ")]) == 1


def test_record_file_is_deleted_after_a_passing_run(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(stub_tools, tmp_path, ["pytest"], DS_TEST_MEMINFO_PATH=str(meminfo))

    # Assert
    assert list(tmp_path.glob("ds_run_record_*.jsonl")) == []


def test_record_file_is_kept_after_a_failing_run(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_EXIT_CODE=1,
    )

    # Assert
    (kept,) = tmp_path.glob("ds_run_record_*.jsonl")
    assert f"run: record {kept}" in result.stdout.splitlines()


@pytest.mark.parametrize(
    ("pytest_exit", "label"), [(0, "PASS"), (1, "FAIL"), (2, "FAIL"), (5, "FAIL")]
)
def test_run_without_a_crash_reports_the_verdict_for_the_pytest_exit_code(
    stub_tools: StubTools, tmp_path: Path, pytest_exit: int, label: str
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_EXIT_CODE=pytest_exit,
    )

    # Assert
    assert closing_lines(result)[-1] == f"run: RESULT {label}"


@pytest.mark.parametrize("pytest_exit", [0, 1, 2, 5])
def test_run_without_a_crash_exits_with_the_pytest_exit_code(
    stub_tools: StubTools, tmp_path: Path, pytest_exit: int
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_EXIT_CODE=pytest_exit,
    )

    # Assert
    assert result.returncode == pytest_exit


def test_retry_after_a_signal_death_runs_only_the_unfinished_tests(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_CRASH_FIRST="collected",
    )

    # Assert
    first, retry = stub_tools.log_lines()
    assert "--ds-only-nodeids=" not in first
    only_options = [t for t in retry.split() if t.startswith("--ds-only-nodeids=")]
    assert len(only_options) == 1


def test_node_id_file_of_a_retry_is_deleted_when_the_run_ends(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_CRASH_FIRST="collected",
    )

    # Assert
    assert list(tmp_path.glob("ds_only_nodeids_*.txt")) == []


def test_retry_carries_no_cov_so_a_subset_run_cannot_fail_a_coverage_threshold(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    pytest.importorskip("pytest_cov")
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_CRASH_FIRST="collected",
    )

    # Assert
    first, retry = stub_tools.log_lines()
    assert "--no-cov" not in first.split()
    assert "--no-cov" in retry.split()


def test_retry_halves_the_worker_count_of_the_previous_attempt(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 10_000)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MAX_WORKERS=4,
        STUB_PYTEST_CRASH_FIRST="collected",
    )

    # Assert
    assert "run: pytest attempts 2, xdist workers 4 -> 2" in result.stdout.splitlines()


def test_crash_line_names_the_attempt_the_unfinished_count_and_the_retry_workers(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 10_000)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-n", "auto"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MAX_WORKERS=4,
        STUB_PYTEST_CRASH_FIRST="collected",
    )

    # Assert
    assert (
        "run: pytest attempt 1/3 crashed (1 tests unfinished); "
        "backing off 30 s, retrying with -n 2" in result.stdout.splitlines()
    )


def test_controller_that_died_before_collection_is_retried_with_the_whole_command(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    run_runner(
        stub_tools,
        tmp_path,
        ["pytest", "-m", "slow"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_CRASH_FIRST="uncollected",
    )

    # Assert
    first, retry = stub_tools.log_lines()
    assert call_tokens(retry) == call_tokens(first)


def test_partial_last_record_line_of_a_killed_controller_is_dropped_and_the_retry_runs(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        STUB_PYTEST_CRASH_FIRST="truncated",
    )

    # Assert
    assert closing_lines(result)[0].startswith("run: pytest attempts 2,")


def test_run_that_crashed_before_collecting_and_has_no_retries_left_is_incomplete(
    stub_tools: StubTools, tmp_path: Path
) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MAX_RETRIES=0,
        STUB_PYTEST_CRASH_FIRST="uncollected",
    )

    # Assert
    assert closing_lines(result)[-1] == "run: RESULT INCOMPLETE"


def test_incomplete_run_exits_75(stub_tools: StubTools, tmp_path: Path) -> None:
    # Arrange
    meminfo = write_meminfo(tmp_path, 4096)

    # Act
    result = run_runner(
        stub_tools,
        tmp_path,
        ["pytest"],
        DS_TEST_MEMINFO_PATH=str(meminfo),
        DS_TEST_MAX_RETRIES=0,
        STUB_PYTEST_CRASH_FIRST="uncollected",
    )

    # Assert
    assert result.returncode == 75


# Real pytest against a throwaway package. Plugin autoload is off, so the repository's
# `addopts` and plugins do not apply; xdist and the coverage plugin are named explicitly.

CRASH_ONCE_TESTS = """\
import os
import signal
from pathlib import Path

import pytest

MARKER = Path(r"{marker}")


@pytest.mark.parametrize("number", range(7))
def test_plain(number):
    pass


def test_kills_its_worker_once():
    if not MARKER.exists():
        MARKER.touch()
        os.kill(os.getpid(), signal.SIGKILL)
"""

KILLS_EVERY_TIME_TESTS = """\
import os
import signal

import pytest


@pytest.mark.parametrize("number", range(3))
def test_plain(number):
    pass


def test_kills_its_worker_every_time():
    os.kill(os.getpid(), signal.SIGKILL)
"""

GENUINE_FAILURE_TEST = """\


def test_genuine_failure():
    assert False
"""

FAILS_FIRST_TESTS = """\
def test_a_fails_first():
    assert False


def test_b_never_runs():
    pass
"""

REAL_RUN_ARGV = ["pytest", "-p", "xdist", "-p", "pytest_cov", "-n", "auto"]


@dataclass
class RealRun:
    """The outcome of one runner invocation over a real pytest package."""

    result: subprocess.CompletedProcess[str]
    temp_dir: Path

    @property
    def lines(self) -> list[str]:
        return self.result.stdout.splitlines()

    def record_events(self) -> list[dict[str, object]]:
        (record,) = self.temp_dir.glob("ds_run_record_*.jsonl")
        return [json.loads(line) for line in record.read_text("utf-8").splitlines()]


def run_real_pytest(
    work_dir: Path, tests: str, argv: list[str], **variables: str | int
) -> RealRun:
    """Run the runner over a package holding `tests`, with real pytest and xdist."""
    pytest.importorskip("xdist")
    pytest.importorskip("pytest_cov")
    package = work_dir / "package"
    package.mkdir()
    (package / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (package / "test_sample.py").write_text(
        tests.replace("{marker}", str(work_dir / "marker")), encoding="utf-8"
    )
    temp_dir = work_dir / "tmp"
    temp_dir.mkdir()
    meminfo = work_dir / "meminfo"
    meminfo.write_text("MemAvailable:   20971520 kB\n", encoding="utf-8")
    settings: dict[str, str | int] = {
        "DS_TEST_TIME_SCALE": 0,
        "DS_TEST_MAX_WORKERS": 4,
        "DS_TEST_WAIT_TIMEOUT_S": 1,
        "DS_TEST_MEMINFO_PATH": str(meminfo),
        "DS_TEST_PSI_PATH": str(work_dir / "no_such_psi"),
        **variables,
    }
    child_env = without_unset_settings(dict(os.environ), settings)
    child_env.update({name: str(value) for name, value in settings.items()})
    child_env.update(
        {
            "PATH": f"{Path(sys.executable).parent}{os.pathsep}{child_env['PATH']}",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TMPDIR": str(temp_dir),
        }
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *argv],
        cwd=package,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )
    return RealRun(result, temp_dir)


@pytest.fixture(scope="module")
def crash_once_run(tmp_path_factory: pytest.TempPathFactory) -> RealRun:
    return run_real_pytest(
        tmp_path_factory.mktemp("crash_once"), CRASH_ONCE_TESTS, REAL_RUN_ARGV
    )


@pytest.fixture(scope="module")
def crash_with_failure_run(tmp_path_factory: pytest.TempPathFactory) -> RealRun:
    return run_real_pytest(
        tmp_path_factory.mktemp("crash_with_failure"),
        CRASH_ONCE_TESTS + GENUINE_FAILURE_TEST,
        REAL_RUN_ARGV,
    )


@pytest.fixture(scope="module")
def crash_every_time_run(tmp_path_factory: pytest.TempPathFactory) -> RealRun:
    return run_real_pytest(
        tmp_path_factory.mktemp("crash_every_time"),
        KILLS_EVERY_TIME_TESTS,
        REAL_RUN_ARGV,
        DS_TEST_MAX_RETRIES=1,
    )


@pytest.fixture(scope="module")
def stop_on_first_failure_run(tmp_path_factory: pytest.TempPathFactory) -> RealRun:
    return run_real_pytest(
        tmp_path_factory.mktemp("stop_on_first_failure"),
        FAILS_FIRST_TESTS,
        ["pytest", "-x", "-p", "pytest_cov"],
    )


def test_worker_killed_once_ends_with_result_pass(crash_once_run: RealRun) -> None:
    assert "run: RESULT PASS" in crash_once_run.lines


def test_worker_killed_once_exits_0(crash_once_run: RealRun) -> None:
    assert crash_once_run.result.returncode == 0


def test_worker_killed_once_retries_with_half_the_workers(
    crash_once_run: RealRun,
) -> None:
    assert "run: pytest attempts 2, xdist workers 4 -> 2" in crash_once_run.lines


def test_worker_killed_once_prints_a_crash_line_with_the_unfinished_count(
    crash_once_run: RealRun,
) -> None:
    crash_lines = [
        line
        for line in crash_once_run.lines
        if re.fullmatch(
            r"run: pytest attempt 1/3 crashed \(\d+ tests unfinished\); "
            r"backing off 30 s, retrying with -n 2",
            line,
        )
    ]
    assert len(crash_lines) == 1


def test_worker_killed_once_counts_every_test_once_in_the_merged_summary(
    crash_once_run: RealRun,
) -> None:
    (summary,) = [line for line in crash_once_run.lines if "summary (merged)" in line]
    assert re.fullmatch(
        r"run: summary \(merged\): 8 passed, 0 failed, 0 skipped in [\d.]+s", summary
    )


def test_worker_killed_once_leaves_no_test_unfinished(crash_once_run: RealRun) -> None:
    assert (
        "run: tests 8 collected, 8 finished, 0 failed, 0 unfinished"
        in crash_once_run.lines
    )


def test_worker_killed_once_deletes_the_record_file(crash_once_run: RealRun) -> None:
    assert list(crash_once_run.temp_dir.glob("ds_run_record_*.jsonl")) == []


def test_crash_with_a_genuine_failure_ends_with_result_fail(
    crash_with_failure_run: RealRun,
) -> None:
    assert "run: RESULT FAIL" in crash_with_failure_run.lines


def test_crash_with_a_genuine_failure_exits_1(
    crash_with_failure_run: RealRun,
) -> None:
    assert crash_with_failure_run.result.returncode == 1


def test_genuine_failure_has_exactly_one_outcome_line_in_the_kept_record(
    crash_with_failure_run: RealRun,
) -> None:
    outcomes = [
        event
        for event in crash_with_failure_run.record_events()
        if event.get("nodeid") == "test_sample.py::test_genuine_failure"
        and event.get("event") == "outcome"
    ]
    assert len(outcomes) == 1


def test_worker_killed_every_time_ends_with_result_incomplete(
    crash_every_time_run: RealRun,
) -> None:
    assert "run: RESULT INCOMPLETE" in crash_every_time_run.lines


def test_worker_killed_every_time_exits_75(crash_every_time_run: RealRun) -> None:
    assert crash_every_time_run.result.returncode == 75


def test_worker_killed_every_time_names_the_attempt_out_of_the_total(
    crash_every_time_run: RealRun,
) -> None:
    assert any(
        line.startswith("run: pytest attempt 1/2 crashed")
        for line in crash_every_time_run.lines
    )


def test_run_stopped_by_x_on_a_failure_ends_with_result_fail(
    stop_on_first_failure_run: RealRun,
) -> None:
    assert "run: RESULT FAIL" in stop_on_first_failure_run.lines


def test_run_stopped_by_x_on_a_failure_makes_one_pytest_attempt(
    stop_on_first_failure_run: RealRun,
) -> None:
    attempts = [
        line
        for line in stop_on_first_failure_run.lines
        if line.startswith("run: pytest attempts ")
    ]
    assert attempts[0].startswith("run: pytest attempts 1,")


# A pytest stand-in for the process-hygiene tests. It writes the oom_score_adj it inherited to
# $STUB_SCORE_FILE and its parent's pid (the runner) to $STUB_PARENT_FILE, then does what
# $STUB_MODE names: `finish` records a finished session and exits; `hold` waits until
# $STUB_RELEASE_FILE exists; `sleep` sleeps; `detach` starts a detached `sleep 300`, writes its
# pid to $STUB_CHILD_FILE and finishes; `retry_sleeps` crashes on its first call and sleeps on
# its second.
STUB_HYGIENE_PYTEST = r"""#!/bin/sh
for arg in "$@"; do
    case "$arg" in
        --ds-record=*) record="${arg#--ds-record=}" ;;
    esac
done
cat /proc/self/oom_score_adj > "$STUB_SCORE_FILE"
echo $PPID > "$STUB_PARENT_FILE"
finish() {
    printf '{"event": "finished", "exitstatus": 0}\n' >> "$record"
    exit 0
}
case "$STUB_MODE" in
    finish) finish ;;
    hold)
        while [ ! -e "$STUB_RELEASE_FILE" ]; do sleep 0.05; done
        finish
        ;;
    sleep)
        echo $$ > "$STUB_CHILD_FILE"
        exec sleep 300
        ;;
    detach)
        python3 -c 'import subprocess, sys; open(sys.argv[1], "w").write(str(subprocess.Popen(["sleep", "300"], start_new_session=True).pid))' "$STUB_CHILD_FILE"
        finish
        ;;
    retry_sleeps)
        if [ ! -e "$STUB_FIRST_DONE_FILE" ]; then
            touch "$STUB_FIRST_DONE_FILE"
            printf '{"event": "collected", "nodeids": ["t.py::a", "t.py::b"]}\n' >> "$record"
            printf '{"event": "outcome", "nodeid": "t.py::a", "outcome": "passed"}\n' >> "$record"
            kill -9 $$
        fi
        echo $$ > "$STUB_CHILD_FILE"
        exec sleep 300
        ;;
esac
"""

WAIT_LIMIT_S = 20


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_file(path: Path) -> str:
    deadline = time.monotonic() + WAIT_LIMIT_S
    while time.monotonic() < deadline:
        if path.exists() and path.read_text(encoding="utf-8").strip():
            return path.read_text(encoding="utf-8").strip()
        time.sleep(0.02)
    raise AssertionError(f"{path} was not written within {WAIT_LIMIT_S} s")


@dataclass
class HygieneRun:
    """A runner started with the hygiene stub; its files live in `tmp_path`."""

    tmp_path: Path
    process: subprocess.Popen[str]

    def file(self, name: str) -> Path:
        return self.tmp_path / name


@pytest.fixture
def start_hygiene_run(
    stub_tools: StubTools, tmp_path: Path
) -> Iterator[Callable[..., HygieneRun]]:
    """Start the runner on the hygiene stub. Teardown kills the runner and the pid the stub
    recorded, so a failed assertion leaves no `sleep 300` behind."""
    started: list[subprocess.Popen[str]] = []
    stub = stub_tools.bin_dir / "pytest"
    stub.write_text(STUB_HYGIENE_PYTEST, encoding="utf-8")
    stub.chmod(0o755)

    def start(mode: str, **variables: str | int) -> HygieneRun:
        settings = {
            "DS_TEST_TIME_SCALE": 0,
            "DS_TEST_PSI_PATH": str(tmp_path / "no_such_psi"),
            "DS_TEST_MEMINFO_PATH": str(write_meminfo(tmp_path, 4096)),
            "DS_TEST_MAX_WORKERS": 2,
            "STUB_MODE": mode,
            "STUB_SCORE_FILE": str(tmp_path / "score.txt"),
            "STUB_PARENT_FILE": str(tmp_path / "parent.txt"),
            "STUB_CHILD_FILE": str(tmp_path / "child.txt"),
            "STUB_RELEASE_FILE": str(tmp_path / "release"),
            "STUB_FIRST_DONE_FILE": str(tmp_path / "first_done"),
            **variables,
        }
        runner_environment = without_unset_settings(
            stub_tools.env(TMPDIR=str(tmp_path), **settings), settings
        )
        process = subprocess.Popen(  # noqa: S603
            [sys.executable, str(SCRIPT), "pytest"],
            cwd=tmp_path,
            env=runner_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started.append(process)
        return HygieneRun(tmp_path=tmp_path, process=process)

    yield start

    for process in started:
        process.kill()
        process.communicate()
    recorded = tmp_path / "child.txt"
    if recorded.exists() and recorded.read_text(encoding="utf-8").strip():
        pid = int(recorded.read_text(encoding="utf-8"))
        if process_is_alive(pid):
            os.kill(pid, signal.SIGKILL)


def inherited_score() -> int:
    return int(Path("/proc/self/oom_score_adj").read_text(encoding="utf-8"))


def child_score(run: HygieneRun) -> int:
    run.process.communicate(timeout=WAIT_LIMIT_S)
    return int(run.file("score.txt").read_text(encoding="utf-8"))


def test_pytest_child_gets_the_default_oom_score_of_500(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    run = start_hygiene_run("finish")

    assert child_score(run) == 500


def test_pytest_child_gets_the_oom_score_from_the_environment(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    run = start_hygiene_run("finish", DS_TEST_OOM_SCORE_ADJ=700)

    assert child_score(run) == 700


def test_runner_keeps_the_oom_score_it_started_with(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    # Arrange
    run = start_hygiene_run("hold")
    runner_pid = int(wait_for_file(run.file("parent.txt")))

    # Act
    runner_score = int(
        Path(f"/proc/{runner_pid}/oom_score_adj").read_text(encoding="utf-8")
    )
    run.file("release").touch()
    run.process.communicate(timeout=WAIT_LIMIT_S)

    # Assert
    assert runner_score == inherited_score()


def test_oom_score_adj_of_zero_leaves_the_child_with_the_score_of_the_runner(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    run = start_hygiene_run("finish", DS_TEST_OOM_SCORE_ADJ=0)

    assert child_score(run) == inherited_score()


def test_process_a_test_detached_is_gone_after_the_runner_exits(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    # Arrange
    run = start_hygiene_run("detach")

    # Act
    run.process.communicate(timeout=WAIT_LIMIT_S)
    detached_pid = int(run.file("child.txt").read_text(encoding="utf-8"))

    # Assert
    assert not process_is_alive(detached_pid)


def test_sigterm_makes_the_runner_exit_143(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    # Arrange
    run = start_hygiene_run("sleep")
    wait_for_file(run.file("child.txt"))

    # Act
    run.process.terminate()
    run.process.communicate(timeout=WAIT_LIMIT_S)

    # Assert
    assert run.process.returncode == 143


def test_sigterm_kills_the_pytest_process(
    start_hygiene_run: Callable[..., HygieneRun],
) -> None:
    # Arrange
    run = start_hygiene_run("sleep")
    pytest_pid = int(wait_for_file(run.file("child.txt")))

    # Act
    run.process.terminate()
    run.process.communicate(timeout=WAIT_LIMIT_S)

    # Assert
    assert not process_is_alive(pytest_pid)


def test_sigterm_during_a_retry_leaves_no_node_id_file(
    start_hygiene_run: Callable[..., HygieneRun], tmp_path: Path
) -> None:
    # Arrange
    run = start_hygiene_run("retry_sleeps")
    wait_for_file(run.file("child.txt"))

    # Act
    run.process.terminate()
    run.process.communicate(timeout=WAIT_LIMIT_S)

    # Assert
    assert list(tmp_path.glob("ds_only_nodeids_*.txt")) == []
