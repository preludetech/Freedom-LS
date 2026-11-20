# A panel for a short list a user edits

Spec 2 of 3 in the Account area on panels effort. Read the "Account area on panels" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The panel framework gains a panel for a short list of entries that belong to one object: the
user adds an entry, edits one, and removes one, each from the panel. It is lighter than a data
table: no search, sort, filters, pagination, export or bulk actions. Each entry shows a short
summary the consumer defines.

## Why

`learner-public-profile-2-profile-and-page` needs a work experience list a learner adds to,
edits and removes from, and `learner-public-profile-4-certificates` has the same shape. The only
framework answer today is a `DataTablePanel` with hand-built row actions. A data table carries a
`table_key`, search, sort and export rules built for management tables, which is heavy for a
list of five entries, and a per-row edit needs a hand-written row-scoped action for each list.
Building the list shape once in the framework keeps the public-profile specs from inventing it.

## What is settled

- The owner decided: this is a new framework panel, not a `DataTablePanel`. The public-profile
  and certificate specs use it.
- It lives in `freedom_ls/panel_framework`, generic, with no FLS name in it.
- Add, edit and remove are framework actions. Adding and editing a multi-field entry happen in a
  dialog (the skill's rule: dialogs are for multi-field forms). Removing asks for confirmation.
- A per-entry edit or remove resolves its entry from the URL, scoped to the parent object, so a
  user can never reach an entry of another object. Entries outside the scope return 404.
- The consumer supplies the model, the form, the query for the entries and their order, and the
  entry summary. The framework renders and wires them.
- The panel has an empty state, and every per-entry button names its entry, as the
  panel-framework skill requires.
- Panels listening for the list's event refresh after a change, through `success_events` and
  `refresh_events` like every other action.
- The dev reference page at `/panel-framework/` shows it, with framework tests and the invariant
  checks the skill names.
- No consumer page changes in this spec.

## Open until the spec

- Whether entries can be reordered by hand, or the order always comes from the consumer's query.
  The work experience list is reverse chronological, so manual order is not needed for it.
- A maximum number of entries, and what the panel shows when it is reached.
- The name of the panel class, checked against `fls-dev:domain-glossary`.

## Out of scope

- File fields on entries: `learner-profile-use-panels-framework-1-file-upload-actions` supplies
  them, and a consumer combines the two.
- Inline editing of an entry inside the list.
- Any consumer panel.

## Resources

- `spec_dd/1. next/learner-profile-use-panels-framework/research_panel_framework_fit.md`,
  "Repeatable list with add, edit, remove"
- Skills: `fls-dev:panel-framework`, `ds:htmx`, `fls-dev:domain-glossary`
