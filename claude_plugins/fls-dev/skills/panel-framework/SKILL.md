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
  `DataTablePanel`, `InstanceDetailsPanel` and `EditableListPanel` are the shapes.
  `EditableListPanel` is a short list of the entries that belong to the page's instance, each
  with Edit and Remove and one Add trigger. A subclass sets `form_class` (or overrides
  `get_form_class()`), `parent_field`, `empty_message`, `refresh_events` (the check fails
  without it, since the list would never show a change), and implements `get_entries()` and
  `get_summary(entry)`, which returns an `EditableListSummary(title, detail)`. `max_entries`
  caps the list (the cap line replaces the Add trigger), `noun` names an entry in the dialogs,
  and `layout` is `"list"` (default) or `"table"`.
- `views.py`: `ListViewConfig` (a section's table page, with its quick view) and
  `ObjectViewConfig` / `InstanceView` (one record's page, with its tabs). `StatusBadge` and
  `HeaderStat` feed the page header.
- `tables.py`: `DataTable` and `TableQuery`, each table's own slice of the query string (search,
  sort, page, filters), so two tables on one page never read each other's parameters.
  A table's rows per page are its `page_size`, else the project setting `PANEL_TABLE_PAGE_SIZE`
  (default 10); set `page_size` only for a table that needs another count. `compact = True`
  shortens rows from `md` up, for a dense table (an outline); cards keep their padding.
  `row_detail_template_name` renders a template under each row, behind a toggle (a disclosure
  below `md`); `has_row_detail(row)` hides it for a row with nothing to show. `has_child_rows`
  with `get_child_rows(row)` nests full rows under a group row (see Tables). A per-row template
  `get_row_template_name(row)` replaces a row's cells from the primary column to the last with
  that template (for a note, not a record: it has no checkbox and no row detail); it renders with
  `object` and `row`. A panel whose rows are computed returns them from
  `DataTablePanel.get_row_sequence` (see Tables).
- `actions.py`: `PanelAction` is a button and what submitting it does; `FormPanelAction`,
  `CreateInstanceAction`, `EditAction` and `DeleteAction` build on it. `renders_in_footer` places
  an action in the panel footer or inline; `submit_buttons` names a form's buttons.
  `ConfirmAction` is the confirm dialog (`confirm_label`, `confirm_variant`, `loading_text`, the
  hooks `get_title`, `get_confirm_context`); `DeleteAction` extends it, and
  its `get_known_blocked_reason(ctx, instance)` returns a refusal known without collecting the
  cascade. `ReasonMixin` adds the reason dialog: a `ReasonForm` (`forms.py`, `reason_form_class`)
  whose field `modal/confirm.html` renders in the body, validated in `handle_submit`. A host
  sets `reason_max_length` on its `ReasonForm` subclass to the length its own store takes.
  `reason_required = True` refuses an empty reason (use it when the record needs a why). A
  `reason_choices` list of `(value, label)` pairs adds a choice ahead of the text, which becomes
  its "Details"; a choice is then always required, whatever `reason_required` says. Override
  `get_reason_choices(ctx)` when the list is per request; the same list renders and validates.
  The submit reads the text from `ctx.reason` and the choice's value from `ctx.reason_choice`.
  With neither option set the dialog is the plain optional reason.
  `refusal_response(ctx, *, title, message, status=422)` renders a refusal in
  `modal/message.html`, and `ConfirmAction.refuse` calls it. `row_param` names the parameter a
  row-scoped action reads, and `get_row_object(ctx)` looks that row up in `get_row_queryset(ctx)`
  (404 when absent), once per request. `get_hidden_fields(ctx)` lives on `PanelAction`: it returns
  the name-to-value pairs the submit posts back as hidden inputs, the row `row_param` names by
  default. `ConfirmAction` and `FormPanelAction` both pass it to their template as
  `hidden_fields`, and `modal/confirm.html` and `modal/form.html` render it. The form
  hooks take `ctx`, and the action's URL is `action_url` in every fragment. A GET to an action
  with no `template_name` answers 405. `CreateInstanceAction`'s form never takes the page's
  instance.
  `EditableListPanel.get_actions()` returns `EditableListAddAction`, `EditableListEditAction`
  and `EditableListRemoveAction`. Each derives its capability from the entry model
  (`add_`, `change_`, `delete_<model>`) and asks it of the parent instance; a subclass sets
  `derive_capability = False` to state its own `capability` (or `None`).
- `context.py`: `PanelContext`. `ctx.once(key, load)` reads a value once per request; the key
  names everything the value depends on, because every context of the request shares the store.
- `filters.py`: declared table filters, applied on top of search and sort, in `PanelAction`'s shape.
  `ToggleFilter` widens the table's own queryset when set (`BooleanFilter` narrows);
  `PeriodFilter(key, label, field, presets)` filters `field` to calendar days ending today, each
  preset a `(label, days)`.
- `quick_view.py`: `QuickView` feeds the drawer one row of a list opens.
- `widgets.py`: `PanelClearableFileInput`, the file widget a form action swaps in for Django's
  default one: it names the current file without a link or its storage key.
- `bulk_actions.py`: row selection and the action that runs once over the selected rows.
  `PermittedBulkAction[ActorT]` is the base a host subclasses: it takes the scope from
  `scope_for_request` (no default) and words each skip reason in both tenses
  (`confirmation_skip_line`, `result_line`). `register_bulk_action` and `bulk_actions_for_table`
  are the registry; registration order is the selection bar's order.
- `lazy_panels.py` and `errors.py`: `LazyBodyPanel` renders its body on request (`load_label` is
  the no-JavaScript link text), and a body that raises `PanelBodyTooLargeError` shows its message
  in the region.
  `show_as_of = True` draws "As of <time>" above the loaded body (`partials/as_of.html`, the
  `as_of` block of `panels/_lazy_region.html`). Use it when the data is gathered or cached: return
  the time it was computed as an aware datetime under `"as_of"` from `get_loaded_context`, or the
  stamp is the render time, which is wrong for older data. `None` (nothing computed yet) shows
  the body with no stamp. A naive or non-datetime value raises.
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
`panel-applied-filter`, `panel-close-button`, `panel-table`, `panel-table-card`,
`panel-list`, `panel-list-row`, `panel-heading`, `panel-empty-state`, `panel-person-link`, `panel-avatar-chip`,
`panel-attention-list`, `panel-attention-row`, `panel-stat-row`, `panel-stat-tile`,
`panel-status-badge`, `panel-definition-list`, `panel-definition-row`, `panel-card`,
`panel-progress-bar`, `panel-skeleton`). The page chrome is in
`templates/panel_framework/partials/`: `table_toolbar`, `table_footer`, `table_selection_bar` (the bulk-action bar), `table_sheet`,
`table_empty`, `quick_view_host`, `modal_host`, `discard_prompt`, `reason_field`, `error_summary`,
`sidebar_nav`, `breadcrumbs`. The dialogs are `templates/panel_framework/modal/`: `confirm.html`,
`delete_confirmation.html`, `form.html` and `message.html`.
`ls freedom_ls/panel_framework/templates/cotton/` is the current list.

