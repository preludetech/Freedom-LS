---
name: panel-framework
description: "How a FreedomLS panel-framework page looks and behaves: list and instance views, data tables, actions and triggers, filters, the quick view, dialogs and sheets, the selection bar, and the invariant tests that enforce each rule. Use when building or changing a panel, table, action, filter, quick view or dialog, and when capturing feedback on how one looks."
allowed-tools: Read, Grep, Glob
---

# Panel framework

`freedom_ls/panel_framework` is a toolkit for building management pages from panels: tables,
record pages, actions, filters, dialogs. A rule about how a panel-framework page looks or behaves
lives here, not in the brand guidelines and not in a generic plugin: a trigger size, a table
footer, a sheet's chrome. An app built on the framework keeps its own page-by-page rules (which
page holds which action) in its own skill: for the educator interface that is
`Skill(fls-dev:educator-interface)`. `Skill(brand-guidelines)` owns colour, type and the brand
components; `Skill(fls-dev:frontend-styling)` owns the theme tokens.

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
  `ConfirmAction` is the confirm dialog (`confirm_label`, `confirm_variant`, `loading_text`, the
  hooks `get_title`, `get_hidden_fields`, `get_confirm_context`); `DeleteAction` extends it, and
  its `get_known_blocked_reason(ctx, instance)` returns a refusal known without collecting the
  cascade. `ReasonMixin` adds the reason dialog: a `ReasonForm` (`forms.py`, `reason_form_class`)
  whose field `modal/confirm.html` renders in the body, validated in `handle_submit`. A host
  sets `reason_max_length` on its `ReasonForm` subclass to the length its own store takes.
  `refusal_response(ctx, *, title, message, status=422)` renders a refusal in
  `modal/message.html`, and `ConfirmAction.refuse` calls it. `row_param` names the parameter a
  row-scoped action reads, and `get_row_object(ctx)` looks that row up in `get_row_queryset(ctx)`
  (404 when absent), once per request; `get_hidden_fields` posts it back by default. The form
  hooks take `ctx`, and the action's URL is `action_url` in every fragment. A GET to an action
  with no `template_name` answers 405. `CreateInstanceAction`'s form never takes the page's
  instance.
- `context.py`: `PanelContext`. `ctx.once(key, load)` reads a value once per request; the key
  names everything the value depends on, because every context of the request shares the store.
- `filters.py`: declared table filters, applied on top of search and sort, in `PanelAction`'s shape.
  `ToggleFilter` widens the table's own queryset when set (`BooleanFilter` narrows);
  `PeriodFilter(key, label, field, presets)` filters `field` to calendar days ending today, each
  preset a `(label, days)`.
- `quick_view.py`: `QuickView` feeds the drawer one row of a list opens.
- `bulk_actions.py`: row selection and the action that runs once over the selected rows.
  `PermittedBulkAction[ActorT]` is the base a host subclasses: it takes the scope from
  `scope_for_request` (no default) and words each skip reason in both tenses
  (`confirmation_skip_line`, `result_line`). `register_bulk_action` and `bulk_actions_for_table`
  are the registry; registration order is the selection bar's order.
- `lazy_panels.py` and `errors.py`: `LazyBodyPanel` renders its body on request (`load_label` is
  the no-JavaScript link text), and a body that raises `PanelBodyTooLargeError` shows its message
  in the region.
- `housekeeping.py`: the sweeps over `BulkActionRun`, `mark_unpicked_runs_failed`,
  `mark_orphaned_runs_failed` and `delete_finished_records`, or `sweep_run_records` for all three.
  The framework schedules none of them: the host does.
- `static/panel_framework/js/`: `alpine-components.js` and `shell-components.js` (`sidePanel`,
  `refreshTimer`, `visibilityPoller`). A host loads both.
- Public names: a framework module lists what a host may import in `__all__`; `tasks`, `checks`,
  `field_display` and `templatetags` are private.

