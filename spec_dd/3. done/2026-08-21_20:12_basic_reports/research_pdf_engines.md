# PDF engine research

Scope: pick an engine to generate multi-page A4 cohort progress reports (title page,
per-student sections, wide multi-page tables with repeating headers, mixed
portrait/landscape orientation in one document, colour-coded cells, simple progress
bars, "page X of Y", controlled page breaks) from a Django admin action, for a library
(FLS) that gets installed into other people's Django projects.

## Bottom line

- **Recommend WeasyPrint.** It is the only candidate that satisfies *every* hard
  layout requirement — repeating `<thead>`, mixed orientation via CSS named pages,
  running headers/footers with `counter(page)`/`counter(pages)`, `break-inside`,
  orphans/widows — **in a single render**, driven by HTML/CSS you can generate from
  the existing django-cotton templates. Every other engine either can't do mixed
  orientation in one render (headless Chromium), can't do it in HTML/CSS at all
  (ReportLab/fpdf2/Typst, which need an imperative Python or markup API instead of
  templates), or has materially weaker/less standard CSS support (xhtml2pdf).
- The real cost of WeasyPrint is **system libraries** (Pango, cairo, gdk-pixbuf,
  HarfBuzz) — not a pip-only install. This is a genuine downstream burden for a
  library meant to drop into arbitrary Django projects, but it is a well-documented,
  one-time `apt`/`apk` install (Debian/Ubuntu and Alpine package names are
  well-known and stable), not a runtime operational burden. Contrast with headless
  Chromium, which is both a large binary (~300 MB) *and* an ongoing operational
  liability in production (browser-process pooling, crash recovery, SSRF surface).
- **Runner-up: fpdf2** — pure-Python (no system libs at all, MIT-licensed, actively
  maintained), and it does natively support repeating table headers
  (`repeat_headings`), per-page orientation (`add_page(orientation=...)`), cell
  background colours, and `{nb}`/`page_no()` for page counters. Pick this only if the
  spec author decides the Pango/cairo system-dependency is a hard no-go (e.g. must
  support minimal/rootless containers the host project controls). The cost: report
  layout must be written as Python flowable/drawing code, not django-cotton HTML
  templates — a real architectural fork from the rest of the app, and one that
  duplicates styling logic (Tailwind colours etc. must be re-expressed as RGB tuples
  in Python).
- **Reject:** wkhtmltopdf (archived, unmaintained since 2023/2024, CVE-2022-35583
  SSRF, explicitly "do not use with untrusted HTML" per its own maintainers).
  **Reject:** LaTeX (multi-GB TeX Live install, or a Python-in-LaTeX templating
  detour — indefensible install footprint for a library). **Reject as primary, note
  as "watch":** Typst — good design, small footprint (prebuilt wheels via
  `typst-py`), but the Django integration ecosystem is immature (`django-typst-engine`
  has ~13 stars) and it means abandoning django-cotton/HTML templates for Typst
  markup — too big a bet for this feature.
- Headless Chromium (Playwright) has the best CSS/JS fidelity of any option (real
  Tailwind, real flexbox/grid) but **cannot mix orientations within a single
  `page.pdf()` call** — Chromium's print pipeline applies one landscape/portrait
  setting to the whole document, so a mixed-orientation report needs two renders
  merged with `pypdf`/`pikepdf`. Its header/footer mechanism is also a single global
  HTML template applied to every page (via `headerTemplate`/`footerTemplate`), not
  WeasyPrint's per-section CSS margin boxes. Combined with the ~300 MB image and the
  "operate a browser in production" operational tax, it's a worse fit here despite
  better raw CSS support.
- **Regardless of engine**, a 50–200 page report should be generated in a
  **background task**, not synchronously in the request/response cycle — even the
  fastest engines (headless Chromium) take tens to hundreds of ms per page under
  load, and WeasyPrint specifically has documented multi-second-to-two-minute times
  for 50+ page documents unless the template is optimized (see Performance section).
  This has an implication FLS doesn't currently seem to have solved: FLS has no task
  queue dependency today, so the spec must decide whether to require Celery/RQ/
  Django-Q as a new downstream dependency, or use a simpler polling/thread approach.

