# Research: co-branded report layout (organisation-primary, platform "Powered by")

Scope: design/document-craft research for `report-rendered-with-org-name` — how to re-hierarchise
the cohort progress report so the customer **Organisation** is the primary brand and the FLS/site
platform brand is demoted to a "Powered by" mark, per `idea.md`. This is not an implementation
spec; it recommends a target layout and flags product questions.

Sources read in-repo:
- `spec_dd/2. in progress/report-rendered-with-org-name/idea.md`
- `spec_dd/2. in progress/report-rendered-with-org-name/report design/build_report.py` (+ rendered sample PDF)
- `freedom_ls/reports/templates/reports/partials/title_page.html`
- `freedom_ls/reports/templates/reports/report.html`
- `freedom_ls/reports/static/reports/print.css`
- `freedom_ls/reports/render.py`, `freedom_ls/reports/gather.py`
- `freedom_ls/organisations/models.py`, `freedom_ls/organisations/validators.py`
- `freedom_ls/base/initials.py`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html`
- `.claude/skills/brand-guidelines/SKILL.md`

---

## 1. Established conventions for co-branded documents

The general pattern across brand-system documentation is **hierarchy through relative weight and
position, not proximity**: the primary brand owns the most prominent real estate (top-left or
top-of-page, largest type/mark), and the secondary "provider"/"powered by" mark is smaller, lower
in the visual order, and never adjacent-and-equal in size to the primary mark.

Concrete rules of thumb found in public brand-system and co-branding guidance:

- **Clear space**: reserve a protective margin around a logo scaled to a feature of the mark
  itself (e.g. the height of a letterform in the wordmark), so nothing — including the *other*
  brand's mark — sits inside it. Android's partner guidance uses the height of the lowercase "o"
  as the clear-space unit ([Google Partner Marketing Hub, Android logo lock-ups](https://partnermarketinghub.withgoogle.com/brands/android/visual-identity/visual-identity/logo-lock-ups/)).
- **Minimum separation between two marks in a lockup**: PTC's brand guide requires partner and
  house logos to sit no closer than 1.3× the height of the house mark
  ([PTC Brand Guide, Partner and Co-Branding](https://www.ptc.com/en/brand-guide/logos/partner-and-co-branding)).
- **Relative size**: co-branding guidance consistently frames size as a hierarchy signal — a
  dominant partner's mark is sized up and a subordinate "powered by"/attribution mark is sized
  down and simplified (icon-only or wordmark-only, dropping a lockup's secondary elements) once it
  drops below a legibility threshold ([Android lock-ups](https://partnermarketinghub.withgoogle.com/brands/android/visual-identity/visual-identity/logo-lock-ups/); [Frontify, Logo Usage Guidelines](https://www.frontify.com/en/guide/logo-usage-guidelines)).
- **Never adjacent-and-equal**: the recurring warning in co-branding write-ups is that two marks
  of equal size, next to each other, read as an *unweighted partnership* (a merger or a joint
  venture), not as "brand X, delivered on platform Y". If the goal is a clear owner + a clear
  attribution, equal-weight adjacency is the one layout to avoid
  ([Designhoops, 4 Crucial Co-Branding Guidelines](https://designhoops.com/4-crucial-co-branding-guidelines/); [Penn State AgSci, Co-branding](https://agsci.psu.edu/brand/extension/co-branding)).

The reference `build_report.py` sample already follows this: the partner wordmark is ~17pt on the
cover header, the "Powered by First Class" wordmark in the cover band is ~11pt, and the same
"Powered by" mark in the interior footer is 7pt — three deliberately decreasing sizes for the
same secondary mark, never sized to compete with the primary wordmark (30pt title / 17pt cover
wordmark).

**Applies to FLS**: the existing `.cover-site` (13pt, `--color-primary`) is currently the *only*
brand mark on the cover and is already sized like a primary mark. Re-purposing that slot for the
organisation and demoting the site's mark to a genuinely smaller "Powered by" treatment (not just
relabelled at the same size) is what the above sources would call correct; simply swapping label
text at the same visual weight would not read as a hierarchy change.

## 2. Where "Powered by" belongs: cover band vs footer vs both

Trade-offs, given the report is commonly 20+ pages, may be printed, may be forwarded (as a whole
PDF or as an extracted page), and is a compliance/record artefact for the organisation:

- **Cover-band only.** Cheapest, and matches the idea note ("the powered by section can go in the
  footer" — but also references the sample's cover band, which *also* carries it). Risk: if any
  single page is extracted or the PDF is forwarded starting mid-document (a screenshot of the
  summary table, a single learner's page emailed to a parent/employer), there is no attribution or
  provenance mark on it at all. For FLS specifically — an open-source project whose brand-guidelines
  skill explicitly treats "Powered by FreedomLS" as *the* sanctioned attribution surface ("Orgs
  using FreedomLS may show 'Powered by FreedomLS' in footer/about", `.claude/skills/brand-guidelines/SKILL.md`) — losing that attribution once a page leaves the cover is a real cost to the
  platform, not merely a nice-to-have.
- **Footer only, every page.** Guarantees provenance survives page extraction and photocopying.
  The risk on a 20+ page report is that a *tiny*, static, identical line repeated 20+ times reads
  as filler rather than reassurance — but only if it is visually loud. At the size and weight
  already used in the current footer (`.footer-identity`, 7pt, `--color-muted`) and in the sample
  (7pt, muted grey, page-corner-adjacent), repetition reads as **document furniture** (like a
  running page-number or a letterhead), which is the established convention for this kind of
  attribution — compare a law firm's "Prepared by [X]" on every page of a contract, or a SaaS
  invoice's "Powered by Stripe" on every emailed receipt page. Low-contrast, small, and
  consistently positioned is what keeps repetition from reading as clutter; the failure mode is
  making it large or brand-coloured, not making it present.
- **Both (cover band + every-page footer).** What the reference design does, and what most
  co-branded compliance documents do (bank statements, LMS certificates, e-signature platforms):
  a *prominent* one-time attribution at first contact (the cover), and a *quiet, findable*
  attribution that survives being separated from the cover. This is the safer default for a
  document whose whole raison d'être is being extracted, filed, and forwarded — a cohort progress
  report is read by educators, but excerpted for compliance/audit and to parents/funders/
  employers.
- **Back page.** Rejected as a *sole* location: nothing in the reviewed sources treats "last page"
  as a reliable attribution location for a multi-page PDF, and unlike a printed booklet a PDF's
  last page is not a fixed physical location a reader reliably reaches (many reports are read via
  a page picker or a bookmark, jumping straight to a learner's section). Fine as an *additional*
  colophon/about-this-report location, not as a substitute for the footer.

**Recommendation for FLS**: keep the "Powered by" mark in *both* the cover band and the per-page
footer, matching the reference design and the existing `.footer-identity`/`.cover-band`
mechanisms already in the template — this is a labelling change to those two mechanisms, not a
new one.

## 3. Handling arbitrary organisation logos in a fixed layout

`Organisation.logo` (`freedom_ls/organisations/models.py`, validated in
`freedom_ls/organisations/validators.py`) accepts PNG/JPEG/WebP from 64×32px to 4000×4000px with
**no aspect-ratio constraint** — an org can upload a wide banner wordmark, a square/circular
badge, or a tall crest, and the layout must not assume any of them.

Standard containment approach, and the one FLS already uses for the site logo
(`.cover-logo { max-height: 12mm; max-width: 55mm; }` in `print.css`) and for the learner-facing
organisation chip (`h-8 max-w-32 ... object-contain`, `course_toc_header.html`):

- **Fixed-height (or fixed-height-and-width-capped) box**, image scaled with `object-fit: contain`
  (browser-facing) / natural aspect-ratio-preserving `<img>` sizing under WeasyPrint (WeasyPrint
  honours `max-height`/`max-width` on `<img>` while preserving intrinsic aspect ratio, which is
  the same effect as `object-fit: contain` without WeasyPrint needing to support the CSS property
  itself — worth confirming `object-fit` support explicitly rather than relying on it, since
  WeasyPrint's CSS coverage is narrower than a browser's).
- **Contain, not cover, and never crop.** A logo is not decorative photography; cropping any part
  of a submitted mark (cutting a wordmark's descenders, or a badge's outer ring) reads as broken,
  not stylised — cropping is the wrong failure mode for a corporate identity asset. Letterboxing
  (extra whitespace on the narrow axis) is the correct, boring, universally-used choice —
  see the `object-fit: contain` discussion in [MDN's object-fit reference](https://developer.mozilla.org/en-US/docs/Web/CSS/object-fit) and the practical write-up in [Smashing Magazine's object-fit / background-size deep dive](https://www.smashingmagazine.com/2021/10/object-fit-background-size-css/).
- **Background chip/plate.** FLS already uses this on-screen (`bg-surface border border-border`
  chip behind the org logo in `course_toc_header.html`), specifically because a mark with
  transparency needs a guaranteed-opaque, guaranteed-legible surface regardless of what colour
  sits behind it. On the report cover this matters less if the cover background is fixed white —
  a chip is redundant there and adds visual noise the reference design doesn't have (its cover
  wordmark sits directly on white paper). A chip **does** matter if the org logo is placed inside
  the cover band, which is a solid brand-colour fill (`--color-primary`): a dark-on-transparent
  logo would partly disappear against that fill without a light plate behind it. Recommendation:
  no chip on the white cover area; a chip (or the "contain within a light plate") if any org mark
  is ever placed on a coloured band.
- **Letterbox vs crop, decided once and applied everywhere**: letterbox (contain-fit inside a
  fixed box, image never distorted or clipped) should be the only supported behaviour — this
  matches both existing FLS precedents (`.cover-logo`, the TOC chip) and every general design
  source reviewed.

## 4. Fallback ladder when an organisation has no logo

FLS already has the pieces of a ladder, but they are only wired up on screen, not in the report:

1. `Organisation.logo` — an uploaded mark (may be blank).
2. `Organisation.initials` (`freedom_ls/organisations/models.py`) — a 1–2 character monogram
   derived from the name, script-aware via `base.initials.two_or_one` / `is_latin`: two Latin
   initials (`"AeroVista Flight Academy"` → `AF`) but a single grapheme for non-Latin scripts,
   because two CJK/Arabic/etc. characters can read as a word fragment rather than a monogram
   (`freedom_ls/base/initials.py`).
3. A generic/unknown icon — `<c-icon name="unknown">` in `course_toc_header.html`, used only when
   `initials` itself is `None` (a name with no alphabetic characters at all).
4. The organisation **name as wordmark** — not currently a documented step in the ladder, but
   used implicitly: the `course_toc_header.html` chip always shows the logo/initials-or-icon
   *plus* the name as text beside it, so "no logo" never means "no visible identity", it means
   "monogram instead of a graphic mark".

**Does the same ladder transfer to print?** Mostly yes, with one adjustment. On screen the chip is
small and sits beside other UI, so a monogram circle reads as a normal, deliberate "avatar" —
users are acclimatised to initials-as-avatar from every product with user/org avatars. On a report
**cover**, which is presented as a formal, single-purpose ceremony page (the sample's cover has
nothing else competing with the wordmark), a small circular monogram in the same top-left position
a full wordmark would otherwise occupy risks reading as a *broken image placeholder* rather than a
deliberate design choice, because a cover page sets an expectation of "this is the one brand
statement" that a UI chip does not.

The safer print fallback, in priority order:
1. **Logo present** → contained image, per §3.
2. **No logo** → **organisation name set as a wordmark** (large, brand-primary-coloured type,
   in the same slot the logo would occupy) — this is what the reference `build_report.py` sample
   effectively does even *with* a nominal logo concept: `.wordmark` is typographic, not an
   `<img>`, and it looks fully deliberate. A name-as-wordmark cover reads as intentional identity
   design far more reliably than a monogram badge does at cover scale.
3. **Monogram** reserved for smaller, secondary placements only (the interior footer/running
   header, if an organisation mark is ever wanted there beside the org name) — the same scale at
   which it already succeeds in `course_toc_header.html`.
4. **Generic icon** — last resort, and only where `initials` is itself `None` (no alphabetic
   characters at all in the org name); vanishingly rare for a real organisation name, so this
   should not need cover-scale treatment.

In short: reuse `initials` and the `logo → initials → icon` *fallback machinery*, but change which
rung the cover page lands on relative to the UI chip — **name-as-wordmark**, not monogram, is the
print cover's no-logo default.

## 5. Typographic hazards

- **Very long organisation names** ("AeroVista Advanced Aeronautical Flight & Ground Crew Training
  Academy (Pty) Ltd") on the cover wordmark slot and in the per-page footer identity line.
  - No JS is available (WeasyPrint only), so **CSS `text-overflow: ellipsis` is the wrong tool**:
    it needs a fixed single-line box with `overflow: hidden` and `white-space: nowrap`, and
    WeasyPrint's support for `text-overflow` is inconsistent/partial across versions — relying on
    it for a legal entity's name risks silently truncating without the visible ellipsis in some
    renders. Prefer either (a) **wrapping** with a reduced, still-legible minimum font size and a
    fixed line-count budget (e.g. cover wordmark allowed 2 lines, footer identity allowed to wrap
    to a second running line only if unavoidable), or (b) a **server-side truncation** done in
    Python before the name ever reaches the template (compute a display name capped at N
    characters with an explicit `…`, so truncation is deterministic and testable, rather than
    relying on the renderer).
  - **Auto-fit / shrink-to-fit** (scaling the wordmark's font-size down until the string fits its
    box) is the visually best option for a cover — it's what most badge/certificate generators do
    — but WeasyPrint has no live layout feedback loop for CSS-only shrink-to-fit; achieving it
    would mean measuring the string's rendered width in Python (e.g. via the chosen font's metrics)
    before rendering and choosing a font-size class from a small stepped scale (e.g. 3–4 discrete
    sizes: full/condensed/small), similar in spirit to how the report already computes derived
    data once rather than in the template. This is a real implementation cost worth flagging
    rather than assuming CSS alone solves it.
  - The **footer identity line** is a worse location for a long name than the cover: it already
    concatenates multiple fields with " · " separators on one line
    (`{{ data.site_name }} · {{ data.organisation_name }} · Cohort progress report · {{ data.cohort_name }}`),
    and a long org name there can push the trailing fields (or crowd the page-number/Powered-by
    slots, which are separate `@bottom-*` running elements sharing the same margin box row) into
    an overlap. This is the strongest argument for shortening what the footer identity line
    carries at all (see §6) rather than trying to make one long concatenated string fit reliably.
- **Non-Latin-script names.** `Organisation.initials` already handles the monogram case correctly
  (falls back to one grapheme). For the *wordmark* rendering, the report's embedded fonts
  (`build_font_css()`, Outfit/DM Sans/IBM Plex Mono per `render.py`) are Latin-only Google-Fonts
  derivatives; an organisation name in Cyrillic, Arabic, Devanagari, CJK, etc. would fall back to
  WeasyPrint's system/DejaVu fallback (the same "glyph fallback" note already present in the
  reference script's font comment), which will not match the brand-primary display face's weight
  or style and may look visually broken next to Latin surrounding text (mixed-script line, mixed
  face). This is a real gap: either the font stack needs a non-Latin-capable fallback face bundled
  alongside the display fonts, or the wordmark treatment needs a documented "falls back to system
  sans, still legible, not visually matched" acceptance rather than treating it as solved.
- **Names that already contain "Academy"/"Training"/"Institute" etc.**, sitting directly above a
  report title that also uses institutional language ("Cohort progress report"). The reference
  sample sidesteps this by giving the org wordmark a *descriptor* line (an accreditation number,
  §7) rather than a second word like "Academy" repeating near "report" — worth flagging as a
  reason the descriptor slot may be doing double duty (disambiguating context) rather than being
  purely decorative.

## 6. The identity line

Current footer line, one running element (`.footer-identity` in `report.html`/`print.css`):

```
{{ data.site_name }} · {{ data.organisation_name }} · Cohort progress report · {{ data.cohort_name }}
```

That is site-first, org-second — the exact hierarchy the idea asks to invert. Once "Powered by
`<site>`" exists as its own `@bottom-center` running element (as in the reference CSS: `@bottom-
center { content: "Powered by $footPoweredBy" }`), keeping the site name *again* in the identity
line is redundant on every single page — the same fact stated twice in the same footer row.

Recommended reordering, dropping the redundant site mention:

```
{{ data.organisation_name }} · {{ data.cohort_name }} · Cohort progress report
```

Rationale:
- Organisation leads, matching the cover's new hierarchy — the footer should not silently disagree
  with the cover about which brand is primary, and it puts the organisation at the corner where a
  reader's eye naturally starts.
- `Cohort progress report` moved last: it is the one constant, generic string across every report
  a given organisation ever receives, so it carries the least information per page and belongs at
  the low-information end of the line (readers scanning a stack of reports for "which org, which
  cohort" don't need "cohort progress report" repeated at the front).
- Site name dropped from this line entirely — it now lives once, quietly, in the adjacent
  "Powered by `<site>`" running element, which is the correct single home for it per §2. Keeping
  it in *both* places is the redundancy this change should remove, not preserve.

## 7. Optional descriptor/strapline

The reference design's `partner_descriptor` ("SACAA ATO 0231") sits directly under the wordmark in
a small mono line, and does real work in that sample: it disambiguates a flight-training org from
any other similarly-named org, and it signals *accredited/regulated* — a trust marker a training
provider plausibly wants on every report a learner or employer might see.

Assessment:
- **Worth having as an optional field**, not a required one — same optionality pattern FLS already
  uses for the site logo (`site_logo_url` conditional block in `title_page.html`) and for the org
  logo/initials ladder: a fresh org configures none of it and the cover must still read as
  finished.
- **Cost**: one more nullable `CharField` on `Organisation` (or a small free-text field scoped to
  report branding specifically, if it's meant to differ from anything shown elsewhere), one more
  conditional block in `title_page.html`, one more line in `print.css`. Low schema/template cost.
  The larger cost is product-definition, not code: what the field *means* is ambiguous — an
  accreditation number, a tagline, a legal registration string, and a marketing strapline are four
  different things with four different appropriate typographic treatments (mono/numeric vs.
  italic/wordmark-style), and a single freeform field invites all four. If adopted, the field
  should be named and documented for one specific purpose (e.g. "accreditation / registration
  line") rather than a generic "subtitle", so organisations don't put a marketing tagline there and
  get a numeric-looking mono treatment, or vice versa.
- **Alternative**: skip the dedicated field for v1 and treat this as a possible follow-up once
  real customer orgs are onboarded and it's clear whether they actually want it — the idea and the
  reference design both treat the wordmark + logo as the must-have, and the descriptor as
  reference-only polish ("It does lay out the various brand names well" — idea.md is explicit that
  the reference is not a source of truth for scope).

---

## Recommendation

**Cover** (`title_page.html` / `.title-page` in `print.css`):

```
┌───────────────────────────────────────────────────┐
│  [org logo, contain-fit box]  AeroVista Flight     │  <- org logo if present, else org
│                                Academy               │     name as wordmark (large,
│                                                      │     brand-primary colour)
│  ───────────── accent rule ─────────────            │
│                                                      │
│                                                      │
│                    Cohort progress report            │
│                    RPC 2026-03 · Johannesburg intake │
│                                                      │
│                    [courses-covered card]            │
│                    [generated / by / cohort size]    │
│                                                      │
├───────────────────────────────────────────────────┤
│ Powered by <site wordmark, small>   Learner progress │
│                                       · RPC 2026-03  │
└───────────────────────────────────────────────────┘
```

- Replace `.cover-brand`'s `site_logo_url` + `data.site_name` with `organisation.logo` (contain-fit,
  same box geometry FLS already uses) falling back to organisation name set as a large wordmark
  (§4) — never a monogram at this scale.
- Keep `.cover-accent` as the divider it already is.
- `.cover-band` keeps its existing position/geometry but its content flips: the **left** slot
  becomes "Powered by `<site>`" (small wordmark or, absent one, site name at a size visibly
  smaller than the cover wordmark — enforce this with an explicit smaller font-size token, not by
  relying on "shorter label = looks smaller"), the **right** slot keeps the existing
  cohort/subject note. This mirrors the reference sample's band exactly and reuses the existing
  `.cover-band`/`.band-site` selectors, just re-pointed.
- Optional: if the descriptor field (§7) ships, it sits directly under the org wordmark, small,
  mono, muted — never under "Powered by".

**Interior footer** (`@page` rules in `print.css`, `.footer-identity` running element):

```
<Organisation> · <Cohort>              Powered by <Site>              Page N of M
```

- `@bottom-left`: `.footer-identity` content becomes
  `{{ data.organisation_name }} · {{ data.cohort_name }}` (drop `Cohort progress report` and
  `site_name` per §6 — or, if `Cohort progress report` is judged worth keeping for a reader who
  received only one page out of context, put it last: `organisation · cohort · Cohort progress
  report`).
- `@bottom-center`: new running/string content, `Powered by <site_name>` (or site wordmark image if
  the platform ever wants a mark there rather than text — text is sufficient at 7pt and is what
  the reference sample uses).
- `@bottom-right`: unchanged (`Page N of M`).
- Keep everything at the current 7pt / `--color-muted` treatment — the size and colour are what
  make the repetition read as document furniture rather than clutter (§2).

**No chip/plate on the cover** (white background, direct-on-paper wordmark/logo, matching the
reference sample); reserve the chip/plate treatment for any future placement of an org mark on a
solid coloured surface (the band, or a themed interior page).

---

## Open product questions

1. **Org logo delivery to WeasyPrint.** The site logo is a *static* asset resolved through
   `finders.find()` and named up front in the render's file allowlist (`render.py`,
   `_resolve_logo` / `_restrictive_url_fetcher`). `Organisation.logo` is an **uploaded** media file
   with a storage-backend URL, not a static path — the render module's current "exact-file
   allowlist known before rendering starts" security model will need a parallel path for
   per-organisation uploaded media, not just a relabelling of the existing static-logo plumbing.
   Worth scoping explicitly rather than assuming it's a drop-in swap.
2. **What happens when the report spans multiple organisations?** (e.g. a cohort or report scope
   that is not itself organisation-scoped, or a `Cohort` whose `organisation` can differ from a
   learner's own organisation — needs checking against `gather.py`'s actual `Cohort.organisation`
   semantics.) The current model assumes exactly one organisation per report; confirm that holds
   for every code path that generates this report.
3. **Does the descriptor/strapline field (§7) ship in this iteration, or later?** If yes, what is
   it *for* — accreditation number, legal registration, tagline — since that decides its
   typographic treatment.
4. **Does "Powered by `<site>`" ever need to be an image (site logo), or is text sufficient?** The
   reference sample uses text only in the band and footer; FLS already has a resolvable
   `site_logo_url`. Using it in the band's "Powered by" slot is possible but adds a second
   contain-fit image the layout has to budget space for at a much smaller scale — confirm whether
   product wants the platform mark to ever appear as a *graphic* on the report, or whether text
   attribution is the deliberate, permanent choice (consistent with the brand-guidelines skill's
   "Powered by FreedomLS ... logo mark ... min 120px width" guidance, which assumes a size floor
   that a report footer at 7pt cannot honour — worth reconciling that guidance against report-scale
   reality, or explicitly scoping report footers as a text-only exception).
5. **Truncation/auto-fit for long organisation names (§5)**: accept CSS-only wrapping with a
   sensible max-line budget, or invest in server-side shrink-to-fit sizing? This is a real scoping
   decision with implementation cost attached, not a pure design call.
6. **Non-Latin organisation names (§5)**: accept the system-font fallback as-is for the cover
   wordmark (visually unmatched but legible), or bundle an additional non-Latin display face?
7. **Should `Cohort progress report` stay in the per-page footer identity line at all** (§6), given
   it is redundant with the cover title and adds width pressure to an already-long line next to a
   potentially long organisation name?

status: ok
reason: research complete; findings and recommendation written to research_cobranded_report_layout.md
