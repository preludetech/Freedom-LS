# Research: reference implementations of CSV formula neutralisation

## First-Class-LMS checkout

Not read. Glob searches under /home/sheena/workspace (and /home/sheena/workspace/lms) timed out after 20s with no match, and no shell tool was available to run `find`. `apps/admin_dashboard/lead_csv.py` (`EXTRA_FORMULA_TRIGGERS`, `escape_visitor_text`) is unverified. The spec author should read it directly or confirm its path.

## Current FLS helper

`freedom_ls/base/csv_safety.py`: `FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")`. It checks only `value[0]` and prefixes `'`. It does not strip leading whitespace and does not look at numbers (it takes `str` only).

## Comparison

| Implementation | Trigger set | Prefix / action | Leading whitespace stripped first? | Numbers |
|---|---|---|---|---|
| OWASP guidance | `= + - @`, TAB, CR, LF, plus full-width `＝ ＋ － ＠` (noted for e.g. Japanese locales) | Quote the field, prepend `'` (or a tab inside the quoted field). Warns this can fail after a re-save in Excel. | Not listed as a trigger | n/a |
| League CSV `EscapeFormula` (PHP) | `= - + @`, TAB, CR (constructor can add more single chars) | `'` | No | Non-strings pass through unchanged |
| csv-stringify `escape_formulas` (Node) | `= + - @`, TAB, CR (per docs and typings) | `'` (`=1` becomes `'=1`), default false | Not documented | Not documented |
| defusedcsv (Python) | `@ + - = \| %` (first char only) | `'`; also replaces `\|` with `\\|` | No | `Number` instances unchanged. Strings matching `^-?[0-9,\.]+$` are left alone. |
| django-import-export | Only `=` | Strips the leading `=`. No prefix. Setting `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT`, default False. | No | `str(cell)` first, so numbers are checked as strings |
| tablib CSV | None | None | No | n/a |
| Apache Commons CSV | None. Formula characters are not special-cased in quoting. | None | No | n/a |
| workglow-dev/sec PR #119 (example of a downstream fix) | `= + - @`, TAB, CR, tested per line after splitting on `\r\n`, `\r` and `\n` | `'` | Yes. It strips ASCII whitespace, NBSP, zero-width and bidi marks, BOM, and later invisible Hangul fillers, U+2028/9 and others, before testing. TAB and CR stay as triggers. | n/a |

Not verified: pandas, the Ruby `csv-safe` gem's current trigger set (CVE-2022-28481 said versions below 3.0.0 did not filter all special characters), `@json2csv`, GitLab, Sentry, Metabase, Odoo and Discourse. No sources were found for them.

## Findings relevant to the idea

- Only OWASP names LF and the full-width forms `＝ ＋ － ＠` as triggers. The libraries (League CSV, csv-stringify, defusedcsv) cover just the ASCII set, with TAB and CR. LF and full-width coverage is therefore stricter than the common libraries.
- `'` is the dominant prefix. defusedcsv's docs are said to prefix with a tab in some descriptions, but its code prefixes `'`.
- League CSV lets the caller extend the trigger list. This matches the idea's "add triggers to the shared helper" approach.
- Leading whitespace is a known bypass (workglow-dev/sec). Spreadsheets may ignore leading spaces or NBSP before `=`. Only that downstream fix handles it, and the idea does not mention it.
- Multi-line cells: after an embedded newline, a trigger at the start of a later line is a further risk (workglow-dev/sec handles it per line). Most libraries check only the first character.
- Numbers: defusedcsv and League CSV leave numeric types alone, so `-5` is not prefixed. defusedcsv also exempts numeric-looking strings. The FLS helper takes `str`, so callers decide.
- django-import-export's removal of `=` only is a weak reference and not worth copying.

## References

- OWASP CSV Injection: https://community.owasp.org/attacks/CSV_Injection
- defusedcsv source: https://raw.githubusercontent.com/raphaelm/defusedcsv/master/defusedcsv/csv.py
- League CSV EscapeFormula: https://raw.githubusercontent.com/thephpleague/csv/master/src/EscapeFormula.php
- django-import-export base_formats: https://raw.githubusercontent.com/django-import-export/django-import-export/main/import_export/formats/base_formats.py
- django-import-export PR #1568: https://github.com/django-import-export/django-import-export/pull/1568
- django-import-export docs: https://django-import-export.readthedocs.io/en/latest/installation.html
- tablib CSV format: https://raw.githubusercontent.com/jazzband/tablib/master/src/tablib/formats/_csv.py
- Apache Commons CSV CSVFormat: https://raw.githubusercontent.com/apache/commons-csv/master/src/main/java/org/apache/commons/csv/CSVFormat.java
- csv-stringify escape_formulas: https://csv.js.org/stringify/options/escape_formulas
- node-csv PR #380: https://github.com/adaltas/node-csv/issues/380
- csv-safe CVE-2022-28481: https://research.averlon.ai/vulnerability-intelligence/cve/CVE-2022-28481
- GHSA-f55g-x8qq-2569: https://osv.dev/vulnerability/GHSA-f55g-x8qq-2569
- workglow-dev/sec PR #119: https://github.com/workglow-dev/sec/pull/119

status: ok · reason: web survey done; First-Class-LMS checkout not located (glob timeouts); several named projects not verified
