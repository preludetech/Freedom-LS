# Research: Reference Implementations for Course Content Widgets

Purpose: ground the FLS "course content widgets" taxonomy, naming, and feature scope in
established conventions (docs systems, design systems) rather than reinventing them.
This feeds high-level idea refinement, not a full spec.

Existing FLS component (the thing we are extending):
`freedom_ls/content_engine/templates/cotton/callout.html` —
`<c-callout level="info|warning|error|success" title="...">` with a markdown body slot.
Each level maps to brand tokens (`bg-primary/10`, `bg-warning/10`, `bg-error/10`,
`bg-success/10`) + an icon (`info`/`warning`/`error`/`success`).

---

## 1. Callouts / Admonitions

### MkDocs Material (the de-facto "full" set)
- **12 canonical types**: `note`, `abstract`, `info`, `tip`, `success`, `question`,
  `warning`, `failure`, `danger`, `bug`, `example`, `quote`.
- Each type has a **distinct icon + colour** baked into the theme. Rough colour family:
  - `note` = blue/grey pencil; `abstract`/`summary` = light blue clipboard;
    `info` = cyan/blue (i); `tip` = teal flame; `success` = green check;
    `question` = light green help; `warning` = orange/amber; `failure` = red x;
    `danger` = red lightning; `bug` = pink/red bug; `example` = purple list;
    `quote` = grey quote mark.
- **Legacy aliases** existed and are now deprecated (kept for back-compat, slated for
  removal): `summary`/`tldr` → abstract, `todo` → info, `hint`/`important` → tip,
  `check`/`done` → success, `help`/`faq` → question, `caution`/`attention` → warning,
  `fail`/`missing` → failure, `error` → danger, `cite` → quote.
  Lesson: they consolidated many synonyms down to one canonical keyword per tone.
- **Authoring syntax**: `!!! note` then body indented 4 spaces.
  - Custom title: `!!! note "My title"` (markdown allowed in title).
  - No title / icon-only block: `!!! note ""` (empty string).
  - Collapsible: `??? note` (collapsed) / `???+ note` (expanded by default) —
    needs the `pymdownx.details` extension.
  - Icons configurable via `theme.icon.admonition`.
- Refs:
  - https://squidfunk.github.io/mkdocs-material/reference/admonitions/
  - https://github.com/squidfunk/mkdocs-material/blob/master/docs/reference/admonitions.md

### GitHub Markdown Alerts (the de-facto "minimal" set)
- **5 types only**: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`.
  - NOTE = useful info even when skimming (blue).
  - TIP = helpful advice / do it better (green).
  - IMPORTANT = key info needed to succeed (purple).
  - WARNING = needs immediate attention to avoid problems (amber/orange).
  - CAUTION = risks / negative consequences of an action (red).
- **Authoring syntax**: blockquote + bracketed keyword:
  ```
  > [!NOTE]
  > Body text, each line prefixed with >
  ```
- Colour-coded left border + background + semantic SVG icon, applied by GitHub's renderer.
- **Scoping lessons**: explicitly recommends using alerts *sparingly* (1–2 per article,
  no consecutive, no nesting); callouts best at 1–3 sentences. No custom titles, no
  collapsible, no custom types — deliberately minimal.
- Refs:
  - https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax
  - https://github.com/orgs/community/discussions/16925

### Docusaurus
- **5 default types**: `note`, `tip`, `info`, `warning`, `danger`.
  (Note the set differs from GitHub: `info`+`danger` instead of `important`+`caution`.)
- **Authoring syntax**: triple-colon fence:
  ```
  :::tip[Optional Title]
  Body markdown
  :::
  ```
  - Title in `[...]`, supports markdown.
  - Nesting via *more* colons on the outer block (`::::`, `:::::`).
  - Extensible: add custom keywords via remark plugin config (`extendDefaults: true`).
- Refs:
  - https://docusaurus.io/docs/markdown-features/admonitions

### Sphinx / reStructuredText
- **9 named admonitions**: `attention`, `caution`, `danger`, `error`, `hint`,
  `important`, `note`, `tip`, `warning` — plus a generic `.. admonition:: Custom title`.
- **Authoring syntax** (directive form):
  ```
  .. warning::

     Body indented.
  ```
- Rendered in colours by severity; many themes support a `:collapsible:` option.
- Lesson: the generic `admonition` directive is the escape hatch for arbitrary titles —
  the named ones are the fixed, semantic set.
- Refs:
  - https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html
  - https://documatt.com/restructuredtext-reference/admonitions.html

### GitBook & Notion (product-style callouts)
- **GitBook "Hints" — 4 styles**: `info`, `success`, `warning`, `danger`.
  Each has a default icon, icon is swappable. This set maps almost 1:1 to FLS today.
  - https://gitbook.com/docs/creating-content/blocks/hint
- **Notion callouts**: not tone-based at all — one block type with a free **icon/emoji**
  + a **background colour** chosen from ~10 (default, gray, brown, orange, yellow, green,
    blue, purple, pink, red). Maximum flexibility, zero semantics.
  - https://www.notion.com/help/customize-and-style-your-content
  - https://developers.notion.com/changelog/block-colors-are-now-supported-in-the-api
- **Asciidoctor** (for completeness): 5 types — `NOTE`, `TIP`, `IMPORTANT`, `CAUTION`,
  `WARNING`. https://docs.asciidoctor.org/asciidoc/latest/blocks/admonitions/

### Cross-system tone comparison (semantic buckets)

| Bucket        | GitHub    | Docusaurus | MkDocs Material        | Sphinx          | GitBook  | FLS today |
|---------------|-----------|------------|------------------------|-----------------|----------|-----------|
| neutral info  | NOTE      | note/info  | note / info            | note            | info     | **info**  |
| helpful tip   | TIP       | tip        | tip                    | tip / hint      | —        | —         |
| key / must    | IMPORTANT | —          | (via tip alias)        | important       | —        | —         |
| positive      | —         | —          | success                | —               | success  | **success** |
| caution/warn  | WARNING   | warning    | warning                | warning/caution | warning  | **warning** |
| severe/destruct | CAUTION | danger     | danger / failure       | danger/error    | danger   | **error** |

Takeaway: every system agrees on a **neutral / warn / severe** spine. The optional
extras are **tip**, **important**, **success**, plus presentational types (`quote`,
`example`, `abstract`, `question`, `bug`) that MkDocs adds but most others omit.

---

## 2. Code / Log Blocks
- **Syntax highlighting**: fenced block with language id (```` ```py ````). Build-time
  (Pygments, MkDocs default) or runtime JS (Prism/highlight.js, Docusaurus default).