## Sites, bulk runs and the task backend

The framework imports nothing from another `freedom_ls` app, so it cannot ask `site_aware_models`
which site a request belongs to. The host says so through a setting.

- `PANEL_FRAMEWORK_SITE_RESOLVER` is the dotted path of a callable that takes the request and
  returns its `Site`, or `None` or a `RequestSite` when the request belongs to no site. Whatever it
  raises propagates. The default is `freedom_ls.panel_framework.sites.current_site_or_none`, which
  wraps `django.contrib.sites.shortcuts.get_current_site` and answers an unknown host with `None`.
  There `SITE_ID` wins over the host name: a project serving several sites from one process must
  set its own resolver, or every request shares one site's runs. FLS sets
  `freedom_ls.site_aware_models.models.get_cached_site` in `config/settings_base.py`.
- `sites.resolve_site(request)` returns the `Site`, or `None` when the resolver returns `None` or
  a `RequestSite`. It resolves once per request. A path that cannot be imported or is not
  callable, or a resolver that returns anything else, raises `ImproperlyConfigured`.
- `BulkActionRun` is a plain `models.Model` with an explicit `site` foreign key, and
  `BulkActionRun.objects` filters by no site. Scope every read with
  `BulkActionRun.objects.for_request(request)` (a request that resolves to no site sees no runs) or
  `.for_site(site_id)`. A worker or sweep has no request and reads by the site id it was given.
