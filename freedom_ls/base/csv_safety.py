"""Neutralising spreadsheet formulas and marking a CSV body as UTF-8.

Shared by every CSV export in the project: the Django admin export in
`site_aware_models.admin_exports`, and the panel-framework table export.
"""

from __future__ import annotations

# Includes the full-width forms, which some spreadsheets normalise to the ASCII
# operators, and line feed, which a spreadsheet may treat like carriage return.
FORMULA_TRIGGERS = (
    "=", "+", "-", "@", "\t", "\r", "\n",
    "\uff1d", "\uff0b", "\uff0d", "\uff20",
)  # fmt: skip
UTF8_BOM = "\ufeff"


def escape_csv_formula(value: str) -> str:
    """Stop a cell being executed as a formula when the CSV is opened."""
    if value and value[0] in FORMULA_TRIGGERS:
        return f"'{value}"
    return value
