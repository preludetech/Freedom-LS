# Research: getting the organisation's media-storage logo into a WeasyPrint render

Scope: how to get `Organisation.logo` (a Django `ImageField`, potentially on S3 with private
signed URLs) into the WeasyPrint-rendered cohort report, without weakening
`_restrictive_url_fetcher` in `freedom_ls/reports/render.py`.

Everything marked **[verified]** was confirmed by reading the actual installed WeasyPrint 69.0
source in this repo's venv (`.venv/lib/python3.13/site-packages/weasyprint/`) or the FLS source
files it discusses. Everything marked **[inference]** is reasoned from that source but not
literally executed (this worker has no `Bash` tool, so nothing here was run — no test render was
performed). Everything marked **[web]** is a claim sourced from WeasyPrint's hosted docs, GitHub
issues, or PRs, cited inline.

Installed versions, confirmed from `uv.lock`: `weasyprint==69.0`, `pillow==12.3.0`,
`pydyf==0.12.1`.

---

## 1. Getting a media-storage image into the render without weakening the fetcher

### Ground truth on the fetch path **[verified, from `weasyprint/urls.py` and `weasyprint/images.py`]**

- Every image WeasyPrint draws — regardless of URL scheme — goes through
  `images.get_image_from_uri(cache, url_fetcher, options, url, ...)`, which calls
  `weasyprint.urls.fetch(url_fetcher, url)`. That `fetch()` context manager is a thin wrapper:
  it calls `resource = url_fetcher(url)` unconditionally (`urls.py:466-471`), then requires the
  result be a `URLFetcherResponse` (or the deprecated dict shape, auto-converted). **There is no
  scheme-based bypass of the custom fetcher anywhere in this path** — a `data:` URI is not
  special-cased to skip `url_fetcher`; it is handed to it exactly like a `file://` or `https://`
  URL. This directly contradicts the "does a `data:` URI bypass the custom url_fetcher" framing
  in the brief: it does **not** bypass it. FLS's `_restrictive_url_fetcher` (`render.py:237-245`)
  currently only branches on `parsed.scheme == "file"` and raises `FatalURLFetchingError` for
  everything else — so **a `data:` URI would currently be rejected** by the existing fetcher and
  must be explicitly allow-listed by scheme if this route is chosen.
