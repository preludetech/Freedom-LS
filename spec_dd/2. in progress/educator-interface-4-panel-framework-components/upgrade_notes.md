---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_instance_details_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_set_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_instance_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_list_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_base_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_refresh.html
  - freedom_ls/panel_framework/templates/panel_framework/navigation_response.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-4-panel-framework-components

## Breaking changes

- **Instance details render a `<dl>`.** `_instance_details_base.html` now renders one
  `<c-panel-definition-list>` with a `<dt>`/`<dd>` pair per field. The stacked mobile `<dl>` and the
  `md:table` `<table>` are both gone. CSS or tests that target the details `<table>`, `<th>` or
  `<td>` need updating.
- **Panels render through `<c-panel-card>` and no longer carry `.surface`.** The `<section>` in
  `_panel_base.html` keeps `data-panel`, the region id and the `hx-*` attributes, but loses
  `class="surface"`. A theme's `.surface` rules no longer reach panels.
- **The card renders the panel heading.** `panel_header` used to hold the `<h2>`. It is now an empty
  hook for content above the body, and the heading comes from the panel's `title` via
  `<c-panel-card>`. An override of `panel_header` that rendered its own title will now show the
  title twice. `panel_actions` still exists and now renders inside the card's `actions` slot.
- **List and base views gain an `h1`.** `_list_view_base.html` and `_base_view_base.html` now open
  with `<c-panel-page-header>` titled from the view's heading. List-view actions move into that
  header, so `partials/list_refresh.html` no longer renders them or takes `actions`/`ctx`; it only
  registers the refresh listeners. `_instance_view_base.html` renders its title and actions through
  the same header, and `#instance-title` keeps its id.
- **The shared `#page-title` region no longer shows the heading.** In `educator_interface/interface.html`
  and `panel_framework/navigation_response.html`, `partials/page_title.html` is included with no
  `page_title`, because the heading now renders inside the view. An override of either template
  that still passes `page_title=heading` will show the heading twice.
- **Default-theme status chips change colour.** In `tailwind.components.css`, `.chip-success`,
  `.chip-warning`, `.chip-error` and `.chip-info` now use `bg-<role>-light text-on-<role>-light`,
  so they clear 4.5:1 contrast. A theme that reopens `.chip-*` keeps its own rules.
- **Tab nav styling.** `_tab_set_base.html` tabs now scroll sideways instead of wrapping. The markup
  and `aria-current="page"` are unchanged.

## Manual steps

1. **Rebuild Tailwind.** Run `npm run tailwind_build` (or your project's equivalent). The new
   `panel-*` components use utility classes your current bundle doesn't have, and the chip rules
   changed.
2. **Re-check shadowed templates.** If your theme shadows any path in `changed_template_paths`,
   diff it against the new FLS version and re-apply your changes. Pay particular attention to
   `panel_header` overrides and anything styled through `.surface`.
3. **Map the five new icon names if you customise icons.** `SEMANTIC_ICON_NAMES` in
   `freedom_ls/icons/semantic_names.py` gains `add`, `search`, `filter`, `trend_up` and
   `trend_down`. All four built-in sets map them. If you use `FREEDOM_LS_ICON_OVERRIDES` or a custom
   `FREEDOM_LS_ICON_BACKEND`, make sure these names resolve there, then run `manage.py check`.
4. **Optional: add the component reference page.** `freedom_ls.panel_framework.urls` (namespace
   `panel_framework`) serves a staff-only page listing every `panel-*` component in every state, at
   `components/`. It is a developer tool. Include it only inside your `if settings.DEBUG:` block, as
   FLS's own `config/urls.py` does:

   ```python
   path("panel-framework/", include("freedom_ls.panel_framework.urls")),
   ```

No migrations, settings, Python packages or npm packages change.

New components, all under `freedom_ls/panel_framework/templates/cotton/`: `panel-applied-filter`,
`panel-attention-list`, `panel-attention-row`, `panel-avatar-chip`, `panel-card`,
`panel-definition-list`, `panel-definition-row`, `panel-empty-state`, `panel-filter-toggle`,
`panel-page-header`, `panel-progress-bar`, `panel-search-field`, `panel-skeleton`, `panel-stat-row`,
`panel-stat-tile`, `panel-status-badge` and `panel-toolbar`. Each file's comment header documents its
attributes. Their names and attributes are public API. A downstream project with its own cotton
component of one of these names will now collide with it.
