# Research: lighter-weight alternatives to Mermaid.js for `<c-mermaid>`

Research date: 2026-07-17. Companion to `research_mermaid_integration.md` (which established mermaid's
self-hosted `mermaid.min.js` is **~3.4 MB minified**, and that "herringbone" = mermaid's native
`ishikawa-beta` diagram, added v11.12.3+).

## Verdict up front

**No lighter client-side JS/WASM library matches mermaid's diagram-type breadth — least of all its
fishbone/Ishikawa support, which mermaid appears to be the only tool in this survey with *native*
support for.** The realistic choice-set for FLS is:

1. **Mermaid as-is** (3.4 MB, self-hosted, one `<script>`, broad breadth incl. native fishbone) — the
   `research_mermaid_integration.md` recommendation.
2. **A much narrower small lib** for a specific diagram family (e.g. nomnoml for class diagrams only,
   ~72 KB) used *alongside* mermaid or instead of it if the idea's scope is trimmed to just
   flowcharts/class-diagrams and fishbone is dropped or hand-approximated.
3. **Server-side rendering** (mermaid-cli/Puppeteer, or PlantUML on a self-hosted JVM server, or Kroki
   fronting multiple engines) — trades a large *client* asset for a *server-side* rendering dependency
   (headless Chromium or JVM), covered in depth by a sibling research file if one exists for
   server-side rendering; only summarized here since the prompt asked to evaluate both models.
4. **D2** looked promising on paper (modern, popular, "lighter than mermaid" reputation) but its
   **WASM binary is actually *larger* than mermaid's entire minified bundle** (~21 MB raw `d2.wasm`,
   ~8 MB `dist/browser/index.js` with the WASM base64-embedded before compression — see §1) *and* D2's
   own maintainers explicitly, permanently exclude mindmap/Gantt/Sankey/Venn/pie from scope, so it is
   neither lighter nor broader. Graphviz/viz.js is genuinely small but only draws generic node-link
   graphs (no sequence/gantt/state/pie/fishbone). PlantUML rivals or exceeds mermaid's breadth but
   requires a JVM server, not a client bundle, and — like D2/Graphviz — has **no native fishbone
   diagram either** (open feature request, unresolved since 2021).

---

## 1. Survey of alternatives

