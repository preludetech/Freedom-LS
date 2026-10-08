# Human QA report: educator interface looks good

Date: 2026-10-05. Reviewed at `http://127.0.0.1:8000/educator/organisations/demodev/...` against
`design_screenshots/` and `design_source/`.

The implementation does not match the design, and several parts are not well thought out. This
report lists every fix. Nothing in it has been fixed yet. Screenshots come from the QA run that is
already going; this report does not include any.

## Ground rules for the fixes

- **Compare against the first_class theme, not the default theme.** The design was drawn with
  first_class (`freedom_ls/themes/first_class/static/themes/first_class/theme.css`), and its tokens
  map almost one to one:
  - design `--bg` (`#F8F9FC`) is first_class `--color-surface`
  - design `--grey-100` is `--color-surface-2`
  - design `--border` is `--color-border`
  - design `--fg-3` is `--color-muted`
  - design `--font-heading`, `--font-body` and `--font-mono` are `--fls-font-display`, `--fls-font-sans`
    and `--fls-font-mono`
  - design `.fc-overline` is the small-caps label treatment the panels already use
    (`text-xs font-semibold uppercase tracking-wide text-muted`)

  Run the dev server with `FLS_THEME=first_class` when checking. Still use semantic tokens so the
  default theme keeps working.
- **Do not change the mobile navigation presentation.** The nav slides up from the bottom (the
  `bottom-sheet` variant) on purpose. Keep it.
- **Do not change the main site header** (the First Class header bar above the shell).
- Avatar, display name and initials are existing data (`User.display_name`, `User.initials`,
  `c-panel-avatar-chip`). Using them is not scope creep.

---

## 1. Cohorts table: the name opens the quick panel instead of the cohort page

**Where:** `/educator/organisations/demodev/cohorts`. `CohortDataTable` in
`freedom_ls/educator_interface/views.py` (~line 204) sets `quick_view=True` on the name column, and
`cotton/data-table-cells/link.html` then renders the name as a `c-quick-view-trigger`.

**Now:** Clicking the cohort name opens the right-hand quick panel. You cannot get to the cohort
detail page from the name.

**Should be:**
- The cohort name is an ordinary link that navigates to the cohort detail page (HTMX nav into
  `#main-content`, as other link cells do).
- A small icon button next to the name opens the quick panel. It needs an accessible label such as
  "Quick view: <cohort name>" and a visible focus ring. Use an existing semantic icon (see
  `freedom_ls/icons/semantic_names.py`, for example `info` or `fullscreen`). Do not add a new one.
- Both choices must be available from every row.
- Fix this once in the framework: `link.html` renders a link plus a trigger button when
  `column.quick_view` is set. Every table that uses `quick_view=True` then behaves the same way:
  - Cohorts
  - Learners (first and last name)
  - Course learner registrations
- On the mobile card list, a card tap still navigates. The quick-view button needs a hit area of at
  least 44px.

**QA check to add (section 3, plus a new section for the quick panel):**
1. On the cohorts list, click a cohort name. The cohort detail page loads and the quick panel does
   not open.
2. Click the quick-view button beside the same name. The quick panel opens and the page does not
   navigate.
3. Repeat both steps on the learners list.
4. Keyboard: Tab reaches the name link and the quick-view button as two separate stops, each with a
   visible focus ring. Enter on each one does the right thing.

## 2. The page content jumps sideways when the quick panel opens or closes

**Where:**
- `freedom_ls/base/templates/_base_interface.html`: the `header_width` block (`max-w-7xl mx-auto`).
- `freedom_ls/base/templates/cotton/page.html`: `mx-auto w-full max-w-7xl`.
- `panel_framework/partials/quick_view_host.html`: `padding-inline-end: 30rem` on
  `#interface-main` when the panel is docked.

**Now:** The content column is centred. When the docked quick panel opens, `#interface-main` gains
30rem of end padding, so the centred cohorts table slides left. When the panel closes, the table
slides back right.

**Should be:** The body is left-aligned against the sidebar in the panel framework and educator
interface shell. It stays where it is when the quick panel opens and closes, and only its right edge
gives way to the panel. Keep a max width if needed, but anchor it to the start, not the centre. This
covers both the content header (breadcrumb row) and the `c-page` content well.

**QA check to add:** At 1442 wide on the cohorts list, note the x position of the table's left edge
and the page title. Open the quick panel and then close it. Neither moves. Repeat at 1280 wide, the
first docked width.

## 3. The quick panel header has the wrong style

