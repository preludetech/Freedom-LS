# Research: seams touched by "report rendered with organisation name/logo"

Codebase survey for the idea-refinement phase. Every claim below is
`path:line` cited against
`/home/sheena/workspace/lms/freedom-ls-worktrees/report-rendered-with-org-name`
at commit `ad626218` (branch `report-rendered-with-org-name`). No web research
was needed for this unit.

## 1. The data path

`gather_cohort_report_data()` is the single assembly point. It already loads
the cohort's organisation and turns it into a plain string:

- `freedom_ls/reports/gather.py:688` — `cohort = load_cohort(cohort_id, site_id)`.
- `freedom_ls/reports/indexes.py:159-165` — `load_cohort()` does
  `Cohort.objects.select_related("organisation").get(pk=cohort_id, site_id=site_id)`,
  so `cohort.organisation` is already prefetched with **no extra query** —
  the organisation row (and therefore `.logo`, `.initials`) is sitting in
  memory the moment `gather_cohort_report_data` runs.
- `freedom_ls/reports/gather.py:739-742` builds the frozen `CohortReportData`:
  ```
  organisation_name=cohort.organisation.name,
  site_name=resolve_site_name(site_id),
  ```
- `freedom_ls/reports/indexes.py:577-586` — `resolve_site_name()` is the one
  *conditional* query in the whole pipeline (`HEADER_TITLE` first, falling
  back to `Site.objects.get(pk=site_id).name`).

**Architectural contracts stated in the module docstrings** (these are the
constraints a "add organisation logo" change must not break):

- `freedom_ls/reports/gather.py:1-10`: *"`freedom_ls.reports.indexes` runs
  every query and returns frozen index bundles; this module turns those
  bundles into the frozen `CohortReportData` tree... and issues no queries of
  its own. The render layer walks that tree and never queries either."*
- `freedom_ls/reports/indexes.py:1-15`: *"This is the only module in the
  report pipeline that queries... Runs from a background task, which has no
  HTTP request, so `SiteAwareManager.get_queryset()` cannot filter by site on
  its own — every query here filters explicitly on `site_id=site_id`."*
- `freedom_ls/reports/report_data.py:1-8`: *"Nothing here touches the ORM...
  Keeping the contract in its own module is what lets the render layer and
  its tests depend on the shape without pulling in the query layer."*
- `freedom_ls/reports/render.py:10-12`: *"No ORM access happens anywhere in
  this module — `build_report_html()` takes the already-gathered
  `CohortReportData` tree and only renders it."*

**Where organisation logo data has to enter the tree, and which contract it
stresses.** The `Organisation` row is already available in `gather.py` (via
`cohort.organisation`), so adding an `organisation_name` string cost nothing
architecturally — it was already loaded. A **logo** is different in kind: it
is not a string, it is a *file*, and it lives in `Organisation.logo`, an
`ImageField` on **arbitrary Django storage** (`freedom_ls/organisations/models.py:31-35`),
not in `STATICFILES_DIRS`. The render layer's only existing mechanism for a
logo — `_resolve_logo()` — resolves a **static path** through
`django.contrib.staticfiles.finders` (`freedom_ls/reports/render.py:162-173`),
which only ever searches app/static and collected static storage. It cannot
resolve a `FieldFile` from `default`/`REPORTS_STORAGE_ALIAS`-style storage.
This is the seam that stresses the "render.py does no ORM, gather issues no
extra queries, only static-file logos exist today" contract — see §2 and the
"Smallest coherent change" sketch below for the two ways to close it.

The cleanest option consistent with the existing architecture: **gather.py
resolves the organisation logo file into bytes (or a storage path/URL) as
part of assembling `CohortReportData`**, since `gather.py` already holds the
`cohort.organisation` instance and is allowed to touch the ORM/storage (it is
the *loader* boundary, not the *renderer* boundary) — `render.py` must
continue to receive something it can hand to WeasyPrint without ORM/storage
access of its own. Precisely what shape that field takes (a `Path`, raw
`bytes`, a `data:` URI, or a resolved absolute file path) is one of the two
architectural decisions flagged at the end of this document — see also §9 on
why "file on local disk" is not a safe assumption in production.

## 2. The render layer

`freedom_ls/reports/render.py` functions and what they must change:

- **`_resolve_logo(static_path)`** (`render.py:162-173`) — today only
  resolves a `STATICFILES_DIRS`-relative path via `_find_static`. Its
  docstring: *"An unset path is not a problem... A path that is set but
  cannot be resolved is a misconfiguration, and raises rather than rendering
  a report with a hole where somebody expected their logo."* That
  "raise on misconfiguration, fall through silently when unset" contract
  should extend to the organisation logo, but the *resolution mechanism*
  (staticfiles finder) cannot be reused as-is for a `FieldFile` on arbitrary
  storage — a new resolver (or a generalisation of this one) is needed, and
  its unset/misconfigured semantics need re-deciding for "org has no logo"
  (not a misconfiguration) vs. "org's logo file is missing from storage"
  (arguably one, but now a *runtime* possibility, not just a settings-time
  one, since deployments delete/move media independent of a deploy).
