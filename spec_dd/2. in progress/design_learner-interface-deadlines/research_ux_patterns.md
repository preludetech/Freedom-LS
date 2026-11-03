# Research: UX patterns for deadline status (cards, outline trees, page headers)

Scope: the idea's chosen treatments only (course-card band, next-deadline card at top of outline, inline outline-row dates, current-item deadline card in body header, tablet and mobile outline sheet). Design screenshots were viewed as a visual reference (`key__key`, `cards__card-c`, `p-sb__sb-b`, `p-outline__ol-a`). Colours, fonts and icons from them are not adopted. Pattern claims come from the cited design systems and NN/g articles; URLs were not re-fetched this session, so treat quotes as paraphrase.

## 1. Status bands / strips on cards

- A full-width strip attached to the card media or edge is the "banner/inline-alert on a card" pattern. It carries one status plus one short fact. Reads as a status of the whole card, not an attribute among others. Carbon's status indicators and Atlassian's lozenge guidance both say status belongs in a consistent, predictable spot so scanning a grid compares like with like.
- Design's card-C: band directly under the thumbnail, left = deadline kind/subject ("Course due", "Module 2 quiz"), right = date plus relative ("02 Mar · 3 days left", "was due 25 Feb"). Cards with no deadline have no band; the footer shows a quiet "No deadline".
- Pitfall: a band appearing on some cards and not others shifts content (the design shows progress bars at different heights across a row). Reserve the band slot or align the card body to the bottom (flex column, `mt-auto` footer) so progress bars align across the row. Worth a spec decision.
- Band is stronger than a pill: use it only for states needing attention (due soon, overdue). Neutral/far-off dates can drop to a quiet footer line or no band, so the grid is not wall-to-wall bands (alert fatigue; Carbon notification guidance: https://carbondesignsystem.com/patterns/notification-pattern/).
- Accessibility: band text must carry meaning without colour (icon + words); contrast >= 4.5:1 for text on the tinted fill (WCAG 1.4.1, 1.4.3).

## 2. Badge/pill vs plain-text date

- Pill/lozenge: for a state (Overdue, Due soon). Atlassian Lozenge: short, uppercase-or-sentence label, colour = semantic meaning, never decorative, and keep text to 1-2 words (https://atlassian.design/components/lozenge). Carbon tag and Polaris Badge say the same: badges communicate status, not content (https://polaris-react.shopify.com/components/feedback-indicators/badge, https://carbondesignsystem.com/components/tag/usage/).
- Plain text: for a value (the date itself). A date is data, so plain text (optionally coloured, with icon) in dense lists; a pill around every row date makes a tree noisy. Rule of thumb from the systems: pill = status needing the eye, text = information.
- Design applies this split: outline rows use coloured mono text plus small icon (no pill); the key uses full pills only in the legend/header blocks.
- Don't put the pill and the plain date for the same fact in one place; pick one (redundancy bloats).

## 3. Icon + colour status systems

- Traffic-light (green/amber/red for every item) tells everything is "fine" only by presence of green and drowns urgency. Neutral-until-urgent is the stronger pattern: items far from the date stay neutral grey; amber near; red only past/today. Design's key: upcoming (>7 days) neutral; due soon (<=7 days) amber; due today red-tinted; overdue solid red, "the only filled state". Four states, one filled. Matches GOV.UK guidance to use colour sparingly with text (https://design-system.service.gov.uk/components/tag/) and Carbon's status-indicator pattern (https://carbondesignsystem.com/patterns/status-indicator-pattern/): never colour alone; pair with icon and text; use shape differences so colourblind users can distinguish.
- Icon vocabulary (concept; map to the project's own icon set): calendar (neutral upcoming), clock (soon/today), exclamation/alert (overdue). Outcome types (informational, marked late, locks) are separate, secondary glyphs; keep them out of rows/cards where space is scarce (show on the detail card only).
- Material: error/warning/neutral roles, and "don't rely on colour alone" (https://m3.material.io/foundations/designing/color-roles; accessibility: https://m3.material.io/foundations/accessible-design/patterns).
- Thresholds are a product decision (7 days in the design); keep them in one place, and compute state server-side so cards, rows and headers agree.
- Colour semantics should not clash with completion: green is typically "complete" (design's progress/ticks are green). So deadline colours must not reuse green; neutral grey is right for upcoming.

## 4. Compact date formats

- Absolute, short: "Fri 14", "14 Mar", "02 Mar". Relative: "in 2d", "3d late", "2 days left", "was due 25 Feb".
- NN/g and GOV.UK: dates must be unambiguous; GOV.UK writes "14 March 2026" in full in prose and avoids numeric-only forms (https://design-system.service.gov.uk/patterns/dates/ and https://www.gov.uk/guidance/style-guide/a-to-z-of-gov-uk-style#dates). Abbreviate month only under space pressure; never use 03/04 numeric.
- Relative dates are friendlier near the deadline and meaningless far out ("in 83d"). Common hybrid: absolute when > ~7 days; relative or day-name when inside a week ("Fri 14", "in 2d", "Today 23:59"); "Nd late" after. Absolute stays the source of truth (Atlassian date guidance: https://atlassian.design/content/writing-guidelines/ shows relative with absolute on hover; Polaris date guidance: https://polaris-react.shopify.com/content/actionable-language and content/fundamentals).
- Pair both on cards/headers where room ("02 Mar · 3 days left"); pick one in rows ("Mar 02" or "3d").
- Due today: show the time instead of the date (design: "Due today · 23:59"). Time zone: state or use the learner's zone; deadlines are ambiguous without one.
- Locale and i18n: abbreviations like "d" are English-only; use framework date formatting/`naturalday`-style helpers where possible. Relative strings drift stale on cached pages; relative-time computed at render is fine for a server-rendered page, but note that a long-open tab goes stale.
- Past: "was due 25 Feb" / "3d late" is clearer than a negative number. "Overdue" word can be the state label while the row only shows the date.

## 5. Truncation and tooltips

- Row text budget in a 240-320px sidebar: index + status icon + title + trailing date. Titles truncate with ellipsis (design: "Airspace fundament…"); the date must be non-truncating (`shrink-0`, `whitespace-nowrap`) so the truncated thing is always the title. The design's tightest rows swap duration for date, so there is exactly one trailing slot.
- Tooltips as enhancement only: hover/focus tooltips (full title; full date + time zone + consequence) are fine on desktop, but never the only path to information. Fail on touch: no hover, long-press is not discoverable, tap targets compete with navigation (the tap activates the row link), and focus-only tooltips vanish on blur. NN/g: tooltip guidelines and why hover-hidden information fails (https://www.nngroup.com/articles/tooltip-guidelines/); WCAG 1.4.13 content on hover/focus must be dismissible, hoverable, persistent (https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus.html). Atlassian/Carbon/Polaris all say tooltips must not hold essential or interactive content (https://atlassian.design/components/tooltip, https://carbondesignsystem.com/components/tooltip/usage/, https://polaris-react.shopify.com/components/overlays/tooltip).
- Do: put the full title and full-form date in the item's own detail view (header card) and the accessible name (`aria-label`/visually hidden text, e.g. "Due 14 March, 3 days left") so screen readers get the full phrase even if the visible text is "14 Mar". Use `title` attribute only as a bonus.
- Mobile: no truncation reliance; the sheet is wider so titles get more room, and rows can wrap onto two lines.

## 6. Outline rows combining completion state and date state

- Two independent dimensions: completion (not started / in progress / done / locked) and time (none / upcoming / soon / overdue). Combine by keeping them in separate slots: leading slot = completion icon (existing), trailing slot = date. Do not mix a completion colour with the deadline colour in the same glyph.
- Completed items: suppress the deadline (nothing left to do), or show it muted. A completed item with a red "overdue" date is a false alarm. Design's outline shows dates only on not-yet-done rows (done modules show duration, not dates). Overdue-but-completed-late is a record, not a call to action.
- Locked rows: design dims whole rows but still shows their date, because the date is what the learner needs to plan. Dimmed row text with legible date colour is a contrast risk; check contrast on the dimmed state (disabled elements are exempt from WCAG 1.4.3 but the date is information).
- Parent/child (module with sections): where a child has the deadline, roll up the earliest unfinished child deadline to the collapsed parent row (design: "Today" on the module while the child "3.5 Section quiz" shows "03 Mar"), so a collapsed tree does not hide urgency. Rollup rule: earliest unfinished deadline among descendants; expand to see which. Spec must define it; don't show both parent and child own-date duplicates unless they differ.
- Current-item highlight (background tint) must stay distinct from deadline colours.
- One date per row max. If a row has several deadlines (type variants), show the most urgent and let the detail show the rest.
- Reading order for screen readers: title, completion state, then deadline. Visual order can differ; DOM order matters.

## 7. "Next up" summary cards

- Pattern: a compact card pinned above a long list that answers "what do I do first?". Label ("Next deadline"), subject, status pill/time-left, optional secondary link ("All 7 ->") to the full list. Design's sidebar card: label, linked title, pill "Due today · 23:59", outcome tag ("Target date"), and a count link.
- Chosen by: earliest unfinished deadline, overdue first (overdue outranks upcoming even though it is earlier in time anyway). Define tie-breaks (deadline type, position in course). Scope: the course in this player, not all courses.
- Pin it outside the scrolling tree (or at least at the top) so it is visible without scrolling; on short laptop screens it costs ~100px of outline height, so consider collapsing to one line under a height threshold.
- Tint card by urgency state (same palette as rows), neutral border when far off. Make the whole title a link to the item.
- Keep it the same component across desktop sidebar, tablet, and mobile sheet (tablet and mobile views reuse it, per the screenshots).
- Don't duplicate the full-course deadline list here (drawer/popover is out of scope).

## 8. No deadline and everything done

- No deadline on a card: show nothing in the band slot (or a muted "No deadline" in the footer as the design does). A muted explicit note makes absence deliberate and helps align heights; it also tells the learner it was not forgotten. Do not show a placeholder band.
- No upcoming deadlines in a course (none set): hide the next-deadline card entirely (empty cards are noise, per Carbon empty-state guidance, which says empty states should be for areas expected to have content: https://carbondesignsystem.com/patterns/empty-states-pattern/). Optionally nothing; do not show "No deadlines" in the outline.
- All deadlines met/completed: either hide the card or show a quiet success line ("All deadlines met") without celebratory colour. Pick one; hiding is simpler and consistent. If shown, green is OK here (it is a completion message) and must not look like an alert.
- Only past, unfinished deadlines remain: card stays and is red (overdue still the "next" thing to do).
- Current item with no deadline: omit the header card, don't reserve a blank block (header title area shifts on navigation between items; acceptable, but make the header layout robust to its absence: the card is on the right, so the title keeps full width when it is missing).
- Deadline kind with no consequence ("target date"): still shown; consequence tag is secondary.

## 9. Responsive collapse

- Desktop: persistent sidebar (about 320px) with the next-deadline card, outline rows with trailing dates; header block floats right of the title.
- Tablet: sidebar stays but narrower or collapsible; trailing-date slot becomes the first thing to be squeezed, so the title truncates harder. Design keeps the card and dates at tablet width. Decide a minimum width below which date shows an icon + short form only.
- Mobile: outline becomes an on-demand sheet (bottom sheet/drawer); full-width rows give dates room back. Material guidance: bottom sheets for secondary content on compact windows, sidebars become modal navigation drawers (https://m3.material.io/components/bottom-sheets/guidelines, https://m3.material.io/components/navigation-drawer/overview). Carbon: UI shell side nav collapses to a hamburger at small breakpoints (https://carbondesignsystem.com/components/UI-shell-left-panel/usage/).
- Sheet needs: >= 44x44 (WCAG 2.5.5 target size) tap rows, focus trap, close affordance, no hover-only info (section 5).
- Header block on mobile: on narrow widths a "block on the right" cannot sit beside the title; stack it under the title, full width, or move it into the sheet-adjacent sticky bar. Define the breakpoint where it stacks. Consider placing the card above the title text so the date is visible without reading the heading.
- Sidebar card on mobile: first item in the sheet, as on tablet; also usable as the summary if the sheet is scrolled.
- Use responsive container rules, not separate markup, where possible: one component, CSS-driven variants (shared among the three surfaces, matching the project's rule against repeating code).

## 10. Implications for the spec (observations, not scope)

1. One urgency model, computed once (none / upcoming / soon / today / overdue) and reused by band, outline rows, next-deadline card and header card.
2. Neutral until within a threshold; only overdue is filled. Colour never alone (icon + text).
3. Rows: one trailing date; non-truncating; hidden or muted when the item is complete; parents roll up earliest unfinished child deadline.
4. Absolute date with a relative form near the deadline; "today" shows time; past shows "was due"/"Nd late"; full phrase in the accessible name.
5. No tooltips for essential info; touch-safe.
6. Empty cases: no deadline = no band/no card; all met = hide (or quiet message); overdue stays.
7. Reserve layout so grids and headers do not jump when a band or card is absent.
8. One shared component across desktop, tablet and the mobile sheet.

## References

- Atlassian Lozenge: https://atlassian.design/components/lozenge
- Atlassian Tooltip: https://atlassian.design/components/tooltip
- Atlassian writing guidelines (dates): https://atlassian.design/content/writing-guidelines/
- GOV.UK Tag: https://design-system.service.gov.uk/components/tag/
- GOV.UK dates pattern: https://design-system.service.gov.uk/patterns/dates/
- GOV.UK style guide (dates): https://www.gov.uk/guidance/style-guide/a-to-z-of-gov-uk-style#dates
- Material 3 colour roles: https://m3.material.io/foundations/designing/color-roles
- Material 3 accessible design: https://m3.material.io/foundations/accessible-design/patterns
- Material 3 bottom sheets: https://m3.material.io/components/bottom-sheets/guidelines
- Material 3 navigation drawer: https://m3.material.io/components/navigation-drawer/overview
- Carbon status indicator pattern: https://carbondesignsystem.com/patterns/status-indicator-pattern/
- Carbon notification pattern: https://carbondesignsystem.com/patterns/notification-pattern/
- Carbon tag: https://carbondesignsystem.com/components/tag/usage/
- Carbon tooltip: https://carbondesignsystem.com/components/tooltip/usage/
- Carbon empty states: https://carbondesignsystem.com/patterns/empty-states-pattern/
- Carbon UI shell left panel: https://carbondesignsystem.com/components/UI-shell-left-panel/usage/
- Polaris Badge: https://polaris-react.shopify.com/components/feedback-indicators/badge
- Polaris Tooltip: https://polaris-react.shopify.com/components/overlays/tooltip
- Polaris actionable language: https://polaris-react.shopify.com/content/actionable-language
- NN/g tooltip guidelines: https://www.nngroup.com/articles/tooltip-guidelines/
- WCAG 1.4.13 content on hover or focus: https://www.w3.org/WAI/WCAG21/Understanding/content-on-hover-or-focus.html
- WCAG 1.4.1 use of colour: https://www.w3.org/WAI/WCAG21/Understanding/use-of-color.html

status: ok
