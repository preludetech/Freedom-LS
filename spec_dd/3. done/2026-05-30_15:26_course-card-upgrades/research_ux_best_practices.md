# UX best practices & pitfalls: dashboard course cards

## Recommendations for FLS

- **Use the "linked title + redundant click area" pattern, not a wrapping `<a>`.** Anchor the semantic link on the card heading; extend the hit area visually with a `::before` pseudo-element on the card. This preserves text selection, gives screen readers a meaningful link name (the course title), and avoids the "long string of card text read before 'link'" trap (Inclusive Components, NN/g).
- **Drive state from text + shape, never colour alone.** The eyebrow ("In progress" / "Not started" / "Complete") and a non-colour cue (icon, checkmark, dimmed thumbnail) must both be present (WCAG 1.4.1).
- **Open the not-started preview as a modal only on desktop; on narrow viewports route to a dedicated page.** Modals on mobile routinely lose to OS chrome and back-gesture; dedicated pages are deep-linkable and survive refresh. If you keep a modal on desktop, use the native `<dialog>` element with `showModal()` so focus trap, Esc handling, and `aria-modal` are free.
- **Make the progress bar a real `role="progressbar"` with `aria-valuenow`/`min`/`max` and an associated label** ("Course progress, 42%"). Show the numeric percent next to the bar for in-progress cards; hide both at 0% (replace with "Not started"); replace with a "Completed" pill at 100%.
- **Cap the in-progress dashboard at 5–6 cards above the fold** and surface a single "Continue where you left off" affordance — the most-cited concrete improvement in LMS dashboard write-ups.
- **One primary action per card.** Secondary actions (e.g. "Unenrol", "View certificate") sit outside the linked title's hit area with their own focus ring, layered above the `::before` overlay (`z-index` + `position: relative`).
- **Provide a deterministic icon fallback.** When `course.icon` is missing, render a generated monogram tile from the course title rather than a generic placeholder — Material guidance is to skip illustrations entirely below medium-card size.
- **Make the focus ring wrap the whole card, not just the title.** Use `:focus-within` so keyboard users see the same hit target sighted mouse users get.

## Whole-card clickability

Block-wrapping the entire card in `<a>` is the most common mistake. It (a) makes the screen reader read the entire card body before announcing "link", (b) breaks text selection because the link sits as a mask over content, and (c) creates invalid markup the moment a second interactive element appears inside. Inclusive Components and Kitty Giraudel both recommend a single semantic link on the title plus a stretched pseudo-element to widen the hit zone; Heydon Pickering notes a ~200ms mousedown-to-mouseup threshold lets you keep text-selection working while still treating quick clicks as navigation. Underline (or otherwise visually mark) the title — NN/g is explicit that "card-shaped thing" is not a sufficient affordance on its own. Add `:focus-within { outline: ... }` so keyboard focus is visible on the card, not buried on the title.

## Modal vs page for course preview

