# Research: Sticky header with scroll-aware blur

Scope: decide whether and how to convert the FLS header (`<header class="bg-primary p-3 sm:p-4 shadow-md ...">`) into an iOS/macOS-style sticky header that hints at content scrolling beneath it.

---

## TL;DR recommendation

1. **Make the header sticky, not fixed.** Use `position: sticky; top: 0;` so it keeps its space in flow and doesn't require body padding hacks.
2. **Always-visible (not auto-hide) is the safer default for an LMS.** Auto-hide ("hide on scroll-down, show on scroll-up") only earns its complexity on long-scroll content sites; an LMS needs the nav predictably available, and the auto-hide pattern adds keyboard/focus edge cases. We can revisit if learners complain about vertical real-estate on mobile.
3. **Drop the frosted-glass effect, OR change the header background to translucent.** A `backdrop-filter: blur()` on top of an *opaque* `bg-primary` is purely decorative — the blur has nothing to filter because nothing shows through. NN/g explicitly recommends opaque, high-contrast sticky headers. If we want the iOS feel, we need to (a) switch to a translucent surface (e.g. `bg-primary/85`) and (b) verify contrast against worst-case page content.
4. **If we go translucent, only blur once scrolled.** At `scrollY === 0` keep the header fully solid (matches the page top, no visual seam). Once content has moved, switch to translucent + blur. Use CSS `@container scroll-state(stuck: top)` where supported, with a JS class-toggle fallback (`scrolled` class on `<header>`).
5. **Add `scroll-padding-top` to `html`** equal to the header height so anchor links and `:focus-visible` scrolls aren't hidden.
6. **Respect `prefers-reduced-motion`** by disabling any size/opacity transitions (the static stuck state is fine — it's not motion).

The opinionated short version: sticky yes, blur only if we commit to translucency, no auto-hide.

---

## 1. UX evidence — is sticky a good idea?

### Consensus

- **NN/g (sticky-headers article):** users save ~22% of navigation time with persistent headers and prefer them, even when they can't articulate why. Useful when nav/search/utility elements are needed throughout a session — true for an LMS (course nav, profile, logout).
- **NN/g caveats (load-bearing for us):**
  - Header must be **opaque and high-contrast** against content. Translucent headers "make semivisible content hard to read and frequently annoy and distract."
  - Header must be **small**: maximize content-to-chrome ratio, especially on mobile.
  - **Minimize animation.** "Stalker menu" effects (delayed slide-in) feel disruptive.
  - Conduct a real cost-benefit per product — don't add a sticky header by default.

### Mobile vertical-space cost

Common guidance (Parallel HQ, Express Jam, mobile UX writeups): a sticky header should not exceed **~10% of viewport height**, ideally **50–70px on desktop, ≤56px on mobile**. Our current header at `p-3 sm:p-4` plus content typically lands around 56–64px — borderline acceptable on a 667px iPhone SE viewport (~9–10%). Worth measuring before committing.

### Always-sticky vs auto-hide ("hide on scroll-down, show on scroll-up")

- Auto-hide gives ~100% reading area while keeping nav one upward swipe away.
- Tradeoffs:
  - Adds JS state (last scroll Y, direction, threshold) or scroll-driven CSS animation. Bram.us has a CSS-only version using `animation-timeline: scroll()` but support is still Chromium-leaning in 2026.
  - **Keyboard accessibility:** if a user tabs to a focused element while the header is hidden, the header must reappear. Easy to forget.
  - HTMX swaps that change the URL or fire `htmx:afterSwap` may leave stale state.
- **Recommendation for FLS:** skip auto-hide v1. Always-on sticky is simpler, more predictable, and the LMS context favors steady access to nav.

---

## 2. The blur effect specifically

This is the question that most affects our decision.

### When frosted glass actually earns its keep

- The header background is **translucent** (e.g. `rgba(255,255,255,0.7)` or `bg-white/70`).
- There is **visible content scrolling underneath** that benefits from being softened (so it doesn't compete with header text).
- The aesthetic suits the brand (Apple, Linear, Vercel, GitHub-on-dark all do this).

### When it's just decoration

- The header has a **solid colored background** like our `bg-primary`. `backdrop-filter: blur()` only affects pixels visible *through* the element. With `bg-primary` at full opacity, nothing is visible through → blur is a no-op cost. You'd see no difference.
- Heavy blurs (>20px) on opaque-ish surfaces still don't reveal content, but cost GPU.

### The fork in the road

We have two coherent options. Avoid the muddled middle (solid color + ineffective blur).

**Option A — Keep brand-coloured opaque header (NN/g compliant).**
- Stay with `bg-primary`.
- Add sticky + a `shadow` or `border-b` that intensifies once scrolled, so users feel separation.
- No blur, no translucency. Works in every browser, fastest, most accessible.

**Option B — iOS-style translucent + blur.**
- Switch to `bg-primary/85` (or a dedicated `bg-surface/80`) plus `backdrop-blur-md saturate-150`.
- Verify contrast of header text/icons against a worst-case page background (light hero image, dark theme, etc.). Likely needs `bg-primary/90+` for AA.
- Blur should be **off at scrollY 0** (header sits flush with page top — no visible seam), **on once scrolled**.

Option A is the safe LMS choice. Option B is the brand-statement choice. The brief asks about the iOS feel, so the rest of this doc assumes B is on the table — but we should make the call deliberately.

---

## 3. Technical approaches

### `position: sticky` vs `position: fixed`

| | sticky | fixed |
|---|---|---|
| Stays in document flow | yes | no — pulled out, body needs `padding-top` |
| Container-scoped | yes (sticks within parent's scroll container) | no — viewport-relative |
| Performance | slightly better; no compositor layer required for non-stuck state | always its own layer |
| Anchor-link math | trivial (`scroll-padding-top: var(--header-h)`) | trivial |
| Quirks | breaks if any ancestor has `overflow: hidden` or a transform — easy to trip on | none, but layout shift on add/remove |

**Use `position: sticky`.** Document-flow preservation is worth more than the marginal differences. Audit our base template ancestors for `overflow` / `transform` traps before shipping.

### `backdrop-filter: blur()`

- **2026 support:** ~92% global. Chrome/Edge ≥76/79, Firefox ≥103, Safari full (Safari <17 needs `-webkit-backdrop-filter`). Tailwind v4's `backdrop-blur-*` already emits both prefixes.
- **Fallback:** wrap in `@supports (backdrop-filter: blur(8px))` for the translucent path; in the `else` branch use a more opaque background. With Tailwind we typically just rely on the more-opaque base background being readable on its own — which is also what the accessibility "transparency-disabled" path needs.
- **Performance:**
  - Each blurred element gets its own compositor layer — expensive on low-end mobile.
  - Don't combine with frequently-repainting animations.
  - Keep blur radius modest (8–12px is enough; 20px+ buys little but costs more).
  - Can disable on small viewports if profiling shows jank.

### Should the blur only activate after scrolling past 0?

Yes. Two reasons:
1. At the top of the page there's nothing behind the header except the page background (often the same colour). Blurring the page background against itself looks dirty.
2. Users get a "the page has moved" affordance precisely when it's useful.

Implementation choices:

**CSS-only — `@container scroll-state(stuck: top)`** (Chrome 133+, ~2025–26 cross-browser rollout in progress):

```css
html { container-type: scroll-state; container-name: page; }

header { position: sticky; top: 0; background: var(--bg-primary); }

@container page scroll-state(stuck: top) {
  header {
    background: color-mix(in srgb, var(--bg-primary) 85%, transparent);
    backdrop-filter: blur(12px) saturate(150%);
    border-bottom: 1px solid color-mix(in srgb, var(--bg-on-primary) 10%, transparent);
  }
}
```

Caveat: `scroll-state` is still rolling out. Firefox/Safari support is partial as of 2026. For now treat as progressive enhancement on top of a JS fallback.

**JS fallback — class toggle on scroll:**

```html
<header x-data="{ scrolled: false }"
        x-on:scroll.window.passive="scrolled = window.scrollY > 4"
        :class="scrolled ? 'is-scrolled' : ''">
```

Then plain CSS for `.is-scrolled` matching the `@container` block above. (Alpine.js fits FLS; matches our existing patterns.)

**Avoid:** `IntersectionObserver` watching a sentinel `<div>` is the classical pattern but `scrollY > 4` is simpler and correct here since we only need a boolean "any scroll yet?".

---

## 4. Accessibility concerns

### `prefers-reduced-motion`

- The static stuck/transparent state itself is fine (no motion).
- Disable any **transitions** on `background`, `backdrop-filter`, `transform`, `height` for users who set the preference. Tailwind's `motion-reduce:` variant is the simplest path:
  ```html
  <header class="transition-[background-color,backdrop-filter] motion-reduce:transition-none">
  ```
- If we ever add auto-hide, the slide animation absolutely must respect this and snap instead.

### Colour contrast

- WCAG AA: 4.5:1 for normal text, 3:1 for ≥18pt or icons.
- Translucent headers fail this against bright/photographic content. Mitigations:
  - High base opacity (≥0.8).
  - Add `saturate(150%)` to give the blurred backdrop more colour weight (Apple does this).
  - Optionally a thin `border-b` (low-opacity) so the header has a structural edge regardless of backdrop colour.
- Test with both our light theme and any future dark theme. Test with worst-case content (course images, video poster frames).

### Keyboard focus

- Without intervention, `Tab`-ing to an element near the top of the page can scroll it under the sticky header.
- Fix with one line on the scroll container:
  ```css
  html { scroll-padding-top: var(--header-h, 4rem); }
  ```
  This affects both anchor links and programmatic scroll-to-focused-element.
- Vispero ("Prevent focused elements from being obscured by sticky headers") confirms `scroll-padding-top` is the expected modern fix.

---

## 5. Common pitfalls

1. **Anchor links hidden behind sticky header.** Solved by `scroll-padding-top` on `html` (preferred) or `scroll-margin-top` on individual targets. Use a CSS variable so it tracks header height changes (e.g. mobile vs desktop padding).
2. **Mobile virtual keyboard.** When the keyboard opens on iOS Safari, `position: sticky` plus `top: 0` can render the header inside the keyboard-shrunken viewport correctly, but `position: fixed` historically did not. Another reason to prefer sticky.
3. **Layout shift when blur turns on.** If the header changes from solid to translucent, declared height stays the same (no shift), but a `border-b` appearing on the stuck state can shift content by 1px. Use `box-shadow: inset 0 -1px 0 ...` or reserve the border via `border-b border-transparent` from the start.
4. **HTMX swaps and scroll restoration.** `hx-swap` defaults to scrolling the target into view. For full-page swaps using `hx-boost`, scroll position can jump unexpectedly. The header itself is fine (it stays sticky on whatever scroll position results), but be aware that any "scrolled" class we set via JS may need to be re-evaluated on `htmx:afterSwap`. With Alpine and a `window.scroll` listener this is automatic. With CSS `@container scroll-state` it's also automatic.
5. **Ancestors with `overflow: hidden` or `transform`.** Will silently break `position: sticky`. Audit `base.html` and any wrapper containers.
6. **z-index battles.** Sticky headers need a z-index above content but below modal overlays. Pick a value (`z-40` is Tailwind's modal-adjacent default — use `z-30` for header, reserve `z-50+` for modals).

---

## 6. Reference implementations

- **Apple.com** — global nav: `position: sticky`, `backdrop-filter: saturate(180%) blur(20px)`, semi-transparent surface. Becomes solid in dark mode at smaller breakpoints. Uses progressive blur in some product hero areas (multiple stacked masks for a soft fade).
- **GitHub** — uses opaque dark header, no backdrop blur on the main app chrome. Implies they prioritize NN/g-style contrast over decoration. Worth noting because their UX is functional like ours.
- **Linear / Vercel** — translucent + `backdrop-blur-lg` + low-opacity bottom border, on light surfaces. Both flip background colours under `prefers-color-scheme: dark`. Both keep blur permanent (don't gate on scroll position) — they get away with it because the page background under the header already matches.
- **iOS / macOS native** — progressive blur (multi-stop mask) and "vibrancy" (blur + saturate boost). Apple Music/Photos use a stronger effect when content has scrolled under the bar; the bar is flat/transparent at top.

### Tailwind v4 sticky+blur snippets to adapt

Common pattern (Linear/Vercel style):

```html
<header class="sticky top-0 z-30
               bg-white/70 dark:bg-neutral-900/70
               backdrop-blur-lg backdrop-saturate-150
               border-b border-black/5 dark:border-white/10
               supports-[backdrop-filter]:bg-white/60">
```

Brand-coloured variant for FLS:

```html
<header class="sticky top-0 z-30
               bg-primary/95 supports-[backdrop-filter]:bg-primary/80
               backdrop-blur-md backdrop-saturate-150
               shadow-md transition-colors
               motion-reduce:transition-none
               p-3 sm:p-4 flex justify-between items-center">
```

Add a scroll-aware variant via Alpine (`is-scrolled` class) or `@container scroll-state(stuck: top)` once we want the "transparent at top, blurred when scrolled" refinement.

---

## References

- NN/g — Sticky Headers: 5 Ways to Make Them Better — https://www.nngroup.com/articles/sticky-headers/
- Avid Core — Sticky Headers: ADA & UX — https://avid-core.com/2023/10/05/sticky-headers-digital-accessibility-user-experience/
- Parallel HQ — What is a Sticky Header? 2026 Design Guide — https://www.parallelhq.com/blog/what-sticky-header
- LogRocket — Should navigation bars be sticky or fixed? — https://blog.logrocket.com/ux-design/sticky-vs-fixed-navigation/
- Kevin Powell — position fixed vs position sticky — https://www.kevinpowell.co/article/positition-fixed-vs-sticky/
- DEV — Stop Using Fixed Headers and Start Using Sticky Ones — https://dev.to/luisaugusto/stop-using-fixed-headers-and-start-using-sticky-ones-1k30
- Bram.us — Hide header on scroll down via CSS scroll-driven animations — https://www.bram.us/2024/09/29/solved-by-css-scroll-driven-animations-hide-a-header-when-scrolling-up-show-it-again-when-scrolling-down/
- Can I Use — backdrop-filter — https://caniuse.com/css-backdrop-filter
- MDN — backdrop-filter — https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- MDN — Container scroll-state queries — https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Conditional_rules/Container_scroll-state_queries
- Chrome for Developers — CSS scroll-state() — https://developer.chrome.com/blog/css-scroll-state-queries
- una.im — Directional CSS with scroll-state(scrolled) — https://una.im/scroll-state-scrolled
- Theo Soti — Detect when sticky is actually stuck — https://theosoti.com/short/sticky-stuck-scroll-state/
- MDN — prefers-reduced-motion — https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- Scott O'Hara — Reduced Position Sticky — https://www.scottohara.me/note/2019/03/27/reduced-sticky.html
- Vispero — Prevent focused elements from being obscured by sticky headers — https://vispero.com/resources/prevent-focused-elements-from-being-obscured-by-sticky-headers/
- Markus Oberlehner — Anchor links behind sticky headers — https://markus.oberlehner.net/blog/simple-solution-for-anchor-links-behind-sticky-headers
- Go Make Things — One-line CSS for anchor links + sticky headers — https://gomakethings.com/how-to-prevent-anchor-links-from-scrolling-behind-a-sticky-header-with-one-line-of-css/
- Tailwind CSS — Backdrop Blur — https://tailwindcss.com/docs/backdrop-blur
- Braydon Coyer — Glassmorphic Navbar with Tailwind backdrop-filter — https://www.braydoncoyer.dev/blog/build-a-glassmorphic-navbar-with-tailwindcss-backdrop-filter-and-backdrop-blur
- Epic Web Dev — Glassmorphism with Tailwind — https://www.epicweb.dev/tips/creating-glassmorphism-effects-with-tailwind-css
- Devs Love Coffee — Apple progressive blur on the web — https://www.devslovecoffee.com/blog/making-apple-progressive-blur-on-web
- HTMX — hx-swap attribute — https://htmx.org/attributes/hx-swap/
- HTMX discussion — preserve scroll on swap — https://github.com/bigskysoftware/htmx/discussions/945
