# Research: prior art in content-as-code image pipelines, and the authoring experience

Scope: `content_engine.File` images only, ingested by `content_save` from an author-supplied
content repository. Hard constraint carried through every recommendation below: **`content_save`
stays simple — no background service, no task queue, no new infrastructure.**

## What FLS does today (read before comparing)

- `content_save` (`freedom_ls/content_engine/management/commands/content_save.py`) calls
  `validate(path)` first (raises and stops on any schema error), then `save_content_to_db(path,
  site_name)` inside one `@transaction.atomic` block.
- `save_file_to_db()` handles every non-`.md`/`.yaml` file, including images. On **every** run it
  unconditionally does `file_obj.file.delete(save=False)` then re-`save()`s the file from disk —
  there is no check for "did this file actually change since last time." `File` has no stored
  content hash or size/dimensions field to make that check possible today.
- `File` (`freedom_ls/content_engine/models/files.py`) stores the original upload with no derived
  copies, no rendition/variant concept, and no processing metadata.
- Authors reference images via `![[file | title]]`, which `markdown_translate()` rewrites to
  `<c-picture src="file" title="title">`. `c-picture` (`.../templates/cotton/picture.html`) also
  takes `alt`, `description`, `number` — all free-text authoring attributes, not processing
  directives. This is FLS's one authoring-time surface per image reference.
- `validate.py` is schema validation only (pydantic `model_validate` against frontmatter); it has
  no concept of file-level checks (size, dimensions) today — that would be new.
- `demo_content/` images are almost entirely hand-drawn `.svg` (vector), not the large author
  photos/screenshots this problem targets — so there's no existing raster-heavy fixture to model
  against; the 5 MB JPEG/PNG case is not currently exercised anywhere in the repo.

## Half 1 — prior art in comparable systems

### The shared pattern

Every system that ingests author images and serves optimised ones does the same three things,
regardless of vocabulary:

1. **Keep the original, generate derived copies separately.** The original is never overwritten in
   place; optimised/resized copies live alongside or in a separate cache location, addressed by a
   key derived from (source + requested parameters).
2. **Key the cache so repeat work is skipped.** Re-running the pipeline over an unchanged source
   with the same parameters must not redo the transcode.
3. **Split into two families by *when* the derived copy is made** — build-time vs. request-time —
   and that split is the one place these systems genuinely disagree (see below).

Concretely, by system:

