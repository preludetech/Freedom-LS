# Research: UX patterns for a short add / edit / remove list (`EditableListPanel`)

Scope: a short list of entries one user adds to, edits and removes from (work experience,
certificates). Findings are tagged **[fetched]** (read from the cited page this session),
**[search]** (seen in a search snippet only) or **[background]** (general practice from memory,
not verified this session; LinkedIn and Material fall here, check before quoting).

## Fit with the panel-framework skill (constraints first)

From `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`:

- All triggers are `size="small"`; per-entry buttons sit in `<c-data-table-actions>`, in their own
  column on the entry's line (table) or under the entry inside its block (card). Each button's
  accessible name names its entry ("Edit Acme Ltd").
- A record row is name in `font-medium`, detail under it in `text-sm text-muted`, no dash-joined
  sentences. This is the title + detail-line layout.
- "An ordered list with an action on each entry is a data table inside `.panel-data-table`", never
  a flex list with a button at the far end. Cards when narrow (`cards_when_narrow`, container
  width). So the entry layout is already settled: table rows that become cards.
- `<c-panel-list>` is the only rule-drawing list, but it is for read-only rows; per-entry actions
  push this panel to the table shape.
- Add and edit in a dialog (`modal/form.html`), remove in `modal/confirm.html` with
  `confirm_variant` error ("Remove" is a delete, so tone `error`). Confirm must state what is true
  now and what changes, naming the record.
- Empty state: `<c-panel-empty-state>`; a table's empty row carries `hover:bg-transparent`.
- Table footer states the entry count at the left; actions with `renders_in_footer` sit in the
  panel footer. A page header holds no action: each action lives with the thing it changes.
- Dialog loading text ends in "…"; Cancel at the left, primary last; phone buttons 44px tall.
- Skill says "Add" plus "Add and add another" for adding records by hand
  (`CreateInstanceAction.submit_buttons`). Decide whether that applies to a 5-entry list; for a
  profile entry with several fields it is reasonable but optional.

## 1. Entry layout (title + detail line)

- Pattern: bold primary line (role / certificate name), muted secondary line (employer, dates /
  issuer, issue date). One or two lines; long free text is truncated or kept in the dialog.
  [background]; matches the skill's name + `text-sm text-muted` row shape.