- `default_url_fetcher(url, ...)` **is deprecated in 69.0** (`urls.py:185-200`): calling it emits
  a `DeprecationWarning` and internally builds a `URLFetcher(..., allow_redirects=False)` and
  calls `.fetch(url)`. FLS's own docstring in `render.py` already references this history
  ("WeasyPrint 69.0 ships `weasyprint.urls.URLFetcher`... verified empirically against the
  installed version"). **A follow-up worth flagging**: `_resolve_logo`'s current fetcher still
  calls the deprecated `default_url_fetcher(url)` for the allow-listed `file://` case
  (`render.py:244`), which will now emit a `DeprecationWarning` on every render (harmless today,
  but confirms the fetcher should move to `weasyprint.urls.URLFetcher().fetch(url)` or construct
  a `URLFetcherResponse` directly, independent of the organisation-logo work).
- `URLFetcher` (the class-based fetcher `weasyprint.HTML(...)` builds by default when no
  `url_fetcher=` is given) supports `data:` URIs out of the box, because
  `request.DataHandler()` is one of the handlers it registers (`urls.py:304`,
  `request.OpenerDirector` subclass). **[web]** WeasyPrint's own docs state it "can read normal
  files, HTTP, FTP and data URIs" ([API Reference — WeasyPrint stable](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)).
  But FLS does not use the stock `URLFetcher` — it passes its own plain callable
  (`_restrictive_url_fetcher`'s `fetch` closure), so this DataHandler support is irrelevant unless
  FLS's fetcher explicitly decodes `data:` URIs itself or delegates to `URLFetcher()(url)` for
  that one scheme.

### `URLFetcherResponse` contract **[verified, from `weasyprint/urls.py:377-454`]**

The plan referenced in `render.py`'s docstring (a dict with `string`/`file_obj`/`mime_type`/
`redirected_url` keys) is the **deprecated** shape. `urls.fetch()` still accepts it
(`urls.py:473-485`) but warns and will remove support "in WeasyPrint 69.0" per the warning text
(worth noting: the warning claims removal *in* 69.0, yet the installed 69.0 still accepts it —
the deprecation appears to lag its own stated version by at least one release; treat dict support
as present-but-legacy, not guaranteed in the next upgrade). The **current, non-deprecated**
contract is to return a `weasyprint.urls.URLFetcherResponse` instance directly:

```python
URLFetcherResponse(
    url,                 # str — becomes response.url / response.geturl()
    body=None,            # str | bytes | file-like — becomes response.read()
    headers=None,          # dict | email.message.EmailMessage
    status=200,
)
```

Key derived properties: `.content_type` (from `Content-Type` header, defaults to
`application/octet-stream` if unset — `images.py` uses this to decide SVG vs. raster), `.charset`,
`.path` (only set if `url` starts with `file:`). For a `data:` URI or any in-memory bytes,
construct this directly: `URLFetcherResponse(url, body=raw_bytes, headers={'Content-Type':
'image/png'})`, no `URLFetcher` instantiation needed.

### Option comparison

**A. `data:` URI embedded in `<img src>`, bytes read via `field.open()`/`storage.open()`**
[inference, reasoned from verified fetch-path above]
- Bytes are read from Django storage (S3 or local) at HTML-build time (in
  `_build_document()`/a new gather step), base64-encoded, and interpolated into the template as
  `data:image/png;base64,<...>`.
- The custom fetcher needs one new branch: `if parsed.scheme == "data": return
  URLFetcherResponse(url, body=<decoded bytes>, headers={'Content-Type': <mime>})`, or simpler,
  decode inline via `urllib.request.urlopen(url)` (stdlib handles `data:` natively since Python
  3.4) and forward that. Either way this is a small, auditable addition — no new *file* or *host*
  is ever named, so the allowlist model (files or hosts named up front) is preserved in spirit:
  a `data:` URI carries its own bytes, so allowing the scheme cannot be used to read an arbitrary
  local file or reach an arbitrary host. **The one new risk is size, not disclosure**: an
  attacker who could somehow control template context (not the case here — the logo bytes come
  from the gathered `CohortReportData`, itself already trusted server-side data, never
  author-supplied question/option text) could not exploit this for SSRF/LFI, only make the
  document bigger. Given FLS's own 2 MiB logo validator (`organisations/validators.py`), the
  worst case is bounded (~2.7 MiB of base64 text per occurrence — see §4).
- Pros: no temp files, no filesystem coupling, works identically whether the media backend is
  local disk, S3, or anything else Django's storage API abstracts over; the fetcher's allowlist
  model needs only a scheme check, not a per-render mutable path set.
  Cons: base64 inflates the HTML string (see §4); the fetcher must be touched (small, reviewable
  diff) to accept `data:`.

**B. Write bytes to a temp file, add the resolved path to `allowed_paths`**
[inference]
- Mirrors the existing font/site-logo pattern exactly (`_find_static` → `.resolve()` →
  `allowed_paths.add(path)` → `path.as_uri()`), so it is the *smallest conceptual diff* against
  the current fetcher design — no new scheme branch needed.
- Cons: requires a real temp file per render (e.g. `tempfile.NamedTemporaryFile`), which this
  module does not otherwise use, plus explicit cleanup (a `try/finally` or context manager around
  `weasyprint.HTML(...).write_pdf()`) — a leaked temp file on every report generation is a
  slow disk leak in a background-task worker that may run for the life of a long-lived process.
  Also reads S3 bytes to local disk unnecessarily when option A can hold them in memory only.
  Given `render_report_pdf()`'s current contract ("No ORM access... only renders"), this option
  also has to decide *where* the S3→local-file materialization happens — logically in
  `gather.py` (which already does the ORM/storage work) or as a new, narrow helper in `render.py`
  — either way it is more moving parts than option A for no clear benefit.

**C. Extending the fetcher to serve bytes directly for a sentinel URL**
[inference]
- E.g. `org-logo://current` as a fake scheme, resolved by the fetcher to bytes handed to it via
  closure, returned as a `URLFetcherResponse`. This is essentially option A without the `data:`
  URI in the HTML — the bytes travel via the fetcher's closure instead of via the src attribute.
- Pros: keeps the HTML string small (no base64 inflation — see §4), and keeps the "every
  resource this document may read is named before rendering starts" property the module's
  docstring calls out, arguably *more* faithfully than a `data:` URI (the sentinel is a name, the
  bytes are supplied by the trusted Python side, never round-tripped through the HTML string).
  Requires only one dict lookup, no MIME-sniffing beyond what FLS already knows (PNG/JPEG/WebP
  from the `Organisation.logo` field).
  Cons: introduces a made-up URI scheme, which is a mild "not standard HTML" smell (though CSS/
  HTML happily accept unknown schemes in `src`; WeasyPrint does not validate against a scheme
  allowlist itself — the custom fetcher is the only gate) and needs the exact same
  `URLFetcherResponse` construction as option A.

**D. Letting WeasyPrint fetch the signed S3 URL directly**
[inference — this is "probably unacceptable" per the brief, and this research agrees]
- Would require loosening the fetcher to allow `https://` to the S3 host, which is exactly the
  SSRF surface the module's docstring says the fetcher exists to close (the report renders
  author-supplied question/option text; an `https://` allowance keyed only by hostname is not
  keyed to "one specific expected file" the way the allowlist is for fonts/site logo — a signed
  URL is also **time-limited**, so a report generated once and re-downloaded later, or rendered
  by a slow background worker after the signature's TTL, could silently fail or (worse) succeed
  against a *different* object if the signature were ever reused/predictable). Also couples the
  render module to knowing about S3/signed-URL mechanics, which the module's own docstring
  explicitly avoids ("No ORM access happens anywhere in this module"). Not recommended.

