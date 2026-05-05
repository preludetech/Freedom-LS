# Research: Sticky / frosted-glass header

Background reading for the learner-experience-polish header refresh. Captures
patterns, tradeoffs, browser quirks and accessibility constraints. No
implementation decisions are made here — that happens in the spec / plan.

Stack constraint: TailwindCSS + Alpine.js. No heavy JS frameworks.

---

## 1. `position: sticky` vs `position: fixed`

### `position: fixed`
- Element is removed from document flow. Following content shifts up under
  the header unless we reserve space (typically `padding-top` on `<body>` or
  the first section equal to header height).
- Easy to reason about — the header is always at viewport top.
- Toggling between `static` and `fixed` via JS introduces a CLS hit because
  the document flow changes mid-scroll. Bad for Core Web Vitals.
- Required if the header must hover above a scroll container that itself
  is scrolling (sticky won't escape an overflow ancestor).

### `position: sticky` (recommended default)
- Stays in document flow; no reserved-space hack needed and no CLS surprise.
- Works as long as no ancestor has `overflow: hidden | auto | scroll` or a
  `transform`/`filter` that creates a containing block — those silently
  break sticky. This is the single most common "why isn't it sticking"
  bug.
- Sticky is scoped to its nearest scroll container; for a site-wide header
  this is usually `<body>` / `<html>`, which is what we want.
- Known Firefox bug: `backdrop-filter` stops working on a `position: sticky`
  element if an ancestor has both `overflow` and `border-radius` set
  (relevant when nesting the header inside a rounded card layout).

**Verdict for a site-level header:** prefer `position: sticky; top: 0;`. Fall
back to `fixed` only if there's a structural reason sticky won't work.

Refs:
- https://www.kevinpowell.co/article/positition-fixed-vs-sticky/
- https://blog.logrocket.com/ux-design/sticky-vs-fixed-navigation/
- https://dev.to/luisaugusto/stop-using-fixed-headers-and-start-using-sticky-ones-1k30

---

## 2. `backdrop-filter: blur(...)` — support, prefixes, fallbacks

### Support (May 2026)
- ~92–97% global support; effectively universal on evergreen browsers.
- Chrome / Edge: full since 76 / 79.
- Firefox: full since **103** (Aug 2022). Older variants don't render the
  blur — the element will still be semi-transparent, just not blurred.
- Safari: works since 9, but **Safari < 17 needs `-webkit-backdrop-filter`**.
  Always ship both properties — autoprefixer handles this if configured.

### Required CSS
```css
.header {
  -webkit-backdrop-filter: blur(12px) saturate(140%);
          backdrop-filter: blur(12px) saturate(140%);
  background-color: hsl(0 0% 100% / 0.6); /* must be translucent */
}
```

If there's no semi-transparent `background-color`, there is nothing to blur
*through* — the filter is a no-op. This is the most common "I added blur and
nothing happened" cause.

### Fallback pattern with `@supports`
```css
.header { background-color: hsl(0 0% 100% / 0.95); } /* opaque-ish default */

@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .header {
    background-color: hsl(0 0% 100% / 0.6);
    -webkit-backdrop-filter: blur(12px) saturate(140%);
            backdrop-filter: blur(12px) saturate(140%);
  }
}
```

The fallback bumps opacity high enough that legibility is preserved when
blur isn't available. Don't ship a 0.4 opacity background without a
fallback — old browsers will render unreadable text over arbitrary content.

Refs:
- https://caniuse.com/css-backdrop-filter
- https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- https://www.joshwcomeau.com/css/backdrop-filter/
- https://www.braydoncoyer.dev/blog/build-a-glassmorphic-navbar-with-tailwindcss-backdrop-filter-and-backdrop-blur

---

## 3. Background opacity values — typical ranges

Empirical values used by reference sites:

| Site         | Light bg approx                   | Blur radius |
|--------------|-----------------------------------|-------------|
| apple.com    | `rgba(255,255,255,0.7)`           | ~20px       |
| stripe.com   | `rgba(255,255,255,0.8)` on scroll | ~20px       |
| linear.app   | very dark `rgba(8,9,12,0.72)`     | ~24px       |
| vercel.com   | `rgba(0,0,0,0.5)` (dark theme)    | ~16–20px    |

Working ranges:
- **Light theme:** background alpha 0.6–0.8, blur 8–20px.
- **Dark theme:** background alpha 0.55–0.75, blur 12–24px. Dark themes
  generally need slightly more blur because the eye is more sensitive to
  variation through dark glass.
- A faint border or inset shadow on the bottom edge
  (`border-b border-white/10` / `shadow-sm`) defines the header silhouette
  without an opaque bar.
- Comeau recommends layering `saturate(140%)` and/or `brightness(120%)` on
  top of `blur()` to avoid the muddy / desaturated look that pure blur
  produces.

Tailwind utility equivalents:
- `bg-white/70 backdrop-blur-md backdrop-saturate-150`
- `dark:bg-neutral-900/70 dark:backdrop-blur-lg`

---

## 4. Always-on blur vs only-on-scroll

### Always-on
- Simplest. Header has the same backdrop-filter at scroll-y 0 and scroll-y
  10000.
- Works well when the page has imagery / colour beneath the header — the
  effect is visible immediately.
- On a plain white page the header essentially looks the same as a
  non-blurred translucent bar at the top — visually pointless until the
  user scrolls, but harmless.

### Only-on-scroll (transparent → frosted)
- Header is fully transparent (or borderless) at scroll-y 0, gains the
  frosted background once the user has scrolled past some threshold (often
  ~8–32px).
- This is the Apple / Stripe pattern. It lets a hero image bleed all the
  way under the header at the top of the page.
- Implementation cost: needs a scrolled/not-scrolled boolean.

### Triggering the boolean

Three approaches, ordered by cost:

**A. CSS-only with a sentinel + `:has()`** — works in modern browsers but
support for `:has()` against scroll-related state is limited. Skip for now.

**B. Alpine `@scroll.window` listener** — small and plenty fast for a
header threshold:
```html
<header
  x-data="{ scrolled: false }"
  @scroll.window="scrolled = window.scrollY > 8"
  :class="scrolled
    ? 'bg-white/70 backdrop-blur-md shadow-sm'
    : 'bg-transparent'"
  class="sticky top-0 z-40 transition-colors duration-200"
>
  ...
</header>
```
Pros: trivial, no observer plumbing, integrates with existing Alpine usage.
Cons: scroll handler runs on every scroll frame. For a single boolean
comparison this is fine — measured cost is sub-millisecond — but throttle
or debounce if more state is added.

**C. IntersectionObserver with a 1px sentinel** — best for performance
purity (callback only fires on threshold crossing, not every frame):
```html
<div id="header-sentinel" class="h-px"></div>
<header id="site-header" class="sticky top-0 z-40 ...">...</header>

<script>
  const sentinel = document.getElementById('header-sentinel');
  const header = document.getElementById('site-header');
  new IntersectionObserver(([entry]) => {
    header.classList.toggle('is-scrolled', !entry.isIntersecting);
  }).observe(sentinel);
</script>
```
Pros: asynchronous, off main thread, no scroll listener at all.
Cons: more moving parts; sentinel must live above the header in DOM order.
Smashing's "Building a Dynamic Header" article walks through this.

For our use case (single boolean) Alpine `@scroll.window` is the pragmatic
pick; reach for an IntersectionObserver if we ever need multiple scroll
zones.

Refs:
- https://www.smashingmagazine.com/2021/07/dynamic-header-intersection-observer/
- https://developer.chrome.com/blog/sticky-headers/
- https://dev.to/jenc/a-stab-at-performance-testing-with-intersection-observer-and-scroll-events-173k
- https://hweb87.wordpress.com/2021/09/14/hyva-how-to-create-a-fixed-header-on-scroll-using-alpinejs-and-tailwind-css/

---

## 5. Avoiding content-jump on transparent → frosted transitions

When the header transitions from `bg-transparent` to `bg-white/70`, the box
size mustn't change. Common causes of jump:

- Adding/removing border or shadow that affects layout: use **`box-shadow`
  not `border`** for the on-scroll edge, or keep a transparent border at
  rest (`border-b border-transparent` → `border-white/20`) so width stays
  identical.
- Adding/removing padding when "shrinking" the header on scroll: animate
  with `transform: scaleY(...)` or transition `height`/`padding` knowing
  that this will reflow children — generally avoid shrinking unless there's
  a clear UX win.
- Changing font size: same problem; compose the resting and scrolled states
  with the same metrics where possible.

Use `transition-colors` (or explicit `transition-[background-color,backdrop-filter]`)
rather than a blanket `transition-all`, which animates layout properties
and produces stutter.

---

## 6. `scroll-margin-top` / anchor offset

A sticky / fixed header covers the top of any element targeted by a hash
link (`#section`). Fix:

```css
:target { scroll-margin-top: 5rem; } /* matches header height + a little air */
```

Or globally via the scroll container:
```css
html { scroll-padding-top: 5rem; }
```

- `scroll-padding-top` on the scroll container is usually preferable for a
  site-wide header because it covers programmatic scroll, focus scroll
  (`element.scrollIntoView()`) and tab navigation, not just `:target`.
- Works in all evergreen browsers since ~2019.
- iOS Safari historically had quirks outside scroll-snap contexts; current
  versions are fine.

Tailwind: `scroll-pt-20` on `<html>` (configure via `@apply` or in a base
layer).

Refs:
- https://css-tricks.com/fixed-headers-and-jump-links-the-solution-is-scroll-margin-top/
- https://gomakethings.com/how-to-prevent-anchor-links-from-scrolling-behind-a-sticky-header-with-one-line-of-css/

---

## 7. Mobile considerations

### Address bar behaviour
- Mobile Safari and Chrome collapse / expand the URL bar on scroll. With a
  `position: sticky; top: 0` header and a `100vh` hero, the hero will jump
  in height as the bar hides/shows. Use `100dvh` (dynamic viewport height)
  for hero heights to avoid this.
- The header itself is fine — `top: 0` resolves to the visible viewport top
  in both states.

### Performance of `backdrop-filter` on low-end devices
- `backdrop-filter` is a compositor effect. It's generally cheap on modern
  GPUs but **can be expensive on low-end Android** when combined with:
  - large blur radii (>20px),
  - large blurred areas (full-width header is fine; full-screen overlay
    less so),
  - non-rectangular masks / `border-radius` + transforms.
- Keep the blur radius modest (8–16px) on mobile. Optionally reduce on
  small screens: `class="backdrop-blur-sm md:backdrop-blur-md"`.
- Avoid `filter` (non-backdrop) on the header itself — that promotes the
  whole thing and its descendants to their own layer and is more costly.

### Touch / safe area
- iOS notch / dynamic island: header should respect
  `padding-top: env(safe-area-inset-top)` if it visually starts at viewport
  top in standalone PWA mode. Not strictly needed for an in-browser site.

Refs:
- https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- https://www.joshwcomeau.com/css/backdrop-filter/

---

## 8. Accessibility

### Contrast through translucent header
- WCAG 2.2 still requires 4.5:1 for body text and 3:1 for large text /
  meaningful UI affordances. With a 60–70% opaque header, the *worst-case*
  background is whatever is scrolling underneath — which is unknown.
- Two reliable tactics:
  1. Bump opacity higher (0.75–0.85) so the header colour dominates the
     blur regardless of what's behind it.
  2. Use a strong border-bottom or shadow to give nav items a defined
     surface, so the contrast contract is between text and the (mostly
     opaque) header bg, not between text and arbitrary page content.
- Verify nav-link colour against the *resting* header background AND a
  reasonable worst case (e.g. dark photo) using a contrast checker.

### `prefers-reduced-transparency`
Users on Windows / macOS / iOS can opt into reduced UI transparency. We
should respect it:

```css
@media (prefers-reduced-transparency: reduce) {
  .header {
    background-color: hsl(0 0% 100% / 0.98);
    -webkit-backdrop-filter: none;
            backdrop-filter: none;
  }
}
```

Support note: Chrome/Edge 118+, Firefox behind a flag, Safari not yet — so
this is a progressive enhancement, not a substitute for sane defaults.

### `prefers-reduced-motion`
If we animate the header (slide-in, scale, opacity fade on the
transparent → frosted transition), wrap the transition in:
```css
@media (prefers-reduced-motion: reduce) {
  .header { transition: none; }
}
```

### Focus visibility
Sticky header must not cover focused content. `scroll-padding-top` on
`<html>` handles tab-induced scroll automatically.

### Skip link
A sticky header is more obstructive than a static one for keyboard users.
A `Skip to main content` link that appears on focus is best practice
regardless, and especially relevant here.

Refs:
- https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency
- https://developer.chrome.com/blog/css-prefers-reduced-transparency
- https://blog.logrocket.com/using-css-prefers-reduced-transparency-light-dark/

---

## 9. Z-index discipline

Suggested layering scale (relative ordering matters more than absolute
numbers):

| Layer                    | z-index |
|--------------------------|---------|
| Page content             | auto    |
| Sticky in-page subheaders| 10      |
| **Site header**          | **40**  |
| Dropdowns from header    | 50      |
| Toasts / flash messages  | 60      |
| **Modals / dialogs**     | **70**  |
| Modal-spawned popovers   | 80      |
| Dev tools / debug banners| 9000+   |

Rules:
- The **header sits *below* modal overlays**. A modal that doesn't cover
  the header is broken — focus trapping fails, the user can scroll, and
  the backdrop doesn't actually back-drop.
- Native `<dialog>` (with `showModal()`) renders in the top layer and
  trumps any z-index — no special handling needed.
- Header dropdowns must be above the header itself but below modals.
- Tailwind defaults: `z-40` for header, `z-50` for dropdowns, native
  `<dialog>` for modals (preferred), or `z-70` if using a custom modal.

---

## 10. Reference implementations to crib from

- **apple.com** — canonical frosted header. Always-on blur, very subtle
  (~0.7 alpha, ~20px blur). No transparent-at-top trick on the homepage.
- **stripe.com** — transparent at top, frosts on scroll. Smooth
  transition; uses a thin bottom border that fades in.
- **linear.app** — dark frosted header with extra `saturate` filter. Good
  example of dark-theme glassmorphism.
- **vercel.com** — dark, transparent at top, frosts on scroll. Adds a
  hairline `1px` bottom border in `rgba(255,255,255,0.1)` only when
  scrolled.
- **Tailwind UI navbars** — both the marketing and application shell
  examples ship the `bg-white/75 backdrop-blur` pattern; good template
  for default opacity/blur values.
- **CodePen — KevinBatdorf "Add Shadow to Header on Scroll"** — minimal
  Alpine.js `@scroll.window` recipe.

Refs:
- https://tw-elements.com/docs/standard/extended/sticky-header/
- https://codepen.io/KevinBatdorf/pen/JjGporG
- https://github.com/markmead/alpinejs-sticky

---

## 11. Quick-reference snippet (illustrative — not the implementation)

```html
<header
  x-data="{ scrolled: false }"
  @scroll.window.passive="scrolled = window.scrollY > 8"
  class="sticky top-0 z-40 transition-colors duration-200
         border-b border-transparent
         supports-[backdrop-filter]:backdrop-blur-md
         supports-[backdrop-filter]:backdrop-saturate-150"
  :class="scrolled
    ? 'bg-white/70 dark:bg-neutral-900/70 border-black/5 dark:border-white/10 shadow-sm'
    : 'bg-transparent'"
>
  <!-- nav contents -->
</header>
```

```css
/* base layer */
html { scroll-padding-top: 5rem; }

@media (prefers-reduced-transparency: reduce) {
  header.sticky {
    background-color: rgb(255 255 255 / 0.98);
    -webkit-backdrop-filter: none;
            backdrop-filter: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  header.sticky { transition: none; }
}
```

This is for reference only — the actual header design lives in the spec.

---

## 12. Summary checklist for the spec / implementation phase

- [ ] Use `position: sticky; top: 0;` unless an overflow ancestor forces
      `fixed`.
- [ ] Translucent background colour (alpha ~0.6–0.8) + `backdrop-filter:
      blur(...) saturate(...)`, with `-webkit-` prefix.
- [ ] Wrap blur values in `@supports` / Tailwind `supports-[backdrop-filter]:`
      and provide a near-opaque fallback.
- [ ] Decide always-on vs only-on-scroll. If on-scroll, prefer Alpine
      `@scroll.window.passive` for our scale; reach for IntersectionObserver
      if multiple scroll zones appear.
- [ ] No layout-affecting properties in the on-scroll transition. Animate
      `background-color`, `border-color`, `box-shadow`, `backdrop-filter`.
- [ ] `scroll-padding-top` on `<html>` matching header height for anchor
      links.
- [ ] Handle `prefers-reduced-transparency` and `prefers-reduced-motion`.
- [ ] Verify contrast at resting opacity AND against a worst-case
      background.
- [ ] Z-index: header `z-40`; dropdowns `z-50`; modals above header.
- [ ] Skip-to-main-content link, especially given the header obstructs the
      top of the page.
- [ ] Mobile: cap `backdrop-blur` at `md` size, use `100dvh` for any
      adjacent hero, test on a low-end Android.

---

## All references

- https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- https://caniuse.com/css-backdrop-filter
- https://www.joshwcomeau.com/css/backdrop-filter/
- https://css-tricks.com/almanac/properties/b/backdrop-filter/
- https://www.braydoncoyer.dev/blog/build-a-glassmorphic-navbar-with-tailwindcss-backdrop-filter-and-backdrop-blur
- https://tailwindcss.com/docs/backdrop-filter-blur
- https://tw-elements.com/docs/standard/extended/sticky-header/
- https://www.kevinpowell.co/article/positition-fixed-vs-sticky/
- https://www.browserstack.com/guide/sticky-vs-fixed
- https://blog.logrocket.com/ux-design/sticky-vs-fixed-navigation/
- https://dev.to/luisaugusto/stop-using-fixed-headers-and-start-using-sticky-ones-1k30
- https://css-tricks.com/fixed-headers-and-jump-links-the-solution-is-scroll-margin-top/
- https://gomakethings.com/how-to-prevent-anchor-links-from-scrolling-behind-a-sticky-header-with-one-line-of-css/
- https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-transparency
- https://developer.chrome.com/blog/css-prefers-reduced-transparency
- https://blog.logrocket.com/using-css-prefers-reduced-transparency-light-dark/
- https://www.smashingmagazine.com/2021/07/dynamic-header-intersection-observer/
- https://developer.chrome.com/blog/sticky-headers/
- https://dev.to/jenc/a-stab-at-performance-testing-with-intersection-observer-and-scroll-events-173k
- https://hweb87.wordpress.com/2021/09/14/hyva-how-to-create-a-fixed-header-on-scroll-using-alpinejs-and-tailwind-css/
- https://codepen.io/KevinBatdorf/pen/JjGporG
- https://github.com/markmead/alpinejs-sticky
