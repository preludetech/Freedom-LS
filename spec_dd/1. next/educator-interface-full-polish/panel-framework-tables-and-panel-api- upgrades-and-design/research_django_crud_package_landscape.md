# Django CRUD / admin-framework package landscape — build vs buy for `panel_framework`

Question asked: is there an open-source Django package that could replace
`freedom_ls/panel_framework/`, or meaningfully reduce it? Surveyed August 2026.

**Answer: no package replaces it. One layer of it (the data table) is commodity, and even that
comes with constraints — see [research_tables2_viability.md](research_tables2_viability.md).**

## 1. What we are shopping for

`panel_framework` bundles seven concerns. Any candidate has to be scored against all of them,
not just "does it do CRUD".

| Concern | Owner in FLS |
|---|---|
| Declarative data tables (columns, search, sort, paginate) | `panel_framework/tables.py` |
| Panels — a titled box with content and its own actions | `panel_framework/panels.py` |
| Tabs with lazy HTMX loading | `panel_framework/tabs.py`, `views.py:104-160` |
| Actions — modal forms, 422 validation, `HX-Trigger`, cascade-delete preview | `panel_framework/actions.py` |
| URL path traversal through a config tree (`__panels`/`__tabs`/`__actions`) | `panel_framework/views.py:333-366` |
| App shell — sidebar, breadcrumbs, OOB fragment bundle | `panel_framework/views.py:597-726` |
| Deny-by-default per-instance authorisation | `panel_framework/views.py:187-211` |

## 2. Closest single package: Wagtail viewsets + panels

`wagtail.admin.viewsets.model.ModelViewSet` gives list/create/edit/delete for a model with
`get_urls()`, an `IndexView` handling columns/search/ordering, breadcrumbs, side panels and
permission policies. `ObjectList` / `TabbedInterface` / `FieldPanel` is *literally* a panel tree
with tabs — both container classes are `Panel` subclasses with a `children` list, so panels
compose and tab sets are reusable values.

Conceptually this is the same design, mature and battle-tested. It is still the wrong
dependency:

- Not distributable as a standalone piece — you inherit the page tree, Wagtail's own admin
  templates and CSS, and its Stimulus frontend, none of which cohabits with FLS's
  Tailwind/cotton/Alpine theme system.
- Not HTMX-based.

**Use as prior art.** The `bind_to_model(model)` (class-definition time) / `get_bound_panel(instance=, request=, form=, prefix=)`
(render time) split is the specific idea worth stealing — it is what FLS's positionally-threaded
`panel_name` argument is a degenerate version of.