**Where:** `panel_framework/partials/quick_view_host.html`, the `<header>`.

**Design** (`educator-learners__03-learner-detail.png`, the right-hand panel): the header row holds
a small overline label, "QUICK VIEW":
- 11px, semibold, uppercase, wide letter spacing, muted colour, in the body font
- small muted icon buttons on the right: expand (opens the full page) and close

The record's name sits in the panel body as a modest heading (about 17px semibold), with a muted
subtitle line under it.

**Now:** The header is a bare `<h2>`, so it picks up the global `h2` rule in `tailwind.components.css`
(`lg:text-3xl font-bold font-display`). The result is a large title in the display font. The
"Open" text link is in primary colour, and the close icon is `size-6`.

**Should be:**
- The header label uses the overline treatment in the body (data) font, not the display font.
  Override the global `h2` styling explicitly.
- The record name moves into the body as the panel's heading.
- "Open" becomes a small muted icon button (`fullscreen`) with `aria-label="Open full page"`, next
  to a close button of the same size.
- The quick-view bodies (`educator_interface/quick_views/cohort.html` and `learner.html`) use the
  same small-caps `dt` labels as `c-panel-definition-row`, not their own `text-sm font-semibold`
  labels.

**QA check to add:**
1. Open the quick panel on a cohort.
2. The header reads "Quick view" (or the record type) in small uppercase muted text, the same size
   as the definition-list labels and not larger than body text.
3. The record name appears as a heading in the body.
4. The open and close controls are two equal, muted icon buttons, each with an accessible name.

## 4. Left navigation: user block at the bottom

**Where:** `educator_interface/templates/educator_interface/interface.html`, `#sidebar-user`.

**Design** (`sidebar__264.png`): a full-width top rule, then one row with:
- a 32px primary-coloured initials avatar
- the name (13px semibold) and a muted second line
- a settings gear on the right

**Now:** For the demodev user (no first or last name), `get_full_name` is empty, so only the email
address shows and looks randomly placed. There is no avatar.

**Should be:**
- An avatar with `request.user.initials`. Reuse the `c-panel-avatar-chip` or the header's avatar
  styling. Do not invent a component.
- `request.user.display_name` as the name. It falls back to the email, so a name always shows.
- A muted second line for the role or the email. Only show what we really have.
- The gear links to the existing `accounts:account_profile` page, with
  `aria-label="Account settings"` and the `settings` icon.
- Pin the block to the bottom of the sidebar.

**QA check to add:**
1. Check the user block for the demodev user, who has no name set.
2. Check it again for a user with a first and last name.
3. Each shows initials in a round avatar, the name, and the gear. Clicking the gear opens the
   account profile page.

## 5. Left navigation: the rule above the user block is partial

**Where:** `_base_interface.html`: the sidebar body wrapper has `px-4 lg:px-6`, and `#sidebar-user`
draws `border-t` inside that padding.

**Design:** The rule spans the full width of the sidebar, edge to edge.

**Should be:** The rule runs the full sidebar width. Either the user block cancels the padding with
negative margins and its own padding, or the padding moves onto the sections instead of the wrapper.
The same applies to any other full-width divider in the sidebar.

**QA check to add:** On desktop, the rule above the user block touches both the left edge of the
sidebar and its right border.

## 6. Left navigation: a full-height right border

**Where:** `_base_interface.html`:
- The shell wrapper has `px-4 sm:px-6 lg:px-8`, and the grid has `lg:gap-12`, so the sidebar floats
  inside the page padding.
- The dialog has no border.

**Design:** The sidebar sits flush to the left edge of the viewport, is white, and has a 1px border
on its right side running from directly under the site header to the bottom of the page.

**Should be:**
- On desktop the sidebar is flush left and has a full-height `border-e border-border`.
- The gap between sidebar and content becomes the content's own padding.
- Do not touch the site header.
- Check that this does not break the learner interface course table of contents, which shares this
  shell. If it would, scope the change through a block override in the educator interface.

**QA check to add:**
1. At 1442 wide, a single vertical rule runs from under the site header to the bottom of the
   viewport, both on a short page and after scrolling a long one.
2. Learner course player regression: its docked table of contents still looks as it did before.

## 7. Left navigation: the active item style

**Where:** `panel_framework/partials/sidebar_nav.html`. The active state is
`aria-[current=page]:bg-primary/10 text-primary font-semibold`.

