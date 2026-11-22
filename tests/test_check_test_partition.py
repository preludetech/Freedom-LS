"""Tests for `claude_plugins/fls-dev/scripts/check_test_partition.py`.

Each test writes a collection file and group reports under `tmp_path` and runs the script as a
subprocess. The `pytester` tests collect a real generated package under `--splits`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

pytestmark = pytest.mark.dev_tooling

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "claude_plugins"
    / "fls-dev"
    / "scripts"
    / "check_test_partition.py"
)
TESTS = [f"pkg/test_m.py::test_{index}" for index in range(6)]


def write_report(path: Path, *collected_per_attempt: list[str]) -> Path:
    lines = [
        json.dumps({"event": "attempt", "n": number, "k": 1})
        + "\n"
        + json.dumps({"event": "collected", "nodeids": nodeids})
        for number, nodeids in enumerate(collected_per_attempt, start=1)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_collection(path: Path, nodeids: list[str]) -> Path:
    path.write_text(
        "\n".join(nodeids) + f"\n\n{len(nodeids)} tests collected in 0.10s\n",
        encoding="utf-8",
    )
    return path


def run_check(collection: Path, *reports: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(SCRIPT),
            "--collection",
            str(collection),
            *map(str, reports),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_reports_that_split_the_collection_exactly_pass(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS[:3])
    second = write_report(tmp_path / "two.jsonl", TESTS[3:])

    result = run_check(collection, first, second)

    assert (result.returncode, result.stdout.strip()) == (
        0,
        "partition: 6 tests in 2 groups",
    )


def test_node_id_in_two_reports_is_a_duplicate(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS[:4])
    second = write_report(tmp_path / "two.jsonl", TESTS[3:])

    result = run_check(collection, first, second)

    assert result.returncode == 1
    assert f"partition: duplicate {TESTS[3]} in {first}, {second}" in result.stdout


def test_node_id_in_no_report_is_missing(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS[:2])
    second = write_report(tmp_path / "two.jsonl", TESTS[3:])

    result = run_check(collection, first, second)

    assert result.returncode == 1
    assert f"partition: missing {TESTS[2]}" in result.stdout


def test_node_id_outside_the_collection_is_extra(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS[:3])
    second = write_report(
        tmp_path / "two.jsonl", [*TESTS[3:], "pkg/test_m.py::test_new"]
    )

    result = run_check(collection, first, second)

    assert result.returncode == 1
    assert "partition: extra pkg/test_m.py::test_new" in result.stdout


def test_report_without_a_collected_event_fails(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS)
    second = tmp_path / "two.jsonl"
    second.write_text('{"event": "attempt", "n": 1, "k": 1}\n', encoding="utf-8")

    result = run_check(collection, first, second)

    assert result.returncode == 1
    assert f"partition: no collection in {second}" in result.stdout


def test_missing_report_file_fails(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    absent = tmp_path / "absent.jsonl"

    result = run_check(collection, absent)

    assert result.returncode == 1
    assert f"partition: no collection in {absent}" in result.stdout


def test_crash_retried_report_counts_the_first_attempts_full_set(
    tmp_path: Path,
) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    first = write_report(tmp_path / "one.jsonl", TESTS[:3], TESTS[2:3])
    second = write_report(tmp_path / "two.jsonl", TESTS[3:])

    result = run_check(collection, first, second)

    assert (result.returncode, result.stdout.strip()) == (
        0,
        "partition: 6 tests in 2 groups",
    )


def test_groups_split_with_different_group_totals_fail(tmp_path: Path) -> None:
    collection = write_collection(tmp_path / "c.txt", TESTS)
    group_one_of_two = write_report(tmp_path / "one.jsonl", TESTS[:3])
    group_one_of_three = write_report(tmp_path / "two.jsonl", [*TESTS[:2]])

    result = run_check(collection, group_one_of_two, group_one_of_three)

    assert result.returncode == 1
    assert "partition: duplicate" in result.stdout


def test_output_is_capped_at_fifty_problem_lines(tmp_path: Path) -> None:
    many = [f"pkg/test_m.py::test_{index}" for index in range(80)]
    collection = write_collection(tmp_path / "c.txt", many)
    only = write_report(tmp_path / "one.jsonl", [many[0]])

    result = run_check(collection, only)

    assert result.stdout.splitlines()[-1] == "partition: ... and 29 more"


GENERATED_TESTS = 20


@pytest.mark.parametrize("seed", [1, 9876])
def test_pytest_split_groups_partition_a_generated_collection(
    pytester: pytest.Pytester, seed: int
) -> None:
    body = "\n".join(
        f"def test_{index}() -> None:\n    pass\n" for index in range(GENERATED_TESTS)
    )
    pytester.makepyfile(test_generated=body)
    durations = {f"test_generated.py::test_{index}": 0.5 + index for index in range(10)}
    (pytester.path / ".test_durations").write_text(
        json.dumps(durations), encoding="utf-8"
    )
    base = [
        "--collect-only",
        "-q",
        "-p",
        "no:django",
        "-p",
        "pytest_split",
        "-p",
        "randomly",
        f"--randomly-seed={seed}",
        "--splitting-algorithm",
        "least_duration",
        "--durations-path",
        ".test_durations",
        "--splits",
        "2",
    ]

    groups = [
        {
            line
            for line in pytester.runpytest_subprocess(
                *base, "--group", str(group)
            ).outlines
            if "::" in line
        }
        for group in (1, 2)
    ]

    assert groups[0].isdisjoint(groups[1])
    assert len(groups[0] | groups[1]) == GENERATED_TESTS
