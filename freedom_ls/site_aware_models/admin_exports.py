"""Shared pieces for admin CSV exports built on django-import-export.

Three things the package leaves to the caller beyond formula-escaping and the
UTF-8 byte-order mark (both in `freedom_ls.base.csv_safety`): a
django-import-export ``CSV`` format that applies them, rendering timestamps in
a form that does not depend on the project's date-format settings, and
rendering booleans as ``TRUE``/``FALSE`` so a spreadsheet reads them as
booleans rather than numbers.
"""

from __future__ import annotations

from datetime import date, datetime

from import_export.formats.base_formats import CSV
from import_export.resources import ModelResource
from import_export.widgets import BooleanWidget, DateTimeWidget, DateWidget
from tablib import Dataset

from freedom_ls.base.csv_safety import UTF8_BOM, escape_csv_formula


def _escape_cell(cell: object) -> object:
    return escape_csv_formula(cell) if isinstance(cell, str) else cell


class FormulaSafeCSV(CSV):
    """CSV a spreadsheet can open directly.

    Every string cell is escaped, headers included: a header can be text a
    form author typed, not only a model field name.
    """

    def export_data(self, dataset: Dataset, **kwargs: object) -> str:
        if dataset.headers is not None:
            dataset.headers = [_escape_cell(header) for header in dataset.headers]
        for index in range(len(dataset)):
            dataset[index] = [_escape_cell(cell) for cell in dataset[index]]
        body: str = super().export_data(dataset, **kwargs)
        return f"{UTF8_BOM}{body}"


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


class SpreadsheetBooleanWidget(BooleanWidget):
    """Render True as TRUE and False as FALSE, which a spreadsheet reads as booleans.

    The base widget writes 1 and 0, which a sheet reads as numbers. None, or
    anything that is not a bool, is an empty cell. Only text formats are
    offered, so the ``force_native_type`` path is not needed here.
    """

    def render(self, value: object, obj: object = None, **kwargs: object) -> str:
        if not isinstance(value, bool):
            return ""
        return "TRUE" if value else "FALSE"


class SiteAwareModelResource(ModelResource):
    """Resource base for site-aware models.

    Drops the ``site`` column, which is constant within one tenant's export,
    swaps the date widgets for the ISO 8601 ones and the boolean widget for
    the TRUE/FALSE one.
    """

    WIDGETS_MAP = {
        **ModelResource.WIDGETS_MAP,
        "DateTimeField": IsoDateTimeWidget,
        "DateField": IsoDateWidget,
        "BooleanField": SpreadsheetBooleanWidget,
    }

    class Meta:
        exclude = ("site",)
