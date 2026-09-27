"""Neutralising spreadsheet formulas and marking a CSV body as UTF-8.

Shared by every CSV export in the project: the Django admin export in
`site_aware_models.admin_exports`, and the panel-framework table export.
"""

from __future__ import annotations

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
UTF8_BOM = "\ufeff"


def escape_csv_formula(value: str) -> str:
    """Stop a cell being executed as a formula when the CSV is opened."""
    if value and value[0] in FORMULA_TRIGGERS:
        return f"'{value}"
    return value
