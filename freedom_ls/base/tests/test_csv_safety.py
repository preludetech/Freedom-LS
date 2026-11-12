"""Tests for the formula-injection guard shared by every CSV export."""

from __future__ import annotations

import pytest

from freedom_ls.base.csv_safety import FORMULA_TRIGGERS, escape_csv_formula


@pytest.mark.parametrize("trigger", FORMULA_TRIGGERS)
def test_escape_csv_formula_prefixes_every_trigger(trigger: str) -> None:
    assert escape_csv_formula(f"{trigger}x") == f"'{trigger}x"


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "",
        "1+1",
        "a=b",
        "   ",
        "one\ntwo",
        'note\n=HYPERLINK("x")',
        "one\r\n  -5\rtwo",
        "one\r\n\ttab",
        "Notes:\n- one\n- two",
    ],
)
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
        ("\n=1+1", "'\n=1+1"),
    ],
)
def test_escape_csv_formula_expected_results(value: str, expected: str) -> None:
    assert escape_csv_formula(value) == expected


@pytest.mark.parametrize("value", ["+2782123", "+27821234567", "+123456789012345"])
def test_escape_csv_formula_leaves_an_e164_phone_number_alone(value: str) -> None:
    assert escape_csv_formula(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "+123456",
        "+1234567890123456",
        "+27 82 123 4567",
        "+27 82 CALL ME",
        "+27821234567+1",
        "+27821234567\n",
        " +27821234567",
        "\uff0b27821234567",
        "+\uff12\uff17821234567",
        "-27821234567",
    ],
)
def test_escape_csv_formula_escapes_a_plus_cell_that_is_not_exactly_e164(
    value: str,
) -> None:
    assert escape_csv_formula(value) == f"'{value}"
