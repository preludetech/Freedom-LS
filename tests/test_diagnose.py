"""Tests for the pure log-signature matcher and main()'s exit-code logic in dev_db.diagnose.

No database or docker access: match_signature and summarise take plain strings, and main()
is exercised with the check functions patched at the I/O boundary.
"""

from __future__ import annotations

from unittest import mock

import pytest

from dev_db.diagnose import (
    DESKTOP_SIGNATURES,
    Finding,
    Verdict,
    format_finding,
    main,
    match_signature,
    summarise,
)


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
    ):
        exit_code = main()

    assert exit_code == 1
    assert engine_kind.called is False
    assert old_project.called is False
    assert container.called is False
