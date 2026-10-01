---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/modal.html  # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_form.html  # deleted, replaced by panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html  # deleted, replaced by panel_framework/modal/delete_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/_link_to_cohort.html  # deleted
  - freedom_ls/base/templates/cotton/data-table-cells/link.html
  - freedom_ls/base/templates/cotton/dropdown-menu.html
  - freedom_ls/content_engine/templates/cotton/picture.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/panel_framework/templates/cotton/panel-page-header.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_main_base.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-3-panel-framework-dialogs

The panel framework's modals are now one shared native `<dialog id="app-modal">` that loads its
content when it opens. A quick-view drawer (`<dialog id="quick-view">`) is added, and panel refresh
runs on declared domain events instead of the catch-all `panelChanged`. No models, settings or
packages change.

## Breaking changes

**Removed templates and component.** These no longer exist, so a theme or project override of any
of them stops taking effect:

- `cotton/modal.html` (`<c-modal>`) and the `modal` Alpine component in
  `freedom_ls/base/static/base/js/alpine-components.js`. Modals are now the `appModal` component in
  `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`, opened with
  `<c-modal-trigger url="..." label="..." variant="...">`.
- `panel_framework/partials/modal_form.html` → re-create overrides as
  `panel_framework/modal/form.html`.
- `panel_framework/partials/delete_confirmation.html` → re-create overrides as
  `panel_framework/modal/delete_confirmation.html`.
- `educator_interface/data-table-cells/_link_to_cohort.html` (it had no remaining user).

The new fragments are swapped into `#app-modal-body` and carry no `modal_open` flag. Each opens with
`<h2 id="app-modal-title">`, and its close and cancel buttons call `requestClose`. Read the new
templates before porting an override. The `.modal-backdrop` class in `tailwind.components.css`
stays defined but nothing uses it any more.

**Host templates must include the dialog hosts.** A project template that extends
`_base_interface.html` to serve panel-framework pages must fill the two blocks, the way
`educator_interface/interface.html` now does:

```django
{% block quick_view_host %}{% include "panel_framework/partials/quick_view_host.html" %}{% endblock quick_view_host %}
{% block modal_host %}{% include "panel_framework/partials/modal_host.html" %}{% endblock modal_host %}
```

Without `modal_host`, create, edit and delete buttons do nothing.

**`PanelAction` API (`freedom_ls.panel_framework.actions`).**

- `CreateInstanceAction.get_created_event_name()` is removed. Declare
  `success_events = ("yourEventName",)` on the action instead, and override
  `get_success_events(instance)` if the mutation touches other entities.
- The trigger and the fragment are now separate. `{% render_action %}` renders
  `trigger_template_name` from the new `get_trigger_context(ctx)`. `template_name` and
  `get_context_data(ctx)` now build only the modal fragment, rendered on the action URL's GET. A
  custom action that overrode `get_context_data` to change its button must move that override to
  `get_trigger_context`.
- `EditAction(...)` and `DeleteAction(...)` take an optional `success_events` tuple.

**Refresh events replace `panelChanged`.**

- `panelChanged` is gone. `Panel.refresh_events` (default `()`) lists the events that make a panel
  refetch itself, and a panel that declares none no longer refreshes in place. Add
  `refresh_events` to any custom panel that relied on `panelChanged`.
- `ListViewConfig.refresh_events` now drives the list table's refresh, replacing the event names
  collected from `get_created_event_name()`.
- `InstanceDetailsPanel` passes its own `refresh_events` to the `EditAction` it builds as
  `success_events`.
- An edit now sends `instanceTitleChanged` with `{"title": ...}` to update `#instance-title`.
  Custom JS listening for `panelChanged` must listen for that instead.
- Domain events carry `{"ids": ["<pk>", ...]}`. Build the header with
  `freedom_ls.panel_framework.events.build_hx_trigger`.

**Response headers.** No panel action sends `HX-Redirect` any more. After a successful create or a
delete with a `success_url`, the response is a 204 with `HX-Trigger` (including `closeModal`) and
`HX-Location` targeting `#main-content`. A delete with a `success_url` sends no domain events. A
forbidden action URL now raises `PermissionDenied`, so it renders the site's 403 page where it
used to return an empty 403. Update any tests that assert `HX-Redirect`, a bare `HX-Trigger`
string or an empty 403 body.

**`ConstraintValidationFormMixin` errors (`freedom_ls.site_aware_models.forms`).** When exactly one
of a `UniqueConstraint`'s fields is rendered, a violation is now a field error on that field
("Another <model> already has this <field>.") instead of a form-level error naming hidden fields.
With two or more rendered fields it stays form-level, without the hidden field names. Constraints
with their own `violation_error_message` keep it. Update tests that assert the old message or
`non_field_errors()`.

**`#main-content`** in `panel_framework/views/_main_base.html` now has `tabindex="-1"` so focus can
land there after a dialog closes. Keep it in any override.

## Manual steps

1. Search your project and theme for `c-modal`, `modal_open`, `panelChanged`,
   `get_created_event_name`, `HX-Redirect`, `partials/modal_form.html` and
   `partials/delete_confirmation.html`, and port each use as described above.
2. If a project template extends `_base_interface.html` for panel-framework pages, add the
   `quick_view_host` and `modal_host` blocks shown above.
3. Diff each overridden template listed in `changed_template_paths` against the new FLS version
   and re-apply your customisations.
4. Optional: to give your own list views a quick-view drawer, subclass
   `freedom_ls.panel_framework.quick_view.QuickView`, set it as `ListViewConfig.quick_view`, and
   set `quick_view` on the data-table link column. `educator_interface/quick_views.py` is the
   reference.
5. Rebuild Tailwind (`npm run tailwind_build`): the new modal, drawer and quick-view templates use
   utility classes your bundle does not have yet.