- **`_build_document(data)`** (`render.py:176-194`) — today resolves exactly
  one logo (`site_config.HEADER_LOGO_STATIC_PATH`) and passes
  `site_logo_url` into the template context. Must be extended to resolve
  the organisation's logo too (and pass both `org_logo_url` and
  `site_logo_url`, or restructure to a primary/secondary pair) and to add
  the resolved path(s) to `allowed_paths` so the URL fetcher permits them
  (`render.py:181-183`).
- **`_restrictive_url_fetcher(allowed_paths)`** (`render.py:203-247`) — its
  docstring is explicit about scope: *"The document does legitimately
  reference a few local files — the configured font faces and, when a
  project sets them, the site and 'powered by' logos... An exact-file
  allowlist rather than a trusted directory, because every file the document
  may read is known before rendering starts. Nothing in the report resolves
  a file path at render time."* Two things to note for the spec: (a) this
  docstring already anticipates a "powered by" mark by name, so the naming
  in this feature ("Powered by <site>") aligns with intent already recorded
  in code; (b) *"Nothing in the report resolves a file path at render time"*
  is a hard constraint the org-logo path must keep — if the logo comes from
  remote storage (S3), it cannot be fetched lazily by the WeasyPrint
  `url_fetcher` at render time from a network URL (that is exactly the SSRF
  surface this function exists to close down) — it must be pulled to a local
  path (or embedded as a `data:` URI) by `_build_document`/`gather.py`
  *before* `render_report_pdf` builds the fetcher and its allowlist.
- **`render_report_pdf(data)`** (`render.py:250-265`) — no logic change
  expected beyond what `_build_document` already funnels through; still the
  single WeasyPrint call site, still catches only `FatalURLFetchingError` and
  re-raises as `ReportRenderError` (`render.py:34-40`, `260-265`).
- **`build_report_html(data)`** (`render.py:197-200`) — unaffected beyond
  whatever `_build_document` returns; used directly by `test_render.py`'s
  pure-Python assertions.
- **`ReportRenderError`** (`render.py:34-41`) — no change; its docstring
  already covers "missing/unresolvable static asset" and "document that
  reached outside its own trusted static assets", both of which the new logo
  resolver must keep raising into.

## 3. Templates & CSS

- `freedom_ls/reports/templates/reports/report.html:38-40` — the
  `.footer-identity` block:
  ```html
  <div class="footer-identity">
    <span class="footer-org">{{ data.site_name }} · {{ data.organisation_name }} · Cohort progress report · {{ data.cohort_name }}</span>
  </div>
  ```
  The surrounding comment (`report.html:30-37`) states the documented
  constraint precisely: *"It must stay a block-level element and it must come
  before the cover — see the note on `.footer-identity` in print.css."* The
  matching CSS note (`print.css:106-116`) explains why: *"Block-level on
  purpose. As an inline element it is wrapped in an anonymous block together
  with the whitespace around it, and that block occupies the first page —
  pushing the full-height cover onto the second and leaving a blank sheet in
  front of the report."* Whatever the new footer text/ordering becomes
  ("Powered by {{ data.site_name }}"), this element must stay `display:
  block` and stay positioned in the DOM before `{% include
  "reports/partials/title_page.html" %}` (`report.html:41`) — moving it after
  the cover include would resurrect the blank-first-page bug this comment
  documents.
- `freedom_ls/reports/templates/reports/partials/title_page.html:7-11` — the
  cover-brand block currently renders the *site* logo/name:
  ```html
  <div class="cover-brand">
    {% if site_logo_url %}<img class="cover-logo" src="{{ site_logo_url }}" alt="">{% endif %}
    <span class="cover-site">{{ data.site_name }}</span>
  </div>
  ```
  This is the block that needs to become organisation-primary; per the
  template's own comment (`title_page.html:1-6`): *"The logo is optional and
  the site name stands alone without one, so it is conditional: a fresh FLS
  install configures no logo, and the page has to read as finished rather
  than as missing a piece."* That same conditional-without-looking-broken
  design has to extend to "organisation configures no logo" (fall back to
  `Organisation.initials`? plain name only? — a product decision, not
  addressed here).
- `title_page.html:49-51` — the bottom band also names the site:
  `<div class="cover-band"><span class="band-site">{{ data.site_name }}</span></div>`.
  This band is a second site-branding surface on the cover distinct from
  `.cover-brand`; the spec needs to decide whether this band becomes the
  organisation too, stays the site (as a subordinate "powered by" style
  mark), or is dropped.
- `title_page.html:36-37` — `data.organisation_name` is *already* printed in
  the `<dl class="cover-meta">` block (`<dt>Organisation</dt><dd>{{
  data.organisation_name }}</dd>`), i.e. the org name is already on the cover
  today, just not as the primary brand mark.
