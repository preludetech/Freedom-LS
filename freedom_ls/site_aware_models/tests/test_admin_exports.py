"""Tests for the shared CSV export format, widgets and resource base."""

from __future__ import annotations

import codecs
import csv
import io
from datetime import UTC, date, datetime

import pytest
from tablib import Dataset

from freedom_ls.base.csv_safety import FORMULA_TRIGGERS
from freedom_ls.site_aware_models.admin_exports import (
    FormulaSafeCSV,
    IsoDateTimeWidget,
    IsoDateWidget,
    SpreadsheetBooleanWidget,
)


def _rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body.removeprefix("\ufeff"))))


@pytest.mark.parametrize("trigger", sorted(FORMULA_TRIGGERS))
def test_formula_safe_csv_escapes_header_starting_with_trigger(trigger: str) -> None:
    dataset = Dataset(headers=[f"{trigger}header", "count"])
    dataset.append(["a", 2])

    header, _ = _rows(FormulaSafeCSV().export_data(dataset))

    assert header == [f"'{trigger}header", "count"]


def test_formula_safe_csv_leaves_header_without_trigger_unchanged() -> None:
    dataset = Dataset(headers=["name", "count"])
    dataset.append(["a", 2])

    header, _ = _rows(FormulaSafeCSV().export_data(dataset))

    assert header == ["name", "count"]


def test_formula_safe_csv_escapes_body_cell_when_header_is_plain() -> None:
    dataset = Dataset(headers=["name", "count"])
    dataset.append(["=1+1", 2])

    _, row = _rows(FormulaSafeCSV().export_data(dataset))

    assert row == ["'=1+1", "2"]


def test_formula_safe_csv_starts_with_utf8_bom() -> None:
    dataset = Dataset(headers=["a"])
    dataset.append(["b"])

    body = FormulaSafeCSV().export_data(dataset)

    assert body.encode("utf-8").startswith(codecs.BOM_UTF8)


def test_formula_safe_csv_leaves_non_string_cells_untouched() -> None:
    dataset = Dataset(headers=["none", "negative"])
    dataset.append([None, -5])

    _, row = _rows(FormulaSafeCSV().export_data(dataset))

    assert row == ["", "-5"]


def test_iso_datetime_widget_renders_isoformat_with_offset() -> None:
    value = datetime(2026, 9, 9, 12, 30, 0, tzinfo=UTC)

    assert IsoDateTimeWidget().render(value) == "2026-09-09T12:30:00+00:00"


def test_iso_datetime_widget_renders_none_as_empty() -> None:
    assert IsoDateTimeWidget().render(None) == ""


def test_iso_date_widget_renders_isoformat() -> None:
    assert IsoDateWidget().render(date(2026, 9, 9)) == "2026-09-09"


def test_iso_date_widget_renders_none_as_empty() -> None:
    assert IsoDateWidget().render(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "TRUE"), (False, "FALSE"), (None, "")],
)
def test_spreadsheet_boolean_widget_renders_text_booleans(
    value: bool | None, expected: str
) -> None:
    assert SpreadsheetBooleanWidget().render(value) == expected