- **Copy button**: MkDocs = global theme feature `content.code.copy`, per-block opt-out
  `.no-copy`. Standard expectation in modern docs — copy button on hover, top-right.
- **Title / filename**: MkDocs `` ```py title="bubble_sort.py" ``. Renders a header bar
  above the block. Docusaurus uses `` ```py title="file.py" `` too.
- **Line numbers**: MkDocs `linenums="1"` (and can start at any number to split blocks);
  Docusaurus `showLineNumbers`.
- **Line highlighting**: MkDocs `hl_lines="2 3"` or `hl_lines="3-5"`; Docusaurus uses
  `// highlight-next-line` comments or `{2,5-7}` metastring.
- **Annotations** (MkDocs `content.code.annotate`): numbered markers `# (1)` in code that
  expand to prose. Powerful but niche — likely out of scope for v1.
- Refs:
  - https://squidfunk.github.io/mkdocs-material/reference/code-blocks/
  - https://docusaurus.io/docs/markdown-features/code-blocks (code block metastring)

---

## 3. Math / Equation Blocks
- **Two engines**: **MathJax** (more LaTeX coverage, MathML output → better a11y, slower)
  vs **KaTeX** (subset of LaTeX, much faster, render-on-server option). Pick KaTeX for
  speed/simplicity, MathJax for breadth/accessibility.
