# Research: serve-time / on-demand image renditions

## Question

Course images are authored huge (camera originals, often 5 MB) and land in `content_engine.File`
via `content_save`. Could FLS shrink them **at serve time** — generate an optimised rendition on
first request and cache it — instead of (or as well as) shrinking them at ingest? This note covers
serve time only; a sibling worker covers ingest-time processing in `content_save`.

## Hard constraint this is judged against

The user has ruled out, explicitly: **no new background services, no task queue, no new
infrastructure a downstream project must run or buy.** `content_save` must stay simple. FLS is
installed into other Django projects — anything this feature requires them to provision (Redis,
Celery, Dramatiq, Django Tasks workers) is a cost imposed on every install, not just this one.
Any option that needs a worker or a broker is **out of budget** and is marked as such below, not
recommended with caveats.

## What's already true in this codebase

- `content_engine.File.file` is a plain `FileField`, not `ImageField` — no width/height stored, no
  Pillow processing anywhere yet. But **Pillow ≥11.0 is already a pyproject dependency**
  (`pyproject.toml:37`), so a DIY resizer needs no new install.
- `file_upload_handler` (`freedom_ls/content_engine/models/files.py:13`) keys every `File.file` at
  `content_engine/{stem}{pk}{ext}` on the `course_media` storage alias
  (`get_content_media_storage()` → `storage_for_alias(config.CONTENT_MEDIA_STORAGE_ALIAS, ...)`,
  `freedom_ls/base/storage.py`).
- `course_media` resolves to the `COURSE_MEDIA` purpose, which is in `SIGNED_URL_PURPOSES`
  (`freedom_ls/deployment/storage.py:19,28-30`) — **private bucket, signed URLs only.**
  `querystring_expire` defaults to 3600s (`freedom_ls/deployment/storage.py:133`, one hour).
- `COURSE_MEDIA` is **not** in `_OVERWRITE_PURPOSES` (`freedom_ls/deployment/storage.py:43`). Two
  writes to the same key on this alias do not collide-and-replace: django-storages' `S3Storage`
  calls `get_available_name()` and suffixes the second write with a random string instead. This
  matters a lot for any scheme that computes a deterministic rendition key (see below).
- `cotton/picture.html`, `cotton/card.html`, `cotton/file-download.html`, `cotton/pdf-embed.html`
  all resolve a `File` via `get_file_by_path` (`content_tags.py:109`) and then render
  `file_obj.file.url` **directly, once, inline in the template** — there is no existing
  indirection layer (no template tag, no manager method) that a rendition scheme could hook without
  touching every one of these templates. A topic page can carry many `<c-picture>` instances, so a
  cold cache is not a one-image problem, it's a whole-page problem.

## The library landscape

