# Research: UX patterns for educator-interface page polish

Fitted to `fls-dev:panel-framework`, `fls-dev:educator-interface` and `brand-guidelines`. It does not repeat `research_comparable_systems.md` (sections 3, 4, 5). Sources for general patterns are cited there and below; the fit is read from the project's skills and components.

## 1. Compact multi-course progress rows (item 1)

**Pattern.** A "mini-list": one row per course, each a grid of `name | thin bar | %`, rows separated by space (`space-y-2`), never a rule or box. Cap at 3, then a "+N more" link.

- **Desktop table cell.** Row grid `grid-cols-[minmax(0,1fr)_6rem_3ch]` with `items-center gap-2`. The name truncates (`truncate`, with `title` for the full text). The % is `text-sm tabular-nums text-muted`, right-aligned so the figures line up (brand rule 4, "things line up"). The cell needs a minimum width so the name is not squeezed to nothing.
- **Phone card.** The same row, full card width, with the bar growing (`1fr`) and the name on its own line above the bar if it is long. Do not change the cap or order between widths: a card is the same data in the card shape. The "+N more" link is the last line, left-aligned with the names.
- **"+N more".** A `variant="link"` text action to the learner's Courses tab. It carries an accessible name: "N more courses for <learner>". This is a link, not a popover. A popover inside a table cell adds a second interaction layer that the framework has no component for.
- **Order.** In-progress first, most recently active first (answers.md). Ties break by title so the list is stable.
- **Accessibility.** Percentage text always shows (WCAG 1.4.1). The bar has an accessible name that includes the course name.

**Fit.** `<c-panel-progress-bar>` exists, but it draws its own `flex` row with an `h-2` bar and a `w-full` `<progress>`, and it does not take the course name as a visible label in a grid. Two options for the spec:
1. Reuse it with `label="<course title>"` (aria-label) and place the visible name in a wrapper beside it. The bar is `h-2` (8px); "thin" means 4 to 6px, so it needs a size prop (`size="thin"`, `h-1.5`).
2. Add a small row component, `panel-course-progress-row`, that owns the grid, truncation and the cap. This keeps the markup out of every host template. Prefer this since the Courses column and the phone card both use it. It must be a `c-panel-*` primitive, since framework templates may not call host components.

The native `<progress>` already has an implicit `progressbar` role, so the idea's `role="progressbar"` needs no extra attribute. State this in the spec so nobody adds a redundant role.

Refs: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html · https://carbondesignsystem.com/components/data-table/usage/

## 2. Course-progress table with status badges and flags (item 2)

**Pattern.** A simple data table, one row per course, one column per kind of content. Answers.md settled on a table.

| Column | Content |
|---|---|
| Course | Title as a link (row-link style, no underline). Owner line "Shared by <org>" under it when another org owns it. |
| Status | One `<c-panel-status-badge>` for the state (In progress, Completed, Not started) |
| Progress | Bar plus `%`, and the counts as muted text ("4 of 9 items") |
| Flags | Zero or more flag chips; empty when none |
| Actions | Row buttons, if any (last column) |

- **Badges versus flags.** A status badge says the state of the record, so it takes one of the five tones. A flag is an attention marker (No recorded activity, Stalled). Show it as a short badge in its own Flags column, and put the long reason into the cell's `title` or the quick view, never beside the badge. The idea already drops "Has not started any course item." since it repeats the badge. The rule to write down: the badge label carries the reason, and the reason text is shown only when it adds something the label does not.
- **One badge per fact.** Do not show "Not started" status and a "No recorded activity" flag side by side if they mean the same thing. Say in the spec which wins (the flag, since it is the one that asks for action).
- **Counts.** Counts sit in the Progress cell as muted text under or beside the bar, in `tabular-nums`, as the panel skill says for a figure at the end of a row.
- **Phone.** `cards_when_narrow`, using `<c-panel-table-card>`. The title block comes first, then the fields as a `<c-panel-definition-list>` (Status, Progress, Flags), with buttons under the item. The framework sets the 12px field gap and 16px card padding.
- **Table header.** Chalk (`bg-surface-2`) header row, as the brand allows. No border per item.
- **Empty and counts.** The footer count and an empty state follow the framework rules ("12 records").

