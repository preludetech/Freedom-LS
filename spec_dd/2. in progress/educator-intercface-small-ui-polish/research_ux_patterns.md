# Research: UX patterns (educator-intercface-small-ui-polish)

Sources are well-known pattern guidance, written from knowledge and not fetched in this run. Treat details as guidance.

## 1. Tabbed detail pages: what goes in the first tab
- The first tab is the default landing view. It holds the overview: identity and settings ("details"), plus the records the educator acts on most. Bulk or reference content, such as a long outline, goes in a secondary tab.
- Tabs split content into peer sections. Keep labels short and nouns ("Overview", "Content"). Use few tabs; two or three is fine.
- Keep tab state in the URL (`?tab=content`) so refresh, back and shared links work.
- Tab markup follows the WAI-ARIA tabs pattern: `role=tablist`, `tab` and `tabpanel`, with arrow-key navigation between tabs.
- For this spec: tab 1 is details, cohort registrations and direct registrations. Tab 2 is content.
- References:
  - https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
  - https://www.nngroup.com/articles/tabs-used-right/
  - https://m3.material.io/components/tabs/guidelines

## 2. Collapsed accordions and outlines
- A long hierarchy should start collapsed so the educator sees the structure first and opens only what they need.
- Each header shows a chevron, the title and a count ("Part 2 · 5 items"), so collapsed parts still carry information.
- Use `<details>/<summary>` or a button with `aria-expanded` and `aria-controls`.
- An "Expand all / Collapse all" control is useful for long outlines. It is optional, and the spec must not build it unless asked.
- Preserve expansion state only if cheap. Otherwise default to collapsed.
- References:
  - https://www.w3.org/WAI/ARIA/apg/patterns/accordion/
  - https://www.nngroup.com/articles/accordion-icons/

## 3. Managing related records from a parent page
- Act where you see it. A panel that lists records should offer add and remove, and each row should link to the record's own page. This matches the rule the idea wants captured in skills.
- **Add:**
  - A primary "Add ..." button in the panel header opens a picker dialog.
  - The picker offers a searchable list of candidates, excluding ones already linked.
  - It has an explicit confirm button, labelled with the verb ("Add cohort", not "OK").
  - After success, the panel refreshes in place. With HTMX that means swapping the panel and returning 422 with the form re-rendered on validation errors.
- **Remove:**
  - Each row has a "Remove" action, shown as a text or icon-plus-label button. An icon alone needs an `aria-label`.
  - Confirm in a dialog that names the record and the consequence: "Remove cohort X from this course? Learners keep their progress", or whatever is true here.
  - Use a destructive style, and say "Remove" (unlink) rather than "Delete" when the record itself survives.
  - Confirmation is more important when the action changes access or has side effects, as registrations do.
- **Row links:** the primary text (name) is a link to the record's detail page. Actions sit in a separate right-aligned cell, and do not nest inside the link.
- **Empty state:** short text plus the Add button.
- **Permissions:** hide or disable controls the educator may not use.
- References:
  - https://www.nngroup.com/articles/confirmation-dialog/
  - https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
  - https://design-system.service.gov.uk/components/button/ (destructive/warning button guidance)
  - https://htmx.org/examples/modal-bootstrap/ (modal with HTMX)

## 4. Previous/Next in a modal content previewer
- **Placement:** put the nav buttons in the modal footer, with Previous on the left and Next on the right. This matches the idea and answers.md, which removes the footer Close button. Close stays available through the header X, Esc and backdrop click, and all three must work.
- **Labels:** "Previous" and "Next" with chevrons. Adding the neighbouring item's title as secondary text ("Next: Fractions intro") helps orientation. Truncate long titles with ellipsis and keep the full title in `title`/`aria-label`. This is optional polish.
- **Position indicator:** "3 of 12" between the buttons or in the header, in outline order across parts as the answers specify. Announce changes with `aria-live="polite"`.
- **Ends:**
  - Disable Previous on the first item and Next on the last, using the `disabled` attribute so the buttons are skipped by keyboard.
  - Do not wrap around, because the answers specify disabling.
  - Keep the buttons visible so the layout does not jump.
- **Keyboard:** Left arrow goes to previous and Right arrow to next. Ignore the keys when focus is in an input, textarea or select, and when modifier keys are held. Esc closes. Keep focus trapped in the modal, and after a swap keep focus on the button or the content heading.
- **Loading:** swap only the modal body and footer through HTMX, with the footer re-rendered for the new position. Prefetching is unnecessary.
- **Quiz top-level preview:** show stats (question count, total marks, perhaps attempts and average score) and settings (pass mark, time limit, attempts allowed) as a compact definition list or stat tiles above or beside the preview.
- References:
  - https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
  - https://www.w3.org/WAI/ARIA/apg/patterns/carousel/ (prev/next and live region conventions)
  - https://www.nngroup.com/articles/modal-nonmodal-dialog/

## 5. Button label alignment
- Typical causes of off-centre text in buttons:
  - Mixed `line-height` and padding. Tailwind `leading-*` on the label versus on the button, or a theme that sets a fixed `height` plus vertical padding.
  - `<button>` versus `<a>` rendering differences. Anchors are inline and need `inline-flex`.
  - Icon plus text without flex alignment. Fix with `inline-flex items-center justify-center gap-*`.
  - Global CSS resets or theme overrides setting `line-height`, `padding`, `vertical-align` or `text-align`.
  - Web-font metrics shifting the baseline.
  - Cotton button components wrapping the slot in an extra inline element.
- Preferred fix: one shared button component or class using `inline-flex items-center justify-center`, a consistent `min-h`, symmetric padding and `leading-none` or a consistent leading. Remove one-off overrides.
- Diagnose with devtools on the computed box (padding, line-height, display) of a misaligned button against an aligned one. Check whether the rule comes from the FLS theme or from the concrete project. FLS-side causes get fixed here, and a First Class cause becomes a downstream note, per answers.md.
- References:
  - https://tailwindcss.com/docs/display
  - https://tailwindcss.com/docs/align-items
  - https://tailwindcss.com/docs/line-height

status: ok
