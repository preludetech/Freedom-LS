# Research: codebase footprint of widening `escape_csv_formula`

## Current helper: `freedom_ls/base/csv_safety.py` (18 lines)
- L9: `FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")` (public tuple of single chars; also `UTF8_BOM = "﻿"` L10).
- L13-17: `escape_csv_formula(value: str) -> str`: `if value and value[0] in FORMULA_TRIGGERS: return f"'{value}"` else returns value. Checks only `value[0]`.
- Behaviour: empty string unchanged; leading whitespace other than tab/CR (space, `\n`) NOT escaped (a leading space then `=` passes). Type hint is `str` only; it does no isinstance check, so a non-str (None/int) would raise TypeError on `value[0]` (None falsy -> returned as-is; int 0 falsy returned; non-zero int -> `int[0]` TypeError). Callers guard against that (below).
- Negative numbers: the helper has no number logic. A numeric cell given as a str, e.g. "-5", IS escaped to "'-5". Numeric (int) cells are never passed in.

## Callers
1. `freedom_ls/site_aware_models/admin_exports.py:20,23-24,34-40`: `_escape_cell` only escapes `isinstance(cell, str)`; non-str (None, -5) passes untouched. `FormulaSafeCSV.export_data` escapes headers and body, prepends `UTF8_BOM`. Used by admin exports (`SiteAwareExportModelAdmin`/`SiteAwareModelResource`; e.g. accounts, referral_tracking, course_applications admins).
2. `freedom_ls/panel_framework/tables.py:12,212-217`: `ExportColumn.cell` returns `""` for None else `escape_csv_formula(str(raw))`. So here a negative int/Decimal becomes the string "-5" and IS escaped to "'-5" (existing behaviour, differs from the admin path). Header escaping in the panel export: not seen in tables.py (header from `ExportColumn.header`); the streaming writer is `freedom_ls/panel_framework/views.py:1222-1247` (imports only `UTF8_BOM`, L33; uses `csv.writer` L1241).
3. `freedom_ls/base/csv_import.py:14,144-154`: `write_error_csv` escapes every header and cell (all str) for the learner-import error CSV. Used by `freedom_ls/educator_interface/views.py` (`_csv_attachment` L2353) via the error-download path.
No other `csv.writer` use under `freedom_ls/` (grep). No direct imports of `FORMULA_TRIGGERS` in non-test code; `views.py:33` imports only `UTF8_BOM`.

## Existing tests
- `freedom_ls/base/tests/test_csv_safety.py`: `test_escape_csv_formula_prefixes_every_trigger` (L10-12, parametrised over `FORMULA_TRIGGERS`, asserts `f"'{trigger}x"`), `test_escape_csv_formula_leaves_other_values_alone` (L15-17, values `["plain", "", "1+1", "a=b"]`). Adding triggers to the tuple auto-extends the first; none of the "unchanged" values start with a new trigger, so no conflict.
- `freedom_ls/site_aware_models/tests/test_admin_exports.py`: L13 imports `FORMULA_TRIGGERS`; L26 `test_formula_safe_csv_escapes_header_starting_with_trigger` parametrised over `sorted(FORMULA_TRIGGERS)` (works for any strs; sorted needs strs - fine). L45 body cell `=1+1`; L63 `test_formula_safe_csv_leaves_non_string_cells_untouched` (None, -5 stay `""`, `"-5"`). Caveat: the "\n" trigger in a header via `csv.reader` round-trip: `_rows` uses `csv.reader`, a header `"\nheader"` is quoted by the writer and read back intact, probably fine but verify; `\r` and `\t` already pass today.
- `freedom_ls/panel_framework/tests/test_tables.py:954-962` `test_formula_cells_escaped` (`=cmd` -> `'=cmd`).
- `freedom_ls/course_applications/tests/test_resources.py:248-272` (answer `=1+1`, header `=SUM(A1)`).
- No test found asserting a value starting with LF or full-width char is unchanged. No conflicts found. New tests belong in `test_csv_safety.py` (parametrised); a cheap integration check optional in the admin and panel tests.

## Docs / conventions
- Mentions: `claude_plugins/fls-dev/resources/admin_interface.md:52,57` and `claude_plugins/fls-dev/skills/admin-interface/SKILL.md:18` (FormulaSafeCSV escapes triggers; never set `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT`); `docs/product/admin-interface.md:139` and `docs/product/signup-attribution.md:29` (generic "safe to open in a spreadsheet", no trigger list, so no edit needed). None list the trigger characters. No `docs/upgrade*` directory exists.
- Upgrade notes: authored per spec via `claude_plugins/fls-dev/commands/update_upgrade_notes.md` (schema at L14+; file is `<spec-dir>/upgrade_notes.md`). Downstream-relevant note: First-Class-LMS can delete its `EXTRA_FORMULA_TRIGGERS`/`escape_visitor_text` wrapper (`apps/admin_dashboard/lead_csv.py`, outside this repo, not inspectable here).
- Related future work: `spec_dd/1. next/extract_panels_framework*` plans COPY `escape_csv_formula` into the standalone panels package (research_coupling_audit.md:41-42; extract_panels_framework-3-standalone-backend/idea.md:14); that copy would need the same widening, or this change should land first.

## Constant-name reliance
- In-repo: `FORMULA_TRIGGERS` imported by two test modules (above). Keep that name and tuple-of-str shape (tests parametrise over it and `sorted()` it). Renaming/splitting it would break them.
- Downstream: the idea says First-Class-LMS wrapper defines its own `EXTRA_FORMULA_TRIGGERS` and defers to `escape_csv_formula`; it is not stated to import `FORMULA_TRIGGERS`. Not verifiable from this repo; keeping the existing names and the function signature is the safe choice.

## Design notes
- Full-width chars are single code points, so `value[0] in FORMULA_TRIGGERS` stays valid; adding `"\n"`, `"＝"`, `"＋"`, `"－"`, `"＠"` to the tuple is enough. Leading-whitespace bypass (space then `=`) is out of the stated scope.

status: ok
