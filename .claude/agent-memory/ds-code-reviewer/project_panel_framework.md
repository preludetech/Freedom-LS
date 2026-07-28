---
name: Panel framework architecture
description: How panel_framework_view dispatches HTMX vs full-page requests, OOB fragment assembly, sidebar/breadcrumb partials, Alpine component patterns
type: project
---

The panel framework centralises all navigation logic in `freedom_ls/panel_framework/views.py`:

- `panel_framework_view` is the main entry point. It resolves paths, dispatches to the right handler, and assembles OOB fragments for HTMX navigation requests (when `HX-Target == "main-content"`).
- `_build_menu_items` generates sidebar data including active state and instance dropdown info.
- `_build_breadcrumbs` generates hierarchy-based breadcrumbs.
- OOB fragments are assembled by rendering `partials/breadcrumbs.html` and `partials/sidebar_nav.html` with `oob=True`.
- Alpine `sidebarMenuItem` component handles expand/collapse animation for instance dropdown.
- The educator interface at `freedom_ls/educator_interface/views.py` passes `root_label="Educator"` and defines `interface_config`.

**Why:** Understanding this architecture is essential for reviewing changes to navigation, sidebar, or breadcrumb behaviour.
**How to apply:** When reviewing panel framework changes, verify OOB fragment assembly, HTMX target discrimination, and Alpine component registration patterns.
