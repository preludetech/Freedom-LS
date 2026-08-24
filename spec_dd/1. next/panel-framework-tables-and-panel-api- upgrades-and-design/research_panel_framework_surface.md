# `panel_framework` surface — what the app actually does, and who consumes it

Inventory taken so the spec author does not have to re-derive it. Line anchors are against the
`schools` branch and will drift; treat them as pointers, not contracts.

Size: ~1,200 lines of source, ~1,300 lines of tests. **One consumer.**

## 1. Concern by concern

### Data tables — `tables.py` (90 lines)

`DataTable` is an abstract classmethod-based renderer:

- `get_queryset(request)` — a `@staticmethod` the consumer implements. This is where
  organisation scoping happens (or doesn't — see §3).
- `get_columns()` — returns a list of plain dicts. Recognised keys: `header`, `template`,
  `attr`, `text_attr`, `sortable`, `sort_field`, `url_name`, `url_path_template`, `htmx_nav`,
  `relation_set`, `link_object_attr`, `link_text_attr`.
- `_prepare_columns()` (`:26-34`) derives `sort_field` from `text_attr`/`attr` by replacing `.`
  with `__`.
- `get_rows()` (`:36-62`) applies `filters`, then `?search=` as an OR of
  `<field>__icontains` across `search_fields`, then `?sort=`/`?order=` validated against the
  declared sortable set, then `Paginator` at `page_size = 5`.
- `render()` (`:64-90`) delegates to `panel_framework/partials/list_view.html`, which is a
  single line: `<c-data-table :columns=… :rows=… :page_obj=… :base_url=… :table_id=… />`.

Presentation lives in `base`: `cotton/data-table.html` (181 lines),
`cotton/data-table-cells/{text,link,boolean}.html`, and the `getattr_str` dot-path filter in
`base/templatetags/data_table_tags.py`.

### Panels — `panels.py` (127 lines)

- `Panel` (`:15-49`) — `title`, `get_actions(request, base_url)`, `get_content(...) -> str`,
  `render(...)` which wraps content and permitted actions in
  `partials/panel_container.html`. Constructed as `Panel(instance)`; no request at
  construction time, hence `request` on every method.
- `DataTablePanel` (`:52-75`) — wraps a `DataTable`, with `get_filters() -> dict` (note: **no
  `request` argument**) and an `HX-Target == f"table-{panel_name}"` short-circuit that returns
  bare content for a targeted refresh.
- `InstanceDetailsPanel` (`:78-127`) — declarative `fields` list supporting dot paths, resolved
  by `_resolve_field` (`:98-114`); optional `editable` + `form_class` adds an `EditAction`.

### Tabs — `tabs.py` (11 lines)

`@dataclass class Tab: label: str; panels: dict[str, type[Panel]]`. That is the whole file.
Only the active tab renders server-side; the rest lazy-load over HTMX
(`views.py:104-160`).

### Actions — `actions.py` (274 lines)

- `PanelAction` — `label`, `variant`, `action_name`, `has_permission(request, instance)`,
  `handle_submit`, `render(request, context, base_url)`.
- `FormPanelAction` — modal form; invalid submissions return **422** with the re-rendered form
  (`:72-87`), matching the project-wide HTMX convention.
- `CreateInstanceAction` — "Save and add another" via `HX-Trigger`, otherwise 204 +
  `HX-Redirect`. Permission from `add_<model>`.
- `EditAction` — 204 + `HX-Trigger: {"panelChanged": {"instanceTitle": …}}`. Bound to an
  instance at construction.
- `DeleteAction` — uses Django's `Collector` to preview cascade deletes (`:225-238`). Bound to
  a `success_url` at construction, **not** an instance.

Permissions go through `user.has_perm(f"{app_label}.{verb}_{model}", instance)` — i.e.
django-guardian object-level permissions.

### URL traversal — `views.py:333-366`

One catch-all view. A path such as
`cohorts/<pk>/__tabs/details/__panels/students/__actions/edit` is walked segment by segment
against a config dict, with `__panels`, `__tabs` and `__actions` as sentinel segments that
change what the next segment means. Helpers: `_resolve_panels`, `_resolve_tabs`,
`_resolve_actions`, and the `_ResolvedTab` / `_ResolvedAction` wrappers.

### App shell — `views.py:597-726`

`panel_framework_view(config, request, path_string, template_name, url_name)`:

- `_build_menu_items` (`:514`) — sidebar with active state and an expanded current-instance
  entry.
- `_build_breadcrumbs` (`:555`) — hierarchy-based; tab names deliberately excluded because the
  tab bar already shows them.
- On `HX-Target == "main-content"`, returns a **hand-assembled OOB bundle** (`:653-726`): main
  content, breadcrumbs, sidebar, page title, `<title>`, an optional ARIA live-region
  announcement (`request.panel_announcement`), and arbitrary host-registered extra fragments
  (`request.panel_extra_oob`). The last of these is how a hosting app injects its own chrome
  without `panel_framework` knowing that app exists.
- Carries a live `# TODO` at `:713-716` against the semgrep
  `python.django.security.audit.xss.direct-use-of-httpresponse` finding.

### Authorisation — `views.py:187-211`

The best-designed part of the app, and the main reason not to replace it:

- `check_access` is the entry point and is documented as not-for-override. Fail-closed
  prologue: no authenticated user, or no `request.organisation`, → `Http404` before any
  subclass code runs.
- `authorise_instance` raises `Http404` unless overridden — a config that forgets to consider
  authorisation cannot serve detail views at all.
- `check_access_exempt_reason` is introspectable, so a test can assert every exemption is
  declared rather than accidental.
- `get_instance_view` (`:213-227`) converts a `ValidationError` from a malformed UUID into a
  404 rather than a 500.

## 2. How `educator_interface` consumes it

`freedom_ls/educator_interface/views.py`, 1,237 lines — the only consumer.

- Three configs: `CohortConfig`, `UserConfig`, `CourseConfig` (`:807`, `:829`, `:1100`),
  assembled into `interface_config` at `:1121`.
- Seven `DataTable` subclasses, four `InstanceView`s, one large bespoke `Panel`
  (`CohortCourseProgressPanel`, `:280-735`) that paginates on two axes and is *not* a queryset
  table.
- `interface()` (`:1148`) is the org-scoping wrapper. It resolves `organisation_slug` from the
  URL, authorises it (404 for both "no such slug" and "no access", deliberately, to prevent
  enumeration), then attaches `organisation`, `panel_url_kwargs`, `accessible_organisations`,
  `path_string`, `panel_extra_oob` and optionally `panel_announcement` to the request.
- `_OrganisationScopedRequest` (`:78-94`) is a typing-only view of that request.
  `panel_framework` never imports it.
- `OrganisationScopeDenied` is caught at `:1202` to soften a cross-organisation switch into an
  informational message rather than a 404.

## 3. Scoping is not uniform — a trap for the next consumer

`get_queryset(request)` is *not* consistently where organisation scoping happens. Three tables
return an unscoped manager and rely entirely on `DataTablePanel.get_filters()` plus the
instance-level `check_access`:

| Table | Line | Queryset | Scoped only by |
|---|---|---|---|
| `CohortCourseRegistrationDataTable` | `:236` | `CohortCourseRegistration.objects…` | `{"cohort": self.instance}` |
| `CourseCohortRegistrationDataTable` | `:950` | `CohortCourseRegistration.objects…` | `{"collection": self.instance}` |
| `CourseInterestDataTable` | `:1047` | `CourseInterest.objects…` | `{"course": self.instance}` |
| `CourseDataTable` | `:851` | `Course.objects.all()` | nothing — declared exempt at `:1107-1118` |

Contrast `CourseStudentRegistrationDataTable` (`:988-999`), which *does* filter on
`organisation=` and carries a comment explaining why.

So the real invariant is `get_queryset(request) ∩ get_filters()`, with the split chosen ad hoc
per table — and `get_filters()` has no `request`, so it structurally *cannot* do
request-scoping. This is a latent trap independent of any table-library decision.

## 4. TODO backlog already written into the code

- `educator_interface/views.py:101-108` — top-level filters (searchable dropdown, HTMX
  reloading one panel), checkboxes and bulk actions (delete, add/remove from cohort), CSV
  export, instance edit, other instance actions such as send-email.
- `panel_framework/views.py:713-716` — the unresolved semgrep `direct-use-of-httpresponse`
  finding on the OOB bundle.
- `educator_interface/views.py:1112-1115` — a `@claude` note that `CourseDataTable` shows every
  course on the site to every logged-in user, deferred to `critical_security_fixes`.

## 5. Test surface that must stay green

`freedom_ls/panel_framework/tests/` — 11 test modules plus `conftest.py`, `urls.py`,
`root_urls.py` and `stub_panels.py`:

`test_breadcrumbs`, `test_check_access`, `test_data_table_panel`, `test_document_title`,
`test_htmx_navigation`, `test_instance_dropdown`, `test_list_view_refresh`, `test_menu_items`,
`test_panel_actions`, `test_panel_tags`, `test_tabs`, plus
`tests/playwright/test_data_table_panel_htmx.py` and
`tests/playwright/test_list_view_refresh_htmx.py`.

The Playwright pair encodes a structural invariant worth knowing before touching the table
render path: an HTMX sort or pagination swap must not nest `<section>` wrappers — there must be
exactly one `[data-panel=…]` and it must contain no nested `section`. That invariant is what
the `HX-Target` short-circuits in `panels.py:69-75` and `views.py:419-422` exist to satisfy.

Also relevant: `freedom_ls/educator_interface/tests/test_config_authorisation.py` asserts every
`ListViewConfig` either authorises or declares an exemption.
