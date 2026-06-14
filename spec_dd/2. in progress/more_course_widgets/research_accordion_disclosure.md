# Research: Accordion / Collapsible Disclosure Widget

## Summary

For the FLS accordion/disclosure widget, the recommended approach is a hybrid: use native `<details>`/`<summary>` as the structural foundation (free keyboard support, no-JS fallback, search-engine visible) and layer Alpine.js `x-collapse` on top for smooth height animation with a CSS-only fallback for the growing number of browsers that support `::details-content` + `transition-behavior: allow-discrete`. The "key takeaways" block should be a named admonition variant (no collapse); the "checklist" block should also be an admonition variant (no collapse) unless the authored markdown checklist specifically needs hide/reveal behaviour.

---

## 1. Native `<details>`/`<summary>` vs Custom Alpine.js Accordion

### Native `<details>`/`<summary>` advantages

- Zero JavaScript needed: fully keyboard-operable (Enter/Space on the `<summary>`) and accessible to assistive technology in all modern browsers.
- Works without JS (progressive enhancement), printable and searchable (browser Ctrl+F finds text inside open or closed `<details>` in most modern browsers, because the content is in the DOM).
- The `name` attribute (now Baseline across Chrome, Firefox 130+, Safari 17+) enables a native exclusive-open group: only one panel in the named group stays open at a time.
- CSS animation is now viable: `::details-content` (Baseline September 2025) + `transition-behavior: allow-discrete` (Baseline August 2024) allow clean CSS-only animated expand/collapse. The newer `interpolate-size: allow-keywords` approach is still Chromium-only (Chrome 129+, Sep 2024) and should be treated as a progressive enhancement.
- Prior NVDA state-announcement issues (reported ~2019) appear to have been resolved in modern NVDA + browser combinations, though this should still be verified.

### When custom Alpine.js is the better choice

- Single-open-at-a-time groups where the `name` attribute is not yet universally established in older browser targets.
- Fine-grained animation control (custom easing, duration, partial-reveal via `x-collapse.min.{N}px`).
- Needing to programmatically open/close from external triggers (e.g., an "expand all" button).
- Complex nested or tightly-integrated interaction patterns.

### Recommendation for FLS