**Design:** The active item has:
- a `grey-100` fill (`bg-surface-2`)
- primary text and a primary icon
- a 2px primary bar on its left edge, drawn as an inset shadow so it follows the 8px rounded corner
  (`box-shadow: inset 2px 0 0 var(--color-primary)`)

Inactive items are 38px tall, with secondary text (weight 500) and muted icons. Counts would use
the mono font, but we show none.

**Should be:**
- Add the rounded left bar and the `surface-2` shading to the active item.
- Use the same treatment on the expanded instance sub-item.
- Use `shadow-[inset_2px_0_0_var(--color-primary)]` or similar, so the bar follows the radius. Do
  not use a square `border-l`.

**QA check to add (section 1):**
1. The active item has a rounded left accent bar, a tinted fill, and primary text and icon.
2. It still shows that way in dark mode.
3. It survives HTMX navigation between Cohorts, Learners and Courses.

## 8. Left navigation: the organisation switcher looks like a bare select box

**Where:** `educator_interface/templates/educator_interface/partials/organisation_switcher.html`.

**Design** (`sidebar__264.png`, and `educator-mobile-dashboard__m02-navigation-drawer.png` for
mobile): a small-caps "Organisation" overline, then a 44px trigger with:
- a strong border and 8px radius
- a 24px rounded-square initials tile (`surface-2` fill, primary initials)
- the organisation name, semibold and truncated
- an up/down caret

The open list repeats each organisation with its initials tile. On mobile it expands inline as a
bordered list under the trigger.

**Now:** A bordered text trigger with a dropdown arrow, which reads as a plain `<select>`. The
options are plain text rows.

**Should be:**
- A polished switcher with initials tiles on the trigger and on every option, the current option
  checked, a proper popover with a shadow and radius, and hover and focus states.
- On mobile, an inline expanded list inside the nav sheet. The sheet still slides up from the
  bottom.
- The single-organisation static state uses the same visual shell, without the caret.
- Keep the existing HTMX swap behaviour and ARIA (`menuitemradio`).

**QA check to add (section 1, step 5, and section 2, step 6):**
1. Trigger: initials tile, truncated name and caret.
2. Open list: initials tile on every option, and a check on the current one.
3. Arrow keys move between options and Escape closes the list.
4. A 40-character name truncates on the trigger and wraps or truncates cleanly in the list.
5. With a single organisation, the static version shows.

## 9. Main body: page background and surfaces

**Where:**
- `_base.html`: `<body>` has no background, so it is white.
- `cotton/panel-card.html`: `bg-surface`.
- The content header and the data-table card.

**Design:** The main body is a slightly darker canvas (`#F8F9FC`). Cards, the table card and the
detail-page header band (title and tabs) sit on it as white surfaces with a border and a 12px
radius. The sidebar and the page header band are white.

**Now:** The page is white. In first_class, `bg-surface` is `#F8F9FC`, so cards come out *darker*
than the page. That is the inverse of the design.

**Should be:**
- The main content area gets a canvas background.
- Cards, the table card, the modal and the detail header band are the raised surface.
- The canvas must differ from the cards in both themes and in dark mode.
- Do not hard-code hex values. The likely mapping is canvas `bg-surface-2` and cards `bg-surface`,
  but in first_class the cards would then be off-white, not white. Check how first_class already
  makes `.course-card` and `.signup-panel` white (a Tier-2 override in its `theme.css`) and follow
  that pattern if the result needs to match the design.
- Decision for the user: which token the canvas uses.

**QA check to add (section 8):**
1. With `FLS_THEME=first_class` and with the default theme, the main area is visibly darker than the
   cards and table on it, on the cohorts list, cohort detail and learner detail.
2. The sidebar stays white and separated by its border.
3. In dark mode the layering still reads.

## 10. Tabs are not visible anywhere

**Where:**
- `CohortTabSet` in `views.py` (~line 398) has one child.
- `_tab_set_base.html` hides the tab nav when `tabs|length > 1` is false.

**Now:** No screen shows tabs, so the tab widget's look and behaviour cannot be checked.

**Design** (`05-cohort-detail`, `03-learner-detail`, M08):
- Tabs sit in the white header band under the title.
- Labels are 14px in secondary text.
- The active tab has primary text, semibold, and a 2px primary underline.
- A count can follow the label in small mono muted text ("Learners 31").
- The row has a bottom rule. On mobile it scrolls horizontally.

The implementation's active tab uses `text-on-surface`, not primary.

