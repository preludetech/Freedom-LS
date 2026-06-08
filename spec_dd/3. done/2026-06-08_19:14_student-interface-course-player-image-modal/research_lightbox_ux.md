# Research: Lightbox / Spotlight Modal — UX & Accessibility Best Practices

Scope: image-expand modal in a course player. Out of scope: zoom, download, pagination/arrows, thumbnails.

---

## 1. Accessible Dialog Pattern — Focus Management, ARIA, Keyboard

### ARIA markup (required)

```html
<dialog
  role="dialog"
  aria-modal="true"
  aria-labelledby="lightbox-title"
  id="image-lightbox"
>
  <h2 id="lightbox-title">Figure 3 — Diagram of the water cycle</h2>
  ...
  <button autofocus>Close</button>
</dialog>
```

- `role="dialog"` — required on the container (the native `<dialog>` element carries this implicitly).
- `aria-modal="true"` — tells screen readers that content behind the dialog is inert. Only set this when all background content is truly inert (use the `inert` attribute on `<main>` or a wrapper, or rely on `<dialog>.showModal()` which handles it natively).
- `aria-labelledby` pointing at the visible title — the accessible name for the dialog. Alternatively use `aria-label` if no visible title element exists, but a visible title is always better.
- `aria-describedby` is optional; omit it if the body content has complex structure (the APG recommends against it in that case).

Source: [WAI-ARIA APG Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)

### Prefer the native `<dialog>` element with `showModal()`

`showModal()` gives you for free:
- Built-in focus trapping (browser-managed).
- Escape key closes the dialog natively.
- Correct ARIA semantics without extra attributes.
- A `::backdrop` pseudo-element for styling the scrim.
- Background content becomes inert automatically.

This avoids re-implementing behaviour that browsers now handle correctly.

Source: [WAI-ARIA APG Modal Dialog Example](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/), [MDN aria-modal](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal)

### Focus on open

- Place `autofocus` on the **close button** (eBay MIND Patterns recommendation: focus goes to the dismiss button first, not the image). This gives screen reader users an immediately actionable control.
- Alternative: place `tabindex="-1"` on the title `<h2>` and focus it programmatically. The heading announces what opened and gives context before any action is taken.
- Do NOT focus the image itself as the first element — screen readers will describe the image with no obvious next action.
- Avoid autofocusing an element deep in the DOM; if focus is placed far down the content, `showModal()` may open the dialog scrolled to the bottom.