| Library | Maintained / Django 6 + Python 3.13 | DB table? | Redis / cache backend? | Worker / queue? | Generation model |
|---|---|---|---|---|---|
| **easy-thumbnails** | Yes — "Django 4.2+", latest 2.10.1 released May 2026 ([GitHub](https://github.com/SmileyChris/easy-thumbnails), [PyPI](https://pypi.org/project/easy-thumbnails/)) | No, filesystem/storage-based by default | No | No | Synchronous, in-request, on first `{% thumbnail %}` reference |
| **sorl-thumbnail** | Yes — Jazzband-maintained, tests against Django 5.2/6.0/6.1, Python 3.10–3.14, released Aug 2026 ([GitHub](https://github.com/jazzband/sorl-thumbnail), [PyPI](https://pypi.org/project/sorl-thumbnail/)) | No (uses a Key Value Store abstraction, not a Django model) | **Recommended default is "cached database" which needs a working Django cache configured with memcached**; Redis is offered as the alternative ([requirements docs](https://sorl-thumbnail.readthedocs.io/en/latest/requirements.html)) | No | Synchronous — "If the thumbnail key is not found [in the KV store], sorl-thumbnail continues to generate the thumbnail" inline ([operation docs](https://sorl-thumbnail.readthedocs.io/en/latest/operation.html)) |
| **django-imagekit** | Yes — maintained by Jeff Triplett/REVSYS, 6.1 supports Django 3.2/4.2/5.2/6.0 ([GitHub](https://github.com/matthewwithanm/django-imagekit), [Read the Docs](https://django-imagekit.readthedocs.io/)) | No table required by default (its `ImageCacheFile` checks storage existence, not a DB row); an optional `CACHEFILE_STRATEGY` can precompute at model-save instead | No, not required | No, not required (Celery integration is optional, not default) | Lazy, on first access to the cache file, generation happens wherever that access occurs — template rendering included |
| **django-pictures** | Yes, actively released (1.7.5, May 2026), Django 5.2/6.0, Python ≥3.10 ([PyPI](https://pypi.org/project/django-pictures/)) | Not disclosed in docs surfaced here | Not disclosed | **Yes — mandatory.** "Django-pictures generates renditions asynchronously via task queues... For Django 6.0+, you must add the `pictures` queue to your `TASKS` setting... If you have either Dramatiq or Celery installed, we will default to async image processing" for older Django | Asynchronous by design — **out of budget** per the hard constraint |
| **django-versatileimagefield** | **No.** "Inactive project... hasn't seen any new versions released to PyPI in the past 12 months... largely unmaintained as of 2025-2026" ([Snyk advisor](https://snyk.io/advisor/python/django-versatileimagefield)) | N/A — dead, do not adopt | N/A | N/A | N/A |
| **wagtail.images renditions** *(pattern, not a dependency FLS could add without Wagtail)* | The pattern itself: a `Rendition` DB row per (image, filter-spec) pair, plus a dedicated serve view that generates-on-first-request and redirects/serves. Wagtail's own docs warn that this "may increase the number of requests handled by Wagtail if you're using an external storage backend like Amazon S3," and that oversized images get silently dropped from the page rather than blocking it ([Performance docs](https://docs.wagtail.org/en/stable/advanced_topics/performance.html)) | Yes, `ImageRendition` model | No | No (synchronous within the serve view) | Same synchronous-on-cold-miss shape as easy-thumbnails/sorl, validated as workable but explicitly flagged as an S3 request-count cost by Wagtail's own docs |

**Bottom line on the landscape:** `django-versatileimagefield` is dead — rule it out outright.
`django-pictures` requires a task queue by design — out of budget regardless of merit. The three
remaining options (`easy-thumbnails`, `django-imagekit`, `sorl-thumbnail`) are all maintained and
Django-6-capable, and none of the three *requires* Redis or a worker to run — but `sorl-thumbnail`'s
documented, recommended default needs a working memcached-backed Django cache, which is itself a new
piece of infrastructure most FLS installs don't already carry (`LocMemCache` is not safe for this —
it's per-process, so two Gunicorn workers would regenerate the same thumbnail independently and
silently duplicate objects at non-overwriting storage). `easy-thumbnails` and `django-imagekit` are
the two that run with nothing beyond what FLS already has: Pillow and object storage.

## The signed-URL problem

`course_media` is private; every URL FLS hands out for it is signed and expires
(`querystring_expire`, 3600s default). This shapes every serve-time thumbnailer, library or DIY,
identically:

- **Reading the original is not free, but it's not the signed URL's problem either.** These
  libraries call `storage.open(name)` on the Django `Storage` API, which talks to S3 directly
  through boto3 — it does not fetch through the public/signed HTTP URL at all. So the "round trip"
  is: one S3 `GetObject` call to pull the (up to 5 MB) original into the app process, Pillow decode
  + resize + re-encode in-process (CPU-bound), one S3 `PutObject` to write the rendition back. All
  three steps happen synchronously in the request/response cycle for every library surveyed here
  that doesn't use a queue.
- **Signing a URL itself is cheap and local — the mistake to avoid is caching it.** `django-storages`
  computes a signed querystring with a local HMAC-SHA256 over the request, no network call. The
  expensive part is the *existence check and the generation*, not the signature. This means: cache
  or memoize "does a rendition exist at this deterministic key" (or, for the DIY approach, nothing
  at all — recompute the key formula each time), but call `.url` fresh on every render. A design
  that instead caches the *signed URL string itself* — e.g., in a Django cache with a TTL — silently
  serves broken links once the signature outlives `querystring_expire`, unless that cache TTL is
  kept safely below 3600s, which just re-adds an extra failure mode for no benefit over recomputing
  the (cheap) signature per request.
- **Writing back to the same private alias needs an overwrite-safe key, and `course_media` doesn't
  have one.** `COURSE_MEDIA` is deliberately not in `_OVERWRITE_PURPOSES` — every other object on
  that alias is written once, at a uuid-derived key, and never replaced. A rendition scheme that
  computes `content_engine/{stem}{pk}_w800.webp` and writes it with `storage.save()` inherits
  `file_overwrite=False`. Two learners racing the same cold cache both pass the `exists()` check as
  false, both write, and the second write lands at a **suffixed** key
  (`..._w800_AbC123.webp`) rather than the deterministic one — so the "deterministic key" property
  a lazy-generation cache depends on breaks under concurrency, and the alias slowly accumulates
  duplicate objects that a future lookup will never `exists()`-hit again. Any serve-time design here
  needs either its own overwrite-safe purpose/alias for renditions, or an explicit "only the first
  writer wins, others discard their own write and re-`exists()`" reconciliation step — neither of
  which any of the surveyed libraries handle for FLS's specific alias layout; it would be FLS-side
  code regardless of which library is chosen.

## Cache-key and cold-start behaviour

On the first request for an uncached rendition, with any of the synchronous options
(easy-thumbnails, django-imagekit, sorl-thumbnail, the Wagtail pattern, or DIY), the learner's
request thread is blocked for: one S3 GET (network round trip, proportional to the up-to-5MB
original), one Pillow decode/resize/encode (CPU, tens to low-hundreds of ms per image depending on
target format — WebP encoding is not free), one S3 PUT (another network round trip), then a local
URL signature. **This repeats once per uncached image on the page.** `picture.html` puts an `<img>`
straight in the DOM per `<c-picture>` component with no lazy-loading gate on the *generation* (only
`loading="lazy"` on the browser's fetch, which does nothing for a synchronous server-side render). A
topic page with a dozen figures, freshly published, turns into up to a dozen serial S3 round trips
plus a dozen image encodes inside a single Django request — a page load that is ordinarily
sub-second can turn into several seconds, or trip a Gunicorn worker timeout, for whichever learner
is unlucky enough to be first. Every subsequent learner is fast, because the rendition now exists at
its deterministic key. This is a real, bounded, one-time-per-image cost — not unbounded — but it is
squarely inside the request/response cycle, on a page a learner is actively waiting on, which is the
opposite of the ingest-time story where this same cost happens once, offline, during a
`content_save` run nobody is waiting on.

## The DIY option

No third-party library, since Pillow is already a dependency. Sketch:

- A deterministic key per `(File, target_width)`, following the existing `file_upload_handler`
  convention: something like `content_engine/renditions/{file.pk}_w{width}{ext}`.
- A small function (not a class hierarchy, not an abstract base per CLAUDE.md's "don't create
  abstract base classes unless asked") — `get_or_create_rendition(file_obj: File, width: int) ->
  str` — that calls `storage.exists(key)`, and on a miss, opens the source via
  `get_content_media_storage()`, resizes with `Image.open(...).thumbnail(...)`, saves to `key`, and
  returns `storage.url(key)`. Backend-agnostic: the same code path runs against local
  `FileSystemStorage` in dev and `S3Storage` in production, because both go through the `Storage`
  API.
- What it actually costs to build: the function above is maybe an hour of work. What's expensive is
  everything **around** it that the libraries would otherwise absorb:
  - The overwrite-race problem above (needs its own purpose/alias decision or a reconciliation
    step — FLS-specific work no library ships pre-solved for this alias layout).
  - Cleanup when `content_save` re-imports a `File` and replaces its bytes: `save_file_to_db`
    already calls `file_obj.file.delete(save=False)` before writing the new original
    (`content_save.py:490-491`) — a DIY rendition cache needs the equivalent, deleting or
    invalidating every rendition key for that `File.pk`, or stale thumbnails silently survive a
    content update.
  - No srcset/format-negotiation machinery — that's extra work on top, not included in the sketch
    above.
  - Ongoing maintenance is now 100% FLS's, with no upstream to pick up Django/Pillow compatibility
    work — versus `easy-thumbnails` or `django-imagekit`, which are maintained today and cost
    roughly the same amount of integration work as the DIY sketch, minus the parts they've already
    solved (case in point: neither of them has an S3-overwrite gotcha specific to *this* alias
    layout, but they also haven't solved it *for* this alias layout — that part is FLS's either way).

## The honest comparison

**What serve-time buys that ingest-time cannot:**
- New sizes without re-running `content_save` — genuinely true, but content in FLS only ever
  changes by re-running `content_save` against the content repository anyway (there's no learner-
  or author-driven upload path for course images), so "add a size later" mostly means "the person
  who'd re-run `content_save` re-runs it" — the counterfactual isn't a locked artifact, it's a
  scheduled batch job that already exists.
- Per-device / responsive `srcset` tailoring on demand, generating only the combinations actually
  requested rather than every combination up front. Real, but the content set is closed and small
  compared to, say, a public CMS with unpredictable traffic patterns — `picture.html` has a fixed,
  small number of rendered contexts (thumbnail card, spotlight/lightbox), so the "combinatorial
  explosion" serve-time is meant to solve barely exists here.
- Format negotiation via `Accept` headers (serving AVIF/WebP only to browsers that support it)
  is the one thing serve-time can do that a build step genuinely can't do *as elegantly* — but a
  `<picture>` element with multiple `<source>` entries (which `picture.html` could grow) lets the
  **browser** pick between formats generated once at ingest, without any server-side negotiation at
  all. The serve-time-only advantage here is thin.

**What it costs:**
- Latency inside the request/response cycle on cold cache, as detailed above — the ingest-time
  approach moves that exact cost to a `content_save` run instead, off any learner's critical path.
- Moving parts: at minimum, the overwrite-safe-key problem above becomes FLS's problem regardless of
  library; at the ceiling, a library's recommended configuration (sorl-thumbnail's memcached-backed
  KV store) that this project's constraint rules out.
- Storage of originals: identical to ingest-time — both keep the original.
- Cache invalidation when `content_save` reruns: ingest-time gets this for free as part of the same
  command already deleting/replacing the old file; serve-time needs an explicit, separate
  invalidation hook wired into `save_file_to_db`, i.e. it doesn't avoid touching `content_save` at
  all, it just adds a second thing `content_save` has to remember to call.

## Recommendation

Do not make serve-time generation the primary mechanism for the "5 MB camera originals" problem.
The content set here is closed and re-imported through one command that already knows every `File`
that changed; doing the resize once, there, off the learner's request path, is strictly cheaper and
has no moving-part cost, and is fully in budget under the "no new infrastructure" constraint. Every
maintained serve-time library evaluated here (`easy-thumbnails`, `django-imagekit`) is a viable
*complement* for a narrow case — a lazy, capped, single-fallback-size DIY rendition for `File` rows
that predate whatever ingest-time mechanism ships, so old content doesn't need a backfill migration
— but that's a safety net, not the mechanism. `sorl-thumbnail`'s recommended configuration and
`django-pictures` are out of budget outright (memcached-class cache dependency and a mandatory task
queue respectively); `django-versatileimagefield` is dead. If a fallback is built, it must be scoped
tightly (one size, `exists()`-gated, explicitly invalidated by `save_file_to_db` on re-import) to
avoid reintroducing the overwrite-race and cold-page-load costs documented above as the common case.

---
status: ok
