# Research: best practices for a data-table bulk-action bar

Scope: Django + HTMX + Alpine.js + Tailwind educator UI. The design (`design.md`) is context only. The bar replaces the filter bar when rows are selected. Sources are cited inline. Recommendations are from my own knowledge of the cited specs and were not re-fetched this session, so check details against the links before relying on them.

## 1. Accessibility

### 1.1 Selection bar: toolbar role and live region
- **Announce the count with a polite live region, not by moving focus.** Put a visually-hidden, always-present `role="status"` element (implicit `aria-live="polite"`, `aria-atomic="true"`) in the DOM on page load. Update its text ("3 learners selected", "Selection cleared"). A live region inserted into the DOM together with its content is often not announced, so the container must exist before the text changes. Do not put `aria-live` on the whole bar, because buttons would be re-read. Refs: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role and https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html (WCAG 4.1.3 Status Messages).
- **Debounce announcements.** Select-all or shift-click range selection should produce one announcement, not one per row. Update the live text once per interaction.
- **`role="toolbar"` is optional here.** The APG toolbar pattern requires a roving tabindex with arrow-key navigation, a single tab stop and `aria-label`. https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/ says to use it for groups of 3 or more controls. If used, the implementer must build the arrow-key behaviour. A half-built toolbar (role present, no arrow keys) is worse than none. A simpler and acceptable choice is a `<div role="group" aria-label="Bulk actions">` or a `<section aria-label="Bulk actions">`, with every button in the normal tab order. Recommendation: use group plus normal tab order unless the spec wants a roving tabindex.
- **Focus when the bar appears.** Do not steal focus. The user is on a checkbox, so keep focus there. When Clear or de-select all is activated, the bar is removed, so move focus to a stable target (the header checkbox, or the table or filter search input). Otherwise focus is lost to `<body>`.
- **The bar must not shift the layout in a disorienting way.** The design swaps the bar in place of the filter bar, which keeps the table position stable. Keep the same height so rows do not jump under the pointer.

### 1.2 Row checkboxes and the tri-state header checkbox
- Use native `<input type="checkbox">`. Set `indeterminate` through JS (`el.indeterminate = true`); there is no HTML attribute. Browsers expose it as `mixed` to assistive technology. Avoid `role="checkbox"` divs unless needed (APG: https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/, which covers the mixed state and a "select all" parent).
- Header checkbox states: unchecked means none selected, checked means all rows on the page selected, indeterminate means some selected. Clicking when indeterminate should select all (convention in Gmail and GitHub), then deselect all on the next click.
- Give each checkbox an accessible name: `aria-label="Select {learner name}"` (or `aria-labelledby` pointing at the name cell), and `aria-label="Select all learners on this page"` on the header. Make clear in the label that it is the current page. Do not rely on a bare column header.
- Hit target: WCAG 2.2 target size minimum is 24x24 CSS px (2.5.8, https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html). Make the whole cell, or a padded label, clickable.
- Selected rows need a non-colour cue too (the checked checkbox itself serves). Highlight is supplementary only (WCAG 1.4.1).
- Do not use `aria-selected` on `<tr>` in a plain `<table>`. It is valid only in grid/treegrid contexts. Using checkboxes inside a normal table is the right approach. Reference: https://adrianroselli.com/2020/01/fixed-table-headers.html and https://adrianroselli.com/2017/11/a-responsive-accessible-table.html for table semantics. Keep native `<table>` semantics; do not apply `role="grid"`.
- Keyboard: Space toggles a focused checkbox (native). Shift+click range selection is a mouse/keyboard enhancement. It is optional, and if built, it should also work with Shift+Space.

