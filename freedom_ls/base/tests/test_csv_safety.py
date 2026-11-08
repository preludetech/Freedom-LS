"""Tests for the formula-injection guard shared by every CSV export."""

from __future__ import annotations

import pytest

from freedom_ls.base.csv_safety import FORMULA_TRIGGERS, escape_csv_formula


@pytest.mark.parametrize("trigger", FORMULA_TRIGGERS)
def test_escape_csv_formula_prefixes_every_trigger(trigger: str) -> None:
    assert escape_csv_formula(f"{trigger}x") == f"'{trigger}x"


@pytest.mark.parametrize("value", ["plain", "", "1+1", "a=b", "   ", "one\ntwo"])
def test_escape_csv_formula_leaves_other_values_alone(value: str) -> None:
    assert escape_csv_formula(value) == value


def test_formula_triggers_are_exactly_the_known_set() -> None:
    assert FORMULA_TRIGGERS == (
        "=", "+", "-", "@", "\t", "\r", "\n",
        "\uff1d", "\uff0b", "\uff0d", "\uff20",
    )  # fmt: skip


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("\uff1d1+1", "'\uff1d1+1"),
        ("\uff0dテスト", "'\uff0dテスト"),
        ("\nplain", "'\nplain"),
        (" =1+1", "' =1+1"),
        ("\u00a0@SUM(A1)", "'\u00a0@SUM(A1)"),
        ("\u3000=1+1", "'\u3000=1+1"),
        ("\n=1+1", "'\n'=1+1"),
        ('note\n=HYPERLINK("x")', 'note\n\'=HYPERLINK("x")'),
        ("one\r\n  -5\rtwo", "one\r\n'  -5\rtwo"),
        ("one\r\n\ttab", "one\r\n'\ttab"),
    ],
)
def test_escape_csv_formula_expected_results(value: str, expected: str) -> None:
    assert escape_csv_formula(value) == expected
