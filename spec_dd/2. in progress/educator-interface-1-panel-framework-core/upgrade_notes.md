---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/instance_details_panel.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/list_view.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/panel_container.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/instance_actions.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/instance_details_panel.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_view.html  # renamed to panels/_data_table_region_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/main_content.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/panel_container.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/tab_container.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/tab_panels.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_refresh.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-1-panel-framework-core

## Breaking changes

These only affect projects that build their own interfaces on `freedom_ls.panel_framework`, or that override its templates or the educator interface's templates. The URL shape (`__panels/`, `__tabs/`, `__actions/`) has not changed.

**Panel API** (`freedom_ls/panel_framework/panels.py`):

- A panel is now bound per request as `PanelClass(ctx)`, where `ctx` is a `freedom_ls.panel_framework.context.PanelContext` (`request`, `instance`, `base_url`, `name`). The old `Panel(instance)` constructor is gone.
- `get_content()` and the string-returning `render()` are removed. Set `template_name` and override `get_context_data()`, calling `super()` first.
- `DataTablePanel.get_filters()` is removed. Override `get_queryset(self, request)` and narrow `super().get_queryset(request)`.
- `freedom_ls/panel_framework/tabs.py` and its `Tab` dataclass are deleted. Tabs are now the `children` of a `TabSet`. Use `PanelStack` for panels shown one after another. A child's `title` is its tab label.
- `InstanceView.panels` and `InstanceView.tabs` are replaced by a single root `panel` (a `PanelStack` or `TabSet`).
- A panel that sets `model` now needs an instance. `InstanceDetailsPanel` always needs one.
- `InstanceDetailsPanel.fields` entries now use `__` paths through relations (`"user__email"`, not `"user.email"`). Properties and methods also resolve. Labels come from the field's `verbose_name`, not `.title()`.
- New optional hooks: `Panel.has_permission(request)`, `Panel.region_template_name`, and `get_menu_count(request)` and `icon` on section configs.

**Actions** (`freedom_ls/panel_framework/actions.py`): `PanelAction.render(request, context, base_url)` is removed. Actions render through `template_name` and `get_context_data(ctx)`. `handle_submit` now takes `(ctx: PanelContext)` instead of `(request, instance, base_url)`. `has_permission(request, instance)` is unchanged.

**Tables** (`freedom_ls/panel_framework/tables.py`): `DataTable.render()` and `DEFAULT_TABLE_ID` are removed. `DataTable.get_rows(request, columns, queryset)` now takes the queryset instead of `filters`, and `DataTable.get_context(request, queryset, base_url, table_id)` returns the template context.

**Views** (`freedom_ls/panel_framework/views.py`):

- `panel_framework_view(config, ...)` now takes `config: list[NavGroup]` instead of a `dict[str, type[ListViewConfig]]`. Replace the dict with groups, for example `[NavGroup("Teaching", [MyConfig, ...])]`. The framework keys sections by each config's `url_name`, which must be unique across groups, and a duplicate raises `ImproperlyConfigured`.
- `PanelGetter` is removed.
- New section kinds: `ObjectViewConfig` (the instance view of one object) and `BaseViewConfig` (a root panel with no instance).
- The context a host template gets has changed. `content` is gone, and a host now includes the view with `{% include main_template_name with main=main request=request only %}`. The sidebar partial reads `menu_groups` instead of `menu_items`.

**System checks:** `manage.py check` now validates every `Panel` subclass. `freedom_ls_panel_framework.E001` fires for a panel `fields` entry that does not resolve on the panel's `model` (for example, an old dotted path), `E002` for a panel that declares `fields` but no `model`, and `E003` for a `children` value that is not a `Panel` subclass.

**Educator interface:** the cohort course-progress matrix (`CohortCourseProgressPanel`) and its template are deleted. The QA commands `qa_create_cohort_progress`, `qa_create_paginated_progress_matrix`, `qa_create_column_pagination_scenario` and `qa_add_course_items_for_pagination` are deleted too. `/educator/` now lands on a new Dashboard placeholder section.

**htmx history cache is off site-wide.** `_base.html` now sets `<meta name="htmx-config" content='{"historyCacheSize": 0, "historyRestoreAsHxRequest": false}'>`, so Back/Forward re-fetches the page instead of restoring a cached snapshot.

## Manual steps

1. Run `npm run tailwind_build`. The sidebar groups, tab links and sidebar footer use new utility classes, and the new `cohort` icon has to be in the bundle.
2. If your project shadows any template in `changed_template_paths`, compare it with the new version:
   - Overrides of the deleted `panel_framework/partials/*` templates no longer apply. Move the customisation to the matching leaf template, which is the file meant to be overridden: `panel_framework/panels/{panel,panel_stack,tab_set,instance_details,data_table,data_table_region}.html` or `panel_framework/views/{instance_view,list_view,base_view}.html`. Each one only extends its `_base` partner. Overriding `panels/panel.html` reaches every leaf panel.
   - Host templates (your own, or an override of `educator_interface/interface.html`): replace the `main_content.html` include with the `main_template_name` include above. Replace an inline `<div id="scope-announcer">` with `{% include "panel_framework/partials/announcer_host.html" %}`, outside `#main-content`. Pass `menu_groups` to `sidebar_nav.html`.
   - An override of `_base.html` needs the new `htmx-config` meta tag. An override of `_base_interface.html` needs the empty `quick_view_host` and `modal_host` blocks after the `.side-panel-grid` element.
3. If you have your own panels, port them to the API above, then run `uv run manage.py check` and fix any `freedom_ls_panel_framework.E001`–`E003` errors.
4. The icons app has a new semantic name, `cohort`. Add it to `FREEDOM_LS_ICON_OVERRIDES` if you want a different icon than the default (defaults: `user-group` for heroicons, `users` for lucide, tabler and phosphor).

No migrations, settings, or Python or npm package changes.
