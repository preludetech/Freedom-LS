# Research: output format, quality and size budgets for content_engine `File` images

Scope: `content_engine.File` records where `file_type == IMAGE`. Covers the encoding decision only
(format, quality, max dimension, byte budget). Ingest mechanics, serve-time rendition strategy and
front-end markup are covered by sibling research files.

## Constraints this research is written against

- `content_save` must stay simple: no new background services, no new task queue, no new
  infrastructure for downstream projects (per the idea owner). Encoding has to happen synchronously,
  inline, in `save_file_to_db`, during the existing `content_save` management-command run.
- Pillow `>=11.0` is already a declared dependency (`pyproject.toml:37`). Anything beyond what a
  plain `pip install pillow` wheel gives you is a **new** dependency and must be justified.
- FLS is installed *into* other Django projects (`CLAUDE.md`). A dependency that needs a
  system-level package (`apt install libavif...`) imposes that requirement on every downstream
  project's deploy image/Dockerfile — a materially bigger cost than adding a pure-Python/wheel
  dependency.
- Today `get_file_type_from_extension()` in
  `freedom_ls/content_engine/management/commands/content_save.py:442` treats
  `.jpg .jpeg .png .gif .bmp .svg .webp` as images. `demo_content/` bears this out: every raster/vector
  image actually checked into the demo course content is an **SVG**
  (`demo_content/functionality_demo_content_widgets/2. media/images/diagram.svg`,
  `.../images/portrait.svg`, `.../images/landscape.svg`, `.../images/square.svg`,
  `demo_content/functionality_demo_end_with_quiz/images/graph1.drawio.svg`,
  `demo_content/functionality_demo_end_with_topic/images/graph1.drawio.svg`). The "5 MB content
  image" problem this idea is solving is about **raster** photos/screenshots authors drop into
  topics, not about the SVG diagrams already in the demo course — SVG is explicitly out of scope for
  re-encoding (see "when lossless or the original wins" below).

---

## 1. Format choice in 2026

### Measured compression at matched visual quality (not vendor marketing)

The most-cited independent, methodologically transparent comparison remains Ctrl.blog's DSSIM-matched
study (600 photos, 6 sizes each, binary-searched per-image quality to hit a fixed DSSIM target of
0.0025 per format, published 2020-07-12, still the reference study everyone else's 2025/2026 "roundup"
articles restate without new methodology):

- WebP: **31.5% median** smaller than JPEG at matched DSSIM; 85th-percentile reduction only 20%; 2.7%
  of images were actually *larger* than the JPEG.
- AVIF: **50.3% median** smaller than JPEG at matched DSSIM; 85th-percentile reduction 39.6%; no
  image was larger than its JPEG.
- "AVIF's 85th percentile was the same as WebP's 15th percentile" — AVIF beat WebP on essentially
  every image in the set.
  Source: https://www.ctrl.blog/entry/webp-avif-comparison.html (2020-07-12)

Google's own web.dev AVIF guidance (CDN-observed, not lab-controlled, so read as directional rather
than a matched-quality number) reports AVIF files running ~60% smaller than JPEG and ~35% smaller
than WebP in production CDN traffic — consistent in direction with the Ctrl.blog numbers even though
the methodology differs.

**Conclusion on bytes:** AVIF is the best available format by a wide margin (~40-50% smaller than
JPEG, ~20-35% smaller than WebP). WebP is a solid, much smaller win over JPEG (~30%) with far lower
encode cost. This is a real trade-off, not a free upgrade — see §2 and §3.

### Browser support

- AVIF: ~94.7% of global browser usage per StatCounter data as tracked by caniuse, snapshot dated
  July 2026. Full support in current Chrome, Firefox, Safari (from Safari 16 / iOS 16), Edge. Gaps
  are old iOS (≤15) and old Safari/macOS (≤Monterey).
  Source: https://caniuse.com/avif (accessed for July 2026 snapshot)
- WebP: has been supported in every evergreen browser (including Safari) since 2020 and is
  effectively universal at this point — nobody serious tracks it as a risk any more.
