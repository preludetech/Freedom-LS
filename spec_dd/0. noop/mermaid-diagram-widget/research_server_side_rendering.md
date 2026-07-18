# Research: Server-side rendering of Mermaid diagrams (SVG instead of shipping 3.4 MB `mermaid.min.js`)

Research date: 2026-07-17.

## Summary / recommendation up front

Every faithful mermaid renderer — official or third-party — ultimately needs mermaid's own JS
running against **either a real browser DOM or a very convincing fake one**, because mermaid's
layout (dagre/ELK graph layout, text measurement via `getBBox`/`getComputedTextLength`) is done by
walking real (or faked) DOM APIs, not by a portable pure-data layout algorithm. There is **no
mature, widely-used, browser-free renderer** that FLS should bet content-rendering infrastructure
on today (see §3) — the one credible non-browser project (`mermaidx`) is a single-maintainer,
43-star, days-old-relative-to-mermaid-11 effort using a hand-built fake DOM.

Given that, "server-side render" for FLS concretely means **"introduce a headless-Chromium
dependency into the render path,"** whether that's mermaid-cli, Kroki, or a Playwright script.
**Kroki, self-hosted via Docker Compose, is the strongest fit if FLS goes this route** — it's an
HTTP service (matches Django's "call an HTTP API, get bytes back" comfort zone far better than
shelling out to Node), it isolates the headless-Chromium blast radius (fonts, sandboxing, crashes)
into its own container instead of FLS's app/worker processes, and it's designed to be called
per-request-with-caching rather than embedded in a request thread. But it is still a **new stateful
service to deploy, monitor, and keep patched** (Java gateway + Node/Puppeteer companion + Chromium),
and FLS has no existing cache framework (`CACHES`) or background-job runner configured today — both
would need to be added to make "render once, cache forever" actually work.

The **client-side `mermaid.min.js` (3.4 MB, browser-cached after first load) is materially simpler
operationally**: zero new services, zero new infra, zero cache-invalidation-on-edit logic, and it's
the same shape as the KaTeX pattern FLS already ships. The tradeoff is purely a one-time ~3.4 MB
download per browser (browser-cached thereafter, only loaded on pages that actually render
diagrams) versus taking on a headless-browser service in production. See §5 for the balanced
comparison this is meant to feed into a spec decision — this file does not pick a winner.

---

## 1. Approaches to render mermaid → SVG on the server

### 1a. `mermaid-cli` (`@mermaid-js/mermaid-cli`, binary `mmdc`)