- **Hugo** treats an image as a "resource"; calling `.Resize`/`.Fit`/`.Fill`/`.Process` on it in a
  template produces a new resource written under `resources/_gen/images` (configurable via
  `:resourceDir`/`:cacheDir` tokens), keyed on the source plus the operation string. Re-running
  `hugo` reuses the cached file instead of reprocessing; `hugo --ignoreCache` forces a redo.
  [gohugo.io/content-management/image-processing](https://gohugo.io/content-management/image-processing/)
  Only "processable" raster formats go through this path — SVG is a vector format and passes
  through untouched, which matches most of `demo_content`'s existing images.
- **Astro** (`astro:assets`) processes images referenced via `<Image>`/`getImage()` at build time
  and caches the output in `node_modules/.astro/assets`, keyed so unchanged sources aren't
  reprocessed on the next build.
  [docs.astro.build/en/guides/images](https://docs.astro.build/en/guides/images/) ·
  [github.com/withastro/astro/commit/818252a](https://github.com/withastro/astro/commit/818252acda3c00499cea51ffa0f26d4c2ccd3a02)
  Astro's escape hatch from processing is directory/tag convention, not metadata: put the file in
  `public/` (never touched) or reference it with a plain `<img>` tag instead of the `<Image>`
  component/import.
  [zellwk.com/blog/simpler-astro-images](https://zellwk.com/blog/simpler-astro-images/)
- **Eleventy Image** (`@11ty/eleventy-img`) writes transformed files into a `.cache` directory
  during build and explicitly **skips the transform if the output file for that
  source+params already exists** — the same idempotency FLS's `save_file_to_db` currently lacks.
  [syntackle.com/blog/eleventy-image-html-transform-plugin-disk-cache](https://syntackle.com/blog/eleventy-image-html-transform-plugin-disk-cache/) ·
  [zachleat.com/web/faster-builds-with-eleventy-img](https://www.zachleat.com/web/faster-builds-with-eleventy-img/)
- **Next.js `next/image`** is the outlier: it optimises **on request**, not at build, caching the
  result keyed by `(url, width, quality, format)` the first time a given size is actually
  requested. This needs a running image-optimisation endpoint/server at all times — it is the
  clearest example of the "build server / image CDN" pattern the user has already ruled out for
  FLS.
  [nextjs.org/docs/app/getting-started/images](https://nextjs.org/docs/app/getting-started/images) ·
  [strapi.io/blog/nextjs-image-optimization-developers-guide](https://strapi.io/blog/nextjs-image-optimization-developers-guide)
  Its per-image escape hatch is a component prop, `unoptimized={true}`, which serves the file as-is
  — but note the documented gotcha: a global "unoptimized" config setting cannot be overridden back
  on per-image, only off. One-way escape hatches like this are worth avoiding.
  [github.com/vercel/next.js/issues/85208](https://github.com/vercel/next.js/issues/85208)
- **Wagtail** keeps the uploaded `Image` row untouched and generates **renditions** — new derived
  image files — lazily, the first time a `{% image %}` tag with a given spec (e.g. `width-800`) is
  hit, then reuses that rendition file thereafter; rendition *lookups* are additionally cached
  (Django cache, default backend, or a dedicated `"renditions"` alias) to avoid a DB hit on every
  page render.
  [docs.wagtail.org/en/stable/advanced_topics/images/renditions](https://docs.wagtail.org/en/stable/advanced_topics/images/renditions.html)
  This is the closest existing Django-ecosystem shape to what FLS could build: one source row
  (`File`), N derived rows/files keyed by spec, generated once. `django-imagekit` and
  `sorl-thumbnail` follow the identical shape purely at the library level — thumbnail filename/key
  is derived from source + requested options, checked before regenerating.
  [sorl-thumbnail.readthedocs.io](https://sorl-thumbnail.readthedocs.io/_/downloads/en/latest/pdf/)
- **Open edX Studio** is a useful negative data point: it does **not** optimise course images at
  all. Studio enforces only a 50 MB upload ceiling and tells authors in the docs to compress images
  themselves before uploading — a purely documentation-based nudge, not an enforced or automated
  one.
  [edx.readthedocs.io/.../course_files.html](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-redwood.master/course_assets/course_files.html)
  This is effectively FLS's current situation (author uploads a 5 MB JPEG, it goes straight to
  learners) and is direct evidence that "just tell authors to compress" doesn't get fixed by an
  LMS peer without deliberate engineering — Open edX has had this exact complaint for years.
- **Moodle**'s "draft file area" is unrelated to optimisation — it's a staging area for the rich
  text editor so in-progress edits don't touch the live file until save.
  [moodledev.io/docs/4.5/apis/subsystems/form/usage/files](https://moodledev.io/docs/4.5/apis/subsystems/form/usage/files)
  Moodle likewise has no built-in raster image optimisation pipeline for course content images.

### Where systems genuinely disagree

**Build-time (Hugo, Astro, Eleventy) vs. request-time (Next.js, Wagtail-on-first-render,
sorl/imagekit).** Build-time systems process everything up front as part of a single deterministic
pass and need no server component afterwards; request-time systems process lazily on first access
and need a resolver (view, middleware, or dedicated service) sitting in front of every image URL.

**This is the single most load-bearing finding for FLS.** `content_save` *is* FLS's build step —
authors already run it once per content push, inside one transaction, with no server component.
That maps FLS directly onto the Hugo/Eleventy build-time family, not the Next.js/on-demand family.
Recommend: process images synchronously inside `save_file_to_db()` (or a function it calls) during
`content_save`, the same moment the file is written to storage — not lazily on first learner
request. A request-time resolver would need new infrastructure (a view or middleware doing
first-access generation, plus a lock to avoid duplicate concurrent generation) that the hard
constraint has already ruled out.

**What to steal, and what to leave:**

| Steal | From | Why |
|---|---|---|
| Never touch the original in place; write processed bytes separately | All of them | `File.file` should keep being the author's exact upload; irreversible in-place edits are the root of the WordPress complaints below |
| Key derived work by source content + params, skip when unchanged | Hugo, Eleventy, sorl-thumbnail | `save_file_to_db` currently re-writes every file on every run; this is the fix, and it's needed regardless of whether optimisation is added |
| Process at the single synchronous ingestion point, not lazily on request | Hugo, Astro, Eleventy | Matches `content_save`'s existing shape; avoids needing a resolver/service |
| Leave request-time, on-demand generation | Next.js, Wagtail's lazy rendition | Needs a live resolver — ruled out by the "no new infrastructure" constraint |
| Leave a rendition/variant *concept name* as prior art, but do not reuse the word "variant" | Wagtail | FLS already uses "variant" for UI component styling; call any per-size derived copy something else (e.g. reference it by "optimised file" / a size descriptor) in the design doc |
| Pass SVG through untouched | Hugo | SVG is vector; re-encoding it is meaningless and risks breaking it. `demo_content`'s images are almost all SVG today |

## Half 2 — the authoring experience and its complaints

### Validation-time warnings: real, but weak on their own

`content_validate`/`validate.py` could warn "this image is 5 MB / 6000 px wide" without failing the
build. General research on developer tooling shows warnings that don't block anything get tuned
out over time — "if a rule is important, it should be set to error so developers don't have the
option of ignoring it," and unenforced warnings "pile up... creating noise... important warnings
get lost in the noise."
[stackoverflow.blog/2020/07/20/linters-arent-in-your-way](https://stackoverflow.blog/2020/07/20/linters-arent-in-your-way-theyre-on-your-side/) ·
[dev.to/thawkin3/eslint-warnings-are-an-anti-pattern](https://dev.to/thawkin3/eslint-warnings-are-an-anti-pattern-33np)
Open edX's outcome is the concrete version of this: it has relied on a documentation-only nudge
("compress before uploading") for years, and the underlying problem — large author images reaching
learners — evidently still exists there, which is exactly the problem FLS is trying to avoid
repeating. A warning authors can ignore, with no automatic remedy, does not by itself solve
anything; it just moves the failure from "silent" to "logged and still silent."

**Recommendation:** don't rely on validation-time warning as the *fix*. Use it (if at all) as
secondary, human-readable confirmation of what the automatic step already did, not as the
enforcement mechanism. None of the researched static-site tools (Hugo/Astro/Eleventy) warn-and-wait
for the author to act — they process automatically and unconditionally as part of the build. That
matches the "keep it simple, no extra step for the author" spirit of the hard constraint better
than a warn-then-fail-later validation gate would.

### The silent-fix objection is real and well documented — but the fix isn't "ask the author," it's "don't discard the original"

The clearest cautionary tale is WordPress's `big_image_size_threshold`, introduced in WP 5.3: any
upload over 2560 px is automatically scaled down and the scaled copy is what's served.
[make.wordpress.org/core/2019/10/09](https://make.wordpress.org/core/2019/10/09/introducing-handling-of-big-images-in-wordpress-5-3/)
The complaints that followed map onto exactly the objection this brief raises:

- **Detail/quality loss.** WordPress compresses every JPEG to 82% quality by default; "high-detail
  product photos, photography portfolios, and images with text can look soft."
  [smartwp.com/large-image-scaling-wordpress](https://smartwp.com/large-image-scaling-wordpress/)
  For FLS this maps directly onto screenshots and diagrams with fine text — exactly the content
  type `demo_content`'s "Annotated diagrams" pattern uses (`c-picture` + a `<dl>` legend keyed to
  letters drawn on the image). Aggressive re-encoding is the one thing most likely to make those
  labels illegible.
- **No opt-out, originally.** "Users complain that they're given no way to turn it off... WordPress
  fails to consider that 95%+ of their user base are not technically able to implement such
  workarounds" (the fix was a PHP filter hook — a developer-only escape hatch).
  [smartwp.com/large-image-scaling-wordpress](https://smartwp.com/large-image-scaling-wordpress/)
- **But the original was never deleted.** "The full-resolution original is still saved in your
  uploads folder... grab the original back from your uploads folder."
  [smartwp.com/large-image-scaling-wordpress](https://smartwp.com/large-image-scaling-wordpress/)
  This is the load-bearing detail: WordPress's actual failure was the *lack of a documented,
  reachable* opt-out, not the fact that it silently transformed. It never lost data — it just made
  recovering the original invisible. That is a cheaper, more important thing for FLS to get right
  than building an interactive prompt.
- **Metadata/copyright stripping.** "When resized images are created in WordPress, the platform
  strips all metadata, including copyright information and contact details" — a specific,
  recurring complaint from photographers/agencies whose business depends on EXIF/IPTC copyright
  tags surviving.
  [shuttermuse.com/warning-photographers-wordpress-copyright-metadata](https://shuttermuse.com/warning-photographers-wordpress-copyright-metadata/)
  A general optimisation tool (ShortPixel) defaults `KEEP_EXIF` to **off** — metadata removal by
  default, not opt-in.
  [shortpixel.com/blog/can-compressing-an-image-remove-copyright-information](http://shortpixel.com/blog/can-compressing-an-image-remove-copyright-information/)
  This is lower-stakes for FLS course content (diagrams/screenshots rather than licensed
  photography) but the *default direction* matters: default to preserving what the encoder library
  preserves by default, don't add an explicit strip step, and don't advertise metadata-stripping as
  a feature.
- **Animated GIF flattened to a static frame.** This is a concrete *technical* risk, not just a
  UX complaint: several image libraries silently drop all but the first frame when resizing/
  optimising a GIF unless the pipeline explicitly handles multi-frame images (`sharp`'s
  `.gif({ animated: true })` requirement is one documented instance;
  [github.com/lovell/sharp/issues/4418](https://github.com/lovell/sharp/issues/4418) a
  Discourse report of "optimized/resized GIFs lose all animation, become still frames" is another,
  [meta.discourse.org/t/optimized-resized-gifs-lose-all-animation](https://meta.discourse.org/t/optimized-resized-gifs-lose-all-animation-become-still-frames/19714)
  and the standard remedy is to "coalesce" the GIF before resizing).
  `File.FileType.IMAGE` in FLS includes `.gif` today
  (`freedom_ls/content_engine/management/commands/content_save.py:442`) — whatever image library
  the eventual implementation reaches for (Pillow is the standard choice given FLS's Python/Django
  stack) must be explicitly told to preserve/process every frame, or GIFs must be excluded from
  optimisation entirely and passed through like SVG. This is worth flagging directly for the
  implementation, not just the authoring UX.
- **Unexpected cropping.** Not as heavily documented in complaint form as the above, but implicit
  in every resize API surveyed: Hugo's `.Fill` crops to an aspect ratio (with an anchor), while
  `.Fit`/`.Resize` preserve the whole image. The complaint risk is real wherever a "fill"-style
  operation is chosen by default instead of a "fit"-style one.
  [gohugo.io/content-management/image-processing](https://gohugo.io/content-management/image-processing/)
  Whichever library FLS reaches for, the default operation for course images should be
  resize-to-fit (scale down, preserve full frame, cap max dimension/bytes) — never crop — since
  nothing in the `c-picture` authoring surface (`alt`, `title`, `description`, `number`) gives the
  author a way to specify a crop anchor, and an uncommunicated crop is worse than an uncommunicated
  resize.

### Per-image opt-out: what comparable systems actually offer, mapped onto FLS's authoring surface

Three distinct opt-out mechanisms were found across the tools surveyed, and FLS's authoring surface
constrains which ones are cheap to build:

1. **Component/call-site prop** — Next.js's `unoptimized={true}` on `<Image>`. Fine-grained,
   colocated with the reference, discoverable at the point of use. FLS's closest equivalent is an
   attribute on the `c-picture` component and/or the `![[file | title]]` shorthand that
   `markdown_translate()` already rewrites into it — e.g. an additional pipe segment or attribute
   the author adds at the point they reference the image. This requires schema/template changes
   (new pydantic field or shorthand grammar, new `c-picture` attribute) but matches how FLS authors
   already control per-image behaviour (`alt`, `title`, `description`, `number` are all set this
   way already), so it's consistent with the existing authoring vocabulary rather than introducing
   a new one.
2. **Directory/location convention** — Astro's `public/` folder (anything placed there is never
   processed).
   [zellwk.com/blog/simpler-astro-images](https://zellwk.com/blog/simpler-astro-images/)
   FLS's equivalent would be a convention like "files under an `originals/` (or similarly named)
   directory are stored as-is" — cheaper to build than option 1 (no schema/template change, just a
   path check in `save_file_to_db`/`get_all_files`), but coarser: the author has to move the file
   rather than annotate it in place, and it's invisible from the content file itself (you can't
   tell an image is exempt by reading the markdown that references it).
3. **Global config, not per-image** — WordPress's `big_image_size_threshold` filter, and
   Next.js's config-level `unoptimized` (which, notably, cannot be overridden back on
   per-image — [github.com/vercel/next.js/issues/85208](https://github.com/vercel/next.js/issues/85208)).
   Useful as a site-wide escape hatch (e.g. an env var to disable processing entirely for a given
   deployment) but not a substitute for a per-image one — flag this as a "have both, and make sure
   the per-image one can win" design note, given the Next.js pitfall above.

Given "`content_save` must stay simple," the directory-convention route (2) is the cheaper build,
but the attribute route (1) is more consistent with how FLS already lets authors control per-image
behaviour and is more discoverable (visible right next to the image reference, not a fact about
where the file happens to live). This is a genuine trade-off for the design doc to make explicitly,
not one this research resolves — but note that whichever is picked, it should be **reversible and
visible**, per the WordPress lesson above: the point of an opt-out is that the author can find it
and trust it, not that it exists in principle in a changelog.

### What authors are told afterwards

None of the build-time SSGs surveyed produce a human-facing "here's what changed" report by
default — Hugo/Astro/Eleventy just process and move on; the evidence of processing is the file
itself (and `--verbose` cache-hit logging in Hugo's case). Wagtail's renditions are entirely silent
— generated on first render, never reported anywhere. The WordPress complaints above suggest the
opposite lesson from a *support-burden* angle: the actual failure mode wasn't "no report," it was
"no way to find out what happened or recover the original" when a learner or author *noticed* a
problem after the fact.

`content_save` already has the right surface for this: `save_file_to_db()` logs one line per file
via `logger.info(f"{action} {file_type} file: {relative_path}")`
(`freedom_ls/content_engine/management/commands/content_save.py:496-497`), which is the exact place
authors already look when running the command. Extending that existing log line with what
optimisation did (original size → resulting size, or "left unchanged: below threshold" / "left
unchanged: opted out") costs nothing structurally and directly avoids the WordPress-style "silent
until someone complains" failure — it's reporting the author already reads, not a new report they
have to go find.

## Recommendations summary (for the design/plan phase, not decided here)

- Process synchronously inside `content_save`'s existing file-ingestion step (Hugo/Eleventy
  build-time shape), not lazily on request (Next.js/Wagtail shape) — the "no new infrastructure"
  constraint effectively already picks this for FLS.
- Never overwrite/discard the author's original bytes; whatever "optimised" means, keep the
  original recoverable. This is the one thing WordPress's most-complained-about feature still got
  right, and getting it wrong is the actual root of every "silent-fix" horror story found.
  "Variant" is taken in this codebase for UI styling — pick different wording (e.g. reference
  concretely as "the optimised file"/"the original file", not "variant").
  spec_dd should decide the actual field/model shape; this file only rules out the word.
  the codebase's own vocabulary is `File`, so keep new fields/columns on `File` rather than
  inventing a parallel model, matching Wagtail's single-Image-row shape rather than a separate
  rendition table, unless the design doc finds a concrete reason to split (e.g. multiple sizes).
- Key any processing so `content_save` re-runs are idempotent (skip files unchanged since last
  save) — this is needed independent of optimisation, since `save_file_to_db` currently redoes the
  file write unconditionally on every run.
- Exclude SVG from raster processing entirely (pass-through, matching Hugo).
- Treat animated GIF as a real technical risk, not just a UX one: either explicitly preserve all
  frames or exclude GIF from processing outright.
- Default to resize-to-fit (scale, don't crop) since nothing in `c-picture`'s authoring attributes
  gives an author a crop anchor to specify.
- Prefer automatic-and-reversible over warn-and-wait: a validation-time warning alone is weak
  (warning fatigue is well documented) and mirrors Open edX's unresolved "please compress before
  upload" status quo; make the fix automatic, and use validation/logging to report what happened,
  not to gate on the author noticing.
- Give a per-image opt-out. A `c-picture`/shorthand attribute is the more discoverable, more
  FLS-idiomatic option (consistent with `alt`/`title`/`description`/`number` already working this
  way); a directory convention is the cheaper build. Whichever is chosen, log it in the same
  per-file line `save_file_to_db` already emits.

status: ok