### 1.3 "More" dropdown: menu button pattern
APG Menu Button: https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/ and https://www.w3.org/WAI/ARIA/apg/patterns/menubar/ (menu keyboard model).
- Trigger is a `<button aria-haspopup="menu" aria-expanded="false|true" aria-controls="menu-id">More</button>`. Menu container is `role="menu"` with `role="menuitem"` children.
- Keys: Enter/Space/Down Arrow opens and focuses the first item; Up Arrow opens and focuses the last (optional). Inside the menu, Up/Down move (wrap), Home/End jump, Escape closes and returns focus to the trigger, Tab closes the menu. Typing a character jumps to a matching item (optional).
- Close on outside click. Do not use `role="menu"` for ordinary site navigation, only for application-style action menus like this one. Heydon Pickering / Adrian Roselli warn that menu roles are often misapplied: https://adrianroselli.com/2017/10/dont-use-aria-menu-roles-for-site-nav.html. A bulk-action list is a valid use.
- Alpine.js: `x-data="{open:false}"`, `@keydown.escape.window` or on the menu, `@click.outside="open=false"`, `x-ref` plus `$nextTick` for focus. Alpine's `@alpinejs/focus` plugin supplies `x-trap`, and `@alpinejs/focus` docs are at https://alpinejs.dev/plugins/focus. Alpine UI (Headless UI style) menus implement the APG pattern but are a paid product, so you would hand-roll with the above.
- Menu items that open a modal: on close of the modal, return focus to the "More" trigger (see 1.4), not to the removed menu item.
- Destructive items in the menu: style distinctly (colour plus text, never colour only) and place them last.
- Disabled items: prefer `aria-disabled="true"` so they remain discoverable, and explain why (e.g. "Not available for your selection"). Items that need a certain selection should be hidden or disabled with a reason. Do not leave them silently inert.
- Overflow: only the first N actions render as buttons and the rest go into More. On narrow widths, the bar should wrap or move more actions into More. Do not horizontally scroll the bar. The ordering of actions must be the same between the visible buttons and the menu.

