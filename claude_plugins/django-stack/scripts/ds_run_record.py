"""Pytest plugin that records what an attempt collected and finished, one JSON line per event.

Load it with `-p ds_run_record` and `PYTHONPATH` set to this directory. It imports only the
standard library and pytest, so it works with or without xdist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TextIO

import pytest

WORKER_CRASH = re.compile(r"worker '.+' crashed while running")

# Higher wins when a test's phases disagree.
OUTCOME_SEVERITY = {"passed": 0, "skipped": 1, "failed": 2}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ds_run_record")
    group.addoption(
        "--ds-record", default=None, help="JSON-lines file to append events to"
    )
    group.addoption(
        "--ds-only-nodeids",
        default=None,
        help="file of node ids, one per line; every other test is deselected",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect every item not listed. Runs on xdist workers too: collection happens there,
    and every worker must collect the same set."""
    only_file = config.getoption("--ds-only-nodeids")
    if only_file is None:
        return
    wanted = {line for line in Path(only_file).read_text().splitlines() if line}
    kept = [item for item in items if item.nodeid in wanted]
    dropped = [item for item in items if item.nodeid not in wanted]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


class Recorder:
    """Appends one JSON line per event and flushes it, so a killed run loses nothing written."""

    def __init__(self, handle: TextIO, uses_xdist: bool) -> None:
        self._handle = handle
        self._uses_xdist = uses_xdist
        self._collected_written = False
        self._final: set[str] = set()
        self._worst: dict[str, str] = {}

    def _write(self, event: dict[str, object]) -> None:
        self._handle.write(json.dumps(event) + "\n")
        self._handle.flush()

    # `node` is an xdist type, which cannot be imported when xdist is absent.
    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(
        self, node: object, ids: list[str]
    ) -> None:
        # Every worker collects the same set, so the first report is the whole list.
        if not self._collected_written:
            self._collected_written = True
            self._write({"event": "collected", "nodeids": list(ids)})

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        # Under xdist the controller collects nothing; its workers report through the hook above.
        if self._uses_xdist or self._collected_written:
            return
        self._collected_written = True
        self._write(
            {"event": "collected", "nodeids": [item.nodeid for item in session.items]}
        )

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid = report.nodeid
        if WORKER_CRASH.search(report.longreprtext):
            self._write({"event": "crashed", "nodeid": nodeid})
            return
        if nodeid in self._final:
            return
        previous = self._worst.get(nodeid, "passed")
        outcome = max(previous, report.outcome, key=OUTCOME_SEVERITY.__getitem__)
        self._worst[nodeid] = outcome
        # A setup or call that did not pass ends the test's story: a failing teardown after it
        # must not write a second line.
        is_final = report.when == "teardown" or (
            report.when in ("setup", "call") and report.outcome != "passed"
        )
        if is_final:
            self._final.add(nodeid)
            self._write({"event": "outcome", "nodeid": nodeid, "outcome": outcome})

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self._write({"event": "finished", "exitstatus": int(exitstatus)})
        self._handle.close()


def pytest_configure(config: pytest.Config) -> None:
    record_path = config.getoption("--ds-record")
    # A process with `workerinput` is an xdist worker: the controller sees every report, so
    # recording there too would write each outcome twice.
    if record_path and not hasattr(config, "workerinput"):
        uses_xdist = getattr(config.option, "dist", "no") != "no"
        handle = open(record_path, "a", encoding="utf-8")  # noqa: SIM115 - closed at session finish
        config.pluginmanager.register(
            Recorder(handle, uses_xdist), "ds_run_record_recorder"
        )
