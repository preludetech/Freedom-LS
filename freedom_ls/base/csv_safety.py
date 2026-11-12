"""Neutralising spreadsheet formulas and marking a CSV body as UTF-8.

A cell is escaped when it starts with a formula trigger, even after leading
whitespace. The one exception is a phone number in E.164 form.

Shared by every CSV export in the project: the Django admin export in
`site_aware_models.admin_exports`, and the panel-framework table export.
"""

from __future__ import annotations

import re

# Includes the full-width forms, which some spreadsheets normalise to the ASCII
# operators, and line feed, which a spreadsheet may treat like carriage return.
FORMULA_TRIGGERS = (
    "=", "+", "-", "@", "\t", "\r", "\n",
    "\uff1d", "\uff0b", "\uff0d", "\uff20",
)  # fmt: skip
UTF8_BOM = "\ufeff"

# A phone number in E.164 form: an ASCII plus and 7 to 15 ASCII digits, nothing
# else. A spreadsheet can only read that as the number itself, and the
# apostrophe would stop a CRM or SMS tool reading the column as phone numbers.
_E164_PHONE_NUMBER = re.compile(r"\+[0-9]{7,15}")


def escape_csv_formula(value: str) -> str:
    """Prefix `'` when a spreadsheet could run the cell as a formula."""
    if _E164_PHONE_NUMBER.fullmatch(value):
        return value
    # str.lstrip() strips exactly what str.isspace() accepts. The first character
    # is checked on its own because tab is both a trigger and whitespace. An
    # empty slice is "", which is never a trigger.
    if value[:1] in FORMULA_TRIGGERS or value.lstrip()[:1] in FORMULA_TRIGGERS:
        return f"'{value}"
    return value