- JPEG XL: **not viable as an encode target in 2026.** Chrome 145 (Feb 2026) ships a decoder but
  disabled behind `chrome://flags/#enable-jxl-image-format`; Firefox 152 (June 2026) ships one
  disabled behind a preference; only Safari decodes it out of the box, and incompletely (no
  animation, no progressive decode). Practical without-user-action support is estimated around 14%
  of visitors.
  Source: https://www.corewebvitals.io/pagespeed/jpeg-xl-core-web-vitals-support (2026);
  https://www.devclass.com/development/2025/11/24/googles-chromium-team-decides-it-will-add-jpeg-xl-support-reverses-obsolete-declaration/

### Encode cost

AVIF's compression advantage is bought with real CPU time, not a free win:

- Cloudinary's codec comparison (methodologically careful about not skewing on unusably-low
  qualities) measured, at a normal web quality (~q75) on a large test image: MozJPEG 0.9s, AVIF
  (aom, speed 6) 4.2s — **~4.7x slower to encode than JPEG** for a meaningfully better result.
  Multi-threading AVIF at speed 7 gets ~3x faster but costs ~3% more bytes.
  Source: https://cloudinary.com/blog/contemplating-codec-comparisons (2022-12-14, methodology
  still the clearest public write-up of this trade-off)
- Independent reports of libaom (the reference AVIF encoder Pillow links against) put full-effort
  AVIF encode at roughly 10-50x a WebP encode for the same source image, with peak memory in the
  gigabytes for a 4000px source versus ~200MB for WebP.
  Source: https://github.com/joedrago/avif/issues/11; corroborating third-party benchmarks
  aggregated in the same search (figures vary by encoder speed setting, but all agree AVIF is an
  order of magnitude slower than WebP at comparable effort).
- SVT-AV1 is roughly 2x faster than libaom at a comparable quality/size operating point, and rav1e is
  roughly 5x *slower* than SVT-AV1 — i.e. even among AVIF encoders the choice of backend matters by a
  factor of 10.
  Source: https://github.com/strukturag/libheif/wiki/AVIF-Encoder-Benchmark

### Is AVIF ready to be the only format shipped?

**No — recommend WebP as the single format `content_save` writes, not AVIF, and not a two-format
picture-element fan-out.** Reasoning:

1. **The dependency isn't free, and it's the kind of dependency this idea is meant to avoid.** Pillow
   gained *core* AVIF read/write in 11.2.0, but that release was pulled from PyPI for exceeding
   PyPI's package-size limit specifically because of the bundled `libavif`; 11.2.1 shipped **without
   libavif in the wheel**. So `pillow>=11.0` — the exact pin FLS already has — does **not** give you
   AVIF write support out of the box. Getting it back requires either building Pillow from source
   against a system-installed `libavif` (a system-level dependency downstream projects would have to
   add to every deploy image — explicitly the cost the idea owner flagged), or adding the third-party
   `pillow-avif-plugin` package as an extra Python dependency (better — it's a wheel, not a system
   package — but it is still a *new* dependency, maintained outside Pillow core, for one format).
   Source: https://pillow.readthedocs.io/en/stable/releasenotes/11.2.1.html ("The release of Pillow
   11.2.0 was halted prematurely, due to hitting PyPI's project size limit and concern over the size
   of Pillow wheels containing libavif. ... Pillow 11.2.1 has been released instead, without libavif
   included in the wheels.")
2. **The encode cost lands exactly where the constraint bites.** `content_save` runs synchronously,
   inline, no background task — encoding a few hundred images at 4-40x the WebP encode time each,
   during a `content_save` invocation that's already scanning a whole content tree, is a real
   wall-clock cost with no async escape hatch under the "stay simple, no new infra" rule.
3. **WebP already gets ~two-thirds of the win for near-zero marginal cost.** `libwebp` ships bundled
   and statically linked in Pillow's own PyPI wheels today — no extra dependency, no system package,
   works the moment `pillow>=11.0` is installed. ~30% smaller than JPEG at matched quality, at JPEG-ish
   encode speed, with support that's been universal for years.

**Recommendation: WebP now, single format, no `<picture>` fan-out needed.** Revisit AVIF later if
either (a) Pillow's upstream wheels start bundling `libavif` again (tracked in the same release-notes
thread) or (b) the project is willing to take `pillow-avif-plugin` as an explicit, documented optional
dependency for downstream projects that want the extra ~20-35% over WebP badly enough to accept the
encode-time cost. Do not chase JPEG XL — it is not decodable by default in any browser but Safari in
2026, and Safari's implementation is incomplete.

---

## 2. Pillow's encoders, specifically

