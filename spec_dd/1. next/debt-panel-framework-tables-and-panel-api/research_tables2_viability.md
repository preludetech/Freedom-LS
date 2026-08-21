# Is django-tables2 a viable replacement for `panel_framework/tables.py`?

The obvious recommendation — "swap the 90-line hand-rolled `DataTable` for django-tables2 +
django-filter and delete maintained code" — was stress-tested against FLS's actual rendering,
HTMX, multi-tenancy and distribution constraints.

**Finding: the constraints eat most of the benefit.** A narrow, library-only adoption is
defensible. Adopting tables2's template stack is not. The spec should make the call with this
evidence in front of it.

## 0. Version facts

- **django-tables2 3.0.0**, released 2026-04-13, declares Django 5.2 and 6.0. FLS pins
  `django>=6.0.4,<6.1` — compatible today. 3.0.0 was a **breaking** release:
  `{% querystring %}` → `{% querystring_replace %}`, `RelatedLinkColumn` removed.
- **django-filter 26.1** declares Django 5.2 / 6.0 / 6.1.
- django-tables2 has **no `AppConfig`**. `INSTALLED_APPS` is only needed for templatetag,
  template, locale and static discovery. This fact carries most of the argument in §4.

Refs: [django-tables2 on PyPI](https://pypi.org/project/django-tables2/) ·
[django-tables2 docs](https://django-tables2.readthedocs.io/) ·
[django-filter docs](https://django-filter.readthedocs.io/)

## 1. Rendering — why tables2's own templates cannot be used

tables2 renders via `{% render_table table %}` → `get_template(table.template_name)` →
`django_tables2/table.html`, overridable by the `DJANGO_TABLES2_TEMPLATE` setting,
`Table.Meta.template_name`, or a second argument to `{% render_table %}`.

Theme shadowing itself is *not* the problem. `configure_theme()`
(`freedom_ls/base/theming.py:69-73`) inserts `<theme>/templates/` at `TEMPLATES[0]["DIRS"][0]`,
and the cotton loader starts from `engine.dirs` before appending app template dirs — so
`themes/<slug>/templates/django_tables2/table.html` would correctly shadow the packaged one,
and could even contain cotton components. That part is clean.

Three real collisions, two of them decisive:

**(a) Tailwind does not scan `site-packages`.** `tailwind.input.css:10-12` is the entire source
set:

```
@source "./freedom_ls/**/templates/**/*.html";
@source "./freedom_ls/themes/*/templates/**/*.html";
```

Anything rendered from `.venv/.../django_tables2/templates/` produces classes that were never
compiled. The failure is **silent** — the page renders unstyled rather than erroring. Fixable
by shipping an FLS-owned `panel_framework/templates/django_tables2/table.html`, but that means
"adopt tables2's templates" is off the table from step one. The downstream template repo has
its own hardcoded `@source` globs and inherits the same constraint.

**(b) FLS styles bare elements, so the default template half-works — which is worse than not
working.** `tailwind.components.css:82-105` styles `table`, `thead`, `th`, `td`, `tbody tr` and
`tbody tr:last-child` as `@layer base` element selectors. tables2's `table.html` would
therefore look *almost* right, and then `<ul class="pagination">`, `<li class="active">`,
`BooleanColumn`'s `<span class="true">✔</span>` and `render_attrs table.attrs` would all be
unstyled placeholders — importing a second, competing class vocabulary into a design system
whose skill file says to style only with what is already there.

**(c) Every FLS column becomes a `TemplateColumn` anyway.** This is the decisive point:

- `cotton/data-table-cells/link.html` calls `{% resolve_url_path_template %}`, which merges
  `request.panel_url_kwargs` (the organisation slug segment,
  `panel_framework/templatetags/panel_tags.py:66-68`) and emits
  `hx-get` / `hx-target="#main-content"` / `hx-push-url="true"` / `hx-swap="outerHTML"`.
  `Column(linkify=True)` cannot express any of that — it wants `get_absolute_url()` or a
  `reverse()` spec.
- `cotton/data-table-cells/boolean.html` renders `<c-icon name="boolean_true">`.
  `BooleanColumn` hardcodes `✔`/`✘` in a `<span>`.
- `cohort_links.html`, `user_courses.html`, `cohort_courses.html` are bespoke loops over
  prefetched relations.

So after migration you have seven `Table` subclasses whose columns are essentially all
`TemplateColumn(template_name="cotton/data-table-cells/…")` pointing at the templates you
already have, rendered by an FLS-owned `table.html` you also now maintain. The 90 lines you set
out to delete are replaced by a comparable volume of column declarations plus a table template
plus `RequestConfig` wiring.

**Trap to record if this is adopted:** `TemplateColumn(template_code=…)` compiles via
`django.template.Template(...)`, bypassing the loader. Cotton's `<c-…>` syntax is a
**loader-stage** transform, not a templatetag, so **cotton components silently do not render in
`template_code`** — you get literal `<c-icon>` in the output. Only `template_name=` goes through
`get_template()`. Any spec must mandate `template_name` and ban `template_code`.

## 2. The HTMX contract

The `HX-Target` short-circuits are load-bearing, and tables2 is orthogonal to them — good news,
but only in library-only mode.

Three copies of the idiom exist: `panels.py:72-75` (against `f"table-{panel_name}"`),
`views.py:421-422` (against `DEFAULT_TABLE_ID`, short-circuiting *before* actions so the create
button and modal are not duplicated), and `educator_interface/views.py:733` (a hardcoded
`"course-progress-content"` literal). None of this lives in the table; tables2 neither knows
nor needs to know about it.

What tables2 *would* break:

**(a) Relative-only querystrings.** `querystring_replace` emits a bare `?…` with no path. FLS
needs *two* URLs per control: an `href` (relative, for the no-JS fallback) **and** an
`hx-get="{{ base_url }}?…"` pointing at the panel sub-URL `…/__panels/<name>`, because that is
the only endpoint returning just the table. `base_url` has no home on a `Table` —
`Table.__init__` takes a fixed keyword list with no `**kwargs` — so you would set it
post-construction and read it in the template. Workable, but it makes an FLS-owned table
template mandatory rather than optional.

**(b) The swap root.** Every control in `cotton/data-table.html` is
`hx-target="#{{ table_id }}" hx-swap="outerHTML"` (`:16-20`, `:47-49`, `:56-58`, `:67-69`), and
the fragment root is `<div id="{{ table_id }}">` (`:13`). The Playwright suite asserts the
structural invariant that a swap must not nest `<section>` wrappers
(`tests/playwright/test_data_table_panel_htmx.py:24-30`: exactly one `[data-panel=…]`, zero
nested `section`). tables2's own template wraps in `<div class="table-container">` with no id —
using it verbatim fails all four Playwright tests plus `test_data_table_panel.py` and
`test_list_view_refresh.py`.

**(c) OOB navigation is untouched.** `panel_framework_view` assembles the OOB bundle only when
`HX-Target == "main-content"`; table swaps never reach it. No conflict.

### Two genuine defects tables2 *would* fix

1. **Unprefixed params collide across sibling tables.** `DataTable.get_rows` reads
   `request.GET["page"|"sort"|"order"|"search"]` unconditionally (`tables.py:44-60`), but
   `CourseInstanceView.panels` renders three `DataTablePanel`s on one page
   (`educator_interface/views.py:1091-1098`) and the Cohort "details" tab renders two
   (`:746-754`). HTMX masks it via the short-circuit; the `href` fallback genuinely collides.
   tables2's `Table.prefix` / `prefixed_page_field` / `prefixed_order_by_field` is the
   systematic fix. Note the codebase has already hand-rolled a partial workaround —
   `<c-pagination page_param_name=… extra_params=…>` exists solely for the two-axis progress
   panel.
2. **`pagination_suffix` drops unknown params.** `base/templatetags/pagination_tags.py:21-47`
   rebuilds the querystring from an allowlist of `sort`/`order`/`search`/`extra_params`;
   anything else in `request.GET` is lost on a pagination click. The moment filtering is added
   — the stated motivation for the whole exercise — every filter must be threaded through
   `extra_params` by hand at every call site. `querystring_replace` starts from
   `dict(request.GET)` and is immune. **This is the strongest single technical argument for
   adoption**, and it is also ~15 lines to fix locally by starting from `request.GET` and
   dropping `page`.

## 3. Multi-tenancy and authorisation

A `Table` cannot fail open on its own: `Table.__init__` raises
`TypeError("Argument data … is required")` if not given data, and `Meta.model` only generates
columns, never rows.

The fail-open path is exactly one class: **`SingleTableView` = `SingleTableMixin` + `ListView`**.
`SingleTableMixin.get_table_data()` falls back to `self.get_queryset()`, and
`ListView.get_queryset()` falls back to `self.model._default_manager.all()`. That is a silent
unscoped `Model.objects.all()` reachable by setting one class attribute.

Because FLS models are `SiteAwareModel` with a thread-local site-filtering manager
(`freedom_ls/site_aware_models/models.py:43-50`), such a leak would be **site-scoped but not
organisation-scoped** — precisely the blast radius `critical_security_fixes` describes ("Site
isolation holds… The gap is within a single tenant").

`ListViewConfig.check_access` is untouched by any of this — it runs during `_resolve_path`,
before any table is constructed.

### What a spec would have to mandate

1. **Ban `SingleTableView` / `SingleTableMixin` / `MultiTableMixin`** in prose *and* with a rule
   in the existing repo-wide `tests/test_security_patterns.py` forbidden-pattern harness. Cheap,
   and it is the whole mitigation.
2. **One choke point for data:** `panel_framework` constructs every `Table` itself from
   `cls.get_queryset(request)`; consumers never call `Table(...)`.
3. **Make `get_filters` request-aware**, or better, fold it into a single
   `get_queryset(request, instance)` so there is exactly one place scoping can be got wrong.
   (See `research_panel_framework_surface.md` §3 — this weakness exists today, regardless.)
4. Column-level ordering is already safe on both sides: FLS validates `?sort=` against the
   derived sortable set (`tables.py:53-56`), and tables2's `order_by` setter filters to declared
   columns. No regression, no improvement.
5. If django-filter is adopted: `FilterSet(request.GET, queryset=scoped_qs)` — the `queryset=`
   kwarg is the scoping seam, and a `FilterSet.Meta.model` with no explicit queryset is the
   equivalent fail-open. Same ban-and-grep treatment.

## 4. Downstream distribution cost

FLS ships as a git submodule with `[tool.setuptools.packages.find] include = ["freedom_ls*"]`,
consumed downstream via `uv.sources`.

- **Python deps propagate automatically** on `uv sync`. Low friction; covered by
  `requires_package_upgrade: true` + `changed_packages` in `upgrade_notes.md`.
- **`INSTALLED_APPS` does not.** It is a hand-maintained list in each downstream's
  `config/settings_base.py`. Adding `django_tables2` and `django_filters` means
  `requires_settings_change: true`, an `/fls-dev:update_template_repo` run, and a manual edit in
  every existing downstream.

This is the strongest argument for the **library-only** variant: skip `{% render_table %}` and
`{% querystring_replace %}`, and — because tables2 has no `AppConfig` — there is **no
`INSTALLED_APPS` change at all**. That turns "a settings change for every downstream" into "a
`uv sync`". If adopted, this should be a hard requirement, not a preference.

**No precedent for optional feature deps.** `[project.optional-dependencies]` has exactly one
group, `dev` (tooling only). All 33 runtime deps are unconditional, including narrow ones
(`django_ace`, `encrypted_fields`, `premailer`, `coloraide`). FLS's mechanism for optionality is
`AppSettings`/`Setting` plus swappable dotted paths (`COURSE_ACCESS_BACKEND`) — that makes
*behaviour* pluggable, not *packages* optional. So these become hard deps for everyone,
including downstreams that never open the educator interface.

Also price in **two more packages in the security surface** — the repo runs `pip-audit`,
`bandit`, `detect-secrets` and Dependabot, and tables2 shipped a breaking rename four months ago.

## 5. What is actually left in the credit column

Under the constraints above, adopting django-tables2 buys:

- `Accessor` dot-path traversal (retires `getattr_str`)
- `Table.prefix` / `prefixed_page_field` / `prefixed_order_by_field`
- `RequestConfig` ordering/pagination plumbing
- `Table.as_values()` for export
- a column-class hierarchy

It does **not** buy, contrary to the initial recommendation:

- **Filtering UI** — that is django-filter, a separate dependency with its own form-rendering
  integration to reconcile against `partials/form.html`.
- **Bulk selection.** tables2's own `CheckBoxColumn` docstring: *"You might expect that you
  could select multiple checkboxes in the rendered table and then do something with that. This
  functionality is not implemented. If you want something to actually happen, you will need to
  implement that yourself."*
- **Export** without the `tablib` extra.

And the ledger loses `cotton/pagination.html` (124 lines) from the credit column before it
starts, because `educator_interface/partials/course_progress_panel.html:165,174` uses it for
two paginators over the progress matrix, which can never be a tables2 table.

## 6. Verdict

The two behaviours FLS actually needs — per-table parameter prefixing, and pagination that
preserves unknown query parameters — are roughly 20 lines each locally. tables2 delivers both,
plus `Accessor` and `as_values()`, at the price of a hard dependency, an FLS-owned copy of its
table template, seven rewritten table classes whose columns all point back at the existing cell
templates, and a permanent `SingleTableMixin` ban enforced by a grep test.

**My read is that building the two behaviours locally wins**, and the `base` →
`panel_framework` component move should proceed on its own merits either way. But the spec
should reach that conclusion deliberately, with this evidence, rather than inherit it.
