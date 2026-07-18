# Research: UX & Accessibility Best Practices for Mermaid Diagrams in Course Content

Scope: informs the `mermaid-diagram-widget` idea (a `c-mermaid` cotton component). This is
idea-refinement-level research, not a spec — it surfaces the known failure modes and the
concrete patterns FLS should reuse or adapt, referencing the existing `c-equation` (KaTeX) and
`c-picture` (image spotlight) widgets as the established idioms for this codebase.

## 1. Common UX problems & complaints

Recurring complaints across GitHub issues, Obsidian forum threads and blog posts about
embedding Mermaid in reading content:

- **Wide/tall diagrams overflow their container or become illegible.** Rendered diagrams that
  are wider than their container overflow horizontally instead of scaling down, causing layout
  breakage or an unwanted horizontal scrollbar
  ([zenuml-core#308](https://github.com/mermaid-js/zenuml-core/issues/308);
  [Obsidian forum](https://forum.obsidian.md/t/mermaid-js-diagram-unreadable-due-to-large-size/23769)).
  A frequently cited cause is mismatched layout direction vs. content shape — e.g. a long
  sequential flow forced `TD` grows tall, a wide decision tree in `LR` grows wide
  ([mermaidcreator.com](https://www.mermaidcreator.com/blog/mermaid-flowchart-sizing-layout-best-practices)).
- **Fixed/awkward sizing.** Long-standing complaints that diagrams don't auto-fit their
  container or reflow ([mermaid#204](https://github.com/mermaid-js/mermaid/issues/204),
  [mermaid#838](https://github.com/mermaid-js/mermaid/issues/838)); Obsidian users report
  diagrams "not resizing to fit the page"
  ([Obsidian forum](https://forum.obsidian.md/t/mermaid-diagrams-not-resizing-to-fit-in-page/98078)).
- **No zoom/pan on unreadable diagrams.** Out of the box Mermaid diagrams have "fixed size and
  no interactivity for zooming or panning"
  ([mostlylucid.net](https://www.mostlylucid.net/blog/enhancingmermaiddiagramswithpanzoomandexport)),
  a gap requested repeatedly (e.g.
  [mermaid-live-editor#887](https://github.com/mermaid-js/mermaid-live-editor/issues/887),
  [Obsidian pan/zoom feature request](https://forum.obsidian.md/t/pan-and-zoom-on-mermaid-diagrams/65271),
  GitLab docs are "[not zoomable](https://gitlab.com/gitlab-org/gitlab-docs/-/issues/1168)").
- **Flash of raw Mermaid source before JS renders it** — readers briefly see the raw
  ` ```mermaid ` text/code block before client-side rendering swaps in the SVG.
- **Render failures show cryptic errors or nothing.** Reports of "unable to render", blank SVG
  output for some diagram types, intermittent non-rendering, and iOS-specific failures
  ([github/docs#29691](https://github.com/github/docs/issues/29691),
  [GitLab #349892](https://gitlab.com/gitlab-org/gitlab/-/issues/349892),
  [Obsidian gitGraph bug](https://forum.obsidian.md/t/mermaid-cannot-render-gitgraph/31676),
  [Obsidian iOS <17 bug](https://forum.obsidian.md/t/mermaid-graphs-not-rendering-at-all-on-ios-17/107464)).
  Async render race conditions can also make otherwise-valid diagrams fail intermittently, and
  failures are often mislabeled as "syntax error" when they're really a runtime/DOM issue
  ([fred#1210](https://github.com/ThalesGroup/fred/issues/1210)).
- **Doesn't print/export well.** Diagrams overflow the page when exported to PDF, and long
  vertical flowcharts get sliced mid-shape/mid-text across page breaks
  ([Obsidian PDF export overflow](https://forum.obsidian.md/t/prevent-mermaid-charts-from-overflowing-the-page-in-export-to-pdf/13381);
  [mermaid-cli#744](https://github.com/mermaid-js/mermaid-cli/issues/744); Obsidian also has a
  [separate PDF-export rendering bug](https://github.com/mermaid-js/mermaid/issues/6922) where
  diagrams fail entirely on `getBoundingClientRect` in headless export contexts).

## 2. Overflow & wide-diagram handling

Practices observed, in increasing order of sophistication:

1. **Horizontal scroll container (baseline, cheap).** Wrap the rendered `.mermaid > svg` in a
   container with `overflow-x: auto` (and a sane `min-width`) so the browser scrolls instead of
   clipping or breaking layout
   ([mermaidcreator.com](https://www.mermaidcreator.com/blog/mermaid-flowchart-sizing-layout-best-practices)).
   Cheap, always correct, but scroll-inside-a-reading-column is a known-poor mobile UX (thin
   hit target, easy to lose horizontally, doesn't help tiny text).
2. **Responsive/max-width SVG.** Set `max-width: 100%; height: auto` on the SVG so it shrinks to
   fit the column on any viewport. Prevents overflow but makes large diagrams' text shrink to
   illegible sizes — solves overflow, not readability.
3. **Click-to-zoom / lightbox (expand to full screen).** Let the shrunk, fit-to-column diagram
   act as a thumbnail; clicking/tapping opens a larger (ideally full-viewport) view. This is the
   pattern already built in FLS for images
   (`freedom_ls/content_engine/templates/cotton/picture.html`, Alpine `contentLightbox`
   component in `content_engine/static/content_engine/js/alpine-components.js`): a native
   `<dialog>` opened via `showModal()`, giving focus-trap, `Escape`-to-close, `inert` background
   and focus-restore "for free", plus a backdrop-click-to-close guard and scroll-lock. **This is
   directly reusable for "expand diagram"** — same trigger-button + `<dialog>` shape, swapping
   the `<img>` for the rendered SVG (and disabling `object-contain` cropping, since a diagram
   needs to stay fully legible rather than being visually cropped/filled like a photo).
4. **Pan/zoom inside the expanded view.** For diagrams too large to read even at full-viewport
   scale (e.g. big architecture diagrams, long sequence diagrams), pair the lightbox with an
   in-place pan/zoom library. `svg-pan-zoom` is the most commonly referenced library for this in
   the Mermaid ecosystem — used by Obsidian plugins
   ([obsidian-mermaid-pan-and-zoom](https://github.com/MarcoUmpierrez/obsidian-mermaid-pan-and-zoom),
   [obsidian-mermaid-zoom](https://github.com/ALXRITR/obsidian-mermaid-zoom)), a VS Code
   extension PR
   ([vscode-markdown-mermaid#295](https://github.com/mjbvz/vscode-markdown-mermaid/pull/295)),
   and a blog walkthrough
   ([mostlylucid.net](https://www.mostlylucid.net/blog/enhancingmermaiddiagramswithpanzoomandexport)).
   Typical integration is a single extra script tag plus wiring pan/zoom controls (zoom
   in/out/reset, drag-to-pan, wheel-to-zoom) onto the already-rendered SVG, and it's commonly
   deferred/lazily initialized "only when a button is pressed" rather than on every diagram, to
   avoid paying its cost for diagrams that never need it.

**Tradeoffs:**

| Approach | Cost | Solves overflow | Solves readability | Mobile fit |
|---|---|---|---|---|
| Horizontal scroll | trivial | yes | no (text stays tiny) | poor (thin scroll target) |
| Responsive max-width SVG | trivial | yes | no (shrinks text) | good (no overflow) |
| Lightbox expand (reuse `contentLightbox`) | low — pattern already exists | yes | mostly (bigger canvas) | good |
| Lightbox + pan/zoom | medium — new dependency (`svg-pan-zoom`) | yes | yes | good, but adds gesture-conflict risk (pinch-zoom vs. page scroll) |

**Recommendation for the idea:** default every diagram to a responsive, max-width SVG inline in
the column (never horizontal-scroll-by-default — it's the most complained-about pattern), and
reuse the existing `c-picture`/`contentLightbox` `<dialog>` idiom for an "expand" affordance
exactly as images already do. Treat `svg-pan-zoom`-style in-dialog pan/zoom as a stretch
enhancement gated on actual diagram size (e.g. only offer/enable it once the rendered SVG
exceeds some width/height threshold), not a day-one requirement.

## 3. Loading & failure states

- **Flash of raw source.** The FLS `c-equation` widget already solves the general "flash of
  unrendered source" problem for a client-side-rendered widget: the raw source is placed in a
  visible `<span x-ref="src">`, the (empty) rendered output span starts `hidden`, and only once
  `katex.render()` succeeds does the component flip `src.hidden = true; out.hidden = false`
  (`freedom_ls/content_engine/templates/cotton/equation.html`,
  `freedom_ls/content_engine/static/content_engine/js/alpine-components.js`). The same
  swap-on-success pattern applies directly to Mermaid: render to an off-DOM/hidden container
  first, then reveal only on success — the raw fenced-code text (or a lightweight skeleton) is
  what's visible until then, never a half-rendered SVG.
- **Validate before rendering.** Mermaid exposes `mermaid.parse(text, { suppressErrors: true })`
  to check syntax without committing to a render, useful for a "did this fail" branch without
  relying on thrown exceptions
  ([mermaid-js-mermaid.mintlify.app error-handling docs](https://mermaid-js-mermaid.mintlify.app/advanced/error-handling)).
- **Malformed diagrams should degrade to readable source, not a cryptic error.** This mirrors
  the KaTeX widget's existing fallback contract (`throwOnError: false` — malformed LaTeX
  degrades to visible source, and a missing/late KaTeX global also just leaves the raw source
  visible, per the comment in `alpine-components.js`). The same contract should apply to
  Mermaid: on parse/render failure, leave the raw fenced source visible (ideally styled as a
  code block, so authors and — if JS never loads — even students see *something* legible) rather
  than a stack trace or a blank box. Community guidance echoes this: label runtime/render
  failures distinctly from syntax errors rather than lumping everything under "syntax error"
  ([fred#1210](https://github.com/ThalesGroup/fred/issues/1210)), and where a platform can't
  guarantee client-side Mermaid rendering, fall back to a pre-rendered image
  ([mermandraw.com](https://mermandraw.com/blog/how-to-add-mermaid-to-github-readme/)) — not
  applicable to FLS's fully-controlled client runtime, but confirms "always leave a legible
  fallback" as the cross-platform norm.
- **How other platforms behave (illustrative, not to imitate uncritically):** GitHub/GitLab/docs
  generators render Mermaid blocks automatically in-browser but have had recurring bugs where
  valid diagrams silently fail to render in certain contexts (project overview pages, PDF
  export, some diagram types) with no useful fallback shown to the user
  ([github/docs#29691](https://github.com/github/docs/issues/29691),
  [GitLab#206948](https://gitlab.com/gitlab-org/gitlab/-/issues/206948),
  [GitLab#349892](https://gitlab.com/gitlab-org/gitlab/-/issues/349892),
  [Obsidian gitGraph](https://forum.obsidian.md/t/mermaid-cannot-render-gitgraph/31676)). The
  lesson for FLS is negative: don't let a failed render mean "nothing shows" — always fall back
  to the visible source.
- **JS-unavailable case.** Since content is server-rendered markdown with client-side SVG
  rendering, if JS is disabled/blocked the widget must degrade to the same "visible raw source"
  state as a render failure (this falls out naturally if the source span starts visible and is
  only hidden on a successful render, exactly like `c-equation`).

## 4. Accessibility

- **`accTitle` / `accDescr` directives.** Mermaid diagram source can include an `accTitle:` line
  (single line) and an `accDescr:`/`accDescr { ... }` block (single- or multi-line) that Mermaid
  uses to set the rendered SVG's `aria-labelledby`/`aria-describedby`-referenced `<title>` and
  `<desc>` elements, plus an `aria-roledescription` set to the diagram type
  ([Mermaid accessibility docs](http://mermaid.js.org/config/accessibility.html),
  mirrored at
  [docs.mermaidchart.com](https://docs.mermaidchart.com/mermaid-oss/config/accessibility.html)).
- **This is *not* sufficient alone.** Mermaid's own docs/maintainers are explicit that support
  is limited to the SVG-level title/description and `aria-roledescription` — Mermaid does **not**
  expose the diagram's internal structure (nodes, edges, relationships) to assistive tech. "A
  screen reader will read a mermaid diagram as a jumble of unrelated text from the diagram"
  unless a text description is supplied
  ([mermaid#2732](https://github.com/mermaid-js/mermaid/issues/2732),
  [mermaid#5632](https://github.com/mermaid-js/mermaid/issues/5632) — open tracking issue for
  real diagram-structure accessibility, unresolved as of writing;
  [mermaid#3626](https://github.com/mermaid-js/mermaid/issues/3626) requests
  `aria-roledescription` per data view, also open). A raw rendered SVG is essentially opaque to
  screen readers beyond whatever `accTitle`/`accDescr` text is supplied.
  ([Princeton library writeup](https://pulibrary.github.io/2023-03-29-accessible-mermaid) gives
  a practical walkthrough of the same limitation and workaround pattern.)
- **Practical FLS recommendation:** treat `accDescr` as functionally equivalent to the `alt`
  text requirement FLS already enforces for images in `c-picture` (`alt` "describes the image
  for screen-reader users... must not duplicate the visible title"). The widget should:
  - Encourage/require authors to supply `accTitle`/`accDescr` in the Mermaid source (or expose
    equivalent cotton-component attributes, mirroring `c-picture`'s `alt`/`title`/`description`
    split), rather than relying on the diagram's visual structure alone.
  - Not treat a rendered SVG as a self-sufficient accessible artifact — course authors writing
    diagrams that carry essential information (not purely decorative) should be nudged (author
    tooling / docs / maybe a lint warning) to add a text equivalent, the same way alt text is
    already a first-class, documented requirement for images.
  - Set `role="img"` (or rely on Mermaid's own `aria-roledescription`) plus reference the
    `accTitle`/`accDescr`-driven `<title>`/`<desc>` so screen readers announce something
    meaningful rather than raw path/text fragments.
- **Keyboard/focus:** the expand/lightbox trigger must be a real, keyboard-focusable `<button>`
  (as `c-picture` already does — "Real button so the spotlight trigger is keyboard-accessible")
  and the `<dialog>` must carry an appropriate `aria-labelledby`/`aria-label` — again, directly
  reusable from the existing lightbox markup.

## 5. Authoring UX (brief)

Common author-reported pain points, kept brief since this is out of scope for the diagram
*rendering* widget itself:

- Syntax errors are easy to introduce (indentation/quoting sensitivity, diagram-type-specific
  keyword sets) and Mermaid's parse errors can be non-obvious to a non-expert author.
- Special characters inside node labels need escaping/quoting, which trips up authors writing
  markdown-adjacent prose inside diagram labels.
- No in-editor live preview in FLS's markdown authoring flow today (unlike the Mermaid Live
  Editor or IDE plugins) — authors currently only see whether it rendered once the page reloads
  in-browser. Worth flagging as a later authoring-tooling improvement, not a rendering-widget
  requirement.

## 6. Mobile/responsive & print

- **Mobile:** the responsive max-width-SVG + lightbox-to-expand pattern (section 2) is the
  practical mobile answer — small screens make in-column diagrams illegible fast, and
  horizontal-scroll-in-a-narrow-column is a poor touch UX, so "shrink to fit, tap to expand
  full-screen" is preferable to relying on scroll or shrinking alone. Keep diagrams reasonably
  scoped (course-authoring guidance, not a technical constraint) — external guidance suggests
  diagrams beyond roughly 15–20 nodes get hard to parse on small screens regardless of zoom
  ([mermaidcreator.com](https://www.mermaidcreator.com/blog/mermaid-flowchart-sizing-layout-best-practices)).
  Also note real reports of Mermaid simply failing to render on some older iOS Safari versions
  ([Obsidian iOS <17 bug](https://forum.obsidian.md/t/mermaid-graphs-not-rendering-at-all-on-ios-17/107464))
  — another reason the "leave legible raw source on failure" fallback (section 3) matters most
  on mobile.
- **Print/PDF:** the common, low-effort CSS fix is `@media print { .mermaid > svg { max-width:
  100%; max-height: 100%; page-break-inside: avoid; } }`, which keeps a diagram intact on one
  printed page rather than letting it split mid-shape. Long/tall diagrams that exceed a single
  printed page are a known hard case with no fully satisfying default (mermaid-cli tracks this
  as an open ask for smarter page-aware breaking —
  [mermaid-cli#744](https://github.com/mermaid-js/mermaid-cli/issues/744)); scaling the whole
  diagram down to fit one page is the safe default over letting it clip. FLS course content
  print/PDF export (if/when it exists) should apply `page-break-inside: avoid` at minimum.

## Synthesis: concrete recommendations for the idea

1. **Reuse, don't reinvent, two existing idioms:** the `c-equation` render/hide/fallback
   lifecycle (source visible → hidden render happens → swap to rendered output on success,
   otherwise leave source visible) for load/failure states, and the `c-picture`
   `contentLightbox` `<dialog>` pattern for "expand diagram" — same trigger-button +
   `showModal()` shape, adapted so the expanded view keeps the diagram fully visible (fit, not
   cropped).
2. **Default rendering:** responsive/max-width SVG inline in the reading column. No
   horizontal-scroll-by-default (it's the most-complained-about pattern in the research and a
   poor mobile fit).
3. **Failure/no-JS default:** always leave the raw Mermaid source legible (styled as a code
   block) rather than a blank box or a stack trace — this is the single most consistent
   "don't do this" lesson across GitHub/GitLab/Obsidian issue trackers.
4. **Accessibility requirement to bake into the component contract:** treat `accTitle`/`accDescr`
   (or equivalent cotton-component attributes) the same way `alt`/`title`/`description` are
   already required/encouraged on `c-picture` — a rendered SVG diagram is not accessible on its
   own, and this should be stated explicitly in the widget's authoring docs/comments, not left
   implicit.
5. **Pan/zoom (svg-pan-zoom or similar) is a stretch goal, not core scope** — gate it on
   diagram-size/need rather than shipping it for every diagram; the lightbox alone likely
   resolves most "diagram too small to read" complaints, and adding a pan/zoom library brings
   real cost (gesture conflicts, extra dependency, extra a11y surface) that should be justified
   by evidence of need after the basic widget ships.
6. **Print:** apply `page-break-inside: avoid` + max-width/max-height in a print stylesheet from
   day one; it's a one-line fix with an outsized "don't split diagrams across pages" payoff.

## References

- [Mermaid Accessibility Options docs](http://mermaid.js.org/config/accessibility.html)
- [Screen reader / a11y tech support for diagrams — mermaid#5632](https://github.com/mermaid-js/mermaid/issues/5632)
- [More Accessible Mermaid Charts — mermaid#2732](https://github.com/mermaid-js/mermaid/issues/2732)
- [Need aria-roledescription on each data view — mermaid#3626](https://github.com/mermaid-js/mermaid/issues/3626)
- [Accessible Mermaid charts in GitHub Markdown (Princeton Library)](https://pulibrary.github.io/2023-03-29-accessible-mermaid)
- [Mermaid flowchart sizing and layout: best practices](https://www.mermaidcreator.com/blog/mermaid-flowchart-sizing-layout-best-practices)
- [Width fixed to 400px — mermaid#204](https://github.com/mermaid-js/mermaid/issues/204)
- [Configure flowchart to auto-resize — mermaid#838](https://github.com/mermaid-js/mermaid/issues/838)
- [Rendered diagrams overflow horizontally — zenuml-core#308](https://github.com/mermaid-js/zenuml-core/issues/308)
- [Mermaid diagrams not resizing to fit page (Obsidian forum)](https://forum.obsidian.md/t/mermaid-diagrams-not-resizing-to-fit-in-page/98078)
- [Mermaid JS Diagram Unreadable Due to Large Size (Obsidian forum)](https://forum.obsidian.md/t/mermaid-js-diagram-unreadable-due-to-large-size/23769)
- [Enhancing Mermaid Diagrams with Pan/Zoom and Export](https://www.mostlylucid.net/blog/enhancingmermaiddiagramswithpanzoomandexport)
- [obsidian-mermaid-pan-and-zoom plugin](https://github.com/MarcoUmpierrez/obsidian-mermaid-pan-and-zoom)
- [obsidian-mermaid-zoom plugin (fork w/ responsive fixes)](https://github.com/ALXRITR/obsidian-mermaid-zoom)
- [Pan and Zoom on Mermaid Diagrams feature request (Obsidian forum)](https://forum.obsidian.md/t/pan-and-zoom-on-mermaid-diagrams/65271)
- [vscode-markdown-mermaid pan/zoom PR #295](https://github.com/mjbvz/vscode-markdown-mermaid/pull/295)
- [Mermaid diagrams are not zoomable — GitLab Docs #1168](https://gitlab.com/gitlab-org/gitlab-docs/-/issues/1168)
- [Mermaid error-handling docs](https://mermaid-js-mermaid.mintlify.app/advanced/error-handling)
- [Handling Mermaid Diagram Rendering Errors (dev.to)](https://dev.to/geanruca/handling-mermaid-diagram-rendering-errors-1n8i)
- [Mermaid viewer async render cleanup race — fred#1210](https://github.com/ThalesGroup/fred/issues/1210)
- [Valid mermaid diagram fails to parse (Obsidian forum)](https://forum.obsidian.md/t/valid-mermaid-diagram-fails-to-render-with-parsing-error/67685)
- [Mermaid not rendering — github/docs#29691](https://github.com/github/docs/issues/29691)
- [Mermaid diagrams not rendered in project overview — GitLab#206948](https://gitlab.com/gitlab-org/gitlab/-/issues/206948)
- [Intermittent Mermaid rendering issue — GitLab#349892](https://gitlab.com/gitlab-org/gitlab/-/issues/349892)
- [Mermaid cannot render gitGraph (Obsidian forum)](https://forum.obsidian.md/t/mermaid-cannot-render-gitgraph/31676)
- [Mermaid not rendering on iOS <17 (Obsidian forum)](https://forum.obsidian.md/t/mermaid-graphs-not-rendering-at-all-on-ios-17/107464)
- [Mermaid fails in Obsidian PDF export — mermaid#6922](https://github.com/mermaid-js/mermaid/issues/6922)
- [How to add Mermaid to a GitHub README (fallback-image guidance)](https://mermandraw.com/blog/how-to-add-mermaid-to-github-readme/)
- [Prevent Mermaid charts overflowing PDF export (Obsidian forum)](https://forum.obsidian.md/t/prevent-mermaid-charts-from-overflowing-the-page-in-export-to-pdf/13381)
- [mermaid-cli page-break option request #744](https://github.com/mermaid-js/mermaid-cli/issues/744)
- [Cumulative Layout Shift (web.dev)](https://web.dev/articles/cls)

## FLS code referenced (existing patterns to reuse)

- `freedom_ls/content_engine/templates/cotton/picture.html` — image spotlight/lightbox
  component; `alt`/`title`/`description` attribute contract to mirror for diagram text
  alternatives.
- `freedom_ls/content_engine/templates/cotton/equation.html` — client-side KaTeX render widget;
  source-visible → hidden-render → swap-on-success lifecycle to mirror for Mermaid.
- `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` — `equation` and
  `contentLightbox` Alpine components implementing the above patterns (including scroll-lock,
  focus-trap via native `<dialog>`, and graceful-degrade-on-error comments).
- `spec_dd/1. next/mermaid-diagram-widget/idea.md` — current idea scope (theming, `c-mermaid`
  cotton component, modern Mermaid version for newer diagram types e.g. herringbone-style
  layouts).

status: ok
