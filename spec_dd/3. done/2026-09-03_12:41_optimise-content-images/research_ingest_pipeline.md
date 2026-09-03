# Research: ingest-time image optimisation with Pillow inside `content_save`

Scope: `content_engine.File` images only, processed synchronously in-process inside
`save_file_to_db()` (`freedom_ls/content_engine/management/commands/content_save.py`), using the
already-vendored `pillow>=11.0`. No new services, no queue.

## Existing local precedent — read this first

`freedom_ls/organisations/validators.py` (`check_logo_safety`) already decodes untrusted image bytes
with Pillow in this codebase, for organisation logo uploads. It is the closest prior art and the
ingest pipeline should reuse its hard-won exception list rather than rediscovering it:

```python
except (Image.DecompressionBombWarning, Image.DecompressionBombError) as err: ...
except (OSError, Image.UnidentifiedImageError, SyntaxError, ValueError) as err: ...
```

Its docstring explains *why* each exception type is there: a PNG with a bad chunk checksum raises
`SyntaxError`, one with a truncated `IHDR` raises `ValueError`, and only a genuinely unrecognisable or
truncated body raises `OSError`/`UnidentifiedImageError`. Catching `OSError` alone lets the first two
escape uncaught. `freedom_ls/tests/images.py` (`break_png_chunk_crc`, `shorten_png_ihdr`) already
builds fixtures for exactly these two cases and is reusable for testing the ingest pipeline too — no
need to invent new corrupt-image fixtures.

The logo validator differs from this feature in intent (reject-on-upload vs. optimise-in-pipeline) and
in one explicit decision — it does **not** strip EXIF, reasoning that a corporate logo carries no GPS
data and re-encoding a transparent WebP risks visible regression. That reasoning does not transfer:
author photos from cameras/phones routinely carry GPS EXIF, and this feature *is* about re-encoding.
So the ingest pipeline should strip EXIF (see below) — a deliberate divergence from the logo
validator's choice, not an oversight.

## Current behaviour of `save_file_to_db()`

Reads bytes from `open(file_path, "rb")`, deletes the old `file_obj.file` if present, then
`file_obj.file.save(file_path.name, DjangoFile(f), save=True)` — a raw byte copy, no processing.
`get_file_type_from_extension()` classifies `.jpg/.jpeg/.png/.gif/.bmp/.svg/.webp` as `File.FileType.IMAGE`
uniformly; SVG and GIF are lumped in with raster formats that Pillow can re-encode, so any change here
must branch inside the `IMAGE` case by *actual decoded format*, not by the extension bucket.
`demo_content/` confirms SVG is not a hypothetical edge case: every image currently checked into
demo content is `.svg` (`diagram.svg`, `portrait.svg`, `landscape.svg`, `square.svg`,
`graph1.drawio.svg` x2) — zero raster images in the shipped fixture set. The pipeline must be a no-op
on the common case in this repo's own demo content, or every demo-content regeneration silently
"succeeds" while doing nothing, which is a bad signal to design against.

## Recommendation summary (read this, then the detail below)

1. Open with `PIL.Image.open`, call `ImageOps.exif_transpose()` first, then downscale with
   `Image.thumbnail((MAX_DIM, MAX_DIM), Image.Resampling.LANCZOS)` (never upscale — `thumbnail` already
   guarantees that), then re-encode: JPEG stays JPEG at quality ~82 with `optimize=True,
   progressive=True`; PNG stays PNG with `optimize=True` unless it is fully opaque, in which case
   converting to JPEG is a large win — do this only if explicitly wanted, since it changes the file
   extension/mime type learners' browsers see.