Modals are appropriate for short, focused, context-preserving tasks. The course preview (description + ToC + enrol/start CTA) sits right on the boundary. Pros of modal: keeps dashboard scroll position, feels lightweight, faster perceived load. Cons: not deep-linkable (you can't share or bookmark a course), browser Back is inconsistent (some users expect Back to close, others to leave the dashboard), and on mobile the ToC commonly grows taller than the viewport and the modal becomes a worse version of a page. Recommended pattern: route to a real URL either way; on desktop intercept the click and open as a `<dialog>` while pushing history state, so Back closes the modal; on mobile, just navigate. Use the native `<dialog>` for free focus trap, Esc to dismiss, and `inert` on the background. Always return focus to the originating card on close.

## Progress bars

Use the native `<progress>` element or `role="progressbar"` with `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuenow`, and a name via `aria-labelledby` pointing at the course title plus the word "progress". Show numeric percent adjacent to the bar — NN/g and Carbon both find numbers reduce uncertainty and lift completion motivation. At 0%, hide the bar entirely; a 0-filled bar reads as "broken" or "stuck". At 100%, swap the bar for a "Completed" badge and a checkmark — Carbon explicitly warns against leaving a full bar visible after completion. Maintain 3:1 contrast between filled/unfilled track and 4.5:1 for adjacent text. Don't animate fill on every dashboard render; it draws the eye away from the primary action.

## State communication

Three signals, layered: (1) eyebrow text ("In progress"), (2) shape/icon (play, lock-open, check), (3) colour. Avoid duplicate labelling — if the eyebrow says "Completed", the progress area must not also say "100%"; pick one. Don't use only a coloured dot or only a coloured border to signal state (WCAG 1.4.1, SC 4.1.3). Status badges should either have an accessible name via `aria-label` or be `aria-hidden="true"` with the same information conveyed in nearby text.

## Fallback states

- **No icon:** deterministic monogram (first 1–2 letters of the title) on a themed background derived from a hash of the slug — avoids the "ghost course" feeling of a generic placeholder.
- **No description:** skip the description region entirely; do not render "No description available".
- **No progress (not started):** replace bar+percent with the eyebrow "Not started" and a "Start" CTA; don't render a 0% bar.
- **Empty dashboard (no enrolments):** real empty state with one clear next action ("Browse courses") — not a grid of placeholders.

## Learner complaints worth designing against

- "I can't tell what I was last working on" — solved by a prominent single "Continue" entry point above the card grid.
- "Cluttered screens overwhelm the average learner" (eLearning Industry) — drives the 5–6 card cap and one-CTA-per-card rule.
- "The whole card looked clickable but the button inside did something different" — argues for one primary action and visibly carved-out secondary controls.
- "Progress doesn't match what I actually did" — argues for showing the numeric percent and a last-activity timestamp, not just a bar.
- "~88% of users won't return to a platform with poor design" (cited across LMS UX articles) — small polish on the dashboard pays off disproportionately.

## References

- [NN/g — Cards: UI-Component Definition](https://www.nngroup.com/articles/cards-component/)
- [NN/g — Beyond Blue Links: Making Clickable Elements Recognizable](https://www.nngroup.com/articles/clickable-elements/)
- [NN/g — Progress Indicators Make a Slow System Less Insufferable](https://www.nngroup.com/articles/progress-indicators/)
- [Inclusive Components — Cards (Heydon Pickering)](https://inclusive-components.design/cards/)
- [Kitty Giraudel — Accessible Cards](https://kittygiraudel.com/2022/04/02/accessible-cards/)
- [Nomensa — How to build accessible cards / block links](https://www.nomensa.com/blog/how-build-accessible-cards-block-links/)
- [UC Berkeley DAP — Accessible card UI component patterns](https://dap.berkeley.edu/web-a11y-basics/accessible-card-ui-component-patterns)
- [USWDS — Card accessibility tests](https://designsystem.digital.gov/components/card/accessibility-tests/)
- [W3C WAI-ARIA APG — Dialog (Modal) Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [MDN — ARIA progressbar role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/progressbar_role)
- [Carbon Design System — Progress bar](https://carbondesignsystem.com/components/progress-bar/usage/)
- [Smashing Magazine — Designing A Better Back Button UX](https://www.smashingmagazine.com/2022/08/back-button-ux-design/)
- [LogRocket — Modal UX design patterns](https://blog.logrocket.com/ux-design/modal-ux-design-patterns-examples-best-practices/)
- [TPGi — The current state of modal dialog accessibility](https://www.tpgi.com/the-current-state-of-modal-dialog-accessibility/)
- [Material Design — Empty states](https://m2.material.io/design/communication/empty-states.html)
- [PatternFly — Empty state design guidelines](https://www.patternfly.org/components/empty-state/design-guidelines/)
- [WebAIM — Contrast and Color Accessibility](https://webaim.org/articles/contrast/)
- [eLearning Industry — 7 LMS Navigability Issues](https://elearningindustry.com/learning-management-system-lms-navigability-issues-negatively-impact-user-experience)
- [eLearning Industry — 8 Tips To Improve LMS UX](https://elearningindustry.com/tips-improve-learning-management-system-lms-user-experience-online-learners)
