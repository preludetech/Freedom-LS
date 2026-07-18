# Research: Keeping Mermaid.js, Shrinking Its Client-Side Cost

Scope: `mermaid-diagram-widget` idea refinement. Companion to
`research_mermaid_integration.md` (which recommends vendoring `mermaid.min.js` as a single
self-hosted UMD file, KaTeX-style, and flags its ~3.4 MB size as a caveat without exploring
mitigations) — **this file goes deep on that one caveat**: given FLS's constraints (no JS
bundler for app JS, `ManifestStaticFilesStorage` hashed static filenames, no runtime CDN),
what are the real options to reduce the *effective* client cost of Mermaid without abandoning
self-hosting or accepting a materially worse maintenance/CSP posture?

Research date: 2026-07-17.

## Summary / recommendation up front

Do **not** chase Mermaid's ESM code-splitting or a custom subset build — both are real
mechanisms upstream but land badly on FLS's specific toolchain (no bundler, hashed static
filenames, no build-time verification of import wiring). The high-leverage, low-complexity win
is **conditionally loading the existing single `mermaid.min.js` file only on pages whose
rendered content actually contains a `c-mermaid` diagram**, decided server-side at render time
(FLS already has the raw markdown source in hand) rather than mirroring KaTeX's "always loaded
on every course page" pattern — a 3.4 MB script is a fundamentally different cost/benefit
calculus than KaTeX's ~280 KB, so the extra conditional-load complexity (which wasn't judged
worthwhile for KaTeX) is justified here. This supersedes the throwaway line in
`research_mermaid_integration.md` §1 suggesting mermaid load "same as KaTeX" on every course
page. See §6 for the full ranking.

---

## 1. The ESM code-splitting model — is it feasible for FLS?

