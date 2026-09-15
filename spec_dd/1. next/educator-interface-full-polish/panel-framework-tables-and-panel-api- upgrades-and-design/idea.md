# Debt: panel_framework data tables + Panel API review

> **Consolidated debt spec.** Folds in the former
> `debt-move-datatable-fuctionality-from-base-to-panels-framework` idea, whose whole content
> was: *"Currently the data table component is inside the base app. Move it to the panel
> framework app."* It lives here because the move and the "should the table layer be a
> library?" question would otherwise relocate the same component twice.

Research backing: [package landscape](research_django_crud_package_landscape.md) ·
[panel_framework surface](research_panel_framework_surface.md) ·
[table-library viability](research_tables2_viability.md)

## Framing — what is *not* changing

`panel_framework` stays bespoke. This was checked properly, and the answer should not be
re-opened without new evidence: nothing in the Django ecosystem replaces the
`__panels`/`__tabs`/`__actions` path-traversal dispatcher, the out-of-band navigation bundle
(`views.py:653-726`), or the fail-closed `check_access`/`authorise_instance` contract
(`views.py:187-211`). The nearest packaged alternatives are all pre-1.0 with thin bus factors.
Wagtail's `ObjectList`/`TabbedInterface`/`FieldPanel` is the right **prior art** and the wrong
**dependency** — read it, do not install it.

Two things *are* worth doing, and they are entangled because both touch the table layer.

## Blocked on / coordinate with

`spec_dd/1. next/critical_security_fixes/` should land first, or this spec must absorb one of
its open questions. Its "Questions to resolve when specifying" (idea.md:65-69) asks whether the
object-permission hook belongs in `panel_framework` or in `educator_interface` — the same
surface workstream B redesigns. Doing them independently means either rebasing the security fix
onto an API that did not exist when it was written, or writing it twice.

Two observations for whoever picks that spec up, since it predates the `schools` branch:

- **Its defect 1 reads as substantially addressed here.** `ListViewConfig.get_instance_view`
  now calls `check_access` (`panel_framework/views.py:226`), which has a fail-closed prologue
  and a deny-by-default `authorise_instance` (`:187-211`). `CohortConfig` and `UserConfig`
  both override it (`educator_interface/views.py:819-826`, `:837-844`).
- **Its defect 2 is still open** and now *declared* rather than invisible —
  `CourseConfig.check_access_exempt_reason` plus the `@claude` note at
  `educator_interface/views.py:1107-1118`.

## Workstream A — data tables

### Current state

| Piece | Location | Size |
|---|---|---|
| `DataTable` (queryset, columns, search, sort, paginate) | `freedom_ls/panel_framework/tables.py` | 90 lines |
| Table markup | `freedom_ls/base/templates/cotton/data-table.html` | 181 lines |
| Cell templates | `freedom_ls/base/templates/cotton/data-table-cells/{text,link,boolean}.html` | 3 files |
| `getattr_str` dot-path filter | `freedom_ls/base/templatetags/data_table_tags.py` | 33 lines |

### The folded-in move, and the decision it was missing

Cotton's component namespace is flat — every `<c-name>` resolves to `<COTTON_DIR>/name.html`
with no app prefix — so moving `data-table.html` and `data-table-cells/` from `base` to
`panel_framework` is invisible to every call site and to every theme override path. That makes
it unusually cheap debt.

But **`c-pagination` must stay in `base`.** It is not a table-only component:
`educator_interface/partials/course_progress_panel.html:165` and `:174` use it for two
independent paginators over the cohort progress matrix, which is not a queryset table and never
will be one. Deciding where pagination lives is the prerequisite the one-line debt item did not
contain. Recommendation: `data-table*` moves, `pagination` stays.

Free deletion while in there:
`freedom_ls/educator_interface/templates/educator_interface/partials/list_view.html` is
byte-identical to the `panel_framework` partial and is referenced by nothing.

### The two capability gaps that actually matter

Stated as behaviours, not as a library choice:

1. **Sibling tables on one page share querystring parameters.** `DataTable.get_rows` reads
   `?page`, `?sort`, `?order` and `?search` unprefixed (`tables.py:44-60`), but
   `CourseInstanceView` renders three `DataTablePanel`s flat on one page
   (`educator_interface/views.py:1091-1098`) and the Cohort "details" tab renders two
   (`:746-754`). Under HTMX the collision is masked by the `HX-Target` short-circuit — only the
   targeted panel re-renders. The `href` fallback is genuinely broken: a full-page load of
   `?page=2` applies it to every table on the page. Needs per-table parameter prefixing.
