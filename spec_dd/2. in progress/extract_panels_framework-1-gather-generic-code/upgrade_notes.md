---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/panel_framework/templates/cotton/modal-footer.html
  - freedom_ls/panel_framework/templates/cotton/modal-header.html
  - freedom_ls/panel_framework/templates/cotton/modal-body.html
  - freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html
  - freedom_ls/panel_framework/templates/cotton/panel-person-link.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/confirm.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/message.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/reason_field.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/lazy_panel.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_lazy_region.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: extract_panels_framework-1-gather-generic-code

Generic dialog, table, action, filter, sweep and Alpine code moved from `educator_interface` into
`panel_framework`, and several framework names changed. No models, migrations, settings or packages
changed.

## Breaking changes

Code that subclasses or calls `panel_framework`:

- **Import only public names.** Every `panel_framework` module declares `__all__`. A host importing
  any other name from it is unsupported, and FLS's own test
  `freedom_ls/panel_framework/tests/invariants/test_public_names.py` fails on one.
- **The action URL is `action_url` everywhere.** In fragment context, `form_url`, `delete_url` and
  `confirm_url` are gone. `form_fragment_context(...)` takes `action_url=` instead of `form_url=`.
  Templates that read `{{ form_url }}`, `{{ delete_url }}` or `{{ confirm_url }}` need renaming.
- **Template attributes end in `_template_name`.** On `DataTable`, `card_template`,
  `row_detail_template` and `empty_state_template` become `card_template_name`,
  `row_detail_template_name` and `empty_state_template_name`. `Column(template=...)` becomes
  `Column(template_name=...)`, and in templates `column.template` becomes `column.template_name`.
- **`PanelAction.template_name` defaults to `None`.** An action with no `template_name` raises
  `ImproperlyConfigured` on GET. Set a `template_name` on any action that renders a fragment.
- **Form action hooks take `ctx`.** `FormPanelAction.form_valid(ctx, form)`,
  `form_invalid(ctx, form)`, `get_form_title(ctx, form)` and `get_empty_message(ctx, form)`, and
  `CreateInstanceAction.get_success_url(ctx, instance)`, replace the `request`-based signatures.
  `FormPanelAction` accepts a plain `forms.Form`. The `refresh_on_change` attribute names the fields
  that re-render the dialog.
- **Modal actions extend `ModalPanelAction`** (or `FormPanelAction`/`ConfirmAction`, which extend it)
  instead of setting `trigger_template_name = "panel_framework/partials/modal_trigger.html"`.
- **Row-scoped actions** set `row_param` and `get_row_queryset(ctx)` and read the row through
  `get_row_object(ctx)`, which returns 404 for a missing, malformed or out-of-scope value.
- **`ReasonMixin`** lives in `freedom_ls.panel_framework.actions`. Its reason field template is
  `panel_framework/partials/reason_field.html` (was `educator_interface/partials/reason_field.html`).
- **Filters:** `ShowInactiveFilter` and `AuditPeriodFilter` are gone. Use
  `freedom_ls.panel_framework.filters.ToggleFilter` and `PeriodFilter`.
- **Alpine:** `listRefresh` and `headerRefresh` are replaced by `eventRefresh`. `sidePanel` and
  `refreshTimer` moved to `panel_framework/static/panel_framework/js/shell-components.js`.

Dialog templates:

- **`<c-modal-footer>` renders its own Cancel.** The `cancel` slot is gone. Delete any
  `<c-slot name="cancel">…</c-slot>`. Set the button with the attributes `cancel` (label, default
  "Cancel"), `cancel_href`, `cancel_click` (the Alpine method, default `cancel`) and `focus_cancel`,
  for example `<c-modal-footer cancel="Close" />` or `<c-modal-footer focus_cancel="true">`.
- **`panel_framework/modal/read_only.html` is removed.** Extend `panel_framework/modal/message.html`
  (blocks `title` and `body`), or include it with `title` and `message`. Return a refusal with
  `freedom_ls.panel_framework.actions.refusal_response(ctx, title=..., message=...)`.
- **Confirm dialogs** extend `panel_framework/modal/confirm.html` and fill `body`, with the action
  a `ConfirmAction`.
- Moved templates: `lazy_panel.html` and `_lazy_region.html` now live in
  `panel_framework/templates/panel_framework/panels/`. `cotton/modal-trigger.html` and
  `cotton/quick-view-trigger.html` moved from `base` to `panel_framework`. An override at the old
  path no longer applies.
- Removed educator templates: the refusal dialogs (`account_already_set_up`,
  `cohort_already_active`, `cohort_inactive`, `learner_already_in_state`,
  `setup_email_recently_sent`, `staff_change_refused`), `delete_cohort_confirmation.html`,
  `panels/cohort_details.html`, `panels/learner_details.html`, `cotton/active-status-badge.html`,
  and several `data-table-cells/` templates now served by framework cells. Overrides of these no
  longer render.

## Manual steps

- If you override `freedom_ls/base/templates/_base.html`, add
  `<script defer src="{% static 'panel_framework/js/shell-components.js' %}"></script>` before
  Alpine, as FLS's own `_base.html` does. Without it, `sidePanel`, `refreshTimer` and
  `eventRefresh` are undefined and the sidebar and refreshing panels break.
- If you run your own housekeeping instead of `fls_run_housekeeping`, schedule the run-record
  sweeps for bulk-action runs from `freedom_ls.panel_framework.housekeeping`:
  `mark_unpicked_runs_failed`, `mark_orphaned_runs_failed` and `delete_finished_records`, or the
  one-call `sweep_run_records`.
- Rebuild Tailwind (`npm run tailwind_build`): the new framework components and
  `tailwind.components.css` add classes.
- Re-apply any overrides of the templates listed in `changed_template_paths` and above, then
  rename attributes and context keys as described under Breaking changes.
