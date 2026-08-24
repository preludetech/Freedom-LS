# Reports rendered with the organisation's brand

## The idea

Cohort progress reports currently render the *site's* logo and name as the only brand on the
document. When a report belongs to a specific organisation, that organisation's name and logo
should be the primary brand — front and centre — and the site brand should be demoted to a
"Powered by <site>" mark.

The organisation's brand leads. The platform is attribution, not the headline.

There is a reference design in `report design/` (a standalone script and its rendered sample PDF)
that demonstrates the layout. It was created without knowledge of this repository's functionality
and is **not a source of truth** — it is a reference for how the brand names sit together. It lays
those out well. The logos need to be in place too, which the sample does not exercise.

## Decisions taken

These were settled during idea refinement and should carry into the spec.

**1. Where the platform mark appears.** Both the cover band and every interior page footer, at the
existing small/muted treatment. A prominent one-time mark at first contact, plus a quiet one that
survives a single page being extracted, printed or forwarded — which is what a report used as a
progress record needs.

**2. The house-organisation case.** Every Site auto-creates exactly one `is_default` Organisation.
For cohorts sitting in that house org, the "Powered by <site>" mark is **suppressed** — the primary
brand already is the platform, and showing both says the same thing twice. `is_default` is already
loaded in memory, so detecting this costs no extra query. Note the caveat: an admin can rename the
default organisation so it no longer matches the site name, and this rule suppresses the mark
anyway. That is accepted.

**3. Attribution is always on.** No setting to suppress "Powered by <site>". Comparable products
make it a paid-tier removal, but FLS is not selling tiers, and a visible mark supports provenance
for training records that may be shown to third parties. A toggle can be added later without
breaking anything; it is not needed now.

**4. In scope alongside the branding change:**
- PDF document metadata — Author set to the organisation, generator to the site, so the file's
  document properties agree with its cover. Only `<title>` is set today.
- The download filename carries the organisation name. The *stored* filename stays pk-derived and
  identity-blind by design; only the Content-Disposition name changes.

## The hard part

The organisation logo is not the same kind of thing as the site logo, and this is the main risk in
the whole feature.

The site logo is a **static** asset resolved through the staticfiles finders to a local file path.
`Organisation.logo` is an `ImageField` on **media storage**, which in production may be S3 serving
private signed URLs. The report renderer deliberately confines WeasyPrint to an exact allowlist of
local files and refuses everything else — that boundary exists because reports render
author-supplied text, and it is locked in by an existing test that refuses even a sibling file in
an allowed directory.

So the organisation logo cannot simply reuse the site logo's plumbing:

- A naive `organisation.logo.path` → `file://` implementation **works in development and breaks in
  production**, where `.path` raises on remote storage. This is the single biggest correctness risk
  and belongs in the acceptance criteria explicitly, not left to be found against a real
  S3-backed deployment.
- The recommended approach is to read the logo bytes through Django's storage API and embed them as
  a base64 `data:` URI. This behaves identically on local disk and on S3, because the bytes are
  read before WeasyPrint sees a URL. Verified against the installed WeasyPrint source: `data:` URIs
  do **not** bypass the custom fetcher, so this needs a deliberate, reviewable `data:` branch added
  to it. The existing 2 MiB upload validator bounds the payload, and WeasyPrint de-duplicates
  repeated images at the PDF object level, so a logo on every page is still embedded once.
- The storage read belongs on the gathering side, which is already allowed to touch the ORM. The
  render layer must keep receiving an already-resolved value — it does no ORM access by contract.

## Brand fallbacks

An organisation may have no logo, and the cover has to read as finished rather than broken.

On the **cover**, the fallback is the organisation *name set as a wordmark* — large, in the brand
colour, in the slot the logo would have occupied. Not the initials monogram: the existing on-screen
organisation chip uses a monogram and that reads correctly as an avatar at UI scale, but at cover
scale in a slot that otherwise holds a full mark, a small monogram badge reads as a broken image
placeholder. The monogram stays appropriate for smaller, secondary placements.

Logos are contained, never cropped or distorted — an organisation's mark is an identity asset, and
clipping a wordmark's descenders or a badge's outer ring reads as broken rather than styled. The
codebase already contains this pattern for both the site logo and the on-screen org chip.

The organisation logo is **not** placed on the solid primary-colour cover band — it sits on the
white cover area, and the band carries the small "Powered by" text. This is what makes a protective
plate behind the mark unnecessary; if a later design ever moves an uploaded logo onto a coloured
fill, that decision has to come back, because a dark-on-transparent logo would partly disappear
into the band.

## Known consequences worth stating in the spec

- **Generated PDFs are immutable snapshots.** A report is rendered once and stored; nothing
  re-renders it. An organisation that uploads a new logo does not retroactively change reports
  already generated. This is already true of the current design — the spec should say so plainly
  rather than leave it implicit.
- **The footer identity line should stop naming the site.** It currently reads
  `site · organisation · Cohort progress report · cohort`. Once "Powered by <site>" sits beside it
  in the same footer row, the site name is stated twice on every page. The organisation should
  lead the line instead.
- **Long organisation names** are a real layout hazard, on the cover and in the footer line, and
  CSS-only ellipsis is not reliable under WeasyPrint. The spec needs a deliberate answer
  (wrapping with a line budget, or deterministic server-side truncation) rather than assuming
  CSS handles it.
- **Non-Latin organisation names** fall back to the fallback face, which covers Cyrillic, Greek and
  Arabic but not CJK, and will not match the display face's weight. Worth an explicit accepted
  limitation rather than a silent gap.
- **Logos are raster only** — SVG is deliberately blocked at upload because it is XML that can
  carry scripts. Nobody should expect vector-crisp marks in the PDF.

## Explicitly out of scope

- Any setting to suppress the platform attribution (decision 3).
- A low-resolution warning when a too-small logo is uploaded. Worth revisiting: a logo below roughly
  71px tall cannot print crisply in the current cover slot, and there is no feedback today.
- An organisation descriptor/strapline field (the accreditation line in the reference design's
  sample). Genuinely useful for a regulated training provider, but it is a new field with an
  ambiguous definition, and the reference design is not a scope document.
- PDF/UA tagging. A document-wide accessibility track with its own validation burden, not something
  this branding change should attempt.

## Research

Findings live alongside this file and are cited to sources and to `path:line`:

- `research_fls_report_branding_seams.md` — every seam the change touches, the tests that will need
  changing, and the QA fixture work already in flight.
- `research_weasyprint_logo_embedding.md` — how a storage-backed image reaches WeasyPrint without
  weakening the URL fetcher; verified against the installed WeasyPrint 69 source.
- `research_cobranded_report_layout.md` — co-branding conventions, the fallback ladder, and
  typographic hazards.
- `research_white_label_precedents.md` — how other LMSes brand exported reports. Two of its
  recommendations do not apply to FLS: it suggests preferring SVG logos (deliberately blocked here)
  and treating snapshot-at-generation as a decision (already inherent, since reports render once).
- `research_pdf_metadata_and_print_legibility.md` — PDF metadata fields, alt-text handling, and
  print legibility of uploaded marks.
