# Research: UX, accessibility, and usability pitfalls for non-modal "quick view" side panels

Scope: a right-hand quick-view drawer triggered from cells in an educator's course-progress table. Page underneath stays interactive (educator can click another cell, scroll, etc.). On mobile the panel becomes a full-screen overlay. Open state is ephemeral (not in URL).

---

## Accessibility model

- The W3C ARIA APG `dialog` pattern is **modal-first**: it assumes focus is trapped and `aria-modal="true"`. Using it for a non-modal drawer is the most common misuse. See the open APG discussion explicitly noting that "the difference between modal and non-modal dialogs appears to be almost non-existent" in the current pattern, which "defeats the purpose of a non-modal dialog." (https://github.com/w3c/aria-practices/issues/1021, https://github.com/w3c/aria-practices/issues/102)
- The right pattern for a non-modal, click-to-reveal panel that stays in the page flow is the **Disclosure pattern**, not the Dialog pattern. The trigger is a `<button>` with `aria-expanded` and `aria-controls`; the panel is a region with `aria-labelledby` pointing at the button (or its own heading). (https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/)
- A subtlety: disclosure assumes the **same button** toggles open and close. If your "trigger" is a table cell that only opens (and a separate close button closes), aria-expanded on the cell is ambiguous. Two clean options:
  - Treat each cell as the disclosure trigger, with `aria-expanded` reflecting whether **its** detail is currently shown in the panel; clicking the already-expanded cell collapses. (https://github.com/adaptlearning/adapt-contrib-core/issues/657)
  - Or: treat the panel as a `role="region"` with `aria-label="Quick view"` and use `aria-pressed`/`aria-selected` on cells (see "Specific to table-cell triggers" below) to express selection, not disclosure.
- Recommended ARIA on the panel itself for the non-modal case:
  - `role="region"` (a labelled region that screen readers can navigate to as a landmark when it has an accessible name).
  - `aria-labelledby="quickview-heading"` (or `aria-label="Quick view"` if there is no visible heading).
  - **Do not** add `role="dialog"` + `aria-modal="true"` for the desktop/non-modal case — that lies to AT and conflicts with the still-interactive background.
  - **Do not** apply `inert` or `aria-hidden` to the rest of the page — the page must remain reachable. (https://web.dev/articles/inert)
- Trigger button should expose state and target:
  - `aria-expanded="true|false"`
  - `aria-controls="quickview-panel"`
  - Visible accessible name describing the cell ("Quick view: Alice — Module 3").

References:
- W3C APG Disclosure pattern: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- W3C APG Dialog (Modal) pattern (for contrast): https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- MDN aria-modal: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal
- TPGi, current state of modal dialog accessibility: https://www.tpgi.com/the-current-state-of-modal-dialog-accessibility/

---

## Keyboard & focus

- **Esc closes**: convention, expected even for non-modal panels. Restore focus to the cell that opened it. (https://github.com/mattermost/mattermost/pull/34132)
- **No focus trap.** The whole point is that the educator can Tab back out into the table. If you trap, you have a modal in disguise. (https://github.com/w3c/aria-practices/issues/1021)
- **Initial focus on open**:
  - Move focus into the panel (typically the panel heading made focusable with `tabindex="-1"`, or the close button) so screen-reader and keyboard users can immediately read/act on the new content.
  - Some non-modal patterns argue: **leave focus on the trigger** and only move focus when the user explicitly Tabs in. Trade-off:
    - Move focus → screen-reader user notices new content immediately, but interrupts table-row navigation.
    - Leave focus → keyboard table navigation is preserved, but content change can go unnoticed without a live-region announcement.
  - Recommended for a quick-view panel where users repeatedly click cells: **leave focus on the cell** and use an `aria-live="polite"` announcement (see next section) so they can keep arrow-keying through cells. Provide a documented shortcut (e.g. `F6` or a "Jump to quick view" button) to enter the panel. F6 is the W3C-suggested shortcut for moving focus between non-modal dialogs and the main page. (https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- **Tab order**: panel content should sit in DOM order such that Tab moves into it after the trigger, or place it as a sibling of `<main>` so Tab from the table eventually reaches it. Avoid teleporting it to the end of `<body>` without a way to reach it; that creates an "orphan" region.
- **Focus when content swaps to a new item**:
  - If the user clicks a different cell while the panel is open, the panel content is replaced but focus should remain on the newly clicked cell. Do **not** snatch focus into the panel each time — it makes rapid browsing impossible.
  - Update the `aria-live` region with the new context (e.g. "Quick view updated: Bob — Module 3, 60% complete") so AT users hear the swap.
- **Closing**:
  - Close button inside the panel (visible, labelled "Close quick view"). On click → restore focus to the most recently triggering cell.
  - Esc → same.
  - If the triggering cell no longer exists (e.g. table re-rendered), fall back to a stable anchor like the panel toggle in the table header, or `<main>`.
- Sources: https://www.makethingsaccessible.com/guides/accessible-nav-drawer-disclosure-widgets/ , https://aaardvarkaccessibility.com/keyboard-accessibility-101-basics-you-cant-ignore/

---

## Screen reader

- Add a polite live region (`aria-live="polite"`, `aria-atomic="true"`, visually hidden) that gets updated with a short summary when the panel opens or its content swaps.
  - Example payload: "Quick view: Alice Smith, Module 3, 60% complete, last activity 2 days ago."
  - Keep it concise; live regions interrupt context.
  - https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions
- Live region must already exist on page load (not injected at click time) — screen readers don't reliably observe regions added after the fact unless you wait ~2s. (https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-2/, https://www.tpgi.com/screen-reader-support-aria-live-regions/)
- For loading states inside the panel:
  - Render a skeleton with `aria-busy="true"` on the panel container.
  - When data arrives, set `aria-busy="false"`. Pair with a polite "Loaded" announcement only if the wait is perceptible (>~500ms).
- Avoid `aria-live="assertive"` for routine swaps — it interrupts whatever the user is reading. Reserve assertive for errors.
- The panel itself, once labelled (`aria-labelledby` or `aria-label`) and given `role="region"`, becomes a navigable landmark in screen readers like NVDA/JAWS — users can jump to it via the regions/landmarks list.

---

## Mobile breakpoint flip

- This is the big trap: at narrow widths the panel covers the page entirely, so the underlying content is no longer visible or interactive. That **is** modal behaviour, and ARIA semantics should reflect reality.
- Recommendation: at the mobile breakpoint, switch to a true modal:
  - `role="dialog"` + `aria-modal="true"`
  - Apply `inert` to the rest of the page (or `aria-hidden="true"` as fallback for older browsers)
  - Trap focus inside
  - Esc still closes; close button still required
- Common pitfalls when flipping:
  - Forgetting to add `inert` on mobile — keyboard/AT users can Tab "behind" the visually-covering drawer.
  - Forgetting to **remove** `inert` on resize back to desktop — page becomes inert until reload.
  - Animating between states while the breakpoint flips — can leave focus orphaned. Listen for `matchMedia` change events and re-evaluate ARIA + focus state explicitly.
  - Address-bar resize on mobile Safari/Chrome triggers viewport changes; debounce the breakpoint flip.
- A reasonable cutover point: when the panel would occupy ≥ ~85% of viewport width, treat it as modal. Tailwind's `md` (768px) is a common natural break.
- Source overview: https://www.nextjsshop.com/resources/blog/responsive-dialog-drawer-shadcn-ui , https://web.dev/articles/inert

---

## Common pitfalls and how to avoid them

- **Treating the non-modal drawer as a modal.** Locks users in, breaks the "click another row" flow, lies to AT. (https://github.com/w3c/aria-practices/issues/1021)
- **Lost context / "where did my work go?"** Panel covers the very row the user just selected. Mitigations:
  - Keep panel narrow enough not to occlude the table on desktop.
  - Use a push layout (table reflows narrower) **or** an overlay layout with a visible offset; pick one and stick with it.
  - Visibly mark the selected row (see next section).
- **Content reflow / layout shift when panel opens.** If you "push" the table by shrinking it, columns can wrap or hide unexpectedly. Either:
  - Reserve space at the gutter so opening doesn't reflow the whole table, or
  - Use an overlay (transform/opacity animation, not max-height/width) so the underlying flow is unchanged. (https://www.smashingmagazine.com/2016/08/ways-to-reduce-content-shifting-on-page-load/, https://web.dev/articles/optimize-cls)
- **Too narrow to be useful.** If users routinely need to scroll horizontally inside the panel to read a row of stats, the panel is too narrow. NN/g recommends sizing detail panels to fit the longest expected primary content. (https://www.nngroup.com/articles/utility-navigation/)
- **Slow load / no skeleton.** Educator clicks cell, sees nothing for 800ms, clicks again — duplicate fetches. Render a skeleton synchronously; use `aria-busy`; debounce trigger; cancel in-flight requests on new click.
- **Dismiss-by-accident.** Click-outside-to-close on a non-modal feels wrong because clicks outside are also legitimate (clicking another cell). Do **not** use click-outside to close on desktop. Instead:
  - Close button (visible)
  - Esc
  - Click a different cell → swap content (don't close)
  - Click the same already-selected cell → close (toggle)
- **No persistence between page navigations.** User clicks a link inside the panel, comes back, panel is gone. Spec says open state is ephemeral and not in URL — make sure the link click doesn't full-page-navigate, or open links in a new tab, or accept that this is a known tradeoff and document it. NN/g flags loss of context as a top app-design mistake. (https://www.nngroup.com/articles/top-10-application-design-mistakes/)
- **Discoverability of the trigger.** A bare cell with no affordance doesn't read as clickable. Add cursor:pointer, hover state, and ideally a small chevron/info icon so the cell looks interactive. (https://www.nngroup.com/articles/icon-usability/)
- **No way to compare two cells.** Quick views are great for "drill down on one"; users frequently want "compare A and B." Either accept this as out-of-scope or provide a "pin" option later.
- **Overflowing the viewport vertically.** Panel must scroll independently of the page; don't assume the panel content fits. Sticky header (item title + close) inside the panel is standard.
- **Stale content after data changes.** If the underlying row updates (e.g. live progress refresh), the open panel can be out of sync. At minimum, re-fetch on focus return; ideally subscribe to the same data source.
- **Hamburger / nav drawer learnings carry over only partially.** NN/g and Smashing both warn that hidden navigation suffers from "out of sight, out of mind." A quick-view panel is opt-in by user click so this is less acute, but the same lesson applies to anything *in* the panel: don't make it the only path to important actions. (https://www.smashingmagazine.com/2017/05/basic-patterns-mobile-navigation/, https://www.nngroup.com/articles/fight-right-rail-blindness/)

---

## Specific to table-cell triggers

- Mark the active cell so the user always knows what the panel is showing. Options ordered from best to worst:
  - `aria-pressed="true"` on the cell-button when it is the source of the open panel. Pairs naturally with a visible "selected" style. (https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-pressed)
  - `aria-selected="true"` if the table is structured as `role="grid"` with `role="row"`/`role="gridcell"`. Only use the grid role if you actually need grid keyboard semantics — Adrian Roselli specifically warns against turning a plain table into a grid just to make rows clickable. (https://adrianroselli.com/2023/11/dont-turn-a-table-into-an-aria-grid-just-for-a-clickable-row.html)
  - `aria-current="true"` is also acceptable and is supported on table cells; it expresses "this is the currently displayed item."
- Visual treatment:
  - Strong but not garish background change on the active cell.
  - Connecting visual line/arrow from the cell to the panel is overkill but a subtle chevron or a left-edge accent on the panel referencing the cell row works well.
  - Maintain the highlight even when the user clicks within the panel — the cell is still "the source."
- Click target:
  - The clickable thing inside the cell should be a `<button>`, not a div with `onclick`. This gives keyboard activation, focus ring, and semantics for free. (https://adrianroselli.com/2023/11/dont-turn-a-table-into-an-aria-grid-just-for-a-clickable-row.html)
  - If the cell already contains links/buttons (e.g. a score with a "view rubric" link), nesting a row-level button breaks. Either move the row-level action to a dedicated cell ("Quick view" column) or use the row-as-link pattern with care.
- Keyboard:
  - Arrow keys for cell navigation are not standard on `<table>`; only adopt that if you also adopt the full grid pattern. Otherwise rely on Tab between cell buttons. Don't half-implement grid semantics.
- Don't lose row context when the panel is full-screen on mobile:
  - Echo the row identity at the top of the panel (e.g. "Alice Smith — Module 3") so the user has not "lost" what they were looking at.

---

## Print, responsive, RTL

- **Print**: hide the panel via `@media print { [data-quickview] { display: none } }` — printed table should show table, not a partial overlay. If users want to print panel contents, give them a per-record print/export action *inside* the panel.
- **Responsive beyond mobile/desktop**: between `md` and `lg`, the panel can squeeze the table such that a column drops below readable width. Define a minimum table width below which the panel must overlay rather than push.
- **RTL**: use CSS logical properties (`inset-inline-end`, `padding-inline`, `border-inline-start`) so the panel slides from the inline-end edge — appears on the right in LTR and on the left in RTL, automatically. Don't hard-code `right: 0` or `left: 0`. (https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/direction, https://medium.com/nerd-for-tech/css-logical-properties-rtl-layouts-236edec711fa)
- Animation direction must also respect RTL: `transform: translateX(100%)` is wrong in RTL. Either animate logical properties (limited browser support) or branch on `dir="rtl"`.
- Reduced motion: respect `prefers-reduced-motion: reduce` — slide animation should fall back to a fade or instant show, otherwise vestibular-disorder users get hit.

---

## Concrete recommendations for FLS

Pulling the above into a checklist for implementation/spec:

- ARIA on the desktop panel
  - `<aside id="quickview-panel" role="region" aria-labelledby="quickview-heading" aria-live="polite" aria-busy="false">`
  - Heading `id="quickview-heading"` inside, focusable via `tabindex="-1"`.
  - Visible close button labelled "Close quick view".
- ARIA on each cell trigger
  - Cell content is a `<button>`.
  - `aria-controls="quickview-panel"`.
  - `aria-expanded="true"` only when this cell is the source of the open panel; `false` otherwise (and absent on cells that have never been the source — either is acceptable but be consistent).
  - Visual "selected" state mirrors `aria-expanded="true"`.
- Polite live region
  - Either reuse the panel's `aria-live="polite"` (preferred) or a separate visually-hidden region updated with a one-line summary whenever panel content changes.
- Keyboard
  - Esc closes, returns focus to the source cell.
  - Clicking the source cell again closes.
  - Clicking another cell swaps content; focus stays on the new cell.
  - Initial focus on open: stay on the cell. Provide an explicit "View details" focusable element inside the panel that users can Tab to next.
  - No focus trap on desktop.
- Mobile breakpoint flip (≤ `md` ~768px or whatever FLS standard is)
  - Re-render with `role="dialog"` + `aria-modal="true"`.
  - Apply `inert` to siblings of the dialog, **remove** on close and on resize back to desktop.
  - Trap focus inside.
  - Esc and close button both close.
- Layout
  - Overlay style on desktop with a `box-shadow` left edge; do not push/reflow the table.
  - Reserve right gutter so table content doesn't sit underneath panel when open.
  - Independent vertical scroll inside panel; sticky panel header (title + close).
  - Use logical properties for inline-start/end so RTL Just Works.
- Loading
  - Render skeleton synchronously; `aria-busy="true"`.
  - Cancel in-flight fetch on new cell click.
  - On error, show inline error inside the panel with a retry button; do **not** close the panel automatically.
- Print: hide.
- Reduced motion: fade or no animation.
- Don't dismiss on click-outside on desktop. Do dismiss on backdrop click on mobile (modal mode).
- Out of scope but flag for future: deep-linking via URL hash, "pin" two panels for compare, browser-history Back to close (mobile only).

---

## Sources

- W3C ARIA APG, Disclosure pattern: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- W3C ARIA APG, Dialog (Modal) pattern: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- W3C aria-practices issue #1021 (modal vs non-modal confusion): https://github.com/w3c/aria-practices/issues/1021
- W3C aria-practices issue #102 (non-modal pattern proposal): https://github.com/w3c/aria-practices/issues/102
- W3C aria-practices issue #59 (draft non-modal dialog pattern): https://github.com/w3c/aria-practices/issues/59
- MDN, ARIA live regions: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions
- MDN, aria-modal: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal
- MDN, aria-selected: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-selected
- MDN, direction (CSS): https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/direction
- web.dev, the inert attribute: https://web.dev/articles/inert
- web.dev, Optimize CLS: https://web.dev/articles/optimize-cls
- TPGi, current state of modal dialog accessibility: https://www.tpgi.com/the-current-state-of-modal-dialog-accessibility/
- TPGi, screen reader support for aria-live regions: https://www.tpgi.com/screen-reader-support-aria-live-regions/
- Sara Soueidan, Accessible notifications with ARIA Live Regions (parts 1 & 2): https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-1/ , https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-2/
- Adrian Roselli, Don't Turn a Table into an ARIA Grid: https://adrianroselli.com/2023/11/dont-turn-a-table-into-an-aria-grid-just-for-a-clickable-row.html
- Heydon Pickering, Inclusive Components: https://inclusive-components.design/
- NN/g, Top 10 Application-Design Mistakes: https://www.nngroup.com/articles/top-10-application-design-mistakes/
- NN/g, Right-Rail Blindness: https://www.nngroup.com/articles/fight-right-rail-blindness/
- NN/g, Bottom Sheets (related pattern): https://www.nngroup.com/articles/bottom-sheet/
- NN/g, Icon Usability: https://www.nngroup.com/articles/icon-usability/
- Smashing Magazine, Modal vs Separate Page decision tree: https://www.smashingmagazine.com/2026/03/modal-separate-page-ux-decision-tree/
- Smashing Magazine, Basic Patterns For Mobile Navigation: https://www.smashingmagazine.com/2017/05/basic-patterns-mobile-navigation/
- Smashing Magazine, Reduce Content Shifting: https://www.smashingmagazine.com/2016/08/ways-to-reduce-content-shifting-on-page-load/
- GOV.UK Design System, Accessibility: https://design-system.service.gov.uk/accessibility/
- GOV.UK Design System, Details component (related disclosure pattern): https://design-system.service.gov.uk/components/details/
- Make Things Accessible, Accessible nav drawer disclosure widgets: https://www.makethingsaccessible.com/guides/accessible-nav-drawer-disclosure-widgets/
- adapt-contrib-core issue #657 (aria-expanded misuse for drawers): https://github.com/adaptlearning/adapt-contrib-core/issues/657