2. **Pagination silently drops unknown query parameters.** `pagination_suffix`
   (`base/templatetags/pagination_tags.py:21-47`) rebuilds the querystring from an allowlist of
   `sort`/`order`/`search`/`extra_params`. Anything else in `request.GET` is lost on a
   pagination click, so *every* future filter would have to be hand-threaded through
   `extra_params` at every call site. This is the single biggest blocker to the filtering work
   below, and the fix is to start from `request.GET` and drop `page`.

Both are small — order-of-20-lines each — and both are prerequisites for the TODO block already
written into the code at `educator_interface/views.py:101-108`: top-level filter dropdowns,
checkboxes and bulk actions, CSV export.

### The library question, deferred to the spec

An earlier pass recommended adopting `django-tables2` + `django-filter`. The viability review
([research](research_tables2_viability.md)) found the constraints eat most of the benefit, so
the spec should make this call with the evidence in front of it rather than inheriting a
recommendation. If it does adopt a library, these are **hard requirements**, not preferences:

- **Library-only mode.** No `INSTALLED_APPS` entry, no `{% render_table %}`, no
  `{% querystring_replace %}`. django-tables2 has no `AppConfig`, so this is achievable — and
  it turns "a settings change in every downstream project" into "a `uv sync`".
- **Keep FLS's own table template.** Tailwind only compiles classes it can see
  (`tailwind.input.css:10-12` scans `freedom_ls/**/templates/` and nothing else), so anything
  rendered from `site-packages` arrives unstyled. This fails *silently*.
- **Keep `<div id="{{ table_id }}">` as the fragment root** (`data-table.html:13`). Every swap
  is `hx-target="#{{ table_id }}" hx-swap="outerHTML"`, and four Playwright tests assert the
  structural invariant that a swap must not nest `<section>` wrappers.
- **Keep `<c-pagination>`** — the progress matrix needs it.
- **Ban `SingleTableView` / `SingleTableMixin` / `MultiTableMixin`**, enforced by a rule in the
  existing `tests/test_security_patterns.py` harness. Those mixins fall back through
  `ListView.get_queryset()` to `Model._default_manager.all()`, which in FLS is site-scoped but
  **not** organisation-scoped.
- **Mandate `template_name=` over `template_code=` on any template column.** Cotton is a
  loader-stage transform, so `<c-…>` tags silently fail to render in `template_code`.

Correcting two claims from the earlier pass, so the spec does not inherit them: tables2's
`CheckBoxColumn` does **not** provide working bulk selection (its own docs say the behaviour is
unimplemented), and export requires the `tablib` extra.

## Workstream B — Panel / Tab / Action API review

Each item below is evidenced in the current code. None of it needs a future consumer to justify
it.

**A live bug, separable and landable on its own.** `DeleteAction.render` raises `TypeError`
unless its second argument is a `Model` (`actions.py:240-243`), but the three call sites pass
three different things: `Panel.render` passes the **Panel** (`panels.py:36`),
`InstanceView._render_instance_actions` passes the **instance** (`views.py:81`), and the list
view passes **`None`** (`views.py:433`). Returning a `DeleteAction` from any `Panel.get_actions()`
is therefore a guaranteed 500. It has never fired only because `DeleteAction` is currently used
solely from `InstanceView.get_actions` (`educator_interface/views.py:756-770`). The base
signature naming that argument `context: object` (`actions.py:28`) is the API admitting it does
not know what it is.

**Panels have no permission check of their own.** `Panel` (`panels.py:15-49`) has no
`has_permission`; only `PanelAction` does (`actions.py:17-20`). Panel visibility is all-or-
nothing per instance, so an "Audit log" or "Personal details" panel cannot narrow itself. This
is the same hook `critical_security_fixes` is asking about.

**`get_filters()` has no `request`** (`panels.py:55-56`), so it structurally cannot do
request-scoping — yet three data tables rely on it as their *only* scope
(`educator_interface/views.py:236`, `:950`, `:1047`). The real invariant today is
`get_queryset(request) ∩ get_filters()` with the split chosen ad hoc per table. Folding both
into one scoping seam would mean exactly one place to get it wrong.

**`get_content() -> str` blocks composition.** `panel_container.html:8` renders
`{{ content|safe }}`, so a downstream can replace a whole panel template but cannot wrap or
extend one. Worse, `views.py:100-102` hand-assembles HTML in Python with manual `escape()`, and
there is a live `# TODO` at `views.py:713-716` against the semgrep
`direct-use-of-httpresponse` finding. A `get_template_name()` + `get_context_data()` contract
addresses both.

