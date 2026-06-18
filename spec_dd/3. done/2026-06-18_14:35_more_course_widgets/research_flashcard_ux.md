# Research: Two-Sided Flip Flash Card Widget

**Summary:** A click-to-flip flash card widget for FLS course content is well-established as a UX pattern and technically feasible with Alpine.js + Tailwind, but the implementation has several non-obvious traps — particularly around accessibility (hidden faces must be removed from the a11y tree, keyboard operability requires explicit handling, screen-reader state announcement has no perfect ARIA match), variable-height content (the standard absolute-positioning layout breaks when back content is taller than front), and interactive content inside a hidden face (links stay focusable unless explicitly managed). The recommendations below are tailored to the Alpine.js + Tailwind + cotton authoring context.

---

## 1. Flip Card UX Patterns in Learning Apps

### Click vs Hover

All major flashcard apps (Anki, Quizlet, Brainscape) use **click-to-reveal** (or tap-to-reveal on mobile), not hover. Hover-triggered flips are broadly considered a broken pattern because:

- Hover does not exist on touch devices; users cannot reveal the back face at all.
- Accidental hovers cause the card to flip mid-read.
- WCAG 2.1 SC 1.4.13 (Content on Hover or Focus) is harder to satisfy when flip state is driven by hover.

**Recommendation:** Use a single click/tap toggle. The flip should be intentional, not incidental.

### Front vs Back Convention

- **Front (prompt face):** A question, cue term, concept name, image, or code snippet. Ideally concise — one or two sentences at most. This is what the learner sees first.
- **Back (answer/explanation face):** The answer, definition, worked example, or elaboration. May be longer. Can contain lists, code, or multiple paragraphs.

This is the universal convention across Anki, Quizlet, and paper flashcards. Authors should understand this framing; the cotton tag should reflect it with clear slot names (`front` / `back`).

### Flip Affordance

Users need a visual cue that the card is interactive. Common patterns:
- A "flip" icon or label ("Click to reveal") visible on the front face.
- A subtle border/shadow that suggests depth.
- Cursor changes to `pointer` on hover.

Without at least one affordance, many users will not discover the card is interactive. This should be a design-time decision but is worth noting during implementation.

---

## 2. CSS / Tailwind 3D Flip Technique

### Core CSS Model