- Name the site when creating a run: `BulkActionRun.objects.create(site=site, ...)`.
  `PermittedBulkAction` does this itself, from `resolve_site(ctx.request)`. When no site
  resolves, the bulk-action view answers 422 ("This request belongs to no site.") before the
  preview, and `execute` raises `PermissionDenied` as a backstop.
- `freedom_ls_panel_framework.W001` is a system-check warning (`checks.check_task_backend`). It
  fires when `TASKS["default"]["BACKEND"]` is, or subclasses, Django's or the `django_tasks`
  backport's immediate or dummy backend and `DEBUG` is off, because a bulk action over
  `BULK_BACKGROUND_THRESHOLD` rows then runs inline or never. Run a durable backend with a worker,
  or add the id to `SILENCED_SYSTEM_CHECKS` when that is intended.
- `freedom_ls_panel_framework.W002` (`checks.check_site_resolver`) fires when `SITE_ID` is set,
  `PANEL_FRAMEWORK_SITE_RESOLVER` is still the default, and the database holds more than one
  `Site`: every site's runs would be recorded under `SITE_ID`'s. It counts sites, so it runs only
  under `migrate` or `manage.py check --database default`. FLS sets its own resolver and never
  sees it.

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
  `freedom_ls/panel_framework/css/panel_framework.css` gives every panel button an invisible 44px-tall hit area and leaves
  its look alone, so a small button stays about 32px tall on a phone. The dialog footer's buttons
  are the one exception: on a phone they are 44px tall, at the bottom of the sheet under the
  thumb. A text field is 44px tall on a phone. No template adds a height to a button.
- Buttons in a table cell or a card sit inside `<c-data-table-actions>`, which owns the gap; the
  buttons carry no margins.
- A table row's buttons sit in columns by what they act on. A button for one item in a cell sits
  in its own column, on the same line as its item; the buttons that act on the whole row take the
  last column. One cell never stacks both kinds.
- A list row's or card's buttons for its own entry sit in the entry's item footer: the `footer`
  slot of `<c-panel-list-row>` or `<c-panel-table-card>`, under the title and detail, left edge on
  the title's left edge, inside `<c-data-table-actions>`. Each button is as wide as its label; none
  stretches to fill the line or shares a line with the detail. The row's trailing slot holds a
  badge, figure or progress bar, never the entry's buttons. A desktop table row keeps its buttons
  in its actions cell.
- On a card, a button for one item sits under that item, inside the item's block; the card never
  gathers every item's buttons under one shared label. Where the same label repeats for several
  items, each button's accessible name names its item ("Deactivate Organisation admin").
- A table whose columns do not fit its own container shows as cards, never behind a sideways
  scroll. The table declares it (`cards_when_narrow`) and the switch reads the container's width,
  not the viewport's, so it also holds beside an open quick view. `<c-data-table>` takes it from
  `DataTablePanel.cards_when_narrow`; a static `<c-panel-table cards="true">` takes
  `cards_when_narrow="true"` on the tag, and switches its table and its `card_rows` on the width of
  its own container.
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

Framework templates draw their buttons, chips, callouts, dates, pagination and dropdown menus with
their own `c-panel-*` primitives (`panel-button`, `panel-button-group`, `panel-chip`, `panel-callout`,
`panel-back-link`, `panel-date`, `panel-datetime`, `panel-pagination`, `panel-dropdown-menu`,
`panel-dropdown-menu-separator`, `panel-icon` and `panel-page`) and never include a host component or template. FLS's wrappers
forward to its own `c-button`, `c-back-link` and the rest; the rules here name
the component an FLS panel template writes. The panel framework's own styles (`.panel-surface`,
`.panel-canvas`, `.panel-heading`, `.panel-btn`, the modal host, the selection bar and the compact
table) live in `freedom_ls/panel_framework/css/panel_framework.css`, not in `tailwind.components.css`.
`freedom_ls/panel_framework/HOST_CONTRACT.md` lists every primitive and what a host must supply.

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
- `<c-panel-avatar-chip>`, `<c-panel-person-link>` and `<c-panel-attention-row>` (with `user_id`) take `picture_url`, a plain URL the caller
  resolves and passes bound (`:picture_url="user.profile_picture_url"`; a quoted `{{ }}` turns
  `None` into the text "None"). Empty shows the initials, which stay under the picture as the
  fallback when the image fails to load.
