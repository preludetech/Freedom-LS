"""Tests for the test-cost recorder plugin, `scripts/record_test_costs.py`, and the ranking
script, `scripts/rank_test_costs.py`.

The recorder tests run a small inner suite in a subprocess, so the plugin sees a real pytest
session, including a real xdist controller and workers. The ranking tests render from fixed
input, and run `main` against a throwaway inner pytest run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from scripts import rank_test_costs
from scripts.record_test_costs import CostRecorder, CostsFile, costs_path

pytestmark = pytest.mark.dev_tooling

pytest_plugins = ["pytester"]

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "rank_test_costs"
DB_SETUP_SECONDS = 0.5
DISTRIBUTED = ["-n", "2", "--dist", "loadfile"]
PLUGIN_ARGS = [
    "-p",
    "scripts.record_test_costs",
    "-p",
    "no:django",
    "-p",
    "no:randomly",
    "-p",
    "no:cacheprovider",
]
TEST_FILE_BODY = (
    "def test_with_db(django_db_setup):\n    pass\n\ndef test_without_db():\n    pass\n"
)


@pytest.fixture
def inner_suite(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> pytest.Pytester:
    """Two test files, each with one test that asks for a slow `django_db_setup` and one that
    does not, so `--dist loadfile` puts one file on each worker."""
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    pytester.makeconftest(
        "import time\n"
        "import pytest\n"
        "\n"
        '@pytest.fixture(scope="session")\n'
        "def django_db_setup():\n"
        f"    time.sleep({DB_SETUP_SECONDS})\n"
    )
    pytester.makepyfile(test_one=TEST_FILE_BODY, test_two=TEST_FILE_BODY)
    return pytester


def run_inner(suite: pytest.Pytester, extra_args: list[str]) -> CostsFile:
    result = suite.runpytest_subprocess(*PLUGIN_ARGS, *extra_args)
    result.assert_outcomes(passed=4)
    costs: CostsFile = json.loads(costs_path(suite.path).read_text())
    return costs


@pytest.mark.parametrize("extra_args", [[], DISTRIBUTED], ids=["serial", "distributed"])
def test_plugin_writes_three_phase_seconds_per_node_id(
    inner_suite: pytest.Pytester, extra_args: list[str]
) -> None:
    # Arrange
    expected_ids = {
        f"{module}.py::{name}"
        for module in ("test_one", "test_two")
        for name in ("test_with_db", "test_without_db")
    }

    # Act
    costs = run_inner(inner_suite, extra_args)

    # Assert
    assert set(costs["tests"]) == expected_ids
    for phases in costs["tests"].values():
        assert set(phases) == {"setup", "call", "teardown"}
        assert all(isinstance(seconds, float) for seconds in phases.values())
    assert costs["test_count"] == 4
    assert costs["outcomes"] == {"passed": 4}


def test_plugin_excludes_database_setup_from_the_triggering_test(
    inner_suite: pytest.Pytester,
) -> None:
    # Act
    costs = run_inner(inner_suite, [])

    # Assert
    # The margin is the sleep itself: a loaded machine slows the other work in the phase, but
    # the sleep is what must be gone.
    assert costs["tests"]["test_one.py::test_with_db"]["setup"] < DB_SETUP_SECONDS


@pytest.mark.parametrize(
    ("extra_args", "worker_count"),
    [([], 1), (DISTRIBUTED, 2)],
    ids=["serial", "distributed"],
)
def test_plugin_reports_database_setup_once_per_worker(
    inner_suite: pytest.Pytester, extra_args: list[str], worker_count: int
) -> None:
    # Act
    costs = run_inner(inner_suite, extra_args)

    # Assert
    assert len(costs["django_db_setup"]) == worker_count
    assert all(
        seconds >= DB_SETUP_SECONDS for seconds in costs["django_db_setup"].values()
    )


def test_recorder_on_a_worker_writes_nothing(tmp_path: Path) -> None:
    # Arrange
    config = cast(
        pytest.Config,
        SimpleNamespace(workerinput={"workerid": "gw0"}, rootpath=tmp_path),
    )
    recorder = CostRecorder(config)

    # Act
    recorder.pytest_sessionfinish(cast(pytest.Session, SimpleNamespace()))

    # Assert
    assert not costs_path(tmp_path).exists()


@pytest.mark.parametrize(
    ("nodeid", "expected"),
    [
        ("a.py::test_x[1]", "a.py::test_x"),
        ("a.py::test_x[2]", "a.py::test_x"),
        ("a.py::TestC::test_y[p::q]", "a.py::TestC::test_y"),
        ("a.py::test_z", "a.py::test_z"),
    ],
)
def test_function_key_groups_parametrized_cases(nodeid: str, expected: str) -> None:
    # Act
    key = rank_test_costs.function_key(nodeid)

    # Assert
    assert key == expected


def test_render_ranking_matches_the_expected_file() -> None:
    # Arrange
    costs: CostsFile = json.loads((FIXTURES / "test_costs.json").read_text())
    run = rank_test_costs.RunInfo(
        date="2026-01-02",
        commit="abc1234",
        cpu_seconds=38.0,
        wall_seconds=12.5,
        conditions=(
            "pytest arguments: -p scripts.record_test_costs -n 4 --no-cov",
            "Python: 3.13.1",
            "CPUs: 8",
            "Load average at start: 1.50 1.25 1.00; CPU pressure avg60 at start: 0.50",
            "Load average at end: 2.50 2.00 1.50; CPU pressure avg60 at end: n/a",
        ),
    )

    # Act
    rendered = rank_test_costs.render_ranking(costs, run, top_files=2, top_functions=3)

    # Assert
    assert rendered == (FIXTURES / "expected_ranking.md").read_text()


@pytest.fixture
def failing_run(
    pytester: pytest.Pytester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], Path]:
    """The command for an inner pytest run with one failing test, and a ranking file that
    already exists."""
    monkeypatch.setattr(rank_test_costs, "COSTS_PATH", costs_path(tmp_path))
    pytester.makeini("[pytest]\n")
    test_file = pytester.makepyfile(
        test_failing="def test_fails():\n    assert False\n"
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--rootdir",
        str(pytester.path),
        "-c",
        str(pytester.path / "tox.ini"),
        "-p",
        "no:cacheprovider",
        "-p",
        "no:django",
        "-p",
        "no:randomly",
        str(test_file),
    ]
    ranking = tmp_path / "test_cost_ranking.md"
    ranking.write_text("the previous ranking\n")
    return command, ranking


def test_main_with_failing_tests_leaves_the_ranking_unchanged(
    failing_run: tuple[list[str], Path],
) -> None:
    # Arrange
    command, ranking = failing_run

    # Act
    rank_test_costs.main(command=command, output=ranking)

    # Assert
    assert ranking.read_text() == "the previous ranking\n"


def test_main_with_failing_tests_exits_non_zero(
    failing_run: tuple[list[str], Path],
) -> None:
    # Arrange
    command, ranking = failing_run

    # Act
    exit_code = rank_test_costs.main(command=command, output=ranking)

    # Assert
    assert exit_code != 0
