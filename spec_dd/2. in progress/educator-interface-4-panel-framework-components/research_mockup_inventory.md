# Research: mockup component inventory, screen by screen

Source: `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/*.dc.html`
(read in full: `Educator Dashboard`, `Educator Learners`, `Educator Cohorts and Admin`, `Educator
Interface`, `Sidebar`, and the three `Educator Mobile *` files — 8 desktop screens 01–08, 11 mobile
screens M01–M11, plus the shared `Sidebar` import). `_ds/README.md` describes the first-class
system and was not read as instruction, only as context per the idea.

Screens are files of HTML fixed at 1440×900 (desktop) or 390×844 (mobile) built with inline
styles and CSS custom properties (`var(--fg-1)`, `var(--color-primary)`, etc. — the first-class
token names, not FLS's). Everything below is read off the markup as drawn.

## 1. Screen-by-screen component inventory

### Sidebar (shared, `dc-import`'d into every desktop screen 01–08; reappears as a drawer sheet in M02)

- Brand tile: 28×28 rounded-7px square, primary bg, initials, white bold text.
- Org switcher control: 44px-tall bordered row, 24×24 rounded-6px avatar-initials tile, truncated
  name, `caret-up-down` icon. M02 shows it expanded into a 3-row picker list (current org bordered,
  alternates as plain rows with a 26×26 avatar tile each).
- Section overline label (`.fc-overline`: small caps, letter-spaced) — "Organization", "Teaching",
  "Administration".
- Nav item row: 17–19px icon + label + optional right-aligned mono count chip. Active state: bg
  tint, primary text/icon, bold, and a 2px inset left accent bar (`box-shadow: inset 2px 0 0`).
  Inactive: fg-2/fg-3, regular weight.
- User footer: 32–36px circular avatar-initials (primary bg on desktop sidebar and M02), name +
  role sub-line, trailing `gear` icon.

This is the interface shell (spec 1's territory, already built — `panel_framework/templates/
panel_framework/partials/sidebar_nav.html` exists). Its avatar, badge-like count chip and nav-row
accent-bar patterns overlap spec 4 primitives but the sidebar itself is out of this spec's scope.

### 01 — Dashboard (desktop)

- Top bar: greeting title, search input (36px, icon + placeholder, no focus state shown), bell
  icon button in a 36×36 bordered square.
- **Stat tile**, 4-column grid, 16px gap, card padding 18×20px, radius 12px. Three drawn variants:
  - overline + 30px bold value + fg-3 12.5px sub-line ("Active learners" 284 / "Across 12
    cohorts"; "Awaiting review" 11 / "Practical submissions").
  - overline + value + 6px rounded progress bar under it, no numeric sub-line ("Average progress"
    64%).
  - overline + value + coloured delta line with a `trend-up` icon ("Pass rate" 87% / "Up 4
    points", success colour).
- **Attention list** ("Learners needing attention"): section-card header (title + sub-line +
  "View all" link) then rows: 34px circular initials avatar, name (14px bold) + context sub-line
  (12px fg-3), right-aligned mono meta text, a status **badge** (rounded-full, 4×10px padding,
  11.5px/600), and a text action ("Message" / "Review", 13px/600, primary colour). Divider
  between rows, no divider after the last.
- **Progress bar with label**, repeated 4× inside one section card ("Cohort progress"): label +
  right-aligned mono percentage, 6px bar below. This is the idea's progress-bar component used as
  a stacked list, not a single instance.
- "This week" agenda card: mono date tag (fixed 62px column, primary colour on the soonest item)
  + title + count/meta sub-line. **Out of scope** — the roadmap's out-of-scope list names "this
  week" explicitly.

### 02 — Learners table (desktop)

- Breadcrumb-style page header: org name → chevron → "Learners", with an action group ("Import"
  outline button, "Add learner" primary button, both icon+label).
- **Toolbar**: search input with a drawn *focused* state (primary border + focus ring + caret),
  an unapplied filter trigger ("Cohort", funnel icon + `caret-down`), an **applied filter chip**
  ("Status: Stalled" — tinted bg, primary border/text, trailing `x`), a ghost "Add filter" button,
  a "Sorted by …" text line, and a "manage columns" icon button (`columns` icon in a 40×40 square
  — not named anywhere in the idea).
- Data table (checkbox column, sortable header with `arrow-up` + primary text, avatar+name+email
  cell, cohort text, progress-bar-plus-percentage cell, mono last-active, status badge, trailing
  kebab `dots-three` icon). Selected-row state: tinted bg + filled checkbox with `check`. This
  whole region, its pagination footer (Previous/Next buttons, numbered page squares, "N selected ·
  showing X of Y" text) and its checkbox/sort states are spec 2's table layer, not spec 4's — only
  the badge, avatar chip and progress-bar cells inside it are spec 4 components.

### 03 — Learner detail (desktop)

- Top bar: back-link ("← Learners"), breadcrumb chevron, page title, action group ("Edit" outline,
  "Send message" primary).
- Profile header block: 52px circular avatar-initials (bold, primary bg), 24px name, meta row
  (email, a 1px divider rule, mono record id, status **badge** "Retake due"). This — not the plain
  top bar — is the closest match to the idea's "page header with title, subtitle, status badge".
- **Tab bar**: Overview / Courses & progress / Assessments / Certificates / Activity. Active tab:
  bold, primary, 2px inset-bottom accent; inactive: fg-2/500.
- **Definition list** ("Learner details"): section-card heading + 4-column grid of overline-label /
  value pairs, 8 fields. Exact match for the idea's citation.
- Section card ("Module progress"): heading + right-aligned mono summary, then rows of state icon
  (`check-circle` success / `warning-circle` error / `lock-simple` locked, ~19–20px) + title + 6px
  progress bar + right-aligned mono status text (colour follows state). This icon+title+bar+status
  row is a composite the idea does not name separately — it reads as progress-bar + status icon
  assembled ad hoc, not a distinct "module row" component.
- Quick-view side panel (380px, spec 3's territory): header ("Quick view" overline + `arrows-out-
  simple` expand icon + `x` close). Body: a bordered "progress snapshot" card (heading + mono % +
  bar + fg-3 commentary line — a boxed variant of stat tile + progress bar), a 2-column grid of
  **small stat tiles** (13–14px padding, 17px mono value, no delta — a denser tile variant than
  01's), an **inline callout/alert card** (tinted bg, 3px inset accent bar, bold heading + body
  text — "One retake remaining"; not named anywhere in the idea, recurs on 08, M06, M11), and an
  **activity list** (icon + 13px text + mono timestamp rows, no avatar/badge/action — a lighter
  relative of the attention list). Footer: "Message" (primary) + **"Reset attempt"** (outline) —
  the latter is explicitly out of scope ("Deliberate retakes or progress resets").

### 04 — Message/quick-view panel (desktop)

- Minimal toolbar (title + "Add learner").
- A stripped-down data table (name, cohort, progress, status) with one row in a **selected-row**
  state (tint + left accent bar, same visual language as the sidebar's active-nav accent).
- Right panel (420px, spec 3's quick-view/dialog): header (title + `x`), avatar chip (36px) + name
  + cohort/idle sub-line, a "Template" field styled as a bordered trigger + chevron, "Subject" text
  input, a large "Message" textarea shown focused (primary ring), a checkbox + label ("Also send
  as email"), footer ("Draft saved" text + Cancel/Send buttons). This whole message-composer
  screen is the messaging feature the roadmap defers to `user-communication`; its generic text
  input / textarea / checkbox controls are not itemised in the idea's component list at all and
  read as ordinary form fields, not new panel_framework components.

### 05 — Cohort detail (desktop)

- Header block: breadcrumb bar + action group ("Enrol learners", "Edit cohort", both outline),
  then status **badge** ("Active") + mono cohort code, 26px title, and an **inline stat row** —
  four label/value pairs (Learners 31, Avg progress 78%, Pass rate 91%, Closes 30 Nov 2026) laid
  out flush right with no card wrapper. This is the idea's cited "page header … status badge …
  (05)" screen, but the stat values here are a card-less variant of the stat tile the idea doesn't
  distinguish from the boxed one on 01.
- **Tab bar**: Overview / Learners (with a mono count chip) / Curriculum / Assessments / Schedule /
  Settings.
- **Definition list** ("Cohort details"): 3-column grid, 9 fields — a second, wider instance
  confirming the component is reused beyond the idea's single citation.
- "Module completion across the cohort" card: same title+bar+right-aligned-fraction row pattern as
  03's module list, but without the per-learner icon/lock states (cohort-level, not gated).
- "Needs attention" card: severity-coloured icon (`clock-countdown` warning / `file-text` info /
  `warning-circle` error) + text + a "View"/"Review" link, no avatar or badge. A leaner variant of
  the attention list the idea cites only for learner rows (01, M01) — here the "reason" carries no
  per-item badge.
- "Instructors" card: 32px avatar (primary bg for the lead, grey for others) + name (13.5px bold) +
  role sub-line (12px). Exact match for "Avatar chip … optionally with email or role under it (02,
  05)" — note the idea's own citation of "02" is not actually where this pattern appears; it
  appears on 03 (profile header, no role line) and 05 (this card, no email). See §2.
- "Compliance" card: icon (`check-circle` / `warning-circle`) + text rows, no link. **Out of
  scope** — the roadmap names "compliance" directly in its ignore-list.

### 06 — Roles and permissions (desktop)

Entire screen is largely **out of scope**: the roadmap explicitly ignores "custom roles and a
'create role' button". The reusable parts are generic: a data table (spec 2) with a role
name+scope-tag stacked cell (a plain small text tag, "System role"/"Custom" — styled as plain text,
not a pill, inconsistent with the badge style used everywhere else), holders count (mono), last-
changed date (mono), and a row-actions cell with two states: a **locked row** ("Locked" text +
`lock-simple` icon, muted, no actions) versus an editable row ("Edit"/"Duplicate" text links,
primary colour). The locked/editable row-actions split is relevant to spec 5's hidden-vs-disabled
question, not a spec 4 component.

### 07 — Create cohort modal (desktop)

Spec 3's territory (dialog chrome: overlay, centered 640px panel, header title+sub-line+`x`,
footer bar with helper text + Cancel/primary). Its form fields (labelled text input with a focus-
ring state, a select-style trigger with helper caption underneath, two-up date fields with a
`calendar-blank` icon, an instructor-picker field with an inline avatar chip, a numeric input, and
a checkbox+two-line-label combo) are not named anywhere in the idea's component list; they read as
ordinary form controls, not panel_framework components.

### 08 — Bulk import modal (desktop)

Spec 3 dialog chrome again, plus:
- A **stepper** ("Upload / Map fields / Review"): circular 22px node per step (filled
  success+`check` = done, filled primary+number = current, outlined+number = future) joined by 1px
  rules. Not named anywhere in the idea — a clear gap.
- A **file chip**: bordered row, `file-csv` icon (22px, primary), filename (bold) + mono meta
  ("28 rows · 6 columns · 42 KB"), "Replace file" text action. Not named in the idea.
- A column-mapping mini-table (source column mono text → `arrow-right` → target-field select
  trigger → sample value). Presentationally close to a data table but is import-specific — reads
  as spec 8 (bulk operations) territory, not spec 4.
- The same **inline warning callout** pattern as 03 (tinted bg, inset accent bar, icon + text).
- Footer: Back (outline) + Cancel (outline) + primary "Review N learners".

### M01 — Dashboard (mobile)

- Top bar swaps the sidebar for a hamburger (`list`) icon; search/bell become bare icons (no
  bordered squares).
- Stat tiles: only 2 of the desktop's 4 are shown, in a 2-column grid (Active learners, Awaiting
  review) — the delta tile and the "Average progress" tile are pulled out into their own full-
  width progress-bar card instead of being 4-across.
- **Attention list**: 36px avatar, name + badge inline, a *single* combined meta line (desktop's
  two lines collapsed into one, e.g. "14 days idle · RPAS Basic"), badge on the right — the
  separate "Message"/"Review" text action is dropped (row presumably becomes tappable as a whole).
- "This week" card retained (2 of 3 items) — still out of scope per roadmap.
- **Bottom tab bar** (Dashboard/Cohorts/Learners/More, icon+label, active = primary+bold). Flagged
  in the roadmap as an open question the shared spec 1 core defaulted to "no" on (default is to
  keep the sidebar sheet) — this bottom tab bar is not confirmed in scope.

### M02 — Navigation drawer (mobile)

Overlay + slide-in panel reusing the Sidebar's content verbatim (org switcher expanded to a 3-row
picker, nav list, user footer) plus a close `x`. This is the mobile Sidebar, not a spec-4
component.

### M03 — Learners list (mobile)

- Toolbar: full-width search, an applied filter **chip** ("Stalled" + `x`), and two ghost trigger
  buttons ("Filter", "Sort") that open sheets rather than inline controls.
- Stacked list rows replace the table: 40px avatar, name+badge inline, one combined meta sub-line,
  progress bar + inline percentage, trailing `caret-right` for navigation. This is spec 2's
  "stacked rows on mobile," reusing spec 4's badge/avatar/progress-bar primitives.
- A **floating action button** (56px circle, primary, `plus`, positioned above the tab bar) — not
  named anywhere in the idea; likely a first-class-system artifact rather than a confirmed FLS
  pattern.
- Same bottom tab bar as M01.

### M04 — Filter and sort sheet (mobile)

A bottom sheet (spec 3's dialog territory: rounded-top 16px, 36×4px drag handle). Content: a
wrapped **chip toggle group** for Status (selected = tinted+primary border, unselected = outline —
matches the idea's "toolbar with … filter chips"), a select-style "Cohort" field, and a **radio-
style selectable list** for "Sort by" (selected row bold+primary+`check`, others plain) — this
selectable-list pattern is not named in the idea. Footer: Cancel (outline) + primary "Show N
learners".

### M05 — Learner detail (mobile)

- Header: back arrow, title, kebab (`dots-three-vertical`) menu trigger — the icon-only kebab-menu
  trigger recurs here and on M08's header and 02's table rows (there as `dots-three`, horizontal —
  see icon table below for the inconsistency).
- Profile header stacked (48px avatar + name + id+badge inline).
- **Tab bar**, 4 tabs, horizontally overflowing (no visible scroll affordance drawn).
- Progress card, callout, and **definition list** all reappear, but "Learner details" drops to a
  2-column grid (vs 4-column desktop) — confirms the idea's "definition list … responsive" note.
- "Modules" card: condensed rows drop the per-row progress bar entirely, keeping only icon+title+
  mono status — a real density difference from 03's module-progress row.
- Fixed footer (76px): "Message" (primary, flex-fill) + a **single icon-only secondary button**
  (`chart-line-up`) replacing 03's text button "Reset attempt" — mobile substitutes an icon button
  for a secondary action where desktop uses a labelled one, and the icon's meaning has visibly
  changed (chart, not reset).

### M06 — Quick view sheet (mobile)

Bottom sheet (partial height, not full — spec 3). Same progress-snapshot card, 2-column small-
stat grid, and activity list as 03's quick view, plus a text link ("Open full learner record")
that has no desktop equivalent — desktop instead puts an `arrows-out-simple` expand icon in the
header to do the equivalent job. Footer again pairs "Message" with **"Reset attempt"** (out of
scope).

### M07 — Send message (mobile)

Full-screen composer (spec 3, or rather out of scope per the messaging deferral). Header moves the
primary action into the bar itself ("Send" text, top-right) instead of a footer button. Same
recipient chip / Template / Subject / Message / checkbox fields as 04. Includes a decorative
on-screen keyboard mockup — not a real UI element, ignore.

### M08 — Cohort detail (mobile)

- Header: back arrow, truncated title, kebab menu.
- Status badge + mono code + title, then an **inline stat row** with only 3 of the desktop's 4
  metrics ("Closes" is dropped).
- **Tab bar**: 4 of the desktop's 6 tabs (Assessments and Settings dropped).
- "Needs attention" rows drop the text link, using a trailing `caret-right` chevron instead
  (mirrors M03's list-row convention).
- "Cohort details" definition list: 2-column grid, only 6 of 9 fields (drops Lead instructor,
  Capacity, Attempts allowed).
- "Module completion": only 1 row shown, no "view all" affordance drawn (may just be a mockup
  space constraint, not a confirmed pattern — flagged, not asserted).
- Same bottom tab bar, "Cohorts" active.

### M09 — Roles and permissions (mobile)

Out of scope content (role creation), same caveat as 06. Notable mobile differences: the "Create
role" action moves from a header button to a **sticky full-width bottom button**; the locked-role
indicator becomes inline text+icon rather than a right-aligned table cell; the "Duplicate" action
is dropped everywhere on mobile, leaving only "Edit".

### M10 — Create cohort (mobile)

Full-height sheet. Header uses a **left/right text-action pattern** ("Cancel" … "Create") instead
of desktop's icon-close + footer-buttons pattern — a mobile sheet convention not seen on any
desktop dialog. Same field set as 07, but the date fields drop the `calendar-blank` icon (mono
text only) and the helper text moves from a fixed footer into the scrollable content.

### M11 — Import learners (mobile)

Full-height sheet. Header combines a back-arrow *and* a close `x` (unlike M10's cancel/create text
pair). The 3-step progress becomes three **flat 4px bars** (done=success colour, current=primary,
future=grey) instead of 08's circular numbered stepper with connecting rules — a real visual
inconsistency between the desktop and mobile stepper that the spec needs to resolve if a stepper
is built at all. Mapping rows stack vertically (source→sample above, target-field select below)
instead of 08's 4-column grid row — consistent with the "stacked on mobile" table theme. Footer
drops Back/Cancel, keeping only the primary "Review N learners" button (back is implied by the
header's back-arrow).

## 2. Cross-check against the idea's inventory

| Idea's listed component | Where it actually appears | Notes |
|---|---|---|
| Page header w/ title, subtitle, status badge, action group (cites 03, 05) | 03's profile header block and 05's header block, yes — but the plain top *toolbar* bars (back-link/breadcrumb + buttons) on 02/03/04/05/07/08 carry no status badge; only the profile/cohort header blocks do. The idea's citation is accurate but easy to misread as "the top bar" | No mismatch, just note which block carries the badge |
| Stat tile w/ value, label, delta/sub-line, responsive row (cites 01, M01) | 01 (4-up boxed), M01 (2-up boxed), 05 (4-up, card-less inline variant), M08 (3-up, card-less) | The idea only cites the boxed card variant; the header-embedded, card-less variant on 05/M08 is a second shape for the same data the idea doesn't distinguish |
| Status badge, fixed vocabulary (active/inactive/pending/complete/in progress/stalled) | Badges seen: Active, Stalled, Retake due (M01: "Retake"), Submitted (M01: "Review"), Complete, In progress, Invited, Locked (plain text, not a badge) | Mockups never show "inactive." "Pending" is not used verbatim — "Invited" is the closest analogue. "Retake due"/"Submitted" are assessment-review states layered into the same badge visual language as the six-word learner-status vocabulary; the spec needs to decide whether they're in scope for this badge component or belong to spec 10's per-assessment status. Desktop and mobile also disagree on wording for the same state ("Retake due" vs "Retake"; "Submitted" vs "Review") — see §3 |
| Avatar chip w/ initials + name, optional email/role under it (cites 02, 05) | 05's "Instructors" card (name+role) and 03/M05's profile header (name+email, no role); the idea's own "02" citation doesn't hold — 02's table cells pair avatar+name+**email**, not on cohorts/05 as cited | 02 does have avatar+name+email, so the citation is directionally right, just imprecise about which screen shows which sub-line |
| Attention list: row per learner, reason, badge, one action (cites 01, M01) | 01 and M01 match closely (avatar, reason text, badge, action link — dropped on M01). 05/M08's "Needs attention" card is a cohort-level sibling with no avatar/badge, just icon+text+link/chevron | The idea's citation covers the learner-row variant only; the cohort-level "needs attention" card is a related but distinct usage worth naming explicitly if it's to be built the same way |
| Progress bar w/ percentage, optional label (cites 01, 03) | 01 (dashboard cohort list), 03 (module rows, quick-view snapshot), 05 (module rows, header stat), M01/M05/M06/M08 mobile equivalents | Matches; recurs far more than the two citations suggest, consistently 6–8px height |
| Section card: heading, optional description, body, actions footer | Every card on every screen | Matches broadly; note that many cards have no footer at all (e.g. "Cohort details", "Learner details" definition-list cards) — the "actions footer" is optional in practice, confirming the idea's own wording |
| Definition list, responsive (cites 03 "Learner details") | 03 (4-col → M05 2-col), 05 (3-col → M08 2-col, fewer fields) | Matches, and the idea's single citation understates reuse — it appears on both learner and cohort detail |
| Toolbar w/ search, filter chips, primary actions (cites 02) | 02 (desktop), M03/M04 (mobile — search + chip + two sheet-opening triggers, rather than inline filter/sort controls) | Matches; mobile toolbar defers filter/sort to sheets instead of inline controls, which the idea doesn't call out |
| Empty state: icon, sentence, one action | **Not drawn anywhere in the mockups.** No screen shows a zero-data state | The idea lists it as settled but the mockups have nothing to read it from — build it from the domain vocabulary skill and the framework's existing patterns, not the mockups |
| Tab bar styling shared with framework tab container (cites 03, 05) | 03, 05, M05, M08 | Matches; mobile tab bars overflow horizontally with no scroll affordance drawn |
| Skeleton blocks for loading states (spec 3's consumer) | **Not drawn anywhere** — static mockups show no loading state | Same as empty state: nothing to read from the mockups |

Components that **appear in the mockups but are not in the idea's list**:

| Component | Screens | Likely home |
|---|---|---|
| Inline callout / alert card (tinted bg, inset accent bar, icon+heading+body) | 03, 08, M06, M11 | Recurs enough (4 screens) that it reads as a real gap in spec 4's list, not noise |
| Stepper / wizard progress (circular nodes on desktop, flat bars on mobile — inconsistent between the two) | 08, M11 | Spec 4 if a generic component, or spec 8 (bulk import) if built one-off — needs a decision, and the desktop/mobile visual mismatch needs resolving either way |
| File attachment chip (icon + filename + mono meta + "Replace" action) | 08, M11 | Spec 8 (bulk import), not spec 4 |
| Selectable/radio list row (bold+primary+check for the chosen row) | M04 ("Sort by") | Could be a spec 4 primitive (a list variant) or left to spec 2/3's own controls |
| Floating action button (56px circle, primary, plus icon) | M03 | Unclear if wanted at all; not mentioned in the idea or the roadmap's mobile notes |
| "Manage columns" icon button (`columns` icon, square) | 02 | Spec 2's table layer, not spec 4 |
| Mapping mini-table (source→target field row) | 08, M11 | Spec 8 |
| Kebab-menu icon-only trigger | 02 (`dots-three`, horizontal), M05/M08 (`dots-three-vertical`) | Worth a single spec-4 primitive since it recurs, but the two screens use different Phosphor glyphs for the same job — pick one orientation |

Components the idea lists that the mockups **do not actually show**: empty state, skeleton
blocks (see table above) — both genuinely absent from every screen, desktop and mobile.

## 3. Every status/badge label, verbatim, by screen

| Label (verbatim) | Screens | Colour token as drawn |
|---|---|---|
| `Active` | 05, M08 | success-light bg, `#26714a` text |
| `Stalled` | 01, 02, 04, M01, M03, M04 (as a chip label) | warning-light bg, `#8a6412` text |
| `Retake due` | 01 (table/list row), 02, 03, M03 | error-light bg, `#a52a2a` text |
| `Retake` | M01 | error-light bg, `#a52a2a` text — **shortened form of "Retake due," same state, different wording than desktop** |
| `Submitted` | 01, 02 | info-light bg, `#215b96` text |
| `Review` | M01 | info-light bg, `#215b96` text — **same state as "Submitted" above, different wording on mobile** |
| `Complete` | 02 | success-light bg, `#26714a` text |
| `In progress` | 02, 04, M03 | neutral grey-100 bg, fg-2 text (no colour accent, unlike the other states) |
| `Invited` | 02, M03 | neutral grey-100 bg, fg-3 text (dimmer than "In progress") |
| `Locked` | 06, M09 | plain text + `lock-simple` icon, fg-4 — **not styled as a pill badge at all**, unlike every other status here |

The idea's fixed vocabulary is "active, inactive, pending, complete, in progress, stalled." The
mockups never draw "inactive," and use "Invited" where "pending" might map. "Retake due" and
"Submitted"/"Review" are assessment-outcome states drawn in the identical badge visual language as
the six-word learner-status vocabulary and in the same table column — the spec must decide whether
those are in this component's vocabulary or belong to a separate per-assessment status (spec 10's
territory, since it computes "stalled").

## 4. Every Phosphor icon used, by rough purpose, and the closest FLS semantic name

FLS's default icon set is Heroicons (`freedom_ls/icons/config.py`,
`FREEDOM_LS_ICON_SET` default `"heroicons"`). Per the idea and `fls-dev:icon-usage`, components
must use `<c-icon name="semantic_name" />` and pick the closest existing icon in the active set —
Phosphor itself must not be added. The table below maps each Phosphor class the mockups use to the
closest FLS **semantic name** (see `freedom_ls/icons/semantic_names.py` / the skill's list), not to
a specific Heroicons/Phosphor glyph, since the semantic name is what a component references.

| Mockup icon (`ph-…`) | Used for | Closest FLS semantic name | Gap? |
|---|---|---|---|
| `magnifying-glass` | search inputs (01, 02, M01, M03) | — | **Gap: no "search" semantic name exists** |
| `bell` | notifications trigger (01, M01) | `notifications` | exact |
| `trend-up` | dashboard delta ("Up 4 points") | — | **Gap: no trend/delta semantic name** |
| `caret-up-down` | org switcher | `dropdown` (single-direction only) | partial — no combined up/down affordance |
| `gear` | settings / user footer | `settings` | exact |
| `squares-four` | "Dashboard" nav icon | — | **Gap: no dashboard/grid semantic name** |
| `users-three` | cohort nav/actions | `cohort` (mapped to `users`, not `users-three`, in Phosphor set) | close, not exact glyph |
| `user` | learner nav/rows | `user` | exact |
| `book-open-text` | "Courses" nav | `topic` (mapped to `book-open`) | close |
| `chalkboard-teacher` | "Educators" nav | — | **Gap: no educator/instructor semantic name** |
| `shield-check` | "Roles & permissions" nav | — | **Gap: no permissions/roles semantic name** |
| `buildings` | "Organization settings" nav | — | **Gap: no organisation semantic name** |
| `caret-right` | breadcrumb separators, list-row chevrons | `collapse` (mapped to `caret-right`) | exact, but semantically mismatched (used for breadcrumbs/navigation, not collapse) |
| `upload-simple` | "Import" button | — | **Gap: no upload semantic (only `download` exists)** |
| `plus` | Add learner / Add filter / Create cohort / Create role / FAB | — | **Gap: no generic "add/create" semantic name, despite being the single most-used action icon in the mockups** |
| `funnel` | filter triggers | — | **Gap: no "filter" semantic name** |
| `caret-down` | dropdown/select triggers | `dropdown` | exact |
| `x` | close buttons, applied-filter-chip remove | `close` | exact |
| `columns` | "manage columns" button | — | gap, low priority (spec 2 concern) |
| `arrow-up` | active sort-column indicator | `sort_asc` | exact |
| `dots-three` (horizontal) | table row kebab menu (02) | `more_options` (mapped to vertical `dots-three-vertical`) | **orientation mismatch vs M05/M08's `dots-three-vertical`** |
| `dots-three-vertical` | mobile header kebab (M05, M08) | `more_options` | exact |
| `dots-three-circle` | mobile "More" tab-bar item | `more_options` (circled variant not mapped) | close |
| `check` | checkboxes, stepper "done" node, checked list item | `check` / `boolean_true` / `complete` | exact |
| `arrow-left` | back navigation | `previous` | exact |
| `pencil-simple` | Edit actions | `edit` | exact |
| `paper-plane-tilt` | Send/Message actions | — | **Gap: no message/send semantic name** |
| `check-circle` | success state icon (module passed, compliance ok) | `success` | exact |
| `warning-circle` | both error states (failed module) and warning states (needs-attention items) — overloaded in the mockups | `warning` (mapped to a triangle, not a circle) or `error` (mapped to `x-circle`) | **ambiguous: mockups use one glyph for two different FLS semantics** |
| `lock-simple` | locked module / locked role | `locked` (mapped to plain `lock`) | close |
| `arrows-out-simple` | quick-view "expand" | `fullscreen` (mapped to `arrows-out`) | close |
| `file-text` | notes/activity-feed icon, "submissions" icon | `notes` | exact |
| `play-circle` | "completed lesson" activity icon | `in_progress` (mapped to plain `play`) | close |
| `chat-circle` | "asked a question" activity icon | — | **Gap: no chat/discussion semantic name** |
| `clock-countdown` | idle-learner "needs attention" icon | `deadline` (mapped to plain `clock`) | close |
| `calendar-blank` | date-field icon | — | **Gap: no date/calendar semantic name** |
| `file-csv` | import file-type icon | `notes` (generic file icon only) | gap, no CSV-specific semantic |
| `arrow-right` | mapping-row arrows, "next" affordances | `next` | exact |
| `list` | mobile hamburger menu trigger | `menu_open` (mapped to `list`) | exact |
| `arrows-down-up` | mobile "Sort" trigger | `sort_neutral` | exact |
| `chart-line-up` | M05's secondary footer button (progress/report) | — | **Gap: no reporting/analytics semantic name** |
| `backspace` | on-screen keyboard mockup (M07) | n/a | decorative, not a real UI icon — ignore |

Summary of real gaps (semantic names the mockups need but FLS's list doesn't have): search, add/
create, upload, filter, trend/delta, dashboard/grid, educator/instructor, permissions/roles,
organisation, message/send, chat/discussion, date/calendar, reporting/analytics, CSV/file-type.
`plus` (add/create) is the single highest-frequency gap — it appears on nearly every screen with a
primary creation action.

## 5. Mobile differences, by component

- **Stat tile**: desktop shows up to 4 in a card row; mobile shows 2 in a 2-column grid and pulls
  the others (progress-bar and delta variants) into their own full-width cards. The card-less,
  header-embedded stat-row variant (05/M08) drops from 4 fields to 3 on mobile (M08 drops
  "Closes").
- **Attention list**: mobile collapses the two-line meta text into one truncated line and drops
  the row's text action entirely (no "Message"/"Review" link drawn on M01's rows).
