---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/cotton/dropdown-menu.html
  - freedom_ls/base/templates/cotton/pagination.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html
  - freedom_ls/educator_interface/templates/educator_interface/interface.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/cohort.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/link.html
  - freedom_ls/panel_framework/templates/cotton/data-table.html
  - freedom_ls/panel_framework/templates/cotton/modal-header.html  # new
  - freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html
  - freedom_ls/panel_framework/templates/cotton/panel-card.html
  - freedom_ls/panel_framework/templates/cotton/panel-definition-list.html
  - freedom_ls/panel_framework/templates/cotton/panel-definition-row.html
  - freedom_ls/panel_framework/templates/cotton/panel-page-header.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/delete_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/read_only.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_nav.html  # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_set_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_denied.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_unavailable.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/panel_toggle.html  # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/quick_view_host.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_sheet.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/quick_view/frame.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_base_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_bulk_confirmation_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_instance_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_list_view_base.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_main_base.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-looks-good

A restyle of the educator interface and the shared panel framework. Every panel interface changes
with it. No models, settings or packages change.

## Breaking changes

- **Modal fragments draw their own header and padding.** `panel_framework/partials/modal_host.html`
  no longer renders the close button or pads its body. A fragment loaded into `#app-modal` must
  start with `<c-modal-header>Title</c-modal-header>`, which renders `<h2 id="app-modal-title">`
  and the Close control, and must pad its own body (the built-in fragments use `px-6 py-4`, with a
  `border-t border-border px-6 py-4` footer row). A downstream action template that still writes a
  bare `<h2 id="app-modal-title">` renders with no close button and no padding. Below `sm` the
  dialog is now a bottom sheet.
- **Page header has its own block, and carries the mobile navigation toggle.**
  `panel_framework/views/_main_base.html` now renders a `page_header` block in a header band above
  the `main` block, which sits on the panel canvas. A downstream view template that extends it and
  draws its heading inside `main` should move the heading into `page_header`. The old
  `pl-2 sm:pl-6` on `#main-content` is gone; both regions pad themselves. The shell no longer draws
  the toggle that opens the navigation sheet below `lg`: a heading rendered through
  `<c-panel-page-header>` must pass `panel_toggle="true"` (as the built-in view templates do), and
  a `page_header` block with other markup must include
  `panel_framework/partials/panel_toggle.html` itself. A template that leaves the block alone gets
  the toggle on its own from the base.
- **Sidebar menu items changed shape.** The dicts built for `sidebar_nav.html` drop `expanded`,
  `instance_label` and `instance_url` and gain `aria_current` (`"page"` on the section list,
  `"true"` on one of its instance pages, `""` otherwise). The sidebar no longer shows the current
  instance as a sub-item, and the `sidebarMenuItem` Alpine component is removed. A shadowed
  `sidebar_nav.html` that reads the old keys must be rewritten.
- **Quick-view link columns.** A `Column` with `quick_view=True` now renders the name as a link to
  the row's page plus an eye-icon trigger beside it that opens the quick view. Before, the whole
  name opened the quick view. The educator interface's learner tables no longer set `quick_view`.
- **`DataTable.page_size` defaults to 10** (was 25). Set `page_size = 25` on a downstream
  `DataTable` subclass to keep the old page length.
- **Instance page headings** use the new `SectionConfigBase.get_instance_label(instance)`
  (default `str(instance)`) for the heading, the back link and the document title, and
  `EditAction` sends the same label back after a save so the heading and the browser tab keep
  their shape. `EditAction` reads the section from the context in `handle_submit()`, so a
  downstream subclass that overrides `handle_submit()` must call `super().handle_submit(ctx)`
  before `form_valid()` runs. Override `get_instance_label` on a section whose model's `str()` is
  not a readable name.
- **Mobile cards mark link columns only.** `Column` gains an `is_link` property (true when
  `url_name` or `url_path_template` is set). The card below `md` ends its primary line with the
  open-page icon only for such a column; a table whose primary column is a text or boolean cell
  no longer shows the icon.
- **The modal keeps its last fragment between opens.** `#app-modal-body` is emptied when the next
  fragment is requested, not when the dialog closes, so the phone bottom sheet slides out with
  its content. A downstream script that read `#app-modal-body` after `close` to find it empty
  should check `#app-modal`'s `open` attribute instead.
- **Educator cohort page.** Edit and Delete moved from `CohortDetailsPanel` to
  `CohortInstanceView.get_actions()`, so they sit in the page header. Learners moved out of
  `CohortDetailsStack` into its own tab on `CohortTabSet`. Downstream subclasses of these classes
  should be checked.
- **first_class theme:** `--color-muted` darkened from `#718096` to `#5F6B7F` to pass 4.5:1
  contrast.

## Manual steps

1. Diff each shadowed template against the paths in `changed_template_paths` and re-apply your
   customisations to the new markup. `_base_interface.html` gains the blocks `shell_class`,
   `grid_class`, `sidebar_body_class`, `main_class`, `content_header`, `content_header_top` and
   `panel_toggle_icon`.
2. Update any custom `#app-modal` fragment to use `<c-modal-header>` and pad its own body (see
   above).
3. Rebuild Tailwind (`npm run tailwind_build`). `tailwind.components.css` adds the `.panel-canvas`
   and `.panel-surface` component classes and the `bottom-sheet` and `bottom-sheet-bare` utilities,
   and the templates use new utility classes. A theme can reopen `.panel-canvas` and
   `.panel-surface` to retune the page canvas and card surface, as `first_class` does.
4. If you set `FREEDOM_LS_ICON_BACKEND` to a custom `IconBackend`, make its `render()` handle the
   new semantic icon names `menu`, `quick_view` and `open_page`. The built-in Heroicons, Lucide,
   Tabler and Phosphor mappings already have them, so the default backend needs nothing.
