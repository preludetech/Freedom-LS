# Gather the generic panel code into the framework

Spec 1 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Everything in the panel framework's shape that today sits outside `freedom_ls/panel_framework` moves
into it, and the framework's own tests then prove all of it without the educator interface.

The code that moves, from the app it lives in now:

- **`educator_interface`**
  - `ReasonMixin`, `ReasonForm` and the `reason_field` partial (the optional-reason confirm dialog).
  - `LazyBodyPanel`, its two templates and `render_region`, with `ReportTooLargeError` replaced by a
    framework error type the host raises.
  - The generic half of `EducatorBulkAction` (the `permitted` / `skip_reason` / `perform` / `sentence` /
    `consequences` template) and the table-keyed bulk-action registry (`register_bulk_action`,
    `bulk_actions_for_table`). Organisation scoping, `can_on_any` and notification calls stay in
    `educator_interface`, which subclasses the generic class.
  - `ShowInactiveFilter` and `AuditPeriodFilter`, generalised enough to be named for what they do
    (a toggle filter; a period filter taking a field name and preset windows) and kept in `filters.py`.
- **`base`**: the `modal-trigger` and `quick-view-trigger` cotton components, which framework templates
  already render.
- **`deployment`**: the `BulkActionRun` part of `housekeeping.py` (reaping unpicked and orphaned runs,
  deleting stale previews, retention deletion) becomes a callable in the framework that a host
  schedules. FLS's `housekeeping.py` calls it and keeps its own `LearnerImport` handling, which goes
  through the `RunRecord` protocol.
- **`comms`**: the framework's sidebar nav no longer reaches into `comms` for its poller and event
  (see "Open until the spec").

The framework's own test suite then covers:

- Every cotton component directly. Today there is no direct test for `panel-search-field`,
  `panel-filter-toggle`, `panel-applied-filter`, `panel-attention-row`, `panel-stat-row`,
  `panel-definition-row`, `data-table`, `data-table-card`, `data-table-cells/*` and `modal-header`, nor
  for the two cotton components that arrive from `base`.
- The filters: the toggle and period filters plus the existing four, including widget and URL toggling.
  `test_filters.py` has seven tests for all of them.
- The Alpine components `tableSelection`, `listRefresh`, `headerRefresh` and the instance-title update,
  in browser tests on stub panels. Today only `educator_interface` Playwright tests drive them.
- A check that every Alpine name used in a framework template is registered in the framework's
  `alpine-components.js`.
- The moved code itself: the reason dialog, lazy panels and the generic bulk action and registry (their
  tests move out of `educator_interface/tests`, for example `invariants/test_reason_mixin.py`, and
  `educator_interface` keeps tests only for what it still owns), and the housekeeping sweep.

The framework declares a public surface: an `__all__` (or one documented module) around the names a host
imports, the moved ones included, so later specs and the release know what is promised and what is
private. `views.py` holds about 25 helper functions that are not API.

## Why

Every later spec in the effort assumes the framework is one self-contained unit. Today it is not:
generic code lives in five apps, and a host that installed the framework alone would get bulk-run rows
stuck in `running` forever (no sweep), no reason dialog, no skeleton-first panels and no way to register
bulk actions the way FLS does. The coupling audit and the completeness research list the same pieces.
Moving them first, alone, means specs 2 and 3 work on the final layout instead of chasing code across
apps, and the test gaps are closed while the educator interface can still be used as a cross-check.

## What is settled

- The three colliding specs have landed, so the framework templates and JS are quiet while this runs.
- Specs 2 to 6 do not start until this lands. 2 and 3 run in parallel after it.
- The housekeeping sweep is a plain callable the host schedules. It is not a management command and not
  a scheduler the framework owns. FLS's `housekeeping.py` calls it.
- `ReportTooLargeError` is not imported by the framework. A framework error type that the host raises
  takes its place; `educator_interface` and `reports` raise or translate to it, and the message the
  region shows is carried by the error.
- `ReasonMixin` moves as it is: an optional reason. The required-reason dialog and the reason-choice
  list are spec 2's.
- `LazyBodyPanel` moves without an `as_of` value. The `as_of` stamp is spec 2's.
- The generic bulk-action class and registry are what the educator-side classes subclass. Behaviour of
  every existing FLS bulk action is unchanged, and so are their capability and scoping rules.
- Every moved symbol keeps its behaviour. Imports in `educator_interface`, `comms`, `reports`,
  `learner_management` and `learner_interface` are updated to the new location. Old import paths are not
  kept as aliases, since FLS is the only importer.