- CSS rules in `freedom_ls/reports/static/reports/print.css` scoped to
  branding:
  - `.footer-identity` (`print.css:106-116`, quoted above) — block-element
    constraint.
  - `.title-page .cover-brand` / `.cover-logo` / `.cover-site`
    (`print.css:489-506`) — right-aligned top brand mark; comment at
    `print.css:489-490`: *"The tenant's own identity, top right per the
    report's design brief. Both parts are optional in the template, so
    neither may reserve space."* — i.e. no fixed-height reservation for a
    logo; an org-logo variant must keep that "no reserved space" property.
  - `.title-page .cover-accent` (`print.css:507-514`) — the accent rule
    sits under "the identity it belongs to" (comment at 511-512), margined
    to align under `.cover-brand`; unaffected by content, only by whether
    `.cover-brand`'s width changes.
  - `.title-page .cover-band` / `.band-site` (`print.css:574-588`) — the
    primary-colour band at the bottom of the cover; currently only ever
    prints the site name.
  - `@page { @bottom-left { content: element(footer-identity); } }`
    (`print.css:56-58`) — the running element that pulls `.footer-identity`
    onto every non-cover page's footer; unaffected by content changes as
    long as `.footer-identity` stays block-level (see above).
  - `@page :first { margin: 0; ... }` (`print.css:75-89`) — the cover page
    has all margin boxes (including `@bottom-left`) suppressed, so the
    footer identity line only ever appears from page 2 onward; relevant
    context for anyone deciding whether "Powered by <site>" should also
    appear on the cover itself.

## 4. Settings

- `freedom_ls/site_aware_models/config.py:6-24` — `HEADER_LOGO_STATIC_PATH`,
  `HEADER_TITLE`, `EMAIL_LOGO_STATIC_PATH` all live here, all `Setting(default=None)`,
  all optional. `HEADER_LOGO_STATIC_PATH` is the setting `_resolve_logo()`
  reads today for the "site" logo on the cover
  (`render.py:181`: `_resolve_logo(site_config.HEADER_LOGO_STATIC_PATH)`).
  This is the natural analogue of, but **not** a candidate for, the "powered
  by" mark: `HEADER_TITLE`/`HEADER_LOGO_STATIC_PATH` already mean "the site's
  own nav-bar branding" project-wide (used outside reports too — see
  `docs/product/configuration-and-extension.md:19-25`), so reusing them
  *is* correct for the demoted "Powered by <site>" mark (no new setting
  needed there) — the site branding settings do not need to move.