### WebP

Pillow's `WebPImagePlugin` needs `libwebp >= 0.5.0`, which is **statically bundled in the official
PyPI wheels** — no extra install step, no system package, works today with `pillow>=11.0`. Supports
lossy, lossless, alpha, and animated WebP.
Source: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html

Save-time parameters (`Image.save(path, "WEBP", **kwargs)`):

- `quality` (int, 0-100, default 80) — for lossy encoding, the usual perceptual-quality dial.
- `lossless` (bool, default False) — switches to lossless VP8L; `quality` then controls encode
  *effort*, not visual fidelity.
- `alpha_quality` (int, 0-100, default 100, lossy mode only) — separate quality dial for the alpha
  channel, independent of the RGB quality.
- `method` (int, 0-6, default 4) — encode effort/speed trade-off; 6 is slowest/smallest, 0 is
  fastest/largest. Since `content_save` encodes once at ingest time and the result is read many times
  by learners, effort should be biased toward smaller output, not fast encode — recommend `method=6`.
  Source: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp

**Quality-parameter semantics differ from JPEG — do not reuse one number across formats.** Both
accept an integer 0-100, but they aren't the same perceptual scale: JPEG's `quality` drives DCT
quantization-table selection tuned for photographic block artifacts (Pillow's own guidance treats
anything above ~95 as "not recommended," diminishing returns and large size growth); WebP's
`quality` drives a different (VP8) block-transform and in-loop filtering pipeline that is
measurably more efficient at the same nominal number (this is exactly the Ctrl.blog ~30% gap in §1 —
"WebP quality 80" is not visually equivalent to "JPEG quality 80", it's better per byte). Treat the
two as separate tuning surfaces; a migration from JPEG-quality-N to WebP-quality-N is not a like-for-
like swap and needs its own visual check, not an assumption of parity.

### AVIF

Established in §1: Pillow gained core `AvifImagePlugin` support in **11.2.0/11.2.1** (2025-04), but
the **standard PyPI wheel ships without `libavif`** because bundling it blew PyPI's package-size
limit. Practically, `import PIL; Image.new(...).save(..., "AVIF")` will raise (format unsupported)
on a plain `pip install pillow` unless the environment separately provides a working `libavif`, or
the `pillow-avif-plugin` package is installed alongside (it vendors/depends on `libavif` itself, via
its own wheel). Recommendation stands: don't take this on now.

### Encode speed per megapixel

No single authoritative "Pillow ops/megapixel" benchmark exists, but the encoder-level numbers in
§1 translate directly since Pillow's WebP/JPEG paths are thin wrappers over `libwebp`/`libjpeg`:
JPEG and WebP are both sub-second per image at typical content-image resolutions (well under
4 megapixels), AVIF is the outlier at multiple seconds per image and gigabytes of peak RAM at full
resolution/effort. For `content_save` encoding "a few hundred images" synchronously, WebP keeps the
whole run in the tens-of-seconds range; AVIF at comparable effort could plausibly add minutes.

---

## 3. Choosing a quality number

The field has settled on **WebP quality ≈ 75-82** for general photographic web content — high enough
that compression artifacts are not visible at normal viewing distance/zoom, low enough to capture
most of the available savings (the marginal byte cost of quality 90+ grows much faster than the
marginal quality gain — this is the same "elbow" behaviour JPEG's quality curve has always had, and
WebP inherits it). **Recommend `quality=80, method=6`** as the default for content_engine photographic
images — it matches Pillow's own WebP default quality, sits in the middle of the field-standard band,
and `method=6` spends the (one-off, ingest-time) extra encode effort to get the smallest file at that
quality.

**Screenshots, diagrams and text-heavy images need different treatment, and this matters a lot in
e-learning content specifically** — course topics are full of annotated screenshots, flowcharts and
slides with text baked in. These images are graphically flat: large areas of a single flat colour,
sharp high-contrast edges (text glyph edges, UI chrome borders). Block-transform lossy codecs
(JPEG's DCT, WebP's lossy VP8 path, AVIF's AV1 path) are all tuned for photographic gradients, and
on flat-colour/sharp-edge content they produce visible ringing/mosquito-noise haloes around edges and
smearing of small text — this is the well-known reason "don't JPEG your screenshots" has been standard
web advice for two decades, and it applies just as much to lossy WebP/AVIF as it did to JPEG (the
artifact shape differs by codec but the underlying failure mode — blur/ringing near hard edges — is
the same because all three use block-based lossy transforms). For this content class, lossless
encoding is very often *smaller*, not just cleaner, because flat colour compresses extremely well
under lossless coding and there's no need to spend bits preserving noise that isn't there.

**A single quality number cannot serve both classes well.** Recommend the encoder classify per image
rather than apply one fixed number:

- Cheap, dependency-free heuristic available directly from Pillow: count distinct colours via
  `Image.getcolors(maxcolors=N)` (returns `None` if the image has more than `N` colours). An image
  with few distinct colours relative to its pixel count (a common threshold used by similar
  "smart compression" tools is a few hundred colours, or equivalently a low colour-to-pixel ratio) is
  almost certainly a screenshot/diagram/rendered-text image, not a photo.
  - Few colours → treat as graphic: lossless WebP (`lossless=True`) if smaller than the original,
    else keep the original (PNG) — see §4.
  - Many colours (photographic) → lossy WebP `quality=80, method=6`.

This mirrors the "content type" distinction FLS already reasons about elsewhere (topics vs activities,
image vs document) — it's a per-`File` classification made once at `content_save` time, not a runtime
decision.

---

## 4. When lossless or the original wins

Two independent reasons to *not* force a lossy re-encode, and both are cheap to implement as
guardrails around whatever encoder logic §3 lands on:

1. **Format-level: SVG and (per §3) flat-colour PNGs are frequently smaller and always higher
   fidelity than any lossy re-encode.** `content_save`'s own `get_file_type_from_extension()` already
   treats `.svg` as an image extension. SVG is vector — there is no raster re-encode to perform, and
   attempting to rasterize-then-recompress an SVG would be strictly worse (bigger file, lower
   fidelity, loses scalability) for no benefit. **Rule: `.svg` files bypass the raster encoder
   entirely, unchanged, full stop.** This is not a hypothetical edge case for FLS — per the repo scan
   above, every content image actually present in `demo_content/` today is an SVG.
2. **Byte-level, universal safety net regardless of format decision: never ship a re-encode that is
   bigger than what it replaced.** Encode the candidate rendition, compare byte size to the source
   file, and if the rendition is not strictly smaller, keep the original file as-is. This covers the
   "2.7% of images WebP made bigger than JPEG" case from the Ctrl.blog numbers (§1) and any small
   image where compression overhead exceeds the source size, cheaply, without needing a size or
   dimension threshold to detect them in advance.

---

## 5. Byte budgets

### What the web looks like today (HTTP Archive Web Almanac, 2025 edition, image-bytes chapter)

- Individual image response sizes across the whole web: **P50 8 KB, P75 48-52 KB, P90 183-186 KB**
  (desktop vs mobile nearly identical). Note this P50 is pulled down hard by icons, tracking pixels
  and UI chrome — it is not representative of a deliberately-authored content image.
- Aggregate image bytes per page: **P50 ~1,058 KB desktop / ~911 KB mobile** on home pages, roughly
  half that (**~442 KB / ~354 KB**) on inner/content pages, which is the closer analogue to an FLS
  course topic page.
- Median page loads **13 images on inner pages** (19 on home pages).
  Source: https://almanac.httparchive.org/en/2025/page-weight

### Core Web Vitals framing

Largest Contentful Paint's "good" threshold is **≤2.5s at the 75th percentile of page loads**, and
LCP is only marked complete once the largest above-the-fold element (frequently an image) has fully
downloaded and rendered — so an oversized inline image can single-handedly push a topic page's LCP
over the good/needs-improvement line.
Source: https://web.dev/articles/lcp

### Translating this into a per-image target for FLS content images

A course topic-page inline image is deliberately authored content, not decorative chrome, so it
should sit above the whole-web P50 (which is icon-skewed) but well below the P90 tail. Recommend:

- **Target: ~80-150 KB per inline content image** after re-encode. This sits comfortably inside the
  P75 (48-52 KB) to P90 (183-186 KB) band of real-world individual image sizes — big enough that an
  800-1200px-wide diagram or annotated screenshot at WebP quality 80 comfortably fits, small enough
  that several per page stay well under the inner-page median page-image-weight of ~350-450 KB.
- **Hard ceiling: 250 KB per image.** Anything the encoder produces above this after the quality-80
  pass should be a signal to downscale dimensions further, not to drop quality further (dropping
  quality on an already-large image degrades visible fidelity faster than it saves bytes near the
  bottom of the WebP quality curve).
- **Max dimension: cap the longest edge at 1600px** on save. FLS's course-player content column is a
  standard prose-width reading layout (well under 1200px CSS width in practice); 1600px covers a
  ~800px CSS display width at 2x pixel density, which is the highest realistic requirement for an
  inline content image (this is not a full-bleed hero banner). Images already smaller than 1600px on
  their longest edge are left at their native size — never upscale.
- **Per-page budget: keep total inline-content-image weight on a single topic page under ~750 KB-1
  MB.** A topic page with 3-6 images at the 80-150 KB target lands well inside this, leaving budget
  for the rest of the page (CSS, HTMX, fonts) against the ~1.5-2.9 MB whole-page medians HTTP Archive
  reports, without requiring `content_save` or the render path to enforce a page-level cap directly —
  the per-image target is what should be enforced; the per-page number is the sanity check that
  justifies it.

---

## 6. Storage cost

Rough arithmetic for "a course with a few hundred images," per the prompt:

- **Originals as authored today:** 300 images × ~5 MB (the problem statement's own figure) ≈ **1.5
  GB**. At S3 Standard's per-GB-month rate of $0.023 (first 50 TB/month tier;
  https://www.nops.io/blog/aws-s3-pricing/, 2026), that's **~$0.035/month** — essentially free at this
  scale, and stays essentially free even at 10x this volume (a few thousand images).
- **Re-encoded renditions at the recommended target:** 300 images × ~120 KB (mid-point of the 80-150
  KB target) ≈ **36 MB**, an additional **~$0.0008/month**.
- **Conclusion: storage dollar-cost is not what should drive the "keep the original or not" decision
  here** — at these volumes it's noise either way. The decision should instead be driven by whether
  the original is *needed* for anything: since `content_save` always regenerates `File` rows from the
  authored source tree passed on its command line (`save_file_to_db` reads straight from
  `file_path` under `base_path`, not from whatever is currently in the bucket — see
  `freedom_ls/content_engine/management/commands/content_save.py:459-497`), the multi-megabyte
  original does **not** need to be retained in the storage bucket to remain "recoverable" — the
  source-of-truth original already lives in the content repository/directory that gets fed into
  `content_save`, and can be re-encoded again on a future `content_save` run if the target
  quality/dimensions change. **Recommend: the bucket stores only the encoded rendition that
  `File.file` points to (today's model shape — one `FileField` per `File` row); it does not need a
  second "keep the 5 MB original too" field or a second storage location.** This keeps
  `content_save` simple per the hard constraint, avoids doubling storage/egress for no serving
  benefit, and is a genuinely free decision at these dollar amounts either way — the argument for
  not keeping the original is architectural simplicity, not cost.

---

## Headline recommendations (for the spec)

- **Format:** WebP only, written via Pillow's already-bundled `libwebp` — no new dependency, no
  system package. Do not add AVIF now (Pillow's PyPI wheels dropped bundled `libavif` in 11.2.1 over
  a PyPI size limit; getting AVIF back means a new pure-Python dependency at minimum, a new
  system-level one at worst, plus a 5-50x encode-time cost inside the synchronous `content_save`
  run). Do not consider JPEG XL (effectively 0% no-flag browser support outside Safari in 2026).
- **Quality:** classify per image via Pillow's `getcolors()` colour-count heuristic. Photographic
  (many colours) → lossy WebP `quality=80, method=6`. Graphic/screenshot/diagram (few colours) →
  lossless WebP, or keep the original PNG if lossless WebP isn't smaller.
- **Guardrails:** `.svg` bypasses the encoder entirely (already the largest image class in FLS's own
  demo content); any re-encode that comes out larger than its source is discarded in favour of the
  source, unconditionally.
- **Numbers:** max longest-edge dimension 1600px; target 80-150 KB per image, hard ceiling 250 KB;
  keep total inline-image weight on a topic page under ~750 KB-1 MB.
- **Storage:** keep only the encoded rendition in the bucket, not a second copy of the multi-MB
  original — `content_save` can always re-derive it from the authored source tree, and the dollar
  cost of either choice is negligible at FLS's scale.

status: ok
