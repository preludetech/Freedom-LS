# Optimise content images

Course images are authored outside FLS and loaded by `content_save`. Authors drop in whatever their
camera or screenshot tool produced, so a topic image is routinely 5 MB. Every learner who opens that
topic downloads all of it, over whatever connection they have, to render it in a card 576 px wide.

We fix it where the file enters the system. `content_save` re-encodes each image once and stores
that instead of the original.

## Optimise at ingest, not on the way out

`content_save` is FLS's build step. It already runs over the whole content tree, in one transaction,
with nobody waiting on it. Doing the work there costs a learner nothing.

Generating an optimised copy on first request instead is a poor fit here, for reasons specific to
this codebase. `course_media` is a private bucket served by signed URLs, so a serve-time resizer puts
an S3 download, a Pillow encode and an S3 upload inside a learner's request, once per uncached image,
on a topic page that can carry a dozen figures. `COURSE_MEDIA` is also excluded from the
overwrite-safe purposes on purpose, so when two learners race the same cold cache both write, and the
second write lands at a suffixed key. That breaks the deterministic key any lazy cache depends on.
`research_serve_time_renditions.md` has the full survey, including which off-the-shelf libraries are
still maintained and which need infrastructure FLS will not ask downstream projects to run.

## What content_save does to an image

One image in, one image out. `File.file` holds the optimised bytes. No second copy, no new model.

- **WebP, always.** Pillow's own wheels bundle libwebp, so this costs no new dependency and no
  system package. WebP is about 30% smaller than JPEG at matched quality, and every browser that can
  reach a course player has supported it for years. AVIF would be smaller again, but Pillow's
  published wheels stopped bundling libavif, and its encode is an order of magnitude slower inside a
  synchronous command. `research_formats_and_budgets.md` sets out the measured numbers behind both
  calls.
- **Longest edge capped at 1600 px**, scaled to fit, never cropped and never upscaled. That covers
  the lightbox at 2x pixel density, the widest the player ever renders an image.
- **Quality chosen per image.** Photographs get lossy WebP. Screenshots, diagrams and anything else
  built from flat colour and hard edges get lossless, because lossy codecs put visible haloes around
  text and course content is full of annotated screenshots.
- **The source format decides which, and a second encode settles the rest.** A JPEG arriving means
  the author already accepted lossy compression, and a camera model in the EXIF confirms it. A PNG
  means someone chose lossless, which is what screenshot tools and diagram exports produce. Where
  those signals disagree, encode the image both ways and keep the lossless result unless the lossy
  one is substantially smaller. The second encode falls on a minority of images and buys a decision
  with no threshold to tune. `research_formats_and_budgets.md` proposes counting distinct colours
  instead; that is superseded here, because the antialiased text, shadows and gradients in a modern
  screenshot read as photographic, which is the one case this split exists to protect.
- **Never grow a file.** If the re-encode comes out no smaller than its source, keep the source.
- **Orientation, colour and metadata.** The encoder applies EXIF rotation to the pixels before it
  resizes, so phone photos do not come out sideways, and it carries the ICC profile over, so
  wide-gamut photos do not desaturate. The rest of the EXIF block goes, taking with it the GPS
  coordinates phones attach to author photos.

The target is 80 to 150 KB for a typical content image. A 5 MB photo lands near 120 KB.

## What it leaves alone

SVG passes straight through. Pillow cannot open it, rasterising a vector would be strictly worse,
and every image in `demo_content/` today is an SVG. Animated GIF passes through too, because naively
re-saving one keeps the first frame and silently kills the animation.

An image Pillow cannot decode, whether truncated, corrupt, or not what its extension claims, gets a
logged warning and is stored as-is. One bad file must not abort a `content_save` run over a whole
content repository, and it must not vanish either, or the learner gets a broken image with nothing
telling anyone why. `freedom_ls/organisations/validators.py` already decodes untrusted image bytes
for logo uploads, and the exception set this needs is worked out and commented there.

## Deliberately not in this change

- **No responsive image ladder.** One stored size, one `<img>`, one URL. Multiple widths with
  `srcset` would save perhaps another 2x on mobile and cost a model change plus rework across
  `c-picture`, `c-image-grid` and the lightbox. `research_responsive_delivery.md` works out the
  widths and the markup, should anyone pick this up later.
- **No stored width and height.** `c-picture` still cannot reserve space before an image loads, so
  the page still shifts as figures arrive. A real problem, a separate one, and no worse after this.
- **The lightbox and the inline thumbnail still share one URL.** A learner who never opens the
  lightbox still pays for the larger image, but that is now around 120 KB rather than 5 MB.
- **No per-image opt-out.** The format signals, the passthrough rules and the never-grow guardrail
  cover the cases an author would reach for one. If a real case turns up, the marker should name the
  intent, something meaning keep this one crisp, rather than the genre. Photo and diagram map onto
  lossy and lossless cleanly, but screenshot straddles both, so genre words ask the author a question
  with no stable answer. Weigh two costs before adding one. An attribute on `c-picture` sits at the
  reference while the encode happens once per file, and several topics can reference one image, so it
  needs a rule for when they disagree. A filename or directory marker avoids that but changes the
  relative source path, which is the key `<c-picture src="...">` resolves against, so adopting one
  means editing every reference to every image that gets renamed.
- **No skipping of unchanged files.** Every run re-encodes everything, tens of seconds for a few
  hundred images. The encode always starts from the pristine source on disk rather than from what
  was stored last time, so repeated runs produce identical bytes and there is no cumulative quality
  loss to guard against.
- **Only `content_engine.File` images.** Organisation logos and learner uploads stay out of scope.

## Consequences worth knowing

The stored file's extension changes. `photo.jpg` is stored as WebP, and `File.mime_type` records
that. The author's filename and the relative source path stay as they are, and the source path is
what `<c-picture src="photo.jpg">` resolves against, so existing content keeps working untouched.

Images already in the database keep their unoptimised bytes until `content_save` runs again. That
command is the only way content reaches the database, so re-running it is the migration.

Authors learn what happened from the line `content_save` already prints per file, extended to say
what each image became.

## Research

- `research_ingest_pipeline.md` for the Pillow transform, its correctness traps, and why re-runs do
  not degrade quality
- `research_formats_and_budgets.md` for the format, quality and dimension numbers, with sources
- `research_serve_time_renditions.md` for the serve-time option and why it loses here
- `research_responsive_delivery.md` for the widths and markup a responsive ladder would need
- `research_prior_art.md` for how Hugo, Astro, Eleventy, Wagtail and Open edX handle this, and the
  authoring complaints worth avoiding
