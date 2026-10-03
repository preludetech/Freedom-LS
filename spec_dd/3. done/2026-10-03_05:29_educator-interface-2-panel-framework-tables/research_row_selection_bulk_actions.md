# Research: row selection and the bulk-action contract

For spec 2 (`educator-interface-2-panel-framework-tables`), read by spec 8
(`educator-interface-8-bulk-operations`), the consumer of the hook.

**Decisions taken while researching (not open questions for the spec to re-litigate):**
selection clears on any page, sort, filter or search change — it is always scoped to the
*currently rendered page* of results; the only way to act across pages is the explicit "select all
matching" mode. And row selection must work on the mobile stacked-card layout, not just the
desktop grid, even though the mockups don't draw it there — spec 2 has to design that affordance
itself. Both are folded into the recommendation below rather than left as options.

## What the idea and the mockups already commit to

`idea.md` settles: a checkbox column, an "n selected" bar that appears when anything is checked,
and a hook by which the consumer registers bulk actions receiving the selected primary keys and
the current filter, "so 'select all matching' can be offered later without changing the
contract." It leaves open exactly how "select all matching filter" is represented in the payload.

The desktop mockup (`Educator Learners.dc.html`, screen 02) shows a checkbox column (unchecked
square per row, one row checked with a filled primary-colour check), an unchecked header checkbox
in the same column, and below the table a status line reading "1 selected · showing 8 of 31
learners" — a per-page count, not a cross-page or cross-filter one. There is no "select all 31"
affordance drawn anywhere in this mockup; it shows only page-level selection and a per-row
kebab menu, no bulk-action toolbar. The mobile mockup (`Educator Mobile Learners.dc.html`,
screens M03/M04) has **no checkboxes or selection at all** — stacked cards are tap-through only,
and the M04 filter/sort sheet has no bulk-select entry point. That gap is real: the mockups were
drawn for the visual language, not the full interaction set (the roadmap's own "assumptions"
section says as much generally), and per the coordinator's decision, mobile selection is in scope
for spec 2 regardless of what the mockup omits — see "Mobile selection" below for a proposed
affordance that fits the stacked-card layout without contradicting the mockup's chrome.