Use `<details>`/`<summary>` as the HTML skeleton. Apply Alpine.js `x-collapse` (already a dependency in FLS's Alpine ecosystem) on the `<details>` content wrapper for smooth animation. This gives native semantics + fallback, with the animation layer being purely additive. There is no need for a "single open" accordion group for the course widget use-case (FLS needs independent disclosure panels, not a tabbed FAQ); the `name` attribute can be offered as an opt-in attribute if needed later.

Example skeleton (informing the cotton template):

```html
<details {% if open %}open{% endif %}>
  <summary class="cursor-pointer flex items-center justify-between ...">
    <span>{{ title }}</span>
    <svg ...><!-- chevron, rotated via CSS on [open] --></svg>
  </summary>
  <div x-show="$el.parentElement.open" x-collapse>
    <!-- markdown body -->
  </div>
</details>
```

Note: `x-collapse` on a child of `<details>` requires a small Alpine x-data bridge because `x-show` is reactive to Alpine state, not the native `open` attribute. A cleaner pattern is to wire the `<summary>`'s click event through Alpine and toggle an `x-data` boolean, keeping `<details>` for semantics and the Alpine boolean for animation only.

---

## 2. Accessibility: WAI-ARIA Disclosure / Accordion Patterns

### Roles and attributes

The WAI-ARIA Authoring Practices Guide (APG) distinguishes two patterns:

- **Disclosure**: a single independently-toggleable section. The trigger is a `<button>` with `aria-expanded="true|false"`. An `aria-controls="content-id"` link between button and panel is recommended (not strictly required but improves AT experience). This maps directly to `<summary>` inside `<details>` — the browser already exposes `<summary>` with button role and manages `aria-expanded` internally.
- **Accordion**: multiple disclosure panels managed together (arrow key navigation between headers). Only needed when panels are semantically grouped.

For FLS's single disclosure widget, the Disclosure pattern is correct. No extra ARIA is needed on top of `<details>`/`<summary>` — do not add `role="button"` or manual `aria-expanded` to `<summary>`, as this duplicates what the browser already sets and can cause doubled announcements.

### Keyboard support

Native `<details>`/`<summary>` provides:
- Tab: focus moves to/from `<summary>`
- Enter / Space: toggles the panel
- No arrow-key navigation between panels (appropriate for independent disclosures; arrow keys are only required for the full Accordion role)

If an "expand all" button is added in the future, it must be keyboard-reachable and update all panels.

### Heading semantics for the title

The `<summary>` element is not a heading. For accessibility, if the title is meaningful in the document outline (e.g., a section heading), wrap it in an appropriate heading level inside or adjacent to the disclosure. However, for FLS's use-case (inline optional-depth content within a course page), a styled label inside `<summary>` without a heading element is appropriate — overuse of heading levels inside body content creates noisy screen-reader navigation. The title text should be clear and descriptive enough to make sense when the panel is collapsed.

### prefers-reduced-motion

Wrap animation CSS in `@media (prefers-reduced-motion: no-preference)` so the slide only runs when the OS motion setting is active. For Alpine's `x-collapse`, override the transition to `duration-0` in a reduced-motion class, or add a Tailwind `motion-reduce:transition-none` utility. The widget must still function (open/close) even when animation is disabled — only the visual transition is suppressed.

### Common a11y mistakes to avoid

- Adding `role="button"` or `tabindex="0"` to `<summary>` — the browser already handles this.
- Using a `<div>` as the trigger with a click handler but without keyboard support.
- Setting `display: none` or `visibility: hidden` on the open panel content programmatically without also removing it from the accessibility tree (or vice versa: animating opacity to 0 while leaving it keyboard-focusable).
- Hiding essential course content behind a disclosure — use only for "optional depth" or supplementary material, never for content the learner must read to pass an assessment.
- Forgetting to rotate the chevron icon when the panel opens (a clear non-text indicator of state).

---

## 3. Animating Disclosure: The `height: auto` Problem and Modern Solutions

The core challenge: CSS cannot transition from `height: 0` to `height: auto` because `auto` is a keyword, not a calculable length.

### Approaches (best to least preferred for FLS):

**A. CSS `::details-content` + `transition-behavior: allow-discrete` (Baseline 2024/2025)**
Target the new `::details-content` pseudo-element to animate the height of the details content area. Pair with `transition-behavior: allow-discrete` to allow the discrete `content-visibility` state to animate. This is now Baseline across Chrome, Firefox, and Safari (September 2025 for `::details-content`). No JavaScript needed.

```css
details::details-content {
  height: 0;
  overflow: hidden;
  transition: height 300ms ease, content-visibility 300ms allow-discrete;
}
details[open]::details-content {
  height: auto; /* requires interpolate-size for full cross-browser support */
}
@media (prefers-reduced-motion: reduce) {
  details::details-content { transition: none; }
}
```

For full cross-browser height animation, `interpolate-size: allow-keywords` is still needed but is Chromium-only. Treat CSS animation as progressive enhancement.

**B. Alpine.js `x-collapse` (recommended for FLS now, until Baseline matures)**
Alpine's `x-collapse` plugin animates `height` from 0 to the element's natural `scrollHeight` via JavaScript, with a `transitionend` listener to set `height: auto` after expansion. It respects `display: none` after collapse (removing hidden elements from the accessibility tree). Supports `.duration.{ms}` and `.min.{N}px` modifiers.

```html
<div x-data="{ open: {{ open|yesno:'true,false' }} }">
  <button @click="open = !open" :aria-expanded="open.toString()">
    <span>{{ title }}</span>
    <svg :class="{'rotate-180': open}" class="transition-transform ...">...</svg>
  </button>
  <div x-show="open" x-collapse>
    {% markdown slot %}
  </div>
</div>
```

**C. CSS Grid `grid-template-rows: 0fr` to `1fr` trick**
Works in all browsers that support grid track animation (Chrome 107+, all current browsers). Does not require JavaScript. Inner element needs `overflow: hidden`. Slightly awkward because the element is still in the accessibility tree even when visually hidden (requires `aria-hidden` toggling or `inert` attribute).

**D. `max-height` hack**
Set a large fixed `max-height` on the open state. Cheap to implement but animation timing is inconsistent (the timing function runs over the full max-height duration, not the actual content height). Causes layout jank on complex/large pages. Avoid.

### FLS Recommendation

Use Alpine.js `x-collapse` today (already a project dependency, gives the smoothest accessible result with proper DOM cleanup). Add the CSS `::details-content` approach as a CSS-only fallback for no-JS environments, acknowledging that no-JS users get an instant open/close but correct functionality. Remove the `x-collapse` once `::details-content` is fully cross-browser and production-stable.

---

## 4. UX Patterns and Pitfalls

### What accordions/disclosures are good for

- "Optional depth" content: definitions, worked examples, background reading, supplementary context that the learner can skip on first pass.
- Breaking up long pages where some content is only relevant to some learners.
- Reducing cognitive load without removing content.

### Key pitfalls for an LMS context

**Hidden-from-search**: Closed `<details>` content IS in the DOM and is found by browser Ctrl+F (browsers expand `<details>` when the searched term is found inside). However, custom CSS/JS accordion implementations that use `display: none` may prevent Ctrl+F from finding content. Using `<details>` natively is safe.

**Print**: Native `<details>` panels print in their current state (closed = not printed). Consider a print stylesheet that forces `details[open]` or all `details` content visible. For an LMS where learners may print course pages, this is worth addressing.

**Deep linking**: If a URL fragment targets content inside a closed `<details>`, the browser should auto-expand the panel. This works natively in modern browsers when the fragment target is a child of `<details>`. Test this if FLS uses in-page anchors.

**SEO**: Google and other search engines do crawl and index `<details>` content regardless of open/closed state. Content behind custom JS-only accordions may not be indexed.

**Chevron rotation**: Rotate the icon on open state, not on hover. Use `[open] > summary svg { transform: rotate(180deg); }` in CSS or Alpine's `:class` binding.

**Default-open behaviour**: The `open` attribute on `<details>` is the correct HTML mechanism. In cotton: `<c-accordion title="..." open>...` maps to `{% if open %}open{% endif %}` on the `<details>` element.

**Do not hide essential content**: Assessments, safety notices, required reading should never be behind a closed disclosure. Disclosures are for elective depth.

**Nested accordions**: Avoid. They greatly increase cognitive load and interaction cost. Nested `<details>` is technically valid but a bad UX choice in an LMS.

**Indicate state clearly**: A label like "Show more" / "Show less" or a chevron icon is sufficient. Both the icon and the summary text must make sense without the body content visible.

---

## 5. The Reuse Question: Checklist / Key Takeaways vs Accordion vs Admonition

### How other documentation systems handle this

Material for MkDocs defines admonitions as typed blocks (`note`, `tip`, `warning`, `abstract`, etc.) that can optionally be made collapsible with `???` syntax. The `abstract` type (formerly also keyed as `summary`/`tldr`) is the closest built-in to "key takeaways". Checklists are not a separate widget — they are standard markdown task lists rendered inside any block. This pattern is well-established: typed admonition for semantic context, markdown for content.

Sphinx uses a similar directive-based approach. Neither system treats "checklist" as a widget separate from admonition + markdown.

### Should key takeaways be an admonition type, accordion variant, or separate widget?

**Key takeaways**: should be a named admonition type, not an accordion. Takeaways are summary content the learner should always see — collapsing them would be counterproductive. An admonition with `type="key-takeaways"` (or `type="summary"`) renders a styled box with a distinctive icon (e.g., a list/checklist icon) and no collapse. The body is standard markdown bullet points. This fits cleanly into the configurable admonition system already planned.

**Checklist**: a titled markdown checklist is also best served as an admonition variant (`type="checklist"` with a checkbox icon), not an accordion. The checklist items are interactive-looking (via markdown `- [ ]` syntax rendering), but in a course content context they are likely read-only reference content (not persistent state tracking). If checklist items need to be persistently ticked off by the learner, that becomes a different feature requiring its own model — not a styling question. For now, render as admonition with checklist icon.

### Rationale

Both key takeaways and checklists gain nothing from being collapsible — their purpose is to surface summarised information efficiently. Hiding them behind a disclosure adds interaction cost for no benefit. Making them admonition variants keeps the authoring syntax consistent (`<c-admonition type="key-takeaways">...</c-admonition>`), avoids a proliferation of widget templates, and means they inherit any theme customisation built for admonitions.

The accordion widget (`<c-accordion title="..." open>`) remains its own distinct component because it serves a structurally different purpose: hiding optional depth content behind an interaction rather than presenting a styled summary block.

---

## References

- [HTML Details Element: The Native Accordion You're Not Using — Trevor Lasn](https://www.trevorlasn.com/blog/html-details-element)
- [Accessible accordions part 2 - using `<details>` and `<summary>` — Hassell Inclusion](https://www.hassellinclusion.com/blog/accessible-accordions-part-2-using-details-summary/)
- [Accessible Accordion vs Disclosure: Dev Best Practices — 216digital](https://216digital.com/accessible-accordion-vs-disclosure-dev-best-practices/)
- [WAI-ARIA Authoring Practices Guide: Disclosure Pattern — W3C](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/)
- [WAI-ARIA Patterns — W3C APG](https://www.w3.org/WAI/ARIA/apg/patterns/)
- [Accordion Pattern — UX Patterns for Devs](https://uxpatterns.dev/en/patterns/content-management/accordion)
- [Accordions on Desktop: When and How to Use — Nielsen Norman Group](https://www.nngroup.com/articles/accordions-on-desktop/)
- [Accessible Accordion — aditus.io](https://www.aditus.io/patterns/accordion/)
- [Alpine.js x-collapse Plugin](https://alpinejs.dev/plugins/collapse)
- [Collapse Animations in Alpine.js — blimto](https://blimto.com/concepts/alpinejs/alpinejs-collapse-animations)
- [Accessible and Animated Expand/Collapse with Alpine.js and Tailwind — DEV Community](https://dev.to/philw_/accessible-and-animated-expand-collapse-components-with-alpine-js-and-tailwind-css-ccn)
- [Animated Accordions with Details Element & CSS — Builder.io](https://www.builder.io/blog/animated-css-accordions)
- [Animating accordion using CSS only with interpolate-size — Medium](https://rifkiaf.medium.com/animating-accordion-using-css-only-with-the-interpolate-size-property-db0a853973d1)
- [CSS Grid Can Do Auto Height Transitions — CSS-Tricks](https://css-tricks.com/css-grid-can-do-auto-height-transitions/)
- [Admonitions - Material for MkDocs](https://squidfunk.github.io/mkdocs-material/reference/admonitions/)
- [Details and summary — web.dev](https://web.dev/learn/html/details)
- [Details/Summary Are Not [insert control here] — Adrian Roselli](https://adrianroselli.com/2019/04/details-summary-are-not-insert-control-here.html)
- [prefers-reduced-motion — MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion)

status: ok
