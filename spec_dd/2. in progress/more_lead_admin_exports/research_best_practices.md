# Research: best practices for exporting users and variable-question form submissions from a Django admin

Idea: export Users and Applications (including anonymous ones) via the admin; application exports include the full application form (all questions and answers).

## Codebase facts that shape the advice

- django-import-export and django-unfold are already dependencies. An existing pattern is in `freedom_ls/site_aware_models/admin_exports.py`: `FormulaSafeCSV` (a `CSV` format that escapes every string cell via `freedom_ls.base.csv_safety.escape_csv_formula` and prepends a UTF-8 BOM), ISO 8601 date widgets, and `SiteAwareModelResource` (drops the constant `site` column). `freedom_ls/referral_tracking/resources.py` is an existing consumer. The new exports should reuse this, not invent a second mechanism.
- Headers are NOT escaped by `FormulaSafeCSV`. This is fine for model-field headers, but the application export will have headers derived from question text (admin-authored, but still free text). Those headers must be escaped too (see injection section).
- No `IMPORT_EXPORT_*` settings were found in `config/settings_base.py`, so the package defaults apply: everyone with admin access to the export UI can export unless gated, and formula escaping is off (the custom format covers this).

## 1. CSV vs XLSX

- CSV: simplest, streamable, diffable, universally importable. Weaknesses: no types (leading zeros, long IDs, dates get mangled by Excel), encoding quirks, and formula injection.
- XLSX: keeps types, supports multiple sheets (e.g. one sheet for answers in long format, one in wide), no encoding problem. Costs: openpyxl builds the workbook in memory (unless write-only mode is used), it is not streamable in the HTTP sense, and it rejects illegal control characters (django-import-export raises `ValueError` unless `IMPORT_EXPORT_ESCAPE_ILLEGAL_CHARS_ON_EXPORT` is on). Formula injection still applies to XLSX string cells.
- Practice: ship CSV as default (matches the existing `FormulaSafeCSV`); offer XLSX only if users need it, and size-cap it. With django-import-export, formats are controlled by `EXPORT_FORMATS` / per-admin `export_formats`.
- Source: https://django-import-export.readthedocs.io/en/latest/installation.html

## 2. CSV / formula injection

- The risk: cells starting with `=`, `+`, `-`, `@` (and tab / carriage return) are treated as formulas by Excel/Sheets/LibreOffice. Users, and especially anonymous application submitters, control these values (name, free-text answers), so the exported file is an attack vector against the staff who open it.
- Standard mitigation (OWASP): prefix such cells with a single quote (or otherwise neutralise them). Known caveat: the apostrophe prefix is partial, since a user can edit it away after opening; also apply to every export path including headers.
- The Python options: `defusedcsv` (drop-in `csv` replacement), or a small helper (what the project already has in `escape_csv_formula`). django-import-export has `IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` (default False), which only strips a leading `=`; that is weaker than the OWASP guidance, so prefer the project's own helper.
- Apply it to: all string cells, header row (question text), and to XLSX if offered. Escape after flattening (the flattened value is what lands in the cell). Test with values like `=1+1`, `+cmd`, `-2+3`, `@SUM(1)`, `\t=1`, `\r=1`.
- Sources:
  - https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
  - https://cwe.mitre.org/data/definitions/1236
  - https://securelayer7.net/lab/cve-2026-45263-facturascripts-csv-formula-injection-csvexport (fix must cover header writer and other export paths)

## 3. Streaming large exports

- Django docs: use `StreamingHttpResponse` plus a generator and the `Echo` pseudo-buffer with `csv.writer`; batch rows (`itertools.batched(rows, 100)`) to cut per-chunk overhead. Reasons: avoid memory spikes and avoid load-balancer timeouts on slow idle connections. Source: https://docs.djangoproject.com/en/stable/howto/outputting-csv/
- Pair streaming with `queryset.iterator(chunk_size=...)` and `select_related` / `prefetch_related` (note: `iterator()` ignores `prefetch_related` unless a `chunk_size` is passed, and Django supports it from 4.1). Avoid per-row queries (N+1) when fetching answers.
- django-import-export does not stream the HTTP response; it builds a tablib `Dataset` in memory, though it fetches rows in chunks (`IMPORT_EXPORT_CHUNK_SIZE`, default 100, or `Resource.chunk_size`). Fine for tens of thousands of rows; if volume is much larger, a hand-rolled streaming action or an async job (export to file, notify user) is the established alternative.
- Caveat for streaming: errors mid-stream cannot change the HTTP status, and a flattened wide format needs the full column set up front, which means a first pass over the questions (cheap) before streaming the rows.
- Source: https://django-import-export.readthedocs.io/en/latest/installation.html

