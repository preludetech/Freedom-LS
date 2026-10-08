"""Tests for the pure log-signature matcher and main()'s exit-code logic in dev_db.diagnose.

No database or docker access: match_signature and summarise take plain strings, and main()
is exercised with the check functions patched at the I/O boundary.
"""

from __future__ import annotations

from datetime import date
from unittest import mock

import pytest

from dev_db.diagnose import (
    DESKTOP_SIGNATURES,
    POSTGRES_SIGNATURES,
    Finding,
    Verdict,
    format_finding,
    main,
    match_signature,
    recent_log_names,
    summarise,
)

pytestmark = pytest.mark.dev_tooling


@pytest.mark.parametrize(
    "line",
    [
        "2026-01-01T00:00:00Z [ERROR] injecting event blocked for 30s",
        "2026-01-01T00:00:00Z [ERROR] Service fs failed to start",
    ],
)
def test_match_signature_classifies_a_desktop_signature(line: str) -> None:
    matched = match_signature(line, DESKTOP_SIGNATURES)

    assert matched in DESKTOP_SIGNATURES


def test_match_signature_returns_none_for_unrelated_line() -> None:
    matched = match_signature(
        "2026-01-01T00:00:00Z [INFO] all is well", DESKTOP_SIGNATURES
    )

    assert matched is None


# Sample lines shaped by the server's log_line_prefix: "%m [%p] %q%u@%d app=%a client=%h".
POSTGRES_LOG_LINES = [
    (
        "too many clients",
        "2026-09-27 10:15:23.123 UTC [1234] pguser@postgres app=psql client=172.18.0.1 "
        "FATAL:  sorry, too many clients already",
    ),
    (
        "remaining connection slots",
        "2026-09-27 10:15:24.001 UTC [1235] fls_dev@db_feature_x app=pytest:gw0:db_feature_x "
        "client=172.18.0.1 FATAL:  remaining connection slots are reserved for "
        "non-replication superuser connections",
    ),
    (
        "could not resize shared memory",
        "2026-09-27 10:15:25.500 UTC [1236] fls_dev@db_feature_x app=runserver:-:db_feature_x "
        "client=172.18.0.1 WARNING:  could not resize shared memory segment "
        '"/PostgreSQL.abc123" to 67108864 bytes',
    ),
    (
        "terminated by signal",
        "2026-09-27 10:15:26.000 UTC [1237]  LOG:  server process (PID 1238) was terminated "
        "by signal 9: Killed",
    ),
    (
        "No space left on device",
        "2026-09-27 10:15:27.000 UTC [1239] fls_dev@db_feature_x app=- client=172.18.0.1 "
        'ERROR:  could not extend file "base/16384/16385": No space left on device',
    ),
    (
        "PANIC",
        "2026-09-27 10:15:28.000 UTC [1240]  PANIC:  could not locate a valid checkpoint "
        "record",
    ),
    (
        "being accessed by other users",
        "2026-09-27 10:15:29.000 UTC [1241] pguser@postgres app=psql client=[local] "
        'ERROR:  database "db_feature_x" is being accessed by other users',
    ),
    (
        "idle-in-transaction timeout",
        "2026-09-27 10:15:30.000 UTC [1242] fls_dev@db_feature_x app=pytest:gw1:db_feature_x "
        "client=172.18.0.1 FATAL:  terminating connection due to idle-in-transaction timeout",
    ),
]


@pytest.mark.parametrize(("signature", "line"), POSTGRES_LOG_LINES)
def test_match_signature_classifies_a_postgres_signature(
    signature: str, line: str
) -> None:
    matched = match_signature(line, POSTGRES_SIGNATURES)

    assert matched == signature


def test_recent_log_names_for_a_sunday_returns_the_last_three_days() -> None:
    names = recent_log_names(date(2026, 10, 4))  # a Sunday

    assert names == ["postgresql-Sun.log", "postgresql-Sat.log", "postgresql-Fri.log"]


def test_recent_log_names_for_a_monday_wraps_to_sunday_and_saturday() -> None:
    names = recent_log_names(date(2026, 10, 5))  # a Monday

    assert names == ["postgresql-Mon.log", "postgresql-Sun.log", "postgresql-Sat.log"]


def test_summarise_counts_matches_and_keeps_the_last_occurrence() -> None:
    lines = [
        "line one: PANIC: disk full",
        "line two: nothing here",
        "line three: PANIC: disk full again",
    ]

    hits = summarise(lines, ("PANIC",))

    assert hits["PANIC"].count == 2
    assert hits["PANIC"].last_occurrence == "line three: PANIC: disk full again"


def test_format_finding_includes_next_step_when_present() -> None:
    finding = Finding(
        check="container",
        verdict=Verdict.FAIL,
        message="not running",
        next_step="start it",
    )

    assert format_finding(finding) == "[fail] container: not running -> next: start it"


def test_format_finding_omits_next_step_when_absent() -> None:
    finding = Finding(check="container", verdict=Verdict.OK, message="running fine")

    assert format_finding(finding) == "[ok] container: running fine"


def _finding(check: str, verdict: Verdict) -> Finding:
    return Finding(check=check, verdict=verdict, message="message")


def test_main_returns_1_when_a_finding_fails() -> None:
    with (
        mock.patch(
            "dev_db.diagnose.check_engine_reachable",
            return_value=[_finding("engine", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_engine_kind",
            return_value=[_finding("engine_kind", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_old_project",
            return_value=[_finding("old_project", Verdict.FAIL)],
        ),
        mock.patch(
            "dev_db.diagnose.check_container",
            return_value=[_finding("container", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_postgres_logs",
            return_value=[_finding("postgres_logs", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_postgres_activity",
            return_value=[_finding("postgres_activity", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_orphaned_processes",
            return_value=[_finding("orphaned_processes", Verdict.OK)],
        ),
    ):
        exit_code = main()

    assert exit_code == 1


def test_main_returns_0_when_no_finding_fails() -> None:
    with (
        mock.patch(
            "dev_db.diagnose.check_engine_reachable",
            return_value=[_finding("engine", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_engine_kind",
            return_value=[_finding("engine_kind", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_old_project",
            return_value=[_finding("old_project", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_container",
            return_value=[_finding("container", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_postgres_logs",
            return_value=[_finding("postgres_logs", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_postgres_activity",
            return_value=[_finding("postgres_activity", Verdict.OK)],
        ),
        mock.patch(
            "dev_db.diagnose.check_orphaned_processes",
            return_value=[_finding("orphaned_processes", Verdict.OK)],
        ),
    ):
        exit_code = main()

    assert exit_code == 0


def test_main_skips_later_checks_when_engine_is_unreachable() -> None:
    with (
        mock.patch(
            "dev_db.diagnose.check_engine_reachable",
            return_value=[_finding("engine", Verdict.FAIL)],
        ),
        mock.patch("dev_db.diagnose.check_engine_kind") as engine_kind,
        mock.patch("dev_db.diagnose.check_old_project") as old_project,
        mock.patch("dev_db.diagnose.check_container") as container,
        mock.patch("dev_db.diagnose.check_postgres_logs") as postgres_logs,
        mock.patch("dev_db.diagnose.check_postgres_activity") as postgres_activity,
        mock.patch("dev_db.diagnose.check_orphaned_processes") as orphaned_processes,
    ):
        exit_code = main()

    assert exit_code == 1
    assert engine_kind.called is False
    assert old_project.called is False
    assert container.called is False
    assert postgres_logs.called is False
    assert postgres_activity.called is False
    assert orphaned_processes.called is False
