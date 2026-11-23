"""Pytest plugin that records what each test costs, for `scripts/rank_test_costs.py`.

Load it with `-p scripts.record_test_costs` (with `PYTHONPATH` at the repo root). It writes
`.sdd-work/test_costs.json`: per node ID the setup, call and teardown seconds, plus the time
spent building and destroying the test database per worker, taken out of the phases it ran in. Under xdist only the controller writes the file.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from collections.abc import Generator
from pathlib import Path
from time import perf_counter
from typing import TypedDict

import pytest

DB_SETUP_FIXTURE = "django_db_setup"
DB_SETUP_PROPERTY = "django_db_setup_seconds"
DB_TEARDOWN_PROPERTY = "django_db_teardown_seconds"


class PhaseSeconds(TypedDict):
    setup: float
    call: float
    teardown: float


class CostsFile(TypedDict):
    tests: dict[str, PhaseSeconds]
    django_db_setup: dict[str, float]  # worker id -> seconds
    django_db_teardown: dict[str, float]  # worker id -> seconds
    test_count: int
    outcomes: dict[str, int]


def costs_path(root: Path) -> Path:
    return root / ".sdd-work" / "test_costs.json"


def worker_name(config: pytest.Config) -> str:
    """The xdist worker id, or "main" when the run is not distributed."""
    workerinput = getattr(config, "workerinput", None)
    return str(workerinput["workerid"]) if workerinput else "main"


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(CostRecorder(config), "record_test_costs_recorder")


class CostRecorder:
    """Collects phase durations; the methods are the hooks because `pytest_runtest_logreport`
    receives no `config` and the data has to live somewhere."""

    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.pending_db_setup = 0.0
        self.pending_db_teardown = 0.0
        self.db_teardown_start: float | None = None
        self.phases: dict[str, dict[str, float]] = defaultdict(dict)
        self.outcomes: dict[str, str] = {}
        self.db_setup: dict[str, float] = defaultdict(float)
        self.db_teardown: dict[str, float] = defaultdict(float)

    @pytest.hookimpl(wrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> Generator[None, object, object]:
        if fixturedef.argname != DB_SETUP_FIXTURE:
            return (yield)
        start = perf_counter()
        try:
            return (yield)
        finally:
            # The session-scoped database is built inside the setup phase of the first test
            # that asks for it; hold the time until that phase's report exists.
            self.pending_db_setup += perf_counter() - start
            # Finalizers run last-registered first, so this one runs before the fixture's
            # own teardown, which destroys the database.
            fixturedef.addfinalizer(self._start_db_teardown)

    def _start_db_teardown(self) -> None:
        self.db_teardown_start = perf_counter()

    def pytest_fixture_post_finalizer(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> None:
        if fixturedef.argname != DB_SETUP_FIXTURE or self.db_teardown_start is None:
            return
        # The database is destroyed inside the teardown phase of the last test on the
        # worker that holds it; hold the time until that phase's report exists.
        self.pending_db_teardown += perf_counter() - self.db_teardown_start
        self.db_teardown_start = None

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, pytest.TestReport, pytest.TestReport]:
        report = yield
        if call.when == "setup" and self.pending_db_setup:
            self._move_out(report, DB_SETUP_PROPERTY, self.pending_db_setup)
            self.pending_db_setup = 0.0
        if call.when == "teardown" and self.pending_db_teardown:
            self._move_out(report, DB_TEARDOWN_PROPERTY, self.pending_db_teardown)
            self.pending_db_teardown = 0.0
        return report

    def _move_out(self, report: pytest.TestReport, name: str, seconds: float) -> None:
        """Take database time out of the phase it ran in and attach it to the report."""
        report.duration = max(0.0, report.duration - seconds)
        # user_properties travel with the report from an xdist worker to the controller.
        report.user_properties.append(
            (name, {"worker": worker_name(self.config), "seconds": seconds})
        )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # Runs in workers too; only the controller's copy is written.
        self.phases[report.nodeid][report.when] = report.duration
        totals = {
            DB_SETUP_PROPERTY: self.db_setup,
            DB_TEARDOWN_PROPERTY: self.db_teardown,
        }
        for name, value in report.user_properties:
            if name in totals and isinstance(value, dict):
                totals[name][str(value["worker"])] += float(value["seconds"])
        self.outcomes[report.nodeid] = self._outcome(
            report, self.outcomes.get(report.nodeid)
        )

    @staticmethod
    def _outcome(report: pytest.TestReport, previous: str | None) -> str:
        """A failed setup or teardown is an error and a setup skip is a skip; otherwise the
        call report's outcome stands."""
        if report.when == "call":
            return "error" if previous == "error" else report.outcome
        if report.outcome == "failed":
            return "error"
        if report.outcome == "skipped" and report.when == "setup":
            return "skipped"
        return previous or report.outcome

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if hasattr(self.config, "workerinput"):
            return
        costs: CostsFile = {
            "tests": {
                nodeid: {
                    "setup": phases.get("setup", 0.0),
                    "call": phases.get("call", 0.0),
                    "teardown": phases.get("teardown", 0.0),
                }
                for nodeid, phases in sorted(self.phases.items())
            },
            "django_db_setup": dict(sorted(self.db_setup.items())),
            "django_db_teardown": dict(sorted(self.db_teardown.items())),
            "test_count": len(self.phases),
            "outcomes": dict(sorted(Counter(self.outcomes.values()).items())),
        }
        path = costs_path(self.config.rootpath)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(costs, indent=2) + "\n")
        os.replace(temporary, path)