Fit: it follows the "inside a panel, space separates items" rule, and a table is the form the framework already uses for a list with per-row actions.

## 3. Read-only email above an editable name form (item 4)

**Pattern.** Show the email as a definition row at the top of the Name panel's body, above the fields: label "Email" in `text-muted`, value in body text, with no input look. A disabled input looks editable (the project's rule for submitted answers makes the same point), so use text.

- Use `<c-panel-definition-list>` with one `<c-panel-definition-row>` for the email, then the form fields below at the 12px gap. It is not a second heading and not a second panel; the panel's title stays the one heading.
- Add a one-line hint when an educator would ask how to change it, only if that action exists ("Changed by the learner in their account"). If it does not exist, add no note (the framework removes "no note saying why" notes elsewhere).
- The email is not inside the `<form>`, so a 422 swap of the form leaves it intact and JavaScript-off posts stay the same.
- Save stays in the card footer (existing rule).
- Placement: the Name panel (first and last name), not Account. Its job is "who is this person"; Account holds the actions.
- The Overview tab keeps its email; this one repeats it in context, which is allowed here because the person is about to edit the identity.

Refs: https://design-system.service.gov.uk/patterns/ (read-only summary versus field), https://polaris.shopify.com/ (settings cards).

## 4. Everything the dashboard names is one click away (item 5)

**Pattern.** Three tiers, each already in the framework:
1. **Tile with a count** (Learners, Cohorts): the whole `<c-panel-stat-tile href>` is the link, with an `aria-label` that includes the value ("12 learners"), as the Cohorts tile does. Learners links to the learners list. Keep one pattern: the tile is a link, with no extra "View all" link inside it.
2. **A named person**: `<c-panel-person-link>` with `quick_view_url`, which opens the quick view drawer. This exists.
3. **A named cohort**: the same drawer pattern. The cohort name is a link in the row-link style (`no-underline text-on-surface` plus hover) that has `quick_view_url` pointing at the cohort's `__quick-view`. For a name with no avatar there is no `panel-person-link` equivalent. The spec should either reuse `<c-quick-view-trigger>` (listed in the framework's component list) or add a cohort-named variant. Check that `quick-view-trigger` accepts a plain text label.
4. **Without JavaScript**, the link goes to the record's page. With JavaScript it opens `#quick-view`. The quick view is non-modal (`show()`), so the dashboard stays tappable. "Open full page" is the header icon in the drawer.

Selecting the right target: the quick view for a thing that has one (learner, cohort, staff member), the full page for a thing that has none (a course, a count tile). The rule goes in `fls-dev:educator-interface` as the idea says; also add the dashboard to the Visual checklist: "every name on the dashboard is a control; tiles with counts link to their list".

Checklist for the spec: test every named thing on the dashboard in a table (tile, attention row, activity row, cohort progress row) rather than fixing only the two in the idea. An invariant test could fail on a dashboard region template that holds a bare name.

Refs: https://carbondesignsystem.com/components/data-table/usage/ · https://m3.material.io/components/side-sheets/guidelines (a side sheet keeps the page in context).

## 5. Busy state in a confirm dialog with an explanation line (item 6)

**Pattern.** While the in-request run is going:
- Submit shows its loading text ("Running…", with the ellipsis character, already a rule) and is disabled.
- Cancel and the header close are disabled (`disabled` on the buttons, `aria-disabled` on the close control), and Esc and the backdrop do nothing. Research section 4 notes the rule that Esc and the overlay follow the button.
- The explanation is body text, at the dialog's base size, at the end of the body: "This is running and can't be stopped. Wait for it to finish." This follows the panel skill's rule that a disabled control's reason lives in the body, never the footer, with `aria-describedby` from the disabled control to it.
- Put the line in an element that is hidden until the run starts. Make it `role="status"` (polite live region) so a screen reader announces it when it appears. Do not use a callout: a notice of the dialog's own state is body text here.
- Set `aria-busy="true"` on the dialog body while it runs.
- When the run ends, the dialog swaps to the result (counts), which has its own Close.

