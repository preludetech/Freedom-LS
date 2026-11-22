"""Check that a pool's group reports partition one collection of that pool.

usage: check_test_partition.py --collection <file of `pytest --collect-only -q` output> <group report>...

Every test of the collection must appear in exactly one group report. Prints one `partition:`
line per problem (at most 50, then a count of the rest) and exits 1; otherwise prints the
count of tests and groups and exits 0.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import ds_runner

MAX_PROBLEM_LINES = 50


def collected_in_pool(collection: Path) -> set[str]:
    """Node ids in `pytest --collect-only -q` output: the lines holding `::`."""
    return {
        line.strip()
        for line in collection.read_text(encoding="utf-8").splitlines()
        if "::" in line
    }


def collected_in_report(report: Path) -> set[str]:
    """The tests a group report collected, over every pytest attempt; empty when the file
    is absent or holds no `collected` event."""
    run_tests = ds_runner.load_run_tests()
    state = run_tests.RunState()
    if report.is_file():
        run_tests.read_attempt(report, state)
    collected: set[str] = state.collected
    return collected


def problems(pool: set[str], groups: dict[Path, set[str]]) -> list[str]:
    reports_by_test: dict[str, list[Path]] = defaultdict(list)
    for report, tests in groups.items():
        for test in tests:
            reports_by_test[test].append(report)
    lines = [
        f"partition: duplicate {test} in {', '.join(map(str, reports))}"
        for test, reports in sorted(reports_by_test.items())
        if len(reports) > 1
    ]
    lines += [
        f"partition: missing {test}" for test in sorted(pool - reports_by_test.keys())
    ]
    lines += [
        f"partition: extra {test}" for test in sorted(reports_by_test.keys() - pool)
    ]
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("reports", type=Path, nargs="+")
    args = parser.parse_args(argv)

    groups = {report: collected_in_report(report) for report in args.reports}
    empty = [report for report, tests in groups.items() if not tests]
    if empty:
        for report in empty:
            print(f"partition: no collection in {report}")  # noqa: T201
        return 1

    pool = collected_in_pool(args.collection)
    found = problems(pool, groups)
    if found:
        for line in found[:MAX_PROBLEM_LINES]:
            print(line)  # noqa: T201
        if len(found) > MAX_PROBLEM_LINES:
            print(f"partition: ... and {len(found) - MAX_PROBLEM_LINES} more")  # noqa: T201
        return 1
    print(f"partition: {len(pool)} tests in {len(groups)} groups")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