`freedom_ls/panel_framework/actions.py` (spec 1's action concept) is entirely single-instance:
`PanelAction.handle_submit(ctx: PanelContext)` where `ctx.instance` is one `Model | None`, and
`has_permission(request, instance)` checks one object. There is no bulk variant today — spec 2's
selection hook and spec 8's bulk actions are a new, parallel concept, not a generalisation of
`PanelAction`, though they should probably share its permission-check shape (`has_perm` per
object, not just the first) and its "modal with confirmation, POST to an action URL" flow, per
`FormPanelAction`/`DeleteAction`'s pattern of a confirmation modal before a state-changing POST.

`freedom_ls/panel_framework/tables.py`'s `DataTable.get_rows` takes the request and an
already-scoped `queryset`, then narrows it by search/sort/page from the query string. Spec 2's
per-table-key rework (open in the idea, not yet built) will change `search`/`sort`/`page` to
`<key>-search` etc. and add declared filters read the same way. Whatever selection payload spec 2
designs must re-derive "the current filter" through this same table class, not through a second,
hand-rolled filter parser, so that spec 8's "re-evaluate server-side" step is just "call
`get_rows` again with the stored query string."

## Reference systems

**Django admin.** `ModelAdmin.actions`: a `<select>` of registered actions plus a "Go" button,
each row a checkbox named `_selected_action` (their pks), a hidden `select_across` field, and
"Select all N matching your search" link that appears once every checkbox on the page is ticked.
Clicking it sets `select_across=1` and the action view then builds the changelist's *full* filtered
queryset (`self.get_changelist_instance(request).get_queryset(request)`) rather than filtering by
the posted pks, discarding `_selected_action` entirely in that branch. So `select_across` is a
single boolean flag, not a serialised filter: it works because admin has already reconstructed the
list's queryset from the current URL/session inside the action view, independent of what was
posted. Every action receives `(modeladmin, request, queryset)` — a real `QuerySet`, already
scoped and re-filtered, not IDs. Known rough edge: with `actions_on_top` and `actions_on_bottom`
both on, only one form's `select_across` value used to get posted, since the toolbars didn't share
state client-side (Django ticket #33083). Lesson: if a page can show the selection bar/toolbar in
more than one place, they must share one client-side state, or only one of them wins.
([Django admin actions docs](https://docs.djangoproject.com/en/5.1/ref/contrib/admin/actions/), [ticket #33083](https://groups.google.com/g/django-updates/c/hOJUZiuatYs), [ticket #14742 on select_across defaults](https://code.djangoproject.com/ticket/14742))

**GitHub issues/PRs.** Selecting every checkbox on the page shows a banner: "25 issues on this
page selected. Select all issues matching this search query." Clicking that extends the
selection to everything matching the current filter/search, capped at 1000 items — an explicit,
documented ceiling past which only the first 1000 are affected. Projects imitating this pattern
(cited in the search results) commonly add an **exclude-list**: once "select all matching" is on,
individual deselection doesn't re-narrow the filter, it adds that one id to an exclusion set, so a
user can select 4,000 minus 3 without re-running the query per click.
([tthub issue on select-all-with-exclude](https://github.com/iliksis/tthub/issues/36), [Sentry issue on the 1000-item cap](https://github.com/getsentry/sentry/issues/4050))

**Wagtail bulk actions.** `wagtail.admin.views.bulk_action` registers a `BulkAction` class per
model with `execute_action(objects, **kwargs)`. The listing posts the checked ids; there is no
built-in "select all matching" that bypasses ids — Wagtail's UI instead offers the header
checkbox for "everything on this page" and a footer bulk-actions bar. A known bug (#8563) is
instructive: the JS assumed ids were always numeric and broke for UUID pks — a reminder that a pk
serialisation format (string vs int) must be treated generically, not int-typed, since FLS ids may
not all be integers everywhere.
([Adding custom bulk actions](https://docs.wagtail.org/en/stable/extending/custom_bulk_actions.html), [Issue #8563 on non-numeric ids](https://github.com/wagtail/wagtail/issues/8563))

**Filament.** Bulk actions get `$livewire->getSelectedTableRecords()`. "Select all" naively loads
every matching row into memory before invoking the action closure, which the Filament community
found times out or exhausts memory at scale; the fix under discussion is to hand the action the
*query* (so it can `chunk()`/`cursor()` or issue a single `UPDATE ... WHERE` instead of N
row-loads) rather than a materialised record list once "select all" is in play.
([Tables: performance on select-all discussion](https://github.com/filamentphp/filament/discussions/1483), [Bug: bulk action receives non-selectable records](https://github.com/filamentphp/filament/issues/19219))

**Gmail.** "All 40 conversations on this page are selected. Select all conversations that match
this search" — the same two-step disclosure as GitHub: page selection first, an explicit
click-through to extend to the full search result. Selection state does not survive navigating to
a different label/search; it's cleared, matching the general web convention that leaving the
filtered view drops the selection rather than persisting it silently — this is the same rule the
coordinator settled on for FLS: selection is scoped to the rendered page/result set, not carried
across a filter change.

**Salesforce list views.** Selects are capped per list view (a fixed small maximum, historically
in the low hundreds, enforced by a warning banner) and bulk actions with more than that go through
a separate mass-action tool (Data Loader/Process Builder), not the list view UI. The lesson that
generalises: an interactive selection UI is not obligated to scale to "everything"; past a
threshold, route to the same background-task path the CSV import already uses (spec 8 says this
explicitly: "Large selections go through the same background path as the import").

## Recommended payload shape

One contract, two shapes, discriminated by a single field, matching the `{keys: [...]} |
{all_matching: true, filter_state: ..., excluded: [...]}` sketch in the idea:

```
selection = {
    "mode": "keys",
    "keys": ["<pk>", "<pk>", ...],
} | {
    "mode": "all_matching",
    "query_string": "<the table's own querystring keys, e.g. learners-status=stalled&learners-q=mol>",
    "excluded": ["<pk>", ...],
}
```

- `query_string` is not a re-parsed filter object; it is literally the table's own prefixed query
  parameters (the `<key>-sort`, `<key>-q`, `<key>-<filter>` keys spec 2 already threads through
  `DataTable.get_rows`), captured at the moment "select all matching" is chosen. The bulk-action
  view re-derives the queryset by calling the *same* table class's `get_queryset` +
  `get_rows`-style filtering against that query string and the acting user's own request-time
  scope — never against a client-supplied list of what the filter matched, and never against a
  cached count from click time. This is the Django admin lesson: the action re-derives the
  queryset from server-owned inputs (request/session-equivalent state), not from anything the
  client asserts about which rows matched.
- `excluded` is the GitHub/tthub pattern: once "all matching" is chosen, per-row deselection adds
  to an exclusion set instead of collapsing back to an explicit `keys` list, so deselecting 3 of
  4,000 doesn't require materialising and re-posting 3,997 pks.
- `mode: "keys"` is what page-level selection posts: exactly the checked pks on the currently
  rendered page, nothing else. This is also what a plain, JS-off form posts (see below) — the
  simple case never needs the `all_matching` branch, so JS-off support does not have to include
  it.
- Every action handler receives one thing regardless of mode: a `QuerySet` re-scoped and
  re-permission-filtered server-side (see Security, below), never the raw `selection` dict, never
  raw pks trusted as-is. `mode` and its fields are consumed once, at the top of the bulk-action
  view, to build that queryset; `PanelAction`-style handlers never see the discriminated union.

This gives spec 2 one contract that spec 8 can light up "all matching" on later purely by adding
the UI affordance (the "select all N matching" link) and the `all_matching` branch of the view;
`mode: "keys"` alone is a complete, useful spec-2 deliverable and the stub action spec 2 ships can
be tested against it without spec 8's filter-re-evaluation machinery existing yet.

## Count confirmation and the safety issue

The filter is re-evaluated at *action-submit* time, not reused from when "select all matching" was
clicked — the underlying data (or the user's visible scope) may have changed between the two. The
confirmation dialog ("This will affect 312 learners") must run the same re-derivation the action
itself will run — same queryset, same scoping, same permission filter — immediately before
rendering the count, so the number shown is never stale relative to what the action does a moment
later. This is exactly the admin/Filament caution: the action must operate on a freshly-scoped
queryset, not a client-supplied count or id list taken on faith. A cheap way to get this for free:
the confirmation step and the commit step call the identical "resolve selection to queryset"
function; the confirmation step just runs `.count()` and renders instead of mutating.

## Selection persistence across pages, sort, filter, search (settled)

**Selection is always scoped to the currently rendered page of results, in both modes, and clears
whenever the table's own query string changes** — page, sort, filter or search. There is no
"carry these 6 pks over as I flip pages" behaviour: the only way to act on rows outside the
current page is the explicit `all_matching` mode, which is defined *by* the query string rather
than by pks, so a filter change while in that mode simply re-scopes what "all matching" means —
which is correct, not a bug, and matches Gmail/GitHub (leaving a search clears/redefines the
selection, it does not carry pks into an unrelated result set). Concretely:

- In `mode: "keys"`, changing `<key>-page`, `<key>-sort`, `<key>-<filter>` or `<key>-q` clears the
  selection client-side (the idea already says changing sort/filter/search resets that table's
  page; extend the same reset to selection). This also settles the "keep across pages" question
  the idea leaves implicit: no, by design — a table-scoped `Set` of checked pks that survives a
  page swap is real added complexity (checkbox states restored from client state on every htmx
  swap rather than read from the DOM) for a "select this one weird row on page 1 and another on
  page 3" case the mockup doesn't show and the idea doesn't ask for. `all_matching` is the
  supported way to act beyond one page.
- After an htmx swap of the table fragment (`outerHTML` on `<div id="<key>">`, per the idea's kept
  invariant), the whole checkbox column is replaced, so any selection state that lived only in
  checked-attribute DOM is gone unless it's tracked in Alpine state outside the swapped fragment.
  Given the "clear on any query-string change" rule above, this is fine for keys-mode: the swap
  that clears selection is the same swap that changed the query string. The selection bar
  ("n selected") should live in Alpine state scoped to the table's wrapper (outside the
  `id="<key>"` swap target, the way the search input debounce logic already has to live outside
  it per the htmx-modal-drawer-url-state research), so it disappears/updates in step with the
  swap rather than needing its own round trip.
- Selection is **not** encoded in the URL. Nothing about "these 6 pks are checked" belongs in a
  shareable, bookmarkable link — the URL contract in this spec is about what rows are *shown*
  (filters, sort, page), not what's *selected*, which is inherently a short-lived, one-user,
  one-tab interaction on top of that. `all_matching`'s `query_string` piggybacks on the table's
  already-pushed URL state, so nothing new needs pushing for it either.
- Tri-state header checkbox: checked when every row on the current page is selected, indeterminate
  (`aria-checked="mixed"`, since native `<input type=checkbox indeterminate>` has no HTML
  attribute, only a JS/Alpine-set DOM property) when some but not all are, unchecked when none
  are. It always means "this page," never silently mutates into "all matching" — the "all
  matching" affordance is the separate, explicit banner/link the GitHub/Gmail pattern uses, shown
  once the header checkbox's all-on-page state is reached, exactly like the mockup's per-page
  count suggests ("1 selected · showing 8 of 31") is the room this pattern fits into.

## Mobile selection

The mockups don't draw this, so spec 2 is designing new affordance, not matching one. The
underlying contract does not change for mobile — same `mode: "keys" | "all_matching"` payload,
same server-side re-derivation — only the *markup* that produces `<key>-selected` values differs,
because stacked cards (`Educator Mobile Learners.dc.html`, M03) have no grid header row to host a
header checkbox and no checkbox column to host a row checkbox.

Recommendation: give each stacked card a small checkbox at its leading edge (before the avatar),
always visible rather than revealed by a long-press or swipe gesture. Long-press-to-select is a
common native-app pattern but fails the project's own stated preferences twice over: the roadmap's
denied-experience rule prefers explicit, visible affordances ("controls the user cannot use are
hidden, not disabled" — the same instinct argues for visible-not-gestural here), and a gesture with
no visible trigger is a discoverability and accessibility problem (screen readers and keyboard
users have no equivalent to "long-press"), which the idea's plain-GET/JS-off invariant already
leans against for the rest of the table. An always-visible leading checkbox costs a little card
density but needs no gesture layer and degrades to a plain checkbox in a plain `<form>` exactly
like the desktop column does.

Because cards have no header row, "select all on this page" moves into the toolbar that already
sits above the list on mobile (next to "Filter" and "Sort" in M03, or as a new small "Select" /
"Select all" control that appears once any card is checked — mirroring how the desktop header
checkbox only starts mattering once one row is checked there too). Concretely: an unobtrusive
"Select" toggle in that toolbar switches the list into selection mode (each card's checkbox
becomes visible/enabled — it can still be present-but-visually-quiet outside selection mode so
there's no layout jump), and once at least one card is checked, replace the bottom tab bar
(dashboard/cohorts/learners/more) with the same "n selected" bar and its action buttons — the same
overlay-the-tab-bar convention common to mobile multi-select UIs (a contextual action bar taking
over the bottom navigation's position while selection is live), which fits neatly with M03's
existing 68px bottom bar and avoids inventing a second new UI region. The bar itself is the same
`aria-live="polite"` region as desktop, "n learners selected" text, with the bulk actions (or a
"select all matching" link) as real buttons, not icons only.

Exactly the same clearing rule applies: opening the filter/sort sheet (M04) or submitting a search
clears the mobile selection, since that's a `<key>-*` query-string change like any other, and
`all_matching` mode still works identically underneath — it's still "the table's query string plus
an exclude-list," regardless of which layout rendered the checkboxes that built the initial `keys`
selection.

## Accessibility

- Each row checkbox needs an accessible name tied to the row's subject, not just "select row":
  `aria-label="Select Naledi Kwena"` (or a visually-hidden `<label>` naming the row's primary
  column), so a screen-reader user tabbing the checkbox column hears who they're selecting, not an
  undifferentiated "checkbox." The same rule applies to each mobile card's leading checkbox.
- The header checkbox needs `aria-label="Select all on this page"` (never bare "select all," to
  avoid ambiguity with the separate "select all matching" affordance) and, per the W3C APG mixed
  checkbox pattern, `aria-checked="mixed"` plus JS-managed `indeterminate` for the partial state.
  On mobile, the equivalent "Select all on this page" control in the toolbar carries the same
  label and mixed state.
  ([W3C APG mixed-checkbox example](https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/examples/checkbox-mixed/))
- The "n selected" bar is an `aria-live="polite"` region (not `assertive` — selection count isn't
  urgent enough to interrupt) so a screen-reader user checking/unchecking rows hears the count
  update without having to navigate to the bar. Text should read as a full sentence ("3 learners
  selected"), not just a number, since a live region announces its full text node each time.
- Position: pinned to the bottom of the table (matching the mockup's placement below the rows,
  beside pagination) on desktop, or replacing the bottom tab bar on mobile as described above. A
  sticky-top bar as a desktop table grows tall is a later refinement, not spec 2's default.
- Keyboard shift-click range selection: a nice-to-have, explicitly not required by the idea or the
  mockup (which shows no keyboard-selection affordance). Recommend leaving it out of spec 2's
  scope — it's pure client-side Alpine behaviour that can be added later without touching the
  server contract, since it only changes which checkboxes end up `checked` before the same
  `mode: "keys"` payload is built.

## Security

- Every bulk-action POST goes through Django's normal CSRF protection, the same
  `hx-headers='{"X-CSRFToken": ...}'` global convention the project already uses; no special-casing
  needed because the payload shape (form-encoded pks or a query string) is unremarkable POST data.
- **Never trust posted pks as the action's scope.** The bulk-action view re-filters every posted
  pk (in `mode: "keys"`) through the same scoped, permission-checked queryset the table itself
  would render — `Model.objects.filter(pk__in=posted_pks) & <the table's own scoped queryset>` —
  so a pk for an object in another organisation, or one the user's role can't act on, silently
  drops out rather than raising. This mirrors `has_permission` being checked per-object in
  `panel_framework/actions.py`'s single-instance actions (`EditAction.has_permission`,
  `DeleteAction.has_permission` both check the specific instance, not just "has the model
  permission somewhere") — spec 8's bulk actions need the same per-object check inside the
  queryset intersection or the loop that acts on it, not only a top-level "may use this action at
  all" gate.
- **Cap the number of pks accepted in `mode: "keys"`.** A posted list of pks is bounded by
  ordinary Django `DATA_UPLOAD_MAX_NUMBER_FIELDS`/body-size settings already, but the action
  itself should apply its own explicit ceiling (a few hundred, matching Salesforce's list-view cap
  and spec 8's "large selections go through the same background path as the import") so a
  hand-crafted POST with tens of thousands of pks can't force a synchronous action to iterate an
  unbounded queryset inline. Past the cap (in either mode), route through the same background-task
  path spec 8 already commits to for the CSV import.
- In `mode: "all_matching"`, the `query_string` is validated exactly the way a normal table-load
  GET validates it (declared filters only, unknown values ignored per the idea's existing rule),
  so a crafted query string can't smuggle anything the filter declarations wouldn't otherwise
  accept.

## Behaviour with JavaScript off

The idea's invariant — every URL a table can push renders a full page on a plain GET, bulk actions
are POST — is compatible with a no-JS degradation as long as spec 2 builds the selection UI as a
real `<form>`, on both layouts:

- The checkbox column (desktop) or each card's leading checkbox (mobile) is a set of real
  `<input type="checkbox" name="<key>-selected" value="<pk>">` inside one
  `<form method="post" action="...">` wrapping the whole table fragment (or the table posts to an
  action URL that includes the table's key so the handler knows which `<key>-selected` name to
  read). With JS off, checking boxes and clicking a bulk-action's submit button is a perfectly
  normal form submission — the browser posts every checked value, no different from any HTML
  checkbox list, and the server-side view is `mode: "keys"` with those posted values as `keys`.
  No JS is needed for the *core* keys-mode bulk action to work, on either layout.
- What JS off necessarily loses: the "n selected" live-updating bar (no live DOM update without
  JS, though the *count* still shows up fine after a full-page POST-then-redirect/re-render
  cycle), the tri-state header checkbox's indeterminate visual (an unscripted header checkbox can
  only be a plain "select all rows in this HTML form," which is actually still correct and useful
  as a real `<input>` — browsers give "select all checkboxes in a form" for free with a bit of
  inline behavior, but the mixed/indeterminate *visual* state needs JS; without it the header
  checkbox is just binary and can be omitted or left as decoration with no JS fallback expected),
  the mobile "Select" mode toggle (without JS, the per-card checkboxes can simply be always
  present rather than hidden until toggled), and "select all matching" (which is inherently a
  JS-mediated concept — an extra link/button that swaps the form's hidden fields — so it degrades
  to "not offered" with JS off, which is acceptable: the plain keys-mode form with the current
  page's rows checked stays the no-JS path on both layouts).
- The confirmation step ("this will affect N learners") is itself a modal in the JS-enabled build,
  but per `DeleteAction`'s existing pattern (a POST leads to a confirmation view first, and only a
  second POST with confirmation actually acts, per `panel_framework`'s delete-confirmation
  template), the no-JS path is: first POST renders a confirmation *page* (not a modal — a real
  page with the count and a "confirm"/"cancel" button, both real submits), second POST commits.
  This is exactly the two-step GET-then-POST-confirm pattern the CSV import already uses
  (upload → preview → result), so spec 8's bulk actions can reuse the same shape rather than
  inventing a modal-only flow that has no JS-off equivalent.

## Recommendation summary

1. One selection contract with two modes (`keys`, `all_matching`), discriminated by a `mode`
   field, `all_matching` carrying the table's own prefixed query string plus an `excluded` list —
   not a serialised filter object of its own. Spec 2 ships `keys` fully and wires the `mode` field
   so spec 8 can add `all_matching` without changing what already exists.
2. The bulk-action view always resolves `selection` to a fresh, scoped, permission-filtered
   `QuerySet` before anything downstream sees it — action handlers never see raw pks or the
   `selection` dict. This is what makes "the filter must be re-evaluated server-side at action
   time" true by construction rather than by discipline.
3. Selection is always scoped to the currently rendered page/result set: it lives in client-side
   (Alpine) state scoped to the table wrapper, clears on any `<key>-*` query-string change (page,
   sort, filter, search) in both layouts, and is never pushed to the URL. Acting beyond the
   current page is only ever done through explicit `all_matching` mode.
4. Row selection works on both layouts. Desktop keeps the checkbox column and tri-state header
   checkbox. Mobile gets an always-visible leading checkbox per card (never a long-press gesture,
   for discoverability and accessibility), a "Select all on this page" toolbar control standing in
   for the header checkbox, and the "n selected" bar replaces the bottom tab bar once selection is
   live — new affordance the mockup doesn't draw, built on the same underlying contract.
5. `aria-live="polite"` selection-count bar on both layouts, named checkboxes, `aria-checked=
   "mixed"` header/toolbar control, shift-click range selection deferred as a later, contract-free
   enhancement.
6. A server-side cap on accepted pks/`all_matching` size, routing anything above it through the
   same background-task path spec 8 already uses for CSV import.
7. Build the whole thing as one real `<form>` with named checkboxes, on both layouts, so a plain
   no-JS submit still performs the core (keys-mode, page-scoped) bulk action; confirmation is a
   real intermediate page/POST, not only a modal, following `DeleteAction`'s existing confirm-then-
   act shape.

## References

- [Django admin actions documentation](https://docs.djangoproject.com/en/5.1/ref/contrib/admin/actions/)
- [Django ticket #33083 — select_across lost with both toolbars on](https://groups.google.com/g/django-updates/c/hOJUZiuatYs)
- [Django ticket #14742 — per-action select_across default](https://code.djangoproject.com/ticket/14742)
- [Wagtail: Adding custom bulk actions](https://docs.wagtail.org/en/stable/extending/custom_bulk_actions.html)
- [Wagtail issue #8563 — bulk actions assumed numeric ids](https://github.com/wagtail/wagtail/issues/8563)
- [Filament discussion #1483 — performance of select-all bulk actions](https://github.com/filamentphp/filament/discussions/1483)
- [Filament issue #19219 — bulk action receiving non-selectable records on select-all](https://github.com/filamentphp/filament/issues/19219)
- [tthub issue #36 — select-all-matching-filters with an exclude list](https://github.com/iliksis/tthub/issues/36)
- [Sentry issue #4050 — 1000-item cap on bulk merge/resolve](https://github.com/getsentry/sentry/issues/4050)
- [W3C ARIA APG — mixed/tri-state checkbox example](https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/examples/checkbox-mixed/)

Local sources read: `spec_dd/1. next/educator-interface-2-panel-framework-tables/idea.md`,
`spec_dd/1. next/roadmap.md` (Educator interface rebuild section),
`spec_dd/1. next/educator-interface-8-bulk-operations/idea.md`,
`freedom_ls/panel_framework/actions.py`, `freedom_ls/panel_framework/tables.py`,
`spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/Educator Learners.dc.html`,
`spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/Educator Mobile Learners.dc.html`.

status: ok
