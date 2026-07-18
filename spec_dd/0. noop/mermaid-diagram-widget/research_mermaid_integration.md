# Research: Mermaid.js integration for `<c-mermaid>` (mirroring the KaTeX/`c-equation` pattern)

Research date: 2026-07-17.

## Summary / recommendation up front

Mermaid.js **can** follow the exact same self-hosted, CSP-Alpine, single-`<script defer>` pattern
FLS already uses for KaTeX (`c-equation`), with two differences to plan for in the spec:

- **Bundle size**: the single-file self-hosted build (`mermaid.min.js`, UMD/IIFE, exposes
  `window.mermaid`) is **~3.4 MB minified** (~7.8 MB unminified) — far larger than KaTeX's
  `katex.min.js` (~280 KB). This is a real, known pain point for self-hosters (see §1) but the file
  itself is a drop-in analog of `katex.min.js`: no CDN, no dynamic per-chunk network fetches, no
  build step required.
- **Render call, not auto-scan**: use `mermaid.render(id, sourceText)` (async, returns
  `{svg, bindFunctions}`) inside the Alpine `init()`, exactly mirroring how `equation` calls
  `katex.render()`. Do **not** use `mermaid.run()`/`mermaid.init()` — those auto-scan the whole page
  for `.mermaid` elements, which is the wrong shape for a per-widget cotton component and Alpine
  already gives us the "find my own slot" scoping KaTeX uses.
- **"Herringbone diagrams"**: the idea file's phrase is not a mermaid-doc red herring — it is
  **literally mermaid's own synonym for its new "Ishikawa diagram" type** (fishbone / cause-and-effect
  diagram), added in **mermaid v11.12.3+** as an experimental (`-beta`) diagram type. See §4. The idea
  owner should be told this exists and is very new/beta, so `c-mermaid` should pin a mermaid version
  ≥ 11.12.3 (current is 11.16.x) if this diagram type matters for launch.

---

## 1. Version & distribution