- **Definition list**: column count drops (4→2 on learner detail, 3→2 on cohort detail) and field
  count drops on cohort detail (9→6 fields on M08; 03→M05 keeps all 8 fields, just re-columned).
- **Module progress rows**: desktop keeps a per-row progress bar; mobile (M05) drops the bar,
  keeping only the icon + title + mono status.
- **Tab bar**: mobile shows fewer tabs than desktop for the same screen (03/M05: 5→4; 05/M08:
  6→4) and provides no visible overflow/scroll affordance for the tabs it hides.
- **Toolbar**: desktop's filter/sort controls are inline; mobile opens them as bottom sheets
  (M04) instead, and the sheet uses a chip-toggle-group + selectable-list pattern not present on
  desktop's toolbar at all.
- **Quick-view panel**: desktop offers an "expand" icon in the header to open the full record;
  mobile instead puts a text link ("Open full learner record") at the bottom of the sheet — two
  different affordances for the same action.
- **Secondary footer action**: desktop's learner-detail secondary button is a labelled "Reset
  attempt"; the mobile equivalent (M05) is an icon-only button with a different icon
  (`chart-line-up`) and, seemingly, a different meaning — not a straight responsive relabel.
  M06's mobile quick-view sheet, unlike M05, does keep a labelled "Reset attempt" button, so the
  two mobile screens disagree with each other, not just with desktop.
