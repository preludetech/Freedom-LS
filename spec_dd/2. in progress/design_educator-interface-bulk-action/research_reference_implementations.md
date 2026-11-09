# Research: reference implementations of data-table bulk-action bars

Question: how do established systems solve the bulk-action bar (appears when rows are selected, count, select all, de-select all, Clear on right, text-only actions, overflow "More", modal for confirmation or forms)?

Verification key: [V] = fetched and verified this session; [K] = from prior knowledge of the product, not re-fetched (treat as likely, confirm before citing in a spec).

## Per-system findings

| System | Where the bar appears | Count wording | Select all across pages | Clear / cancel | Button style | Overflow | Confirmation |
|---|---|---|---|---|---|---|---|
| Gmail [K] | Replaces the toolbar above the list; header checkbox becomes a tri-state with a dropdown (All, None, Read, Unread, Starred...) | "1-50 of 240" stays; no separate selected count | Banner above the list: "All 50 conversations on this page are selected. Select all 240 conversations in Inbox" then "Clear selection" | Clear is an inline link in the banner; deselect via header checkbox | Icon-only buttons with tooltips | "More" (three-dot) menu | Mostly none; undo toast ("Conversation archived. Undo"); modal only for destructive/irreversible cases |
| GitHub issues/PR list [K] | Table header row itself changes: the Open/Closed/filter row is replaced by the selection controls | "N selected" | Per-page only; no select-all-across-pages | Deselect via header checkbox | Text dropdown buttons ("Label", "Assignee", "Projects", "Milestone", "Mark as") | Each action is itself a dropdown/popover (inline form-in-popover) | No modal; popover is the form, applied on pick |
| Linear [K] | Floating bar docked at bottom-centre of the viewport, not above the table | "N selected" (with an x to dismiss) | Cmd+A selects all loaded items | x button at the bar edge, Esc clears | Compact buttons, mix of icon and text | Command menu (Cmd+K) holds the rest | None for most actions; undo toast |
| Notion database [K] | Floating contextual toolbar above the selected rows / table | "N selected" | Select-all checkbox in header selects loaded rows | Click away or Esc | Icon and text | "..." menu | Modal only for delete; otherwise undo |
| Airtable [K] | Footer of the grid shows record count; right-click menu on selection for actions | "N records selected" style | Select-all checkbox in header applies to the view | Click away | Context menu rather than a bar | Context menu | Dialog for delete |
| Shopify Polaris IndexTable [K; official page redirected and was not fetched: https://polaris.shopify.com/components/tables/index-table, now https://shopify.dev/docs/api/polaris] | Bar replaces the table header/sticky header when rows are selected, on top of the table | "N selected" next to the header checkbox; "Select all N+" appears when more pages exist (`hasMoreItems`, `paginatedSelectAllActionText`) | Explicit "Select all N+ customers" button, later "Deselect all N+" | "Deselect all" / header checkbox | `promotedBulkActions`: first few shown as buttons (plain/secondary); destructive in critical tone | `bulkActions`: collapsed into a "More actions" disclosure | Modal for destructive actions (Polaris recommends it), otherwise none |
| Atlassian design system [K] | Dynamic table has no built-in bar; Jira issue navigator shows a "Bulk change" wizard (multi-step page) | "N issues selected" | "Select all N issues" in the wizard | Cancel in wizard | Primary Next button | n/a | Final review step is the confirmation (Confirm step before Apply) |
| Material UI DataGrid [V] https://mui.com/x/react-data-grid/row-selection/ | No bar shipped; docs describe no bulk action bar, only controlled `rowSelectionModel` / `apiRef.current.getSelectedRows()` so you build your own (the MUI Table demo "EnhancedTableToolbar" swaps the toolbar for "N selected" plus a delete icon) | Footer shows "N row(s) selected" (default locale text) [K] | Header "Select All" selects every row by default; `checkboxSelectionVisibleOnly` limits to the page; the model switches to an `exclude` (all-except) model internally, which is the key pattern for server-side "all N" | Deselect via header checkbox | Developer's choice | Developer's choice | Developer's choice |
| Carbon data table batch actions [V] https://carbondesignsystem.com/components/data-table/usage/ | Batch action bar appears at the top of the table, replacing the table toolbar; height matches row height | "N items selected" (count text; wording itself not confirmed on page) [K] | Header checkbox with three states (checked, unchecked, indeterminate); no across-pages pattern documented | "Cancel" button on the far right; deselecting all also exits batch mode | Ghost/text-style buttons with icons on a dark (primary-coloured) bar [K] | Overflow for extra table-toolbar actions (up to five before overflow); while batch mode is active, row-level actions and row overflow menus are disabled | Left to the product |
| GOV.UK / Primer [K] | GOV.UK has no bulk-action component (guidance: avoid; use a separate "select then act" page). Primer (GitHub) DataTable has selection but no official bulk bar; GitHub apps build their own | n/a | n/a | n/a | n/a | n/a | GOV.UK prefers a dedicated confirmation page |
| Django admin actions [V] https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ | A bar above the changelist: action dropdown plus "Go" button | "N of M selected" [K] | After ticking the page checkbox a "Select all M objects" link appears; "Clear selection" next to it [K] | "Clear selection" link | A select dropdown and a Go button, not buttons per action | The dropdown is the whole menu | Intermediate confirmation page (e.g. delete selected); docs recommend redirecting to your own view with the ids in the query string |
| Moodle bulk user actions [K] https://docs.moodle.org/en/Bulk_user_actions | Users list at Site admin > Users > Bulk user actions: two lists (available, selected) with an action dropdown beneath | "Selected users (N)" list | "Add all" / "Remove all" buttons, filter first | "Remove all" | Dropdown plus "Go" | Dropdown | Confirmation page for delete ("Are you sure...") |
| Canvas LMS [K] | People page has no bulk bar; bulk is mostly through add/remove dialogs and SIS import; Gradebook uses a menu on the selected column | n/a | n/a | n/a | n/a | n/a | Modal dialogs |

## Convergent pattern

1. The bar appears only once at least one row is selected, and it takes the place of (Carbon, Polaris, Gmail, GitHub) or floats over (Linear, Notion) the normal toolbar/filter row. Placement above the table is the most common.
2. A count of the form "N selected" (Polaris, GitHub, Linear) or "N items selected" (Carbon) is always visible at the left, next to the header checkbox.
3. The header checkbox is tri-state (none / some = indeterminate / all) and is the primary select-all and de-select-all control.
4. When the list is paginated, selecting the page is followed by an explicit second step to extend to everything ("Select all 240" in Gmail, Polaris, Django admin). The count banner states the page scope first, then offers the escalation. The server-side model is "all except these ids" (MUI exclude model).
5. Clear / Cancel is on the far right (Carbon explicitly; Linear x) or an inline link next to the select-all banner (Gmail, Django admin).
6. A few primary actions are shown directly, lightweight (ghost, plain or text, often icon plus label), and the rest collapse into a "More" / "More actions" menu (Polaris, Carbon toolbar, Gmail).
7. Confirmation is graded by risk: reversible actions run immediately with an undo toast (Gmail, Linear, Notion); destructive or irreversible actions get a modal (Polaris guidance, Notion delete) or an intermediate page (Django admin, Moodle, Jira bulk change).
8. Actions that need user input use a popover (GitHub) or a modal/step (Jira) rather than navigating away.

## Notable variations

- Floating bottom bar (Linear) versus in-flow bar above the table (Carbon, Polaris, the FLS idea). The in-flow bar avoids covering rows and works better with long tables and screen magnifiers.
- Dropdown plus "Go" (Django admin, Moodle) versus per-action buttons: older pattern, slower, but scales to many actions.
- Row-level controls disabled in batch mode (Carbon) prevents conflicting single and bulk operations.
- Undo-over-confirm (Gmail, Linear) is only suited to reversible actions; sending messages or enrolling learners is not undoable, so those need a modal.
- Result feedback: Django admin and Gmail use a message/toast after the action; Jira ends on a progress/result page.

## Implications for the FLS spec (suggestions, not decisions)

- The idea's list (count, select all, de-select all, Clear right, text buttons, More dropdown, modal) matches the Carbon + Polaris convergent core.
- Decide explicitly whether select-all means the page or the whole filtered result set, and if the latter, include the Gmail/Polaris style "Select all N" escalation step and an all-except-ids server model.
- Decide a rule for which actions get a modal (irreversible, or needing form input) versus run directly.
- Consider disabling row-level actions while selection is active (Carbon).

## Sources

- https://carbondesignsystem.com/components/data-table/usage/ [fetched]
- https://mui.com/x/react-data-grid/row-selection/ [fetched]
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/ [fetched]
- https://polaris.shopify.com/components/tables/index-table (redirects to https://shopify.dev/docs/api/polaris; not fetched)
- https://docs.moodle.org/en/Bulk_user_actions (not fetched)
- Gmail, GitHub, Linear, Notion, Airtable, Atlassian, Canvas, GOV.UK, Primer: prior knowledge only, no URL fetched this session; verify before quoting.

status: ok · reason: Carbon, MUI and Django admin verified from docs; other systems from prior knowledge and marked as such