**Should be:**
- Give cohort detail a second tab. Move the Learners card into a "Learners" tab, leaving
  "Details" (details and course registrations) as the first tab. Placeholder content is also
  acceptable; the layout will be rearranged later.
- Restyle the tab nav to the design: primary active colour and underline, and an optional count.
- Tabs keep their own URLs, HTMX region swaps and `aria-current`.

**QA check to add (section 6):**
1. Cohort detail shows two tabs, and the first is active.
2. Click "Learners": only the region below the tabs swaps, the URL changes, the active underline
   moves, and focus stays on the tab.
3. Reload the Learners tab URL: it renders directly with that tab active.
4. Browser back returns to Details.
5. At 392 wide the tab row fits or scrolls horizontally without page overflow.
6. Dark mode check.

## 11. Breadcrumbs and the page title area

**Where:**
- `panel_framework/partials/breadcrumbs.html` and `_build_breadcrumbs` in
  `panel_framework/views.py`
- `views/_list_view_base.html` and `_instance_view_base.html`

**Now:** The cohorts list shows a single breadcrumb, "Cohorts", above a large "Cohorts" title, so
the same word appears twice.

**Should be:**
- **List views:** no breadcrumb. Only the page title (and actions).
- **Instance views:** a back link in place of the breadcrumb trail: a left arrow and the list name
  (for example "← Cohorts"), linking back to the list view with HTMX nav. The design shows this as
  `← Cohorts` in primary, semibold and small. Use the existing `previous` icon.
- This applies to cohort, learner and course detail.
- The mobile M05 and M08 screens show the same back-arrow pattern.

**QA check to add (sections 3, 5 and 6):**
1. The cohorts, learners and courses lists show no breadcrumb.
2. Cohort and learner detail show "← Cohorts" and "← Learners".
3. Clicking the back link returns to the list without a full reload, and the sidebar active state
   follows.
4. On the phone the back link has a hit area of at least 44px.

## 12. Other differences spotted against the design

These were found by reading the design. Fix them alongside the items above.

1. **Detail header band.** In 05 and 03 the title block (title, meta line, tabs) sits in a white
   band with a bottom border, full width of the content column, above the canvas. Today the title
   sits straight on the page with a `border-b`. This depends on item 9.
2. **Card headings.** The design's card titles are about 17px, semibold, in the heading font, with
   no rule under them in definition cards ("Cohort details", "Learner details"). They keep a rule
   only when a list or table follows ("Module completion"). `panel-card` always draws
   `border-b` under the header. Drop the rule for definition cards, or make it optional.
3. **Card padding and radius.** The design's cards have 24px padding and a 12px radius
   (first_class `--fls-radius-lg`). Check that `panel-card` (`rounded-lg`, `px-6 py-4`) resolves to
   the same values under first_class.
4. **Definition grid.** The design uses three columns on desktop and two on phone, with 11px
   overline labels and values in body text. Dates and numbers in mono. Check that
   `panel-definition-row` matches. Use the mono font only for values that really are dates or codes.
5. **Sidebar group headings.** "Teaching" and "Organisation" are overline style, with padding
   about 10px 8px 4px. Check that they match the switcher label so the two read as one system.
6. **Page actions.** In the design, page actions ("Edit cohort", "Create cohort") sit at the right
   of the top row, level with the back link or title. Make sure they stay level with the title on
   desktop and do not wrap under it at 1024 wide.
7. **Quick panel width and border.** The design's panel has a start border and no heavy shadow when
   docked. Today it uses `shadow-xl` in every mode. Keep the shadow for the modal and sheet modes
   only.

**QA check to add:** A side-by-side pass of each in-scope desktop screen against its design
screenshot at 1442 wide with `FLS_THEME=first_class`:
- `sidebar__264`
- `02-learners-table`
- `03-learner-detail` (left part only)
- `05-cohort-detail`
- `07-create-cohort-modal`

Do the same for the in-scope mobile screens at 392 wide:
- `m03`
- `m04`
- `m05`
- `m08`
- `m10`

Ignore the out-of-scope content listed in `design.md` and `research_current_vs_design.md`. The
mobile navigation must still be a bottom sheet, even though M02 draws a left drawer.

---

## Follow-up for the QA plan

When these fixes are made, update `3. frontend_qa.md` with the "QA check to add" steps above, in the
sections they name. Also add a new section, "Quick panel":
- open and close from the trigger buttons
- the header style
- content does not shift (items 1 to 3)
- Escape and backdrop close below 1280 wide
- focus returns to the trigger button on close
