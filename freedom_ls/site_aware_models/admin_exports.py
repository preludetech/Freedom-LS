"""Shared pieces for admin CSV exports built on django-import-export.

Three things the package leaves to the caller: neutralising spreadsheet
formulas (its own setting only strips a leading ``=``), writing the UTF-8
byte-order mark Excel on Windows needs to detect UTF-8, and rendering
timestamps in a form that does not depend on the project's date-format
settings.
"""

from __future__ import annotations

from datetime import date, datetime

from import_export.formats.base_formats import CSV
from import_export.resources import ModelResource
from import_export.widgets import DateTimeWidget, DateWidget
from tablib import Dataset

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_formula(value: str) -> str:
    """Stop a cell being executed as a formula when the CSV is opened."""
    if value and value[0] in FORMULA_TRIGGERS:
        return f"'{value}"
    return value


def _escape_cell(cell: object) -> object:
    return escape_csv_formula(cell) if isinstance(cell, str) else cell


class FormulaSafeCSV(CSV):
    """CSV a spreadsheet can open directly.

    Every string cell is escaped; headers are left alone because they name
    model fields, not values a visitor typed.
    """

    def export_data(self, dataset: Dataset, **kwargs: object) -> str:
        for index in range(len(dataset)):
            dataset[index] = [_escape_cell(cell) for cell in dataset[index]]
        body: str = super().export_data(dataset, **kwargs)
        return f"\ufeff{body}"


class IsoDateTimeWidget(DateTimeWidget):
    """Render a datetime as ISO 8601 with its offset, whatever the settings say.

    Only text formats are offered, so the binary-format ``force_native_type``
    path the base widget supports is not needed here.
    """

    def render(self, value: object, obj: object = None, **kwargs: object) -> str:
        return value.isoformat() if isinstance(value, datetime) else ""


class IsoDateWidget(DateWidget):
    """Render a date as ISO 8601, whatever the settings say."""

    def render(self, value: object, obj: object = None, **kwargs: object) -> str:
        return value.isoformat() if isinstance(value, date) else ""


class SiteAwareModelResource(ModelResource):
    """Resource base for site-aware models.

    Drops the ``site`` column, which is constant within one tenant's export,
    and swaps the date widgets for the ISO 8601 ones.
    """

    WIDGETS_MAP = {
        **ModelResource.WIDGETS_MAP,
        "DateTimeField": IsoDateTimeWidget,
        "DateField": IsoDateWidget,
    }

    class Meta:
        exclude = ("site",)