2. Route by Pillow's **decoded** `img.format`, not by file extension: SVG, animated GIF (`n_frames >
   1`), and anything `Image.open` cannot decode all bypass the optimiser and are copied through
   verbatim, exactly as today.
3. Failure mode for a genuinely malformed raster image: log a warning and fall back to saving the
   original bytes unmodified — never hard-fail the whole `content_save` run over one bad image, and
   never silently drop the file. Reuse the exception tuple from `check_logo_safety`.

## 1. Resizing

- **Max dimension cap.** No universal number; it must match how the course player actually renders
  images. A `max(width, height)` cap in the 1600–2000 px range is the common recommendation for
  content shown at reading width on desktop, with room for retina density — e.g. Cloudinary and
  Thumbor guidance both land in this band for "web content, not full-bleed hero" images
  ([Cloudinary image optimization guide](https://cloudinary.com/guides/image-effects/image-optimization),
  general web-perf guidance from
  [web.dev/articles/serve-images-with-correct-dimensions](https://web.dev/articles/serve-images-with-correct-dimensions)).
  Pick the number from the player's actual CSS max-width plus a 2x retina multiplier, not a general
  web guideline; that number lives in `learner_interface`/`c-picture`, not in this research. Treat it
  as a single named constant in `content_engine.config` (`ContentEngineConfig`, following the existing
  `AppSettings`/`Setting` pattern already used for `CONTENT_MEDIA_STORAGE_ALIAS`), not a magic number
  in `content_save.py`, so it is one place to tune. Avoid calling this a "variant" anywhere in code or
  docs — that word is taken in this codebase for UI component styling (Cotton components); call it
  something like `max_dimension` / `MAX_IMAGE_DIMENSION_PX`.
- **`thumbnail()` vs `resize()`.**
  [`Image.thumbnail()`](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.thumbnail)
  is the right primitive: it mutates in place, preserves aspect ratio automatically by fitting inside a
  `(w, h)` box, and — critically — **never enlarges an image that is already smaller than the box**.
  That gives "never upscale" for free without a manual `if img.width > cap` guard. `resize()` is lower
  level: it produces an exact target size, will happily upscale, and requires the caller to compute the
  aspect-preserving target dimensions itself. Use `thumbnail()`.
- **Resampling filter.** `Image.Resampling.LANCZOS` (a.k.a. `ANTIALIAS` pre-Pillow-9) is the best
  quality/cost trade-off for downscaling photographic content — sharper than `BICUBIC` at a roughly
  20–40% slower per-image cost, but downscaling a handful-of-megapixel JPEG is still low tens of
  milliseconds either way, so the quality win is free in the context of a CLI batch job. `BICUBIC` is
  the pragmatic fallback only if wall-clock on very large batches becomes a real constraint (it isn't,
  per the speed section below). Do not use `NEAREST` or `BILINEAR` for downscaling photographic
  content — visible ringing/aliasing on any content with text or line art (screenshots, diagrams),
  which is a real category here given course content includes screenshots.
- **Never upscale.** Confirmed as `thumbnail()`'s built-in behaviour; no extra code needed as long as
  `resize()` is not used directly.

## 2. Re-encoding

- **JPEG quality.** Pillow's `quality` save parameter defaults to 75
  ([Pillow JPEG plugin docs](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg)).
  The commonly cited sweet spot for photographic web content is **80–85**: below ~75 JPEG block
  artefacts become visible on screenshots/diagrams with sharp edges (a real category of author content
  here, not just photos); above ~90 file size grows steeply for a barely-visible quality gain (this is
  the well-known JPEG quality/size curve — see
  [Google's WebP/JPEG comparison study](https://developers.google.com/speed/webp/docs/webp_study) for
  the shape of the curve, and Pillow's own docs note "values above 95 should be avoided; 100 disables
  portions of the JPEG compression algorithm and results in large files"). Recommend **quality=82** as
  a single fixed constant — good default for the mixed photo/screenshot content this repo actually has.
  Do not expose per-author quality control; that's scope creep for a "keep it simple" ingest command.
- **`optimize=True`.** Makes libjpeg do an extra pass to pick optimal Huffman tables — typically 2–8%
  smaller output for negligible extra encode time on images this size. Always set it; no reason not
  to for a batch command that already accepts multi-second runtimes.
- **`progressive=True`.** Produces a JPEG that renders as a low-res preview refining to full detail,
  rather than top-to-bottom — better perceived load performance for the course player, no quality
  cost, small (sometimes negative on tiny images) size cost. Reasonable default; safe for course
  content sizes.
- **PNG `optimize`.** PNG is lossless; `optimize=True` on save asks Pillow's zlib backend to try
  harder for a smaller lossless encode (same pixels, smaller bytes) — always worth setting, it costs
  encode time only.
- **When PNG should become JPEG.** Only when the PNG has no alpha channel (`img.mode in ("RGB", "L")`,
  or `"P"` without a transparency entry) — i.e., it is being used as a lossless container for what is
  really a photo. A screenshot PNG with no transparency, converted to JPEG at quality 82, is
  routinely 5-10x smaller with imperceptible loss. This is the single biggest win available in this
  research, larger than resizing for many "5MB screenshot" cases described in the idea doc.
- **When it must not.** Any PNG with an alpha channel (`RGBA`, `LA`, or `P` with a transparency
  index) must stay PNG (or become WebP, if adding a new served format is in scope) — JPEG has no
  alpha channel, so converting drops transparency and silently breaks any image relying on it (logos
  overlaid on content, diagrams with transparent backgrounds). Detect via
  `img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)`.
- **WebP.** Out of scope to recommend as a hard requirement here (adds a served-format decision the
  player/templates need to support, e.g. `<picture>` fallback), but worth flagging: WebP lossy at
  similar quality is typically 25-35% smaller than JPEG for photographic content, and WebP lossless
  beats PNG too. If the spec wants it, it's the same `img.save(..., format="WEBP", quality=82,
  method=6)` shape as JPEG — `method=6` trades slower encode for better compression, still not a
  problem for batch ingest. Leaving as a "nice to have, not core to this ticket" per the "keep
  `content_save` simple" constraint — every extra output format is another thing the player templates
  must know how to serve.

## 3. Correctness traps

- **EXIF orientation.** Cameras and phones store rotation as an EXIF `Orientation` tag rather than
  physically rotating pixels; a naive `Image.open().thumbnail()` ignores that tag, so an image that
  displays upright in every EXIF-aware viewer comes out sideways or upside-down after resize+save
  because Pillow's raw pixel buffer was never rotated. Fix: call
  `ImageOps.exif_transpose(img)` (returns a new, correctly-oriented image with the EXIF orientation
  tag cleared/normalised) **before** `thumbnail()`. This must run first — resizing after transpose
  resizes the corrected image; resizing before would resize the wrong-orientation buffer, and cropping
  math would be off for non-square outputs too. Docs:
  [`PIL.ImageOps.exif_transpose`](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose).
- **ICC colour profile.** Dropping `icc_profile` on re-save is usually fine for sRGB-tagged web
  content (the vast majority of author photos) — browsers assume sRGB when no profile is present, so
  no visible shift. It is *not* fine for wide-gamut (Display P3, Adobe RGB) source photos: dropping the
  profile there means the browser reinterprets the same numeric pixel values as sRGB, producing a
  visible desaturation/colour shift. Since this pipeline cannot know in advance which authors export
  wide-gamut, the safe default is to **preserve** the ICC profile if present: read
  `img.info.get("icc_profile")` before transpose/resize and pass it back via `icc_profile=...` on
  save. Costs a few KB per file, not worth the risk of silently shifting colours on some fraction of
  author photos.
- **Stripping EXIF vs keeping it.** EXIF on unedited camera/phone photos routinely includes GPS
  coordinates of where the photo was taken — a real privacy concern for course content authored by
  staff/learners and then served publicly to a whole cohort. Recommend: **strip EXIF**, i.e. do not
  pass `exif=...` on save (Pillow only writes EXIF if explicitly given the bytes; a fresh `img.save()`
  without `exif=` already drops it). `ImageOps.exif_transpose()` already consumes the orientation tag
  before this, so nothing is lost by discarding the rest of the block — the pixels are already
  correctly oriented. This is the one point of deliberate divergence from
  `organisations/validators.py`'s "don't strip EXIF" decision, and the divergence is intentional
  (see "Existing local precedent" above) — different feature, different threat model.
- **Alpha channel / palette (`P` mode) images.** `P`-mode (indexed/palette) PNGs are common for
  simple diagrams/icons exported from design tools. Before resizing, convert with
  `img.convert("RGBA")` if the palette has a transparency entry, else `img.convert("RGB")` — resizing
  a palette image with `LANCZOS` directly produces incorrect blended colours because Pillow's resampling
  math operates on raw palette *indices*, not the colours they represent, unless converted to a true
  colour mode first. This is a well-known Pillow footgun (search "Pillow resize palette image wrong
  colors" surfaces many corroborating reports; documented behaviour, not a bug —
  [Pillow modes docs](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#modes)).
- **CMYK JPEGs.** Rare but real — some design-tool exports (Photoshop "Save for Web" set to CMYK,
  print-oriented workflows) produce CMYK JPEGs. Pillow decodes these as mode `"CMYK"`; saving a CMYK
  image back out as JPEG with Pillow's default encoder frequently produces wrong colours because
  Adobe's CMYK JPEGs use inverted/APP14-tagged CMYK that libjpeg doesn't auto-correct. Safe handling:
  detect `img.mode == "CMYK"` and convert with `img.convert("RGB")` before any further processing —
  Pillow's `CMYK -> RGB` conversion is a reasonable approximation and far safer than re-saving CMYK
  as-is.

## 4. Formats that must not be re-encoded

- **SVG.** Pillow cannot open SVG at all (it is XML, not a raster format Pillow's plugins understand;
  `Image.open()` on an SVG raises `UnidentifiedImageError`). This is not an edge case to defend
  against defensively so much as the expected, common path in this repo — every image currently in
  `demo_content/` is SVG. Route by extension *before* attempting `Image.open` for this one case (SVG
  is the one format where extension-sniffing before decode is legitimate, since Pillow has no SVG
  codec to fall back to) and pass the bytes through unchanged, exactly as `save_file_to_db()` does
  today.
- **Animated GIF.** Pillow *can* open GIFs, but naively resizing/re-saving with `Image.open` +
  `.save()` only touches the first frame and silently produces a static image — a correctness bug, not
  a quality trade-off. Detecting animation: `img.is_animated` (or `getattr(img, "n_frames", 1) > 1`).
  If animated, pass through unchanged. If genuinely worth optimising later, that requires
  frame-by-frame handling (`ImageSequence.Iterator`) and a size/duration-preserving re-save — real
  extra complexity, explicitly out of scope for "keep `content_save` simple."
- **Anything Pillow cannot open** (corrupted file, unsupported/obscure format, extension mismatch
  where the real bytes are something else entirely). See the failure-mode discussion below — the
  general answer is: catch decode failure, log a warning naming the file, save the original bytes
  through unmodified. Never let one bad image abort the whole `content_save` run, and never drop the
  file's row/bytes.

## 5. Safety

- **Decompression bombs.** Pillow's default `Image.MAX_IMAGE_PIXELS` is ~89.5 megapixels
  (`1024*1024*1024 // 4 // 3`, sized as "a bit under a gigabyte of decompressed RGB data" — Pillow
  source comment). Opening an image over that limit raises `DecompressionBombWarning` (a warning, not
  an exception, by default — silently a no-op in production unless a filter escalates it); opening one
  over *twice* that raises `DecompressionBombError` outright
  ([Pillow `Image.open` reference](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open)).
  Mirror `check_logo_safety`'s pattern exactly: wrap the open+decode in
  `warnings.catch_warnings(); warnings.simplefilter("error", Image.DecompressionBombWarning)` so the
  warning band becomes a catchable exception too, and catch both
  `(Image.DecompressionBombWarning, Image.DecompressionBombError)` alongside the malformed-image tuple.
  Do **not** raise `MAX_IMAGE_PIXELS` or set it to `None` — content_save processes author-supplied
  files from a separate content repo, which is a lower-trust input than code the author wrote by hand,
  and the default cap is generous enough for any legitimate course image.
