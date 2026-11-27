# Research: best practices for educator-interface page polish

Method note: written from established knowledge of the cited standards. The URLs were not re-fetched in this run, so verify wording before quoting. This extends `research_comparable_systems.md` (sections 3 to 5) and does not repeat it. Settled in `answers.md`: simple table for the Courses tab, in-progress-first ordering, a smaller visual button with a 44px hit area.

## 1. Inline progress bars in table cells

- Use `role="progressbar"` for task or course completion (a value moving toward a goal). `role="meter"` is for a scalar in a known range, such as disk usage or a score, and has weaker screen reader support. Course progress is a progressbar.
- Required attributes: `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, and an accessible name. A native `<progress value max>` carries the role and values for free; style it with `appearance:none` and the `::-webkit-progress-*` / `::-moz-progress-bar` pseudo-elements. A `div role="progressbar"` with an inner width bar is easier to style in Tailwind. Both are fine.
- Name it by the course: `aria-label="Progress in <course title>"`, or `aria-labelledby` pointing at the visible course name. Add `aria-valuetext="40% complete"` if the text should be more than a bare number.
- The visible percentage is already text beside the bar. Avoid a double announcement: either hide the bar's text from screen readers (`aria-hidden` on the percentage) or leave the bar unnamed-by-value. Simplest: keep the bar labelled and valued, and mark the adjacent percentage `aria-hidden="true"`. Only do this if the bar is exposed; never hide both.
- Static bars (no live updates) need no `aria-live`. Do not make each row a live region.
- Do not rely on colour (WCAG 1.4.1). The bar fill vs. track needs 3:1 contrast against the track and the background (WCAG 1.4.11 non-text contrast). A 4 to 6px bar is acceptable if contrast holds.
- Zero progress: still render the bar with `aria-valuenow="0"` so the row aligns and the state reads.
- In a `<table>`, the cell holding several bars is a list: use a `<ul>` of rows inside the `<td>` so screen readers announce "list, 3 items". Keep the course name in the same row as its bar so the label matches.
- Refs: https://www.w3.org/WAI/ARIA/apg/ · https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/progressbar_role · https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/meter_role · https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html

## 2. "+N more" overflow links in cells

- It must be a real link or button with a name that says what it opens. Visible text "+2 more" is vague out of context (WCAG 2.4.4 Link Purpose, in context). Add visually hidden text: `+2 more<span class="sr-only"> courses for Jane Smith</span>`, or `aria-label` that begins with the visible text (WCAG 2.5.3 Label in Name: the accessible name must contain the visible label).
- A link is right when it navigates (the settled design: the learner's Courses tab). A button is right when it expands in place or opens a popover. Do not use a link for an in-place toggle.
- Show the count of hidden items, not the total, and only when N is at least 1. Do not render an empty element otherwise.
- Include the link in the cell's reading order straight after the list. Give it the same target-size treatment as other compact controls (see section 6), since a short text link in a dense row is a typical 24px failure.
- Keep the cap in one place (a constant or view-side slice) and have the view supply the hidden count, so the template and tests agree.
- Refs: https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html · https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html · https://www.w3.org/WAI/WCAG22/Techniques/general/G53

## 3. Simple tables in panels vs bordered cards

- Design systems agree: do not nest a bordered card inside a card or panel. Carbon, Polaris and Atlassian treat the panel as the one container; inside it use whitespace, dividers between rows, or a table. Polaris explicitly says to avoid cards in cards.
- A table is the semantic choice when each item has the same attributes (course, status, progress, counts). It gives a header row, column alignment and screen reader table navigation. Use `<th scope="col">` in the header and `<th scope="row">` on the course name cell.
- Simple table: no zebra, no vertical rules, a thin horizontal rule between rows (or none), generous row padding, a muted small-caps or small header. Right-align or tabular-num figures (`tabular-nums`) so counts line up.
- Badges: keep to one status badge per row, in a Status column. A reason that repeats the badge (the `NoRecordedActivityRule` text) is noise; where a flag reason adds information, put it in the status cell under the badge or as hidden-by-default detail, not in a separate stacked line.
- Phones: a table in a panel needs either horizontal scroll (`overflow-x-auto` wrapper with `tabindex="0"` and a label, so keyboard users can scroll) or a stacked layout at narrow widths. Prefer stacking the cells per row, with the course name as the row title. Do not remove table semantics with `display:block` without restoring roles (`role="table"` etc.), because CSS display changes can strip semantics in some browsers.
- Add a `<caption class="sr-only">` naming the table.
- Refs: https://polaris-react.shopify.com/components/layout-and-structure/card · https://carbondesignsystem.com/components/data-table/usage/ · https://www.w3.org/WAI/tutorials/tables/ · https://adrianroselli.com/2020/11/under-engineered-responsive-tables.html · https://adrianroselli.com/2018/02/tables-css-display-properties-and-aria.html

## 4. Read-only fields in settings forms (email that cannot be edited)

- Options, in order of preference for a value that is context, not an input:
  1. Not a form field at all: a label and a value in a description-list row (`<dl><dt>Email</dt><dd>…</dd></dl>`) above the form. Simplest, fully accessible, no tab stop, and no misleading input look. Best fit for "show the email, read-only, above the name form".
  2. `<input readonly>`: focusable, submitted with the form, selectable and copyable, announced as read-only. Use if the value should look like a field and be copied.
  3. `<input disabled>`: not focusable, not submitted, skipped by screen readers' tab order, and low contrast (WCAG 1.4.3 exempts disabled controls, but users still cannot read it well). Avoid for information users need.
  4. `aria-disabled` on an input: still focusable but must be blocked in script; not recommended here.
- GOV.UK and Polaris guidance: if a value cannot be changed, show it as plain text, not as a greyed field; if the user may wonder why it cannot be changed, say why in hint text ("Change this on the learner's account" or "Learners sign in with this address").
- Keep the email outside the `<form>` so a Save does not post it and the page cannot be tampered with. Do not add a field the view would then have to ignore.
- Make the value copyable and not truncated; wrap long addresses (`break-all` or `overflow-wrap:anywhere`). A `mailto:` link is optional and expected to work, so only add it if it does.
- If shown as a row in the panel, match the panel's label and value styling used on the Overview tab so it reads as the same fact.
- Refs: https://design-system.service.gov.uk/components/summary-list/ · https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/readonly · https://adrianroselli.com/2022/11/brief-note-on-disabling-buttons.html · https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html

## 5. Disabling a modal's close and cancel during an uncancellable in-flight request

(The earlier file covers the UX choice. This covers the mechanics.)

- Disable every exit together, or none: the Cancel button, the header close (X) button, Esc, and a backdrop click. A dialog with a live Esc and a disabled X is inconsistent and lets the user dismiss a run that cannot be stopped.
- Native `<dialog>`: Esc fires `cancel` and then `close`. Call `event.preventDefault()` in the `cancel` listener while busy. Chrome limits repeated prevention of `cancel` without user activation in some versions, so also treat this as best effort. If the dialog is Alpine or HTMX driven, guard the handler (`@keydown.escape.window` and the backdrop click) with the same `busy` flag.
- Use `disabled` on the buttons for this case, with a caveat: disabled buttons leave the tab order, so keyboard focus can jump out of the dialog flow or be lost if the focused button is the one that becomes disabled. Before disabling the focused submit button, move focus to the dialog container (`tabindex="-1"`) or the status message so focus is not dropped to `<body>`. The alternative, `aria-disabled="true"` plus ignoring activation, keeps the button focusable and lets the reason be read as its description; it is a sound choice for Cancel and the X.
- Announce why: put the reason in visible text inside the dialog, for example "Running. This can't be stopped once started." with `role="status"` (a polite live region) that exists in the DOM before its text changes, or insert it with HTMX into an existing `aria-live="polite"` container. Link it to the disabled controls with `aria-describedby`.
- `aria-busy="true"` goes on the region whose content is updating, not on the dialog as a whole. It tells assistive tech to hold announcements until the update ends, which can suppress the very status message you want read. Use it on the results area, not on the container of the status text. Do not rely on it to disable anything; it does not block interaction.
- Do not set `inert` on the dialog itself, because it would make the status text unreachable. `aria-modal`/`showModal()` already make the background inert.
- Visual: keep the disabled style (reduced opacity, `cursor-not-allowed`) and show a spinner on the submit button with a text change ("Running…"), not a spinner alone.
- On completion: re-enable the controls, or replace the dialog content with the result and a single "Close" button, and move focus to it. On failure (HTTP 422 or 5xx in the project's HTMX convention), re-enable everything and show the error.
- Be sure the guard also covers `hx-on` and htmx's `hx-disabled-elt`, which can disable the submit button and the Cancel button in one attribute (`hx-disabled-elt="this, #cancel-id"`). That is the lowest-code route for "disable while the request runs" and clears itself on response.
- Refs: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ · https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/cancel_event · https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-busy · https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role · https://htmx.org/attributes/hx-disabled-elt/ · https://adrianroselli.com/2022/11/brief-note-on-disabling-buttons.html

## 6. Compact buttons with 44px hit areas via pseudo-elements in Tailwind

- Technique: `relative` on the button, and `after:absolute after:content-[''] after:-inset-y-[calc((44px-var(--h))/2)]`, or simply fixed offsets. Example for a 28px button: `relative h-7 after:absolute after:-inset-y-2 after:inset-x-0 after:content-['']` gives 44px height. For width, widen with `after:-inset-x-2` only if the button is narrower than 44px.
- Pitfalls:
  - Overlapping hit areas. Neighbouring compact buttons with -8px insets overlap if the gap is under 16px. The topmost in DOM order wins, so clicks land on the wrong action. Fix: keep gaps at least twice the extension, or extend only vertically (`-inset-y`) and rely on the gap for the horizontal axis. WCAG 2.5.8 allows a smaller target if a 24px circle centred on it does not hit another target.
  - `overflow-hidden` (or `overflow-auto`) parents clip the pseudo-element, so the extended area is cut off at the container edge, for example in a panel footer, a dialog footer or a table scroll wrapper. Fix: add padding to the container so the extension fits, or move the clip to an inner element.
  - Focus ring. The ring is drawn on the button, not the pseudo-element, so the ring is smaller than the hit area. That is correct: the ring should hug the visible button. Do not put the ring on the `::after`. Make sure `focus-visible:outline-offset` is not clipped by the same `overflow-hidden` parents.
  - Pointer-only. The pseudo-element extends the hit area for mouse and touch, not for screen readers, so no a11y-tree change is needed. Voice-control hit-testing uses the accessible name.
  - Stacking. `::after` over a sibling's content can swallow its clicks, and over text can block text selection. Do not set `z-index` on it, so it stays in the button's own stacking order.
  - Hover and active styles. The extended zone makes the hover/active state trigger when the pointer is outside the visible box. That is intended on touch, but looks odd on desktop. Scope it with `pointer-coarse:` (Tailwind variant `pointer-coarse`, available in Tailwind 4) or a `max-sm:` breakpoint so desktop keeps the plain button.
  - Button inside a `<label>` or a link wrapper: the pseudo-element belongs to the button only; do not extend a hit area that covers a different interactive element.
  - Do not use negative margin and padding instead: it shifts layout and is harder to reason about.
- Make it a reusable class or Cotton prop (for example a `compact` size on the button component) rather than repeating the utilities, in line with the project's "avoid repeating code" rule. Test with browser dev tools' element picker at 375px, or measure with `getBoundingClientRect()` on the pseudo-element is not possible, so check by clicking at the edges.
- Rule of thumb for sizes: visual height of 32px with a 6px extension each side gives 44px; 28px gives 8px each side. Keep adjacent visible buttons at least 8px apart so extensions never overlap, which means a 16px gap is the safe floor when both extend 8px.
- Refs: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html · https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html · https://tailwindcss.com/docs/hover-focus-and-other-states#pseudo-elements · https://tailwindcss.com/docs/hover-focus-and-other-states#pointer-and-hover-media-queries · https://adrianroselli.com/2019/06/target-size-and-2-5-5.html · https://m3.material.io/foundations/designing/structure#touch-targets

## Recommendations for the spec

1. Progress bar: `role="progressbar"` with min, max, now, and a label naming the course; the percentage text sits beside it; one `<ul>` per cell.
2. "+N more": a link to the Courses tab with a visually hidden suffix naming the learner; the visible text stays "+N more".
3. Courses tab: a simple table with a `caption`, `th scope`, one status badge per row, no per-item border.
4. Email: a label and value row outside the form, with a hint if needed; not a disabled input.
5. Bulk dialog: disable Cancel, X, Esc and backdrop together while running; prefer `aria-disabled` or `hx-disabled-elt`; show the reason in a `role="status"` region; return focus on completion.
6. Compact buttons: one shared class with a vertical `::after` extension, gaps of at least 16px, padding on clipping parents, and the ring on the button.

status: ok · reason: complete; URLs cited from prior knowledge, not re-fetched
