---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/page_title.html
  - freedom_ls/base/templates/partials/form.html
  - freedom_ls/educator_interface/templates/educator_interface/_shell.html
  - freedom_ls/panel_framework/templates/
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: extract_panels_framework-4-template-contract

## Breaking changes

- **Panel-framework CSS moved out of `tailwind.components.css`.** `.panel-surface`, `.panel-canvas`,
  `.panel-heading`, `.panel-table-selection-bar` (with `@keyframes selection-bar-in`),
  `.panel-data-table-compact`, `.modal-backdrop-host::backdrop`, the panel form-control min-height
  rule and the `bottom-sheet` / `bottom-sheet-bare` utilities now live in
  `freedom_ls/panel_framework/css/panel_framework.css`. A project whose Tailwind build does not
  import the generated `tailwind.panel_framework.css` loses these rules: educator pages render with
  no canvas or surface colours, no modal scrim and no bottom sheets. See Manual steps 1-3.
- **Panel-framework templates call `c-panel-*` primitives.** Framework templates now use
  `c-panel-button`, `c-panel-button-group`, `c-panel-chip`, `c-panel-callout`, `c-panel-back-link`,
  `c-panel-pagination`, `c-panel-dropdown-menu`, `c-panel-dropdown-menu-separator`, `c-panel-page`,
  `c-panel-date` and `c-panel-datetime`. FLS ships wrappers for all eleven in
  `freedom_ls/base/templates/cotton/` that render the existing `c-button`, `c-chip` and so on, so a
  project that restyled `cotton/button.html` (or any of the others) keeps its look. A project that
  overrides a template under `freedom_ls/panel_framework/templates/` must repoint its calls to the
  `c-panel-*` names, and any `trigger_class="btn …"` on a dropdown menu to `trigger_variant` /
  `trigger_size`.
- **The framework's dropdown is the Alpine component `panelDropdownMenu`**, registered by
  `panel_framework/js/alpine-components.js`. FLS's own `dropdownMenu` is unchanged.
- **`partials/page_title.html` and `partials/form.html` moved into the framework.** Their markup is
  now at `panel_framework/partials/page_title.html` and `panel_framework/partials/form.html`; the FLS
  paths are single includes of those. An override of `partials/page_title.html` no longer affects
  educator pages (the educator shell and htmx navigation responses both include the framework's
  path), and an override of `partials/form.html` no longer affects panel modal forms or reason fields.
- **A data table's row-action buttons stay on one line through `.panel-data-table-actions .btn`**
  in `tailwind.components.css`. A project that overrides `cotton/panel-button.html` to draw button
  classes other than `.btn` must copy that rule, with the data-table and dialog-footer button rules
  beside it, onto its own classes.

## Manual steps

1. Run `uv run manage.py write_panel_framework_css` before every Tailwind build, for example by
   adding it to the npm script that runs before your build (FLS's `_write_active_theme` script now
   runs it after `write_active_theme_css`). It writes `tailwind.panel_framework.css` into `BASE_DIR`
   with machine-specific paths, so it must be regenerated after installing or upgrading FLS.
2. In your Tailwind input CSS, add `@import "./tailwind.panel_framework.css";` after the FLS
   components import and before your active-theme import, so theme overrides of `.panel-surface` and
   `.panel-canvas` still win.
3. Add `tailwind.panel_framework.css` to `.gitignore`.
4. Rebuild Tailwind.
5. If you override `partials/page_title.html` or `partials/form.html`, move the override to
   `panel_framework/partials/page_title.html` or `panel_framework/partials/form.html`.
6. If you override any template under `freedom_ls/panel_framework/templates/`, re-apply your change
   to the new version of that template (see Breaking changes).
7. Run `uv run manage.py check`. Two new checks run at boot:
   - `freedom_ls_panel_framework.E010` (or the warning `W003` when the icon renders empty) fires for
     each icon name in `REQUIRED_ICON_NAMES` (`freedom_ls/panel_framework/checks.py`) that your
     `c-icon` cannot draw. A project using FLS's icon set passes; one with a custom icon set must
     map every listed name.
   - `freedom_ls_panel_framework.E009` fires when `PANEL_REFERENCE_BASE_TEMPLATE` names a template
     that does not exist. The new setting is optional: FLS's `config/settings_base.py` sets it to
     `panel_reference_base.html`, and a project that does not set it gets the framework's
     `panel_framework/minimal_shell.html` for the DEBUG-only component reference page.

`freedom_ls/panel_framework/HOST_CONTRACT.md` describes everything a host page must provide.