- **Malformed / truncated files.** Reuse `check_logo_safety`'s exception tuple verbatim:
  `except (OSError, Image.UnidentifiedImageError, SyntaxError, ValueError)`. Its docstring is the
  citation for *why* that specific set: `SyntaxError` for a bad PNG chunk checksum, `ValueError` for a
  too-short `IHDR`, `OSError`/`UnidentifiedImageError` for everything else unreadable or truncated.
  `freedom_ls/tests/images.py` already has fixtures for the first two
  (`break_png_chunk_crc`, `shorten_png_ihdr`) — reusable directly for testing this pipeline, no need to
  write new corrupt-image generators.
- **Sensible failure mode for a management command.** Three options, weighed:
  - *Hard fail the whole run* — wrong. `content_save` is meant to be run repeatedly over a whole
    content repo; one bad image (which the author may not even have noticed, e.g. a truncated
    download) should not block every other topic/course from being saved. This is a CLI batch
    command an author reruns often, not a one-shot deploy gate.
  - *Skip the file entirely (no DB row, no bytes)* — wrong. It silently breaks the `<c-picture
    src="...">` reference in the rendered markdown; a learner would see a broken image with no signal
    to any human that something failed.
  - *Log a clear warning naming the file and the exception, then save the original bytes through
    unmodified* — recommended. This is exactly what happens today for every image (no optimisation at
    all), so a decode failure degrades to "acts like this feature doesn't exist for this one file"
    rather than a new failure mode. `logger.warning(...)` is already the pattern used elsewhere in this
    file for non-fatal conditions (see `Could not find content for path ...` in
    `save_content_to_db`).