Source: [WAI-ARIA APG Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [HTML Dialog: Getting Accessibility and UX Right](https://jaredcunha.com/blog/html-dialog-getting-accessibility-and-ux-right), [eBay MIND Patterns — Lightbox Dialog](https://ebay.gitbook.io/mindpatterns/disclosure/lightbox-dialog)

### Focus trap (Tab / Shift+Tab)

- Tab moves forward through all focusable elements inside the dialog; at the last element it wraps to the first.
- Shift+Tab moves backward; at the first element it wraps to the last.
- No focus may escape to the page behind the dialog.
- The APG strongly recommends the dialog tab sequence include **at least one visible button** that closes the dialog.

Source: [WAI-ARIA APG Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)

### Keyboard interactions (full set required)

| Key | Behaviour |
|-----|-----------|
| Escape | Close the dialog |
| Tab | Next focusable element (wraps) |
| Shift+Tab | Previous focusable element (wraps) |

No other keyboard interactions are needed for this design (no zoom, no navigation arrows).

### Focus restoration on close

Focus must return to the element that triggered the dialog (the thumbnail/image in the course content). Store a reference to `document.activeElement` before calling `showModal()` and call `.focus()` on it after `close()`.

### Close button

- Place the close button visibly in the modal header (top-right per the design mockup).
- Label it with an accessible name: `aria-label="Close image"` or use visually hidden text alongside the X icon. A bare `<button>` with only an SVG icon and no text alternative is a common failure.
- The button must be visible at all times — do not hide it behind hover states.

Source: [eBay MIND Patterns — Lightbox Dialog](https://ebay.gitbook.io/mindpatterns/disclosure/lightbox-dialog), [WAI-ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)

### Image alt text inside the lightbox

- The `<img>` inside the modal needs a meaningful `alt` attribute. For a lightbox this should be the same as (or more descriptive than) the inline thumbnail.
- If the caption text already fully describes the image, `alt=""` (decorative) is acceptable to avoid duplication, but only if the caption is programmatically associated.
- Use `aria-describedby` on the `<img>` pointing at the caption `<p>` if additional description is useful.

---

## 2. Backdrop — Dimming, Blur, Click-Outside-to-Close

### Scrim opacity

- Standard practice: `rgba(0,0,0,0.5–0.7)`. Values above ~0.85 risk making users feel they have left the page entirely (NN/G finding). For a course player — where the student should feel in context — a value in the 0.5–0.65 range is appropriate.
- Blur on the backdrop (`backdrop-filter: blur(…)`) reinforces that content is behind, not gone. Keep it subtle (4–8px).
- The `<dialog>::backdrop` pseudo-element is the right place for both dimming and blur when using the native element.

Source: [NN/G — Overuse of Overlays](https://www.nngroup.com/articles/overuse-of-overlays/), [MotoCMS Lightbox UX](https://www.motocms.com/blog/en/lightbox-design-for-ux/)

### Click-outside-to-close — the backdrop click pitfall

This is a known sharp edge with the native `<dialog>` element.

**The problem:** If you add a `click` listener to the dialog and check `event.target === dialogElement`, it fails when the user clicks on child content (e.g., the image card, or the image itself) because `event.target` is the child element, not the dialog. Conversely, the `::backdrop` pseudo-element cannot receive events by default.

**Reliable solution (two-part):**

```css
dialog::backdrop {
  pointer-events: none; /* backdrop clicks fall through to <html> */
}
```

```javascript
document.addEventListener('click', (event) => {
  if (event.target.closest('dialog')) return; // click was inside dialog
  const dialog = document.querySelector('dialog[open]');
  dialog?.close();
});
```

By setting `pointer-events: none` on `::backdrop`, clicks on the backdrop register on `<html>`. Then `.closest('dialog')` traverses up the DOM tree and correctly identifies whether the click originated inside the dialog or outside.

**Specific risk for this design:** The spotlight card is a white box centered within the dialog. If a student clicks the card (or the image within it), `event.target` will be the card/image — the `.closest('dialog')` guard correctly handles this. Without that guard, any click inside the modal would close it.

**Alternative modern approach:** The new `closedby` HTML attribute (`closedby="none"` or `closedby="any"`) declaratively controls this, but browser support is not yet universal as of mid-2026. Avoid relying on it without a polyfill.

Source: [Go Make Things — Revisiting backdrop click dismissal](https://gomakethings.com/revisiting-how-to-dismiss-native-html-dialog-elements-when-the-backdrop-is-clicked/), [Go Make Things — backdrop click original](https://gomakethings.com/articles/how-to-dismiss-native-html-dialog-elements-when-the-backdrop-is-clicked/)

### Providing multiple close mechanisms

Users expect all three: close button, Escape key, click-outside. Keyboard users and screen reader users rely on Escape and the close button. Pointer users expect click-outside. Providing only one of these is an anti-pattern.

Source: [NN/G — Overuse of Overlays](https://www.nngroup.com/articles/overuse-of-overlays/), [Lightbox Accessibility — WP Newsify](https://wpnewsify.com/blog/lightbox-accessibility-and-seo-considerations-for-improved-ux/)

---

## 3. Caption / Title / Description Placement

### Below the image, not overlaid

The design mockup (title + description below the image, in a white chrome area) aligns with best practice. Avoid overlaying text on top of the image:

- Lightbox libraries that default to overlaying captions on the image bottom edge consistently produce **unreadable text on light-coloured images** (white text on white background). This is a known failure mode.
- Text in a dedicated white/surface area below the image has guaranteed contrast regardless of image content.
- Overlay text requires a semi-transparent scrim behind the text, adding visual noise and partially obscuring the image itself.

**Recommendation:** Keep title and description in the white card area below the image — the design is correct. Do not move them onto the image.

Source: [Lightbox Accessibility and SEO — WP Newsify](https://wpnewsify.com/blog/lightbox-accessibility-and-seo-considerations-for-improved-ux/), [eBay MIND Patterns](https://ebay.gitbook.io/mindpatterns/disclosure/lightbox-dialog)

### Figure number and title (top-left of card)

- Mark it up as an `<h2>` (or `<h3>` if the page already has an `<h2>` in the main content). eBay MIND Patterns specifies dialog headings should be `h2`.
- This element should be the `aria-labelledby` target of the dialog — it becomes the accessible name.
- Keep it brief. If "Figure 3" and the title are separate, wrap both in the heading element.

### Description text (bottom of card)

- Plain `<p>` element. No truncation on desktop (this is an expanded view — the student expects to read the full text).
- On mobile, allow scroll within the card if content is long (see mobile section below).
- Associate it with the image via `aria-describedby` on the `<img>` if it meaningfully describes what is shown.

---

## 4. Common UX Complaints and Anti-Patterns

Based on multiple sources, these are the most frequently cited failures:

| Anti-pattern | Consequence | Fix |
|---|---|---|
| Close button too small, icon-only, no accessible name | Keyboard/SR users can't identify or activate it | Large enough touch target (min 44×44 CSS px), visible label or `aria-label` |
| Close button hidden until hover | Mobile users with no hover state cannot find it | Always visible |
| Text overlaid on unknown image content | Unreadable on light images | Put text in dedicated surface below image |
| No Escape key support | Keyboard users trapped | Always support Escape (native `<dialog>` does this for free) |
| No focus trap | Keyboard users can tab into background content | Use `showModal()` or manual trap |
| No focus restoration on close | Screen reader/keyboard user lost their place | Store and restore trigger element focus |
| Background page remains scrollable | Dual scrollbars, confusing context | `showModal()` / `overflow: hidden` on `<body>` while open |
| Layout shift when dialog opens | Scrollbar disappears, content jumps | `scrollbar-gutter: stable` on `<body>` |
| Modal with only one close mechanism | Users who can't use a mouse have no exit | Provide button + Escape + click-outside |
| Excessive backdrop opacity (>0.85) | Users feel they left the page | Use 0.5–0.65 |
| Dialog opens scrolled to wrong position | Image or close button off-screen | Focus on title or close button at top of dialog |
| Card fills full dialog width with no padding | Clicks anywhere on card register as "inside" correctly but feels cramped | Keep card narrower than viewport, with visible dark scrim around it |

Sources: [NN/G — Overuse of Overlays](https://www.nngroup.com/articles/overuse-of-overlays/), [eBay MIND Patterns](https://ebay.gitbook.io/mindpatterns/disclosure/lightbox-dialog), [Accessible Modal Dialogs — Floe Project](https://handbook.floeproject.org/approaches/accessible-modal-dialogs/), [WAI-ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [Jared Cunha — HTML Dialog](https://jaredcunha.com/blog/html-dialog-getting-accessibility-and-ux-right)

---

## 5. Mobile / Small-Screen Considerations

### Card sizing

- On desktop: the card should not fill the full screen — the visible dark scrim around it is the visual cue that this is a modal layer.
- On mobile (< ~640 px): let the card fill most of the viewport width (e.g., 95 vw), with padding inside. The image should scale to fit (`max-width: 100%; height: auto`).
- Avoid fixed pixel dimensions for the card — use `max-width` + `width: 90vw` pattern.

### Card height and overflow

- On small screens, long description text may cause the card to exceed the viewport height.
- Solution: set `max-height: 90dvh` on the card (use `dvh` not `vh` to account for mobile browser chrome), with `overflow-y: auto` on the content area inside the card.
- Do NOT let the dialog itself scroll the page — only the card interior should scroll.

### Touch targets

- The close button must be at least 44×44 CSS px (WCAG 2.5.5 / 2.5.8 guideline). On mobile this is especially critical.
- No hover-dependent interactions — close button and any other controls must be permanently visible and tappable.

### Backdrop click on mobile

- Mobile users may accidentally tap outside the modal (especially on small screens). This is more disruptive than on desktop because there is less margin.
- The click-outside-to-close mechanism is still correct UX, but consider whether to add a brief visual confirmation (e.g., the backdrop click does nothing on first tap, user must tap a close element). However, this is non-standard and adds friction — the simpler approach is to ensure the card is large enough that accidental taps outside it are unlikely.
- NN/G explicitly notes: "many users won't know they can click outside the modal to dismiss it, and touchscreen users may dismiss it accidentally." The close button must therefore be prominent enough to be the primary close affordance.

### Background scroll lock

- Prevent the underlying page from scrolling while the modal is open: `overflow: hidden` on `<body>`, or rely on `showModal()`.
- Use `scrollbar-gutter: stable` on `<body>` before the dialog opens to prevent layout shift when the scrollbar disappears.

Sources: [NN/G — Overuse of Overlays](https://www.nngroup.com/articles/overuse-of-overlays/), [Jared Cunha — HTML Dialog](https://jaredcunha.com/blog/html-dialog-getting-accessibility-and-ux-right), [MotoCMS Lightbox Design](https://www.motocms.com/blog/en/lightbox-design-for-ux/)

---

## 6. Reduced-Motion Considerations

Users with vestibular disorders can experience nausea, vertigo, or migraines from scaling, panning, or fast-moving animations. WCAG 2.3.3 (AAA) requires a way to disable non-essential animation. Even at AA, respecting `prefers-reduced-motion` is a strong accessibility practice.

### What to do

```css
/* Default: fade + scale in */
@keyframes dialog-enter {
  from { opacity: 0; transform: scale(0.92); }
  to   { opacity: 1; transform: scale(1); }
}

dialog[open] .spotlight-card {
  animation: dialog-enter 200ms ease-out;
}

/* Reduced motion: fade only, no scale */
@media (prefers-reduced-motion: reduce) {
  dialog[open] .spotlight-card {
    animation: none;
    /* Or replace with a simple opacity transition: */
    /* transition: opacity 150ms linear; */
  }
}
```

Key principles:
- **Remove or skip** scale/slide/zoom animations when `prefers-reduced-motion: reduce`.
- **Opacity fades** are generally safe (they don't imply spatial movement) — a simple fade-in is acceptable even for reduced-motion users.
- Short durations (100–200 ms) are less problematic than slow sweeping motions.
- Do not animate the backdrop blur level on open/close — that is a motion trigger.

Sources: [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion), [W3C WCAG C39 technique](https://www.w3.org/WAI/WCAG22/Techniques/css/C39), [CSS-Tricks — prefers-reduced-motion](https://css-tricks.com/almanac/rules/m/media/prefers-reduced-motion/), [Pope Tech — Accessible animation](https://blog.pope.tech/2025/12/08/design-accessible-animation-and-movement/)

---

## Summary of Concrete Recommendations for This Design

1. Use `<dialog>` + `showModal()` — gets focus trapping, Escape, inert background, and `::backdrop` for free.
2. `aria-modal="true"`, `aria-labelledby` pointing at the figure title `<h2>`.
3. On open, autofocus the close button (or the `<h2>` with `tabindex="-1"`). On close, restore focus to the trigger element.
4. Close button: top-right, always visible, minimum 44×44 px touch target, `aria-label="Close image"`.
5. Backdrop scrim: `rgba(0,0,0,0.55)` + `blur(6px)` via `dialog::backdrop`.
6. Click-outside-to-close: use `pointer-events: none` on `::backdrop`, listen on `document`, guard with `.closest('dialog')`.
7. Title + description stay in the white card area below the image — do not overlay on image.
8. Card: `max-width: 720px; width: 90vw; max-height: 90dvh; overflow-y: auto` on card interior.
9. `scrollbar-gutter: stable` on `<body>` to prevent layout shift.
10. `@media (prefers-reduced-motion: reduce)` — strip scale animation, allow opacity fade only.
11. Image `alt` attribute must be meaningful; associate description with `aria-describedby` on the `<img>` if it adds value.

---

## Reference URLs

- [WAI-ARIA APG — Dialog (Modal) Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [WAI-ARIA APG — Modal Dialog Example](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/)
- [MDN — aria-modal attribute](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal)
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)
- [eBay MIND Patterns — Lightbox Dialog](https://ebay.gitbook.io/mindpatterns/disclosure/lightbox-dialog)
- [NN/G — Overuse of Overlays](https://www.nngroup.com/articles/overuse-of-overlays/)
- [Go Make Things — Revisiting backdrop click dismissal](https://gomakethings.com/revisiting-how-to-dismiss-native-html-dialog-elements-when-the-backdrop-is-clicked/)
- [Go Make Things — Backdrop click original](https://gomakethings.com/articles/how-to-dismiss-native-html-dialog-elements-when-the-backdrop-is-clicked/)
- [Jared Cunha — HTML Dialog: Getting Accessibility and UX Right](https://jaredcunha.com/blog/html-dialog-getting-accessibility-and-ux-right)
- [Floe Project — Accessible Modal Dialogs](https://handbook.floeproject.org/approaches/accessible-modal-dialogs/)
- [Lightbox Accessibility and SEO — WP Newsify](https://wpnewsify.com/blog/lightbox-accessibility-and-seo-considerations-for-improved-ux/)
- [W3C WCAG — C39: Using prefers-reduced-motion](https://www.w3.org/WAI/WCAG22/Techniques/css/C39)
- [CSS-Tricks — prefers-reduced-motion](https://css-tricks.com/almanac/rules/m/media/prefers-reduced-motion/)
- [Pope Tech — Accessible animation](https://blog.pope.tech/2025/12/08/design-accessible-animation-and-movement/)
- [MotoCMS — Lightbox Design for UX](https://www.motocms.com/blog/en/lightbox-design-for-ux/)
- [Code Accessible — Lightbox pattern](https://codeaccessible.com/codepatterns/lightbox/)

status: ok
