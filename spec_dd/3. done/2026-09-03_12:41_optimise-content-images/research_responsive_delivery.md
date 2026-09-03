# Research: responsive image delivery in the course player

Scope: the front end only — what the browser is given for `content_engine.File` images rendered
through `c-picture` / `c-image-grid`, and what sizes the player genuinely needs. Backend rendition
generation is a sibling worker's territory; this file assumes renditions exist and asks what widths
they should be and how the templates should use them.

Constraint carried through every recommendation below: **`content_save` stays simple, no new
background services or tasks** — a small, fixed set of renditions produced in-process (Pillow is
already a dependency, per `pyproject.toml:37`), not an on-demand/CDN resizer.

## 1. What the player actually renders — measured from the templates

### 1.1 Inline thumbnail (`c-picture`, standalone)

`freedom_ls/content_engine/templates/cotton/picture.html:34` wraps the `<img>` in
`<c-media-card class="max-w-xl mx-auto m-4">`. Tailwind's default scale puts `max-w-xl` at
`36rem` = **576px** CSS (Tailwind default spacing scale — this is a fixed, non-configurable value
in this codebase; there is no `tailwind.config` override of `xl` visible in the repo). The image
itself is `w-full h-auto` inside that card, so **576px CSS is a hard cap regardless of viewport**:
widening the browser past ~608px (576 + the card's own `m-4` margins) does not grow the image
further. Below that, the image shrinks to `100vw − page/shell padding − card margins`.

The content column itself (`c-page` in `freedom_ls/base/templates/cotton/page.html:8-10`, default
`width="wide"` → `max-w-7xl` = 1280px, used flush in `course_topic.html:8`) is wider than 576px on
desktop even after the docked TOC sidebar (`--sidebar-width: 20rem` = 320px,
`freedom_ls/learner_interface/templates/learner_interface/_course_base.html:41`) and its
`lg:gap-12` gutter are subtracted — so the sidebar is irrelevant to this component's width; the
card's own `max-w-xl` is always the binding constraint on tablet/desktop.

- **Practical CSS width range: ~330–576px.** Mobile phones (360–430px viewport, minus page and
  card margins) render at ~330–400px CSS. Everything ≥ ~610px viewport renders at the 576px cap.

### 1.2 Lightbox (`<dialog>`)

`picture.html:94` — `<div class="max-w-4xl w-full max-h-[70dvh] ...">`. `max-w-4xl` = `56rem` =
**896px CSS**, and the image inside is `w-full object-contain` (`picture.html:98`), so it can grow
to that width — but only for images whose aspect ratio lets them hit the width cap before the
`max-h-[70dvh]` height cap does. On a typical laptop viewport (~800–900px tall), `70dvh` ≈
560–630px CSS; a landscape screenshot or wide diagram will hit the 896px width cap first, a
portrait photo or a tall annotated screenshot will be height-bound and render narrower.

- **Practical CSS width range: up to 896px**, reached only by wide-aspect images on
  short-to-medium viewports. Most images will render somewhat narrower than that in the lightbox.

### 1.3 Grid tiles (`c-image-grid`)

`freedom_ls/content_engine/templates/cotton/image-grid.html:21-27` strips `c-picture`'s own
`max-w-xl`/`mx-auto`/`my-6` via `[&_figure]:max-w-none!` so each figure fills its grid cell. Grid
breakpoints: **all three column counts (2/3/4) collapse to a single column below the `sm` (640px)
breakpoint** — `grid-cols-1` is the un-prefixed base — then `sm:grid-cols-2`, and only the
`columns="4"` variant additionally goes to `lg:grid-cols-4` (`columns="3"` goes to
`lg:grid-cols-3`; `columns="2"` stays 2-up from `sm` upward).

Given the markdown content column (~800–850px net of the docked sidebar on desktop `lg`, narrower
below `lg` where the sidebar is a slide-over rather than docked):

| columns= | viewport tier | approx. cell CSS width |
|---|---|---|
| any | < 640px (mobile) | ~330–400px (1-col, ≈ same as §1.1 mobile) |
| 2 | ≥ 640px | ~390–420px |
| 3 | 640–1023px (falls back to 2-col) | ~390–420px |
| 3 | ≥ 1024px | ~250–270px |
| 4 | 640–1023px (falls back to 2-col) | ~390–420px |
| 4 | ≥ 1024px | ~185–200px |

- **Practical CSS width range across all grid configurations: ~185–420px.** The grid never asks
  for more than the standalone thumbnail's 576px cap; it only asks for *less*.

### 1.4 Combined rendered-width envelope

Across every context the CSS-pixel envelope the player ever needs is **~185px to ~896px**, with
576px (thumbnail cap) and 896px (lightbox cap) as the two structurally-fixed upper bounds, and the
grid supplying everything smaller.

## 2. From CSS pixels to a rendition shortlist

### 2.1 DPR: why 3x is not the right multiplier here

Naively multiplying every CSS-pixel bound by 1x/2x/3x device-pixel ratio gives up to
896 × 3 = 2688px for the lightbox alone. That is the wrong number to design for. There is a
long-documented tension in the responsive-images spec between "correctly" serving 3x assets to
high-DPR phones and the resulting byte cost, discussed at length in the WHATWG HTML issue tracker,
where the reporter notes correctly-implemented `srcset`/`sizes` causes "high-resolution smartphone[s
to] download larger image files to meet screen resolution demands" and records that WordPress
(≈third of the web) deliberately **caps generated image width at 1024px** specifically to avoid
this, and proposes DPR-capping (e.g. treating a 4x display as 2x) as a mitigation —
https://github.com/whatwg/html/issues/4421 (accessed 2026-09, ongoing spec discussion, no final
resolution but the WordPress 1024px cap is a real, shipped precedent). The general finding —
diminishing perceptual return from 2x to 3x on larger images, at roughly double the bytes for the
extra step — is echoed elsewhere in the responsive-images ecosystem (e.g. `unpic-img`'s issue
"Cap images for > 2x DPR screens", https://github.com/ascorbic/unpic-img/issues/202). FLS course
images are informational (screenshots, diagrams, annotated photos), not product/detail photography
where per-pixel fidelity matters — the class of image these sources agree benefits least from 3x.

**Recommendation: cap the DPR multiplier at 2x.** Do not generate a 3x rendition.

### 2.2 The shortlist

Applying the 2x cap to the two structural upper bounds and the grid's smaller cells:

| context | CSS width | × 2 DPR | nearest bucket |
|---|---|---|---|
| grid, 4-col, desktop | ~200px | 400px | **400** |
| grid, 3-col, desktop / mobile 1-col | ~270–400px | 540–800px | **800** |
| thumbnail cap / grid 1-col tablet | ~576px | 1152px | **1200** |
| lightbox cap (wide images) | ~896px | 1792px | **1600** |

**Shortlist: 400w, 800w, 1200w, 1600w** — four renditions, `webp` only (see §3.3), generated
in-process at `content_save` time alongside the existing full-size `File`. This is a genuinely
small, fixed set: no per-request resizing, no arbitrary widths, nothing that needs a CDN image
service.

Notes on the rounding:
- 1600 is ~11% under the theoretical 1792px (896 × 2) top bound. That is an intentional trade —
  going to 1792/1800 buys a rarely-reached edge case (a wide-aspect image on a 2x display, viewed
  in the lightbox on a viewport short enough to hit the width cap rather than the height cap) at
  the cost of a fifth bucket. Given §2.1's diminishing-returns argument, 1600 is judged sufficient;
  raise to 1800 only if user testing on 2x tablets shows visible upscaling artefacts in the
  lightbox.
- The **original uploaded file stays as-is** (untouched, full quality) as the top of the `srcset`
  ladder for very old browsers that ignore `srcset` entirely (they fall back to the plain `src`,
  which should point at the smallest sensible rendition — see §3.1 — not the 5 MB original) and as
  a safety net for any future "download original" / print use case. It should never be the `src`
  fallback target for `<img>` without `srcset` support, or non-`srcset`-aware browsers get the full
  5 MB.
- 400w also happens to satisfy 1x for the mobile single-column contexts (~330–400px), so it is not
  a wasted bucket even outside the grid.

## 3. The two-image problem

`c-picture` currently points **both** the inline `<img>` (`picture.html:35`) and the lightbox
`<img>` (`picture.html:95`) at the same `file_obj.file.url` — the original, full-size file. A
learner who never opens the lightbox (the majority case for illustrative/reference images) still
pays for the full original on page load, and even a learner who *does* open it pays for it twice:
once decoded at 576px CSS in the thumbnail (wasted resolution) and once again, from cache, at up to
896px CSS in the lightbox.

### 3.1 Recommended split

- **Inline `<img>`**: real `srcset`/`sizes` scoped to the thumbnail's own envelope
  (400/800/1200 — 1600 is never useful here since the card caps at 576 CSS px, i.e. ≤1152 device
  px). `loading="lazy"` (already present) is correct here, since the thumbnail is basically always
  below the fold on a course topic page below the LCP element (see §4).
- **Lightbox `<img>`**: do **not** eagerly point it at a large asset in the initial HTML. Two
  concrete options, both compatible with "no new background service":

  **Option A — defer the `src` until the dialog opens (recommended).** Leave the lightbox `<img>`
  with no `src` (or a 1x1 transparent placeholder) in the server-rendered HTML, and set
  `src`/`srcset` from Alpine's existing `x-data="contentLightbox"` controller
  (`freedom_ls/content_engine/static/content_engine/js/alpine-components.js`) in the same `open()`
  method that already calls `showModal()`. This means the large rendition (1200/1600 bucket) is
  never fetched by a learner who doesn't open the lightbox — it costs zero bytes until requested.
  To avoid a flash of empty space while the larger image loads: reuse the thumbnail's already-cached
  `800` bucket as a low-res placeholder shown immediately (it is already in the browser cache from
  the thumbnail decode, assuming inline and lightbox share a bucket at that width), swap to the
  larger asset once its `load` event fires. This is the standard "blur-up" / low-quality-placeholder
  pattern, implementable here with plain Alpine (`x-data`, `@load`) — no new library.

  **Option B — one middling size for both (simpler, worse for the common case).** Point both
  `<img>`s at the same `1200` bucket. Simpler (one `<img>` markup, no JS swap), but every thumbnail
  view now downloads a 1200px-wide asset even though the thumbnail only ever renders at ≤576 CSS px
  (≤1152 device px at 2x) — roughly 2x the bytes the thumbnail alone needs, on every page view,
  to save a JS-driven swap that only fires when the lightbox is opened (a minority interaction).

  **Recommendation: Option A.** It is a small, template-local change (the Alpine controller
  already exists and already owns `open()`/`close()`), it costs nothing extra at `content_save`
  time (same four buckets serve both contexts), and it removes the wasted download for the common
  no-lightbox case entirely rather than just shrinking it.

### 3.2 `srcset`/`sizes` for each context

Given the shortlist, the `sizes` attribute needs to describe each context's *actual* rendered
width, not a guess — a wrong `sizes` value defeats `srcset` entirely (browser picks a candidate
sized for the wrong slot; documented as one of the most common `srcset`/`sizes` implementation
errors — e.g. https://renderlog.in/blog/srcset-sizes-responsive-images-explained/ and
https://www.liip.ch/en/blog/things-you-should-know-about-responsive-images, both accessed
2026-09; treat as general confirmation of well-known behaviour rather than novel findings).

- **Inline thumbnail** (`picture.html`, standalone): the card caps at 576px CSS regardless of
  viewport once the viewport is wide enough, and is otherwise `100vw` minus fixed margins. `calc()`
  inside `sizes` is long-standing, well-supported syntax (part of the sizes grammar since the
  original Responsive Images spec; `calc(100vw - 9rem - 200px)`-style values are a documented
  pattern per https://css-tricks.com/a-guide-to-the-responsive-images-syntax-in-html/). Recommended:
  `sizes="(min-width: 40rem) 576px, calc(100vw - 4rem)"` — the `4rem` accounts for the card's `m-4`
  margins on both sides plus any shell padding; the exact constant needs checking against rendered
  DOM, not derived from Tailwind classes alone. Avoid `min()`/`max()` functions *inside* `sizes`
  specifically — support for CSS math functions in that exact attribute grammar is less
  consistently documented than plain `calc()` (no single authoritative caniuse entry was found for
  "min() inside the `sizes` attribute" specifically); a media-query-conditional list with `calc()`
  is the safe, well-established choice.
- **Grid tiles** (`c-image-grid`): `sizes` must vary by `columns=`, matching the same breakpoints
  as the grid's own Tailwind classes (`sm:grid-cols-2`, `lg:grid-cols-{3,4}`). Since `c-image-grid`
  is a layout wrapper around `c-picture` children that don't know their own column count, the
  `columns` value needs to be threaded down to each child's `sizes` string (a prop-passing change,
  not a research question — flagging it for the planning stage). E.g. for `columns="4"`:
  `sizes="(min-width: 64rem) 25vw, (min-width: 40rem) 50vw, 100vw"` (approximating the grid's own
  gaps; exact `vw` fractions should subtract gap/padding the same way, or accept the small
  over-fetch from ignoring gaps — a few px of error here is cheap relative to bucket granularity).
- **Lightbox**: since §3.1 defers loading to `open()`, `sizes` is less load-bearing (there's no
  competing viewport at markup time), but should still say `(min-width: 56rem) 896px, 100vw` so the
  swap-in picks the right bucket immediately rather than the largest one by default.

### 3.3 `<picture>` + `type="image/webp"`/`image/avif` — still needed in 2026?

- **AVIF**: ~94.7–95.5% global support per caniuse (accessed 2026-09,
  https://caniuse.com/avif) — Chrome 85+ (2020), Firefox 93+ (2021), Safari 16.4+ (March 2023,
  the last major holdout), Edge 121+. The remaining gap is pre-16.4 Safari and legacy/niche
  browsers.
- **WebP**: supported since Safari 14 (2020) — universally safe at this point, no research needed;
  every browser that can reach an FLS course player supports WebP.
- Given WebP alone already clears effectively every real learner browser, and AVIF's marginal
  compression gain over WebP is smaller than WebP's gain over JPEG, **a single `<picture>` source
  step (WebP) with the original format as the plain `<img src>` fallback is sufficient** — a
  three-tier `<picture>` (AVIF → WebP → original) is not obviously worth the extra encode step
  and template complexity for a "keep `content_save` simple" project, but is a defensible upgrade
  later since Pillow (already a dependency) can encode AVIF. **Recommend WebP-only for the first
  cut**, with AVIF flagged as a possible follow-up once WebP is shipped and measured, not a launch
  blocker.
- If `<picture>` is used, each `<source>` needs its own `srcset`/`sizes` (the `sizes` value is
  shared across all sources for one `<picture>`, only `srcset`/`type` differ) — same buckets, same
  `sizes` strings as §3.2, just repeated per format.

## 4. Layout stability and loading

- **CLS / intrinsic size**: neither `<img>` in `picture.html` sets `width`/`height`
  (`picture.html:35-38`, `:95-98`), and `File` (`freedom_ls/content_engine/models/files.py`) stores
  no dimensions — nothing to source them from today. Missing `width`/`height` means the browser
  can't reserve layout space before the image decodes, causing a shift as content re-flows once it
  loads — the standard CLS failure mode
  (https://web.dev/articles/browser-level-image-lazy-loading, accessed 2026-09-02: "A lazily loaded
  image must always have defined dimensions using width and height attributes. This prevents
  potential issues with the CLS metric.") **`File` needs width/height fields captured at
  `content_save` time** (a model/backend concern, flagging for the sibling backend research, but
  it's a hard prerequisite for fixing CLS on this component — `object-contain`/`h-auto` CSS alone
  doesn't give the browser an aspect ratio before the image loads unless the HTML also carries
  `width`/`height`, which the browser uses to compute intrinsic `aspect-ratio` automatically since
  Chrome 84/Firefox 71/Safari 15 — this is now a well-established behaviour, not new guidance).
- **`loading="lazy"`**: already used on the inline `<img>` (`picture.html:38`). Correct for this
  component in the common case — course topic images are essentially always below an
  above-the-fold text/heading block, not the page's LCP element, so lazy-loading them is the right
  default and does not fight the "never lazy-load the LCP image" rule
  (https://web.dev/articles/browser-level-image-lazy-loading, https://unlighthouse.dev/learn-lighthouse/lcp/lcp-lazy-loaded,
  both accessed 2026-09-02 — "don't lazy-load images that are likely to be in-viewport when the
  page loads, especially LCP images"). The one case where it actively hurts: a topic whose content
  opens with an image as the very first element (no heading/paragraph above it) — that image *is*
  likely the LCP candidate and should be `loading="eager"` (the HTML default) with
  `fetchpriority="high"` instead. This is a per-instance authoring decision (`c-picture` would need
  an opt-out, e.g. a `priority` prop), not something the component can infer from the template
  alone — flagging for planning rather than resolving here.
  - The lightbox `<img>` should **not** carry `loading="lazy"` at all once §3.1 (Option A) is
    applied — it has no `src` until `open()` sets one, so native lazy-loading semantics don't apply
    and would only add a second, redundant deferral on top of the JS-driven one.
- **`decoding="async"`**: ~95.7% global support per caniuse (accessed 2026-09,
  https://caniuse.com/mdn-html_elements_img_decoding — Chrome 65+/2018, Firefox 63+/2018, Safari
  11.1+/2018). Safe to add to both `<img>`s; lets the browser decode off the main thread instead of
  blocking on it, cheap and uncontroversial.
- **`fetchpriority`**: ~92.7% global support per caniuse (accessed 2026-09,
  https://caniuse.com/mdn-api_htmlimageelement_fetchpriority — Chrome/Edge 102+/2022, Firefox
  132+/2024 [late], Safari 17.2+/2023). Recommended narrowly: only on the rare LCP-candidate image
  from the previous bullet (`fetchpriority="high"`), never on the routine inline thumbnail or the
  lightbox image — "use `fetchpriority="high"` on exactly one image per page and leave the rest at
  default `auto`" is the general guidance
  (https://allahabadi.dev/blogs/frontend/fetchpriority-lcp-hero-image-priority/, accessed
  2026-09-02).

## 5. Accessibility and low bandwidth

- **Byte-cost arithmetic for the status quo**: a 5 MB original image, at typical "Slow 3G"
  throughput (~400–780 kbps, a standard DevTools/WebPageTest 3G profile), takes roughly
  **50–100 seconds** to download; at a more realistic mobile 4G rate (~5–10 Mbps), still
  **4–8 seconds** — for one image, on a page that may contain several. Compare against the
  Core Web Vitals LCP "good" threshold of **2.5 seconds** for the *entire* page
  (https://web.dev/articles/lcp, general Core Web Vitals reference). The proposed 400/800/1200/1600
  WebP buckets bring a typical course screenshot from megabytes to tens-to-low-hundreds of KB
  (WebP at reasonable quality settings is routinely 25–35% smaller than an equivalent JPEG at the
  same visual quality, and re-encoding at the *actual* rendered pixel count rather than the
  original capture resolution is the dominant saving here — most of the 5 MB is unused pixels, not
  format inefficiency).
- **Page-weight budget**: no single authoritative "the" number exists for this — treat any specific
  KB target as a policy the FLS team should choose rather than a discovered fact, since the search
  results surfaced for this were low-quality SEO content rather than primary sources. What *is*
  citable: the LCP 2.5s threshold above, and the observation that a course topic page is
  content-heavy and often has 2–4+ `c-picture`/`c-image-grid` images — so per-image weight matters
  more here than on a page with one hero image. A reasonable working target given the bucket sizes
  above: **keep the inline thumbnail rendition (800 bucket, WebP) under ~150 KB and the lightbox
  rendition (1600 bucket, WebP) under ~350 KB** for a typical photographic/screenshot image; this
  is a starting point for the backend worker's encode-quality tuning, not a hard spec.
- **`prefers-reduced-data`**: **not implemented in any shipping browser** as of 2026-09
  (MDN, https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-data, accessed
  2026-09-02 — "This feature is not supported by any user agent and its specifics are subject to
  change"; marked experimental/non-Baseline). **Do not build against it.** The related HTTP
  `Save-Data` request header (sent by some Chromium-based browsers/Data Saver modes) is a
  server-side signal FLS *could* act on later (e.g. skip the 1600 bucket, serve 800 everywhere) but
  is out of scope for a front-end-only change and would need view-level logic, not template
  changes — flagging as a possible future enhancement, not part of this recommendation.
- **Alt text / captions**: unaffected by any of the above — `c-picture` already requires `alt`
  as a documented convention (`picture.html:12-14`) and this research doesn't touch that contract.
  Worth noting only that deferring the lightbox `src` (§3.1) must not defer or drop the
  `aria-describedby`/`aria-label` wiring already present (`picture.html:69,97`) — those attributes
  are static and unaffected by the JS swap.

## Summary of concrete recommendations

1. **Rendition widths: 400w, 800w, 1200w, 1600w**, WebP, generated in-process at `content_save`
   alongside the untouched original — four buckets, DPR capped at 2x, derived directly from the
   template's own Tailwind caps (576px thumbnail, 896px lightbox) and the grid's narrower cells.
2. **Split inline vs. lightbox**: inline `<img>` gets real `srcset`/`sizes` from the shortlist and
   keeps `loading="lazy"`; lightbox `<img>` gets no `src` in the initial HTML and is populated by
   the existing `x-data="contentLightbox"` Alpine controller on `open()`, so a learner who never
   opens the lightbox never pays for the larger bucket.
3. **`<picture>`**: WebP-only source plus original-format fallback is sufficient for 2026 browser
   coverage; AVIF is a defensible later addition, not needed for launch. Add `width`/`height`
   (needs new `File` fields — flag to backend), `decoding="async"` on both `<img>`s, and
   `fetchpriority="high"` only on the rare case where a topic's image is itself the LCP candidate.

status: ok