**How it actually works.** `mermaid.esm.min.mjs` is a small (~29–50 KB minified) entry module.
It does **not** contain diagram-rendering code; instead it `import()`s a diagram-type-specific
chunk at runtime, on first use of that diagram type, from mermaid's own `dist/chunks/` tree
(chunk filenames are mermaid's *own* build-time content hashes, e.g. `chunk-6VWZOGXT.mjs` —
this matters below). Individual diagram chunks are not small: from mermaid's published
`dist/chunks/mermaid.esm.min/` listing, minified chunk sizes run roughly
**sequence ~117 KB, swimlanes ~116 KB, architecture ~155 KB, and the shared KaTeX-for-labels
support chunk ~270 KB** — plus shared core/layout chunks (d3, `dagre-d3-es`, mermaid's own core)
that most diagram types pull in regardless of type.
[jsDelivr package data — mermaid@11.16.0](https://data.jsdelivr.com/v1/packages/npm/mermaid@11.16.0)

**Total footprint is not dramatically smaller — it's the same code, sliced.** Bundlephobia's
build-and-measure of `import mermaid from "mermaid"` (the ESM entry graph) reports the main
bundle at **656 KB minified / 157 KB gzip**, and the *full* package — 72 JS assets, i.e. every
lazily-loadable chunk — at **~1.83 MB uncompressed total**.
[Bundlephobia — mermaid](https://bundlephobia.com/package/mermaid) This is meaningfully less
than 3.4 MB (some of the gap is UMD-vs-ESM tree-shaking/bundling differences), but the real win
of ESM code-splitting was never "less total code" — it's "a page using only a flowchart doesn't
pay for the sequence/gantt/mindmap/etc. chunks it never touches." For a single-diagram-type
course page, realistic transfer is probably in the 300–700 KB range (entry + one diagram chunk +
shared layout chunks), not the full 1.83 MB.

**Could FLS self-host the ESM build + chunks under Django static, with an import map making
the relative dynamic imports resolve against hashed URLs?**

- **Native `<script type="module">` + relative `import()`**: mermaid's own bundle contains
  literal relative specifiers like `import("./chunk-6VWZOGXT.mjs")`. Under
  `ManifestStaticFilesStorage`, `collectstatic` renames every collected file to include a
  content hash it computes itself (`chunk-6VWZOGXT.<django-hash>.mjs`) — but does **not**
  rewrite string literals inside arbitrary `.mjs` files by default. Django does ship an
  **experimental** opt-in (`ManifestStaticFilesStorage.support_js_module_import_aggregation =
  True`) that regex-rewrites JS "module import" and "module aggregation" statements to point at
  hashed names, explicitly documented as experimental with a known caveat — it doesn't ignore
  paths inside comments and can crash on non-existent paths as a result
  ([Django docs — staticfiles](https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/);
  background: [Django ticket #21080](https://code.djangoproject.com/ticket/21080)). Its
  documented coverage is MDN's "importing/aggregating modules" — i.e. static `import`/`export
  ... from` syntax — with no documented guarantee it also rewrites the dynamic-`import()`
  call-site pattern a third-party bundler's runtime chunk loader emits. Without this feature (or
  with it working only partially), the literal chunk paths baked into `mermaid.esm.min.mjs`
  simply won't match the hashed filenames Django produces for the chunk files — a page loading
  the entry module fine, then getting a **404 on the first diagram actually rendered**, is the
  realistic failure mode, discovered by a student's browser console rather than at build/CI
  time.
- **Import maps**: the import-map resolution algorithm *does* first resolve a relative specifier
  (`./chunk-X.mjs`) to an absolute URL using the referring module's own URL, and *that* absolute
  URL can then match an import-map entry — so in principle you could hand- or script-generate an
  import map keyed by every chunk's pre-hash absolute static URL → Django's post-hash URL,
  sourced from the `staticfiles.json` manifest `ManifestStaticFilesStorage` already writes (no
  bundler required for *this* part — pure Django). This is the theoretically-sound path, and it
  is worth knowing it exists. But it does not remove the two practical blockers:
  1. **No manifest of "which chunks a diagram type needs."** Chunks nest/share transitively (a
     diagram chunk imports a shared layout chunk which imports the d3 chunk, etc.), and this
     dependency graph is an undocumented internal build artifact, not a published contract — the
     only reliably-safe posture is vendoring mermaid's **entire** `dist/chunks/mermaid.esm.min/`
     tree (100+ files) to avoid a missed transitive chunk silently 404ing, which defeats the
     "don't ship code you don't need" premise for *repo/static-collection* footprint (transfer
     footprint per page-view is still improved, since only touched chunks are actually
     *fetched*).
  2. **Zero build-time verification.** There is no bundler to fail a CI build if a chunk
     reference and an import-map entry drift out of sync (e.g. after a mermaid version bump
     changes chunk boundaries/hashes). This is exactly the failure class reported by consumers
     of mermaid's own lazy-chunk loading in bundler contexts: chunk files get new hashes on
     redeploy and stale references cause runtime crashes/404s, not build failures
     ([vercel/streamdown#343](https://github.com/vercel/streamdown/issues/343)). Mermaid's own
     maintainers acknowledge the underlying friction: an open feature request for
     "diagram preloading" was blocked by the exact same problem — *"there are content hashes in
     the diagram files' file names,"* making direct/predictable imports of specific diagram
     chunks impractical even for mermaid's own recommended usage
     ([mermaid-js/mermaid#4275 "Support diagram preloading"](https://github.com/mermaid-js/mermaid/issues/4275)).

**Verdict**: the import-map mechanism is *sufficient in principle*, but the real bottleneck is
operational — a 100+-entry, version-coupled mapping with no tooling to keep it in sync and no
build-time safety net, in a codebase whose entire JS story today is "vendor a file, load it with
`<script defer>`." This is precisely the class of problem a bundler exists to solve, and adding
one just to make ESM chunking safe is a bigger toolchain change than the size problem justifies
(see §4, which is the same tradeoff from a different angle). **Not recommended.**

## 2. Conditional-load-only-when-a-diagram-is-present (highest leverage)

Instead of shrinking mermaid, only fetch `mermaid.min.js` on pages whose content actually
contains a `c-mermaid` widget — diagram-free course pages (almost certainly the majority of
content) pay nothing.

**Prior art**: exactly this pattern, done client-side (DOM-scan then inject), is documented for
a static-site scenario: *"Mermaid represents a 660KB download... only 2 pages out of the entire
site use Mermaid"* — the loader does `if (!document.querySelector(".mermaid")) return;` before
creating and appending a `<script>` tag
([Rick Strahl — "Lazy Loading the Mermaid Diagram Library"](https://weblog.west-wind.com/posts/2025/May/10/Lazy-Loading-the-Mermaid-Diagram-Library)).
FLS can do materially better than a client-side DOM scan, because the decision can be made
**server-side, at render time**, where the raw content is already available.

**How the content pipeline can signal "this content has a diagram":**

- `MarkdownContent.rendered_content()` (`freedom_ls/content_engine/models.py:124`) already
  converts `self.content` (raw markdown, including any ` ```mermaid ` fences that become
  `c-mermaid` cotton tags) through `render_markdown()`
  (`freedom_ls/markdown_rendering/markdown_utils.py`) — `markdown.Markdown` → `nh3.clean()` →
  Cotton compile. The cheapest possible signal is a `@cached_property` on the model (e.g.
  `has_mermaid_diagram`) doing a plain substring/regex check against the **raw** `self.content`
  before any of that pipeline runs (e.g. `"```mermaid" in self.content`, or matching whatever
  fence/tag syntax the eventual `c-mermaid` spec settles on) — no need to render first just to
  find out whether to load the script.
- **Where to emit the conditional `<script>` tag matters, because course navigation is
  HTMX-boosted, not full-page.** `freedom_ls/student_interface/templates/cotton/player-nav.html`
  sets `hx-boost="true" hx-target="#interface-main" hx-swap="outerHTML show:window:top"` on
  in-course Previous/Next navigation — meaning `_course_base.html`'s
  `extra_alpine_components` block (where KaTeX and `alpine-components.js` are currently loaded,
  `freedom_ls/student_interface/templates/student_interface/_course_base.html:14-19`) only
  renders on a **hard/initial page load**, not on subsequent boosted navigation between topics
  within the same course session. If a student lands on a diagram-free topic first, then
  navigates (boosted) to a topic with a diagram, a script tag placed in `_course_base.html`
  would never fire a second time. **The conditional loader script must therefore live inside the
  HTMX-swapped region itself** — i.e. emitted from the topic-content template, alongside/near
  the rendered `c-mermaid` markup, not from the shared course chrome. htmx's default behaviour
  is to extract and re-execute `<script src>` elements found in swapped-in fragments
  (`htmx.config.allowScriptTags`, on by default), so a `<script defer src="{% static ... %}">`
  placed inside the swapped fragment should fire correctly on each boosted navigation into a
  diagram-bearing topic; a small guard (checking `window.mermaid` is already defined, or a
  `data-mermaid-loaded` flag) is needed to avoid double-injection/double-init on repeat visits
  within a session, since a cached script re-fetch is cheap but re-running top-level init code
  twice is not automatically safe.
- **Complexity**: low. One cached boolean-ish signal at the content-model layer, one `{% if %}`
  around the existing `<script defer src="{% static 'content_engine/vendor/mermaid/mermaid.min.js' %}">`
  tag (same vendored file as today, no new files), placed in the swapped-content template rather
  than course chrome. No bundler, no chunking, no extra vendored files.

## 3. Dynamic import on first diagram scrolled into view (IntersectionObserver)

A refinement layered *on top of* §2, not a competitor to it: once "does this page have a
diagram at all" is known server-side, a further optimization is deferring the fetch until a
`c-mermaid` element is actually near-viewport (`IntersectionObserver` + `rootMargin`), for the
case of a long page with a diagram far below the fold that many readers never scroll to.

**Assessment for FLS**: likely a small next increment, not a must-have. FLS course topics are
scoped per-topic units (one concept/section per page in the existing IA), so a `c-mermaid`
widget is more likely to be near the top of a topic's visible content than deeply buried below
several screens of prose — unlike a long blog post or full README where in-view lazy-loading
earns its keep. It also adds real integration cost: the Alpine `mermaid` component's `init()`
(per `research_mermaid_integration.md` §2/§5) currently only needs to wait on "script loaded";
gating on "script loaded AND scrolled into view" means restructuring that lifecycle to coordinate
two async conditions instead of one, a more invasive change than §2 requires. **Recommendation:
defer to a later enhancement, not day-one scope** — revisit only if usage data later shows long
topic pages with diagrams well below the fold.

## 4. Custom/partial builds (subset of diagram types)

Mermaid supports registering diagram types as external plugins with a `lazyLoad` flag
(`mermaid.registerExternalDiagrams([...])`, loader invoked only when a detector matches the
diagram's opening keyword) — this is the same mechanism mermaid's own build uses internally to
treat each stock diagram type as a separate entry/chunk in its Vite config
([mermaid `vite.config.ts`](https://github.com/mermaid-js/mermaid/blob/develop/vite.config.ts)).
To get a genuinely smaller **single self-hosted file** containing only, say, flowchart +
sequence + ER + class + state + gantt + pie (a plausible "classic subset" covering most
course-authoring needs) rather than all 20+ types including the newer/beta ones, you would need
to run mermaid's own build tooling (Vite/ESBuild) against a custom entry that imports mermaid
core and registers only the desired diagram plugins, then emit a single UMD/IIFE bundle from
that — i.e. **adopt a JS build step that does not exist in FLS today**. Per `CLAUDE.md` and
confirmed in the codebase, Node/npm is present only for the Tailwind CSS build
(`npm run tailwind_build`); there is no bundler wired up for app JS (KaTeX and
`alpine-components.js` are hand-vendored/hand-written plain files loaded via
`<script defer>`).

**Payoff estimate**: based on the per-diagram-chunk sizes in §1 (sequence ~117 KB, architecture
~155 KB, KaTeX-label-support ~270 KB, swimlanes ~116 KB minified) plus the shared d3/layout core
that dominates the total (per a community bundle-shrinking writeup, Lodash tree-shaking alone
was ~10% of total size, with dagre/d3 dominating the rest —
[Shrinking Mermaid >30% — Sidharth Vinod](https://www.sidharth.dev/posts/shrinking-mermaid/)), a
"classic subset" custom build plausibly lands around **1–1.8 MB minified** rather than 3.4 MB —
a real but roughly 50%, not order-of-magnitude, reduction. It also **forecloses the idea's own
explicit "herringbone/Ishikawa diagrams" requirement** (and any other diagram type) unless
deliberately included in the custom entry, creating an ongoing maintenance tax: every time a
course author wants a new diagram type, someone must rebuild and re-vendor the custom bundle,
forever, versus a stock build where "bump the version string" is the entire upgrade path.

**Verdict**: works, but trades "vendor one upstream file, bump a version string" (today's whole
KaTeX/mermaid-vendoring story) for "own and maintain a small build pipeline plus a curated
diagram-type allowlist, indefinitely." Not recommended unless §2 alone proves insufficient in
practice (e.g. some flagship page legitimately needs many diagrams and even conditional loading
doesn't help) — no evidence that's the case for FLS today.

## 5. Compression reality — 3.4 MB in perspective

- **3.4 MB minified is the uncompressed-over-the-wire figure.** Real deployments (browser ↔
  Django/whitenoise/CDN) serve static JS with gzip or brotli content-encoding, and JS compresses
  well (repetitive tokens, whitespace, identifier patterns). Gzip typically reduces JS payload by
  roughly 70–80%; brotli typically adds another ~15–20% on top of gzip for text assets
  ([web.dev — Minify and compress with brotli](https://web.dev/articles/codelab-text-compression-brotli);
  [DebugBear — Brotli vs. Gzip](https://www.debugbear.com/blog/http-compression-gzip-brotli)).
  Extrapolating those general ratios to 3.4 MB gives a **rough order-of-magnitude estimate of
  ~700 KB–1 MB gzip, ~550–800 KB brotli** transferred — flagged explicitly as an *estimate from
  typical JS compression ratios*, not a directly-measured figure for this exact file (no public
  source was found publishing a measured gzip/brotli size specifically for the monolithic
  `mermaid.min.js` UMD build).
- **A directly-measured data point exists for the (smaller-scope) ESM entry graph**:
  Bundlephobia's build-and-measure pipeline reports mermaid's primary import graph at **656 KB
  minified / 157 KB gzip** ([Bundlephobia — mermaid](https://bundlephobia.com/package/mermaid))
  — a ~24% gzip ratio, consistent with the general "JS compresses to roughly a fifth to a
  quarter of minified size" pattern used for the estimate above, though this measures a
  different bundle scope (ESM entry, not the full UMD file) so isn't a stand-in for the 3.4 MB
  figure.
- **Caching**: this is a one-time cost per browser. `ManifestStaticFilesStorage` gives the
  vendored file a content-hashed, effectively-immutable URL, so a returning student does not
  re-download it on subsequent page loads/sessions regardless of which loading strategy (§2/§3)
  is used — standard practice pairs hashed static URLs with long-lived
  `Cache-Control: max-age=..., immutable`.
- **But transfer size isn't the whole cost.** A cached asset still has to be **parsed and
  compiled**, and on repeat use, **executed** — this is CPU time, not network time, and it does
  not disappear just because the bytes were cached. The consistent finding across V8's and
  Addy Osmani's "cost of JavaScript" work is that download and CPU execution time are the
  dominant costs of processing large scripts, and that this cost is materially worse on
  low-end/budget mobile devices than on desktop — *"all bytes are not equal,"* a large JS
  bundle has fundamentally different processing cost than an equivalently-sized image
  ([V8 blog — "The Cost of JavaScript in 2019"](https://v8.dev/blog/cost-of-javascript-2019);
  [Addy Osmani — "The Cost Of JavaScript"](https://medium.com/@addyosmani/the-cost-of-javascript-in-2018-7d8950fbb5d4)).
  This is precisely the residual cost that "it's cached after first load" does **not** answer,
  and is a second, independent reason (alongside first-load transfer size) that §2's
  "don't load it at all on diagram-free pages" remains valuable even for returning students on a
  warm cache.

## 6. Recommendation ranking (leverage ÷ complexity, for FLS specifically)

| Rank | Option | Leverage | Complexity | Notes |
|---|---|---|---|---|
| 1 | **§2 Conditional load only when a diagram is present** | High — skips 3.4 MB (transfer *and* parse/exec) entirely on diagram-free pages, likely the majority of content | Low — one cached signal on the content model, one template conditional, placed inside the HTMX-swapped fragment (not course chrome) | **Recommended for the spec.** Same vendored file as the "accept as-is" baseline; only changes *when* it loads. |
| 2 | Accept the vendored UMD file as-is, load on every course page like KaTeX | None (status quo) | Lowest (already the plan in `research_mermaid_integration.md`) | Reasonable fallback if §2's signal proves awkward to compute, but leaves the biggest, cheapest win unclaimed given the 12× size gap vs. KaTeX (~3.4 MB vs. ~280 KB) that KaTeX's own "always load" precedent doesn't justify. |
| 3 | §3 IntersectionObserver in-view lazy load | Low-medium incremental, on top of §2 | Medium — restructures the Alpine `mermaid` component's async init to gate on two conditions | Defer; revisit only with evidence of long pages with below-fold diagrams. |
| 4 | §1 ESM code-splitting + import map | Medium (per-diagram-type savings) in theory | High — no bundler, no build-time verification, 100+ files, version-coupled, mermaid's own chunk hashes are undocumented/unstable | Not recommended: the failure mode (silent runtime 404 on a diagram render) is worse than the problem being solved. |
| 5 | §4 Custom/partial subset build | Medium (~50% size cut) | High — adds a JS build step FLS doesn't have anywhere else in the app-JS story, plus an ongoing diagram-type-allowlist maintenance tax, and forecloses the idea's explicit Ishikawa/herringbone requirement unless deliberately included | Not recommended unless §2 is proven insufficient. |

**Cross-reference**: a sibling research file (not yet written as of this research pass, if the
idea refinement produces one) would cover **full server-side SVG rendering** — i.e. rendering
diagrams to static SVG at content-save/build time instead of shipping any client-side Mermaid
runtime at all — as the other major structural alternative to "ship the JS and render in the
browser." That approach sidesteps this entire bundle-size question by construction (zero
client-side Mermaid JS ever, at the cost of losing client-side theme-reactivity/interactivity
and needing a server-side rendering toolchain, e.g. `mermaid-cli`/Puppeteer or a WASM renderer).
This file assumes client-side rendering is kept (per the idea's framing: "keep mermaid.js") and
only optimizes *within* that constraint.

## References

- [mermaid — npm](https://www.npmjs.com/package/mermaid) ·
  [mermaid-js/mermaid GitHub](https://github.com/mermaid-js/mermaid)
- [jsDelivr package data — mermaid@11.16.0 dist listing](https://data.jsdelivr.com/v1/packages/npm/mermaid@11.16.0)
- [Bundlephobia — mermaid size report](https://bundlephobia.com/package/mermaid)
- [mermaid `vite.config.ts` — diagram types as entry points](https://github.com/mermaid-js/mermaid/blob/develop/vite.config.ts)
- [mermaid-js/mermaid#4275 — "Support diagram preloading" (content-hashed chunk filenames blocking predictable imports)](https://github.com/mermaid-js/mermaid/issues/4275)
- [mermaid-js/mermaid#3061 — "Modularise mermaid" code-splitting discussion](https://github.com/mermaid-js/mermaid/issues/3061)
- [mermaid-js/mermaid#843 — "Smaller bundles"](https://github.com/mermaid-js/mermaid/issues/843) (cited in
  `research_mermaid_integration.md`)
- [vercel/streamdown#343 — stale lazy-loaded chunk hash causes runtime crash after redeploy](https://github.com/vercel/streamdown/issues/343)
- [Shrinking Mermaid >30% — Sidharth Vinod](https://www.sidharth.dev/posts/shrinking-mermaid/)
- [Rick Strahl — "Lazy Loading the Mermaid Diagram Library"](https://weblog.west-wind.com/posts/2025/May/10/Lazy-Loading-the-Mermaid-Diagram-Library)
- [Django docs — `ManifestStaticFilesStorage` / `support_js_module_import_aggregation`](https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/)
- [Django ticket #21080 — import-rewriting doesn't ignore comments](https://code.djangoproject.com/ticket/21080)
- [Matthias Kestenholz — "Django, JavaScript modules and importmaps"](https://406.ch/writing/django-javascript-modules-and-importmaps/)
- [Adam Johnson — "Django: render JavaScript import maps in templates"](https://adamj.eu/tech/2025/01/09/django-import-maps/)
- [web.dev — Minify and compress network payloads with brotli](https://web.dev/articles/codelab-text-compression-brotli)
- [DebugBear — Brotli vs. Gzip](https://www.debugbear.com/blog/http-compression-gzip-brotli)
- [V8 blog — "The Cost of JavaScript in 2019"](https://v8.dev/blog/cost-of-javascript-2019)
- [Addy Osmani — "The Cost Of JavaScript"](https://medium.com/@addyosmani/the-cost-of-javascript-in-2018-7d8950fbb5d4)

## FLS code referenced

- `freedom_ls/content_engine/models.py:119-137` — `MarkdownContent.rendered_content()`, where a
  `has_mermaid_diagram`-style signal would be computed from raw `self.content`.
- `freedom_ls/markdown_rendering/markdown_utils.py` — `render_markdown()` pipeline
  (markdown → `nh3.clean()` → Cotton compile) that content passes through before display.
- `freedom_ls/student_interface/templates/student_interface/_course_base.html:14-19` — current
  KaTeX/`alpine-components.js` `<script defer>` loading pattern, only fires on hard page loads.
- `freedom_ls/student_interface/templates/cotton/player-nav.html` — `hx-boost="true"
  hx-target="#interface-main"` in-course navigation; establishes that a conditional mermaid
  loader must live inside the swapped fragment, not course chrome.
- `freedom_ls/content_engine/static/content_engine/vendor/katex/katex.min.js` — existing
  self-hosted vendor-file pattern to mirror for `mermaid.min.js`.

status: ok