Ref: [Wagtail viewsets](https://docs.wagtail.org/en/stable/reference/viewsets.html) ·
[Wagtail generic views](https://docs.wagtail.org/en/stable/extending/generic_views.html)

## 3. HTMX CRUD frameworks — all young, none sufficient

| Package | Stars | Status | Verdict |
|---|---|---|---|
| `neapolitan` | ~705 | Self-declared alpha, CalVer | `CRUDView` + `get_urls()`, deliberately minimal. **No HTMX, no tabs, no panel tree, no nested related tables.** It is the base layer others build on, not a solution. |
| `django-powercrud` | 6 | Pre-1.0, "expect rough edges while APIs settle" | Builds on neapolitan. HTMX modal create/edit/delete, inline row editing, bulk edit/delete with selection persistence, **daisyUI + Tailwind templates** (closest stack match to FLS). But effectively one author, no tabs, no panel tree, no object-level permissions. Renamed successor to `django-nominopolitan`, itself alpha. |
| `django-crud-views` | — | 0.20.0, pre-1.0 | ViewSets, django-tables2 tables, permission-based access, breadcrumbs, crispy-forms, nested parent/child URLs, per-object permission extension. No HTMX story. Explicitly *"not a complete page building system with navigations and lots of widgets."* |
| `django-htmx-viewsets` | — | Dead | One-line viewsets with HTMX + DataTables + Chart.js. Last release **May 2023**. |

Bus factor is the deciding issue. FLS ships into downstream projects; taking a pre-1.0 single-author
dependency for the core of an educator-facing interface is a worse risk than maintaining 1,200
lines.

Refs: [neapolitan](https://github.com/carltongibson/neapolitan) ·
[neapolitan docs](https://noumenal.es/neapolitan/) ·
[django-powercrud](https://github.com/doctor-cornelius/django-powercrud) ·
[powercrud docs](https://doctor-cornelius.github.io/django-powercrud/) ·
[django-nominopolitan](https://doctor-cornelius.github.io/django-nominopolitan/) ·
[django-crud-views](https://django-crud-views.readthedocs.io/en/stable/) ·
[django-htmx-viewsets](https://pypi.org/project/django-htmx-viewsets/)

## 4. Composable pieces — the realistic option

This is where the only genuine value sits, and it maps onto exactly one file
(`panel_framework/tables.py`):

- **django-tables2** — declarative tables, auto-generation from a model, sorting, pagination,
  custom columns via subclassing, `Accessor` dot-path traversal, per-table `prefix`,
  `RequestConfig`, `as_values()`. Production/stable; **3.0.0 released 2026-04-13**, declaring
  Django 5.2 and 6.0 (FLS pins `django>=6.0.4,<6.1`, so compatible). Note 3.0.0 was a breaking
  release — `{% querystring %}` → `{% querystring_replace %}`, `RelatedLinkColumn` removed.
- **django-filter** — ModelForm-style declarative filtering; 26.1 declares Django 5.2/6.0/6.1.
  The standard partner to tables2 and a superset of FLS's hand-rolled `?search=`/`get_filters()`.
- **django-template-partials** and **django-htmx** — the documented companions for the
  fragment-swap pattern FLS already implements by hand.

The `django-tables2 + django-filter + django-template-partials + htmx` combination is a
well-trodden, documented stack for exactly this interaction model.

Refs: [django-tables2 docs](https://django-tables2.readthedocs.io/) ·
[django-tables2 filtering](https://django-tables2.readthedocs.io/en/latest/pages/filtering.html) ·
[Task Badger: Django tables and htmx](https://taskbadger.net/blog/tables.html) ·
[tables2 + filters + partials + htmx gist](https://gist.github.com/RNCTX/872f7d09a0c0177d5f4d59653998f780) ·
[Django Packages: tables grid](https://www.djangopackages.org/grids/g/tables/)

Not applicable: **django-unfold** is already a dependency, but it themes `django.contrib.admin`.
It does nothing for a front-of-house, organisation-scoped educator interface.

## 5. What has no off-the-shelf equivalent

Three things in `panel_framework`, and they are the reason the build-vs-buy answer is "build":

1. **The `__panels` / `__tabs` / `__actions` path-traversal dispatcher.** Every package above
   uses one URL pattern per view. FLS's single catch-all tree walk (Zope/Plone-style traversal,
   if you want a name for it) has no packaged modern-Django equivalent.
2. **The OOB navigation bundle** — main content + breadcrumbs + sidebar + `<title>` + page
   heading + ARIA live-region announcer + host-registered extra fragments, assembled into one
   response. Packages either do full-page loads or swap a single target.
3. **The deny-by-default authorisation contract** — a fail-closed prologue, an
   `authorise_instance` that raises unless overridden, and an introspectable
   `check_access_exempt_reason` so a test can assert every exemption is deliberate. Every
   package listed uses opt-in Django permission strings; none fails closed on a config that
   forgot to consider authorisation.

## 6. Recommendation for FLS

**Keep the framework.** Do not adopt neapolitan, powercrud, crud-views or Wagtail.

**Read Wagtail's panel API as prior art** before the `Panel`/`Tab` API hardens — specifically
the bound-panel split and the fact that container panels are themselves panels.

**Treat the table layer as an open question, not a foregone swap.** django-tables2 is the only
credible candidate and the only one worth costing, but FLS's rendering, HTMX and multi-tenancy
constraints remove much of its value — see
[research_tables2_viability.md](research_tables2_viability.md) before deciding.