## Comparison table

| Engine | License | System deps | Py 3.13 / Django 6 | HTML/CSS-driven | Repeat `<thead>` | Mixed orientation, 1 render | Page X of Y | Colour cells | Progress bars | Maintenance (2026) |
|---|---|---|---|---|---|---|---|---|---|---|
| **WeasyPrint** | BSD | Pango, cairo, gdk-pixbuf, HarfBuzz (native libs) | Yes | Yes (HTML/CSS) | Yes, native (`display: table-header-group`, since 2013) | Yes, native (CSS named pages) | Yes, native (`counter(page)`/`counter(pages)` in `@page` margin boxes) | Yes (CSS) | Yes (CSS/SVG) | Active (CourtBouillon), releases every 2–3 months |
| **fpdf2** | MIT | None (pure Python; Pillow, fontTools, defusedxml) | Yes | No (imperative API; limited HTML subset) | Yes, native (`repeat_headings=ON_TOP_OF_EVERY_PAGE`) | Yes, native (`add_page(orientation=)`) | Yes (`{nb}`/`page_no()` in `header()`/`footer()`) | Yes (`cell_fill_color`) | Yes (drawing API) | Active (py-pdf org) |
| **ReportLab (OSS core)** | BSD-3 (OSS toolkit); **ReportLab PLUS is a separate paid product** (RML, speed) | None (pure Python + Pillow) | Yes | No (Platypus flowables / Canvas) | Yes, native (`Table(repeatRows=...)`) | Yes, native (`PageTemplate`/`NextPageTemplate`) | Manual (custom `NumberedCanvas`, two-pass) | Yes (`TableStyle`) | Yes (Canvas drawing) | Active, dual OSS/commercial |
| **xhtml2pdf** | Apache-2.0 | None (pure Python, built on ReportLab) | Likely, unverified for edge cases | Yes (HTML/CSS subset) | Partial/inconsistent, non-standard CSS handling | Weak/undocumented | Limited | Yes | Limited | Maintained but "maintenance roadmap" concerns raised by its own team; much smaller CSS coverage than WeasyPrint |
| **Typst (`typst-py`)** | MIT/Apache-2.0 | None (prebuilt Rust wheel) | Yes | No (Typst markup, not HTML) | Yes (native table design) | Yes (native page rules) | Yes (native) | Yes | Yes | Active, but Django integration ecosystem immature |
| **LaTeX (django-tex/pylatex)** | Varies (LaTeX itself free; TeX Live) | Full TeX distribution (hundreds of MB–4 GB) | Yes | No (LaTeX markup) | Yes (`longtable`) | Yes (`pdflscape`) | Yes | Yes | Yes (TikZ) | Mature but wrong tool for a Django-app-embedded library |
| **Headless Chromium (Playwright)** | Apache-2.0 (Playwright) | ~300 MB Chromium binary + libs | Yes | Yes (real HTML/CSS/JS) | Yes (browser print CSS) | **No** — one render = one orientation; needs 2 renders + merge | Yes, but as a single global `headerTemplate`/`footerTemplate`, not per-section | Yes | Yes | Active, fast, but heaviest ops footprint |
| **wkhtmltopdf** | LGPL | System Qt WebKit binary | N/A | Yes | Inconsistent | No | Limited | Yes | Limited | **Archived/unmaintained since 2023-2024; CVE-2022-35583 (critical SSRF); do not use** |
| **Hosted APIs** (DocRaptor, PDFShift, Api2Pdf, Gotenberg-as-a-service) | Commercial/SaaS | None locally | N/A | Yes (usually WeasyPrint or Chromium under the hood) | Depends on backend | Depends on backend | Depends on backend | Yes | Yes | N/A — adds a network dependency + recurring cost, wrong shape for an installable library used for internal admin reports |

## WeasyPrint — detail

- **License:** BSD. Actively developed by CourtBouillon; steady release cadence
  (stable docs at `doc.courtbouillon.org`, releases roughly every 2–3 months).
