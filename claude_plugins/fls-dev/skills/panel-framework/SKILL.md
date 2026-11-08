---
name: panel-framework
description: "How a FreedomLS panel-framework page looks and behaves: list and instance views, data tables, actions and triggers, filters, the quick view, dialogs and sheets, the selection bar, and the invariant tests that enforce each rule. Use when building or changing a panel, table, action, filter, quick view or dialog, and when capturing feedback on how one looks."
allowed-tools: Read, Grep, Glob
---

# Panel framework

`freedom_ls/panel_framework` is the toolkit every educator-facing management page is built from. A
rule about how one of its pages looks or behaves lives here, not in the brand guidelines and not in
a generic plugin: a trigger size, a table footer, a sheet's chrome. `Skill(brand-guidelines)` owns
colour, type and the brand components; `Skill(fls-dev:frontend-styling)` owns the theme tokens.

## What it is

- `panels.py`: a `Panel` subclass is a definition (model, fields, children, template); an instance
  is bound fresh per request from a `PanelContext` and is what renders. `PanelStack`, `TabSet`,
  `DataTablePanel` and `InstanceDetailsPanel` are the shapes.
- `views.py`: `ListViewConfig` (a section's table page, with its quick view) and
  `ObjectViewConfig` / `InstanceView` (one record's page, with its tabs). `StatusBadge` and
  `HeaderStat` feed the page header.
- `tables.py`: `DataTable` and `TableQuery`, each table's own slice of the query string (search,
  sort, page, filters), so two tables on one page never read each other's parameters.
- `actions.py`: `PanelAction` is a button and what submitting it does; `FormPanelAction`,
  `CreateInstanceAction`, `EditAction` and `DeleteAction` build on it. `renders_in_footer` places
  an action in the panel footer or inline; `submit_buttons` names a form's buttons.
- `filters.py`: declared table filters, applied on top of search and sort, in `PanelAction`'s shape.
- `quick_view.py`: `QuickView` feeds the drawer one row of a list opens.
- `bulk_actions.py`: row selection and the action that runs once over the selected rows.

Components live in `freedom_ls/panel_framework/templates/cotton/`: `data-table`,
`data-table-actions`, `data-table-cells/{text,link,datetime}`, `modal-header`, `modal-footer` and the
`panel-*` set (`panel-page-header`, `panel-toolbar`, `panel-search-field`, `panel-filter-toggle`,
`panel-applied-filter`, `panel-empty-state`, `panel-person-link`, `panel-avatar-chip`,
`panel-attention-list`, `panel-attention-row`, `panel-stat-row`, `panel-stat-tile`,
`panel-status-badge`, `panel-definition-list`, `panel-definition-row`, `panel-card`,
`panel-progress-bar`, `panel-skeleton`). The page chrome is in
`templates/panel_framework/partials/`: `table_toolbar`, `table_footer`, `table_selection_bar`,
`table_sheet`, `table_empty`, `quick_view_host`, `modal_host`, `sidebar_nav`, `breadcrumbs`.
`ls freedom_ls/panel_framework/templates/cotton/` is the current list.

## How it looks and behaves

### Triggers and buttons

- Every action trigger the framework renders is `size="small"`: `{% render_action %}`,
  `<c-modal-trigger>`, the page header, a panel footer, an empty state, the selection bar, a table
  row, a card. The one full-size pair is `<c-modal-footer>`'s Cancel and confirm, because that is
  the decision the dialog asks for.
- Buttons in a table cell or a card sit inside `<c-data-table-actions>`, which owns the gap; the
  buttons carry no margins. Per-item buttons come first and the row's own action (Deactivate staff
  member) last, at the bottom of the cell.
- Two buttons in one row never share a bare verb: "Deactivate role" beside "Deactivate staff
  member", never beside "Deactivate".

### Controls are components