Components live in `freedom_ls/panel_framework/templates/cotton/`: `data-table`,
`data-table-card`, `data-table-actions`, `data-table-cells/{text,link,datetime,date,badge,related_list}`,
`modal-header`, `modal-body`, `modal-footer`, `modal-trigger`, `quick-view-trigger` and the
`panel-*` set (`panel-page-header`, `panel-toolbar`, `panel-search-field`, `panel-filter-toggle`,
`panel-applied-filter`, `panel-notice`, `panel-close-button`, `panel-table`, `panel-table-card`,
`panel-list`, `panel-list-row`, `panel-heading`, `panel-empty-state`, `panel-person-link`, `panel-avatar-chip`,
`panel-attention-list`, `panel-attention-row`, `panel-stat-row`, `panel-stat-tile`,
`panel-status-badge`, `panel-definition-list`, `panel-definition-row`, `panel-card`,
`panel-progress-bar`, `panel-skeleton`). The page chrome is in
`templates/panel_framework/partials/`: `table_toolbar`, `table_footer`, `table_selection_bar` (the bulk-action bar), `table_sheet`,
`table_empty`, `quick_view_host`, `modal_host`, `discard_prompt`, `reason_field`, `error_summary`,
`sidebar_nav`, `breadcrumbs`. The dialogs are `templates/panel_framework/modal/`: `confirm.html`,
`delete_confirmation.html`, `form.html` and `message.html`.
`ls freedom_ls/panel_framework/templates/cotton/` is the current list.

## How it looks and behaves

### Triggers and buttons

- A button's size and variant follow from where it sits:

  | Place | Size | Variant |
  | --- | --- | --- |
  | Dialog footer (`<c-modal-footer>`) | default | Cancel `secondary`; the one confirm `primary`, or `error` when it deletes |
  | Panel footer, page header, empty state | small | `primary` for the panel's one main create action; `secondary` for the rest |
  | Table row, card | small | `secondary`; never `primary` or `error` |
  | Toolbar (Filter, Sort, Export), pager | small | `secondary` |
  | Selection bar | small | `ghost`, text only |
  | Text action in content ("Edit", "Change", "Clear all") | small | `link` |

  Every trigger the framework renders is `size="small"` (`{% render_action %}`,
  `<c-modal-trigger>`); the dialog footer's pair is the one full-size pair, because that is the
  decision the dialog asks for. A panel holds at most one `primary` button outside a dialog.
- A button looks the same at every width. Below `md` the shared rule in
  `tailwind.components.css` gives every panel button an invisible 44px-tall hit area and leaves
  its look alone, so a small button stays about 32px tall on a phone. The dialog footer's buttons
  are the one exception: on a phone they are 44px tall, at the bottom of the sheet under the
  thumb. A text field is 44px tall on a phone. No template adds a height to a button.
- Buttons in a table cell or a card sit inside `<c-data-table-actions>`, which owns the gap; the
  buttons carry no margins.
- A table row's buttons sit in columns by what they act on. A button for one item in a cell sits
  in its own column, on the same line as its item; the buttons that act on the whole row take the
  last column. One cell never stacks both kinds.
- On a card, a button for one item sits under that item, inside the item's block; the card never
  gathers every item's buttons under one shared label. Where the same label repeats for several
  items, each button's accessible name names its item ("Deactivate Organisation admin").
- A table whose columns do not fit its own container shows as cards, never behind a sideways
  scroll. The table declares it (`cards_when_narrow`) and the switch reads the container's width,
  not the viewport's, so it also holds beside an open quick view.
- A wide read-only table with no action column (a report's progress table) may scroll sideways
  inside its own region instead. Its name column then has a minimum width, so a person's name
  stays readable at every width, a status badge stays on one line, and no button sits behind the
  scroll.
- A row the viewer cannot act on states its fields and leaves its buttons column empty: no note
  saying why, no link to the page where it can be changed.
- A row's own record is opened in the quick view; detail a row does not need to be scanned (who
  made an entry, and when) lives there, not in the row.
