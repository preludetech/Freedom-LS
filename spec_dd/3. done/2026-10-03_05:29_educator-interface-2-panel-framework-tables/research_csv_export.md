# Research: the table CSV export hook

For spec 2 (`educator-interface-2-panel-framework-tables`). Read against `idea.md`'s "Export
hook" paragraph, the roadmap's Educator interface rebuild section, and spec 10's "roster CSV"
consumer. Grounded in `freedom_ls/panel_framework/tables.py`, `panels.py`, `views.py`, the current
`cotton/data-table.html` and `cotton/data-table-cells/*.html` in `base` (they move into
`panel_framework` in this spec), and the existing CSV export code in `site_aware_models/admin_exports.py`
and `referral_tracking/tests/test_exports.py`.

**Coordinator decision to build to:** export uses declared export columns. Each column opts in or
out of export explicitly. Export may include columns that are hidden on screen (e.g. email) and
must exclude UI-only columns (row-selection checkboxes, action buttons). The rest of this
document assumes that decision and does not re-argue it.

## What already exists to build on

- `DataTable.get_rows` (`tables.py`) already does search → sort → paginate, in that order, from
  `request.GET`. Spec 2 is adding declared filters to this pipeline. Export needs the same
  search/sort/filter narrowing minus the `Paginator` step, so factor `get_rows` into a
  `get_filtered_queryset(request, columns, queryset)` that both the paginated view and the export
  path call, rather than duplicating the filter logic. This directly gives "what you see is what
  you export, minus pagination": search, sort and declared filters all narrow the exported rows,
  because they narrow the same queryset the page renders from.
- Column dicts already carry a `text_attr` (used by `link.html`) or `attr` (used by `text.html`
  and `boolean.html`), resolved through `getattr_str` in
  `freedom_ls/base/templatetags/data_table_tags.py:6`. `getattr_str(obj, "user.first_name")` is a
  plain Python function (decorated as a template filter, but callable directly) that already does
  dotted-path resolution and calls a result if it is callable. It is the natural accessor to reuse
  from export code — no template engine involved, so no HTML markup, `<a>` tags or icons leak into
  a cell. Columns rendered by a bespoke template with no `attr`/`text_attr` at all (e.g.
  `cohort_courses.html`, `cohort_links.html`, `learner_courses.html` in `educator_interface`) have
  no plain-value accessor today and cannot default into an export; they need one declared
  explicitly if a table wants them exported.
- `DataTablePanel.get_context_data` (`panels.py:207`) is the seam that already builds a table's
  context including `base_url`. The export path hangs off the same panel.
- `panel_framework_view`'s dispatch (`views.py`) resolves a panel and its scope/permission checks
  (`_bind_root`, `check_access`, `has_permission`) once per request, then branches only in
  `_respond` on whether the request is htmx. There is no existing "give me a different
  content-type for the same resolved panel" branch — the export hook is the first one.
- `site_aware_models/admin_exports.py` is the project's only existing hand-written CSV
  hardening: `escape_csv_formula` (leading `=+-@\t\r` gets a leading `'`), a `FormulaSafeCSV`
  wrapper that also prepends a UTF-8 BOM, and ISO 8601 date/datetime widgets. It is built on
  `django-import-export`'s `ModelResource`/`tablib.Dataset`, and it is Django-admin-only —
  `site_aware_models.admin` wires it into `ModelAdmin.resource_classes`. `django-import-export` is
  already a project dependency (`pyproject.toml:39`, `>=4.4.1`), so using it would not add a new
  dependency in the literal sense, but see "which layer owns this" below for why panel_framework
  should not import it.