Every anchor under `freedom_ls/panel_framework/templates/` and
`freedom_ls/educator_interface/templates/` is a control. The base layer underlines every `<a>`, and
that underline means "a link inside prose", which these templates never hold. A control takes the
component for its job: a person gets `<c-panel-person-link>` (avatar and name, the one way a learner
or staff member is linked from a row, a card, an attention list or a dialog), a back link
`<c-back-link>`, a text action ("Edit", "Change", "Clear all") `<c-button variant="link">`, and a
clickable row, a sort header or a filter choice the row-link style (`no-underline text-on-surface`,
or `text-muted` for a secondary one). An anchor whose class list names neither `no-underline` nor
`btn` has been forgotten.

### Page header

`<c-panel-page-header>` states each fact once. Its `badge` slot carries a state only when it differs
from the default (Inactive, Pending); stats stay out when the tabs already count them; no action
sits in the header, each lives with the thing it changes. A list page opens with its heading and
its toolbar, so the list starts at the top; help lives in a dialog the page opens, or in the docs.

### Tables

- The footer states the entry count at the left, in line with the pager, on a single-page table
  too ("12 learners", "Showing 1–10 of 80 learners"). It renders from `entry_count`, so a table
  never writes its own.
- An empty table shows `<c-panel-empty-state>` inside the data table's empty row, which carries
  `hover:bg-transparent` so the empty state takes no row hover.
- A log or History table sorts on `created_at`, `actor_label`, `action` and `target_label` and
  filters on who, what and when (`AuditActorFilter`, `AuditActionFilter`, `AuditPeriodFilter`),
  on the organisation Audit log and on every History tab alike.
- A person in a list row is `<c-panel-attention-row>`: the name `text-sm font-semibold`, the chip
  `size="sm"` with its centre on the name's first line. `<c-panel-avatar-chip size="lg">` is for a
  page header only.
- A row of figures is `<c-panel-stat-row>`, a grid at every width (two columns on a phone), so the
  labels line up.
- A list of records in a panel is rows that share one shape: the name in `font-medium`, the
  detail under it in `text-sm text-muted` ("via Cohort A", "Individual"), the figure at the end in
  `tabular-nums`. Values are never joined into a sentence with dashes, and one word names a
  relation everywhere ("via", never "via" in one place and "through" in another).

### Filters and sorting

- A filter dropdown is a `<details>` whose `<summary>` carries `list-none marker:hidden
  [&::-webkit-details-marker]:hidden` and ends in `<c-icon name="dropdown">`, never the browser's
  triangle. A group nested inside a popover carries no `surface`: the popover is the one box.
- On a phone, Filter and Sort are two controls in the toolbar. Filter opens the filter sheet
  (selects and grouped checklists, one group per facet, never a chip cloud; chips show the values
  already applied). Sort opens a menu of columns; choosing the active column again flips its
  direction.
- Controls that belong together sit together: Filter next to Sort, the search field next to its
  filters, each sized to its content.

### Dialogs, sheets and the quick view

- A dialog ends in `<c-modal-footer>`: Cancel in its `cancel` slot at the left, the actions in the
  default slot at the right, the primary last; three or more group at the right.
  `<c-button-group>` is for buttons outside a dialog.
