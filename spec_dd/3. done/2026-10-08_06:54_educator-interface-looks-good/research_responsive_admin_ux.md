# Research: responsive admin / educator dashboard UX, applied to the design

Source note: the WCAG 2.5.8 text was fetched and verified. Other URLs are well-known authoritative guidance cited from established knowledge and were not re-fetched in this run (marked "unverified fetch"). Design observations come from `design_screenshots/` (M02, M03, M04, M05, 02).

## 1. Data tables on mobile

Findings
- Wide tables should become stacked cards or lists at narrow widths. Each card holds the row's identity plus the 2 to 4 attributes the user acts on. Secondary columns move to the detail page. Horizontal scroll is the most common complaint (lost row identity, hidden sort and actions, poor discoverability). (NN/g "Mobile Tables" https://www.nngroup.com/articles/mobile-tables/ ; Smashing "Designing better data tables" https://www.smashingmagazine.com/2019/01/table-design-patterns-web/ ; unverified fetch)
- Sort, filter and pagination must stay reachable. Search stays inline. Filter and sort collapse into one control that opens a sheet. Active filters stay visible as chips, and the result count is shown. (Material "Chips" and "Data tables" https://m3.material.io/components/chips ; GOV.UK "Filter" pattern https://design-system.service.gov.uk/ ; unverified fetch)
- Pagination beats infinite scroll for admin lists. Users need to find their place and reach a footer or tab bar. (NN/g "Infinite scrolling" https://www.nngroup.com/articles/infinite-scrolling-tips/ ; unverified fetch)

Implications for this design
- M03 follows the pattern well. Each card shows avatar initials, name, status chip, cohort plus recency, a progress bar and a chevron. Active "Stalled" chip, Filter and Sort buttons are all visible. That is the right card content, so keep it to those items.
- Desktop table columns are Learner, Cohort, Progress, Last active, Status, plus a checkbox and a row menu. The card drops the checkbox, the row menu and the email. This is fine as a restyle, but the card is the whole-row tap target. The row menu and bulk selection have no mobile equivalent in the design. Do not invent one.
- Risk: the design's pagination (1 2 3, Previous, Next) and the "showing 8 of 31" count do not appear in M03. Keep the project's existing pagination at mobile width. Make it a compact Previous/Next with a count, not a long run of page numbers.
- Risk: the mobile card must not rely on colour alone for status. M03 uses a text chip, which is good.
- Requires the same server-rendered view to render both layouts (CSS responsive switch, not two data paths). Beware duplicated DOM that doubles HTMX target IDs, and screen readers reading both layouts. Hide one with `hidden`/`display:none`, not just by visual clipping.

## 2. Mobile navigation: bottom tab bar plus drawer

Findings
- Bottom tabs suit 3 to 5 top-level destinations used often. The drawer or "More" holds the rest. Using both is common and acceptable if destinations are not duplicated confusingly. (Material "Navigation bar" https://m3.material.io/components/navigation-bar ; Apple HIG "Tab bars" https://developer.apple.com/design/human-interface-guidelines/tab-bars ; NN/g "Hamburger menus and hidden navigation hurt UX metrics" https://www.nngroup.com/articles/hamburger-menus/ ; unverified fetch)
- Pitfalls: more than 5 tabs, duplicate entries with different behaviour, hidden current location, and tab labels that truncate. Keep labels visible next to icons. The active tab needs a non-colour cue. Tab bar and drawer should show the same active state.
- Tenant or organisation switchers belong near the top of the navigation (drawer header or top bar), labelled with the current organisation, since a switch changes all data. Make the current organisation always visible. (NN/g and Material guidance on account/context switching, unverified fetch.)

Implications for this design
- Tab bar has 4 items (Dashboard, Cohorts, Learners, More). That is within limits. But Dashboard is out of scope here (no dashboard exists). Do not build a Dashboard tab. Tabs should be only the existing sections (Cohorts, Learners, Courses). Confirm with the spec, but do not add a destination just because the design draws one.
- M02 drawer repeats Dashboard, Cohorts, Learners, Courses, which are also tabs. The design therefore duplicates destinations (tabs and drawer). That duplication is acceptable if the drawer is the full list plus the organisation switcher and the user, but both must show the same active state. "More" and the top-left hamburger both open the drawer or similar, which is two entry points to one thing. Make both open the same drawer rather than two different overlays.
- Drawer places the organisation switcher at the top under the brand. Good. It must show the current organisation, and the list of other organisations must be keyboard reachable (button with `aria-expanded`).
- Admin-only items in the drawer (Educators, Roles, Settings) are out of scope. Omit them and the nav group headers that would be empty.
- Count badges (12, 284, 9) in the nav are decorative extras. They would need new queries on every page. Treat as out of scope unless the spec asks.
- The FAB "+" in M03 overlaps the content above the tab bar. It can hide the last card's chevron and needs bottom padding on the list. It is a primary action (add learner) the project may not have. Include only if an existing action exists.

## 3. Bottom sheets and dialogs

Findings
- Use native `<dialog>` with `showModal()`. It provides focus trapping, Escape to close, inert background and top-layer rendering. Return focus to the invoking control on close (explicit in older browsers). (MDN `<dialog>` https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog ; WAI-ARIA APG Dialog (Modal) https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ ; unverified fetch)
- Scroll lock: `<dialog>` does not lock body scroll by itself. Add `overflow: hidden` on the body (or `:has(dialog[open])`) and `overscroll-behavior: contain` on the sheet. iOS Safari scroll-chaining is a common bug.
- Bottom sheets suit short choices and short forms. For longer forms or ones with the keyboard open, full-screen is more robust, since the on-screen keyboard shrinks the viewport. Use `100dvh`/`dvh` units and keep the primary action sticky. (Material "Bottom sheets" https://m3.material.io/components/bottom-sheets ; NN/g "Bottom sheets" https://www.nngroup.com/articles/bottom-sheet/ ; unverified fetch)
- Sheets need a visible close affordance (Cancel/close button), not just drag-to-dismiss and a handle. Drag-only dismissal is inaccessible.

Implications for this design
- One component, two presentations: the same `<dialog>` is a centred modal on desktop (create cohort) and a bottom-anchored sheet on mobile (M04 filter, M10 create cohort), via CSS only. Avoid two separate implementations.
- M04 has a handle, a Reset link, Cancel and a "Show 3 learners" primary. The handle is decorative; Cancel gives the accessible close. Keep Cancel. A live count on the primary button requires a server round trip. Treat it as a restyle risk and drop it, or use static copy like "Apply", unless it already exists.
- M04 sort options are a selectable list with a check mark. Use radio inputs (or `aria-checked`) so the selection is exposed to assistive tech. The status chips are toggles: use checkboxes or `aria-pressed`.
- Create cohort sheet (M10) has text fields, so the keyboard will open: keep the footer actions reachable (sticky) and use `dvh`.
- HTMX 422 on validation errors must re-render inside the open dialog without closing it or losing focus.

## 4. Accessibility basics a restyle must not break

Findings
- WCAG 2.2 SC 2.5.8 (AA): pointer targets at least 24 by 24 CSS px, unless spacing, equivalent, inline, user-agent or essential exceptions apply. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html (verified). Platform guidance is larger: Apple 44pt (https://developer.apple.com/design/human-interface-guidelines/accessibility), Material 48dp (https://m3.material.io/foundations/designing/structure). Aim for 44 px on mobile primary controls.
- Contrast (1.4.3 AA): 4.5:1 for normal text, 3:1 for large text and UI components (1.4.11). https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html (unverified fetch)
- Focus visible (2.4.7) and, in 2.2, Focus Not Obscured (2.4.11): a sticky bottom bar or sticky header must not hide the focused element. https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html (unverified fetch)
- Reduced motion: wrap sheet slide and drawer transitions in `@media (prefers-reduced-motion: reduce)`. https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion (unverified fetch)
- Tabs: ARIA tabs (`role=tablist`, arrow keys, `tabpanel`) fit when panels switch in place on one page. When each tab is a different URL or an HTMX-loaded view, navigation links with `aria-current="page"` are simpler and more correct. APG tabs https://www.w3.org/WAI/ARIA/apg/patterns/tabs/ ; GOV.UK Tabs warns against tabs for content users must compare, https://design-system.service.gov.uk/components/tabs/ (unverified fetch)

Implications for this design
- Risks of tiny targets: the desktop row "..." menu, the filter-chip "x", the table checkboxes, the small chevrons and the settings cog in the sidebar footer all look under 24 px as drawn. Pad their hit areas to at least 24 px (44 px on mobile) even if the glyph stays small.
- Light grey secondary text (the uppercase section labels such as ORGANIZATION and TEACHING, the "Locked" text, the percentage labels, the monospace "last active" text in the table and the muted nav counts) looks close to or below 4.5:1 at small size. Use the project's theme tokens, then check contrast. Do not lighten text to match the screenshot.
- Status chips (Stalled yellow, Retake due red) use colour plus a text label. Keep the text label. Do not turn them into dots.
- Learner detail tabs (Overview, Progress, Assessments, Activity): decide by implementation. If tabs switch panels via HTMX or load a URL, use links with `aria-current`. If they switch in-page panels, use full ARIA tabs with arrow-key support. Do not do half of each (role=tab on links). On mobile the four labels fit at 375 px as drawn, but there is no room for more or longer labels. Allow horizontal scroll on the tab strip with a visible edge, not wrapping.
- Sticky bottom bars: M05 has a sticky "Message" action bar above the tab bar (two bottom bars). "Message" is out of scope (no messaging). Do not add a second sticky bar, and keep content padding so the focused field is not obscured.
- Truncated organisation name ("Skyward Aviation Ac...") in the desktop sidebar switcher: give the full name through `title` or a tooltip, and keep an accessible name.

## 5. Density and hierarchy for educator/admin views

Findings
- Common LMS admin complaints (Moodle, Canvas, Blackboard): too many options and settings per screen, deep menus, unclear status of learners, hard-to-find "who needs attention", many clicks to reach a learner's progress, inconsistent patterns across sections, and poor mobile behaviour. (Moodle UX discussions https://moodle.org/ ; Canvas community feedback https://community.canvaslms.com/ ; general: NN/g "Data tables" https://www.nngroup.com/articles/data-tables/ ; all unverified fetch, treat as directional)
- Good practice: one clear primary action per screen, visible status chips, scannable rows with strong name hierarchy (name bold, email muted), progress shown visually and as a number, and consistent placement of filters and actions. Do not over-style: dense, readable rows beat spacious cards in desktop tables.

Implications for this design
- Desktop table (02) has strong hierarchy: bold name over muted email, a progress bar with a number, a status chip. That matches the practice. Keep row height at about 60 px, comfortable but not wasteful.
- Learner detail header (avatar, name, ID, status chip, tabs) puts status next to identity. That answers the "who needs attention" complaint. Keep it.
- The design's callout (the yellow "One retake remaining" note), the "Modules" list and "Course completion" card are content features. Restyle only the sections that exist today. The design's callout and quick-view are out of scope.
- Primary actions (Add learner, Import) in the header: keep only the existing actions, and make exactly one the primary style.

## Summary of design risks

1. Duplicate or out-of-scope destinations (Dashboard tab, admin drawer items, nav counts, FAB, Message bar): omit unless an existing feature backs them.
2. Small hit areas (row menu, chip x, checkbox, chevrons, cog): pad to at least 24 px, 44 px on mobile.
3. Low-contrast muted text: verify against project tokens.
4. Tabs semantics: choose links or full ARIA tabs.
5. Dialog/sheet: one native `<dialog>`, CSS-only modal-vs-sheet, with scroll lock, Cancel button, `dvh` and sticky footer.
6. Mobile pagination: the design omits it, so keep the existing one in a compact form.

status: ok
