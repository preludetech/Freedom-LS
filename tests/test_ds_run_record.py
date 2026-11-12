"""Tests for the `ds_run_record` pytest plugin.

Each test runs real pytest in a throwaway package with its own `pytest.ini`, with plugin
autoload off so the repository's `addopts` and plugins do not apply.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.dev_tooling

PLUGIN_DIR = (
    Path(__file__).resolve().parents[1] / "claude_plugins" / "django-stack" / "scripts"
)

SAMPLE_TESTS = """\
import pytest


@pytest.fixture
def bad_teardown():
    yield
    raise RuntimeError("teardown boom")


@pytest.fixture
def bad_setup():
    pytest.skip("skipped in setup")


def test_pass():
    pass


def test_fail():
    assert False


def test_skip_in_setup(bad_setup):
    pass


def test_teardown_error(bad_teardown):
    pass
"""

ALL_NODEIDS = [
    "test_sample.py::test_fail",
    "test_sample.py::test_pass",
    "test_sample.py::test_skip_in_setup",
    "test_sample.py::test_teardown_error",
]

XDIST = ["-p", "xdist", "-n", "2"]


def run_pytest(project: Path, *args: str) -> tuple[list[dict[str, object]], str]:
    """Run pytest with the plugin loaded; return the recorded events and pytest's stderr."""
    (project / "pytest.ini").write_text("[pytest]\n")
    (project / "test_sample.py").write_text(SAMPLE_TESTS)
    record = project / "record.jsonl"
    child_vars = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DS_TEST_") and key != "PYTEST_ADDOPTS"
    }
    child_vars["PYTHONPATH"] = str(PLUGIN_DIR)
    child_vars["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "ds_run_record",
            f"--ds-record={record}",
            *args,
        ],
        cwd=project,
        env=child_vars,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = record.read_text().splitlines() if record.exists() else []
    return [json.loads(line) for line in lines], completed.stderr


def outcome_lines(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [event for event in events if event["event"] == "outcome"]


@pytest.mark.parametrize(
    ("nodeid", "expected"),
    [
        ("test_sample.py::test_pass", "passed"),
        ("test_sample.py::test_fail", "failed"),
        ("test_sample.py::test_skip_in_setup", "skipped"),
        ("test_sample.py::test_teardown_error", "failed"),
    ],
)
def test_each_test_gets_one_outcome_line(
    tmp_path: Path, nodeid: str, expected: str
) -> None:
    events, _ = run_pytest(tmp_path)

    matching = [
        line["outcome"] for line in outcome_lines(events) if line["nodeid"] == nodeid
    ]
    assert matching == [expected]


@pytest.mark.parametrize("extra", [[], XDIST], ids=["no_xdist", "xdist"])
def test_collected_line_lists_every_nodeid_once(
    tmp_path: Path, extra: list[str]
) -> None:
    events, _ = run_pytest(tmp_path, *extra)

    collected = [event for event in events if event["event"] == "collected"]
    assert [sorted(str(i) for i in event["nodeids"]) for event in collected] == [
        ALL_NODEIDS
    ]


@pytest.mark.parametrize("extra", [[], XDIST], ids=["no_xdist", "xdist"])
def test_only_nodeids_runs_only_listed_tests(tmp_path: Path, extra: list[str]) -> None:
    (tmp_path / "only.txt").write_text("test_sample.py::test_pass\n")

    events, _ = run_pytest(
        tmp_path, f"--ds-only-nodeids={tmp_path / 'only.txt'}", *extra
    )

    assert [line["nodeid"] for line in outcome_lines(events)] == [
        "test_sample.py::test_pass"
    ]


def test_plugin_records_with_xdist_absent(tmp_path: Path) -> None:
    events, stderr = run_pytest(tmp_path)

    assert (len(outcome_lines(events)), "unrecognized arguments" in stderr) == (
        4,
        False,
    )


def test_xdist_worker_writes_nothing_so_each_outcome_appears_once(
    tmp_path: Path,
) -> None:
    events, _ = run_pytest(tmp_path, *XDIST)

    assert sorted(str(line["nodeid"]) for line in outcome_lines(events)) == ALL_NODEIDS


def test_finished_line_written_once(tmp_path: Path) -> None:
    events, _ = run_pytest(tmp_path)

    assert [event["event"] for event in events].count("finished") == 1


def test_finished_line_written_when_exitfirst_stops_the_session(tmp_path: Path) -> None:
    events, _ = run_pytest(tmp_path, "-x")

    assert [event["event"] for event in events].count("finished") == 1