- **Authoring (near-universal)**: inline `$...$`, block `$$...$$`.
  - MkDocs: `pymdownx.arithmatex` extension feeds MathJax/KaTeX.
  - Docusaurus: `$...$` inline + ```` ```math ```` (or `$$`) block via `remark-math` +
    `rehype-katex`.
- Lesson: don't invent syntax — `$`/`$$` is the established convention; the only real
  decision is engine + whether render is client-side or pre-rendered.
- Refs:
  - https://squidfunk.github.io/mkdocs-material/reference/math/
  - https://docusaurus.io/docs/markdown-features/math-equations

---

## 4. Data Tables (responsive)
- Markdown pipe tables are the universal authoring format; the responsive concern is
  pure CSS. Common approach: wrap the table in a horizontally scrollable container
  (`overflow-x: auto`) so wide tables scroll instead of breaking layout (MkDocs Material
  does this; most themes do).
- Native markdown tables can't do caption/numbering/merged cells — systems that need
  those drop to HTML `<table>` or MyST/`{list-table}` directives.
- Lesson: keep tables as plain markdown + a responsive scroll wrapper; only reach for a
  widget if captions/figure-numbering are required.
- Refs:
  - https://squidfunk.github.io/mkdocs-material/reference/data-tables/
  - https://github.com/squidfunk/mkdocs-material/discussions/4673 (numbering is non-trivial)

---

## 5. Figures / Images with Captions, Galleries
- **No native markdown caption** — convention is the HTML `<figure>` + `<figcaption>`
  pattern. MkDocs renders `![alt](img)` followed by emphasis as a `<figure>` caption
  ("Markdown in HTML" / attr_list). MyST has a dedicated `{figure}` directive with
  caption body + cross-reference label.
- Galleries: not a markdown primitive anywhere — always a theme/plugin/widget concern.
- Lesson: a `<figure caption="...">` widget is the conventional unit; galleries are an
  explicit add-on, not expected by default.
- Refs:
  - https://squidfunk.github.io/mkdocs-material/reference/images/
  - https://mystmd.org/guide/figures

---

## 6. Pull Quotes, Glossary / Definition Lists, Video & Audio
- **Pull quotes**: no standard markdown construct; treated as a presentational variant of
  blockquote. MkDocs' admonition `quote` type is the closest "blessed" pattern. Keep it a
  styled blockquote/callout, not a new syntax.
- **Definition lists**: PHP-Markdown-Extra / `pymdownx`/`def_list` syntax
  (`Term` on one line, `: definition` indented below) is the established authoring form;
  renders to `<dl><dt><dd>`.
- **Glossary**: Sphinx has a first-class `.. glossary::` directive with `:term:`
  cross-refs; MkDocs does it via the `abbr` extension (`*[HTML]: Hyper Text...`) for
  tooltips. For an LMS, a definition-list-backed glossary term is the low-surprise choice.
- **Video / audio embeds**: no markdown primitive — universally a raw HTML `<video>`/
  `<audio>`/`<iframe>` or a theme shortcode/widget. Expect a widget, not syntax.
- Refs:
  - https://python-markdown.github.io/extensions/definition_lists/
  - https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#glossary

---

## 7. Recommended Mapping for FLS

### Guiding principles (from the survey)
- Every system shares a **neutral → tip → warn → severe** spine. Don't break it.
- The minimal, low-surprise sets are GitHub (5) and Docusaurus (5). MkDocs' 12 is the
  "everything" set; most of its extras are presentational, not semantic.
- One canonical keyword per tone (MkDocs deprecated its synonyms for a reason).
- Custom title + markdown body are table stakes; collapsible is a nice-to-have;
  annotations/numbering/galleries are explicitly out-of-scope-able.

### Callout tone taxonomy — recommended
FLS already ships `info | warning | error | success`. This is exactly the GitBook set and
covers neutral / warn / severe / positive. Recommended **additive** extension (no renames,
no breakage):

| Keep (current) | Add (recommended) | Rationale |
|----------------|-------------------|-----------|
| `info`         | `note`            | neutral alias; GitHub/Docusaurus/Sphinx all use `note` as the default neutral tone |
| `warning`      | `tip`             | "helpful advice" tone present in GitHub/Docusaurus/MkDocs/Sphinx; distinct from info |
| `error`        | `important`       | "must-know to succeed" tone (GitHub/Sphinx); maps to a brand-accent, not error-red |
| `success`      | `quote` / `example` (optional) | presentational, only if pull-quote / worked-example widgets want a callout backing |

- **Naming decision**: keep `level=` as the attribute name and keep the four current
  values working verbatim. Treat `note` as a **synonym of `info`** (or vice versa) and
  add `tip` + `important` as genuinely new tones. This yields a 6-tone semantic set
  (`note/info`, `tip`, `important`, `success`, `warning`, `error`) — between the GitHub-5
  and MkDocs-12, and a strict superset of today.
- **Do NOT** adopt MkDocs' `danger` as separate from `error`, or `failure`, `bug`,
  `question`, `abstract` — they add semantic ambiguity for an LMS and overlap existing
  tones. Reserve `quote`/`example` only if they become real widgets.
- **`level` vs `type`**: `level` reads as a severity scale, which is slightly awkward for
  non-severity tones (`tip`, `note`, `quote`). Consider accepting an alias attribute
  `tone=` (or `type=`) that maps to the same values, while keeping `level=` for
  back-compat. Lowest-surprise external name across the industry is **`type`** (MkDocs,
  GitHub, Docusaurus, Sphinx all think in "admonition type"). Keep `level` as the
  deprecated-but-supported alias.

### Widget naming — recommended (conventional, least surprising)
- Callout / admonition → keep **`c-callout`** (callout is the GitBook/Notion term;
  admonition is the docs-tooling term — both fine, callout is more learner-friendly).
- Pull quote → `c-pull-quote` (or a `tone="quote"` callout variant).
- Glossary term → `c-glossary-term`, backed by a definition list (`<dl>/<dt>/<dd>`).
- Equation block → `c-math` / `c-equation`, `$$` authoring, KaTeX for speed.
- Code block → keep fenced ```` ``` ```` markdown; support `title=`, copy button (default
  on), optional `linenums`. Mirror MkDocs attribute names (`title`, `linenums`,
  `hl_lines`) to stay conventional.
- Data table → plain markdown table + responsive `overflow-x:auto` wrapper; only add
  `c-table` if captions are needed.
- Figure → `c-figure` with `caption=` (HTML `<figure>/<figcaption>` semantics).
- Image gallery → `c-gallery` (explicit add-on, not default).
- Video / audio → `c-video` / `c-audio` (HTML5 element or iframe embed).

### Feature-scoping lessons to carry into the spec
- Start with the **6-tone superset** callout; everything else (collapsible, annotations,
  figure numbering, galleries) is opt-in / later.
- Callouts should be short by convention (GitHub: 1–3 sentences) — worth a docs note, not
  enforcement.
- Don't invent math/code/quote *syntax*; reuse the `$$` / fenced-block / blockquote
  conventions and the MkDocs attribute names so authors transfer knowledge in.