| Library | Model | Diagram types covered | Approx size | Self-hostable | Syntax maturity | License |
|---|---|---|---|---|---|---|
| **Mermaid** (baseline) | Client JS (or headless-Chromium server via mermaid-cli) | Flowchart, sequence, class, state, ER, Gantt, pie, quadrant, requirement, gitgraph, C4, mindmap, timeline, ZenUML, sankey, XY chart, block, packet, kanban, architecture, radar, treemap, venn, **Ishikawa/fishbone (native, v11.12.3+, beta)**, wardley, cynefin, treeview | `mermaid.min.js` **3.4 MB min** (~7.8 MB unmin) | Yes, one vendored file | Mature core, several 🔥beta types | MIT |
| **D2** (terrastruct) | Go binary (server CLI) **or** WASM via `@terrastruct/d2` (client, worker-thread) | Directed graphs, SQL tables, UML-class-like shapes, sequence diagrams, grid diagrams; **explicitly excludes** mindmap, Gantt, Sankey, Venn, pie by design ("D2 does none of those and will not support these") | `dist/node-cjs/d2.wasm` **~21 MB** raw; `dist/browser/index.js` **~8.2 MB** (WASM embedded as compressed base64) — [jsDelivr file listing](https://cdn.jsdelivr.net/npm/@terrastruct/d2@0.1.33/) | Yes (Go binary or WASM) | Actively developed, syntax fairly stable | MPL-2.0 |
| **Graphviz via viz.js / @viz-js/viz** | WASM (client) or `dot` binary (server) | Only generic node-link/DAG graphs (`dot`, `neato`, `circo`, etc. layout engines) — no sequence/state/gantt/pie/ER-specific syntax (ER-like output possible only by hand-crafting DOT `record` shapes) | `dist/viz.js` **~1.19 MB** (WASM embedded), no separate `.wasm` file — [jsDelivr listing](https://cdn.jsdelivr.net/npm/@viz-js/viz@3.28.0/) | Yes | Very mature (Graphviz itself is decades old); viz.js wrapper actively maintained | MIT (viz.js wrapper); EPL-1.0 (Graphviz core) |
| **PlantUML** | Server-side only (JVM; `.jar` or `plantuml/plantuml-server` Docker image) | Very broad: sequence, class, use case, activity, component, state, object, deployment, timing, network (nwdiag), WBS, mindmap, Gantt, C4 (via plugin), Salt/wireframe, JSON/YAML/EBNF/regex diagrams, ArchiMate | Docker image **~127 MB** (Jetty/Tomcat base) — no client bundle at all, all rendering is server-side PNG/SVG | Yes, but requires a JVM process/container, not a static asset | Very mature (20+ years), stable syntax | GPL/MIT-ish dual (core plantuml.jar is GPL family; check current license terms before adopting) |
| **nomnoml** | Client JS | UML **class diagrams only** (plus loosely related box/arrow "sassy" diagrams) | `dist/nomnoml.js` **~72 KB** — [jsDelivr listing](https://cdn.jsdelivr.net/npm/nomnoml@1.7.0/) | Yes, tiny vendored file | Small, stable, low diagram-type ambition | MIT |
| **flowchart.js** | Client JS | Flowcharts only | Small (~tens of KB) but **effectively unmaintained** — last significant activity years ago; syntax predates mermaid and mermaid's flowchart grammar is a superset | Yes | Stale/legacy | MIT |
| **js-sequence-diagrams** | Client JS (depends on Raphael/snap.svg for SVG rendering) | Sequence diagrams only | Small core but drags in a separate SVG rendering dependency (Raphael/snap.svg), inflating real installed size | Yes | Stale/legacy, largely superseded by mermaid's own sequence diagrams | BSD-ish |
| **svgbob** | Rust/WASM (CLI) or server-side; ASCII-art-to-SVG | Boxes/lines/simple flowcharts/sequence-ish/circuit diagrams drawn from ASCII art — a fundamentally different authoring model (draw with `-`, `|`, `/`, `\`) rather than a declarative diagram grammar | CLI tool / small WASM; not really comparable to mermaid's declarative syntax | Yes | Niche, stable for its narrow ASCII-art scope | MIT |
| **Structurizr (DSL + Lite)** | Server-side (Java/Spring Boot, Docker: `structurizr/lite`) | C4 model diagrams only (context/container/component/deployment) — a single specialized diagram family, not general-purpose | Docker container, not a client asset | Yes (self-hosted Docker) | Mature for its narrow C4 scope | Structurizr Lite is free/self-hostable; commercial cloud offering also exists |
| **bpmn-js** (+ elk.js for layout) | Client JS | BPMN 2.0 process diagrams only — a single specialized notation, and it's a full interactive *modeler/editor* toolkit, not a lightweight text-to-SVG renderer | Multi-module toolkit; `elkjs` layout engine alone is a large dependency (general graph layout algorithms bundled) — heavier than needed for "render static diagram from text" | Yes | Mature for BPMN specifically | bpmn.io license (source-available, check terms) |
| **Kroki** (meta-option) | Server (Docker, fronts many engines incl. PlantUML, Graphviz, Mermaid, D2, BlockDiag family, Ditaa, Excalidraw, SvgBob, Vega, WaveDrom, Structurizr, BPMN, etc.) | Whichever of the above engines is invoked per-request via URL/syntax prefix — effectively "union of everything it fronts," so breadth is very high in aggregate, but each individual diagram is still constrained by its underlying engine's own type coverage (e.g. asking it for Kroki+PlantUML still gets no native fishbone) | Docker image bundling multiple JVM/Go/Rust toolchains — large server footprint, not applicable to "small client asset" framing | Yes, self-hosted Docker | Mature project, actively maintained | MIT (Kroki itself); underlying engines carry their own licenses |

Sources: [mermaid npm](https://www.npmjs.com/package/mermaid) ·
[mermaid dist listing](https://cdn.jsdelivr.net/npm/mermaid@11.16.0/dist/) ·
[@terrastruct/d2 npm](https://www.npmjs.com/package/@terrastruct/d2) ·
[terrastruct/d2 GitHub](https://github.com/terrastruct/d2) ·
[D2 design decisions](https://d2lang.com/tour/design/) ·
[D2.js Architecture (DeepWiki)](https://deepwiki.com/terrastruct/d2/8.1-d2.js-architecture) ·
[@viz-js/viz npm](https://www.npmjs.com/package/@viz-js/viz) ·
[mdaines/viz-js GitHub](https://github.com/mdaines/viz-js) ·
[plantuml/plantuml-server Docker Hub](https://hub.docker.com/r/plantuml/plantuml-server) ·
[plantuml/plantuml-server GitHub](https://github.com/plantuml/plantuml-server) ·
[PlantUML feature request #830 — Ishikawa/fishbone](https://github.com/plantuml/plantuml/issues/830) ·
[PlantUML Q&A — fishbone workarounds](https://forum.plantuml.net/9935/create-an-ishikawa-fishbone-diagram) ·
[nomnoml npm](https://www.npmjs.com/package/nomnoml) ·
[skanaar/nomnoml GitHub](https://github.com/skanaar/nomnoml) ·
[adrai/flowchart.js GitHub](https://github.com/adrai/flowchart.js/) ·
[bramp/js-sequence-diagrams GitHub](https://github.com/bramp/js-sequence-diagrams) ·
[ivanceras/svgbob GitHub](https://github.com/ivanceras/svgbob) ·
[Structurizr Lite](https://trailheadtechnology.com/tooling-for-the-c4-model-structurizr-lite/) ·
[bpmn-io/bpmn-js GitHub](https://github.com/bpmn-io/bpmn-js) ·
[elkjs npm](https://www.npmjs.com/package/elkjs) ·
[Kroki](https://kroki.io/) · [Kroki diagram types](https://docs.kroki.io/kroki/diagram-types/) ·
[yuzutech/kroki GitHub](https://github.com/yuzutech/kroki) ·
[D2 Gantt feature request #1825 (declined per design philosophy)](https://github.com/terrastruct/d2/issues/1825)

## 2. Diagram-type coverage matrix

`✓` native · `~` partial/manual workaround only · `—` not supported

| Diagram type | Mermaid | D2 | Graphviz/viz.js | PlantUML | nomnoml | flowchart.js | js-seq-diagrams | svgbob | Structurizr | bpmn-js |
|---|---|---|---|---|---|---|---|---|---|---|
| Flowchart | ✓ | ✓ (generic graph) | ✓ (generic graph) | ✓ (activity diagram) | ~ (box/arrow) | ✓ | — | ~ (ASCII) | — | ~ (as BPMN) |
| Sequence | ✓ | ✓ | — | ✓ | — | — | ✓ | ~ | — | — |
| Class/UML | ✓ | ~ (shapes) | ~ (manual DOT records) | ✓ | ✓ | — | — | — | — | — |
| State | ✓ | — | — | ✓ | — | — | — | — | — | — |
| ER | ✓ | ✓ (SQL tables) | ~ (manual) | ✓ | — | — | — | — | — | — |
| Gantt | ✓ | — (explicitly excluded) | — | ✓ | — | — | — | — | — | — |
| Pie chart | ✓ | — (explicitly excluded) | — | ~ | — | — | — | — | — | — |
| Mindmap | ✓ | — (explicitly excluded) | — | ✓ | — | — | — | ✓ (ASCII-ish) | — | — |
| Timeline | ✓ | — | — | ~ | — | — | — | — | — | — |
| GitGraph | ✓ | — | — | — | — | — | — | — | — | — |
| C4 / architecture | ✓ | ✓ (general diagrams usable for it) | ~ | ✓ (plugin) | — | — | — | — | ✓ (native, only this) | — |
| BPMN | — | — | — | ~ | — | — | — | — | — | ✓ (native, only this) |
| **Fishbone / Ishikawa** | **✓ native (v11.12.3+, beta)** | ~ manual layout only | ~ manual layout only | **— no native, open feature request since 2021, community workarounds via mindmap/WBS only** | — | — | — | — | — | — |

**Key confirmation for research question 4**: no single lighter alternative matches mermaid's breadth.
D2 explicitly and permanently declines to cover mindmap/Gantt/pie/Sankey/Venn as a design principle
(["D2 does none of those and will not support these"](https://d2lang.com/tour/design/)). Graphviz/viz.js
is a generic graph layout engine, not a diagram-grammar library — it can approximate a flowchart or
class diagram by hand-crafting DOT, but has no sequence/Gantt/state/pie syntax at all. PlantUML is the
only alternative that rivals mermaid's raw breadth, but it is JVM/server-side, not a client bundle, so
it doesn't answer the "lighter client-side lib" framing — it answers "avoid the client bundle
entirely" instead (see §4). Narrow tools (nomnoml, bpmn-js, Structurizr, flowchart.js,
js-sequence-diagrams) are each excellent at exactly one diagram family and nothing else.

## 3. Fishbone/Ishikawa specifically

- **Mermaid**: native `ishikawa-beta` diagram type since **v11.12.3**, first-line = effect/problem
  statement, indented lines = branching causes. Confirmed in
  `research_mermaid_integration.md` §4. This is the only tool surveyed with a purpose-built grammar
  for this diagram shape.
- **PlantUML**: **no native fishbone/Ishikawa diagram type.** Open feature request
  [#830](https://github.com/plantuml/plantuml/issues/830) since December 2021, still unresolved.
  Community workaround discussion on the [PlantUML forum](https://forum.plantuml.net/9935/create-an-ishikawa-fishbone-diagram)
  suggests combining PlantUML's mindmap + WBS (work-breakdown-structure) diagram types can produce a
  cause-effect-*like* tree shape, but it does not produce the classic fishbone "spine + angled bones"
  visual layout — it's a tree, not a fishbone.
- **D2 / Graphviz**: neither has a diagram type for this at all. Both are general-purpose node/graph
  layout engines; a fishbone shape would have to be hand-built as a manually-positioned graph (fixed
  coordinates or a contrived DAG that happens to render fishbone-ish under a particular layout engine),
  which is not a text-authoring experience comparable to mermaid's `ishikawa-beta` — it would be
  bespoke diagram-authoring work for every fishbone diagram a course author wants, defeating the
  "text-to-diagram" premise entirely.
- **nomnoml, flowchart.js, js-sequence-diagrams, svgbob, Structurizr, bpmn-js, Kroki-fronted-engines**:
  none has fishbone support; Kroki only proxies to underlying engines, none of which (per this survey)
  natively support it either.

**Honest conclusion**: if native fishbone/Ishikawa authoring (the idea's explicit "herringbone
diagrams" requirement) is a hard launch requirement, **mermaid is currently the only tool surveyed that
satisfies it out of the box.** Everything else means either dropping fishbone from scope, accepting a
non-fishbone-shaped mindmap/WBS approximation (PlantUML), or hand-authoring fixed-layout SVG/DOT per
diagram (D2/Graphviz) — none of which is "text-to-diagram" in the sense the idea intends.

## 4. The tradeoff verdict

Three genuinely distinct paths, stated plainly for the idea owner:

1. **Mermaid as-is (recommended baseline from `research_mermaid_integration.md`)**: 3.4 MB single
   self-hosted file, one `<script defer>`, broadest diagram coverage of anything surveyed, and the
   *only* tool with native fishbone/Ishikawa support. The cost is purely a one-time cached static
   asset download — no CDN, no per-request server rendering cost, no JVM/headless-browser
   infrastructure. Given FLS already accepts this pattern for KaTeX (280 KB) just at 12x the size, and
   given the diagram widget is loaded only on course/exam base templates (not site-wide), this is
   arguably an acceptable, well-understood tradeoff rather than a problem needing a "lighter
   alternative" fix.
2. **A much narrower small lib for a trimmed scope**: if the idea's actual need turns out to be
   "flowcharts and maybe class diagrams," nomnoml (~72 KB) or a similarly narrow lib could replace
   mermaid entirely at a fraction of the size — but this means **explicitly dropping** fishbone,
   sequence, ER, Gantt, state, mindmap, etc. from what `c-mermaid` (or a renamed, less mermaid-specific
   component) can render. This is a scope-reduction decision, not a like-for-like swap, and the idea
   text's explicit callout of herringbone diagrams as a *reason* to want "a modern version" suggests
   this path contradicts the idea's own stated requirement.
3. **Server-side rendering** (mermaid-cli via headless Chromium, or PlantUML on a self-hosted JVM
   container, or Kroki fronting either): removes the client bundle entirely — the browser downloads
   only the rendered SVG/PNG per diagram, typically a few KB. The cost moves to server-side
   infrastructure (a headless-browser or JVM process per render, or a Kroki sidecar container) and a
   render-request/caching architecture (render at content-save-time or cache-on-first-view, since
   per-page-load Puppeteer/JVM invocation would be far too slow for a request-response Django view).
   This is a legitimate way to shrink the *client* footprint to near-zero while keeping mermaid's full
   diagram breadth including fishbone (since mermaid-cli just runs real mermaid headlessly) — it is
   **not** a "lighter alternative library," it's an architectural shift from client-rendering to
   server-rendering of the *same* library, and deserves its own spec-level infrastructure discussion
   (JVM/headless-Chromium hosting, render caching, async job or on-save pre-render) beyond what this
   comparison-of-libraries file should recommend on its own.

**Bottom line for the idea refinement**: there is no "free lunch" lighter client-side library that
keeps mermaid's breadth and fishbone support. The decision is genuinely: accept mermaid's 3.4 MB
client asset, narrow the diagram-type scope to fit a smaller lib, or move rendering server-side (same
mermaid engine, different execution location, added infra). Recommend the spec state this tradeoff
explicitly rather than silently picking one.

status: ok