- **Current version**: mermaid **11.16.0** on npm (`npm install mermaid`), 0 runtime dependencies for
  the bundle build. [npm: mermaid](https://www.npmjs.com/package/mermaid) ·
  [GitHub Releases](https://github.com/mermaid-js/mermaid/releases)
- **Distribution files** (from the published `dist/` folder, checked via jsDelivr's file listing for
  `mermaid@11`, [cdn.jsdelivr.net/npm/mermaid@11/dist/](https://cdn.jsdelivr.net/npm/mermaid@11/dist/)):
  | file | purpose | approx size |
  |---|---|---|
  | `mermaid.min.js` | UMD/IIFE, self-contained, sets `window.mermaid` when loaded via plain `<script>` | ~3.4 MB min (~7.8 MB unminified) |
  | `mermaid.esm.min.mjs` | ESM entrypoint, must be loaded via `<script type="module">`/`import` | ~29 KB min |
  | `mermaid.core.mjs` | Core ESM module used internally | ~50 KB |
  The ESM entrypoint is small because mermaid **code-splits by diagram type and dynamically
  `import()`s the needed diagram renderer at runtime** (flowchart, sequence, etc. are separate
  chunks fetched on demand). That is fine for a CDN/bundler setup but is a poor match for FLS's
  "single vendored static file, works with `collectstatic`, no network path assumptions" constraint —
  it would mean vendoring dozens of chunk files and getting webpack/vite-style relative resolution
  right under Django's static file hashing (`ManifestStaticFilesStorage`), which is fragile.
  **`mermaid.min.js` is the right choice**: everything is bundled into one file, no further requests,
  directly analogous to `katex.min.js` + `<script defer src="{% static ... %}">`.
- **History note relevant to "why is `mermaid.min.js` even there"**: mermaid v10 briefly shipped
  **ESM-only** with no minified single-file build, which broke offline/self-hosted users; a user
  explicitly reported *"our product is required to be able to run offline (without access to the
  internet) so we can not use a CDN"* and that it's *"not possible... to know which of the thousands
  of files in the release folder are actually required."* The UMD/IIFE build was restored by
  [PR #4281 "Add UMD build Back"](https://github.com/mermaid-js/mermaid/pull/4281) in response to
  [Issue #4279 "There is no mermaid.min.js"](https://github.com/mermaid-js/mermaid/issues/4279).
  FLS's self-hosting requirement is exactly the use case that motivated this file's existence, and
  it has remained in `dist/` since v11 — confirmed present at 11.16.0.
- **Bundle size caveat for the idea/spec**: 3.4 MB is a meaningfully larger static asset than any
  other vendored lib in the repo. Recommend the future spec explicitly note this (one-time cached
  static download, `defer`red, only loaded on `_course_base.html`/`_exam_runner_base.html` same as
  KaTeX — not on every page) rather than silently accepting it. There is no realistic way to shrink
  this while keeping "all diagram types in one file, no CDN, no dynamic chunk loading" — see
  [mermaid-js/mermaid#843 "Smaller bundles"](https://github.com/mermaid-js/mermaid/issues/843) and
  [Shrinking Mermaid >30% (community writeup)](https://www.sidharth.dev/posts/shrinking-mermaid/) for
  background on why the library is this large (it bundles d3, dagre/ELK layout, katex-for-math-labels,
  and every diagram grammar).

## 2. Initialization & render API — fits the `equation` pattern almost exactly

- `mermaid.initialize(options)` — call once, sets config (theme, `startOnLoad`, security level).
  Must be called **before** any render call. `startOnLoad` defaults to `true` and auto-scans the DOM
  for `<pre class="mermaid">`/`.mermaid` elements on `DOMContentLoaded` — **set
  `startOnLoad: false`** so nothing auto-renders; each `c-mermaid` widget renders only its own slot,
  same principle as why `equation` doesn't call a page-wide KaTeX auto-render.
  [Usage docs](https://mermaid.ai/open-source/config/usage.html)
- `mermaid.run(options)` — v10+ replacement for the deprecated `mermaid.init()`. Still an
  auto-scan/batch API (`querySelector`/`nodes` targeting elements with the `mermaid` class), returns
  a Promise. **Not the right fit** here: it's designed for "render everything matching a selector",
  whereas each `c-mermaid` Alpine component should render exactly its own `x-ref` source, mirroring
  `katex.render(source, outEl, opts)` in `equation`'s `init()`.
- `mermaid.render(id, definitionText, container?)` — the programmatic, single-diagram API:
  ```js
  const { svg, bindFunctions } = await mermaid.render(id, sourceText);
  targetEl.innerHTML = svg;
  bindFunctions?.(targetEl); // wires up any interactive elements mermaid embedded in the SVG
  ```
  Returns a **Promise** resolving to `{ svg, bindFunctions }`: `svg` is the SVG markup string,
  `bindFunctions` is an optional callback that must be invoked after the SVG is inserted into the DOM
  (wires up things like click-interaction handlers if `securityLevel: "loose"` is used — FLS should
  not enable that; see §3). Requires a unique `id` per call (any string works — an Alpine-generated
  id, e.g. via `$id()`, is a natural fit, mirroring how `equation` scopes to its own refs).
  [`mermaid.render()` reference](https://mermaid.ai/open-source/config/usage.html)
- **Alpine mapping**: `Alpine.data("mermaid", () => ({ async init() { ... } }))`, reading source text
  from `this.$refs.src.textContent` (same "raw text in a hidden slot, read via `textContent`" pattern
  as `equation`), calling `await window.mermaid.render(...)`, and swapping `$refs.out.innerHTML = svg`
  + toggling `hidden` on src/out exactly like `equation` does. `init()` can simply be declared
  `async` — Alpine does not require `init()` to be synchronous or to return anything; it just calls it
  once on component init and does not await it, which is fine since the component's own state/DOM
  update happens inside the async function once the promise resolves.

## 3. CSP compatibility

- FLS uses Alpine's **CSP build** (`@alpinejs/csp`), which forbids inline expressions and relies on
  `Alpine.data()` registrations — that constraint is about *Alpine's own directive evaluation*, not
  about mermaid. Nothing in `equation`'s pattern nor the proposed `mermaid` component requires inline
  `x-data="{...}"` expressions; both use named `Alpine.data()` components, so CSP-Alpine is unaffected
  either way.
- **DOMPurify sanitization**: mermaid runs its own SVG output through **DOMPurify** before returning
  it from `mermaid.render()` (unless `securityLevel` is `"loose"`), stripping inline event handlers
  and dangerous SVG constructs. Default `securityLevel` is `"strict"` (HTML-encodes text in labels);
  `"loose"` allows raw HTML in labels and enables click-interaction callbacks — **FLS should keep the
  default `"strict"` (or `"antiscript"`)** rather than opt into `"loose"`, since course-content
  authors are semi-trusted at best and the markdown pipeline already sanitizes via `nh3` upstream —
  no reason to re-open an HTML injection surface inside diagram labels.
  [Mermaid security docs](https://mermaid.js.org/community/security.html) ·
  background: [Snyk Labs — exploiting diagram renderers](https://labs.snyk.io/resources/exploiting-diagram-renderers/)
- **`unsafe-eval` / CSP `script-src`**: no evidence found that self-hosted mermaid (loaded as a plain
  `<script defer src=".../mermaid.min.js">`, i.e. **not** doing its own dynamic `import()` of extra
  chunks — that only happens in the ESM build, which FLS should not use, see §1) requires
  `unsafe-eval`. Mermaid's diagram grammars used to be generated by Jison (compile-time
  grammar-to-JS, not a runtime `eval`) and are being progressively migrated to a Langium-based parser
  (also compile-time codegen); neither is documented as needing runtime `eval`/`new Function()` in
  the browser. The `new Function()` CSP violations found in web search were in **third-party
  wrapper** libraries that dynamically `import()` mermaid from a CDN URL at runtime (e.g. Streamdown,
  [vercel/streamdown#344](https://github.com/vercel/streamdown/issues/344)) — that pattern doesn't
  apply here since FLS vendors the file directly and loads it with a static `<script defer>` tag, same
  as KaTeX. No `mermaid-js/mermaid` GitHub issue was found reporting `unsafe-eval` as required for
  self-hosted/UMD usage.
- **Inline `<style>` / `style-src`**: mermaid embeds a `<style>` block *inside each rendered SVG's own
  `<defs>`* for diagram theming (see §on theming below) — this is scoped to the SVG element mermaid
  returns, not injected into `<head>` or as a page-level inline `<style>` tag, so it doesn't trigger a
  `style-src` violation under a strict CSP the way inline `style="..."` attributes on regular HTML
  elements would. FLS's current `SECURE_CSP_REPORT_ONLY` already allows `CSP.UNSAFE_INLINE` for
  `style-src` (report-only mode), so this is a non-issue today regardless; worth re-checking only if
  FLS later tightens `style-src` to nonce/hash-based.
- **Net assessment**: no CSP blockers found for the "vendor `mermaid.min.js`, load via `<script defer>`,
  drive via `Alpine.data()`" approach — same posture as KaTeX today.

## 4. Diagram types — and what "herringbone diagrams" actually means

Modern mermaid (v11.16.0) documents the following diagram types (from the
[mermaid.js.org syntax nav](https://mermaid.js.org/intro/) /
[mermaid.ai docs mirror](https://mermaid.ai/open-source/syntax/examples.html)):

**Established types**: Flowchart, Sequence Diagram, Class Diagram, State Diagram, Entity
Relationship (ER) Diagram, User Journey, Gantt, Pie Chart, Quadrant Chart, Requirement Diagram,
GitGraph (Git), C4 Diagram, Mindmap, Timeline, ZenUML, Swimlanes.

**Newer/marked-experimental types**: Sankey, XY Chart, Block Diagram, Packet, Kanban, Architecture,
Radar, Event Modeling, Treemap, Venn, **Ishikawa**, Wardley, Cynefin, TreeView.

**"Herringbone diagrams" — resolved, not a red herring**: this is **not** a separate/nonexistent
mermaid type the idea author invented. Mermaid's own docs for the Ishikawa diagram type state
verbatim: *"They are also known as fishbone diagrams, herringbone diagrams or cause-and-effect
diagrams."* — i.e. **"Ishikawa diagram" is mermaid's canonical name, and "herringbone diagram" is a
listed synonym mermaid itself uses**, describing the classic fishbone/cause-and-effect diagram shape
(a "spine" problem statement with branching "bones" of causes).
[mermaid.js.org/syntax/ishikawa.html](https://mermaid.js.org/syntax/ishikawa.html) ·
[mermaid.ai/open-source/syntax/ishikawa.html](https://mermaid.ai/open-source/syntax/ishikawa.html) ·
announcement: [mermaid.ai blog — "Root Cause Analysis Gets a Diagram: Introducing Fishbone in
Mermaid.js"](https://mermaid.ai/blog/posts/root-cause-analysis-gets-a-diagram-introducing-fishbone-in-mermaid)

Practical implications for the idea owner:
- **Version requirement**: Ishikawa/fishbone support landed in **mermaid v11.12.3+**
  (per the docs page header "Ishikawa diagram (v11.12.3+)"). The idea's "use a modern version of
  mermaid, we need things like herringbone diagrams" is directly satisfiable by vendoring current
  11.16.0 — just needs to be ≥ 11.12.3, which current is.
  [GitHub tracking issue #4784](https://github.com/mermaid-js/mermaid/issues/4784)
- **Beta/unstable syntax**: the docs explicitly warn *"This is a new diagram type in Mermaid. Its
  syntax may evolve in future versions"*, and the keyword to start such a diagram is literally
  `ishikawa-beta` (mirroring mermaid's convention for other in-flux types, e.g. `block-beta`,
  `packet-beta`). The future spec should flag this as **not syntax-stable** — content authors using
  it should expect possible breakage on future mermaid version bumps, and FLS may want to pin a
  specific mermaid version rather than "always latest" for this reason (this generalizes to several
  of the other 🔥-marked newer types too — Kanban, Architecture, Radar, Treemap, etc. are all also
  post-v11 additions with varying stability).
- Basic shape of the syntax (first line = effect/problem statement, indented following lines =
  causes, indentation encodes the fishbone branch hierarchy) confirms this is exactly the classic
  Ishikawa/fishbone/herringbone diagram, not something else.

**Recommendation for the idea refinement**: no ambiguity to resolve — advise the idea owner that
"herringbone diagram" = mermaid's Ishikawa/fishbone diagram type, available and named exactly that in
mermaid's own docs, but call out its beta status so the spec can decide whether to support it at
launch or flag it as "supported, syntax may shift under us."

## 5. Async/render-timing considerations

- `mermaid.render()` is `async`/Promise-returning (see §2) — never synchronous, unlike `katex.render()`
  which mutates the DOM synchronously in `equation`'s `init()`. The Alpine `init()` for `mermaid` must
  itself be an `async` function (or use `.then()`); Alpine supports this fine — it just calls `init()`
  once during component initialization and doesn't block on its return value, so a `mermaid` component
  whose `init()` is `async function init() { ... await window.mermaid.render(...) ... }` behaves
  correctly: the rest of the page continues initializing while the diagram render resolves in the
  background, then the DOM is patched once the promise settles.
- **FOUC / layout-shift**: because rendering is async, there is a window (typically small — single-
  digit to low-double-digit milliseconds for simple diagrams, longer for large/complex ones since
  layout is computed via dagre/ELK) where the widget shows either nothing, the raw mermaid source
  text, or a placeholder before the SVG swaps in. Recommend mirroring `equation`'s degrade-gracefully
  approach: keep the raw source visible (in a `hidden`-toggled `x-ref="src"`) until the SVG is
  successfully rendered into `x-ref="out"`, then flip visibility — so slow/failed renders show *raw
  mermaid text* rather than a blank box, exactly analogous to `equation`'s `throwOnError:false`
  fallback-to-source behavior for malformed LaTeX. This avoids a jarring "diagram pops in" FOUC (raw
  text has some height already) at the cost of a brief flash of unstyled source, and avoids a
  fully-blank layout-shifting placeholder.
- Because diagram SVGs mermaid returns are typically given explicit `width`/`height` (or
  `viewBox` + intrinsic sizing) in the SVG root, once rendered the layout is stable; the only shift
  risk is the initial source-text → SVG swap itself, not post-render reflow.
- **Theming note** (relevant since the idea says "styled according to the current theme"): mermaid
  supports `theme: "base"` + a `themeVariables` object of **hex-color** values (no CSS variable/color-name
  passthrough) supplied to `mermaid.initialize()` once, globally, before any `render()` calls — this
  is the mechanism a future spec would use to line diagram colors up with FLS's Tailwind theme tokens
  (would need to resolve the site's active theme's hex values server-side or via a small bit of JS
  reading computed CSS custom properties, then pass them into `initialize()`).
  [Theme Configuration docs](https://mermaid.js.org/config/theming.html)

## Files studied (existing FLS pattern)

- `freedom_ls/content_engine/templates/cotton/equation.html` — cotton component shape to mirror.
- `freedom_ls/content_engine/static/content_engine/js/alpine-components.js` — `Alpine.data("equation", ...)` registration pattern (CSP-Alpine, `alpine:init` listener, degrade-on-failure).
- `freedom_ls/student_interface/templates/student_interface/_course_base.html` and `_exam_runner_base.html` — where the KaTeX vendor script/css and `alpine-components.js` are loaded via `<script defer>`/`<link>`.
- `config/settings_base.py` — `MARKDOWN_ALLOWED_TAGS` (new `c-mermaid` tag + its attrs will need an entry here) and `SECURE_CSP_REPORT_ONLY` (currently permissive/report-only; no changes needed for mermaid per §3).

status: ok