- Two buttons in one row each name their object, so no two share a bare verb.

### Controls are components

Every anchor in a panel-framework page is a control. The base layer underlines every `<a>`, and
that underline means "a link inside prose", which these templates never hold. A control takes the
component for its job: a person gets `<c-panel-person-link>` (avatar and name, the one way a person
is linked from a row, a card, an attention list or a dialog), a back link
`<c-back-link>`, a text action ("Edit", "Change", "Clear all") `<c-button variant="link">`, and a
clickable row, a sort header or a filter choice the row-link style (`no-underline text-on-surface`,
or `text-muted` for a secondary one). An anchor whose class list names neither `no-underline` nor
`btn` has been forgotten.

### Page header

`<c-panel-page-header>` states each fact once. Its `badge` slot carries a state only when it differs
from the default (Inactive, Pending); stats stay out when the tabs already count them; no action
sits in the header, each lives with the thing it changes. A list page opens with its heading and
its toolbar, so the list starts at the top; help lives in a dialog the page opens, or in the docs.

### Panels

- Each panel does one job. A tab that does several jobs is a `PanelStack` of panels, one per job
  (a cohort's Settings tab: Name, Staff, Status), never one card with sub-headings.
- A panel's title is the only heading for its job; nothing inside the panel repeats or nests a
  heading for a different job.
- `<c-panel-card>` looks the same flush or not: the header draws no rule. Flush only drops the
  body padding. A panel never adds its own rule, border or uppercase sub-heading inside the card.
- A part built for its own page and embedded in a panel (a conversation thread) drops its own
  header, sits on the panel's padding, and a bar along the card's bottom edge follows the card's
  rounded corners.
- Inside a panel, space separates items. A list of people or records is rows in a grid with a gap,
  one column per kind of content (person, role, buttons), so the columns line up.
- `<c-panel-list>` is the one list that draws a rule between its rows. Nothing else inside a panel
  does, and nothing inside a panel is boxed: a group within a panel (one course among several) is
  a section with its own heading, separated from the next by space, never a card inside the card.

### Tables

- The footer states the entry count at the left, in line with the pager, on a single-page table
  too ("12 records", "Showing 1–10 of 80 records"). It renders from `entry_count`, so a table
  never writes its own. A paged `<c-panel-table>` uses the same footer: the count at the left and
  the pager at the right, never a bare pager.
- An empty table shows `<c-panel-empty-state>` inside the data table's empty row, which carries
  `hover:bg-transparent` so the empty state takes no row hover.
- A person in a list row is `<c-panel-attention-row>`: the name `text-sm font-semibold`, the chip
  `size="sm"` with its centre on the name's first line. `<c-panel-avatar-chip size="lg">` is for a
  page header only.
- A person's badges ("You", "Inactive", "Also a learner") go in the `badges` slot of
  `<c-panel-person-link>` or `<c-panel-avatar-chip>`, never beside the component. The slot puts
  them on their own line under the name and email, left-aligned with the name, and the avatar
  stays beside the name and email.
- `<c-panel-avatar-chip>` and `<c-panel-person-link>` take `picture_url`, a plain URL the caller
  resolves and passes bound (`:picture_url="user.profile_picture_url"`; a quoted `{{ }}` turns
  `None` into the text "None"). Empty shows the initials, which stay under the picture as the
  fallback when the image fails to load.
- A row of figures is `<c-panel-stat-row>`, a grid at every width (two columns on a phone), so the
  labels line up.
- A list of records in a panel is rows that share one shape: the name in `font-medium`, the
  detail under it in `text-sm text-muted` ("via Group A", "Individual"), the figure at the end in
  `tabular-nums`. Values are never joined into a sentence with dashes, and one word names a
  relation everywhere ("via", never "via" in one place and "through" in another).
- An ordered list with an action on each entry is a data table inside `.panel-data-table`: one
  `<tr>` per entry with its number, title and type in cells and its action in a
  `<c-data-table-actions>` cell, spaced by the table's own row padding. It is never a flex list
  with `gap-*` between rows and a button at the far end.
- A group row carries the row-detail chevron (`size-8`, `aria-expanded`, `aria-controls` naming
  its child rows) beside its title, and its children are the indented rows under it, open by
  default. An empty group shows its note as a child row.

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
- From `md` up the toolbar is one row: search, filters, "Add filter", "Clear all" and Export. The
  search field shrinks (`md:flex-1 md:min-w-40 md:max-w-72`) before anything wraps.

### Dialogs, sheets and the quick view

- Every dialog is three sibling components and nothing else at the top level:
  `<c-modal-header>`, `<c-modal-body>`, `<c-modal-footer>`. The body owns the padding and the gap
  between its blocks; the footer is never inside the body or another padded element. A message
  dialog (`panel_framework/modal/message.html`) ends in a Close footer like every other. The
  discard prompt (`panel_framework/partials/discard_prompt.html`) puts its body in `<c-modal-body>`
  and ends in the same footer.
- A dialog takes one of three shapes. `modal/confirm.html` is one `<form>` holding the body, the
  reason field when `reason_form` is set, and a footer with one confirm button; a subclass keeps
  only its title, body and hidden fields. `modal/message.html` states something and ends in a
  Close the footer focuses (refusals, "unavailable", empty messages). `modal/form.html` is a
  multi-field form. A multi-step dialog keeps its own template but still uses `<c-modal-body>`,
  `partials/error_summary.html` and `<c-panel-notice>`.
- A dialog ends in `<c-modal-footer>`: it renders its own Cancel at the left (`cancel`,
  `cancel_href`, `cancel_click`, `focus_cancel`), the actions in the default slot at the right, the
  primary last; three or more group at the right. No template writes a Cancel button or a `cancel`
  slot. `<c-button-group>` is for buttons outside a dialog.
- A footer's Cancel or Close calls `cancel()`: it drops the input and never asks to discard. Only
  the header close control and Esc call `requestClose()`, which goes through the dirty-form
  guard.
- A notice inside a dialog or panel is `<c-panel-notice tone title>` (`info`, `warning`, `error`,
  `success`), never `<c-callout>` or a hand-built `bg-error/10` box. The close control is
  `<c-panel-close-button>`.
- Tone follows the effect. A confirm that deletes a row (Delete, Remove) is `error`; one that
  flips `is_active` (Deactivate, Reactivate) is `primary`, as the bulk actions are.
- A confirmation is a modal in `#app-modal`, never a page of its own. Without JavaScript the
  confirmation URL renders the page it came from with the same modal chrome open over it, its
  Cancel a link back to that page.
- Body text in a dialog is one size, the base size; only the title in `<c-modal-header>` differs.
  Lists, consequences, notices and errors in the body take no `text-sm`.
- A confirm dialog states what is true now and what the action changes, naming the records it
  touches. A disabled confirm's reason is body text in the dialog's body, never in the footer:
  directly under the field that causes it (the picker), or at the end of the body when no field
  does. The footer holds Cancel and the disabled confirm only, and the confirm names the reason
  with `aria-describedby`. A bulk confirm waiting on its picker gives
  "Choose a <field label> first." as that reason, worded from the picker field's label.
- A list of options in a dialog (radio choices, search results) is separated by space. An option
  draws no border of its own and options have no dividers between them; the group's own container
  is the one box.
- A field's hint sits directly under the field as its help text, and a search's empty message
  takes the results' place below it. An empty result list renders nothing.
- The modal host and the side panel clip horizontal overflow and the title wraps, so a dialog
  stays inside the viewport at every width, 375px included, title and every button included.
- A dialog's loading text ends in the ellipsis character "…", and its `hx-disabled-elt` is
  `find button[type='submit']`.
- Every sheet and dialog shares one chrome: on a phone it rises from the bottom with rounded top
  corners (`bottom-sheet` / `bottom-sheet-bare`) and opens with a header holding the title and a
  close control (`aria-label="Close"`, `<c-icon name="close">`), as `#quick-view`,
  `<c-modal-header>` and the filter sheet have.
- The shell side panel (`side-panel-dialog` in `_base_interface.html`: the educator navigation,
  the learner course outline) is shell navigation, not a framework sheet. On a phone it rises as a
  bottom sheet with no header and no close control, and closes by a backdrop tap, Esc or
  device-back.
- `#quick-view` opens with `show()` at every width, never `showModal()`: no scrim, no inert page,
  the list behind it stays tappable. `#app-modal` is the modal; it dims and blocks the page.
- A preview opens in `#app-modal` at the wide size, titled "<title> (Preview)" with its type
  chip. The title says it is a preview, so no callout does.
- `#app-modal` has one wide size, for previews only; no other dialog widens. A fragment opts
  in by putting `data-modal-size="wide"` on its root. It changes the width (about
  `min(92vw, 64rem)` from 640px up) and the max-height (95dvh); the height, the scrolling and the
  sticky header stay the shared rule's.
- Only a dialog's body scrolls. The header and footer stay put and span the dialog's full width,
  so their rules reach both edges, and the body has the same padding left and right.
- The body shows that it scrolls: its scrollbar track is always visible, and a fade sits at the
  body's bottom edge while content lies below the fold, gone once the end is reached.

### Selection bar

The selection bar shows only while rows are selected or a bulk run is going. It has one position
at every width: it replaces the whole toolbar above the table, at the toolbar's height, and sticks
under the site header while the page scrolls. Search, filters and export are out of reach until
the selection clears. Every control stays inside the bar at 375px.

- Actions are ghost, text-only, `size="small"` buttons. `promote_bulk_actions` gives the first
  `PROMOTED_BULK_ACTION_COUNT` (4) permitted non-destructive actions a button each.
- Every other action sits under a "More" menu. A destructive action (`BulkAction.destructive`, a
  `variant` of `"error"`) never takes a button: it is last in the menu, in error text, under a rule
  when a non-destructive entry sits above it.
- The count reads "N selected". "Select all N" (a `variant="link"` button) selects every row the
  filters match, and reads "Deselect all" once it has. "Clear" empties the selection and sits alone at the right edge.
- Changing page, sort or filters clears the selection.
- More is a `<c-dropdown-menu>`. Without JavaScript it is a `<details>` with the same panel, rule
  and error tone, never a row of loose buttons.
- A bulk result states counts: the headline "N records changed", then one line per skip reason
  ("N records already up to date"). It names only the rows that failed, never the skipped ones.

### Adding and editing records

- Adding a record by hand is a form for one record with "Add" and "Add and add another"
  (`CreateInstanceAction.submit_buttons` is the shape), so a person adds one, reads the outcome
  and adds the next. A textarea that asks for one record per line is an import wearing a form's
  clothes; a list goes to an import page with a preview.
- A record's own name is a field with a Save button on its Settings panel, posted inline to the
  `edit` action (`renders_in_footer = False`), not a dialog.
  Dialogs are for confirmations and multi-field forms.
- Entering an email for a person who may already exist searches as you type and offers the
  matches, so the person picks rather than remembers.
- An inline form in a panel (a record's name on its Settings tab) shows a field error as one line
  under its field: the message alone, never prefixed with the field's label, with `role="alert"`,
  and the input names it with `aria-describedby` and carries `aria-invalid`. It gets no notice
  box and no error summary.
- An element that takes focus only by script, so a screen reader announces it (a result heading,
  a notice, an error summary: `tabindex="-1"`), shows no outline. One shared rule does this.
  Buttons, links and fields keep their focus rings.

### Placement

A control sits beside the thing it changes, as the brand's visual system says; a Settings panel
holds only the actions with no home of their own. Which page of an app holds which action is that
app's skill.

### Padding, gaps and phones

- Every control has padding on all four sides. The base `<select>` rule draws its chevron inside
  the end padding, clear of the edge.
- Siblings sit apart through the container (`gap-*` or `space-*`); children carry no margins.
- A list value in a details panel sits flush with its label: the bullets line up with the label's
  first letter. Override the base `ul` margin (`ml-0`) and keep wrapped lines under the text.
  Its items sit close together: override the base list spacing (`space-y-1`, `py-0` on each item).
- On a phone a button is as wide as its label and as tall as at desktop; its 44px hit area is
  invisible (see Triggers and buttons).
- Vertical space follows one scale, and the components own it:
  - 4px (`space-y-1`) inside one field: the items of one list value.
  - 12px (`gap-y-3`, `mt-3`) between the fields of a card or an inline
    `<c-panel-definition-list>`, and between a card's title block (name, email) and its fields.
  - 16px (`py-4`) above and below a card's content, with the list's rule between cards.

  So a card reads as title, then fields, each field distinct, and a list value stays tighter than
  the space between fields. A card template takes this spacing from `<c-panel-definition-list>`
  and `<c-data-table-card>`, plus `mt-3` above its fields; it sets no `gap-y-1` or `mt-1` of its
  own.

## What enforces it

`freedom_ls/panel_framework/tests/invariants/test_templates.py` fails on most of the above before
QA looks: `test_no_control_link_is_hand_styled`, `test_every_anchor_with_visible_text_carries_its_own_classes`,
`test_every_framework_action_trigger_is_small`, `test_every_dialog_ends_in_the_modal_footer_not_a_button_group`,
`test_the_modal_host_and_the_side_panel_clip_horizontal_overflow`, `test_the_filter_sheet_has_a_close_control`,
`test_the_quick_view_is_never_modal`, `test_the_base_select_rule_draws_its_own_chevron_inside_the_end_padding`,
`test_no_panel_component_uses_raw_colours`. For dialogs it also has
`test_every_dialog_is_a_header_a_body_and_a_footer`, `test_no_dialog_footer_sits_inside_the_body`,
`test_no_dialog_pads_its_own_body`, `test_every_dialog_renders_one_modal_footer_outside_its_body`
(one footer per step, none in a template that extends one),
`test_no_dialog_template_hand_writes_what_a_component_owns` (no Cancel button, `text-sm`,
`px-6 py-4`, `bg-error/10` or `<c-callout>`), `test_every_dialog_loading_text_ends_in_the_ellipsis_character`,
`test_every_dialog_disables_only_its_own_submit_buttons`,
`test_no_dialog_form_with_a_find_selector_holds_an_element_that_issues_its_own_request`,
`test_no_educator_module_sets_the_modal_trigger_template_by_hand`,
`test_no_template_hand_writes_a_table_outside_the_table_components`,
`test_no_button_hand_writes_a_touch_height`, `test_only_the_dialog_footer_makes_a_button_44px_tall_on_a_phone`
and `test_every_expand_chevron_turns_when_its_control_opens`. In the browser,
`educator_interface/tests/playwright/test_touch_targets.py` checks that a small button keeps its
desktop height on a phone, that its hit area is 44px, and that a dialog footer's buttons are 44px tall.
Run that file after any change to a panel template.

Three more files sit beside it in `tests/invariants/`:

- `test_reason_mixin.py`: every `ReasonMixin` subclass submits through the mixin's `handle_submit`.
- `test_alpine_registration.py`: every `x-data` name a framework template uses is registered by
  `Alpine.data` in `alpine-components.js` or `shell-components.js`, unless the host supplies it.
- `test_public_names.py`: a file outside the framework imports only names a framework module lists
  in `__all__` (and no private module), and every `__all__` entry exists.

## Visual checklist

What QA checks in a screenshot of a panel-framework page, at every viewport.

- A link that acts as a control (a name, a back link, a row, "Edit", a choice in a filter menu)
  has the look of that control, with the prose underline absent.
- Row, card, toolbar and pager buttons are the small size at every width, with no taller look on a
  phone; only a dialog footer's buttons are full size, and 44px tall on a phone. Each button's
  variant matches its place (outline in rows, cards, toolbar and pager; text-only in the selection
  bar). Buttons that sit together have a gap between them.
- Every control has padding on all sides and a select's chevron sits clear of its edge; at the
  phone viewport a button is as wide as its label.
- In a card, the fields have clear space between them, more than between the items of one value,
  and the title block stands apart from the fields.
- A dialog's Cancel sits at the left and its actions at the right; two buttons in one row never
  share a bare verb.
- The table footer states the entry count at the left, in line with the pager, on a single-page
  table and a paged static table too; hovering an empty table's message tints nothing.
- A list of records in a panel has the same fields in the same places on every row, never
  dash-joined sentences; a row of figures lines its labels up in columns at every width; a person
  in a list row has a small name and a small avatar centred on the name's first line; a person's
  badges sit on a line under the name and email, their left edge on the name's left edge.
- A disclosure, filter chip or menu button shows the icon chevron, never the browser's triangle,
  and the chevron turns up while open; a group opened inside a popover draws no second box.
- A confirmation shows as a modal over the page it came from, JavaScript on or off; body text in a
  dialog is one size.
- A disabled confirm has its reason in the dialog's body, under the field that causes it, at the
  body's text size, and its footer holds Cancel and the confirm on one line; a bulk picker dialog
  with nothing chosen reads "Choose a cohort first." (or the picker's own field).
- A bulk result shows counts ("N records changed", "N records already up to date") and names only
  failed rows.
- The selection bar sits above the table, in the toolbar's place, at every viewport, and stays in
  view while the page scrolls.
- The table toolbar is one row at tablet and desktop widths; the search field is the part that
  shrinks.
- An ordered list with per-entry actions is a data table: rows spaced by their cell padding only,
  the chevron and the small action button inside the row next to its text.
- A preview dialog is titled "<title> (Preview)" with its type chip and carries no "this is a
  preview" callout; the dialog shows its scrollbar and a bottom fade while more content lies
  below.
- A sheet on a phone has rounded top corners and a header with a close control. The shell side
  panel has no header and no close control, and closes by a backdrop tap or Esc. A quick view
  leaves the page behind it undimmed and tappable, a modal dims it.
- A dialog, sheet, table or selection bar (More menu included) stays inside the viewport at every
  width, title and every button included. A table with action columns is cards at 768 and beside
  an open quick view, with no button cut off or behind a sideways scroll. In a table that scrolls
  sideways in its own region, every person's name is readable and no badge wraps.
- A page header states each fact once and shows a state badge only for a state that differs from
  the default; a list page starts at its heading and toolbar, with help in a dialog or the docs
  rather than a paragraph above the list.
- A list value in a details panel has its bullets in line with the start of its label, and its
  items sit close together, with less gap than between two rows.
- A control sits beside the thing it changes; a Settings panel holds only actions that have no
  home beside the thing they change.
- Each panel does one job: no panel holds a second heading for a different job, and no panel
  header has a rule under it.
- Every dialog has a header, a body and a footer, with the header and footer rules running the
  full width of the dialog, edge to edge, and the footer buttons lined up with the body text and
  the close control. The body's padding is the same left and right, and only the body scrolls.
- A heading, notice or error summary that takes focus so a screen reader announces it shows no
  focus box; a button, link or field does.
- A field error in an inline panel form is one line under its field, without the field's label.
- Options in a dialog (radio choices, search results) are separated by space, with no box around
  each option and no line between them; an empty result list draws nothing.
- A table row's per-item buttons sit on their item's line in their own column, and the
  whole-row buttons sit in the last column.
- On a card, each item's buttons sit under that item; no card lists every item's buttons together
  under one label.
- Content embedded in a panel shows no second header or rule, starts on the panel's left padding,
  and a bottom bar keeps the card's rounded corners.
- A row the viewer cannot act on shows its fields and an empty buttons column, with no
  explanatory note or link in its place.