## 4. Flattening dynamic form answers

Options:

1. Wide: one row per submission, one column per question. Best for spreadsheet users who want to filter and pivot. Needs a stable column set, so build the column list first from the form definition(s) in scope.
2. Long / tidy: one row per (submission, question, answer). Robust to any question set and to changes over time; suitable for BI tools; awkward for non-technical staff.
3. Both: wide as the default download, long as an optional second file or XLSX sheet.

Practices for wide format:
- Scope an export to one form (or form version); mixed forms in one wide file give sparse, confusing columns. If several forms are in the changelist selection, either require a single form or emit one section/file per form.
- Column key = stable question identifier (pk / slug), not question text; show the text as the header (optionally "text (id)") so renamed or reworded questions do not silently split or merge columns.
- Questions changed over time: take the union of questions across all submissions in scope, order by the form's current position then by id, and leave blank cells where a submission predates a question. Questions removed from the form but with answers in scope still get a column (do not drop data). Duplicate header texts need disambiguation.
- Multi-valued answers (checkboxes): join with a delimiter inside a single cell (e.g. `; `) or one column per option; document which. Use the choice's label, and consider also exporting the raw value.
- Keep the submission metadata columns fixed and first (id, submitted date, user email or "anonymous", status), then question columns.
- Include anonymous submissions explicitly (blank user columns, but the identifying data the applicant typed into the form is in the answers). Make sure queries do not use inner joins on the user.
- Dates/times: ISO 8601 with offset (already done by the project widgets). Numbers and IDs as text where leading zeros matter.
- In django-import-export, dynamic columns are done by overriding `Resource.__init__` / `get_export_headers()` / `export_field` (or by `before_export` building fields) so the field set derives from the queryset; this is a supported but advanced pattern, and the export-form can take extra fields (`ExportForm` subclass) to choose the form to export.

## 5. Encoding (Excel)

- Excel opens UTF-8 CSV correctly only with a BOM (`﻿`); without it, non-ASCII names (very relevant for a South African user base) turn to mojibake. Emit `utf-8-sig` / prepend the BOM. The project's `FormulaSafeCSV` already does this; use `content_type="text/csv; charset=utf-8"`. Note a BOM annoys some non-Excel consumers (they see it in the first header); that trade-off is the accepted default for admin staff users.
- Set a `Content-Disposition: attachment` with a sanitised, timestamped filename (do not put unescaped user input in the filename).
- Newlines inside cells (free-text answers) are handled by `csv` quoting; use `newline=""` conventions where writing to files. Ensure `\r\n` row ends.

## 6. PII, privacy, audit (POPIA / GDPR)