The standard three-layer structure (from [DeSandro's 3D Transforms primer](https://3dtransforms.desandro.com/card-flip)):

```
scene  (perspective container)
  └── card  (rotating element, transform-style: preserve-3d)
        ├── front face  (backface-visibility: hidden)
        └── back face   (backface-visibility: hidden; rotateY(180deg) initially)
```

When flipped, `rotateY(180deg)` is applied to the **card** layer. The front face (now facing away) becomes hidden by `backface-visibility: hidden`, and the pre-rotated back face rotates into view.

### Tailwind Arbitrary-Value Classes (Tailwind v3)

Tailwind v3 does not ship 3D utilities natively; they require arbitrary values:

```html
<!-- scene -->
<div class="[perspective:1000px]">
  <!-- card, rotating wrapper -->
  <div class="[transform-style:preserve-3d] transition-transform duration-500"
       :class="{ '[transform:rotateY(180deg)]': flipped }">
    <!-- front -->
    <div class="[backface-visibility:hidden]"> ... </div>
    <!-- back -->
    <div class="[backface-visibility:hidden] [transform:rotateY(180deg)]"> ... </div>
  </div>
</div>
```

Note: Tailwind v4 adds `backface-hidden`, `transform-3d`, `perspective-*`, and `rotate-y-*` utilities natively, making this cleaner. If FLS ever upgrades, this becomes significantly simpler.

### Variable-Height Problem and Solution

The standard approach (`position: absolute` on both faces) **breaks when back content is taller than front**: the card clips the back face because the scene's height is set by the front.

The Smashing Magazine solution ([magic flip cards sizing](https://www.smashingmagazine.com/2020/02/magic-flip-cards-common-sizing-problem/)) uses `display: flex` and `min-width: 100%` instead of absolute positioning:

```css
.card-inner {
  display: flex;
  transform-style: preserve-3d;
}

.front, .back {
  backface-visibility: hidden;
  min-width: 100%;
}

.back {
  /* positioned to sit behind the front in layout flow */
  transform: rotateX(-180deg) translate(-100%, 0);
}
```

Both faces participate in normal layout flow (flex items), so the card expands to the height of whichever face is taller. This is essential for markdown content where back faces can contain lengthy explanations.

**Recommendation:** Use the flex-based layout, not absolute positioning.

### Alpine.js State

```html
<div x-data="{ flipped: false }">
  <button @click="flipped = !flipped"
          :aria-pressed="flipped.toString()"
          ...>
    <!-- rotating card inner -->
  </button>
</div>
```

Alpine handles the toggle state cleanly with `x-data`. The `@click` handler plus `:class` binding applies the rotation class. Keyboard handling (Enter/Space) is automatic when the interactive element is a `<button>`.

---

## 3. Accessibility

This is the most commonly botched area of flip card implementations. The [Code: Accessible flip card pattern](https://codeaccessible.com/codepatterns/flip-cards/) documents the required techniques in detail.

### Keyboard Operability

- The flip trigger **must be a `<button>` element** (or an element with `role="button"` and `tabindex="0"`). Using a `<div>` or the scene container without these is a WCAG 2.1 SC 2.1.1 (Keyboard) failure.
- `<button>` elements respond to Enter and Space natively; no extra `@keydown` handler is needed if the button is the flip trigger.
- If the button wraps the full card face, ensure the card has a reasonable minimum tap/click target size (at least 44×44 CSS px per WCAG 2.5.5).

### ARIA Semantics

There is no ARIA pattern that perfectly matches a flip card. The two closest options:

- **`aria-pressed`** (toggle button) — semantically "this button is in a pressed/on state". Works well: `aria-pressed="false"` (front showing) → `aria-pressed="true"` (back showing). Screen readers announce "button, [name], pressed" vs "not pressed". Alpine binding: `:aria-pressed="flipped.toString()"`.
- **`aria-expanded`** — semantically "this control expands/collapses a region". Less apt for a flip card because both faces are always rendered (just hidden), but still widely used.

`aria-pressed` is the recommended choice here because it accurately describes a toggle between two states.

The button also needs an accessible name. Since the front face contains the question/prompt, the button's accessible name can be derived from a `aria-label` (e.g. "Flash card: [topic]") or by making the front-face text the button's text content. Avoid empty `aria-label`.

Add an `aria-describedby` pointing to a visually-hidden instruction: e.g. "Press Enter or Space to flip the card."

### Screen Reader Behaviour for Hidden Faces

`backface-visibility: hidden` is a **visual-only** property. Screen readers ignore it. Without explicit handling, both faces will be read aloud regardless of which face is visible.

The hidden face must be removed from the accessibility tree:

```html
<!-- Front face -->
<div :aria-hidden="flipped ? 'true' : 'false'"> ... </div>
<!-- Back face -->
<div :aria-hidden="flipped ? 'false' : 'true'"> ... </div>
```

This makes only the currently visible face readable by screen readers.

If either face contains links or other interactive elements, `aria-hidden` on the face also removes them from keyboard focus order (in combination with the `tabindex="-1"` technique on children if needed). However, `aria-hidden` alone does not remove elements from tab order in all browser/AT combinations — see pitfalls section.

### Reduced Motion

Users with vestibular disorders can be harmed by 3D rotation animations. Per WCAG 2.3.3 (Animation from Interactions, AAA) and general best practice, the flip animation must be disabled or reduced when the user has enabled `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  .card-inner {
    transition: none;
  }
}
```

With `transition: none`, the card still flips (state changes) but snaps instantly rather than animating. This is the correct approach: remove the motion, not the functionality.

This can also be expressed as an Alpine.js class binding checking `window.matchMedia('(prefers-reduced-motion: reduce)').matches`, but the CSS `@media` approach is simpler and more robust.

### Focus Management

- Do not trap focus inside the card. After flipping, focus should remain on the flip button.
- If the back face contains interactive elements (links, buttons), they should become keyboard-reachable once the back is showing and be hidden (via `aria-hidden` on the face or `tabindex="-1"` on children) when the front is showing.
- Do not programmatically move focus on flip; the user did not navigate — they toggled state.

### WCAG Criteria Addressed

- 1.3.1 Info and Relationships
- 2.1.1 Keyboard
- 2.4.3 Focus Order
- 4.1.2 Name, Role, Value
- 2.3.3 Animation from Interactions (AAA, but still best practice)

---

## 4. Pitfalls and Common Complaints

### Hidden Face Links Stay Focusable

`aria-hidden="true"` removes elements from the accessibility tree but does **not** always remove them from the tab order. A link inside a face that has `aria-hidden="true"` may still receive keyboard focus, producing a confusing "invisible focus" state. To fully remove hidden interactive elements from tab order, set `tabindex="-1"` on all interactive descendants of the hidden face when it is flipped away. With Alpine.js this can be done with an `x-effect` or by setting `tabindex` via `:tabindex="flipped ? -1 : 0"` on individual interactive children.

### Motion Sickness

Full 3D rotation is one of the most motion-intensive effects on the web. Some users with vestibular conditions are severely affected. Do not default to a slow or dramatic animation (1s+ rotations are particularly bad). A transition of 0.3–0.5s is more tolerable. Always honour `prefers-reduced-motion`.

### Content Hidden from Search and Print

The back face is visually hidden (but DOM-present). Search engines and browser find-in-page typically index both faces, which is usually acceptable. However, print stylesheets may produce confusing output (both faces printed, overlapping). Consider adding a print CSS rule that shows both faces linearly for print.

### Markdown with Interactive Content on Hidden Face

If an author embeds a link or another interactive widget on the back face, that content is hidden behind the card. This is by design, but:
- Links inside the back face will be tabbable even when the front is showing (unless `tabindex` management is implemented — see above).
- Nested interactive widgets (e.g., a code block with a copy button) inside a hidden face should be avoided or explicitly handled.

### Mobile Tap Target

The flip trigger must have a sufficient tap target. If the trigger is styled as a small icon or label rather than the whole card surface, it may be too small on mobile. Recommend making the entire card surface the tap target.

### Inconsistent Screen Reader Support

The Articulate community and eLearning accessibility testers have documented that flip cards behave inconsistently across JAWS, NVDA, and VoiceOver. The `aria-pressed` + `aria-hidden` approach described above gives the best cross-AT coverage, but thorough testing with multiple screen readers is advisable before shipping. The `aria-live` approach (announcing the revealed content via a live region) is an alternative but can be verbose.

---

## 5. Front/Back Authoring as Cotton Slots

Django-cotton's **named slots** (`<c-slot name="...">...</c-slot>`) are the natural fit for multi-face content where each face needs markdown rendering:

```html
<c-flashcard>
  <c-slot name="front">
    What is the capital of France?
  </c-slot>
  <c-slot name="back">
    **Paris**. It has been the capital since the 10th century.
  </c-slot>
</c-flashcard>
```

Inside the `flashcard.html` cotton template, both slots become variables (`{{ front }}` and `{{ back }}`) that can each be passed through the `{% markdown %}` template tag (as the existing `callout.html` does with `{% markdown slot %}`).

Attributes (the `<c-vars>` mechanism) are appropriate for configuration (e.g. `label`, `hint`, or an accessibility label for the card), but not for multi-paragraph markdown content. Named slots handle the full richness of markdown including headings, code blocks, and nested cotton components.

The authoring surface is clean and mirrors the paper flashcard metaphor: a clearly-labelled `front` and `back` slot.

---

## References

- [Code: Accessible — Flip Cards pattern](https://codeaccessible.com/codepatterns/flip-cards/) — ARIA, keyboard, and tabindex patterns for accessible flip cards
- [Smashing Magazine — Magic Flip Cards: Solving A Common Sizing Problem](https://www.smashingmagazine.com/2020/02/magic-flip-cards-common-sizing-problem/) — CSS flex-based fix for variable-height faces
- [DeSandro 3D Transforms — Card Flip](https://3dtransforms.desandro.com/card-flip) — Core CSS model: scene / card / face structure
- [Telerik — A Card Flip with Tailwind](https://www.telerik.com/blogs/card-flip-tailwind) — Tailwind arbitrary-value class implementation
- [Alpine JS Flip Cards — StackBlitz demo](https://stackblitz.com/edit/alpine-js-flip-cards) — Alpine.js state management for flip cards
- [Articulate community — Flip card interaction, accessibility question](https://community.articulate.com/discussions/discuss/flip-card-interaction-accessibility-question/851660) — Real-world screen reader testing findings and failure modes
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion) — Media query reference for reduced motion
- [CSS-Tricks — Accessible Web Animation: The WCAG on Animation Explained](https://css-tricks.com/accessible-web-animation-the-wcag-on-animation-explained/) — WCAG animation guidelines
- [Marcy Sutton — Accessible card flip with reduced motion option (CodePen)](https://codepen.io/marcysutton/pen/ejmYEG) — Reference implementation from a leading accessibility practitioner
- [Django-Cotton — Components docs](https://django-cotton.com/docs/components) — Named slots syntax for multi-part content authoring
- [AngularFix — How to make interactive flipcards accessible to screen readers with ARIA?](https://www.angularfix.com/2022/03/how-to-make-interactive-flipcards.html) — aria-hidden toggling and tabindex management patterns

status: ok