- A confirm dialog states what is true now and what the action changes ("Current cohort: Cohort A.
  Sam will be removed from Cohort A."). A disabled action shows its reason beside the control, and
  the control names it with `aria-describedby`.
- The modal host and the side panel clip horizontal overflow and the title wraps, so a dialog
  stays inside the viewport at every width, 375px included, title and every button included.
- Every sheet and dialog shares one chrome: on a phone it rises from the bottom with rounded top
  corners (`bottom-sheet` / `bottom-sheet-bare`) and opens with a header holding the title and a
  close control (`aria-label="Close"`, `<c-icon name="close">`), as `#quick-view`,
  `<c-modal-header>` and the filter sheet have.
- `#quick-view` opens with `show()` at every width, never `showModal()`: no scrim, no inert page,
  the list behind it stays tappable. `#app-modal` is the modal; it dims and blocks the page.

### Selection bar

The selection bar is fixed to the bottom of the viewport below `lg` and keeps every control inside
the viewport at 375px; the list reserves its height beneath itself while it is fixed.

### Adding and editing records

- Adding a record by hand is a form for one record with "Add" and "Add and add another"
  (`CreateInstanceAction.submit_buttons` is the shape), so a person adds one, reads the outcome
  and adds the next. A textarea that asks for one record per line is an import wearing a form's
  clothes; a list goes to an import page with a preview.
- A record's own name is a field with a Save button on its Settings panel, posted inline to the
  `edit` action (`renders_in_footer = False`), as the cohort Settings tab does, not a dialog.
  Dialogs are for confirmations and multi-field forms.
- Entering an email for a person who may already exist searches as you type and offers the
  matches, so the person picks rather than remembers.

### Placement

A control sits beside the thing it changes, as the brand's visual system says. On the educator
instance pages that puts each action here:

| Thing shown | Control beside it |
|---|---|
| A learner's Cohorts panel (Overview tab) | Add to cohort, Remove, Move |
| A learner's Courses tab | Register for a course |
| A learner's Course registrations list (Overview tab) | Deactivate / Reactivate a registration: the list is the only place an inactive registration is shown, so Reactivate has no other home |
| A cohort's Settings tab | The name field, the Staff list with Add staff member, Deactivate, Delete |
| A cohort's Learners tab | Add learners, Remove, Move |
| A learner's Settings tab | Edit name, Resend setup email, Deactivate / Reactivate: the actions with no home of their own |

### Padding, gaps and phones

- Every control has padding on all four sides. The base `<select>` rule draws its chevron inside
  the end padding, clear of the edge.
- Siblings sit apart through the container (`gap-*` or `space-*`); children carry no margins.
- On a phone a button is 44px tall and as wide as its label, with the small size's text and
  padding; the height is the only thing that grows.

## What enforces it

`freedom_ls/panel_framework/tests/invariants/test_templates.py` fails on most of the above before
QA looks: `test_no_control_link_is_hand_styled`, `test_every_anchor_with_visible_text_carries_its_own_classes`,
`test_every_framework_action_trigger_is_small`, `test_every_dialog_ends_in_the_modal_footer_not_a_button_group`,
`test_the_modal_host_and_the_side_panel_clip_horizontal_overflow`, `test_the_filter_sheet_has_a_close_control`,
`test_the_quick_view_is_never_modal`, `test_the_base_select_rule_draws_its_own_chevron_inside_the_end_padding`,
`test_no_panel_component_uses_raw_colours`. Run that file after any change to a panel template.

## Visual checklist

What QA checks in a screenshot of a panel-framework page, at every viewport.

- A link that acts as a control (a name, a back link, a row, "Edit", a choice in a filter menu)
  has the look of that control, with the prose underline absent.
- Every action trigger outside a dialog footer is the small size, and the triggers on one page are
  one size; buttons that sit together have a gap between them.
- Every control has padding on all sides and a select's chevron sits clear of its edge; at the
  phone viewport a button is 44px tall and as wide as its label.
- A dialog's Cancel sits at the left and its actions at the right; two buttons in one row never
  share a bare verb.
- The table footer states the entry count at the left, in line with the pager, on a single-page
  table too; hovering an empty table's message tints nothing.
- A log or History table has sort headers and the Who, What and When filters.
- A list of records in a panel has the same fields in the same places on every row, never
  dash-joined sentences; a row of figures lines its labels up in columns at every width; a person
  in a list row has a small name and a small avatar centred on the name's first line.
- A disclosure shows the icon chevron, never the browser's triangle; a group opened inside a
  popover draws no second box.
- A sheet on a phone has rounded top corners and a header with a close control; a quick view
  leaves the page behind it undimmed and tappable, a modal dims it.
- A dialog, sheet, table or selection bar stays inside the viewport at every width, title and
  every button included.
- A page header states each fact once and shows a state badge only for a state that differs from
  the default; a list page starts at its heading and toolbar, with help in a dialog or the docs
  rather than a paragraph above the list.
- Each instance-page action sits where the Placement table puts it; a Settings tab holds only
  actions that have no home beside the thing they change.