---

## 2. WebP support

**[verified, from `weasyprint/images.py:34-85` and `uv.lock`]**

- WeasyPrint does not decode raster formats itself; it hands the fetched bytes to
  `PIL.Image.open(BytesIO(bytestring))` (`images.py:310`). Format support is therefore exactly
  Pillow's. Installed Pillow is `12.3.0` — PyPI's official Pillow wheels bundle `libwebp`, so
  WebP decode (including alpha) works out of the box; no extra system package needed beyond what
  the project's Pillow install already provides (FLS already depends on Pillow for the
  `organisations/validators.py` byte-level check, so this is not a new dependency).
- **Every raster format except JPEG/MPO is re-encoded to PNG before being embedded** — this is
  unconditional, not conditional on `optimize_images`: `RasterImage.__init__` branches only on
  `pillow_image.format in ('JPEG', 'MPO')`; everything else (`PNG`, `WEBP`, `GIF`, ...) falls into
  the `else` branch and is always re-saved as PNG via `pillow_image.save(image_file,
  format='PNG', optimize=optimize)` (`images.py:78-84`). **So there is no such thing as "does
  WeasyPrint 69 render WebP" in the sense of embedding a WebP stream in the PDF — a WebP logo is
  decoded by Pillow and always embedded as a PNG (FlateDecode) XObject.** A hand conversion to
  PNG before embedding therefore buys nothing WeasyPrint doesn't already do internally — it
  would only move the CPU cost earlier and duplicate logic FLS would then have to maintain.
- **Animated WebP**: `Image.open()` opens the first frame only; nothing in `images.py` calls
  `.seek()`/iterates frames. An animated WebP logo would render as its first frame, silently, with
  no error. FLS's `validate_organisation_logo` doesn't reject animated WebP (it only checks
  `img.format in {"PNG", "JPEG", "WEBP"}`, dimensions, and size) — **inference**: worth a product
  note, not a blocker, since a first-frame-only render of an animated logo is a cosmetic
  surprise, not a failure.
- **Lossless/alpha WebP**: handled correctly. `RasterImage.__init__` converts any image with a
  `'transparency'` info key to `RGBA`, and separately, images already in `RGBA`/`LA` mode (which
  is how Pillow decodes an alpha-channel WebP) get their alpha channel split out into a PDF
  `SMask` (soft mask) at draw time (`images.py:171-193`) — full alpha compositing is preserved in
  the PDF, not flattened onto a background colour.