**`_resolve_field` reimplements a worse `label_for_field`/`display_for_field`**
(`panels.py:98-114`): `.title()` mangles acronyms (`URL` → `Url`), there is no
`get_FOO_display()` for choices and no empty-value placeholder, and `_meta.get_field()` means a
property, a method, or a queryset annotation raises `FieldDoesNotExist` → 500. Decide
explicitly whether to import from `django.contrib.admin.utils` or vendor the helpers — Wagtail
vendored them rather than couple a distributable framework to `contrib.admin`.

**No bind-to-model validation.** A typo in `InstanceDetailsPanel.fields` surfaces as a
request-time 500. FLS already has the right precedent: `required_settings_errors`
(`base/app_settings.py:62-75`) builds `<app_label>.E001` check messages from declared config.

**Two sources of truth for `panel_name`.** It is threaded positionally through
`render`/`get_content` (`panels.py:26-34`) *and* independently recovered from the URL by string
surgery (`views.py:487-489`). Because every override must repeat the
`(self, request, base_url="", panel_name="")` signature, adding any new render-time context is
a breaking change across every consumer. Wagtail's `bind_to_model` (class-definition time) /
`get_bound_panel` (render time) split is the single most valuable thing to take from the prior
art.

**`Tab` is not a `Panel`** (`tabs.py`, 11 lines), so panels do not compose, a tab set cannot be
reused, tabs have no permission hook, and `_resolve_panels` has to special-case `_ResolvedTab`
(`views.py:262-269`). In Wagtail both `ObjectList` and `TabbedInterface` are `Panel` subclasses
with a `children` list.

**`Panel.__init__` hard-requires an instance** (`panels.py:18`, always constructed as
`panel_class(instance)` at `views.py:27`), so there is no list-level, dashboard, or
instance-free panel.

**The targeted-refresh idiom is copy-pasted three times** — `panels.py:72-75`,
`views.py:421-422`, and `educator_interface/views.py:733` with a hardcoded `"course-progress-content"`
literal. Three copies of one idiom is a missing framework primitive.

### One premise to avoid

Do **not** justify this workstream with `spec_dd/1. next/educator-interface-quick-view-panel/`
as "a second consumer". That idea is a right-hand drawer (`role="region"` on desktop,
`role="dialog"` on mobile) that shares the word "panel" and not the concept — it would consume
at most a panel-content endpoint. A reviewer will check the link and find it does not hold. The
`TypeError` and the semgrep TODO are sufficient justification on their own.

## Desired end state

- No code path exists in which `DeleteAction` raises `TypeError`; a delete button can be
  returned from a `Panel` as well as an `InstanceView`.
- Two sibling tables on one page paginate, sort and search independently under a full page load
  with JavaScript disabled.
- A filter added to a table survives a pagination click without being hand-threaded through
  `extra_params`.
- `grep -rn "HX-Target" freedom_ls/` shows one implementation of the targeted-refresh idiom, not
  three, and no hardcoded target literals in consumer code.
- `views.py:100-102` no longer concatenates HTML in Python, and the `# TODO` at `:713-716`
  is resolved or consciously closed.
- A panel declaring a non-existent field fails at `manage.py check`, not at request time.
- `freedom_ls/base/templates/cotton/data-table*` has moved to `panel_framework`;
  `cotton/pagination.html` has not; the dead `educator_interface/partials/list_view.html` is
  gone.
- `uv run pytest freedom_ls/panel_framework` is green, including the two Playwright modules.

## Out of scope

- The path-traversal dispatcher, the OOB navigation bundle, and the authorisation *model* —
  all three are working as designed and are the reason the framework stays bespoke.
- Adopting neapolitan, django-powercrud, django-crud-views, or Wagtail.
- The quick-view drawer (`educator-interface-quick-view-panel`), which is its own spec.
- The `CourseDataTable` scoping gap and the educator-role gate — those belong to
  `critical_security_fixes`.

## Notes

- **Downstream cost of any new dependency.** FLS ships as a git submodule, so Python deps
  propagate on `uv sync`, but `INSTALLED_APPS` is hand-maintained in each downstream's
  `config/settings_base.py`. Requiring a settings change means `requires_settings_change: true`
  in `upgrade_notes.md` plus an `/fls-dev:update_template_repo` run plus a manual edit in every
  existing downstream. Avoiding it is worth real design effort.
- **FLS has no precedent for optional feature dependencies.** `[project.optional-dependencies]`
  holds only `dev`; all 33 runtime deps are unconditional. The `AppSettings`/`Setting` pattern
  makes *behaviour* pluggable, not *packages* optional.
- Any markup change means `requires_tailwind_rebuild: true`.
- Method and convention references: the `fls-dev:template`, `ds:frontend-styling`,
  `fls-dev:multi-tenant` and `fls-dev:testing` skills.