## 6. Idempotency

`content_save` is re-run repeatedly against the same content repo (typical authoring workflow: edit,
run, review, repeat). `save_file_to_db()` already deletes the old stored file and re-saves fresh bytes
**from the source file on disk** every run — it never re-reads back its own previously-optimised
output as input. That is the key fact that avoids generation loss: each run's JPEG re-encode always
starts from the same original author-supplied bytes on disk, transforms them once, and writes the
result. Repeated runs produce the same bytes each time (deterministic — same input, same
`quality=82`/`optimize=True` params, same Pillow version → same output), not a cascading
re-compression of an already-lossy JPEG. This is the standard way idempotent image pipelines avoid
"JPEG-of-a-JPEG-of-a-JPEG" generation loss: **always transform from the pristine source, never from a
previously-transformed output** — and this codebase already satisfies that precondition by design
(source of truth is the content repo on disk, not the DB-stored `File.file`), so no extra work is
needed to preserve it. The one thing to get right when implementing: don't accidentally introduce a
"skip if already processed" optimisation that reads the *stored* file back in as a shortcut — that
would break exactly this invariant. If a future optimisation is added to skip unchanged files (e.g. by
mtime/hash) to save re-encode time on `content_save` reruns, it must skip based on **source-file**
identity, not touch/re-derive from the stored output either way.