- **Unsupported/corrupt format behaviour**: `get_image_from_uri` catches `(URLFetchingError,
  ImageLoadingError)`, logs via `LOGGER.error(...)`, sets `image = None`, and returns — **this is
  a silent omission, not an exception** (`images.py:329-335`). Nothing in `render_report_pdf()`
  currently listens to the WeasyPrint logger or inspects its output, so a broken organisation
  logo would render a report with a blank space where the logo should be and no
  `ReportRenderError`. Since FLS's own `validate_organisation_logo` already rejects anything that
  isn't a genuine PNG/JPEG/WebP *at upload time*, this failure mode should be unreachable in
  practice for the organisation logo specifically — but it's a real gap if the resolved bytes are
  ever missing/corrupted at render time (e.g. logo deleted from S3 after the DB row still
  references it, a signed-URL/storage read failure treated as "no bytes" instead of raising). If
  that risk matters, it must be handled at the FLS layer (gather.py raising before the fetcher is
  ever invoked), not relied upon from WeasyPrint's behaviour.
- **CMYK JPEG note (ties into §6)**: `images.py:62-66` special-cases Adobe CMYK JPEGs (APP14
  segment) with an inverted `Decode` array — a real historical WeasyPrint bug, fixed and cited in
  source as **[web]** [Kozea/WeasyPrint PR #2179](https://github.com/Kozea/WeasyPrint/pull/2179).
  Confirms CMYK JPEGs are handled correctly in the installed version; not relevant to WebP, but
  relevant if organisation logos are ever allowed as arbitrary JPEGs from external design tools.

---

## 3. Raster sizing for print, `object-fit`/`object-position`, and downscaling

**[verified, from `weasyprint/layout/replaced.py` and `weasyprint/css/properties.py`]**

- `object-fit` and `object-position` **are fully implemented**, not merely parsed-and-ignored:
  `css/properties.py:150-152` lists them with initial values `fill` / `(50%, 50%)`, and
  `layout/replaced.py:86-130` (`replacedbox_layout`) implements `fill`/`contain`/`cover`/`none`/
  `scale-down` plus `object-position` offsetting, exactly per the
  [CSS Images 3 spec](https://drafts.csswg.org/css-images-3/#sizing) the module's own docstring
  cites. **This directly answers the brief's open question**: `object-fit` is not a gap in
  WeasyPrint 69 — FLS can safely use `object-fit: contain` (or `scale-down`) plus fixed
  `max-height`/`max-width` to constrain an arbitrary-aspect organisation logo into a fixed box,
  the same pattern already used for the site logo's `.cover-logo` (`max-height: 12mm; max-width:
  55mm;` in `print.css:494-499`), which today relies on `<img>`'s intrinsic-size-plus-`max-*`
  behaviour rather than `object-fit` — both approaches work; `object-fit: contain` is more robust
  if the box is ever given a *fixed* (not just max-) height and width, since plain `max-*` on an
  `<img>` without an explicit box only constrains one axis at a time unless both are set.
- **DPI / downscaling**: `RasterImage.draw()` (`images.py:90-104`) computes the *actual* on-page
  print resolution from `concrete_width`/`concrete_height` (the laid-out CSS box size) and the
  current transform matrix, compares it against the `dpi` render option, and if the image is
  "too dense" for its printed size, downsamples via `Image.thumbnail()` before writing the
  XObject (`images.py:117-129`, `get_x_object`). **So WeasyPrint already downscales an
  oversized-for-its-box raster image at write time** — a 4000×4000px logo constrained by CSS to
  `max-height: 12mm` will not embed 4000×4000px of pixel data; it embeds only what the configured
  `dpi` option calls for. `render_report_pdf()` currently calls `weasyprint.HTML(...).write_pdf()`
  with **no `dpi`/`optimize_images`/`jpeg_quality` arguments**, so this only activates if FLS
  passes `dpi=<value>` to `write_pdf()` — **[web]** confirmed via WeasyPrint's own worked example,
  `HTML(...).write_pdf('out.pdf', optimize_images=True, jpeg_quality=60, dpi=150)` (from the
  hosted docs; direct section fetch failed for this worker, but the parameters and defaults were
  corroborated by a targeted doc search: `optimize_images` — "size... optimized with no quality
  loss"; `jpeg_quality` 0–95; `dpi` — "sets the maximum resolution of images embedded in the
  PDF." [WeasyPrint documentation](https://doc.courtbouillon.org/weasyprint/stable/)). Setting a
  print-appropriate `dpi` (e.g. 300, the module's fonts/tables are already tuned to A4 print) and
  `optimize_images=True` on the existing `write_pdf()` call is a one-line, low-risk win that
  bounds *both* the site logo and the new organisation logo's contribution to PDF size regardless
  of the uploaded pixel dimensions, and costs nothing extra to add alongside this feature (worth
  doing at the same time, since it's the same call site being touched).
- **Recommendation on manual downscaling**: given the above, a separate hand-rolled Pillow resize
  step before embedding is *not* necessary for correctness — WeasyPrint's `dpi` option already
  does this at the pixel level. It could still be worth doing at *upload* time (already partly
  true: the 4000px validator caps it) to keep the base64 payload small if option A (§1) is chosen,
  since the `dpi` downscaling happens *after* the full-resolution bytes are already base64-decoded
  and parsed into the HTML/DOM — see §4.

---

## 4. Base64 size blow-up and memory implications; does inlining defeat de-duplication?

**[verified, from `weasyprint/images.py:287-335` and `weasyprint/pdf/stream.py:216-230`]**

- Base64 encoding inflates bytes by exactly 4/3 (plus the `data:image/png;base64,` prefix, a few
  dozen bytes). At FLS's own 2 MiB validator ceiling, worst case is ≈2.7 MiB of extra text in the
  HTML string per **occurrence** of the `data:` URI in the template (e.g. once on the cover page,
  once per `content: element(...)` "Powered by" footer mark — noting §5's finding that the
  footer mark is a *single* running element reused across pages at the CSS/box level, not one
  `<img>` per page in the DOM, so realistically this is 1–2 occurrences in the HTML source, not
  N-per-page). This is a one-time, in-memory string concatenation and `lxml` parse in a
  background task (per `freedom_ls/reports/tasks.py`) — a few MB of extra string/DOM memory is
  not a meaningful concern for a task-queue worker generating one PDF at a time, but it is
  strictly worse than option C (§1), which never puts the bytes in the HTML string at all.
- **De-duplication is preserved regardless of which option is chosen**, and this is the more
  important finding: `get_image_from_uri` caches by the exact `url` string
  (`if url in cache: return cache[url]`, `images.py:290-291`) within one document render, *and*,
  independently and more importantly, the PDF writer's `Stream.add_image()`
  (`pdf/stream.py:216-230`) keys the embedded XObject by `image.id` — which is
  `md5(url.encode())` (`images.py:324`) — via a **document-wide** `self._images` dict that every
  page's `Stream` shares (each per-page `Stream` is produced by `Stream.clone()`, which passes
  `images=self._images` through unchanged unless overridden — `pdf/stream.py:37-54`). So: **the
  same `data:` URI (or the same `file://` path, or the same sentinel URI) used on the cover page
  and again in a footer running element embeds as exactly one PDF image XObject**, referenced by
  name (`/Do`) from every page's own content stream — WeasyPrint already does this "de-duplicate
  the repeated logo across every page" work for FLS, and it does so identically whether the URI
  is `file://`, `data:`, or a custom scheme, because the identity used for dedup is the URL
  *string*, not the fetch mechanism. **This resolves the brief's open question**: inlining as a
  `data:` URI does *not* defeat PDF-level image de-duplication, provided the exact same `data:`
  string (not a freshly-recomputed one) is used everywhere the logo appears in one render — which
  is naturally the case here, since both occurrences come from the same
  `CohortReportData`/context value.

---

## 5. Images inside `@page` margin boxes / running elements

**[verified from FLS's own `print.css`, corroborated by web sources]**

- FLS's `print.css` already proves the *mechanism* for text: `.footer-identity { position:
  running(footer-identity); }` (`print.css:110-116`), placed via `@bottom-left { content:
  element(footer-identity); }` in the `@page` rule (`print.css:56-58`), fed from a plain `<div>`
  in `report.html` (`report.html:38-40`). Nothing in WeasyPrint's `position: running()`/`content:
  element()` implementation restricts the *content* of the running element to text — it is a
  general "move this box's rendered content into every matching margin box" mechanism.
- **[web]** The feature itself (`position: running()` / `content: element()`) was added in
  [Kozea/WeasyPrint PR #882](https://github.com/Kozea/WeasyPrint/pull/882), and WeasyPrint's own
  documented pattern for a logo-in-header explicitly uses an `<img>` inside the running element,
  e.g.:
  ```css
  header { position: running(header); height: 4cm; }
  @page { @top-center { content: element(header); } }
  ```
  (pattern corroborated via web search of WeasyPrint print-CSS tutorials; not from the primary
  hosted docs directly — this worker's fetch of the "Common Use Cases" page did not return the
  running-elements section content, likely a fetch/rendering limitation of the fetch tool rather
  than the section not existing, so treat this specific example as **[web, secondary-source]**
  rather than primary-doc-verified). One placement caveat repeated across sources: the running
  element's source node must appear **before** any page-break in the document, or the
  corresponding margin box on earlier pages will read empty (nothing before the first sighting to
  run). FLS's `.footer-identity` div is already placed as literally the first thing in `<body>`,
  ahead of the cover section, for exactly this reason (see the comment at `report.html:30-37`),
  so this is already handled correctly for whatever gets added into it.
- **Known WeasyPrint limitation, specifically not about images**: **[web]**
  [Kozea/WeasyPrint#2013](https://github.com/Kozea/WeasyPrint/issues/2013) — margins are not
  applied correctly to a **`<table>`** placed inside a running element on pages after the first;
  the reporter explicitly states their setup "worked with images and text, but is not working
  with tables." This is a single user report, not a maintainer-confirmed fix/regression note, but
  it is consistent, specific evidence that `<img>` content in a running element is *not* the
  affected case — the bug is scoped to table layout inside running elements, which is irrelevant
  here (the "Powered by" mark needs an `<img>` plus text, not a table).
- **Recommendation for FLS**: adding `<img class="footer-logo" src="...">` alongside the existing
  `<span class="footer-org">` inside `.footer-identity` is consistent with both FLS's own proven
  pattern and the general WeasyPrint feature — no structural change to the running-element
  mechanism is needed, only sizing (a small `max-height` in `print.css`, mirroring `.cover-logo`)
  and getting the URL into `src` via whichever option from §1 is chosen.

---

## 6. Other known WeasyPrint issues relevant to logos

- **Transparency / alpha**: handled correctly for both palette-with-transparency and true RGBA/LA
  images via a PDF `SMask` — **[verified]**, see §2 above (`images.py:171-193`). No known gap for
  a transparent PNG/WebP logo.
- **CMYK JPEGs**: handled correctly for the common Adobe-tool case (APP14 inversion) —
  **[verified]**, §2 above, citing **[web]**
  [PR #2179](https://github.com/Kozea/WeasyPrint/pull/2179). Not relevant to WebP but relevant if
  the allowed-format list is ever widened to plain JPEG uploads from design tools that emit CMYK.
- **Colour profiles / ICC**: not investigated in source for this worker (out of budget); Pillow
  preserves an embedded ICC profile on decode but nothing in `images.py`'s embed path
  (`get_x_object`) writes an `/ICCBased` colour space or an ICC output intent for a *regular*
  image XObject — colour space is derived purely from Pillow's decoded `mode` (`RGB`/`RGBA`→
  `/DeviceRGB`, `L`/`LA`→`/DeviceGray`, `CMYK`→`/DeviceCMYK`, `images.py:131-139`). **Inference**:
  an embedded ICC profile on an uploaded logo is therefore not honoured for image XObjects — the
  logo will render in the assumed device colour space, not through its ICC transform. This is a
  pre-existing WeasyPrint characteristic, not something the organisation-logo feature introduces
  or can practically fix, and PNG/JPEG/WebP corporate logos rarely carry meaningfully different
  ICC data from sRGB in practice, so this is a low-priority note, not a blocker.
  (`weasyprint/pdf/__init__.py` does have output-intent / colour-profile machinery for whole-document
  PDF/A output, per the `output_intent`/`_color_profiles` parameters threaded through `Stream` —
  but that is a document-level PDF/A feature, unrelated to per-image ICC honouring, and FLS's
  reports aren't rendered as PDF/A per anything seen in `render.py`.)
- **SVG — revisiting the FLS validator ban**: **[verified from source, `weasyprint/svg/__init__.py`
  and `weasyprint/images.py:300-321`]** WeasyPrint does support SVG (`images.py` tries SVG first
  when the fetched MIME type is `image/svg+xml`, and falls back to trying SVG if Pillow fails to
  decode a raster and vice versa). Its SVG renderer is a **hand-built, minimal SVG implementation**
  (`weasyprint/svg/`), not a full browser engine — the tag-handler registry
  (`svg/__init__.py:24-31` onward) lists only drawing primitives (`a`, `circle`, `ellipse`,
  `image`, `line`, `path`, `polyline`, and presumably `polygon`/`rect`/`svg`/`g`/`text`/`use` etc.
  further down the file, not exhaustively read by this worker) — **no `script` or
  `foreignObject` handler is present** in the portion inspected, meaning those elements would
  simply be un-drawn (ignored) rather than executed, which *does* meaningfully blunt the classic
  SVG-XSS vector `validate_organisation_logo`'s docstring warns about (`<script>`,
  `on*` handlers, `<foreignObject>` HTML) — **for WeasyPrint's own renderer specifically**. That
  is not the whole story, though: nested `<image href="...">` inside an SVG *is* handled
  (`svg/images.py` exists, and `SVGImage.__init__` threads the same `url_fetcher` through to the
  `SVG(...)` object, `images.py:251-256`), so nested resource fetches inside an SVG still go
  through FLS's restrictive fetcher and can't be used for SSRF against arbitrary hosts — but a
  crafted SVG *is* still XML that could carry `on*` event handlers WeasyPrint's CSS layer might
  still apply as inline styles/attributes in some code path not audited here, and more
  importantly, **the security cost isn't only about WeasyPrint's own rendering**: the same
  uploaded file is stored and could plausibly be served/downloaded/previewed elsewhere in the
  product (e.g. an admin preview, a future public organisation-branding page) by a browser, which
  *would* execute `<script>`/handle `<foreignObject>` if served with an SVG/XML content type.
  **Recommendation: do not revisit the SVG ban for this feature.** The print-quality upside
  (vector logos need no `dpi`-driven downscaling, scale losslessly to any box) is real but small
  given §3 already shows WeasyPrint handles raster downscaling well; the security cost is
  borne by every other place the uploaded bytes might ever be read, not just this one
  WeasyPrint-mediated code path, and that's a much larger surface than this feature's remit.

---

## Recommendation

**Pick option A (§1): base64 `data:` URI, decoded from Django's storage API
(`organisation.logo.open()` / the field's associated storage), with a small, explicit addition to
`_restrictive_url_fetcher` allowing `parsed.scheme == "data"` and constructing a
`URLFetcherResponse` (or delegating to `weasyprint.urls.URLFetcher().fetch(url)`, which already
handles `data:` internally via stdlib's `DataHandler`).**

Why, in order of weight:

1. It requires the **smallest, most auditable change to the security-critical fetcher** — one new
   scheme branch, no new mutable temp-file lifecycle, no new made-up URI scheme to explain in a
   docstring. The existing "every file this document may read is named up front" invariant is
   preserved in spirit: a `data:` URI carries its own bytes, so allowing the scheme cannot be
   used to read an unexpected file or reach an unexpected host — it can only make the document
   bigger, and that's already bounded by the existing 2 MiB logo validator.
2. It works identically regardless of whether `Organisation.logo`'s storage backend is local disk
   (dev) or S3 (prod, per `config/settings_prod.py`), because the bytes are read through Django's
   storage abstraction *before* WeasyPrint ever sees a URL — WeasyPrint never learns the storage
   backend exists. Option D (feeding WeasyPrint the signed S3 URL) is explicitly rejected: it
   would require loosening the fetcher's `https://` allowance by hostname (reopening exactly the
   SSRF-shaped hole the module exists to close) and couples correctness to a time-limited
   signature's TTL surviving until render time.
3. Verified WeasyPrint internals (§4) confirm the two things that made this option look
   worse on paper — HTML bloat and lost de-duplication — are **not both real costs**:
   de-duplication happens at the PDF-XObject level keyed by URL string, independent of fetch
   mechanism, so the logo is still embedded exactly once no matter how many times its `data:` URI
   appears in the HTML source (cover + running footer mark). Only the *HTML string size* pays the
   4/3 base64 tax, and at FLS's 2 MiB validator ceiling that's a few MB of extra in-memory text in
   a background task — not worth the extra moving parts (temp files, sentinel scheme) that
   options B/C would trade for avoiding it.
4. `object-fit`/`object-position` are fully implemented (§3) and WeasyPrint already downscales an
   oversized raster to its printed DPI at embed time (§3) — the sizing/quality half of this
   feature needs no custom Pillow pre-processing, only CSS (`max-height`/`max-width` or
   `object-fit: contain`, mirroring the existing `.cover-logo` rule) and, as a low-cost bonus
   while `render_report_pdf()`'s `write_pdf()` call is already being touched, passing
   `dpi=<a print-appropriate value>` and `optimize_images=True`.
5. Running elements already carry non-text content correctly per FLS's own proven pattern and
   corroborating community reports that the one known running-element content bug is scoped to
   `<table>`, not `<img>` (§5) — so the "Powered by `<site logo>`" footer mark is a template/CSS
   change, not a WeasyPrint-mechanism risk.

**Concrete residual risks to carry into implementation**, none blocking:

- The fetcher's `data:` branch must validate/trust the MIME type it declares in the
  `URLFetcherResponse` — construct it explicitly from what FLS already knows about the logo
  (its Pillow-verified format from `validate_organisation_logo`), not by trusting an
  attacker-controllable string, even though nothing here is currently attacker-reachable.
- A missing/corrupt organisation logo at render time degrades silently (blank space, no
  exception) per WeasyPrint's own `get_image_from_uri` error handling (§2) — if a broken logo
  reference must be a loud failure rather than a silent gap (matching the module's stated
  philosophy for the static site logo: "A path that is set but cannot be resolved is a
  misconfiguration, and raises"), that check belongs in `gather.py`/`render.py` *before* handing
  the fetcher a `data:` URI, not left to WeasyPrint.
- Fix the pre-existing `default_url_fetcher` deprecation warning while this fetcher is being
  touched anyway (§1) — unrelated to the organisation logo but adjacent code, cheap to fix
  alongside.
- Animated WebP logos render as their first frame only, silently (§2) — acceptable, but worth a
  one-line product note if it ever surprises someone.

---

## Sources

- WeasyPrint 69.0 installed source (this repo's venv): `weasyprint/urls.py`, `weasyprint/images.py`,
  `weasyprint/layout/replaced.py`, `weasyprint/css/properties.py`, `weasyprint/pdf/stream.py`,
  `weasyprint/svg/__init__.py` — read directly, not web-sourced.
- [WeasyPrint API Reference (stable)](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- [Kozea/WeasyPrint PR #882 — `position: running()` / `content: element()`](https://github.com/Kozea/WeasyPrint/pull/882)
- [Kozea/WeasyPrint issue #2013 — margins not applied to running-element tables (images/text unaffected)](https://github.com/Kozea/WeasyPrint/issues/2013)
- [Kozea/WeasyPrint PR #2179 — Adobe CMYK JPEG decode-array fix](https://github.com/Kozea/WeasyPrint/pull/2179)
- [CSS Images Module 3 — object-fit/object-position sizing algorithms](https://drafts.csswg.org/css-images-3/#sizing)
- FLS source: `freedom_ls/reports/render.py`, `freedom_ls/reports/static/reports/print.css`,
  `freedom_ls/reports/templates/reports/report.html`,
  `freedom_ls/reports/templates/reports/partials/title_page.html`,
  `freedom_ls/organisations/models.py`, `freedom_ls/organisations/validators.py`,
  `freedom_ls/reports/report_data.py`, `uv.lock`.

status: ok
reason: All six research questions answered and grounded primarily in the installed WeasyPrint 69.0 source (read directly), with web citations for GitHub issues/PRs and doc claims not verifiable from source alone; no test render was executed (no Bash tool available to this worker).
