# Research: PDF metadata and print legibility for the org-branded cohort report

Scope: WeasyPrint 69.0 (the version pinned for this repo), rendering
`freedom_ls/reports/render.py` → `freedom_ls/reports/templates/reports/report.html`. Findings below
are keyed to the current FLS implementation where relevant, then to the reference design at
`spec_dd/2. in progress/report-rendered-with-org-name/report design/build_report.py`.

Every claim below is marked **[verified]** (confirmed against WeasyPrint's own docs, changelog, or
source/issue tracker) or **[inferred]** (reasoned from adjacent verified facts, general PDF/print
practice, or a source that didn't fully confirm the point). Where a claim could not be confirmed at
all it says so explicitly rather than guessing.

---

## 1. PDF document metadata with WeasyPrint

### How WeasyPrint derives metadata from HTML

WeasyPrint's `Document.metadata` object is built by parsing specific `<head>` elements, **[verified]**
against the WeasyPrint 69.0 API reference and source (`weasyprint/pdf/metadata.py`):

| PDF Info field | HTML source | Notes |
|---|---|---|
| `/Title` | `<title>` | No default if `<title>` is absent — stays `None`, not the URL or filename. |
| `/Author` | one or more `<meta name="author" content="...">` | Multiple `<meta name="author">` tags are all kept as **separate list entries** (one `rdf:li` each in the XMP stream) — WeasyPrint does not join them into a single string, and the classic PDF `/Author` info-dict field is the first one. |
| `/Subject` | `<meta name="description" content="...">` | Exactly one; last one wins if duplicated. |
| `/Keywords` | one or more `<meta name="keywords" content="...">` | Comma-separated content per tag is a convention, not enforced by WeasyPrint. |
| `/CreationDate` | `<meta name="dcterms.created" content="...">` | Must be one of the six W3C-profile ISO-8601 formats; if absent WeasyPrint uses the render's wall-clock time. |
| `/ModDate` | `<meta name="dcterms.modified" content="...">` | Same ISO-8601 constraint. |
| `/Creator` | `<meta name="generator" content="...">` | **Not** `/Producer` — see below. |
| `/Producer` | — | Always `"WeasyPrint {version}"`, e.g. `"WeasyPrint 69.0"`, set unconditionally by WeasyPrint itself via `pydyf`. |

Sources: [API Reference — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html), [Common Use Cases — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html). **[verified]**

An open feature request confirms `/Producer` cannot be overridden or suppressed: a user tried setting
it via `custom_metadata`, but "all meta tag names are lowercased when extracting custom metadata from
HTML," so it lands as a *custom* lowercase `producer` key, not the capitalized `/Producer` info-dict
entry the PDF spec reserves for the generating library. The maintainers closed the request as "not
planned." **[verified]** — [Issue #2118, "Allow suppressing the Producer metadata"](https://github.com/Kozea/WeasyPrint/issues/2118).

`custom_metadata` (a `write_pdf()` boolean option, default `False`) stores *arbitrary* `<meta>` tags
(anything not in the table above) as custom XMP/Info entries — not needed for the fields FLS cares
about here, all of which have first-class support. **[verified]**

### `write_pdf()` signature relevant to this feature

```python
HTML(...).write_pdf(
    target=None, zoom=1, finisher=None, font_config=None,
    counter_style=None, color_profiles=None, **options,
)
```

Relevant `**options` (all keys of `DEFAULT_OPTIONS`, all optional):
`pdf_identifier`, `pdf_variant`, `pdf_version`, `pdf_forms`, `pdf_tags`, `uncompressed_pdf`,
`custom_metadata`, `attachments`, `attachment_relationships`, `presentational_hints`,
`optimize_images`, `jpeg_quality`, `dpi`, `full_fonts`, `hinting`, `cache`, `xmp_metadata`,
`output_intent`. **[verified]** — [API Reference — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html).

None of these are metadata-content options — metadata content is driven entirely by the `<head>`
`<meta>`/`<title>` tags above, plus the `custom_metadata` boolean gate. `pdf_identifier` and
`pdf_version` exist but no default value could be confirmed from the docs fetched; `uncompressed_pdf`
defaults to `False` (PDF content streams are compressed by default) — relevant only to file
inspectability/debugging, not to reproducible builds in the sense of stable byte-for-byte output
(WeasyPrint embeds a real `/CreationDate` and, in the absence of `pdf_identifier`, a fresh file ID
each run — there is no documented "deterministic output" flag). **[inferred]** — no source directly
addresses reproducible-build guarantees; treat WeasyPrint PDF output as non-reproducible byte-for-byte
across renders of identical input unless `pdf_identifier` is pinned.

### Current FLS state

`freedom_ls/reports/templates/reports/report.html` sets only:

```html
<title>{{ data.cohort_name }} — Cohort progress report</title>
```

No `<meta name="author">`, `<meta name="description">`, `<meta name="keywords">`, or
`<meta name="generator">`. Per the table above, this means **today's report has `/Title` set and
`/Author`, `/Subject`, `/Keywords` all empty**, `/Creator` empty (falls back to whatever WeasyPrint's
UA-stylesheet default is — effectively empty), and `/Producer = "WeasyPrint 69.0"` regardless.
**[verified against the file read directly]**.

### What the reference design does

`report design/build_report.py` sets:

```html
<meta name="author" content="{partner_name}"/>
<meta name="generator" content="{powered_by}"/>
<meta name="description" content="Cohort progress report — ... Powered by {powered_by}"/>
```

i.e. Author = the organisation (AeroVista Flight Academy), and what the design comment calls
"Generator" is actually the `<meta name="generator">` tag, which per the table above lands in PDF
`/Creator`, **not** `/Producer` — `/Producer` stays `"WeasyPrint {version}"` no matter what. This is
a naming collision worth calling out explicitly in the spec: "Generator" in HTML/PDF terms
(`/Creator`) means "the application that generated the source document" (here: the FLS platform,
i.e. the "Powered by" name), which *is* what the reference design intended — the design's field
mapping is correct, it's just easy to misread "Generator" as "Producer."

### Recommendation for the org-branded report

Set on every render:
- `<title>` — already correct pattern, keep: `"{org_name} — Cohort progress report — {cohort_name}"` (org first, matching the re-brand).
- `<meta name="author" content="{organisation_name}">` — the commissioning organisation, matching the reference design.
- `<meta name="description" content="Cohort progress report for {cohort_name} · Powered by {site_name}">` → PDF `/Subject`.
- `<meta name="generator" content="{site_name}">` → PDF `/Creator` — the platform/"Powered by" brand, not the organisation.
- `<meta name="keywords" content="...">` is optional and low value for an internal report; skip unless a later requirement asks for it.
- Do not attempt to change `/Producer` — it cannot be suppressed or overridden in WeasyPrint 69.0; document this constraint in the spec so nobody spends time on it later.
- Leave `dcterms.created`/`dcterms.modified` unset unless a specific need for machine-readable creation timestamps beyond the visible "Generated" line on the cover surfaces — WeasyPrint already stamps `/CreationDate` at render time by default.

---

## 2. Accessibility / tagged PDF

### Tagged PDF and PDF/UA support in WeasyPrint 69

WeasyPrint has included experimental PDF/A and PDF/UA support since version 57, exposed through the
`pdf_variant` `write_pdf()` option. **[verified]** Accepted values include:
`pdf/a-1b, pdf/a-2b, pdf/a-3b, pdf/a-2u, pdf/a-3u, pdf/a-4u, pdf/a-1a, pdf/a-2a, pdf/a-3a, pdf/a-4e,
pdf/a-4f, pdf/ua-1, pdf/ua-2, pdf/x-1a, pdf/x-3, pdf/x-4, pdf/x-5g, debug` **[verified]** —
[Common Use Cases — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html),
[CourtBouillon: WeasyPrint 57 beta](https://www.courtbouillon.org/blog/00031-weasyprint-57-beta/).

`pdf_variant='pdf/ua-1'` produces a **tagged PDF** with a structure tree derived from HTML — headings,
paragraphs, tables, etc. get corresponding PDF structure tags, and the HTML source order becomes the
PDF's logical reading order. Two hard requirements for a valid PDF/UA-1 document: a non-empty
`<title>` element, and a `lang` attribute on `<html>`. FLS's `report.html` already sets both
(`<html lang="en">` and a `<title>`). **[verified]** — same Common Use Cases page.

Whether FLS should turn `pdf_variant='pdf/ua-1'` on at all is a separate, larger decision (it changes
output structure document-wide, is explicitly called "experimental," and a real-world bug report
(Issue #2153, closed against milestone 66.0) found "strange" tag output for ordinary heading/paragraph
markup) — **out of scope for this narrow research note**, but worth flagging to the spec: PDF/UA is
not a one-line flag to flip on for just the logo; it's a document-wide accessibility variant with its
own validation burden.

### Does `alt` reach the tagged PDF as an accessible name?

**Could not fully confirm from source.** The general and expected behavior for a tagged-PDF generator
building a structure tree from HTML is that an `<img alt="...">` becomes a `Figure` structure element
whose `/Alt` entry carries the `alt` text (this is exactly what PDF/UA requires of any non-decorative
image, and what tools like Prince/wkhtmltopdf-with-tagging/Chromium's PDF tagging do). One community
report (a Medium piece on WeasyPrint + PDF/UA) claims the opposite for some past version — "images
will be embedded but there is no text alternative, and screen readers will not recognize the images
even though they're visible in the PDF" — but that source is not the WeasyPrint project itself, gives
no version number, and is not corroborated by anything in WeasyPrint's own issue tracker that was
found in this pass. **[inferred, low confidence]**: treat WeasyPrint 69's `alt`-to-`/Alt` mapping as
unverified. If the org logo's accessible name matters for a real deliverable (rather than for this
narrow branding change), that mapping should be empirically checked against the actual installed
WeasyPrint 69.0 (e.g. render a one-image test doc with `pdf_variant='pdf/ua-1'` and inspect the
structure tree with `pikepdf`/`pypdf`) before relying on it — do not assume either way.

Separately from PDF/UA tagging: even without `pdf_variant` set at all (FLS's current, untagged-PDF
default), the `alt` attribute is still correct/required HTML per WCAG and is what any assistive tool
reading the *HTML* render (if one is ever exposed, e.g. an HTML preview) would use, and costs nothing
to set correctly regardless of whether WeasyPrint currently threads it into the tag tree.

### Is `alt=""` still correct for the org logo?

Current FLS markup (`title_page.html`):
```html
{% if site_logo_url %}<img class="cover-logo" src="{{ site_logo_url }}" alt="">{% endif %}
<span class="cover-site">{{ data.site_name }}</span>
```
`alt=""` is correct **today** because the mark is genuinely decorative — the adjacent `<span>` already
carries the site name as real text, so a screen reader (or a PDF/UA consumer, if/when tagging is
enabled) loses no information by skipping the image; this is the standard WCAG pattern for a logo
image paired with visible text of the same name (a logo next to its own name in text is "decorative
duplicate," not "informative").

**Once the org logo becomes primary:** if the new cover markup keeps an adjacent text element that
states the organisation's name in full (e.g. `<span class="cover-org">{{ data.organisation_name }}</span>`
next to the `<img>`, mirroring the current site-name pattern), `alt=""` **stays correct** — same
reasoning, just pointed at the org's identity instead of the site's.

**If the design instead relies on the logo alone to carry the org's identity** — e.g. a design that
drops the adjacent org-name text and expects the logo image itself to be the only thing that says
"AeroVista Flight Academy" — then the image is no longer decorative and `alt` must carry the
organisation's name as real text: `alt="{{ data.organisation_name }}"`. This is standard WCAG
practice (an informative image's `alt` states what the image conveys, not that it's "a logo") and
applies regardless of whether WeasyPrint's tagged-PDF `/Alt` mapping above is confirmed — the
attribute is required-correct HTML either way, and becomes load-bearing for accessibility if and when
PDF/UA tagging is enabled later.

Given the idea file explicitly says "the design should not be considered a source of truth" and only
"lay[s] out the various brand names well," and the current FLS pattern is text-beside-logo throughout
(cover, and the reference design's `band-powered` also pairs the "Powered by" wordmark with an actual
`band-brand` text span, not an image) — **the low-risk, consistent choice is to keep the organisation
name as visible text beside the org logo everywhere it appears**, which keeps `alt=""` correct
end-to-end and avoids depending on the unconfirmed `alt`→`/Alt` tagging behavior at all.

---

## 3. Print legibility of logos

FLS accepts an **arbitrary uploaded** organisation logo — any aspect ratio, PNG/JPEG/WebP, possibly
with alpha transparency, no requirement that the admin supply light/dark or greyscale variants. This
is a materially harder case than a hand-designed brand system that ships pre-made variants for every
background, so the defensive posture has to be conservative by default rather than relying on the
uploader having made good choices.

**General print/brand-system guidance found (not WeasyPrint-specific):**

- **Reversed/knockout variant is standard practice, not optional.** Brand systems universally ship a
  full-colour version for light backgrounds and a reversed (white/light) version for dark ones — "the
  white reversed logo must be used on dark backgrounds" — precisely because a single logo asset is
  not expected to read correctly on both. **[verified — general practice]** [Logo usage guidelines — Vistaprint](https://www.vistaprint.com/hub/logo-usage-guidelines), [How to Create a White Logo — Lovable](https://lovable.dev/guides/how-to-create-a-white-logo).
- **Greyscale/single-colour fallback is expected for cost-constrained or mono printing.** "Black,
  greyscale and single colour versions should only be used in instances where colour printing is not
  an option" — implying a real brand system tests and ships one. **[verified — general practice]** [Defining & Communicating Your Logo Uses — Extensis](https://www.extensis.com/extensis-blog/defining-communicating-your-logo-uses).
- A single arbitrary uploaded PNG/JPEG/WebP has **none of these variants** — FLS gets exactly one
  asset from the admin, at one colour treatment, with unknown contrast against whatever background
  the template places it on.

**Implication for FLS's specific situation (an uploaded mark with alpha transparency on a solid
`--color-primary` band, as the current cover band and the reference design's `cover-band` both use):**

1. **Alpha transparency on a coloured band is the highest-risk case.** A logo with transparent
   background, authored assuming a *white* canvas, will show the theme's primary colour showing
   through gaps in the mark (letterforms, negative space) — at best a colour clash, at worst
   illegible strokes if the logo's own ink colour is close to the band colour. **[inferred, direct
   consequence of alpha compositing — not something requiring a citation, it's how alpha blending
   works]**.
2. **A dark logo on a dark band, or a light logo on a light band, is a contrast failure** — no
   different in mechanism from any other foreground/background contrast problem, and FLS cannot know
   the uploaded logo's dominant luminance without inspecting the pixels. WCAG's 4.5:1 non-text
   contrast guidance is the usual reference point brand systems cite when deciding dark-vs-light
   variants. **[verified — general practice cited above]**.
3. **Standard defensive measure: a neutral "plate" behind the mark.** Rather than trying to detect the
   logo's colour and choose a matching band colour (fragile, and wrong for any logo with internal
   colour variation), the robust fix used throughout print/UI design is to place the logo on its own
   small white or near-white card/plate with padding, and put *that* plate on the coloured band —
   i.e. never composite an arbitrary-colour transparent logo directly onto a brand-colour fill.
   **[inferred from general contrast/plate practice — no single citation states this as a rule, but
   it's the standard mechanism (e.g. white circle/rounded-rect behind a sponsor logo on a colour
   backdrop) used precisely because it works for *any* uploaded logo without inspecting its colours]**.
4. **Greyscale printing:** FLS's own report already treats "survives greyscale" as a first-class
   constraint for status colours (`print.css` comment: "so the report stays readable in greyscale
   print" — status cells always pair a colour with a glyph and a number for exactly this reason). The
   same logic extends to the logo: if the deployment's printer/copier renders in mono, a low-contrast
   logo-on-band or logo-with-transparency problem gets *worse*, not better, because hue difference
   that separated logo from band in colour disappears in grey. The neutral-plate fix in point 3 also
   protects the greyscale case, since white-plate-on-solid-band still shows as light-on-dark in
   greyscale.
5. **Low-resolution uploads at print size** — see the arithmetic in section 4 below.

---

## 4. Effective resolution rule of thumb

**Standard print resolution reference points [verified — general print practice]:**
300 dpi is the conventional "full quality" print target; 150 dpi is an accepted lower bound for
material viewed at normal reading distance (vs. 72–100 dpi only for large-format/viewed-from-a-distance
work like banners). [Standard DPI & Image Resolution for Quality Printing](https://www.printingforless.com/resources/image-resolution-for-printing/), [Print DPI Guide — PrintNinja](https://printninja.com/printing-resource-center/printninja-file-setup-checklist/offset-printing-guidelines/recommended-resolution/).

**Arithmetic, for a logo rendered 12mm tall on A4:**

```
12 mm ÷ 25.4 mm/inch = 0.4724 inch

At 300 dpi (full print quality):  0.4724 in × 300 px/in ≈ 142 px tall needed
At 150 dpi (acceptable minimum):  0.4724 in × 150 px/in ≈  71 px tall needed
```

So a source logo needs **≈142px of vertical pixel height to render crisply at 300dpi**, or **≈71px
at the lower 150dpi bound**, when displayed at 12mm tall.

**Against FLS's accepted upload range (64×32px minimum, 4000×4000px maximum):**

- **Lower bound (64×32px):** if the *smaller* dimension (32px) is the one constrained to 12mm (i.e.
  a wide, short logo whose height governs the fit), the effective resolution is
  `32px ÷ 0.4724in ≈ 68 dpi` — below even the 150dpi "acceptable" floor, and well under the 300dpi
  target. This will look visibly soft/pixelated at close inspection on a printed A4 sheet, though it
  may pass at a glance on a monitor or from arm's length. A logo at exactly the minimum accepted
  dimensions is a genuine risk case, not a hypothetical one.
- **Upper bound (4000×4000px):** vastly more than needed at 12mm print size (4000px at 300dpi covers
  ≈339mm — more than the full A4 height). No legibility problem here; the problem this end of the
  range creates is file size and render time (see section 6) — WeasyPrint embeds the image at native
  pixel resolution by default (`dpi` option default `None` — "maximum resolution of images embedded
  in the PDF," unset means no cap) **[verified]** — [API Reference — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html), so an unnecessarily huge upload inflates the PDF for zero visual benefit.

**Warn vs. block vs. just scale:**

- **Just silently scaling** (what CSS `max-height`/`max-width` on the `<img>` already does today —
  see `.cover-logo { max-height: 12mm; max-width: 55mm; }` in `print.css`) handles the display fit but
  gives the admin **no signal** that their upload will print poorly — the failure mode (blurry logo on
  a mailed/printed report) surfaces long after upload, to a different person (the report's recipient,
  not the uploading admin), and is expensive to trace back to "someone uploaded a 64×40 logo."
- **Blocking outright** is too strict: FLS's own accepted range (64×32 minimum) already permits
  sub-142px logos, implying the system deliberately tolerates lower-resolution uploads (e.g. for a
  quick placeholder, or an organisation that genuinely only has a small source file) — hard-blocking
  would contradict that existing design decision without this research surfacing a stated reason to
  change it.
- **Recommended: warn on upload, don't block.** At upload time FLS can compute the same arithmetic
  above against the fixed 12mm cover-band display height (or whatever the final design's largest
  on-page logo size is) and show a non-blocking warning when the shorter dimension implies **below
  150dpi** at that display size (i.e. below ~71px for a 12mm target) — "This logo may look blurry when
  printed; for best results upload an image at least 71px tall (142px recommended)." This keeps the
  existing accepted range intact while giving the admin an actionable, specific number instead of a
  silent downstream failure.

---

## 5. Colour: WeasyPrint output colour space, ICC, and print shifts

Kept brief per the brief's instruction.

- **Default output is device-dependent RGB**, not an sRGB-tagged colour space with an embedded ICC
  profile — WeasyPrint's own announcement of its wider colour-space work states plainly: "for
  old-school RGB colors in your documents, nothing changes: we use either the device-dependent RGB
  colors (as we did before) or the sRGB colors (with an ICC file, as we already did for PDF/A)."
  **[verified]** — [CourtBouillon: More Colors in WeasyPrint](https://www.courtbouillon.org/blog/00052-more-colors-in-weasyprint/).
  In practice this means: unless a project explicitly opts into an sRGB or custom `@color-profile`
  output intent, or a PDF/A variant (which forces an embedded sRGB ICC profile), the PDF carries raw
  RGB numbers with **no colour-management metadata at all** — every downstream viewer/printer/RIP is
  left to *assume* sRGB, which is the near-universal convention for untagged RGB content but is an
  assumption, not a guarantee. **[inferred from the verified default-behavior statement + general
  colour-management convention]**.
- An `output_intent` option exists (`srgb`, `device-cmyk`, or the identifier of an `@color-profile`
  rule) for projects that need to declare an explicit colour space — not needed for FLS's ordinary
  RGB screen/print report unless a future requirement specifically demands CMYK proofing or archival
  PDF/A/X compliance. **[verified — option exists]**, [CourtBouillon: More Colors in WeasyPrint](https://www.courtbouillon.org/blog/00052-more-colors-in-weasyprint/); exact accepted values not independently re-confirmed against the 69.0 API reference in this pass.
- **Embedded ICC profiles inside an uploaded logo image** (a PNG/JPEG *can* carry its own colour
  profile): whether WeasyPrint honours, converts, or silently ignores an image's own embedded profile
  when compositing it into an untagged-RGB-by-default PDF **could not be confirmed** from the sources
  reached in this pass. **[not verified — flag as open]**. Practical, low-risk stance regardless of
  the answer: since FLS's own PDF output carries no colour-management metadata by default anyway, any
  colour-managed nuance in the uploaded logo (wide-gamut or CMYK-tagged source) is likely to be lost
  or approximated somewhere in the pipeline. The safe recommendation is upload-side, not
  render-side — ask admins to supply logos already flattened to sRGB (the overwhelmingly common case
  for web-exported PNG/JPEG anyway), and don't build render-time ICC handling for this feature.
- **Known real-world risk, independent of WeasyPrint:** sRGB screen colours and CMYK offset/laser
  print output are different gamuts; a brand's saturated primary (electric teal `#00CEC9` in the
  reference design's THEME, for instance) can shift visibly when an sRGB PDF is printed on a CMYK
  device, because teal/cyan-heavy colours sit near the edge of typical CMYK gamuts. This is a general,
  well-known colour-management fact **[verified — general knowledge, e.g.** [ICC Profiles and How Color Management Actually Works](https://auricartisan.com/library/learn/articles/2026-05-25-icc-profiles-color-management), [Color management — Wikipedia](https://en.wikipedia.org/wiki/Color_management)**]**, not something specific to WeasyPrint, and not something this feature needs to solve — office/home printers are the primary target for this report, not colour-managed commercial print, so it's noted for awareness rather than as an action item.

---

## 6. PDF file size: repeated logo across pages, and `@page` margin-box images

- **WeasyPrint embeds an image once and reuses the PDF object, not once per occurrence** — fixed in
  **v53.1**: `"#1414: Embed images once"` (issue: ["PDF file size almost double in v53" / duplicate
  embedding](https://github.com/Kozea/WeasyPrint/issues/1414)), with the general "Improve image
  management" performance work landing alongside it in v53.0. **[verified]** —
  [Changelog — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/changelog.html). The
  earlier report of duplicate embedding inflating file size (["Trim duplicate objects" — issue
  #969](https://github.com/Kozea/WeasyPrint/issues/969), a lucky-draw-ticket PDF where an optimizer
  removed 396 duplicate objects) predates this fix (opened 2019, milestone-closed at v52) and does
  **not** describe FLS's current WeasyPrint version's behavior. Since FLS pins **69.0**, a logo used
  identically on every page (e.g. via a CSS running element in the footer, the same mechanism
  `.footer-identity` already uses for text) should embed **once** and be referenced from every page,
  not duplicated per page. **[verified as of the pinned version]**.
- This directly de-risks the design decision of putting a small "Powered by {site}" logo in the
  footer of every page (in addition to, or instead of, the site-name text `.footer-identity` uses
  today) — the per-page cost is a content-stream reference to a shared XObject, not a repeated image
  payload.
- **Caveat: this only holds for the identical asset.** If a future design places *different* crops
  or *differently-scaled* renditions of the logo on different pages (e.g. a large cover logo and a
  differently-processed small footer mark, rather than the same file at different CSS
  width/height), each distinct image resource is embedded separately — the dedup is per source
  resource, not "any logo anywhere in the document." **[inferred, standard PDF XObject semantics —
  a scaled `<img>` reusing the same `src` is one resource with different placement matrices; a
  different `src` is a different resource]**. Practical guidance: reuse the **same** logo file/URL
  for every occurrence (cover and footer) rather than generating separate pre-scaled variants — matches
  FLS's existing pattern of resolving one `site_logo_url` and reusing it, per `render.py`'s
  `_resolve_logo()`.
- **`@page` margin boxes specifically:** WeasyPrint's `.footer-identity` pattern (`position:
  running(footer-identity)` picked up by `content: element(footer-identity)` in `@bottom-left`) is
  block-level HTML content promoted into the margin box — an `<img>` can be part of that running
  element the same way text is; no WeasyPrint-specific gotcha beyond the general running-element rules
  the existing `print.css` comments already document (must stay block-level; must appear before the
  content it's meant to run alongside, since the running element is captured from its first occurrence
  in flow, not injected fresh per page). No source found describing an image-specific bug in margin
  boxes for WeasyPrint 69 during this pass — treat as working the same way text running elements do,
  but validate with a real render once implemented, given how narrowly-tested WeasyPrint's margin-box
  code paths tend to be flagged elsewhere in this codebase's own comments (e.g. the flexbox caution in
  `print.css`: "WeasyPrint's flexbox support is not well tested").
- **Uploaded-logo file size, independent of the dedup fix:** since `dpi` defaults to `None` (no
  downsampling) and `optimize_images` defaults to `False` **[verified, section 4]**, a 4000×4000px
  upload is embedded at full native resolution regardless of how small it's displayed — a single
  such logo, even embedded only once thanks to the v53.1 fix, could still be several hundred KB to
  a few MB of dead weight in every generated report. Given FLS renders potentially many reports (one
  per cohort, possibly regularly), this is worth a cheap mitigation: either downsize the uploaded
  image server-side to a sane cap at upload time (simplest, and gives the admin one clear number to
  reason about) or pass `optimize_images=True` (and optionally a `dpi` cap) to `write_pdf()` — the
  latter costs "slightly increased" render time per WeasyPrint's own docs. **[verified — options
  exist and behave as described in section 4]**.

---

## Recommendations

Concrete, testable rules for the spec to adopt:

1. **Set PDF metadata explicitly, every render:**
   - `<title>` → `"{organisation_name} — Cohort progress report — {cohort_name}"`.
   - `<meta name="author" content="{organisation_name}">` (→ PDF `/Author`).
   - `<meta name="description" content="Cohort progress report for {cohort_name} · Powered by {site_name}">` (→ PDF `/Subject`).
   - `<meta name="generator" content="{site_name}">` (→ PDF `/Creator`, the "Powered by" brand — **not** `/Producer`, which WeasyPrint fixes to `"WeasyPrint {version}"` unconditionally and cannot be overridden).
   - Leave `dcterms.created`/`dcterms.modified` and `<meta name="keywords">` unset unless a separate requirement calls for them.
2. **Never place the uploaded org logo directly on the theme's primary-colour band** (or any solid
   brand-colour fill) if it may carry alpha transparency and arbitrary ink colour — composite it on a
   small neutral (white/near-white) plate first, and put the plate on the coloured band. This is the
   only defensive measure that works without knowing the uploaded logo's own colours, and it also
   protects the greyscale-print case.
3. **Keep the organisation's name as visible text beside the org logo** everywhere it appears (cover,
   and footer if a mark is added there), matching FLS's existing site-name pattern. This keeps
   `alt=""` correct on the logo `<img>` (genuinely decorative, since the adjacent text already states
   the identity) and avoids depending on WeasyPrint's unconfirmed `alt`→PDF-`/Alt` tagging behavior.
   Only set `alt="{{ data.organisation_name }}"` if a later design change drops that adjacent text and
   makes the logo the sole carrier of the org's name.
4. **Warn (don't block) at logo upload time** when the shorter pixel dimension implies below ~150dpi
   effective resolution at the largest size the logo is displayed in the report (≈71px for the current
   12mm cover-logo height; recompute if the final design's display size differs) — e.g. "This logo may
   print blurry; ≥142px tall is recommended for crisp 300dpi print, ≥71px is the minimum for
   acceptable quality." Compute per upload against the fixed display size(s) the template actually
   uses, not a generic threshold.
5. **Reuse the same logo file/URL for every occurrence** in the document (cover, footer) rather than
   generating separately-cropped or pre-scaled variants — WeasyPrint 69.0 (fixed since v53.1) embeds
   one shared PDF object per distinct image resource and references it from every page, so identical
   reuse is essentially free; distinct resources are not deduplicated against each other.
6. **Cap logo cost at the top end too:** either downsize an oversized upload (e.g. above some cap
   like 1000×1000px, well beyond anything a 12mm–55mm-wide print placement needs) server-side at
   upload time, or pass `optimize_images=True` (and consider a `dpi` cap) to `write_pdf()`. Either
   is sufficient; upload-time downsizing is simpler to reason about and doesn't cost render time on
   every report generation.
7. **Do not build render-time ICC/colour-profile handling** for this feature. WeasyPrint's default
   RGB output carries no colour-management metadata regardless, so there is no render-time lever that
   meaningfully improves colour fidelity; if colour accuracy on commercial print output becomes a real
   requirement later, that's a separate, larger `output_intent`/PDF-X investigation, not part of this
   branding change.
8. **PDF/UA tagging (`pdf_variant='pdf/ua-1'`) is out of scope for this feature.** It's a
   document-wide, experimental variant with its own validation burden (a real bug report exists for
   ordinary heading/paragraph tagging), not a one-line addition for the logo alone. Flag it as a
   possible future accessibility track, not something this branding change should attempt.

---

## Sources

- [API Reference — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- [Common Use Cases — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html)
- [Changelog — WeasyPrint 69.0](https://doc.courtbouillon.org/weasyprint/stable/changelog.html)
- [CourtBouillon: WeasyPrint 57 beta (PDF/A, PDF/UA introduction)](https://www.courtbouillon.org/blog/00031-weasyprint-57-beta/)
- [CourtBouillon: More Colors in WeasyPrint](https://www.courtbouillon.org/blog/00052-more-colors-in-weasyprint/)
- [GitHub Issue #2118 — Allow suppressing the Producer metadata](https://github.com/Kozea/WeasyPrint/issues/2118)
- [GitHub Issue #949 — PDF metadata from HTML](https://github.com/Kozea/WeasyPrint/issues/949)
- [GitHub Issue #2153 — PDF/UA accessibility, labeled strange](https://github.com/Kozea/WeasyPrint/issues/2153)
- [GitHub Issue #969 — Trim duplicate objects](https://github.com/Kozea/WeasyPrint/issues/969)
- [GitHub Issue #1414 — PDF file size almost double in v53](https://github.com/Kozea/WeasyPrint/issues/1414)
- [Standard DPI & Image Resolution for Quality Printing](https://www.printingforless.com/resources/image-resolution-for-printing/)
- [Print DPI Guide: 72 vs 300 DPI — PrintNinja](https://printninja.com/printing-resource-center/printninja-file-setup-checklist/offset-printing-guidelines/recommended-resolution/)
- [Logo usage guidelines — Vistaprint](https://www.vistaprint.com/hub/logo-usage-guidelines)
- [How to Create a White Logo — Lovable](https://lovable.dev/guides/how-to-create-a-white-logo)
- [Defining & Communicating Your Logo Uses — Extensis](https://www.extensis.com/extensis-blog/defining-communicating-your-logo-uses)
- [ICC Profiles and How Color Management Actually Works — Auric Artisan](https://auricartisan.com/library/learn/articles/2026-05-25-icc-profiles-color-management)
- [Color management — Wikipedia](https://en.wikipedia.org/wiki/Color_management)

Repository files read directly (not web sources): `freedom_ls/reports/render.py`,
`freedom_ls/reports/templates/reports/report.html`,
`freedom_ls/reports/templates/reports/partials/title_page.html`,
`freedom_ls/reports/static/reports/print.css`,
`spec_dd/2. in progress/report-rendered-with-org-name/report design/build_report.py`,
`spec_dd/2. in progress/report-rendered-with-org-name/idea.md`.

---

status: ok
reason: Researched WeasyPrint 69.0 PDF metadata field mapping, tagged-PDF/PDF-UA support and alt-text carry-through, print legibility guidance for arbitrary uploaded logos, effective-resolution arithmetic, colour-space/ICC behavior, and per-page image deduplication/file-size behavior, all cross-checked against the current FLS report implementation and the reference design; findings and recommendations written to this file with sources cited and verified/inferred distinguished throughout.