- `docs/app_structure.md` shows `panel_framework` has **zero runtime dependencies** — it is a leaf
  app every UI app depends on, never the reverse (`panel_framework | — | —` in the dependency
  table). `site_aware_models/admin_exports.py` lives in an app several layers up the graph.
  Importing it from `panel_framework` would be a new, backwards cross-app edge, and the roadmap's
  "no new dependencies" decision already commits the table layer to bespoke code over
  `django-tables2` for exactly this shape of reason ("an FLS-owned template copy, a mixin ban
  enforced by test, and a hard dependency" — `idea.md`). Recommendation: re-derive
  `escape_csv_formula`'s five lines locally in `panel_framework` rather than import
  `site_aware_models`. It is small enough that duplication costs less than the dependency; a
  shared-behaviour test on both copies (or moving the helper down to a place both can reach, if
  one exists) can keep them from drifting silently.

## Streaming vs building in memory

Django's own "Outputting CSV" how-to is the canonical pattern: a `Echo` pseudo-file whose
`write()` returns the string instead of buffering it, fed to `csv.writer`, driving a generator
expression that `StreamingHttpResponse` consumes chunk by chunk
([Django docs, "How to create CSV output"](https://docs.djangoproject.com/en/6.0/howto/outputting-csv/)).
This keeps memory bounded to one row (or one `chunk_size` batch) at a time regardless of how many
rows the export produces, which matters here because organisation size is openly stated as
"hundreds to tens of thousands of rows" and FLS already caps cohort-report generation at
`REPORTS_MAX_LEARNERS` (default 500, `freedom_ls/reports/config.py:82`) for the same reason —
this table export hook is more general than one report and does not have an equivalent cap unless
one is added.

Recommendation: always stream, never build the CSV in memory first. The extra code over an
in-memory `HttpResponse` is small (the `Echo` class plus a generator), and building in memory has
no real advantage at any of FLS's realistic sizes — it only risks an OOM or a very slow
first-byte on the largest organisations. Two caveats worth writing into the spec, not deciding
here:

- A reverse proxy in front of the app (nginx, etc.) with response buffering on will still buffer
  the whole body before forwarding it to the browser, so streaming mainly protects the app
  server's memory and avoids one huge in-process string, not necessarily perceived latency in
  every deployment. It is still correct to build it, because the app-server memory bound is what
  actually matters at FLS's install sizes (self-hosted, not a CDN-fronted SaaS).
- A CSV export is not a request an HTMX-driven partial should try to swap in. The client-side
  invocation must be a plain `<a href="...">` (or a full-page GET), never `hx-get`, so the browser
  treats the response as a download rather than htmx trying to interpret the CSV bytes as an
  HTML fragment. This falls out of the framework's own "every URL a table can push renders a full
  page on a normal GET, with JavaScript off" invariant: the export URL is one more URL that must
  work as a plain GET, and in this case that is also the *only* way it should ever be requested.

On `.iterator()` and prefetch: Django's `QuerySet.iterator(chunk_size=...)` has supported
`prefetch_related()` since Django 4.1, but **only** when `chunk_size` is given explicitly — an
unset `chunk_size` silently drops the prefetch before 5.0 and raises `ValueError` from 5.0 onward
when prefetches are present
([Django docs, `QuerySet.iterator()`](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#iterator)).
This is directly relevant: FLS's existing tables prefetch heavily (`LearnerDataTable` prefetches
`cohortmembership_set` and `learnercourseregistration_set`; `CohortDataTable` prefetches
`course_registrations__course`), and an export of those tables needs the same related data to
render plain-text values for columns like "Cohorts" or "Registered Courses". Any export path
built on `.iterator()` must always pass `chunk_size` explicitly (Django's own default is 2000)
so a table declaring `prefetch_related` keeps working under export instead of silently N+1-ing or
throwing. Whether export bothers with `.iterator()` at all versus a large-but-bounded `.only()`
projection is a call for the spec once the export column set (below) shows how much of the
prefetched data is actually needed per row — a table whose export columns are all direct fields
may not need the prefetches at all for CSV, even though the screen view does.

## CSV / formula injection

OWASP's CSV Injection guidance: a spreadsheet application (Excel, LibreOffice Calc, Google
Sheets) treats a cell as a formula if it opens with `=`, `+`, `-`, `@`, tab (`\t`) or carriage
return (`\r`); the preferred mitigation is prefixing such a cell with a single quote (`'`), which
tells the spreadsheet to read the rest as literal text rather than stripping or rejecting the
character outright
([OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection),
[OWASP WSTG, Testing for CSV Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection)).
This is exactly what `site_aware_models/admin_exports.escape_csv_formula` already does, and it is
worth re-deriving verbatim (same trigger characters, same leading-quote mitigation) rather than
inventing a variant. It matters here specifically because learner and educator names, cohort
names and free-text fields are all user-entered and could start with any of those characters,
by accident (a learner literally named with a hyphen) or on purpose.

The known downside, worth a line in the spec rather than silently accepting: Excel can strip the
leading quote (or other escaping) when a `.csv` is re-saved and reopened, so the mitigation is
not airtight against a determined attacker chaining a re-save — it protects the first open, which
is the realistic threat model for "an educator downloads a roster and opens it," not a durable
guarantee. Do not let that caveat become a reason to skip the mitigation; it is still the accepted
best practice and the project already has precedent for it.

One thing to decide explicitly in the spec, not carried over silently from the admin export:
whether escaping applies to every exported cell or only string-typed ones (the existing
`_escape_cell` only escapes `isinstance(cell, str)`, leaving numbers, dates and booleans alone,
which is correct — a formula trigger can only appear in front of an already-string value).

## Excel compatibility

- **UTF-8 BOM.** Prepending `﻿` to the CSV body (as `FormulaSafeCSV.export_data` already
  does) is the standard workaround for Excel on Windows defaulting to the system codepage instead
  of UTF-8 for CSV without a BOM. Google Sheets and LibreOffice tolerate a BOM fine, so there is no
  compatibility cost to always including it.
- **Line endings.** Python's `csv` module writes `\r\n` by default per RFC 4180; the `Echo`
  pattern's generator should not second-guess that — pass `csv.writer(pseudo_buffer)` and let the
  module handle quoting and line endings, exactly as Django's how-to does. (`csv.writer` also
  answers the "does the CSV quote a field containing a comma" question referenced in the research
  brief — yes, automatically, with no per-cell decision needed in the calling code.)
- **Filename and Content-Disposition.** The idea text says the export URL is "derived from the
  table's URL and key," which argues for the filename following the same shape: table key,
  organisation (or other scope) slug, and a date, e.g.
  `learners-acme-2026-09-26.csv`. A name built only from static strings (key, slug, ISO date) is
  always ASCII, so the plain `filename=` parameter is enough and RFC 6266's `filename*=UTF-8''…`
  extension is not needed *for the filename FLS generates itself*. It would become necessary the
  moment a filename component is allowed to contain arbitrary user text (e.g. an organisation
  *name* rather than its slug, which FLS already treats as the URL-safe identifier) — recommend
  building filenames from slugs and keys, never from display names, so this stays true and RFC
  6266 encoding never has to be implemented. If a future export wants a human-readable name in
  the filename, send both `filename=` (US-ASCII fallback, characters substituted) and
  `filename*=UTF-8''…` per
  [RFC 6266 §4.3](https://www.rfc-editor.org/rfc/rfc6266#section-4.3), because not every browser
  honours `filename*`.

## How cell values are derived — the declared export columns

Reference systems all converge on the same shape: a table's on-screen rendering and its export
values are two different things that happen to often share a name.

- **django-tables2** gives every column a `render_<name>()` for the display value and an optional
  `value_<name>()` for a plain value used by the export/sort paths; `Table.as_values(exclude_columns=...)`
  is what an export view actually iterates, explicitly excluding columns (its own docs use
  selection checkboxes and action columns as the canonical exclusion example) — see
  [Exporting table data](https://django-tables2.readthedocs.io/en/latest/pages/export.html) and
  the `as_values`/`exclude_columns` implementation in
  [`export.py`](https://github.com/jieter/django-tables2/blob/master/django_tables2/export/export.py).
  This is effectively the same shape as the coordinator's decision: opt-in/opt-out per column, a
  distinct value accessor from the render path.
- **django-import-export** (already an FLS dependency) goes further: a `ModelResource`'s
  `Meta.fields` is an entirely independent list from anything an admin's `list_display` shows —
  `SignupAttributionResource` includes `gclid`, `client_ip` and `user_agent`, none of which the
  admin changelist column set shows (`referral_tracking/tests/test_exports.py:118`, "export header
  includes fields the changelist omits"). This is the existing FLS precedent for "export may
  include columns hidden on screen," which the coordinator's decision now extends to the
  panel_framework table layer.
- **Django admin's own `list_display` vs `list_export`-style add-ons** follow the same split for
  the same reason: a column that makes sense to click through to (a name, linking to the detail
  page) is not the same thing as a column that makes sense in a flat file (that name's plain
  text, or an email address nobody would put in a clickable column).

Recommendation for FLS's `DataTable`: add a declaration that is independent of `get_columns()`,
not a flag bolted onto the existing column dicts. A `get_columns()` dict today conflates several
concerns already (`header`, `template`, `attr`/`text_attr`, `sortable`, `url_name`, …) for the
screen; overloading it further with "is this exported, and under what accessor" makes every
screen-only cell template (`cohort_courses.html`, checkboxes, action buttons) carry export
metadata it has no use for, and makes an export-only column (email, hidden on screen) impossible
to express without also rendering it on screen. A separate declaration —
`get_export_columns()` returning a list of `{header, value}` (or `{header, attr}` reusing the same
dotted-path convention `getattr_str` already understands) — gives:

- Explicit opt-in per column: a column is in the export because it is named in this list, not
  because it happened to have an `attr`. `get_columns()`'s selection-checkbox and action-button
  columns are simply never named here, satisfying "excludes UI-only columns" without a special
  "exclude" flag to forget to set.
- Export-only columns for free: email or any other field hidden on screen can appear only in
  `get_export_columns()`, satisfying "can include columns hidden on screen."
  a table that wants a column both on screen and in the export (a learner's name) declares it
  once for each — an on-screen `text.html`/`link.html` column with `attr`/`text_attr`, and an
  export entry with the same dotted path — rather than one dict trying to serve both.
  A small amount of duplication (the same dotted path named twice) is the honest cost of the two
  lists being genuinely independent; it is also exactly what django-import-export's
  `Meta.fields` vs a `ModelAdmin.list_display` already costs FLS today, so it is not a new kind of
  duplication for this codebase.
- A table's export existing or not is then just "did this table override `get_export_columns()`,"
  matching the idea's "a table can declare that it exports" — an empty/absent declaration means no
  export hook is offered for that table, and the export URL 404s or is not linked, rather than
  producing an empty file.
- Value resolution reuses `getattr_str` directly in Python (no template rendering, no HTML, no
  need for a `render_<name>`/`value_<name>` pair the way django-tables2 needs one — FLS's cell
  templates are already thin enough that the plain accessor *is* the value most of the time). A
  column whose value needs computation beyond a dotted path (the multi-course "Registered Courses"
  cell) declares a small callable instead of a string path — e.g. `{"header": ..., "value": lambda
  learner: ", ".join(c.course.title for c in learner.learnercourseregistration_set.all())}` —
  which is the same "class is lighter than forms" judgement call already made for filters
  elsewhere in this idea.

## URL design

The idea's own text: "a stable URL derived from the table's URL and key, honouring the table's
filters and scoping." Two shapes were on the table:

1. **A query-string flag on the table's own URL**: `?<key>-export=csv`, alongside `<key>-sort`,
   `<key>-page`, `<key>-q`, `<key>-<filter>`.
2. **A sibling path**, e.g. `<base_url>/__export`, parallel to the existing `__panels`, `__tabs`,
   `__actions` segments `_resolve_path` already understands (`views.py:302`).

Recommendation: the query-string flag. The whole point of `panel_framework_view`'s dispatch is
that scoping and permission checks (`_bind_root`, `check_access`, `Panel.has_permission`) run once
per resolved panel, before any response is chosen; a sibling path would need its own entry in
`_resolve_path`'s segment-walking `while` loop, which means a second place that has to remember to
run the same checks, and a second thing to keep in sync every time scoping logic changes (spec 5).
A query flag on the *same* URL that already renders the table reuses that resolution unchanged —
the table's own `base_url`, its own `<key>-sort`/`<key>-q`/`<key>-<filter>` state, and the panel's
existing permission check all apply exactly because it is the same resolved panel, just asked to
answer with CSV bytes instead of a rendered fragment. It also means the URL a "download CSV" link
points at is *already* correct for whatever filters and sort the educator currently has applied —
no separate URL-building logic to keep in sync with the table's own link-building. The dispatch
point for this is naturally alongside `_respond`'s existing htmx/full-page/fragment branch
(`views.py:428`): a fourth branch, checked first, for "the query string asks this table panel for
its export."

Search and sort should apply to the export, for the same "what you see is what you export" reason
the idea's declared-filters paragraph implies (filters "survive pagination" — export is one more
thing pagination should not apply to, while everything else that narrows the rows still should).
Concretely: whatever `get_filtered_queryset` produces (search + sort + declared filters, no
`Paginator`) is exactly what the export iterates.

Export as a permission distinct from view is explicitly out of scope for this spec per the idea
("Export as a permission distinct from view … note but defer to spec 5") — worth restating here
only to flag that the query-flag design does not preclude it: spec 5's permission hook can check
an export-specific permission string inside the same panel resolution path (e.g. in
`DataTablePanel.has_permission` or a new hook alongside it) exactly as easily as it could on a
separate route, because nothing about the URL shape forecloses adding a second permission check
gated on the `export` query flag being present.

## Audit

Spec 11 (`educator-interface-11-audit-log`) is the append-only audit log, recorded "by the role
utilities and every action in specs 6 to 9" per the roadmap. A CSV export of learner data leaving
the system is a plausible audit-worthy event — it is exactly the kind of "sensitive data leaving
the system" the idea's permission paragraph already calls out — but spec 2 predates spec 11 and
the roadmap does not list spec 2 among the actions spec 11 records. Recommendation: note this as
an open question for spec 11 to pick up (does an export get an audit entry, and if so what: which
table, which filters were active, how many rows) rather than deciding it here; spec 2 should not
invent an audit call into an app it doesn't depend on (`panel_framework` has zero runtime
dependencies, `docs/app_structure.md`), and spec 11 is better placed to decide the event shape
once it knows what other actions it is already recording.

## Recommendation, summarised

Build the export hook as: a `get_filtered_queryset` factored out of `DataTable.get_rows` so
search, sort and declared filters apply identically to the paginated view and the export, with
pagination the only step export skips. A table opts into export by declaring
`get_export_columns()` — a list independent of `get_columns()`, giving each export column its own
header and value accessor (a dotted path resolved with the same `getattr_str` the screen cells
already use, or a small callable for computed values), so a column can be export-only (email),
screen-only (never named here — checkboxes, action buttons, and any cell template with no plain
value naturally fall out this way with no flag to remember), or both. Serve the export at the
table's own URL with a query flag (`?<key>-export=csv`) rather than a sibling path, so the
existing panel resolution — scoping, permission, per-table query-string state — applies
unchanged and there is exactly one place that checks access to a table's rows. Stream the
response with the `Echo`/`csv.writer`/`StreamingHttpResponse` pattern from Django's own docs,
passing `chunk_size` explicitly to `.iterator()` if a table's export needs its prefetches (Django
4.1+ requirement). Re-derive (not import) the formula-injection escaping and UTF-8 BOM that
`site_aware_models/admin_exports.py` already established for the Django admin, because
`panel_framework` must stay a zero-dependency leaf app; keep the same trigger-character set and
leading-quote mitigation so the project has one consistent CSV-safety convention rather than two
slightly different ones. Build filenames from the table key, a URL-safe scope slug and an ISO
date, never from a free-text display name, so RFC 6266's `filename*` encoding never becomes
necessary for FLS's own generated filenames. Leave export-specific permissions to spec 5 and
whether an export is an audited event to spec 11; the query-flag URL design accommodates either
without changing shape later.

## References

- [Django docs, "How to create CSV output"](https://docs.djangoproject.com/en/6.0/howto/outputting-csv/) — the `Echo`/`StreamingHttpResponse` pattern.
- [Django docs, `QuerySet.iterator()`](https://docs.djangoproject.com/en/6.0/ref/models/querysets/#iterator) — `chunk_size` required for `prefetch_related` to apply.
- [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection)
- [OWASP WSTG, Testing for CSV Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection)
- [RFC 6266, Content-Disposition](https://www.rfc-editor.org/rfc/rfc6266) (§4.3 on `filename*`/`filename` fallback pairing)
- [django-tables2, Exporting table data](https://django-tables2.readthedocs.io/en/latest/pages/export.html) and [`export.py` (`as_values`/`exclude_columns`)](https://github.com/jieter/django-tables2/blob/master/django_tables2/export/export.py)
- In-repo: `freedom_ls/site_aware_models/admin_exports.py`, `freedom_ls/referral_tracking/tests/test_exports.py`, `freedom_ls/base/templatetags/data_table_tags.py`, `freedom_ls/reports/config.py` (`REPORTS_MAX_LEARNERS`), `docs/app_structure.md`.

status: ok