- Principles: data minimisation (export only the columns needed; do not default-include sensitive fields like password hashes, tokens, IP addresses, internal notes), purpose limitation, security of processing (access control + accountability). POPIA section 19 (security safeguards) and GDPR Art. 5(1)(c)/(f), Art. 32 are the relevant hooks; exported files leave the system's controls, so access gating and logging matter more.
- Permission gating: Django admin actions are visible per-model-admin; protect with a dedicated permission (e.g. a custom `export_<model>` permission checked in `has_export_permission` / the action's `allowed_permissions`) rather than reusing `view`. django-import-export supports `IMPORT_EXPORT_EXPORT_PERMISSION_CODE` (default None, meaning anyone who can see the model can export). Grant the permission narrowly (not to all staff).
- Audit logging: record who exported what, when, how many rows, which filters, and which form. Django's `LogEntry` (admin history) can be written with `ADDITION`/custom change message, or use a dedicated model. Do not log the exported content itself. django-import-export has no built-in audit trail for exports. (Note: project convention is "don't add logging unless asked"; this is an audit record the spec should explicitly decide on, not generic logging.)
- Other: set `Cache-Control: no-store` on the download; avoid emailing exports; consider retention guidance for the downloaded file; mention in the spec whether exported data needs to include consent/opt-in flags; exclude users flagged as erased/anonymised appropriately.
- Sources (general): https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection (for file threats); https://django-import-export.readthedocs.io/en/latest/installation.html (permission setting); https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ (admin actions and `allowed_permissions`).

## 7. Respecting changelist filters and search

- Admin actions receive the queryset of the selected rows only; "select all N results" (the across-all-pages link) passes the full filtered queryset including search and list filters, because the changelist builds it. This is the established way: the export is an action on the changelist.
- django-import-export's admin export (the "Export" button on the changelist) applies the current changelist filters and search to the export queryset (`get_export_queryset` uses the `ChangeList` built from the request). Override `get_export_queryset` to add `select_related`/`prefetch_related` and any extra restrictions.
- Always show the user how many rows will be exported, and set a hard cap or warn above a threshold.
- Do not trust a client-supplied list of ids without re-applying the admin's own `get_queryset` (which is where tenant scoping and permission filtering live).

## 8. Multi-tenant isolation

- The export must come from the admin's own `get_queryset(request)` (or the site-aware manager) so only the current site's rows are included. Cross-tenant leakage is the key risk in exports: a superuser or a mis-scoped manager that uses an unfiltered manager (e.g. `all_objects`) would dump other tenants' data.
- Reuse `SiteAwareModelResource` (drops the constant `site` column). Verify that related rows pulled in during flattening (forms, questions, answers, users) are also site-filtered, since `prefetch_related` can bypass a site-aware default manager depending on how relations are resolved.
- Test: create data on two sites; export on site A; assert nothing from site B appears, for both users and applications, and for anonymous applications (which have no user to scope by, so they must be scoped by their own site field).

## 9. django-import-export vs hand-rolled admin actions

django-import-export (already installed and used here):
- Pros: ready-made admin UI (export button, format choice, field selection, filters honoured), `Resource` abstraction with widgets, permission setting, tested, Unfold-compatible via the project's admin mixins (Unfold publishes an import-export integration: https://unfoldadmin.com/docs/integrations/import-export/).
- Cons: in-memory dataset, no HTTP streaming, dynamic columns need overriding the resource, formula escaping is weak by default (the project replaces it with `FormulaSafeCSV`), no audit trail.

Hand-rolled admin action:
- Pros: full control over streaming, column building and audit; simple for a single purpose.
- Cons: you re-implement UI, permission gates, format handling, and escaping; risk of divergence from the existing exporters.

Recommendation for this project (consistent with existing code): use django-import-export with `SiteAwareModelResource` and `FormulaSafeCSV` for Users (static columns). For Applications, use a Resource whose columns are built dynamically from the form's questions (still import-export), and only drop to a streaming hand-rolled path if the expected row counts make the in-memory dataset a problem. Either way, share the escaping helper and the permission/audit hook.

## Checklist for the spec

1. Dedicated export permission; default not granted to all staff.
2. Audit record per export (who, when, rows, filters).
3. Formula escaping on cells AND headers; test the trigger characters.
4. UTF-8 BOM; ISO 8601 dates.
5. Export queryset from admin `get_queryset`, with filters/search honoured and `select_related`/`prefetch_related`.
6. Tenant-isolation tests incl. anonymous applications.
7. Applications: one form per export; stable column ids; union of questions incl. removed ones; blanks for missing; multi-value joining rule; optionally a long-format alternative.
8. Row cap or streaming strategy.
9. Exclude sensitive fields (password, tokens) from the Users export; minimise columns.

## Reference URLs

- https://docs.djangoproject.com/en/stable/howto/outputting-csv/
- https://django-import-export.readthedocs.io/en/latest/installation.html
- https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection
- https://cwe.mitre.org/data/definitions/1236
- https://securelayer7.net/lab/cve-2026-45263-facturascripts-csv-formula-injection-csvexport
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/
- https://unfoldadmin.com/docs/integrations/import-export/

Note on evidence: sections 1-3 and the settings in section 9 are backed by pages fetched in this session (Django CSV howto, django-import-export docs, OWASP/CWE search results). Statements on the changelist-filter behaviour of import-export's `get_export_queryset`, `iterator()`/prefetch behaviour, POPIA/GDPR article references, and the Unfold integration URL come from background knowledge and were not fetched; verify before relying on them in the spec.

status: ok
