# Best practices: educator interface small UI polish

Note: written from established guidance. I did not fetch the URLs this session, so check them before relying on them.

## 1. Accordion panels collapsed by default
- Use native `<details>/<summary>` or a button with `aria-expanded` and `aria-controls`. Don't render the `open` attribute, or the `aria-expanded="true"` state, by default.
- The accordion button is the header. Keyboard: Enter/Space toggles. Up/Down/Home/End between headers are optional.
- Keep the collapsed default in the template or component, not in JS. That way there is no flash of expanded content.
- If the expanded state matters across HTMX swaps, keep it in the DOM and re-render only the inner fragments. Don't replace the `<details>` element itself, or it resets to collapsed.
- Ref: https://www.w3.org/WAI/ARIA/apg/patterns/accordion/

## 2. Splitting a detail page into tabs
- Ask whether the tabs need to be linkable. For a server-rendered Django+HTMX page, the best pattern is real links or URLs, such as `?tab=content`, with `hx-get` and `hx-push-url`, or plain links. The tab then survives reload, back and share.
- If the tabs are client-side only, follow the APG tabs pattern: `role=tablist`, `tab` and `tabpanel`, `aria-selected`, `aria-controls`, roving `tabindex`, and arrow keys to move between tabs.
- Only tab 1 content should be eagerly rendered. Load heavy tabs, such as course content, lazily with `hx-trigger="revealed"` or on tab click. This keeps the first load fast.
- Keep the page header, breadcrumbs and title outside the tabs.
- Refs: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/ · https://htmx.org/examples/tabs-hateoas/

## 3. Add/remove actions on related-record list panels
- Let the educator act on the thing a panel lists, and link each row to the thing's own page. Capture this in the skill, as the idea asks.
- Put the add action in the panel header, next to the title. Put a per-row remove action in the row.
- Removal is destructive:
  - Ask for confirmation, with `hx-confirm` or a modal. The prompt names the record and says what is removed. Registration removal should say that progress is kept or lost.
  - Use POST or DELETE with CSRF, never GET.
  - Check permissions and the organisation or site scope server-side.
- Adding: use a small form or modal that opens in place. Return HTTP 422 on validation errors, per the project convention.
- After add or remove, swap just the panel (`hx-target` on the panel, `hx-swap="outerHTML"`). Announce the result with an `aria-live="polite"` region or a message.
- Keep an empty state with the add action visible.
- Cohort registrations and direct registrations are different relationships. Label them clearly, and don't let a direct-removal action look like it removes cohort membership.
- Use an icon-only button only with an `aria-label` that names the row, for example "Remove registration for X".

## 4. Button text sitting low (vertical misalignment)
Likely causes, in order of likelihood:
1. **Webfont metrics**: the font's ascent and descent are asymmetric, so the glyphs sit low in the line box. Fix with `@font-face` overrides: `ascent-override`, `descent-override`, `line-gap-override` and `size-adjust`. Or use a font with corrected metrics. Or use `text-box-trim: trim-both; text-box-edge: cap alphabetic` (new, with partial browser support, so treat it as progressive enhancement).
2. **Fixed height plus padding mismatch**: for example `h-10` with `py-*` and a taller `leading-*`. Prefer `inline-flex items-center justify-center` with a fixed `min-height`. Avoid padding that is asymmetric.
3. **Border-width differences**: an outlined button (a 1-2px border) next to a filled one (no border) differs in height and offset. Give filled variants a transparent border of the same width.
4. **`<button>` vs `<a>` default line-height and baseline differences**: normalise with `line-height: 1.25`, `display: inline-flex` and `align-items: center`. Check that the Tailwind preflight is applied.
5. **Icons or inline children** with a baseline-aligned `inline-block`.
- Debug approach: in DevTools, compare the line box and content box; check the computed `font-family` actually loaded vs fallback; test with a system font. If the system font aligns, it is font metrics (cause 1).
- Test: add a visual regression or a Playwright check that compares the bounding box of the text with the button's bounding box centre, within a tolerance of 1px. That works for all variants (outlined, filled, anchor and button).
- Fix at the single source: the button component and theme. Don't patch individual buttons.
- Per the answers, fix in FLS whatever is in FLS. Record a downstream note if the cause is in the First Class repo's own theme or fonts.
- Refs: https://developer.mozilla.org/en-US/docs/Web/CSS/ascent-override · https://developer.chrome.com/blog/css-text-box-trim · https://developer.chrome.com/blog/font-fallbacks

## 5. Previous/next navigation in a preview modal
- Navigation order is the whole course in outline order, across parts. Compute prev/next on the server and render the targets as links or buttons with `hx-get`. Swap only the modal body and footer.
- Disabled states: on the first and last item, render the button with the `disabled` attribute (not just a style). A disabled `<button>` leaves the tab order. If you want it discoverable, use `aria-disabled="true"` and ignore the click, so focus is not lost mid-navigation. Also give it a visual disabled style that isn't colour-only.
- Focus management:
  - On open, focus goes into the dialog (the header or first control). On close, it returns to the trigger.
  - On navigating prev/next, keep focus on the button just pressed. If that button becomes disabled (end reached), move focus to the other nav button or the dialog title. Don't let focus drop to `<body>`.
  - Use `<dialog>` with `showModal()` for built-in focus trap, Esc, inert background and `::backdrop`. Add `aria-labelledby` pointing at the title, which updates with the content.
- After content swaps, update the title and announce the change. Use an `aria-live="polite"` region, or move focus to the heading with `tabindex="-1"`.
- Keyboard: Esc closes (native). Optionally ArrowLeft/ArrowRight for prev/next, only when focus is not in an input, and document it. Never override the browser's alt-arrow history shortcuts.
- Closing: the header X, Esc and backdrop click remain. Only the footer Close button goes (per the answers). The X needs `aria-label="Close"`.
- Label the buttons with text ("Previous", "Next") and optionally the target's title. Icons alone need `aria-label`. Place Previous on the left and Next on the right. In RTL, mirror them.
- Content should show position, for example "3 of 24", so the educator knows where they are.
- Refs: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ · https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog · https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-disabled

## 6. Quiz top-level preview: stats and settings
- Present settings (pass mark, attempts, time limit, shuffle) as a definition list (`<dl>`). Present stats (attempt count, average score, pass rate) as a small summary block.
- Compute stats with aggregate queries, with `select_related`/`prefetch_related`, and avoid N+1 queries. Show an explicit empty state when there are no attempts yet, not zero or NaN.
- Scope stats to the organisation or site.

## Testing suggestions
- Playwright: tab switching and URL persistence; collapsed state on load; add/remove flow with confirm; modal prev/next at first, middle and last items; focus after each navigation; Esc closes.
- Unit tests for the prev/next computation across parts, including courses with a single item and an empty part.

status: ok