- The app keeps its current label and the `freedom_ls.panel_framework` import path. The label and the
  rename are spec 5's, and the framework's Python imports of FLS (`base.app_settings`, CSV helpers, site
  resolution) are spec 3's. This spec adds no new `freedom_ls` imports to the framework beyond what the
  code it moves already needs, and lists any it must add so spec 3 sees them.
- The framework's templates still extend and call the FLS page shell and primitives. The host contract
  for them is spec 4's.
- `RunStatus`, `BulkActionRun`, `scope_lookup` and `run_records` are part of the public surface; other
  FLS apps import them.
- Out of the completeness research's list, this spec carries G2, G4, the `ReasonMixin` / `LazyBodyPanel`
  moves of G5 and G6, G7, G8 (the test half) and G9. G1 is spec 5's, G3 is spec 4's, the new halves of
  G5 and G6 are spec 2's, and G10 is settled by the order of the effort.

## Open until the spec

- **Where `sidePanel`, `refreshTimer` and the `conversationChanged` event live.** The framework's
  `sidebar_nav.html` hard-codes `x-data="refreshTimer"` and `conversationChanged from:body` for menu
  counts. `refreshTimer` is defined in `comms/static/comms/js/alpine-components.js` and
  `conversationChanged` is a `comms` event. `sidePanel` is defined in
  `base/static/base/js/alpine-components.js` and used by the framework's `table_toolbar.html`.
  Recommended default: `sidePanel` and `refreshTimer` move into the framework's
  `alpine-components.js`; `comms` then uses the framework's `refreshTimer` (it already loads the
  framework JS for its `c-panel-*` components). The nav item carries the event names its count refreshes
  on, so the host supplies `conversationChanged` for its messages item and the framework names no
  `comms` event. The spec confirms nothing else in `base` depends on `sidePanel` staying where it is, and
  that the host shell contract for the sidebar stays spec 4's.
- **Whether `ShowInactiveFilter` and `AuditPeriodFilter` keep their current constructor shape** or take the
  more general one. The spec decides, provided every current FLS table behaves the same.

## Out of scope

- Expandable rows, compact density, the `as_of` stamp, the required-reason and reason-choice dialogs
  (spec 2).
- Cutting the framework's Python imports of FLS and the standalone test settings (spec 3), including
  the check that nothing in the framework imports `freedom_ls` outside declared hooks.
- The host page shell, theme tokens, `c-icon` names, the framework's own primitives, and the test that
  every cotton component and `{% include %}` resolves with only the package installed (spec 4).
- The app label, the move to its own repo, tags and install (spec 5).
- A Playwright test of dark mode and mobile rendering of the reference page.
- Preview-then-confirm lists, the import scaffold, a sticky action rail, date, text and range filters.
- `RequiresActiveCohortMixin`, `RelationLinkColumn`, the educator quick views and the educator-only
  Alpine components (`memberRoleChooser`, `cohortChecklist`): they stay.
- Polishing the educator interface.

## Resources

- `spec_dd/1. next/extract_panels_framework/idea.md` (source idea).
- `spec_dd/1. next/extract_panels_framework/research_framework_completeness.md` (moves into this
  child): sections 2 and 3 and gaps G2, G4 to G9.
- `spec_dd/1. next/extract_panels_framework/research_coupling_audit.md` (every coupling with file and
  line, the reverse import list).
- `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md` (layout and release
  discipline).
- Code: `freedom_ls/educator_interface/actions.py` (`ReasonMixin`, `register_bulk_action`,
  `EducatorBulkAction`), `forms.py` (`ReasonForm`), `reporting.py` (`LazyBodyPanel`, `render_region`),
  `filters.py`; `freedom_ls/deployment/housekeeping.py`; `freedom_ls/base/templates/cotton/`
  (`modal-trigger.html`, `quick-view-trigger.html`); `freedom_ls/base/static/base/js/alpine-components.js`
  (`sidePanel`); `freedom_ls/comms/static/comms/js/alpine-components.js` (`refreshTimer`);
  `freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html`;
  `freedom_ls/reports/report_data.py` (`ReportTooLargeError`).
- Skills: `ds:alpine-js`, `fls-dev:alpine-js`, `ds:template`, `fls-dev:template`, `ds:testing`,
  `fls-dev:testing`, `fls-dev:playwright-tests`.
