# Research: known complaints about editable lists and repeaters

Topic: `known_complaints`. Spec: `EditableListPanel` (query order only, optional cap with the Add
button replaced by a limit line and the add endpoint also refusing, summary callable returning
title and optional detail, add/edit in a dialog, remove with confirmation, per-entry URL scoped
to the parent object, 404 outside scope, `success_events`/`refresh_events`).

Evidence level: web sources below are accessibility guidance, bug trackers and mailing lists.
Items marked (general) are common UX knowledge that no search result directly confirmed.

## Complaints and how the design stands

### 1. Identical "Edit" / "Delete" buttons for screen readers
- Repeated identical names are a well-documented failure. Screen reader users pull up a list of
  buttons and hear "Edit, Edit, Edit". Fix: the accessible name carries the entry
  (`aria-label="Edit <title>"`) or off-screen text.
  - https://primer.style/accessibility/descriptive-buttons/
  - https://vispero.com/?p=9046
  - https://dv.accessibility.pearsoncmg.com/resources/developers-corner/reference-library/buttons-with-same-name
  - https://jira.atlassian.com/browse/CONFCLOUD-83382 (Atlassian "Edit button has redundant accessible name")
  - Drupal tests assert unique per-row aria-labels (https://www.drupal.org/project/drupal/issues/3611426)
- Status: the idea already requires every per-entry button to name its entry. **Avoided by
  design, but the spec must pin it:** the name comes from the summary title, with a fallback when
  the title is empty or two entries share a title (add position or detail), and invariant tests
  assert unique accessible names.

### 2. Focus lost after a delete or an HTMX swap
- Removing the row removes the focused Delete button, so focus falls to `body`. Guidance: choose
  the target before removal and focus it; next entry, else previous, else the Add button or the
  list heading (`tabindex="-1"`) when the list becomes empty.
  - https://cloudscape.design/foundation/core-principles/accessibility/focus-management-principles/
  - https://lightningdesignsystem.com/accessibility/guidelines/global-focus
  - https://ripple.watermarkinsights.com/blog/focus-pitfalls/
  - https://accessibility.arizona.edu/web-apps/focus-management
  - https://passiro.com/web-accessibility/fixes/focus-management
- HTMX: swapped elements keep focus only if they keep the same `id`; changed ids drop the
  cursor, and after an error swap the error summary should be focused.
  - https://flaviocopes.com/courses/htmx/focus-after-a-swap/
- Dialogs: focus into the dialog on open, trapped, returned to the opener on close. HTMX's own
  modal example was reported to fail Escape and focus trap
  (https://github.com/bigskysoftware/htmx/issues/1431). Careful: after Add or Edit the opener
  may be re-rendered, so "return to opener" must target the entry's new Edit button or the Add
  button.
- Status: **must address.** Not in the idea. Spec: define focus target after add (the new
  entry), edit (that entry's Edit button), remove (neighbour, else Add button / heading), and
  after cap reached (the limit line, since the Add button vanishes while focused).

### 3. No confirmation or accidental delete, and no undo
- Django admin inlines use a bare delete checkbox; a misclicked one destroys data on save
  (https://forum.djangoproject.com/t/prevent-actual-deletion-of-inlined-one-to-many-object-orphan-the-object/10507).
  Also, a new invalid inline row had no way to be removed
  (https://code.djangoproject.com/ticket/29087).
- (general) Users want undo more than confirmation dialogs; confirmations get clicked through.
- Status: confirmation is **avoided** (settled). Undo is not in scope; the spec should say so
  explicitly. The confirmation text should name the entry ("Remove <title>?") and the confirm
  button should be a distinct label, not a second generic "OK". Keep the confirm dialog's
  default focus on Cancel or the safe action.

### 4. Lost edits when a dialog closes
- (general) Complaint: Escape, backdrop click or a failed submit discards a long form. Dialog
  guidance (see focus sources above) plus the 422 handling below.
- Status: **must address.** Spec: a validation failure re-renders the form inside the dialog
  with the user's values and errors, status 422 (matches the project convention); the dialog
  does not close on error. Decide whether backdrop click closes a dirty form; the safe choice is
  that it does not.

### 5. HTMX validation errors not showing
- HTMX does not swap 4xx by default; a 422 needs the project's global handling
  (https://flaviocopes.com/courses/htmx/handle-http-errors/,
  https://four.htmx.org/docs/full). The project already returns 422 for HTMX validation errors.
- Status: **must verify** the dialog's swap target works with the existing 422 handling, and the
  error summary is focusable.

### 6. Unclear limits and order surprises
- (general, plus Django admin `max_num` behaviour which the search could not confirm) Users hit
  a cap with no explanation or a button that silently disappears; or the form lets them submit
  and then fails.
- Status: the cap line replacing the Add button is **mostly avoided**. Must address: the line
  should state the number ("You can add up to N entries"), the add endpoint refusing must give
  a clear message (and 4xx status, not a 500 or silent no-op), and a race (two tabs) must not
  exceed the cap. Count and check inside one transaction or lock the parent row.
- Order: query-order-only **avoids** hand-reorder complaints, but "I added an entry and it
  vanished to the middle or bottom" is the likely surprise. Spec: after add or edit, the entry
  appears in query position, and the panel should visibly confirm it (message, or focus on the
  entry). A consumer's query with no deterministic tie-break gives flickering order, so require
  a tie-break (for example `-start_date, -pk`) in the invariant check or docs.

### 7. Stale lists after edits elsewhere
- (general) A list shown in two places (profile page and a preview panel) stays old after a
  change. The project's answer is `success_events` / `refresh_events`, already settled. Must
  address: the list panel itself refreshes by re-fetching from the server (not by patching the
  DOM from the posted form), so it shows server-formatted values and the real order. Also,
  editing an entry deleted in another tab must return 404 with a readable message, not a stack
  trace. 404 in a dialog: define what the user sees.

### 8. Slow round trips
- (general) Every add, edit and remove costs a request, plus one to open the dialog; users on
  slow links see nothing happen. Mitigate: `hx-indicator` and disabled submit button to block
  double submit (a double click creating two entries is a classic complaint), keep the list
  query light (select_related, no N+1 from the summary callable). The summary callable runs per
  entry, so the spec should say it must not issue per-entry queries, and a test with
  `django_assert_num_queries` covers that.

### 9. Other points from the sources
- Redundant per-row Edit links read as noise to some accessibility reviewers
  (https://core.trac.wordpress.org/ticket/33002). A row-wide edit target is an option, but the
  idea settles on explicit buttons; keep them.
- Empty state: the idea has one. Keep the Add action visible and focusable there.
- Success feedback: add, edit and remove should announce via a polite live region ("Entry
  removed"); a WebAIM list suggests this (https://webaim.org/discussion/mail_message?id=27978),
  as the focus move alone does not say what happened. Weak source, but cheap.

## Summary

Already avoided by the idea and answers: identical-button naming (once pinned), bare-checkbox
deletes (confirmation), manual reorder complaints, stale sibling panels (events), cross-parent
access (scoped 404), unexplained cap (limit line, plus server refusal).

Must address in the spec:
1. Focus targets after add, edit, remove, cap reached and dialog close.
2. Unique accessible names with title fallback, plus a test.
3. A failed dialog submit keeps the dialog open with values and errors, 422.
4. Live-region announcement of changes.
5. Cap: message text, race-safe check, server refusal status.
6. Deterministic order (tie-break) and where a new or edited entry lands.
7. Double-submit protection and an indicator.
8. Summary callable must not cause N+1 queries.
9. Entry deleted elsewhere: readable 404 path.
10. Say that undo is out of scope.

status: ok