### 1.4 Modal dialog (confirmation and forms)
APG Dialog (Modal): https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/.
- Prefer the native `<dialog>` element with `showModal()`. It gives the top layer, inert background, Escape-to-close and focus return to the invoker on `close()` in modern browsers (MDN: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog; Scott O'Hara notes at https://www.scottohara.me/blog/2023/01/26/use-the-dialog-element.html). Otherwise `role="dialog" aria-modal="true"`, a focus trap (Alpine `x-trap.inert.noscroll`) and Escape handling.
- Name: `aria-labelledby` pointing at the heading, and `aria-describedby` pointing at the confirmation body text. For a destructive confirmation, WAI-ARIA says to consider `role="alertdialog"` (https://www.w3.org/WAI/ARIA/apg/patterns/alertdialog/), which makes screen readers read the message on open. Use it for pure confirmations only, not for forms.
- Initial focus: for destructive confirmations focus the least destructive control (Cancel) or the heading. For forms focus the first field. For a short, safe confirmation, focusing the primary button is acceptable. APG says to place initial focus on the least destructive action if the action is irreversible.
- Return focus to the control that opened the modal. If that control is gone (menu closed, bar removed after success), fall back to a stable target such as the table heading or the status region.
- Tab and Shift+Tab cycle inside the dialog. Escape closes (cancels). Do not close on backdrop click for dialogs holding form input, since data is lost.
- Lock body scroll while open. Add a visible close or Cancel button (WCAG 2.5.8 and discoverability).
- HTMX-loaded modal content: load the form into the dialog target through `hx-get` plus `hx-target`, call `showModal()` after the swap (HTMX `htmx:afterSwap` / `htmx:afterSettle`, or Alpine `x-init`), and use 422 for validation errors, re-rendering the form inside the dialog (project convention). After a validation swap, move focus to the error summary or the first invalid field and link errors with `aria-describedby` and `aria-invalid`. See https://htmx.org/docs/#modals and https://htmx.org/events/.
- Disable the submit button during the request (`hx-disabled-elt="this"`) to prevent a double submit, and show a busy state with text, not just a spinner.

### 1.5 Keyboard summary
Tab through the checkboxes, bar buttons and More trigger in DOM order. The bar should sit directly before the table in DOM order, so it is reachable without tabbing through all rows. Consider a "Skip to bulk actions" only if the table is long, which is probably not needed. Escape closes the menu, then the modal. Pressing Escape on the page itself to clear the selection is optional and not standard, so do not add it unless requested.

## 2. Select-all: current page versus all results
References: Gmail pattern ("All 50 conversations on this page are selected. Select all 1,234 conversations"), Cloudscape table selection guidance https://cloudscape.design/components/table/ , GOV.UK/Primer discussion https://primer.style/product/components/data-table/ , Material Design data tables https://m2.material.io/components/data-tables#data-tables-selection, Nielsen Norman Group on bulk actions https://www.nngroup.com/articles/proximity-consequence/.
- The header checkbox selects only the rows on the current page. Make this explicit in its label.
- If more results exist beyond the page, show an explicit escalation inside the bar or a banner: "All 25 on this page are selected. Select all 312 learners". Never silently extend to all pages. Show the new count and a way back ("Select only this page", or Clear).
- This spec's bar has "select all" and "de-select all" links beside the count. Decide the semantics explicitly in the spec. The safe default, if there is pagination, is: "Select all" = all rows matching the current filter (stated with the count) or this page, but the label and the count must say which. The destructive confirmation must display the exact count that will be affected.
- For "all matching" selection, the server should receive the filter query and apply it. Do not post thousands of IDs. Posting IDs is fine for page-scoped selection. Re-evaluate the filter server-side at execution time and report how many were actually affected, because the data can change between selecting and acting.
- Selection and changing filters, search or sort: clear the selection when the filter or search changes (or ask the user), because hidden selected rows are a classic data-loss trap. If the selection persists across pages, show the total selected count (including off-page) in the bar, never only the visible count.
- Authorisation and site-awareness: always re-check on the server that every submitted ID belongs to the current site and the user's permission scope (use the site-aware manager). Ignore or reject IDs outside it.

## 3. Destructive action confirmation
References: NN/g https://www.nngroup.com/articles/confirmation-dialog/ , Material https://m3.material.io/components/dialogs/guidelines, GOV.UK/Polaris guidance https://polaris.shopify.com/patterns/confirmation-modal , Apple HIG https://developer.apple.com/design/human-interface-guidelines/alerts.
- Confirm only when it matters. Prefer confirm for irreversible or high-blast-radius actions, and offer undo for reversible ones (toast with Undo is better than a modal for reversible actions). Over-confirmation trains users to click through.
- State the count and the object in the title or body: "Remove 3 learners from this cohort?" with the names listed (first 3 to 5, then "and 12 more"). Avoid "Are you sure?".
- Say the consequence in plain words ("They will lose access to X. Their progress is kept."), including whether it can be undone.
- Button labels are specific verbs that repeat the action and count: "Remove 3 learners" and "Cancel". Avoid "OK", "Yes" and "Submit". The destructive button should use the project's danger style; the Cancel button is neutral. Do not rely on colour alone.
- Do not make destructive the default (focused) button; see 1.4.
- For very high-risk actions only (delete many records), consider type-to-confirm. Likely overkill here, so do not build unless requested.
- Results: after completion show the outcome as a status message ("Removed 3 learners"; partial failure: "Removed 2 of 3. 1 could not be removed: reason"). Per the design (02d), clear the selection and restore the filter bar. Announce the result via the live region. Do not leave the selection of already-processed rows.
- Forms in modals (e.g. send a message): the primary button verb is the action ("Send message"), the form includes the recipient count ("To: 3 learners").

## 4. Progressive enhancement with HTMX
References: https://htmx.org/docs/#progressive_enhancement , https://htmx.org/essays/hypermedia-friendly-scripting/ , https://htmx.org/essays/hypermedia-on-whatever-youd-like/ , https://htmx.org/docs/#boosting , https://alpinejs.dev/directives/x-data.
- Baseline: the table is a `<form method="post">` with checkboxes `name="selected" value="{pk}"` and bulk actions as `<button type="submit" name="action" value="remove" formaction="...">`. Without JS, the user can tick and submit, with the server rendering a confirmation page and then the result. HTMX then upgrades via `hx-post` / `hx-boost` on the same form and Alpine only handles the bar visibility and counts. This gives a working fallback and one server code path (the view returns a full page or a partial depending on `request.htmx`, via django-htmx).
- Alpine state is for presentation only (count, bar visibility, menu open). The server remains the authority on what is selected when acting. The count text should be derived from the DOM (the number of checked boxes), not an independently maintained counter that can drift.
- The bar element must be rendered hidden by default with no layout flash. Use `x-cloak` plus a `[x-cloak]{display:none}` rule, or render server-side for the no-JS case.
- Use `hx-include` or a single enclosing form so the checked values travel with the request. For per-action modals: button `hx-get="/learners/bulk/remove/confirm"` with `hx-include="[name=selected]:checked"` (or the form) and `hx-target="#modal"`. The confirm partial then holds hidden inputs for the IDs, so the final POST is self-contained and the count shown matches what is sent.
- CSRF: global `hx-headers` on body (project convention). A plain `<form>` fallback needs `{% csrf_token %}`.
- Respond with 422 for validation errors (project convention; htmx does not swap 4xx by default, so configure `htmx.config.responseHandling` to swap 422, https://htmx.org/docs/#requests / `htmx:beforeSwap`). Use `HX-Trigger` response headers to fire events (`bulkActionDone`) that the page listens to, rather than coupling the response to client scripts (https://htmx.org/headers/hx-trigger/).
- Post-success refresh: either return the refreshed table partial (`hx-target` on the table body, `hx-swap="outerHTML"`) with an out-of-band swap (`hx-swap-oob`) restoring the filter bar and clearing the bar, or `HX-Refresh`/redirect. OOB swaps keep it one round trip.
- Use `hx-push-url` only on filter/sort/page navigations, not on bulk actions.

## 5. Preserving selection across HTMX swaps
- A swap of the table body replaces the checkbox elements, so their checked state is lost. Options:
  1. **Do not swap the checkbox region** when the selection must survive (swap only the specific cells or rows that changed).
  2. **Server re-renders checked state.** Include the selected IDs in the request (`hx-include`) on sort, filter and page requests. The server marks `checked` on those rows in the response. This is robust, works without Alpine, and is what I recommend.
  3. **Client store.** Keep a `Set` of selected IDs in an Alpine store (`Alpine.store('selection', ...)` or `x-data` outside the swapped region); after `htmx:afterSettle`, re-check boxes whose value is in the set and recompute the header checkbox state. Needed for cross-page selection with no server round trip. HTMX itself also preserves focus on elements with a stable `id` across swaps (https://htmx.org/docs/#focus), so give rows/checkboxes stable ids such as `select-{pk}`.
- Keep the Alpine component root outside the swap target (e.g. wrapping the bar and the table container). If Alpine components sit inside swapped content, they re-initialise (HTMX swaps trigger Alpine's MutationObserver, which initialises new nodes), losing state.
- After a swap, recompute the header checkbox state (checked, indeterminate, unchecked) and the bar visibility from the DOM. Also handle the bfcache and the browser Back button: browsers may restore checkbox state on Back, causing the bar and checkboxes to disagree. Compute the bar state from the DOM on `pageshow` and on `htmx:historyRestore`.
- When the selection is deliberately dropped (filter changed, action complete), clear it in one place and announce "Selection cleared".
- Polling or `hx-trigger="every"` refreshes on the table would wipe selection. Avoid them, or apply option 2.

## 6. Text-only buttons: affordance and contrast
References: WCAG 1.4.3 Contrast (Minimum) https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html, 1.4.11 Non-text Contrast https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html, 1.4.1 Use of Color, 2.4.7/2.4.11 Focus Visible/Not Obscured https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html , NN/g "Beyond Blue Links" https://www.nngroup.com/articles/clickable-elements/ and "Ghost buttons" https://www.nngroup.com/articles/flat-ui-less-attention-cause-uncertainty/ , Material text buttons https://m3.material.io/components/buttons/guidelines.
- Text (outline-free) buttons have weaker signifiers. Text must meet 4.5:1 against the bar background (3:1 for large text of 18.66px bold or 24px). The border-less button has no 3:1 requirement of its own, since the text label is the identifying element. Do not use light-grey "muted" text for actions.
- Compensate with: consistent placement and a distinct text colour (primary or link colour) versus the plain count text, an icon only when it clarifies and with an adjacent text label, `cursor-pointer`, a hover background tint (`hover:bg-...`) and a visible focus ring (`focus-visible:ring-2 ring-offset-1`) with 3:1 contrast against the adjacent colours. Focus ring must not be clipped by `overflow-hidden` on the bar.
- Padding sets a comfortable hit area (≥ 24x24 CSS px minimum, ~32 to 44 px high is better) even though the visual is just text.
- Distinguish the count and "select all/de-select all" (link-like text actions) from the actions: put the count as plain bold text, selection links with an underline or link style, and the Clear button on the right (as the design does, which separates the destructive-neutral reset from the actions). Destructive text buttons use the danger text colour but are also worded as a verb, so meaning is not conveyed by colour only.
- Disabled text buttons are particularly hard to distinguish; avoid disabling and instead hide or explain (see 1.3). Disabled controls are exempt from contrast rules, but users still need to know why.
- Dark mode and theme: use the project theme tokens, and check contrast on both the selected-state background of the bar and the row highlight.
- Use `<button type="button">` (never `<a>`) for actions that do something. `type="submit"` only inside the progressive-enhancement form.
- Test with forced colours (Windows High Contrast): transparent borders become visible with `border border-transparent`, so use that and avoid relying on background colour for the focus indicator.

## 7. Implementer checklist
1. Hidden `role="status"` region exists at load; update once per selection change; announce "Selection cleared" and the action result.
2. Native checkboxes with per-row labels; header checkbox tri-state labelled "Select all on this page"; indeterminate set through JS.
3. Bar is a labelled group; do not steal focus on show; on Clear or action completion, move focus to a stable element.
4. "More" implements the APG menu button (aria-haspopup, aria-expanded, arrows/Home/End/Escape/Tab, focus return).
5. Modal is `<dialog>` (or role=dialog plus a trap); labelled and described; safe initial focus; Escape closes; focus returns to the opener or a fallback; 422 re-renders the form in place.
6. Confirmation names the count and the object, lists a sample of names, states the consequence and reversibility, with verb buttons ("Remove 3 learners"/"Cancel").
7. Select-all semantics (page vs all matching) are stated in the label, the count and the confirm; server re-derives the target set and re-checks site and permission scope.
8. Works as a plain POST form without JS; HTMX and Alpine are layered on top.
9. Selection state survives sort/filter/page swaps by round-tripping IDs through `hx-include` (or an Alpine store outside the swap target), recomputed on `htmx:afterSettle`, `pageshow` and `htmx:historyRestore`.
10. Text buttons have 4.5:1 text, a visible focus ring, hover tint and an adequate hit area.

## Source list
- https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/
- https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- https://www.w3.org/WAI/ARIA/apg/patterns/alertdialog/
- https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/
- https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog
- https://www.scottohara.me/blog/2023/01/26/use-the-dialog-element.html
- https://adrianroselli.com/2017/10/dont-use-aria-menu-roles-for-site-nav.html
- https://alpinejs.dev/plugins/focus
- https://htmx.org/docs/ , https://htmx.org/events/ , https://htmx.org/headers/hx-trigger/
- https://htmx.org/essays/hypermedia-friendly-scripting/
- https://www.nngroup.com/articles/confirmation-dialog/
- https://m3.material.io/components/dialogs/guidelines , https://m3.material.io/components/buttons/guidelines
- https://cloudscape.design/components/table/
- https://polaris.shopify.com/patterns/confirmation-modal
- https://developer.apple.com/design/human-interface-guidelines/alerts

status: ok · reason: written from established specs and guidance; URLs cited were not re-fetched this session