- **Dialogs → sheets**: every centered desktop modal (07, 08) becomes a full-height bottom sheet
  on mobile (M10, M11), and the header's action placement changes with it — desktop dialogs put
  primary/secondary actions in a footer bar; mobile sheets put them as left/right text actions in
  the header instead (M10), or split back-navigation into the header while keeping one primary
  footer button (M11).
- **Stepper**: desktop (08) draws circular numbered nodes with connecting rules; mobile (M11)
  draws three flat progress bars instead — a genuine visual inconsistency, not just a density
  change.
- **Row action affordance**: list rows that carry a text link on desktop (05's "Needs attention",
  "View"/"Review") become a trailing chevron-only affordance on mobile (M08), consistent with the
  stacked-list-row convention used throughout mobile (M03).
- **Icons dropped on mobile**: cohort-creation date fields lose their `calendar-blank` icon on
  mobile (M10) though the desktop version (07) has it; no functional difference implied, just a
  drawn omission.

## Assumptions / caveats

- Read all eight `.dc.html` files fully; did not open `support.js` or the `_ds/` design-system
  bundle referenced by `<link>`/`<script>` tags in each file's `<helmet>` — those are the
  first-class rendering harness, not FLS-relevant content, consistent with the idea's framing of
  `_ds/` as context only.
- Colours, sizes and radii above are transcribed directly from each screen's inline `style`
  attributes and CSS custom properties as drawn; they are first-class tokens (`--color-primary`,
  `--fg-1`, etc.), not FLS role tokens — translating them is this spec's job, not this research's.
- "Out of scope" calls follow the roadmap's own "Educator interface rebuild" section (its
  assumptions list and the twelve-spec "out of scope for all twelve" list) verbatim; anything not
  named there is only flagged as a gap or gray area, not asserted as out of scope.

status: ok