## 7. Speed

No exact benchmark run against this codebase's actual images (none exist in `demo_content/` to
benchmark against — see above), but rough, well-established orders of magnitude for Pillow JPEG
decode+resize+encode on typical camera/phone photos (4000-6000px source, single core, commodity
hardware): 50-200ms per image for open + `exif_transpose` + `thumbnail(LANCZOS)` + JPEG encode with
`optimize=True`. `optimize=True`'s extra libjpeg pass is the biggest single cost adder, still well
under 100ms extra on images this size. For "a few hundred images" (the scale named in the prompt), that
is roughly **10-60 seconds of added wall-clock** for the whole `content_save` run, single-threaded,
no parallelism needed. That is acceptable for a synchronous CLI command an author runs interactively
or in CI — it is the same order of magnitude as, or smaller than, the markdown parsing/validation and
DB-write work `content_save` already does per file. No case for background processing or
parallelisation at this scale; multiprocessing would add real complexity (Django DB connections per
worker, transaction semantics inside `save_content_to_db`'s single `@transaction.atomic`) for a
saving that doesn't matter at "a few hundred images." If content repos grow to many thousands of
images, `concurrent.futures.ProcessPoolExecutor` over the pure-Pillow transform step (no Django ORM
inside the worker) would be the first lever — explicitly not needed at today's scale, flagging only so
it isn't rediscovered from scratch if the scale changes.

## Concrete shape recommendation (not a full design, just what the numbers above imply)

- One small pure function, no Django/DB imports:
  `def optimise_image(raw: bytes) -> tuple[bytes, str] | None` — returns
  `(new_bytes, new_extension)` or `None` meaning "pass through unchanged" (covers SVG-by-extension,
  animated GIF, and decode failure alike, so `save_file_to_db()` has one branch: optimised bytes or
  original bytes, always saves something).
- Called from `save_file_to_db()` only when `file_type == File.FileType.IMAGE` and the extension is
  not `.svg`. Extension is still the fast pre-filter for SVG (Pillow has no codec for it); everything
  else goes through `Image.open` and is routed by *decoded* `img.format`/`is_animated`, not extension,
  because extension alone can't distinguish e.g. a PNG worth converting to JPEG from one that must
  stay PNG for alpha.
- All tunables (`max_dimension`, `jpeg_quality`) as `ContentEngineConfig` `Setting`s alongside
  `CONTENT_MEDIA_STORAGE_ALIAS`, not module-level constants in the management command — consistent
  with how this app already exposes its other knobs.

---
status: ok