**Fit and trap.** The existing invariant `test_every_dialog_disables_only_its_own_submit_buttons` and the `hx-disabled-elt="find button[type='submit']"` rule say a dialog disables only its submit buttons. The spec must change this: Cancel is not a submit button, so a new `hx-disabled-elt` selector or an Alpine `busy` flag is needed, and the invariant must be loosened for the bulk confirm. Also, Cancel calls `cancel()` and the header close calls `requestClose()`, so both need the busy check, as does Esc. Prefer one Alpine flag (`running`) that all three read, set on `htmx:before-request` and cleared on `htmx:after-request`, over three selectors.

Refs: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ · https://www.nngroup.com/articles/response-times-3-important-limits/

## 6. Compact mobile page-header and dialog-footer buttons (item 7)

**Current state to correct in the spec.** The panel skill already says a small button looks 32px tall on a phone with an invisible 44px hit area, and that the dialog footer's buttons are the one exception: full size and 44px tall on a phone. The same skill says no action sits in a page header, yet the idea mentions Add learner and Import learners as page-header actions. The spec must first read the screenshot to establish which of these is wrong (a header button using the default size, or a toolbar button). If those are in `<c-panel-page-header>` actions, the fix is `size="small"` as the table says for page headers, and not a new mechanism.

**Page-header actions.** Small buttons, as wide as their label, in a wrapping row under or beside the heading (`flex-wrap gap-2`). Two buttons fit at 375px if the labels are a verb and a noun (existing rule). Do not stack them full-width. The primary is "Add learner"; "Import learners" is `secondary`. If a third comes, use a "More" `<c-dropdown-menu>`. Answers.md rejects the overflow menu as the fix for this item, so that stays only as the later fallback.

**Dialog footer.** Cancel at the left, the confirm at the right, on one line, each as wide as its label (not full-width, not stacked). Two buttons fit at 375px. For three or more, group at the right (existing rule), and consider wrapping, not stacking full-width. Use stacking only when a label will not fit on one line, which the "one line down to 375px" rule makes a wording bug.

**How "smaller to look at, 44px to touch" works.** The mechanism exists: the shared rule in `panel_framework.css` gives panel buttons an invisible 44px hit area. For the footer, the spec choice is a small visual button (about 32px, `size="small"`) with the same hit area, instead of the 44px visual button. Required changes:
1. `<c-modal-footer>` renders its buttons small below `md` (or at every width).
2. The skill's text and `test_only_the_dialog_footer_makes_a_button_44px_tall_on_a_phone` and `test_touch_targets.py` change to say "a dialog footer button is small with a 44px hit area". The spec must name them, since the skill is the source of truth.
3. Keep at least 8px between two adjacent targets so the hit areas do not overlap (Material). Check that the two footer buttons' 44px areas do not collide at `gap-2`.
4. A pseudo-element hit area is clipped by `overflow: hidden` on an ancestor. The dialog body clips, so check the footer's container does not.

Refs: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html · https://m3.material.io/foundations/designing/structure#touch-targets

## Summary of recommendations

| Item | Recommended pattern |
|---|---|
| 1 | Grid row `name | thin bar | %` per course, `space-y-2`, cap 3, "+N more" link to Courses tab; one `c-panel-*` row component for table cell and phone card |
| 2 | Table: Course, Status badge, Progress and counts, Flags, Actions; cards on narrow; the badge label carries the reason |
| 4 | Definition row (text, not a disabled input) at the top of the Name panel, outside the form |
| 5 | Tile is the link; names open the quick view via `quick_view_url`; rule and checklist line in `fls-dev:educator-interface` |
| 6 | One Alpine `running` flag disables submit, Cancel, close and Esc; body line with `role="status"` and `aria-describedby`; loosen the one-submit invariant |
| 7 | Small visual buttons with the 44px hit area, inline and as wide as their label; update the skill, the footer invariant and the touch-target test together |

status: ok · reason: research written; the skills conflict with the idea on page-header actions and on the full-size footer buttons, and the spec must settle both
