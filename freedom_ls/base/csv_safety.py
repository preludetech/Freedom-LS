"""Neutralising spreadsheet formulas and marking a CSV body as UTF-8.

A cell is escaped when any of its lines starts with a formula trigger, even after
leading whitespace.

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


def _starts_formula(line: str) -> bool:
    # str.lstrip() strips exactly what str.isspace() accepts. The first character
    # is checked on its own because tab is both a trigger and whitespace. An
    # empty slice is "", which is never a trigger.
    return line[:1] in FORMULA_TRIGGERS or line.lstrip()[:1] in FORMULA_TRIGGERS


# Spreadsheets break cell lines on these and nothing else; \r\n comes first so it
# is taken as one break, not two.
_LINE_BREAK = re.compile(r"(\r\n|\r|\n)")


def escape_csv_formula(value: str) -> str:
    """Prefix `'` to each line of the cell that a spreadsheet could run as a formula."""
    if not value:
        return value
    # re.split with a capturing group alternates line, separator, line, ...
    parts = _LINE_BREAK.split(value)
    # A cell opening with CR or LF has an empty first line that the per-line
    # check cannot see, yet the cell still starts with a trigger.
    cell_starts_with_trigger = value[0] in FORMULA_TRIGGERS
    for index in range(0, len(parts), 2):
        if _starts_formula(parts[index]) or (index == 0 and cell_starts_with_trigger):
            parts[index] = f"'{parts[index]}"
    return "".join(parts)
