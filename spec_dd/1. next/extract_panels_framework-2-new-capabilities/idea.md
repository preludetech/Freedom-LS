# Panel framework: new capabilities

Spec 2 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The panel framework gains three generic capabilities. Each ships with framework tests (unit, and
Playwright where it has Alpine behaviour) and an entry on the component reference page
(`panel_framework/reference.py`). No consumer adopts them here.

1. **A required-reason dialog with an optional reason-choice list.** Built on `ReasonMixin`,
   `ReasonForm` and `reason_field.html`, which spec 1 has moved into the framework.
   - A required variant: an action sets `reason_required = True`; an empty reason is a 422 with the
     field error and the dialog re-rendered, as the optional dialog already does for an over-long reason.
   - A choice variant: an action declares a list of reasons; the dialog shows a select of them
     beside the free-text field. The submit reads both from `ctx` (the chosen reason and the text).
     Whether the text is required is the action's choice, independent of the list. The list may be
     fixed or computed per request.
   - The default stays what it is today: optional reason, no list. Existing actions are untouched.
2. **An `as_of` stamp on lazy panels.** `LazyBodyPanel` (moved in by spec 1) puts an `as_of`
   datetime in the loaded context, and its loaded template shows "as of <time>" with the time zone
   (the framework's existing date formatting). The panel's `get_loaded_context` may supply the time
   the data was actually computed (a gathered or cached value); if it does not, the stamp is the time of
   the render. A panel can switch the stamp off.
3. **Expandable table rows and a compact table density.** Both are options on `DataTable`.
   - Expandable: a `row_detail_template` renders inline detail under a row. A small Alpine toggle
     opens and closes it, a chevron control carries the accessible expanded state, and the detail is
     keyboard reachable. Without the option, nothing changes. Choosing how the detail loads (inline
     with the row, or fetched on first open) is open below.
   - Nested child rows: the course outline
     (`educator_interface/templates/educator_interface/panels/course_content.html`) hand-writes its
     `<table>` and is exempt from `test_no_template_hand_writes_a_table_outside_the_table_components`
     (`HAND_WRITTEN_TABLE_EXEMPTIONS` in `freedom_ls/panel_framework/tests/invariants/test_templates.py`).
     Its rows form a tree: a group row's chevron shows and hides further table rows, not a detail
     block. Decide whether expandable rows also cover nested child rows. If they do, the outline moves
     onto `<c-data-table>` and its exemption is removed.
   - Compact: a density option that tightens row height and padding for log-style tables, set per
     table and compatible with the mobile card layout.

## Why

The owner decided these are built before the extraction so the first package tag already has them,
and so the second project does not meet an API that changes after it installs the package.
Completeness is judged against FLS's upcoming specs (see `research_framework_completeness.md`,
section 4):

- Application review needs a required reason on `request_changes` and `reject`, and the
  multi-step applications spec needs a reason chosen from a fixed set plus free text. Today
  `ReasonMixin` only offers an optional free-text reason.
- `deadlines-7-educator-at-risk` shows when its gathered data was computed, because stale data is
  the common complaint about at-risk views. `LazyBodyPanel` has no such value.
- `design_educator_interface_audit_log` asks for a tighter, log-like table with "ideally expandable
  rows". Today only a per-cell `<details>` exists, and `data-table.html` has no row-detail slot.

Doing them after the extraction would mean building them in the package repo and tagging a release
before any consumer can use the first one.

## What is settled

- Spec 1 has moved `ReasonMixin`, `ReasonForm`, `reason_field.html`, `LazyBodyPanel` and its two
  templates into the framework, and made the framework's tests cover its components. This spec builds
  on those; it does not move them.
- All three are additive. An existing action, lazy panel or table renders and behaves as before
  unless it opts in.
- Each capability is generic: no FLS name, app or domain wording in the framework code, templates,
  or the reference page entries.
- Consumers adopt in their own specs, not here: application review and multi-step applications adopt
  the reason dialog, deadlines-7 adopts `as_of`, the audit log adopts expandable rows and compact
  density (except as under "Open until the spec"). This spec changes no `educator_interface` screen.
- The framework's tests, not a consumer's, prove each feature: stub panels and actions in the
  framework's test conftest, as the framework suite already does.
- Strings, icons and colours use the framework's existing components and role tokens; nothing
  hardcoded, so spec 4 (template contract) covers what this adds as it covers the rest.

## Open until the spec

- **Did `design_educator_interface_audit_log` build expandable rows (or a compact density)
  inside `educator_interface`?** At writing, its idea is only a TODO ("Ideally expandable rows?")
  and the design is in progress, with human review pending. Default: it did not, and this spec
  builds the feature fresh in the framework. If it did, this spec moves that code into the framework,
  generalises it to the `row_detail_template` and density options above, and changes the audit log
  tables to use the framework version in this spec, so the audit log is not left with a duplicate.
  The spec checks the audit log's merged state first and records which case holds.
- How an expandable row's detail loads: rendered in the page with the row, or fetched on first open
  (and whether it follows the `LazyBodyPanel` skeleton pattern). Default: rendered with the row; a
  fetched variant only if the spec finds the tables with thousands of rows make that too heavy.
- Whether the `as_of` stamp is a context value and a template block only, or also a small
  reusable cotton component the panels can place elsewhere. Default: template block only.
- The names of the options and the shape of the reason-choice declaration. Default: follow the
  naming of the existing action and `DataTable` options.

## Out of scope

- Adopting any capability in an FLS screen, except the audit-log move above.
- The sticky action rail for a full-screen instance view, preview-then-confirm lists and an
  import scaffold (other specs, and the effort's out of scope).
- Bulk action bar changes, filter additions, and date or range filters.
- Cutting FLS imports, theme-token and host-shell assumptions: specs 3 and 4.
- Packaging, a plugin, and developer documentation outside the component reference page.

## Resources

- `spec_dd/1. next/extract_panels_framework/idea.md` and `research_framework_completeness.md`
  (G5, G6, the expandable rows row in "Can wait until after extraction", and the section 4 table).
- `spec_dd/1. next/educator-interface-full-polish/application-review-ui/idea.md`
  (the required message on `request_changes` and `reject`).
- `spec_dd/1. next/deadlines-7-educator-at-risk/idea.md` (the "as of" time).
- `spec_dd/2. in progress/design_educator_interface_audit_log/idea.md`.
- Current code, as spec 1 will have moved it: `ReasonMixin` in `freedom_ls/educator_interface/actions.py`,
  `ReasonForm` in `forms.py`, `LazyBodyPanel` in `reporting.py`; `freedom_ls/panel_framework/`
  (`reference.py`, `static/panel_framework/js/alpine-components.js`, `templates/`, `tests/`).
- Skills: `fls-dev:alpine-js`, `fls-dev:template`, `fls-dev:icon-usage`, `fls-dev:frontend-styling`,
  `ds:testing`, `fls-dev:testing`, `fls-dev:playwright-tests`.
