# Panel framework tables

Spec 2 of 12 in the educator interface rebuild. Read `../educator-interface-full-polish/spec-order.md` first. Depends on spec 1. Runs in parallel with 3, 4 and 5.

## What

Make the framework's data table a complete thing. Move it out of `base`, give every table its own query-string namespace so several tables can share a page, add declared filters that survive pagination, row selection with a hook for bulk actions, an export hook, and a stacked-row rendering below the `md` breakpoint.

## Why

Two behaviours block everything the mockups' learner table needs. Sibling tables on one page share `?page`, `?sort` and `?search`, so a full-page load of `?page=2` pages every table on the page. Pagination links rebuild the query string from a fixed set of names, so any filter added to a table has to be hand-threaded through an escape hatch at every call site. Both are small fixes, and both were verified against the current code. The sort links also interpolate the search text into a URL without encoding it.

The table markup lives in `base` for historical reasons. Cotton's component namespace is flat, so moving `data-table*` into `panel_framework` is invisible to call sites and to theme overrides. `c-pagination` stays in `base`; it was also used by the deleted progress matrix and is a general component.

The library question was asked and answered. `research_tables2_viability.md` costs out django-tables2 against FLS's rendering, htmx and multi-tenancy constraints and finds the two behaviours FLS needs are about twenty lines each locally, while the library would need an FLS-owned template copy, a mixin ban enforced by test, and a hard dependency. Build locally. Copy only its query-string prefix convention. Do not reopen this without new evidence.

## What is settled

**Location.** `cotton/data-table.html` and `cotton/data-table-cells/` move to `panel_framework`. `cotton/pagination.html` stays in `base`. The unreferenced byte-identical copies of `list_view.html` and `instance_details_panel.html` under `educator_interface/partials/`, and the stale `panel_container.html` beside them, are deleted if spec 1 has not already done so.

**Per-table key.** Every table declares a stable key (`learners`, `registrations`), never a position. Its DOM id and its query parameters derive from it: `<key>-sort` with a leading `-` for descending, `<key>-page`, `<key>-q` for search, `<key>-<filter>` for each declared filter. A table reads only its own keys and builds every link from a copy of `request.GET` with its own keys changed, so the other tables' state and anything else in the query string survive. Changing sort, a filter or the search resets that table's page.

**Pushing state.** Sort, filter and page changes push the URL. Search-as-you-type replaces it, debounced, with in-flight requests cancelled. The pushed URL is the real page URL with every table's state in it, so reload and share work and a plain GET renders the full page. The search form's request URL is the current URL minus the table's own keys, so htmx does not append a duplicate.

**Declared filters.** A table declares filters the way it declares columns: a choice filter (status, cohort), a boolean toggle (show inactive), a related-object filter. They render as a toolbar above the table matching the mockup's "Cohort", "Status", "Add filter" chips. Filter values are validated against the declaration; unknown values are ignored, not errored.

**Row selection.** A checkbox column, a "n selected" bar that appears when anything is checked, and a hook by which the consumer registers bulk actions that receive the selected primary keys and the current filter, so "select all matching" can be offered later without changing the contract. Spec 8 registers the first actions. This spec ships the mechanism with one stub action under test.

**Export hook.** A table can declare that it exports, and the framework serves the current rows as CSV at a stable URL derived from the table's URL and key, honouring the table's filters and scoping. Column headers come from the column declarations. Spec 10 uses it for the roster.

**Mobile.** Below `md`, rows render as stacked cards per the `Educator Mobile Learners` mockup. Sorting and filtering move into a sheet opened from a "Filter and sort" button. Same query parameters, same server rendering.

**Invariants kept.** The table's fragment root stays `<div id="<key>">` swapped with `outerHTML`. The Playwright tests keep asserting a swap never nests a `section` wrapper. Every URL a table can push renders a full page on a normal GET, with JavaScript off.

**Default page size** moves from 5 to something sensible for an admin table and is declared per table.

## Open until the spec

- Whether filter declarations should be Django form fields or a small purpose-built class. Form fields give validation and widgets for free but drag in form rendering; a small class is lighter and matches how columns are declared.
- How "select all matching filter" is represented in the bulk-action payload, so spec 8 does not need a second contract.

## Out of scope

- The bulk actions themselves, the CSV import, and the roster export's content. Specs 8 and 10.
- Column-level permissions. If a role must not see a column, the consumer declares a different table.

## Resources

- `research_tables2_viability.md`, why the table layer is built locally and what any future library adoption would have to guarantee.
- `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, section 3, for the prefix convention, `{% querystring %}` limits, `hx-push-url` versus `hx-replace-url`, and the history pitfalls.
- `../educator-interface-full-polish/Educator LMS Interface Design/Educator Learners.dc.html` screen 02, and `Educator Mobile Learners.dc.html` screens M03 and M04.
- Skills: `fls-dev:template`, `ds:htmx`, `fls-dev:frontend-styling`, `fls-dev:playwright-tests`.