- **What it is**: the official CLI, published by the mermaid org. Given a `.mmd` source file (or
  piped diagram text / a Markdown file with fenced mermaid blocks), it drives **Puppeteer → a real
  headless Chromium** to load mermaid.js in an actual page context, call `mermaid.render()` inside
  that page, and pull the resulting SVG (or rasterize to PNG/PDF) back out.
  [GitHub: mermaid-js/mermaid-cli](https://github.com/mermaid-js/mermaid-cli)
- **Why it needs a browser at all**: this is the same fundamental constraint as §3 — mermaid's own
  layout code calls into DOM text-measurement APIs, so `mmdc` is really just "boot mermaid.js inside
  a real browser and script it," not a separate renderer.
- **Output formats**: SVG (default), PNG, PDF — `mmdc -i input.mmd -o output.svg`.
- **Theming**: `-t <theme>` (`default`/`dark`/`forest`/`neutral`/`base`), `-c config.json` (passed
  straight into `mermaid.initialize()`, so `themeVariables` hex-color overrides work exactly as in
  the client-side API researched in `research_mermaid_integration.md` §5), and `--cssFile` for raw
  CSS injection (docs note `themeCSS` overrides sometimes need `!important` to win).
- **Containerization pain**: this is real and well-documented.
  - Puppeteer/Chromium under Docker/root needs `--no-sandbox` (Chrome refuses to run as root with
    the sandbox enabled) — passed via a mounted `puppeteer-config.json` /
    `--puppeteerConfigFile`. The official image's `ENTRYPOINT` already wires this up, but any custom
    container build has to reproduce it correctly or renders fail outright.
    [DeepWiki: Puppeteer Configuration in Docker](https://deepwiki.com/mermaid-js/mermaid-cli/4.2-puppeteer-configuration-in-docker)
  - **Fonts**: the official Alpine-based image bundles `font-noto-cjk`, `font-noto-emoji`,
    `ttf-dejavu`, `ttf-freefont`, `ttf-font-awesome`, `ttf-inconsolata`, `ttf-linux-libertine`, then
    rebuilds the font cache (`fc-cache -f`) — i.e. "just install Chromium" is not enough; you also
    own a font-package maintenance burden inside the image or diagram text renders with tofu/missing
    glyphs.
  - Official Docker image: `minlag/mermaid-cli` on Docker Hub, with alternatives like
    `matthewfeickert/mermaid-cli` and `ahmadnassri/docker-mermaid-cli` reflecting how much community
    effort has gone into "just get this to run reliably in a container."
    [minlag/mermaid-cli](https://hub.docker.com/r/minlag/mermaid-cli) ·
    [matthewfeickert/mermaid-cli](https://hub.docker.com/r/matthewfeickert/mermaid-cli) ·
    [ahmadnassri/docker-mermaid-cli](https://github.com/ahmadnassri/docker-mermaid-cli)
  - Per-render cost: booting a headless Chromium instance is not free — community writeups cite
    roughly **2–3 seconds of overhead per invocation** when `mmdc` is invoked fresh per diagram
    (process boot + page load), which is the strongest argument for build-time/cached rendering over
    request-time rendering (see §2).
- **Suitability for FLS**: `mmdc` is a Node CLI, invoked as a subprocess. FLS's production runtime is
  Python/uv-managed with Node only present for the Tailwind build step — shelling out to `mmdc` from
  a Django management command (author-save-time render, see §2) is plausible **if Node + Chromium are
  added to the deploy image**; using it at Django request-time (spawn a subprocess per HTTP request)
  is the "bad" option flagged in the research brief and should be ruled out regardless of tool choice.

### 1b. Kroki (self-hosted)

- **What it is**: a self-hostable HTTP diagram-rendering gateway supporting many diagram languages
  (Mermaid, PlantUML, GraphViz, D2, Excalidraw, BPMN, etc.) behind one uniform API — POST diagram
  source, get image bytes back. [GitHub: yuzutech/kroki](https://github.com/yuzutech/kroki) ·
  [kroki.io](https://kroki.io/)
- **Architecture**: a core Java gateway (`yuzutech/kroki` image, port 8000) plus optional
  **companion microservices** for languages the JVM can't render natively — Mermaid, BPMN, and
  Excalidraw each get their own container (`yuzutech/kroki-mermaid` on port 8002 by default), wired
  together via env vars like `KROKI_MERMAID_HOST=mermaid` in a Docker Compose file, using Docker's
  internal service discovery.
  [Docker Compose examples](https://github.com/sphinx-contrib/kroki/blob/master/docker-compose.yml) ·
  [Kroki Docker/Podman install docs](https://docs.kroki.io/kroki/setup/install/)
- **Confirms §3, not an exception to it**: the `kroki-mermaid` companion is itself a **Node.js
  microservice built on Puppeteer**, running mermaid.js against headless Chrome internally — Kroki
  does **not** avoid the browser dependency, it just **isolates and containerizes it** as a separate
  service with its own lifecycle, rather than embedding it in the app process. The companion enforces
  its own render timeout (default **10 seconds**; a render that exceeds it is aborted and returns
  HTTP 408). [DeepWiki: Mermaid and BPMN Services](https://deepwiki.com/yuzutech/kroki/5.1-mermaid-and-bpmn-services)
- **HTTP API**: Django would call this like any other HTTP service — no subprocess, no Node
  toolchain in the Django deploy image itself:
  ```
  POST /mermaid/svg
  Content-Type: text/plain
  Accept: image/svg+xml

  graph TD; A-->B;
  ```
  or a JSON body `{"diagram_source": "...", "diagram_type": "mermaid", "output_format": "svg"}`.
  There's also a stateless GET form (deflate+base64-encoded diagram in the URL path) intended for
  embedding Kroki URLs directly in `<img src>` tags — not relevant to FLS since we want to store SVG
  server-side, not hotlink an external image URL at page-render time.
  [Kroki usage docs](https://docs.kroki.io/kroki/setup/usage/)
- **Theming pass-through**: diagram options (including mermaid's `theme`/`themeVariables`) can be
  supplied via the JSON body's `diagram_options`, `Kroki-Diagram-Options-*` headers, or query params
  (in that precedence order) — or via mermaid's own YAML frontmatter block embedded in the diagram
  source itself (`---\nconfig:\n  theme: base\n  themeVariables: {...}\n---`), which Kroki forwards
  to the mermaid companion unchanged. Kroki's own option-naming quirk: dotted mermaid option names
  get kebab-cased with underscore-for-dot (e.g. `er.titleTopMargin` → `er_title-top-margin`).
  [Kroki Diagram Options docs](https://docs.kroki.io/kroki/setup/diagram-options/) ·
  [Mermaid theming docs](https://mermaid.ai/open-source/config/theming.html)
- **Caching**: **Kroki itself does not cache render results** — every POST re-renders. This is
  explicitly the expectation baked into how people integrate it: multiple third-party
  build-tool plugins (e.g. `mkdocs-kroki-plugin`) implement their **own** client-side cache keyed on
  diagram-source hash precisely because Kroki won't do it for you.
  [mkdocs-kroki-plugin README](https://github.com/AVATEAM-IT-SYSTEMHAUS/mkdocs-kroki-plugin) — this
  matches what FLS would need to build regardless (§2): a hash-of-source → cached-SVG layer sitting
  in front of whichever renderer is chosen.
- **Resource footprint**: minimum viable self-host is 2 containers just for mermaid support (Java
  gateway + Node/Puppeteer companion), each with their own memory floor (JVM heap + a Chromium
  process). This is non-trivial compared to FLS's current all-Python/Postgres deploy footprint.
- **Suitability for FLS**: of the browser-driving options, this is the best-shaped for a Django app
  — it's "call an internal HTTP service," no subprocess management, no Node in the Django image,
  and the multi-diagram-language support is a bonus if FLS content authors ever want PlantUML/D2/etc.
  The cost is operating a genuinely new service (or two) in the deploy topology.

### 1c. Python wrappers (`mermaid-py`, `mermaid-cli` (PyPI), `mmdc`/`mermaidx`)

Several PyPI packages exist under confusingly similar names — worth being precise about which ones
actually render locally vs. just call a remote/self-hosted HTTP service:

- **`mermaid-py`** (PyPI) — a Python DSL for *building* diagram source, whose rendering by default
  calls the **public `mermaid.ink`** hosted service (an external SaaS dependency — a red flag per
  FLS's self-hosting preference). It does support pointing `MERMAID_INK_SERVER` at a **self-hosted**
  `mermaid.ink` instance instead (mermaid.ink itself ships a Dockerfile built on
  `ghcr.io/puppeteer/puppeteer`, i.e. still a headless-Chromium service under the hood, same category
  as Kroki's mermaid companion but single-purpose rather than multi-language).
  [PyPI: mermaid-py](https://pypi.org/project/mermaid-py/) ·
  [jihchi/mermaid.ink](https://github.com/jihchi/mermaid.ink) ·
  [mermaid.ink Dockerfile](https://github.com/jihchi/mermaid.ink/blob/main/Dockerfile)
- **`mermaid-cli` (PyPI, distinct from the npm package of the same name)** — a Python port that
  **drives Playwright directly** (`playwright install chromium`, then an async `render_mermaid()`
  call), with no Node.js or npm `mmdc` involved at all. This is architecturally the closest thing to
  "1d done as a reusable library" — same headless-Chromium dependency, but packaged as a pip
  install + `playwright install chromium` rather than an npm dependency. Beta status, single
  maintainer, most recent release Feb 2026. [PyPI: mermaid-cli](https://pypi.org/project/mermaid-cli/)
- **`mmdc` → renamed `mermaidx`** — the one genuine attempt at a **non-browser** Python renderer:
  runs mermaid.js v11 (the real, unmodified library, not a reimplementation) inside an embedded
  **QuickJS-ng** JS engine against a hand-built fake DOM/SVG implementation, with text metrics bridged
  back to Python via a bundled DejaVu Sans font so `getBBox`-equivalent calls return plausible
  numbers without a real layout engine. PNG via `resvg`, PDF via a hand-written stdlib-only writer.
  Genuinely interesting and directly relevant to §3, but: 43 GitHub stars, single maintainer
  (Mohammad Raziei), beta, and its own test suite explicitly does *structural* comparison against
  real mermaid output ("labels + aspect ratio, not pixel-diffing — two different rendering engines
  never match pixel-for-pixel"), i.e. the project itself doesn't claim pixel-fidelity with the
  official renderer. **Not something to bet FLS's course-content rendering pipeline on today**, but
  worth revisiting if it matures. [GitHub: MohammadRaziei/mermaidx](https://github.com/MohammadRaziei/mermaidx) ·
  [PyPI: mmdc](https://pypi.org/project/mmdc/)

**Net**: no Python wrapper avoids the browser-or-fake-DOM constraint from §3; the `mermaid-py`
default path is an external-SaaS red flag unless pointed at a self-host; the PyPI `mermaid-cli`
package is functionally identical to §1d below, just pre-packaged.

### 1d. Playwright-driven in-process render (reusing FLS's existing Playwright)

- **Feasibility**: yes, this is realistic as a **build-time / management-command** step, and is
  exactly what the PyPI `mermaid-cli` package above does under the hood: launch headless Chromium via
  Playwright, `page.set_content()` a minimal HTML shell that loads `mermaid.esm.min.mjs` (or the
  vendored `mermaid.min.js` FLS already plans to ship for the client-side widget — see
  `research_mermaid_integration.md`), call `await page.evaluate("mermaid.render(...)")` inside the
  page context, and pull `svg` back out via the evaluate return value. No new npm/Node package is
  strictly required beyond Playwright itself (already a dev/test dependency) plus the mermaid bundle
  FLS would vendor anyway.
- **Fragility concerns**:
  - This becomes **bespoke, FLS-maintained rendering infrastructure** rather than an
    off-the-shelf tool — every mermaid version bump, every diagram type's rendering quirk, every
    font-availability issue becomes FLS's problem to debug, instead of upstream `mmdc`'s or Kroki's.
  - Playwright's browser binaries (`playwright install chromium`) are a **dev/test-time** artifact
    today (installed for the `fls:playwright-tests` skill's Playwright MCP usage); using the *same*
    browser install as a **production content-rendering dependency** changes its operational
    category — it now needs to exist in the production deploy image, be kept patched, and be
    resourced (memory/CPU headroom for a Chromium process) on whatever host runs the render step.
    That's a meaningfully different commitment than "Playwright exists for CI E2E tests."
  - Concurrency/pooling: rendering many diagrams (e.g. re-rendering all content after a mermaid
    version bump) means either serializing through one browser instance/page (slow) or managing a
    small browser pool — infra FLS would have to write itself, whereas `mmdc`/Kroki already handle
    single-shot process lifecycle for you.
- **Verdict**: technically doable as a management command (`render_mermaid_diagrams` or similar)
  invoked at build/deploy/save time, and has the appeal of "no new external service, reuse what's
  already in the toolchain" — but it trades a maintained tool (mermaid-cli or Kroki) for bespoke glue
  code FLS owns forever. Reasonable **prototype/spike** option, weaker as a long-term-maintenance
  choice versus Kroki (§1b) if going server-side at all.

---

## 2. When to render — fitting FLS's `rendered_content()` pipeline

FLS's existing pipeline (`freedom_ls/markdown_rendering/markdown_utils.py::render_markdown`, called
from `MarkdownContent.rendered_content()` in `freedom_ls/content_engine/models.py`) is **synchronous,
per-request, and uncached today**: markdown → `nh3.clean()` → Cotton component compile+render,
recomputed on every call (no memoization observed in the reviewed code). A `c-mermaid` cotton
component would currently be evaluated inside that same synchronous per-request path.

Three placement options for a hypothetical server-side mermaid render step:

1. **Request-time, uncached (ruled out)**: rendering mermaid → SVG requires booting/round-tripping a
   headless browser (or Kroki HTTP call) **inside a Django request-response cycle**. Given §1a's
   ~2–3s-per-diagram overhead for a cold `mmdc` invocation (Kroki's warm companion service would be
   faster per-call but still adds network + browser-render latency, plus its own 10s internal
   timeout), this would make page loads with diagrams unacceptably slow and fragile (browser
   crash/timeout = broken page). Confirms the research brief's framing — this is the bad option.
2. **On-demand-with-caching (first view renders, then cached)**: closer to viable, but the "first
   ever request for freshly-saved content" still pays the request-time cost above unless the cache is
   warmed asynchronously (e.g. `render_markdown` kicks off a background task rather than rendering
   inline, serving the raw mermaid source or a placeholder until the async render lands). This needs
   a task queue FLS does not currently appear to have configured (no Celery/RQ/Django-Q references
   found in this pass) — an added piece of infrastructure either way.
3. **Build-time / author-save-time (best fit)**: render mermaid → SVG **when an author saves**
   `Topic`/`Activity`/`Course`/`Form`/`FormContent` content (a `post_save` signal, a model `save()`
   override, or an admin/editor-workflow hook), store the resulting SVG (or the full rendered-HTML
   fragment with SVG inlined) keyed by a **hash of the mermaid source + site/theme** (see §4), and
   have `rendered_content()` look up the cached SVG instead of invoking a renderer inline. This
   mirrors how `rendered_content()` already treats markdown source as the input and produces safe
   HTML as output — the mermaid render step slots in as "pre-computed, cached HTML fragment" the same
   way the rest of the pipeline could theoretically be cached, just doesn't need to be today because
   markdown+nh3+cotton is fast/pure-Python. **Diagram rendering is the first stage in this pipeline
   that has good reason to be pre-computed and cached rather than run per-request**, because it's the
   first stage that needs a browser.
- **Where to store it**: given FLS has **no `CACHES` backend configured** in `config/settings_base.py`
  today (Django defaults to `LocMemCache`, which is per-process and not shared across gunicorn
  workers/replicas — unsuitable for "author saves once, all readers get the cached SVG"), the two
  realistic homes are: (a) a **new model field** (e.g. a `rendered_diagrams` JSON/text field or a
  small `RenderedDiagram(source_hash, site, svg, rendered_at)` table) that persists in Postgres
  alongside the content it belongs to, or (b) introducing a real shared cache backend
  (Redis/Memcached) as new infrastructure. A DB-backed cache is more consistent with FLS's current
  "Postgres is the source of truth, no cache layer yet" posture and survives deploys/restarts without
  extra infra, at the cost of a migration and slightly more bespoke invalidation logic than
  `django.core.cache`'s built-in key expiry would give for free.
- **Cache invalidation on edit**: content-hash keying (hash of the mermaid source text, plus the
  site's active theme identifier — see §4) makes this mostly self-invalidating: editing the diagram
  source changes the hash, so the old cached SVG is simply never looked up again (stale rows can be
  garbage-collected later, or left as harmless orphans). This avoids needing an explicit
  "invalidate cache on save" signal beyond "compute the new hash and render-or-fetch-from-cache" —
  simpler than TTL-based invalidation.

---

## 3. The headless-browser dependency problem — is there a browser-free mermaid renderer?

**Short answer: no mature one, and this is confirmed by mermaid's own maintainers/community, not
just inferred.** A GitHub Discussion opened specifically to ask about non-browser rendering
libraries states plainly: *"the reason for the dependency on a web browser is because that gives
access to the browser's layout engine"* and that mermaid's layout needs *"optimizations based on
knowledge about font families and sizes... This can only be done at the user agent level."* The same
discussion notes mermaid's SVG **output** itself often fails to render correctly in non-browser SVG
consumers (Apache Batik, EchoSVG, `rsvg-convert`, CairoSVG, Adobe tools), independent of the
rendering step — reinforcing that mermaid is designed browser-first end to end.
[mermaid-js/mermaid Discussion #7085 — "Render diagrams using non-browser-based rendering
libraries"](https://github.com/orgs/mermaid-js/discussions/7085)

What exists in the "avoid a real browser" space, and how far each really gets:

- **`mermaidx`/`mmdc`** (§1c) — the most serious attempt: runs the *actual* mermaid.js library
  against a **hand-built fake DOM** (QuickJS-ng + bundled font metrics) rather than a real browser.
  This is "no Chromium process," but it is **not** "no DOM emulation" — it's a from-scratch
  reimplementation of just enough of `getBBox`/text-measurement to satisfy mermaid's layout code.
  Its own test suite disclaims pixel-fidelity with real mermaid output. Single-maintainer, 43 stars,
  beta. A genuinely interesting emerging option, not yet a safe production dependency.
  [GitHub: MohammadRaziei/mermaidx](https://github.com/MohammadRaziei/mermaidx)
- **`mmdr`** (Rust) — advertised as parsing mermaid syntax natively in Rust with no browser, claiming
  large speedups; found via search but not independently verified here — treat as an early-stage,
  unverified community project rather than a mermaid-compatible drop-in (mermaid's grammar surface is
  large and evolving; a from-scratch Rust reimplementation reproducing all diagram types' layout
  behavior faithfully is a big claim). Not recommended for further evaluation without much deeper
  vetting.
- **EchoSVG (Java)** — mentioned in the mermaid discussion above as now supporting some mermaid
  rendering via `CSSTranscodingHelper`, but results are explicitly described as "far from perfect"
  and prone to omitting overflowing text in complex flowcharts — not a credible production option.
- **Graphviz / D2** — pure native renderers, but for **different diagram languages**, not
  mermaid-syntax-compatible; irrelevant unless FLS were willing to abandon mermaid syntax entirely
  (out of scope — the idea explicitly asks for mermaid, including new types like Ishikawa/fishbone).

**Conclusion for FLS**: treat "mermaid server-side render" and "headless-Chromium (or a
still-unproven fake-DOM engine) dependency" as effectively synonymous for planning purposes. There is
no way to get faithful, all-diagram-type mermaid rendering server-side today without taking on either
a real browser (mermaid-cli, Kroki, Playwright) or a young single-maintainer alternative
(`mermaidx`) that isn't yet a safe bet for a production content pipeline.

---

## 4. Theming server-side

- **Mechanism**: identical shape to the client-side API researched in
  `research_mermaid_integration.md` §5 — mermaid takes a `theme: "base"` + `themeVariables: {...}`
  (hex-color values only, no CSS-variable passthrough) object at `mermaid.initialize()` time. Both
  `mmdc` (`-c config.json`) and Kroki (`diagram_options` / mermaid YAML frontmatter, §1b) forward this
  straight through to that same API — there's no separate "server theming" mechanism, it's the exact
  same config surface, just supplied out-of-band (CLI flag / HTTP option) instead of via a page-load
  JS call. [Mermaid theme config docs](https://mermaid.ai/open-source/config/theming.html)
- **Per-site theming and the cache key**: since FLS themes are per-site static CSS-custom-property
  bundles (no runtime dark toggle — per the brief), a server render has to **resolve the site's theme
  hex values ahead of the render call** (there's no way to hand the renderer a CSS-variable reference
  and have it resolve at render time — mermaid's `themeVariables` wants literal hex strings). This
  means:
  - FLS needs a small Python-side mapping from "site's active theme" → the handful of hex values
    mermaid's `themeVariables` expects (primary/secondary/background/text/border colors etc.) — this
    mapping has to be maintained in parallel with whatever defines the CSS custom-property theme
    bundles today, i.e. **a second place themes are defined**, which is a real maintenance cost
    (drift risk: someone changes a theme's CSS token but forgets the mermaid hex-mapping).
  - The **cache key** (§2) must include the site/theme identifier alongside the content hash — e.g.
    `hash(mermaid_source + site.theme_id)` — so each site gets a correctly-themed SVG and edits to
    either the diagram *or* the theme correctly invalidate the cached render. This is a straightforward
    extension of the content-hash cache design, but it does mean **a theme change requires
    re-rendering every cached diagram on that site** (a bulk re-render management command, not just a
    lazy per-page invalidation), which is extra operational surface not needed by the client-side
    approach (client-side, theme changes are just CSS — no re-render step at all, since `mermaid.render()`
    runs fresh in the visitor's browser using whatever theme values are read at that moment).
- **Net**: theming is *possible* server-side and uses the same config surface as client-side, but it
  adds a second source-of-truth for theme color values and a bulk-re-render obligation on theme
  changes that the client-side approach doesn't have.

---

## 5. Net recommendation (balanced, feeds a decision — not a verdict)

**Client-side (`mermaid.min.js`, ~3.4 MB, browser-cached, per `research_mermaid_integration.md`)**
- Zero new services, zero new infra, zero new theme-value source-of-truth, zero cache-invalidation
  logic to write. Directly mirrors the KaTeX (`c-equation`) pattern already shipped and understood in
  this codebase. Diagram edits "just work" with no re-render step. Theme changes "just work" (CSS
  only). No headless-browser operational risk in production.
- Cost is a genuinely large one-time download (only on pages using diagrams, `defer`red, browser-cached
  thereafter) and running mermaid's dagre/ELK layout + DOMPurify sanitize in every visitor's browser on
  every page load with a diagram (not amortized across visitors the way a server render+cache would
  be) — a real but bounded and well-understood cost, same category as any large JS vendor library.

**Server-side render + cache SVG (browser gets 0 JS for diagrams)**
- Genuine payoff: **zero mermaid JS shipped to the browser at all**, diagrams are just `<svg>` in the
  HTML, which is strictly lighter and faster for the *reader* than even a cached 3.4 MB bundle (no JS
  parse/execute cost, no client-side layout computation, works with JS disabled).
- Real cost, understood soberly: this is not "add a Python library" — it is **taking on a
  headless-Chromium dependency somewhere in the system** (§3 confirms there's no faithful
  browser-free alternative today). Concretely that means either:
  - A **new self-hosted service** (Kroki, §1b — the best-shaped option of the three, being an HTTP
    API rather than a subprocess/library) that needs deploying, monitoring, resourcing (JVM + Node +
    Chromium memory floor), and keeping patched against Chromium CVEs indefinitely; **or**
  - **Bespoke Playwright-driven render code** (§1d) that FLS authors and maintains itself, reusing
    Playwright's existing dev/test presence but promoting it to a production content-rendering
    dependency — less new "infra," more new "code FLS owns forever."
  - Either way, FLS also needs to add a **caching layer that doesn't exist today** (no `CACHES`
    backend configured currently) — realistically a DB-backed rendered-diagram table keyed on
    content-hash + site/theme (§2, §4) — plus a background-render trigger (save-time hook or async
    task queue, itself new infra if FLS has none today) to keep rendering off the request path.
  - Theme changes become a **bulk re-render obligation** (§4) rather than "just CSS."

**Given FLS is Django-first, self-hosting-preferring, and does not currently run a background task
queue or a shared cache backend**, server-side rendering is not a small increment on top of the
client-side approach — it's a materially larger infrastructure commitment (new service or new
maintained render code + new cache storage + new invalidation/bulk-re-render logic) purchased in
exchange for a real but bounded UX win (0 KB of diagram JS vs. a `defer`red, browser-cached 3.4 MB
bundle). This tradeoff should be made explicitly and revisited if/when the client-side bundle size
proves to be an actual measured problem (e.g. via real user monitoring) rather than a theoretical one
— at which point Kroki (self-hosted) is the concrete recommendation among the server-side options,
given it's the only one of the three that isn't either an external SaaS dependency (`mermaid.ink`
default) or bespoke FLS-maintained render code (Playwright-in-process).

---

## References

- [mermaid-js/mermaid-cli (GitHub)](https://github.com/mermaid-js/mermaid-cli)
- [DeepWiki: mermaid-cli Docker Support](https://deepwiki.com/mermaid-js/mermaid-cli/4-docker-support) ·
  [Puppeteer Configuration in Docker](https://deepwiki.com/mermaid-js/mermaid-cli/4.2-puppeteer-configuration-in-docker)
- [minlag/mermaid-cli Docker image](https://hub.docker.com/r/minlag/mermaid-cli)
- [yuzutech/kroki (GitHub)](https://github.com/yuzutech/kroki) ·
  [kroki.io](https://kroki.io/) ·
  [Kroki install docs](https://docs.kroki.io/kroki/setup/install/) ·
  [Kroki usage docs](https://docs.kroki.io/kroki/setup/usage/) ·
  [Kroki diagram options docs](https://docs.kroki.io/kroki/setup/diagram-options/) ·
  [DeepWiki: Mermaid and BPMN companion services](https://deepwiki.com/yuzutech/kroki/5.1-mermaid-and-bpmn-services)
- [PyPI: mermaid-py](https://pypi.org/project/mermaid-py/) ·
  [jihchi/mermaid.ink (GitHub)](https://github.com/jihchi/mermaid.ink)
- [PyPI: mermaid-cli (Playwright-based Python port)](https://pypi.org/project/mermaid-cli/)
- [PyPI: mmdc](https://pypi.org/project/mmdc/) ·
  [GitHub: MohammadRaziei/mermaidx](https://github.com/MohammadRaziei/mermaidx)
- [mermaid-js/mermaid Discussion #7085 — non-browser rendering](https://github.com/orgs/mermaid-js/discussions/7085)
- [Mermaid Theme Configuration docs](https://mermaid.ai/open-source/config/theming.html)
- Files studied in this repo: `freedom_ls/content_engine/models.py` (`MarkdownContent.rendered_content()`),
  `freedom_ls/markdown_rendering/markdown_utils.py` (`render_markdown()`), `config/settings_base.py`
  (confirmed no `CACHES` backend configured today).

status: ok
