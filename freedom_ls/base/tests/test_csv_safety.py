"""Tests for the formula-injection guard shared by every CSV export."""

from __future__ import annotations

import pytest

from freedom_ls.base.csv_safety import FORMULA_TRIGGERS, escape_csv_formula


@pytest.mark.parametrize("trigger", FORMULA_TRIGGERS)
def test_escape_csv_formula_prefixes_every_trigger(trigger: str) -> None:
    assert escape_csv_formula(f"{trigger}x") == f"'{trigger}x"


@pytest.mark.parametrize("value", ["plain", "", "1+1", "a=b"])
def test_escape_csv_formula_leaves_other_values_alone(value: str) -> None:
    assert escape_csv_formula(value) == value