- An avatar is drawn once per person per row group. A nested row naming the same person as the row
  it expands keeps the name and drops the avatar: `<c-panel-avatar-chip avatar_hidden=True>`. The
  avatar shows by default.
- A row of figures is `<c-panel-stat-row>`, a grid at every width (two columns on a phone), so the
  labels line up.
- A list of records in a panel is rows that share one shape: the name in `font-medium`, the
  detail under it in `text-sm text-muted` ("via Group A", "Individual"), the figure at the end in
  `tabular-nums`. Values are never joined into a sentence with dashes, and one word names a
  relation everywhere ("via", never "via" in one place and "through" in another).
- A numbered list with an action on each entry (the course outline) is a data table inside
  `.panel-data-table`: one `<tr>` per entry with its number, title and type in cells and its
  action in a `<c-data-table-actions>` cell, spaced by the table's own row padding. It is never a
  flex list with `gap-*` between rows and a button at the far end. A short list of records the
  user adds to, edits and removes is an `EditableListPanel`, not a hand-built table.
- After an `EditableListPanel` add, edit or remove, focus lands on a named element and a polite
  announcement is made in `#scope-announcer` (`pendingEntryAction` in `alpine-components.js`).
  Add focuses the cap line when the add filled the list, else the new entry's Edit trigger
  ("Added <title>."). Edit focuses that entry's Edit trigger ("Saved <title>."). Remove focuses
  the next entry's Edit trigger, else the previous one's, else the Add trigger ("Removed
  <title>."). A dialog closed without a change returns focus to its trigger.
- A group row carries the row-detail chevron (`size-8`, `aria-expanded`, `aria-controls` naming
  its child rows) beside its title, and its children are the indented rows under it, open by
  default. An empty group shows its note as a child row.
- Child rows (`has_child_rows`, `get_child_rows(row)`) are for a hierarchy shown in one table
  (a course outline). They cannot be combined with `row_detail_template_name`, and a table with
  child rows cannot have bulk actions: the framework raises `ImproperlyConfigured` for both.
  The `childRows` Alpine component in `alpine-components.js` runs the chevrons. A note row (an
  empty group's "no items") is `get_row_template_name`, not a column. `CourseOutlineTable` in
  `educator_interface/views.py` is the worked example, with `compact = True`.
- A sequence-backed table's panel overrides `get_row_sequence(request)` to return a list of row
  objects for rows that are computed, not stored; `get_queryset` stays a `QuerySet` for every
  other table. It pages and shows its empty state, nothing more: no `search_fields`, no filters,
  no sortable column, no export columns, and `noun` and `noun_singular` must be set (there is no
  model to name them), all checked when the panel class is defined. It has no bulk actions either;
  that, and child rows with bulk actions, raise on render whether or not the user may run them.

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
  multi-field form that renders `hidden_fields`. A multi-step dialog keeps its own template but still uses `<c-modal-body>`,
  `partials/error_summary.html` and `<c-panel-callout>`.
- A dialog ends in `<c-modal-footer>`: it renders its own Cancel at the left (`cancel`,
  `cancel_href`, `cancel_click`, `focus_cancel`), the actions in the default slot at the right, the
  primary last; three or more group at the right. No template writes a Cancel button or a `cancel`
  slot. `<c-button-group>` is for buttons outside a dialog.
- A footer's Cancel or Close calls `cancel()`: it drops the input and never asks to discard. Only
  the header close control and Esc call `requestClose()`, which goes through the dirty-form
  guard.
- A notice inside a dialog or panel is `<c-panel-callout tone title>` in a framework template and
  `<c-callout tone title>` in an FLS panel or dialog template (`info`, `warning`, `error`,
  `success`), never a hand-built `bg-error/10` box. The framework never writes `<c-callout>`: a
  host renders `<c-panel-callout>` as its own callout. The close control is
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
  so a person adds one, reads the outcome and adds the next. `ADD_ANOTHER_BUTTON` is the one
  "Add and add another" button. In `form_valid`, `wants_add_another(ctx)` detects it and
  `add_another_response(ctx, events, "Added <name>.")` returns the dialog again with an empty form
  and that status message, keeping it open while the panels behind it refresh. Put the button
  ahead of "Add" in `submit_buttons` (`CreateInstanceAction` does). A textarea that asks for one record per line is an import wearing a form's
  clothes; a list goes to an import page with a preview.
- A record's own name is a field with a Save button on its Settings panel, posted inline to the
  `edit` action (`renders_in_footer = False`), not a dialog.
  Dialogs are for confirmations and multi-field forms.
- An inline form works with JavaScript off: `partials/inline_record_form.html` carries a method,
  an action and a CSRF token, and a `FormPanelAction` with `renders_in_footer = False` answers a
  POST that has no `HX-Request` header with a 303 to the page, the save or the field errors as a
  flash. A template that renders its own inline form carries the same three, and a test that
  reads such an action's fragment sends `HX-Request: true`.
- Entering an email for a person who may already exist searches as you type and offers the
  matches, so the person picks rather than remembers.
- An inline form in a panel (a record's name on its Settings tab) shows a field error as one line
  under its field: the message alone, never prefixed with the field's label, with `role="alert"`,
  and the input names it with `aria-describedby` and carries `aria-invalid`. It gets no notice
  box and no error summary.
- An element that takes focus only by script, so a screen reader announces it (a result heading,
  a notice, an error summary: `tabindex="-1"`), shows no outline. One shared rule does this.
  Buttons, links and fields keep their focus rings.

### Forms with a file field

A `ModelForm` with a `FileField` or `ImageField` on a `FormPanelAction` (`EditAction`,
`CreateInstanceAction`), in a dialog or the inline record form, uploads with no host code beyond
the form. The framework does the rest:

- A form with a file field posts as `multipart/form-data` (`form.is_multipart`, in `modal/form.html`
  and `partials/inline_record_form.html`).
- A field whose widget is exactly Django's `ClearableFileInput` gets `PanelClearableFileInput`:
  "Current file:" and the basename, and a "Remove" checkbox when the field is not required. A form
  that declares a widget of its own, a subclass included, keeps it.
- A browser cannot be handed a file back, so after a 422 the file input is empty. Each file field
  the person had filled in and that has no error of its own gets `CHOOSE_AGAIN_MESSAGE`.
- While a file is going up, the submit button's loading text reads "Uploading…".
- The discard prompt counts a chosen file as a change.
- A request that fails with nothing to swap in (a 413 or 5xx, a network error) shows a
  `role="alert"` message in the form's `[data-request-error]` element, and Save works again. A
  413 says the file may be too large; anything else says the changes could not be saved. A 403
  or 404 from a user's own submit reloads the page instead, except inside
  `[data-htmx-owns-errors]`; any other 403 or 404 gets the message. A template that renders its
  own form needs the element too.

The host owns:

- The storage alias on the model field, chosen per `Skill(fls-dev:file-storage)`.
- Size and type validators on the form or the model field. The framework limits neither.
- A reverse-proxy body limit (nginx `client_max_body_size`) at or above the largest file the
  validators allow. Below it, the proxy answers 413 before Django runs and the person sees the
  "file may be too large" message, not a field error. A proxy that drops the connection mid-upload
  shows the generic request error instead.
- A form that accepts Django's `(data, files)` arguments. `FormPanelAction.get_form_kwargs` passes
  `files`, so a form whose `__init__` is `def __init__(self, data=None, *, ...)` raises
  `TypeError`. Take `files` after `data` and pass both to `super().__init__(data, files)`.

A response that carries the out-of-band toast from `partials/messages.html` gets no framework
message: the toast is the message. A host that shows a failed response some other way sets
`event.detail.requestConfig.panelErrorShown = true` in its `htmx:beforeSwap` handler; without the
flag, the person sees both.

A `refresh_on_change` request is a GET and carries no files, so a file field's errors do not stop
the dialog re-rendering, and a file already chosen is dropped. Put file fields after the fields
that refresh the dialog.

The "Remove" checkbox's id is the file input's id plus `_clear`, so it follows the form's prefix
and `auto_id`.

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
`px-6 py-4` or `bg-error/10`), `test_no_framework_template_calls_the_host_callout` (no `<c-callout>` in any framework
template), `test_every_dialog_loading_text_ends_in_the_ellipsis_character`,
`test_every_dialog_disables_only_its_own_submit_buttons`,
`test_no_dialog_form_with_a_find_selector_holds_an_element_that_issues_its_own_request`,
`test_no_educator_module_sets_the_modal_trigger_template_by_hand`,
`test_no_template_hand_writes_a_table_outside_the_table_components`,
`test_no_button_hand_writes_a_touch_height`, `test_only_the_dialog_footer_makes_a_button_44px_tall_on_a_phone`
`test_every_expand_chevron_turns_when_its_control_opens` and
`test_every_entry_trigger_names_its_entry` (every `<c-modal-trigger>` in
`editable_list_entry_triggers.html` passes an `aria_label` naming its entry). In the browser,
`educator_interface/tests/playwright/test_touch_targets.py` checks that a small button keeps its
desktop height on a phone, that its hit area is 44px, and that a dialog footer's buttons are 44px tall.
Run that file after any change to a panel template.

`freedom_ls/base/tests/invariants/test_app_templates_use_app_components.py`
(`test_app_templates_use_no_content_widget_or_callout_level`) fails on a content-engine widget such
as `<c-admonition>`, or a `level=` on `<c-callout>` or `<c-panel-callout>`, in any app template
outside the content engine.

Four guards cover the standalone backend:

- `freedom_ls/panel_framework/tests/test_import_guard.py` parses every `.py` file under the
  framework and fails on any import of a `freedom_ls` module outside `freedom_ls.panel_framework`
  (including a bare `import freedom_ls`). Relative imports pass. No directory is exempt, tests
  included. Reach host behaviour through a setting, as the site resolver does.
- `freedom_ls/educator_interface/tests/invariants/test_bulk_run_scoping.py` parses every production
  `.py` file under `freedom_ls/` (`tests/` and `migrations/` directories excluded) and fails on any
  `BulkActionRun.objects.<method>` other than `for_site`, `for_request` and `create`, on
  `BulkActionRun.objects` kept in a variable, and on any use of `BulkActionRun._default_manager` or
  `_base_manager`. A bare `.filter()`, `.get()` or `.all()` reads every site's runs. Its one
  allowance is the worker's `_base_manager` read in `panel_framework/bulk_runs.py`, which filters by
  the site id its task was given. `BulkActionRun.site` has `related_name="+"`, so there is no
  `site.bulkactionrun_set` to read through.
- `freedom_ls/educator_interface/tests/invariants/test_framework_copies_match_base.py` holds the
  framework's private copies to their `freedom_ls.base` originals: `escape_csv_formula`,
  `EchoWriter`, `Setting` and `AppSettings` must have identical source, and `FORMULA_TRIGGERS`,
  `UTF8_BOM`, `_E164_PHONE_NUMBER` and the date display formats identical values. It also pins
  `pagination_suffix` (`freedom_ls/base/templatetags/pagination_tags.py` and the framework's
  `data_table_tags.py`), `assert_no_horizontal_overflow` and `QA_VIEWPORTS` (`freedom_ls/tests/playwright_helpers.py`
  and `freedom_ls/panel_framework/tests/playwright/helpers.py`), and the body of the `panelDropdownMenu`
  Alpine component against `dropdownMenu` in `base`'s `alpine-components.js`. Change each pair in
  both places at once.
- `freedom_ls/panel_framework/checks.py` holds `REQUIRED_ICON_NAMES`, the icon names the
  framework's templates draw. A framework template draws an icon with `<c-panel-icon>`, never
  `<c-icon>`; FLS's wrapper in `freedom_ls/base/templates/cotton/panel-icon.html` forwards it to
  `<c-icon>`. The framework's default reads each icon's paths from
  `templates/panel_framework/icons/<name>.html`. `uv run manage.py check` reports E010 for a name
  `c-panel-icon` cannot render and W003 for one it renders empty. When a framework template draws
  a new icon, add its name there and its body template beside the others.

Three more files sit beside the template invariants in `tests/invariants/`:

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
- A list row's or card's Edit, Remove and other entry buttons sit in a footer under the entry's
  title and detail: every entry's buttons start at the title's left edge, the same distance under
  its text, side by side, each as wide as its label.
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
  badges sit on a line under the name and email, their left edge on the name's left edge; an
  expanded row that names the parent row's person again shows the name with no second avatar.
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
- A numbered list with per-entry actions (the course outline) is a data table: rows spaced by
  their cell padding only, the chevron and the small action button inside the row next to its text.
  A short editable list is an `EditableListPanel`.
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