- **Install footprint:** the Python package is pip-installable, but it dynamically
  links Pango, cairo, gdk-pixbuf and HarfBuzz, which **cannot be installed via pip**
  and must come from system packages. Debian/Ubuntu:
  `build-essential python3-dev python3-pip python3-cffi libcairo2 libpango-1.0-0
  libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`. Alpine:
  `apk add cairo-dev pango-dev gdk-pixbuf` (plus build-time-only `gcc musl-dev
  jpeg-dev zlib-dev libffi-dev`, removable after build). Both are documented,
  stable, and commonly used — but this is a real line item in the host project's
  Dockerfile/CI, which matters because FLS is *installed into other projects*, not
  deployed as its own service.
- **Requirements coverage (all native, no plugins):**
  - Repeating table headers: `thead { display: table-header-group } tfoot { display:
    table-footer-group }` repeats on every page a table spans — this has worked
    since a 2013 fix (GitHub issue #76) and is unrelated to `border-collapse`
    quirks that were fixed at the same time.
  - Mixed orientation in one document: CSS **named pages** (CSS Paged Media Module
    Level 3) — define `@page landscape-table { size: A4 landscape }` and apply it to
    a section via the `page` property, alongside a default `@page { size: A4
    portrait }` for the rest. This is listed as supported in WeasyPrint's official
    features page. (Older GitHub issues, e.g. #108/#1398, predate this support and
    show it was a long-requested feature — worth confirming behaviour with a spike
    against the exact pinned version before committing.)
  - Running headers/footers + page counters: `@page` margin boxes
    (`@top-center`, `@bottom-right`, etc.) plus `content: counter(page) " of "
    counter(pages)` are natively supported, and `position: running(...)` /
    `element(...)` let you promote an HTML block (e.g. a logo or cohort name) into
    the margin box.
  - `break-inside: avoid`, `break-before`, `break-after`, and CSS `orphans`/`widows`
    are all supported for controlling awkward breaks per section.
  - `@font-face` is supported with automatic embedding/subsetting, so Unicode names
    and any brand fonts render correctly.
- **CSS ceiling — Tailwind compatibility:** WeasyPrint implements CSS 2.1 solidly,
  flexbox "works for simple cases but is not deeply tested," and CSS Grid is
  "basic... with limitations" (no `inline-grid`, no subgrid, no auto-fill/fit).
  There is a known, unresolved community report of Tailwind's generated CSS
  producing "ignored"/"invalid" warnings when fed through django-weasyprint
  (tailwindlabs/tailwindcss discussion #11187) — the safe approach is **not** to
  point WeasyPrint at the full compiled Tailwind stylesheet, but to author a small,
  dedicated print stylesheet (plain CSS or a narrow Tailwind subset) for the report
  templates, using simple block/table layout rather than flex/grid-heavy admin UI.
- **Performance:** WeasyPrint is CPU-bound and not itself optimized for raw speed.
  Reports in the wild: ~1.4 minutes for a 52-page PDF in one unoptimized case
  (GitHub #545/#578 threads); a third-party benchmark blog (pdf4.dev, vendor
  content, treat as directional not authoritative) put a "complex" WeasyPrint
  render around 600 ms cold and reported no persistent "warm" mode (each call
  re-parses CSS/HTML), 30–70% slower again in typical Docker-on-Linux setups vs bare
  metal. A practical optimization write-up (Clifford Gama) recommends explicit page
  breaks (avoids WeasyPrint re-flowing the whole document per pagination decision),
  avoiding large/unfiltered CSS frameworks, and avoiding tables-as-page-layout — all
  directly relevant to a 50–200 page report and worth baking into the template
  design. **Conclusion: generate in a background task (Celery/RQ/Django-Q), not
  inside the request/response cycle**, and design the template with explicit
  section-level page breaks and a pruned stylesheet.
- **Security:** WeasyPrint fetches remote resources (images, fonts, stylesheets) by
  default via `default_url_fetcher`. It exposes a `url_fetcher` hook (and a
  `URLFetcher` class with `allowed_protocols`, `allow_redirects`, `timeout`,
  `ssl_context`) to restrict or block this — essential if any report content is
  derived from user/educator-authored markdown/HTML (course content) that could
  contain `<img src="http://169.254.169.254/...">`-style SSRF payloads, or
  `file://` local-file-read attempts. Two relevant CVEs to know about and pin
  around: **CVE-2024-28184** (versions 61.0–61.1: a custom `url_fetcher` could be
  bypassed, letting arbitrary local files/URLs be attached to the output PDF; fixed
  in 61.2) and **CVE-2025-68616** (versions before 68.0: the default fetcher
  followed HTTP redirects without re-validating the redirect target against a
  custom fetcher's allowlist, an SSRF bypass; fixed by defaulting
  `allow_redirects=False`). **Pin WeasyPrint >= 68** and still layer an explicit
  restrictive `url_fetcher` (e.g. disallow `http(s)`/`file` entirely if all images
  are embedded as base64 or served from local static/media paths) rather than
  relying on defaults.
- **Testing in CI:** the common pattern is `pytest` + text extraction, not pixel
  diffing. `pypdf`'s `extract_text()` has known issues with WeasyPrint output
  (spacing/ligature artifacts — GitHub py-pdf/pypdf#242); `pdfplumber` is more
  reliable for both text and `extract_table()`-style structural assertions (e.g.
  "the wide summary table's header row text appears on page 2 as well as page 1").
  For layout-only concerns (mixed orientation, page count) asserting on page
  `mediabox`/orientation and `len(reader.pages)` via `pypdf` is straightforward and
  fast, and doesn't depend on font rendering.
- **Django ecosystem:** `django-weasyprint` (403★, Apache-2.0, actively released
  through April 2026, test matrix now includes Django 5.2/6.0 and Python 3.14) is
  the standard wrapper — a thin `WeasyTemplateResponseMixin`/base view, not a hard
  dependency (FLS could just call `weasyprint.HTML(string=rendered_html).write_pdf()`
  directly from a view/admin action and skip the wrapper).

## fpdf2 — detail

- **License:** MIT. **Install footprint:** pure Python, dependencies are Pillow,
  fontTools, defusedxml — no system libraries, real pip wheels, trivially usable in
  any Docker base image including scratch/distroless-adjacent images. This is the
  strongest possible answer to the "downstream install burden" constraint.
- **Requirements coverage:**
  - Table header repeat: `Table(..., repeat_headings=TableHeadingsDisplay.ON_TOP_OF_EVERY_PAGE)`
    (default first-row-as-heading behaviour, explicitly configurable, can also be
    disabled).
  - Mixed orientation: `pdf.add_page(orientation="L")` / `"P"` per page — since
    layout is imperative (you call `add_page` yourself for each section), mixing
    orientation is simply "call it with a different argument," no CSS trick needed.
  - Page X of Y: `{nb}` is substituted with the final page count at document close,
    combined with `pdf.page_no()` inside a `header()`/`footer()` callback you
    override — this is boilerplate you write once, not a CSS feature, but is
    reliable and simple.
  - Colour-coded cells: `cell_fill_color` on `Table`, or per-cell via `style=`.
  - Progress bars: no built-in widget, but fpdf2's drawing primitives
    (`rect`, `line`, colour fills) make a simple horizontal bar trivial to build as
    a small helper function.
  - Break control: `will_page_break()` lets you pre-check whether adding an element
    would trigger a page break so you can force it earlier/later; unbreakable
    sections group content that must not split.
- **What you give up:** there is no real HTML/CSS rendering — fpdf2 ships a
  deliberately limited `write_html()` for simple inline-styled snippets, not a CSS
  engine. The report's visual structure (title page, per-student sections, tables)
  would be built as Python function calls against the `Table`/`FPDF` API rather
  than django-cotton components — a genuine second templating system to maintain
  alongside the app's HTML templates, with colours/spacing duplicated as Python
  constants instead of reusing Tailwind design tokens.
- **Maintenance:** active, under the `py-pdf` GitHub org (same org as `pypdf`),
  regular releases, "mature and actively maintained" per its own docs/PyPI
  classifiers.

## ReportLab (OSS core) — detail

- **Licensing — important nuance:** the `reportlab` package on PyPI is the
  **open-source Toolkit, BSD-3 licensed, free for commercial use, no page-volume
  fees**. ReportLab the company separately sells **ReportLab PLUS**, a commercial
  product built on top of the OSS core that adds the RML XML templating language
  and faster rendering, licensed per output-page-volume (annual or perpetual) — the
  trial version stamps a "nag line" on every page until licensed. **FLS should use
  only the OSS `reportlab` package**; PLUS brings no capability this spec strictly
  needs and would impose a real recurring-cost burden on every downstream deployer,
  which conflicts hard with the "any dependency becomes a downstream burden"
  principle.
- **Install footprint:** pure Python + Pillow, real wheels, no system libs — same
  advantage as fpdf2.
- **Requirements coverage:** `Table(..., repeatRows=N)` (or a tuple, for cases
  where the first page's header differs from repeats) natively repeats header rows
  on split. Mixed orientation is done via multiple `PageTemplate`s registered on a
  `BaseDocTemplate` and switched mid-flow with the `NextPageTemplate` flowable — a
  well-established, documented pattern (reportlab-users mailing list has several
  worked examples). "Page X of Y" is **not** built in — the standard recipe is a
  custom `NumberedCanvas` subclass that does a two-pass render (buffers pages, then
  stamps the total count once known) via the `canvasmaker=` argument to
  `doc.build()`. `KeepTogether`/`KeepInFrame` avoid awkward breaks. Colour cells via
  `TableStyle`; progress bars via direct `Canvas` drawing calls.
- **Trade-off vs fpdf2:** more mature/precise low-level typography and table engine,
  larger community and more Stack Overflow/mailing-list coverage of exactly these
  patterns (repeatRows + NextPageTemplate + NumberedCanvas is a very well-trodden
  combination), at the cost of a steeper, more verbose API ("somewhat clunky" per a
  2026 Django forum thread) and the same architectural fork away from HTML
  templates that fpdf2 has.

## xhtml2pdf — detail

- Pure Python, built on top of ReportLab plus `html5lib`, Apache-2.0. No system
  libs — attractive on paper.
- In practice: smaller, less-standard CSS coverage than WeasyPrint (own maintainers
  have an open "Maintenance Roadmap" issue about project health), non-standard
  property names in places, and no confirmed, documented support matching
  WeasyPrint's for CSS named pages / paged-media margin boxes / robust
  `orphans`/`widows`. Given this report's requirements are precisely the paged-media
  edge cases (repeating headers on wide tables, mixed orientation, running
  counters), xhtml2pdf is a real risk of silently-wrong output rather than a hard
  failure — not recommended as primary or runner-up.

## Typst (`typst-py`) — detail

- MIT/Apache-2.0, Rust-based typesetting system with a maturin-built Python binding
  (`typst-py`) that ships **prebuilt wheels** for major platforms — much closer to
  fpdf2's "no system deps" story than WeasyPrint's, since the Rust engine is
  statically linked into the wheel.
- Typst natively has page rules (including per-section orientation), running
  headers/footers with page counters, and table header repetition, all as
  first-class language features, and is generally reported as fast.
- The catch: content is authored in **Typst markup**, not HTML/CSS — there is a
  `django-typst-engine` template-engine package, but it's small/early (single-digit
  contributor, ~13★, "Beta" maturity per Django Packages), so betting a
  library-wide reporting feature on it means (a) walking away from django-cotton
  entirely for this feature and (b) taking on an early-ecosystem-risk dependency.
  Worth revisiting in a future iteration if Typst's Django/Python tooling matures,
  but not for this spec.

## LaTeX — detail

- Technically capable of everything required (`longtable` for repeating headers,
  `pdflscape`/`lscape` for mixed orientation, `fancyhdr` for running
  headers/counters) via `django-tex`/`pylatex`, but requires a **full TeX
  distribution** on every machine that renders a report — hundreds of MB (TinyTeX)
  to several GB (full TeX Live). This is disqualifying for a dependency that has to
  be justified to every downstream installer of a Django app library. Included here
  only for completeness; not seriously considered further.

## Headless Chromium (Playwright/Puppeteer/pyppeteer) — detail

- Best-in-class CSS/JS fidelity: real Tailwind output renders correctly, full
  flexbox/grid, no CSS subset concerns.
- **Mixed orientation is the blocker.** Chromium's print-to-PDF pipeline (used by
  both Puppeteer's and Playwright's `page.pdf()`) takes a single `landscape`
  boolean (or `preferCSSPageSize` honouring one `@page size`) for the *entire*
  render — there is no equivalent of WeasyPrint's CSS named pages that lets
  different sections of one document flip orientation within a single call.
  Building this report with Chromium means rendering the portrait sections and
  landscape sections as **two separate PDFs and merging them** with `pypdf`/
  `pikepdf`, adding a real implementation and testing surface this spec would
  otherwise avoid entirely.
- Headers/footers/page numbers use a different, simpler mechanism:
  `displayHeaderFooter: true` plus a single global `headerTemplate`/
  `footerTemplate` HTML string (with special classes `pageNumber`, `totalPages`,
  `date`, `title`, `url`) applied uniformly to every page — workable for a single
  running header, but not WeasyPrint's per-margin-box, per-named-page richness.
- **Security:** running a headless browser against report-adjacent HTML is a
  documented SSRF/IMDS vector (see Black Hills InfoSec's write-up on hunting SSRF
  bugs in PDF generators via headless Chrome) — if an attacker can influence any
  HTML fed to the renderer (e.g. via educator-authored course content that ends up
  quoted in a report), an `<iframe>`/`<img>` can reach internal network resources
  including cloud metadata endpoints, unless network egress is locked down at the
  container/process level (not just in application code).
- **Operational cost:** ~300 MB added to the image for Chromium alone (before base
  OS/fonts), plus production realities absent from pure-library engines: pooling
  browser instances under concurrency, handling OOM crashes mid-render, needing a
  supervisor/retry story, and poor fit for serverless (cold starts, special
  Lambda layers). For a library meant to be dropped into arbitrary host projects,
  this is the single worst fit of any candidate here, despite being the fastest
  and most CSS-faithful engine on raw benchmarks.

## Hosted/API services (DocRaptor, PDFShift, Api2Pdf, Gotenberg) — brief note

- These mostly wrap WeasyPrint or headless Chromium behind an HTTP API (Gotenberg is
  self-hostable and open source; the others are commercial SaaS). They remove the
  install-footprint problem locally but replace it with a network dependency,
  external cost, and data-residency question — sending student/cohort progress data
  to a third-party rendering service is a privacy/compliance decision, not a
  library-dependency decision, and is a mismatch for "triggered from Django admin,
  internal educators/staff only." Not recommended; noted for completeness only.

## Risks and open questions

The spec author must decide:

1. **System-library install burden acceptance.** Confirm the project's documented
   deployment story (Dockerfile, install docs) can absorb Pango/cairo/gdk-pixbuf as
   a documented prerequisite for the reports feature (ideally as an optional
   extra, e.g. `fls[reports]`, so projects that never use reports don't pay the
   cost). If this is genuinely unacceptable, fall back to fpdf2 and accept the
   Python-code-based layout approach instead of HTML templates.
2. **Background task requirement.** FLS currently has no task-queue dependency.
   Decide whether generating a 50–200 page report requires adding Celery/RQ/
   Django-Q as a new (optional) dependency, or whether a simpler in-process
   background thread + polling/webhook pattern is acceptable for "internal
   educators/staff only, admin-triggered" scale. Either way, do not generate
   synchronously in the admin request.
3. **Stylesheet strategy for print.** Full compiled Tailwind output should **not**
   be fed directly into WeasyPrint (known "ignored"/"invalid" warnings, and
   flex/grid support is only partial). Decide whether report templates get a
   dedicated, hand-written, small CSS file, or a filtered/purged Tailwind build
   scoped to only the utility classes the report templates use.
2. **WeasyPrint version pin and `url_fetcher` policy.** Pin `>=68` (CVE-2025-68616)
   and design an explicit `url_fetcher` allowlist/denylist before any report can
   render content that traces back to user/educator-authored input (course
   content, markdown), not just trust the default fetcher.
4. **Named-page mixed-orientation spike.** The CSS named-pages feature for mixed
   orientation is documented as supported, but historical GitHub issues about it
   are old/contentious — do a small spike (one portrait page + one landscape table
   page in a single WeasyPrint render) against the exact pinned version before
   committing the architecture, since this is the single most load-bearing
   requirement in the whole spec.
5. **Testing approach.** Decide between structural assertions (`pypdf` for page
   count/orientation/mediabox, `pdfplumber` for extracted table text/header
   repetition) versus visual/snapshot diffing (rasterize with `pdf2image` and
   compare images) — the former is faster and more CI-friendly, the latter catches
   real visual regressions (colour coding, progress bar rendering) that text
   extraction can't.
6. **Accessibility/robustness of colour coding.** Not engine-specific, but the spec
   should require colour-coded cells/rows to also carry a text/symbol cue, since
   PDF colour won't survive greyscale printing.

## References

- https://doc.courtbouillon.org/weasyprint/stable/
- https://doc.courtbouillon.org/weasyprint/stable/features.html
- https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html
- https://doc.courtbouillon.org/weasyprint/stable/changelog.html
- https://doc.courtbouillon.org/weasyprint/v52.5/install.html
- https://weasyprint.org/
- https://github.com/Kozea/WeasyPrint/issues/108
- https://github.com/Kozea/WeasyPrint/issues/1398
- https://github.com/Kozea/WeasyPrint/issues/29
- https://github.com/Kozea/WeasyPrint/issues/76
- https://github.com/Kozea/WeasyPrint/issues/545
- https://github.com/Kozea/WeasyPrint/issues/578
- https://kozea.github.io/WeasyPerf/
- https://www.naveenmk.me/blog/weasyprint/
- https://www.sentinelone.com/vulnerability-database/cve-2025-68616/
- https://github.com/advisories/GHSA-983w-rhvv-gwmv
- https://cvefeed.io/vuln/detail/CVE-2024-28184
- https://security.snyk.io/vuln/SNYK-PYTHON-WEASYPRINT-6420630
- https://github.com/tailwindlabs/tailwindcss/discussions/11187
- https://github.com/py-pdf/pypdf/issues/242
- https://pypi.org/project/pdfplumber/
- https://github.com/fdemmer/django-weasyprint
- https://github.com/fdemmer/django-weasyprint/blob/main/CHANGELOG.md
- https://djangopackages.org/grids/g/pdf/
- https://reportlab.substack.com/p/announcing-reportlab-450-30042026
- https://www.reportlab.com/pricing/
- https://www.reportlab.com/about/licence-terms/
- https://docs.reportlab.com/developerfaqs/
- https://reportlab-users.reportlab.narkive.com/j52yGA7S/changing-from-landscape-to-portrait-orientation-in-the-same-document
- https://py-pdf.github.io/fpdf2/index.html
- https://py-pdf.github.io/fpdf2/PageBreaks.html
- https://py-pdf.github.io/fpdf2/Tables.html
- https://py-pdf.github.io/fpdf2/PageFormatAndOrientation.html
- https://github.com/py-pdf/fpdf2
- https://pypi.org/project/typst/
- https://github.com/messense/typst-py/blob/main/README.md
- https://github.com/a-musing-moose/django-typst-engine
- https://pypi.org/project/rst2pdf/0.91/
- https://github.com/rst2pdf/rst2pdf/blob/main/CHANGES.rst
- https://pdf4.dev/blog/html-to-pdf-benchmark-2026
- https://pdf4.dev/blog/wkhtmltopdf-alternatives-2026
- https://pdf4.dev/blog/weasyprint-vs-wkhtmltopdf
- https://wkhtmltopdf.org/status.html
- https://doc.doppio.sh/article/wkhtmltopdf-is-now-abandonware
- https://www.blackhillsinfosec.com/hunting-for-ssrf-bugs-in-pdf-generators/ (search-result summary only; direct fetch returned 403)
- https://ayedo.de/en/posts/gotenberg-die-referenz-architektur-fur-pdf-generierung-als-microservice/
- https://forum.djangoproject.com/t/reportlab-weasy-wkhtml-oh-my-which-pdf-printing-plugin-to-use/940
- https://medium.com/@_gabiCavalcante/create-pdf-with-latex-and-django-c892f4805aaf
- https://pylatexenc.readthedocs.io/en/latest/latexencode/

status: ok