- `freedom_ls/reports/config.py:69-101` — `ReportsConfig` (`REPORTS_STORAGE_ALIAS`,
  `REPORTS_MAX_LEARNERS`, `REPORTS_MAX_QUIZ_COLUMNS`, `REPORTS_FONT_FACES`,
  `REPORTS_FONT_DISPLAY/BODY/MONO`) — no logo/branding setting at all today.
  Per `ds:app-settings`/`fls-dev:app-settings`
  (`claude_plugins/django-stack/skills/app-settings/SKILL.md:145-152`, *"Put a
  setting in the lowest-level app that reads it"*), a **new
  `REPORTS_*` setting is not warranted** for the organisation logo, because
  the value is not a project-wide static-path setting at all — it is
  **per-organisation, per-cohort data** (`Organisation.logo`, an uploaded
  `ImageField`), not something a downstream project overrides once in
  `settings.py`. The only setting this feature plausibly needs is a
  fallback/disable toggle (e.g. whether to show the org logo on the report at
  all, or a size/placement knob) — and only if product wants one; there is no
  settings-layer reason to invent one just to carry the logo itself.
- Rules a new setting must follow, from the skills read
  (`claude_plugins/django-stack/skills/app-settings/SKILL.md`,
  `claude_plugins/fls-dev/skills/app-settings/SKILL.md`):
  - Declare it as a class-level annotation with no assigned value in the
    owning app's `config.py`, register it in `declared_settings` as
    `Setting(default=...)` or `Setting(required=True)` (skill lines 45-68).
  - Read it only via `from freedom_ls.reports.config import config; config.NAME`
    — never `settings.NAME` directly, never `getattr` fallback (skill
    lines 89-98).
  - Put it in the **lowest-level app that reads it** (skill lines 147-151) —
    for anything logo-placement-related that would be `freedom_ls.reports`
    (only the report reads it), not `site_aware_models`.
  - If ever `required=True`, it must be enforced by a system check via
    `required_settings_errors()`, never a raise at import
    (skill lines 100-123) — `freedom_ls/reports/checks.py` already exists as
    the place such a check would live (not read in this survey, but present:
    `freedom_ls/reports/checks.py`).
  - `config.py` stays read-only — never mutates other settings or has side
    effects (skill lines 155-158).

## 5. The Organisation model

- `freedom_ls/organisations/models.py:28-39` — `Organisation(SiteAwareModel)`:
  `name`, `slug`, `logo` (`ImageField`, `blank=True`, validated by
  `validate_organisation_logo_extension`/`validate_organisation_logo`), and
  `is_default` — *"Marks the one Organisation a Site falls back to when
  nothing narrower is in scope. Set only by the post_save receiver on Site —
  never exposed in the admin, so the flag cannot be moved to a different
  Organisation."*
- `freedom_ls/organisations/models.py:62-76` — `.initials` property: a
  2-letter (or single-grapheme) monogram derived from `.name`, `None` when
  the name has no alphabetic characters — explicitly *"so the template can
  fall back to a generic icon"* when there is no logo. This is the natural
  fallback for an organisation with no uploaded logo on the cover (mirrors
  `User.initials`, per the docstring).
- `freedom_ls/organisations/utils.py:10-23` — `get_default_organisation(site)`
  reads `Organisation._base_manager.get(site=site, is_default=True)`,
  explicitly *not* the site-aware `objects` manager, because "the latter
  would AND the ambient thread-local site onto the lookup, which is wrong for
  a caller that has already resolved an explicit `site`."
- `freedom_ls/organisations/signals.py:15-42` — every `Site` gets exactly one
  `is_default=True` `Organisation`, seeded from `site.name` at creation time
  but editable afterwards (name/slug/logo can all diverge from the site once
  created) — enforced idempotently on every `Site.save()` and after migrate
  (`signals.py:58-73`).
- `freedom_ls/organisations/models.py:41-57` — DB constraint
  `one_default_organisation_per_site` (partial unique on `site` where
  `is_default=True`) guarantees exactly one default org per site.

**Product edge case: cohort's organisation is the site's default
organisation.** When `cohort.organisation.is_default` is `True`, the report
would show the org's brand (name/logo, possibly identical to what the site
itself would have shown) *and* a "Powered by {{ data.site_name }}" footer —
plausibly duplicative or even contradictory if an admin has since diverged
the default org's name from the site's name (signals.py's docstring notes
"The Site's name is a starting point for the Organisation's, not an identity
for it" — `signals.py:26`). **What data is available to detect this case:**
`gather.py` already holds `cohort.organisation` (an `Organisation` instance)
and could check `cohort.organisation.is_default` directly at
`gather.py:688-741` with no extra query — `is_default` is a plain boolean
field already selected by `select_related("organisation")`
(`indexes.py:162-164`). `CohortReportData` could either carry an
`organisation_is_default: bool` field for the template to branch on, or
`gather.py` could resolve the "powered by" decision itself and hand the
template a single pre-resolved footer string/flag — a template-layer branch
on a raw boolean is more transparent for spec review and testing (matches
how `title_page.html` already branches on `site_logo_url` being falsy).

## 6. How the report is triggered and stored

- `freedom_ls/reports/views.py:109-125` — `download_report_view()`:
  filename is `f"{slugify(report.cohort.name)}-progress-report.pdf"`
  (`views.py:118`) — **cohort-named, not site- or organisation-named**.
  Nothing user-facing currently names the download after the site or the
  organisation. Whether the org name should be folded into the download
  filename (e.g. `{org-slug}-{cohort-slug}-progress-report.pdf`) is a
  product decision the spec should make explicitly — no seam blocks it either
  way, since `report.cohort.organisation` is available via the
  `select_related("cohort")` already on this view's queryset
  (`views.py:111-113`) with one more `select_related("cohort__organisation")` hop.
- `freedom_ls/reports/models.py:24-33` — `report_upload_path()`: *"pk-derived,
  never the cohort name — a cohort name is guessable and enumerable... Nothing
  user-facing reads this name: `download_report_view` names the download
  itself via Content-Disposition."* Confirms the *stored* filename
  (`reports/<uuid>-cohort-report.pdf`) is deliberately identity-blind and
  should stay that way regardless of this feature — only the
  Content-Disposition name is a candidate for change.
- `freedom_ls/reports/admin.py:97-99` — the changelist's `organisation`
  column already reads `obj.cohort.organisation.name` (with
  `list_select_related = ["cohort__organisation", ...]`,
  `admin.py:34`), so the admin UI already exposes organisation identity
  independent of this feature.
- `freedom_ls/reports/models.py:87-95` — `GeneratedReport.__str__` already
  names the organisation: `f"Report for cohort {self.cohort.organisation} / {self.cohort} ({self.status})"`.
- **Stored-artefact / retroactivity note.** `freedom_ls/reports/tasks.py:44-56`
  gathers data and renders the PDF once, synchronously within the task, then
  writes it via `report.file.save(...)` (`tasks.py:54`); nothing re-renders a
  `GeneratedReport` afterwards. `docs/product/reports.md:65` states plainly:
  *"No retention or expiry. A generated PDF is kept until an administrator
  deletes it by hand."* Nothing in the current code assumes a stored report
  can be "refreshed" if the organisation's logo changes later — each
  `GeneratedReport.file` is immutable output from the moment it was rendered.
  This feature does not change that invariant, but the spec should say so
  explicitly: an org that uploads a new logo does **not** retroactively
  change PDFs already generated, only reports generated after the upload.

## 7. Existing tests that will need to change

Grep of `freedom_ls/reports/tests` for `site_name|organisation_name|footer-identity|cover-logo|HEADER_LOGO_STATIC_PATH|band-site|cover-site` hits five files. Concretely:

- **`freedom_ls/reports/tests/test_render.py`**
  - `TestBrandingOnTheCover` (`test_render.py:281-311`) — all four tests
    exercise the *site* logo/name on the cover and will need organisation
    counterparts (or rewriting if the assertions move to organisation-first):
    `test_site_logo_is_omitted_when_no_path_is_configured` (283-287),
    `test_site_logo_is_rendered_when_configured` (289-294),
    `test_configured_but_unresolvable_logo_raises` (296-301),
    `test_site_name_appears_on_the_cover_and_in_the_page_footer` (303-311) —
    the last asserts the exact current footer string
    `"Bright Academy · Northside College · Cohort progress report · Cohort A"`
    (310), which will change format once the footer becomes "Powered by
    <site>".
- **`freedom_ls/reports/tests/report_data_builders.py`**
  - `cohort_report_data()` defaults (`report_data_builders.py:92-108`) has no
    `organisation_is_default` (or equivalent) field — needs one if
    `CohortReportData` grows a field for the default-organisation edge case.
    Also has no logo-bearing field at all today (`organisation_name`/
    `site_name` are the only branding fields); any new
    `CohortReportData` field (e.g. `organisation_logo_url` or similar) needs
    a builder default here too, since both `test_render.py` and
    `test_pdf_integration.py` share this builder
    (`report_data_builders.py:1-8`).
- **`freedom_ls/reports/tests/test_gather.py`**
  - `TestOrganisationName` (`test_gather.py:960-970`) and `TestSiteName`
    (`973-990`) — the pattern to follow for a new
    `TestOrganisationLogo`/`TestOrganisationIsDefault` class: build via
    `CohortFactory(organisation=OrganisationFactory(...))` and assert on the
    resulting `CohortReportData` field, same shape as the existing
    `organisation_name` test.
- **`freedom_ls/reports/tests/test_gather_indexes.py`**
  - `TestResolveSiteName` (`test_gather_indexes.py:525-539`) — asserts
    `resolve_site_name()`'s query-count contract (`django_assert_num_queries`)
    for the `HEADER_TITLE` set/unset branches; a parallel
    `load_cohort`/organisation-logo resolution path, if it issues any new
    query beyond the existing `select_related("organisation")`, needs the
    same query-count discipline this test file enforces throughout (see the
    `load_cohort` query-count expectations implicit in `indexes.py:159-165`'s
    "one query" comment pattern used across this file).
- **`freedom_ls/reports/tests/test_partials.py`**
  - `TestCoverBranding` (`test_partials.py:1255-1276`) — the template-level
    counterpart of `test_render.py`'s branding tests, exercising
    `title_page.html` directly with a hand-built `data`/`site_logo_url`
    context; needs the same organisation-logo counterparts.
- **`freedom_ls/reports/tests/test_pdf_integration.py`** — grep for
  `site_name|organisation_name|logo|footer` returned **no matches**: this
  file currently makes no assertion at all about branding content in the
  rendered PDF bytes (it asserts structure: page orientation, embedded fonts,
  outline, page breaks — see file docstring `test_pdf_integration.py:1-14`).
  If the spec wants a PDF-level assertion that the organisation logo is
  actually embedded/rasterised (not just present in the HTML source before
  WeasyPrint runs), a new test in this file is where it belongs — none
  exists to update, only to add.
- **`freedom_ls/reports/tests/gather_input_builders.py`** — no
  organisation/logo builder function; it currently builds unsaved
  `Topic`/`Form`/`FormProgress`/roster instances only
  (`gather_input_builders.py:57-131`). It is used by
  `test_gather_helpers.py` (pure, no-DB tests of `_completion_counts` etc.)
  — organisation/logo data does not flow through those helpers, so this file
  likely needs **no** new fields unless a new gather-layer pure helper is
  introduced specifically for organisation-branding logic (e.g. an
  "is-default-org, suppress duplicate branding" decision function).

## 8. QA fixtures already in flight

Uncommitted changes (per `git status`) add `--organisation-slug` to both QA
commands, already read above:

- `freedom_ls/qa_helpers/management/commands/qa_create_report_cohort.py:221-239`
  — `_get_organisation(site, slug)`: **lookup-only** (via
  `Organisation._base_manager.filter(slug=slug, site=site).first()`), raises
  `ClickException` listing available slugs if not found — deliberately does
  not auto-create, per its docstring (`qa_create_report_cohort.py:224-227`):
  *"a report cohort belongs to an organisation somebody already set up, and
  silently creating one on a typo would put the fixture where nobody is
  looking for it."*
- `qa_create_report_cohort.py:588-592` — `build_report_cohort()` falls back
  to `get_default_organisation(site)` when no organisation is passed,
  explicitly because *"that is what every fixture built before organisation
  branding existed already assumed"* — confirming this QA work is being done
  specifically in anticipation of this feature.
- `qa_create_report_cohort.py:776-780` — the command's own summary output
  already reports logo presence: `f"Org: {cohort.organisation.name} ({'has logo' if cohort.organisation.logo else 'no logo'})"`.
- `freedom_ls/qa_helpers/management/commands/qa_create_report_fixtures.py:373-403`
  — adds the same `--organisation-slug` option to the fixture-matrix command,
  defaulting to `get_default_organisation(site)`; its summary output also
  reports logo presence (`qa_create_report_fixtures.py:433-438`).
- **Which orgs exist, and which has a logo:**
  - `freedom_ls/qa_helpers/management/commands/qa_create_organisations.py` —
    the smallest seed command. Creates **"RPAS Training"** (**with** a logo,
    attached from `RT-logo.webp` at
    `qa_create_organisations.py:33,58-63`) and **"Northside"** (**no** logo,
    monogram-fallback case, `qa_create_organisations.py:34,65-71`), in
    addition to the site's own default organisation.
  - `freedom_ls/qa_helpers/management/commands/qa_create_organisation_scenarios.py`
    — the fuller scenario builder (superset of the above, per its own
    docstring at `qa_create_organisations.py:3`): `_ensure_logo()`/
    `_clear_logo()` helpers (lines 173-184) are used to give "rpas" a logo
    and explicitly clear it from "northside" and "southgate" (lines
    359-363), and the summary printer reports `logo=yes/no` per org (line
    452).
  - Fixture image: `freedom_ls/organisations/tests/fixtures/RT-logo.webp` —
    referenced by both QA commands above and noted in
    `qa_create_organisation_scenarios.py:77-79` as *"Byte-identical to
    `spec_dd/2. in progress/schools/RT-logo.webp` (same md5)"*, i.e. shared
    with another in-flight spec's fixtures.
  - **Report-cohort fixtures themselves default to the site's default
    organisation** unless `--organisation-slug` is passed
    (`qa_create_report_cohort.py:591-592`,
    `qa_create_report_fixtures.py:400-404`), so none of the eleven QA report
    fixtures in `COHORT_FIXTURES` (`qa_create_report_fixtures.py:164-289`)
    currently sit in "RPAS Training" (the org with a logo) unless a QA
    operator explicitly re-runs the command with
    `--organisation-slug rpas-training-academy` (per the docstring examples
    at `qa_create_report_cohort.py:41-44` and
    `qa_create_report_fixtures.py:24-25`). A logo-bearing report fixture
    does not exist out of the box yet.

## 9. Multi-tenancy rules

From `claude_plugins/fls-dev/skills/multi-tenant/SKILL.md` and
`claude_plugins/fls-dev/resources/multi_tenant.md`:

- `SiteAwareModel`'s default manager (`objects`) auto-filters by the
  thread-local current site (`multi_tenant.md:11-13`), which is populated
  from the request by `CurrentSiteMiddleware` (`multi_tenant.md:9`). A
  background task — which is exactly where report rendering runs
  (`freedom_ls/reports/tasks.py:1-9`, *"Runs from a background task, which
  has no HTTP request"*) — has **no** thread-local site, so `objects` cannot
  be trusted to filter correctly; every query in the reports pipeline
  already filters explicitly on `site_id` for this reason
  (`indexes.py:7-9`, quoted in §1).
- The `Organisation` model follows the same rule, and its own
  `_base_manager` note is the sharpest statement of it in this codebase:
  `organisations/utils.py:18-22` — *"`_base_manager`, not the site-aware
  `objects`: the latter would AND the ambient thread-local site onto the
  lookup, which is wrong for a caller that has already resolved an explicit
  `site`."* **Constraint for this feature:** any *new* Organisation-logo
  lookup added to the report pipeline (e.g. a dedicated
  `load_organisation_logo(organisation_id, site_id)` loader in
  `indexes.py`) must either (a) go through the already-loaded
  `cohort.organisation` instance from `load_cohort()`'s
  `select_related("organisation")` (no new query, no manager-choice
  question at all — the safest option, and what §1/§5 above assume), or (b)
  if a *separate* query is ever needed, filter explicitly on `site_id`
  exactly like every other loader in `indexes.py`, never rely on `objects`'s
  thread-local filtering from inside a task.
- `multi_tenant.md:19-24` also names `SiteAwareModelAdmin` and admin-layer
  site scoping — not directly relevant to render-time logo reading, but
  relevant to `freedom_ls/reports/admin.py`'s existing
  `SiteAwareModelAdmin` base (`admin.py:24`) if the admin UI grows any new
  organisation-logo-related affordance.

## 10. Docs that will need updating

- `docs/product/reports.md:23` — the Cover bullet: *"the cohort, its
  organisation, the courses covered... "* — will need to say the
  organisation's **logo** is now the primary cover brand and the site is
  demoted to a footer "Powered by" mark.
- `docs/product/reports.md:19` — `![](screenshots/cohort_report_cover.png)`
  — the cover screenshot will be stale once the cover's primary brand mark
  changes from site to organisation; same for any other screenshot showing
  the footer running-element text (currently `{{ site_name }} · {{
  organisation_name }} · ...`, §3 above) —
  `docs/product/screenshots/cohort_report_summary_table.png` and
  `cohort_report_quiz_confusions.png` (both listed by the `Glob` for
  `docs/product/screenshots/**report**`) are landscape/inner pages that
  likely still show the page footer running element and so are also
  candidates for re-capture, not just the cover shot.
- `docs/product/configuration-and-extension.md:15-25` — the "Branding" table
  lists `HEADER_LOGO_STATIC_PATH`/`HEADER_TITLE`/etc. as *site*-level
  branding; if this feature adds any new `REPORTS_*` setting (§4), it needs
  a row in the `REPORTS_*` settings-reference table at
  `configuration-and-extension.md:136-142`, and the "Report typography"
  paragraph at `configuration-and-extension.md:37` (*"it names no colour and
  no font family of its own... takes its typefaces from settings"*) should
  gain a sentence about where the logo now comes from (organisation data,
  not a setting) so a downstream integrator does not go looking for a
  `REPORTS_LOGO_STATIC_PATH` setting that will never exist.
- `docs/product/security-and-data-handling.md` — referenced from
  `reports.md:59` for the report's access/privacy posture; not read in this
  survey, but worth a spec-author check: if the organisation logo is pulled
  from remote (e.g. S3) storage at render time (§1/§2), that is a new
  network-fetch-during-render behaviour distinct from today's "no ORM,
  local-static-files-only" render layer, and may be worth a line in that
  doc.

## "Smallest coherent change" sketch

Ordered list of seams to touch, cheapest/most-mechanical first:

1. **`report_data.py`** — add `organisation_is_default: bool` (or a
   pre-resolved `powered_by_line: str | None`, see decision A below) and
   whatever field carries the resolved organisation-logo reference (see
   decision B) to `CohortReportData`. Mechanical: extend one frozen
   dataclass (`report_data.py:221-238`).
2. **`gather.py`** — read `cohort.organisation.is_default` and
   `cohort.organisation.logo` (already in memory via `load_cohort`'s
   `select_related`, `indexes.py:162-164`) at `gather.py:739-741`, resolve
   the logo into whatever form render.py needs (see decision B), populate
   the new `CohortReportData` fields. Mechanical, given decision B is made.
3. **`render.py`** — extend/replace `_resolve_logo`, `_build_document`,
   and the `allowed_paths` set the URL fetcher builds from, to also resolve
   the organisation logo (decision B drives how much new code this is —
   trivial if `gather.py` already hands over a local `Path`/bytes, more
   involved if `render.py` itself has to open the organisation's storage
   backend). Mechanical once B is settled, but B itself is architectural.
4. **`report.html` / `title_page.html` / `print.css`** — swap which
   name/logo is primary on `.cover-brand`/`.cover-band`, rewrite
   `.footer-identity`'s text to lead with "Powered by {{ site_name }}",
   decide the default-organisation-duplication behaviour (decision A) in the
   template via the new `organisation_is_default` field. Mechanical once A
   and the copy are settled by product.
5. **`freedom_ls/reports/config.py`** (only if product wants a
   toggle/size/placement setting — §4 concludes no *new* setting is required
   just to carry the logo itself).
6. **Tests** — extend `report_data_builders.py`'s defaults, add
   organisation-logo/`is_default` cases to `TestOrganisationName`/
   `TestSiteName` (`test_gather.py:960-990`), `TestBrandingOnTheCover`
   (`test_render.py:281-311`), `TestCoverBranding`
   (`test_partials.py:1255-1276`); update the exact footer-string assertion
   at `test_render.py:307-310`.
7. **Docs & QA** — update `docs/product/reports.md`, its screenshots, and
   `configuration-and-extension.md` (§10); optionally point one QA report
   fixture at `rpas-training-academy` (the logo-bearing org) so a
   logo-on-cover screenshot exists to update from (§8 notes none does yet).

### Genuinely architectural decisions (not mechanical)

**Decision A — what happens when the cohort's organisation *is* the site's
default organisation.** (§5.) Does the report suppress the "Powered by
<site>" line entirely in that case, keep it regardless (accepting possible
duplication), or only suppress it when the names/logos are literally
identical? This is a product call with a clean data path already available
(`organisation_is_default`, no extra query) — but it changes the contract of
what `CohortReportData` carries and what the template branches on, and it is
exactly the kind of "reads fine until you hit the single-tenant deployment
that never bothered making a second Organisation" edge case that should be
decided once, explicitly, rather than discovered in QA.

**Decision B — how the organisation logo file reaches WeasyPrint.**
(§1, §2, §9.) `render.py`'s only existing logo path resolves a
`STATICFILES_DIRS`-relative path via `django.contrib.staticfiles.finders`
into a `file://` URI on local disk, and the URL fetcher's allowlist is built
from exact, pre-resolved local `Path`s known before rendering starts
(`render.py:203-235`, quoted in §2) — a deliberate anti-SSRF design ("Nothing
in the report resolves a file path at render time"). `Organisation.logo` is
an `ImageField` on **arbitrary storage** (`freedom_ls/organisations/models.py:31-35`),
which in production may be S3 with private, signed URLs
(`config/settings_prod.py:118-133`), not a local path at all. Three
candidate resolutions, none of them mechanical:
  - **(B1) Pull to a temp local file at gather/render time**, add that temp
    path to the allowlist like any other local file — keeps the existing
    "exact local file allowlist" fetcher design intact, but introduces
    temp-file lifecycle management (cleanup) into a pipeline that currently
    has none, and a network fetch happening inside `gather_cohort_report_data`
    (arguably fine — gather already touches the ORM/storage — but worth
    naming explicitly since gather's docstring only ever talks about "the
    ORM", not storage backends).
  - **(B2) Embed as a `data:` URI** (base64-encode the logo bytes directly
    into the HTML `<img src="data:image/...;base64,...">`), bypassing the
    URL fetcher/allowlist for this asset entirely — simplest and avoids both
    temp files and any file:// trust question, but changes the render
    layer's "every referenced local file is named up front" model
    (`render.py:233-235`) to "some images are inlined, not referenced" and
    needs its own size/format sanity check (the logo is already validated at
    ≤2MiB/4000px on upload, `organisations/validators.py:23-25,75-78`, which
    bounds the inlined payload).
  - **(B3) Generalise `_resolve_logo`/the allowlist to accept a
    storage-backed `FieldFile`** and read its bytes through the storage API
    (`.open()`) rather than the staticfiles finder, still producing a local
    temp path or a `data:` URI under the hood — effectively B1 or B2 with a
    cleaner resolver signature, but is the one that most naturally
    generalises if a future feature wants more storage-backed (not just
    static-path) images in the report.
  All three preserve "no ORM access in render.py" only if the *storage read*
  happens in `gather.py` (or a new helper `gather.py` calls) and `render.py`
  receives an already-resolved value — reading `Organisation.logo` bytes
  from within `render.py` itself would be a first (storage access, not ORM
  access, but still an I/O side channel `render.py`'s docstring does not
  currently admit to). This choice should be made explicitly in the spec,
  not left for implementation to improvise, because it determines whether
  new test infrastructure (temp storage fixtures, `override_settings` for
  `STORAGES`) is needed alongside the existing `requires_tailwind_bundle`-style
  test markers (`freedom_ls/reports/tests/conftest.py`, not read in full
  here but referenced throughout `test_render.py`/`test_pdf_integration.py`).

## Risks / gotchas

- **`.footer-identity` must stay `display: block` and stay before the cover
  include** (§3) — moving it or making it inline reintroduces the
  documented "blank first page" bug (`print.css:106-116`).
- **The URL fetcher's allowlist is exact-file, not directory-trust, by
  design** (`render.py:203-235`) — any implementation of decision B that
  tries to allowlist "the organisations media directory" rather than one
  exact resolved path would contradict this module's stated security model
  and its own test (`test_render.py:258-266`,
  `test_refuses_a_file_outside_the_allowlist`, which specifically checks a
  *sibling* file in an allowed directory is still refused).
- **Production storage may not be local disk at all**
  (`config/settings_prod.py:118-133`, S3 with private signed URLs) — a naive
  "just build a `file://` URI to `organisation.logo.path`" implementation
  will work in dev (`FileSystemStorage`) and silently break (or raise
  `NotImplementedError`, depending on the storage backend's `.path`
  property) in production. This is the single biggest correctness risk in
  the whole feature and should be called out explicitly in the spec's
  acceptance criteria / test plan, not left to be discovered against a real
  S3-backed staging deployment.
- **Stored PDFs are immutable snapshots** (§6) — the spec should state
  explicitly that changing an organisation's logo does not retroactively
  reflow already-generated reports, consistent with the existing "no
  retention/no refresh" model (`docs/product/reports.md:65`).
- **Logo validation already exists and is fairly strict**
  (`organisations/validators.py:21-25`: PNG/JPEG/WebP only, ≤2MiB, 64×32–4000×4000px)
  — useful for bounding decision B2's inline payload size, but also means an
  organisation admin cannot upload an SVG (already blocked, for XSS reasons
  per that file's own docstring, `validators.py:1-9`), which matters if
  anyone assumes vector logos will look crisp on a print-resolution PDF —
  they won't; raster-only.
- **No default-organisation-suppression logic exists anywhere today** — this
  is new product surface, not an existing pattern to copy (decision A has no
  precedent elsewhere in the codebase to point the spec author at).
- **`report_data_builders.py`'s `cohort_report_data()`/`full_report_data()`
  are shared by both `test_render.py` and `test_pdf_integration.py`** (its
  own docstring says so, `report_data_builders.py:1-8`) — any new required
  field on `CohortReportData` must get a sensible default there or every
  existing test in both files breaks at construction time, not just the
  branding-specific ones.

---
status: ok
reason: codebase survey complete; all ten requested areas covered with file:line citations, smallest-coherent-change sketch, and two flagged architectural decisions (default-org duplication handling; organisation-logo delivery mechanism given non-local storage backends)