- GOV.UK summary list: borders between rows show which action belongs to which information;
  don't remove borders when rows carry actions. [fetched]
  https://design-system.service.gov.uk/components/summary-list/
  Fits the table-row shape (row padding and table's own rules, not extra boxes).
- Consumer callable returns title + optional detail (per answers.md): the framework renders the
  detail line only when present, so one-line entries do not leave a gap.

## 2. Add button placement (header vs foot)

- Sources disagree because they serve different shapes:
  - GOV.UK add-another / MoJ add-to-a-list: the add control is a secondary button below the list,
    labelled "Add another <thing>", not a yes/no question. [fetched]
    https://design-system.dwp.gov.uk/patterns/add-another-thing/design-notes ,
    https://design-patterns.service.justice.gov.uk/patterns/add-to-a-list
  - LinkedIn profile sections and most profile editors put a "+" Add control in the section
    header, beside the section title. [background]
- For this framework: the skill says no action in the page header, a control sits beside what it
  changes, and `renders_in_footer` exists. A short list reads top to bottom, so the Add button in
  the panel footer (below the entries, after the count) is the consistent choice, and an empty
  state carries its own Add button (skill: "an empty state" trigger is small). Header placement
  is the alternative if a panel's title bar becomes a toolbar; not recommended here.
- Label includes the thing: "Add work experience", not bare "Add" (GOV.UK: same item word across
  heading and button, keep it short). [fetched, DWP page]

## 3. Per-entry Edit / Remove buttons vs overflow menu

- GOV.UK summary list uses visible text links per row ("Change", "Remove") with visually hidden
  text naming the row ("Change name"). [fetched] https://design-system.service.gov.uk/components/summary-list/
- Overflow ("kebab") menus hide actions and cost a tap; they suit many actions or dense tables.
  With exactly two actions on a short list, visible buttons win on discoverability and
  accessibility. [background]
- Fit: skill already requires per-entry buttons in their own column, small size, named by entry
  ("Edit Acme Ltd", "Remove Acme Ltd"), never two bare identical verbs in a row. Recommend two
  visible buttons (Edit, Remove), no overflow menu. If cards on narrow widths get cramped, keep
  both buttons under the entry inside its block (skill rule), not a menu.
- A row the viewer cannot act on leaves its buttons column empty (skill rule).

## 4. Remove confirmation wording

- GOV.UK/MoJ: ask the user to confirm before removing from the list. [fetched]
  https://design-patterns.service.justice.gov.uk/patterns/add-to-a-list
  GOV.UK also warns removal can have onward effects, so state them. [fetched, DWP page]
- Wording rules (background, aligned with the skill's "states what is true now and what the action
  changes, naming the records"):
  - Title: "Remove work experience?" (or "Remove <title>?").
  - Body: "Remove <title> at <detail>? This removes it from your profile. This can't be undone."
  - Buttons: "Cancel" (left, from `<c-modal-footer>`) and a verb-specific confirm, "Remove"
    (not "Yes" / "OK"), `confirm_variant="error"`, loading text "Removing…".
- Consumer-visible side effects (e.g. entry shown on a public page) belong in the body via
  `get_confirm_context`.

## 5. Empty state copy and call to action

- GOV.UK add-another notes suggest telling people up front that they can add more entries, so they
  do not try to cram everything into one. [fetched, DWP page] No empty-state guidance otherwise.
- Pattern (background): one short sentence saying what the list is for and why add one, plus a
  single primary-ish Add button inside `<c-panel-empty-state>`. E.g. "No work experience yet." and
  button "Add work experience". Avoid apologetic or instructional paragraphs; the panel title is
  the only heading (skill).
- When the cap is zero-room impossible (cap >= 1) the empty state always offers Add.
- Framework should let the consumer supply the noun and empty text; default derived from the
  entry noun.

## 6. Maximum count reached

- Neither GOV.UK page gives limits guidance. [fetched] Common practice (background): disable or
  remove the Add control and say why, rather than let the user fill a form and then fail.
- Decision already taken in answers.md: Add button replaced by a short line ("You can add up to 5
  work experiences. Remove one to add another.") and the add endpoint refuses too.
  UX notes to carry into the spec:
  - Put the line where the Add button was, plain muted text, not a disabled button with the reason
    in a tooltip (tooltips fail on touch and for screen readers; skill also forbids a disabled
    control's reason living outside the body).
  - Say the number and the way out ("Remove one to add another").
  - Server refusal (a stale page, a second tab) uses `refusal_response` / `modal/message.html`
    with status 422 and a Close footer, same wording.
  - The footer count can read "5 of 5" when a cap is set; otherwise "N entries" per the skill's
    footer rule.

## 7. Mobile layout

- Skill: table becomes cards via `cards_when_narrow` (container width, not viewport); dialogs rise
  as bottom sheets with rounded top corners and a header close control; buttons 44px tall; nothing
  cut off at 375px; each entry's buttons sit under that entry in its card.
- GOV.UK summary list page gives no mobile guidance. [fetched] Typical stacking (background):
  title, detail line, then Edit / Remove side by side, as wide as their labels.
- Add button stays in the panel footer, full label, reachable without scrolling past a long
  list; with a cap of ~5-10 entries the list is short, so no sticky bar is needed.

## 8. Focus after dialog close

- WAI-ARIA APG modal dialog: on close, return focus to the element that opened it; if that element
  no longer exists, move focus to a logical alternative. [search]
  https://www.w3.org/WAI/ARIA/apg/patterns/dialogmodal/
- GOV.UK-derived Scottish add-more-fields pattern: focus moves to a newly added field; delete
  controls are labelled per entry. Does not specify post-delete focus. [search]
  https://designsystem.gov.scot/patterns/add-more-fields
- Recommended cases for the spec (background, derived from the APG rule):
  - Cancel / Esc / close: focus back to the trigger that opened the dialog (Add button or the
    entry's Edit button).
  - Edit saved: the list re-renders (success_events / refresh_events); the old Edit button node is
    replaced, so focus the same entry's Edit button in the refreshed list, found by entry id.
  - Add saved: focus the new entry's row/Edit button, or the Add button if the entry is not
    identifiable; announce via a live region ("Work experience added").
  - Remove confirmed: the trigger is gone. Focus the next entry's Edit button, else the previous
    one, else (list now empty) the empty state's Add button. If at cap and the Add button is now
    back, focus it. Announce "Removed <title>".
  - Cap reached after Add: the Add button is replaced by text, so focus the new entry (not the
    removed button).
  - Focus-by-script elements use `tabindex="-1"` and show no outline (skill rule).
- Risk: a plain HTMX swap drops focus to `<body>`. The spec needs an explicit focus step
  (a small Alpine/JS hook or HTMX `hx-on::after-swap`), and a test.

## Open points for the spec writer

1. "Add and add another" on an entry dialog: needed or not for a list capped at a few entries.
2. Whether Remove's confirm uses the existing `ConfirmAction` / `DeleteAction` shape with a
   row-scoped `row_param` (skill: `get_row_object` 404s outside the queryset, which meets the
   "entries outside the scope return 404" requirement).
3. Focus-return mechanism after the list refreshes (section 8); no existing framework rule covers
   it, so the spec likely adds one to the panel-framework skill.
4. Where the cap line and the count sit in the footer.

## References

- GOV.UK Summary list: https://design-system.service.gov.uk/components/summary-list/
- DWP Add another thing, design notes: https://design-system.dwp.gov.uk/patterns/add-another-thing/design-notes
- MoJ Add to a list: https://design-patterns.service.justice.gov.uk/patterns/add-to-a-list
- Scottish Government add more fields: https://designsystem.gov.scot/patterns/add-more-fields
- HMRC add to a list: https://design.tax.service.gov.uk/hmrc-design-patterns/add-to-a-list (search result only)
- W3C APG modal dialog: https://www.w3.org/WAI/ARIA/apg/patterns/dialogmodal/
- Not reached: GOV.UK add-another page (404), Material Design empty-state / dialog pages,
  LinkedIn help pages. Statements about them are background knowledge, unverified.

status: ok
