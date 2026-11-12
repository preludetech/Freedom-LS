# Research: prior art for profile pictures and image uploads

Topic: what has already been tried for profile pictures and untrusted image uploads, in FLS and elsewhere, and what happened. Read first: `idea.md` and `answers.md` (answers settled: private user-data bucket with short-lived signed URLs; a deactivated user keeps their picture, the file is erased only when the user is deleted).

Limits: only Read/Grep/Glob and web tools were available, so `git log` was not run. Findings come from the spec archive and current source.

## 1. In FLS: what exists and what it taught

### 1.1 The decode guard (`freedom_ls/base/images.py`)

Arrived with `spec_dd/3. done/2026-09-03_12:41_optimise-content-images/` (the plan extracted it from the logo validator). Lessons baked into its docstrings:

- Pillow reports malformed files with several exception families, not just `OSError`. `DECODE_FAILURES` covers `OSError`, `UnidentifiedImageError`, `SyntaxError`, `ValueError`, `struct.error` and `IndexError`. Catching only `OSError` lets bad PNG chunks and truncated GIF frames through as 500s.
- A decompression bomb has two bands: past `MAX_IMAGE_PIXELS` Pillow only warns; past twice that it raises `DecompressionBombError`, which is NOT an `OSError`. The earlier report-branding spec (`2026-08-28_07:52_report-rendered-with-org-name/1. spec.md` ~line 283) already called "`DecompressionBombError` in the tuple" non-optional. An untrusted upload must escalate the warning (`bomb_warnings_as_errors`); author-supplied content deliberately does not.
- `ImageFile.LOAD_TRUNCATED_IMAGES` is process-global and WeasyPrint turns it on (lazily, in the same process that serves uploads). After the first report renders, `Image.open` quietly accepts truncated bodies. `truncated_images_rejected()` holds it false and restores the previous value (WeasyPrint sets it on purpose). Implication for a picture validator: use both context managers, and do not rely on the flag's default.

### 1.2 Organisation logo validator (`freedom_ls/organisations/validators.py`)

From `2026-08-21_09:09_organisations/` and reshaped by the report-branding spec.

- Layers: extension allowlist (a filter, not a boundary), declared-size check before reading, bounded read (`MAX_BYTES + 1`), then `Image.open(...).verify()` plus a second `Image.open` for format/size (`verify()` destroys the object), then format allowlist (PNG, JPEG, WebP) and a dimension cap (4000 px per axis, 2 MiB).
- `check_logo_safety(raw)` is split from the upload validator because it has two callers that must not drift: the upload path and the report pipeline reading a stored logo back. Reason given: field validators only run under `full_clean()`, so an unvalidated file can reach storage; the read side is a second enforcement point. A picture will have the same split between upload and render/serve.
- Minimum size is not a safety rule, so it stays only on the upload path.
- Logo validator deliberately does NOT strip EXIF ("location metadata ... does not apply to an admin-uploaded corporate logo"; re-encoding a transparent WebP risks visible regression). That reasoning does not carry over to a person's photo.
- QA (`2026-08-28_07:52_.../qa_report.md`, 35 tests, 0 bugs) confirmed: SVG renamed `.png` rejected with "File is not a readable image"; 9.3 MB rejected; 48x24 px rejected; a 45-byte text file named `.png` attached bypassing `full_clean` degraded to a fallback rather than a traceback; a logo deleted from storage with the DB row left pointing at it did not fail the render. Lesson: the consumer of a stored image must tolerate a missing or invalid file (this is the idea's "picture file is missing" open question, and the answer used before is fall back quietly).

### 1.3 Storage aliases and public vs signed (`2026-08-27_12:32_prod_bucket_setup/`)

`research_public_vs_signed_logos.md` is the most relevant prior art on the open "how is it served" question, though the owner has since answered it as signed URLs:

- A fresh signed URL on every render is a genuine cache miss at the browser and at any CDN: the cache key includes the query string, and a SigV4 URL differs on `X-Amz-Date` and signature. Sources cited there: Cloudflare cache-key docs (https://developers.cloudflare.com/cache/how-to/cache-keys/index.md), Cloudflare community thread (https://community.cloudflare.com/t/cache-miss-on-s3-presigned-urls/832774), django-s3-storage issue 138 (https://github.com/etianen/django-s3-storage/issues/138), django-storages issue 1222 (https://github.com/jschneier/django-storages/issues/1222).
- Longer `querystring_expire` does not help; every `.url` call mints a new signature. The only fix is bucketed/rounded signing time (https://advancedweb.hu/cacheable-s3-signed-urls/), which neither django-storages nor boto3 supports, and which widens the window a leaked URL stays valid.
- Serving through a Django view gives a stable cacheable URL but puts a request in the hot path of every avatar, and only pays off if the view response is itself edge cached.
- Decision made then: logos go in a public bucket because they are branding with UUID keys, free R2 egress and no listing. Profile pictures were listed in the private "learner-uploads" bucket as future content, i.e. the split put pictures on the signed side from the start.
- Consequence for this spec: an avatar appears in many rows (messaging lists, educator tables, chips). With signed URLs each row mints a signature (a signing call is local computation, no network, but the browser re-downloads the image on every page load because the URL changes). The spec should say whether it accepts that, uses a short-TTL Django-cache of the URL, or adds a stable view. The owner picked signed URLs, so the spec should record this cost explicitly rather than rediscover it in QA.
- Overwrite behaviour: only `public` overwrites at a stable key (`_OVERWRITE_PURPOSES = {LOGO_PURPOSE}` in `freedom_ls/deployment/storage.py`). The skill forbids adding an existing purpose to that set. `user_uploads` never overwrites, so a replaced picture lands at a storage-suffixed sibling key and the old object must be deleted by code. The idea already says "no existing purpose is reused for its overwrite behaviour"; a new alias/purpose is expected. `SIGNED_URL_PURPOSES` currently holds course media, user uploads and reports; a new alias for profile pictures needs adding to it (and to `build_storages()` and the base `STORAGES` dict).
- The skill: "a field with a stable key whose extension can change needs the same [delete of the superseded object], or the old object stays in the bucket ... for good". `Organisation.save()` does it.

### 1.4 Learner upload of a file: `QuestionAnswerFile` (`2026-09-10_09:45_simple-application-forms/`)

The closest sibling: a user-supplied, personal, `user_uploads` file.

- Key: `user_uploads/{user_id}/form_answers/{pk}{ext}`, extension chosen by FLS after sniffing the content, never the uploader's filename (path-traversal and collision lesson from the logo's `_logo_upload_path`; the content_engine `file_upload_handler` that interpolates a filename stem was named as the pattern NOT to copy). Anonymous sitting files go under `user_uploads/anonymous/{sitting}/...`.
- `save()` reads the stored name through `_base_manager` (site-filtered `objects` would miss the row), saves, then deletes the superseded storage object. Reading the previous name from the database rather than tracking it on the instance was needed because `file.save()` mutates an instance that was never loaded. Reuse this pattern for replace.
- Research (`research_file_upload_security.md`):
  - EXIF: for personal photos strip unconditionally; re-encoding through Pillow without passing `exif=` drops it, and a full re-encode also forces a full decode and re-emits known-good bytes (one operation, two goals). Cost: JPEG re-compression at about quality 90 is fine for review/avatar use; PNG re-encodes losslessly. Source cited: https://www.gyford.com/phil/writing/2021/10/05/removing-exif-images-django/.
  - No `python-magic` dependency: Pillow `verify()` plus full decode is stronger and needs no libmagic. No HEIC support without `pillow-heif`; reject with a clear message (modern iPhones default to HEIC, so this is a likely user-facing refusal for avatars too).
  - Django's `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE` (5 MB in `settings_prod.py` at that time) fire before the form: `RequestDataTooBig` becomes a bare HTTP 400 with no field error. Keep the validator's own limit comfortably under the global cap so the user gets a form error. (https://code.djangoproject.com/ticket/29427)
  - Django does not delete the stored object when a row is deleted. That spec's threat table calls this "the first place in FLS that needs to solve it"; the sweep for the delete-the-row case (and for erasing a user) is therefore a place to verify rather than assume. `course_applications/receivers.py` has `post_delete` receivers on `QuestionAnswerFile` that only touch timestamps; I did not find a storage-delete there, and `pre_delete` on `User` handles unclaimed applicants only. For this spec: the answer "file is erased only when the user is deleted" needs an explicit `post_delete`/`pre_delete` on `User` (or the model holding the picture) that deletes the storage object, and a test for it. Confirm what the current code does before relying on cascades.
  - Signed URLs vs streaming for `user_uploads`: that spec chose to stream through an admin-gated Django view because a signed URL is a bearer token valid for its whole expiry and cannot re-check state at fetch time. That argument was about confidential, permission-gated documents; a profile picture shown to anonymous viewers is the opposite case, so signed URLs are defensible here, but the tradeoff (URL leaks, valid for the TTL, including after the picture is replaced or the user is erased) should be stated with the chosen TTL.
- QA (`qa_report.md` and `todo.md`): 93 test records, no bugs in the final run, but the todo shows QA bugs found and fixed earlier: client-side 6 MB check did not stop the upload; attached-file Download link a 20 px tap target on mobile; empty file picker should be a "Choose a file" button with Replace and Remove sitting level. UX lessons for the picture form: a client-side size check must actually block submit; Replace and Remove controls need real tap targets (mobile) and sit level; an empty picker reads as a button.
- Scope lesson: a malware-scanning seam with nothing behind it was cut ("a seam with no scanner behind it is the appearance of a control"; parked in `spec_dd/1. next/file-scanning/`). Do not add a scan or moderation seam for pictures; moderation is already out of scope.

### 1.5 Where avatars are rendered today

`research_existing_profile_code.md` (in `spec_dd/1. next/learner-public-profile/`): `panel-avatar-chip`, `participant_avatar.html` and the header menu each render `User.initials`; no picture field exists. The only ImageFields in the codebase are the three on `Organisation` (`logo`, `logo_on_dark`, `profile_logo`), plus the two FileFields (`QuestionAnswerFile.file`, `GeneratedReport.file`). There was no earlier attempt at a user picture, so no code to revert or reuse; the TODO in `accounts/forms.py` is the only trace. Per project rules that TODO may be removed only once the work completes.

### 1.6 Git log

Not examined (no shell tool). The recent commits provided in context are spec bookkeeping only (`start the spec`, roadmap cut). If the spec author wants commit-level history of the logo validator and decode guard, run `git log --follow -- freedom_ls/base/images.py freedom_ls/organisations/validators.py`.

## 2. Elsewhere: incidents and what they imply

### 2.1 EXIF location leaks from profile photos

- Partiful (October 2025): profile photos uploaded to the event app retained granular GPS location metadata, identifying home or work addresses, particularly in rural areas; disclosed by the company on 1 October 2025 after a researcher report, and existing photos were retroactively scrubbed. https://techcrunch.com/2025/10/04/event-startup-partiful-wasnt-stripping-gps-locations-from-user-uploaded-photos/
- Peloton and Echelon profile photos were reported earlier for the same failure (not stripping metadata, exposing real-world location). Reported alongside the Partiful coverage; I did not retrieve a primary link or date for that one.
- Background: EDUCAUSE notes that larger services strip EXIF or reconstitute avatars as new images, which is why these failures stood out. https://er.educause.edu/articles/2021/6/privacy-implications-of-exif-data
- Implication for FLS: the planned picture will be shown to anonymous viewers on a later public profile for job seeking, so a retained GPS tag is a direct home-location leak. The org logo's "keep EXIF" reasoning does not apply. Re-encoding at upload is the standard fix and also normalises the file (and it can resize to bounded sizes for avatars, answering the idea's open resize question without a thumbnail library: Pillow alone can do it). Orientation: strip EXIF only after applying the orientation tag (`ImageOps.exif_transpose`), otherwise phone portraits come out sideways. This last point is general Pillow practice, not from the archive.
- Also scrub existing files if the policy is ever added late: Partiful had to do a retroactive pass.

### 2.2 ImageTragick (CVE-2016-3714)

- A shell command injection in ImageMagick delegates, triggered by a crafted file uploaded to any site that resizes avatars with ImageMagick; actively exploited within days; extension renaming was enough to get a crafted file past naive checks. https://www.theregister.com/2016/05/03/imagemagick/ and CERT https://kb.cert.org/vuls/id/250519 and Cloudflare https://blog.cloudflare.com/inside-imagetragick-the-real-payloads-being-used-to-hack-websites-2
- Implication: FLS uses Pillow in-process, not ImageMagick, so that specific class does not apply; the lessons that do are (a) decide format from decoded bytes, not extension or `Content-Type` (already the logo validator's approach), (b) do not shell out to image tools (no thumbnail binary), (c) re-encode to a known format so untrusted bytes never reach a downstream tool or a browser. Pillow has had its own CVEs over time, so keep it patched; I did not research specific Pillow CVEs here.

### 2.3 Decompression bombs

Covered by the decode guard (section 1.1). Pillow documents the two-band behaviour and the `MAX_IMAGE_PIXELS` default; FLS keeps the default and escalates the warning. A small file with huge declared dimensions is the avatar-specific risk: the dimension cap must be checked from the header before a full decode or resize. Note the logo validator's 4000 px cap is applied after `verify()`, which is acceptable because the guard already escalated the bomb warning first.

### 2.4 Signed URL cache-busting

Covered by section 1.3. Outside FLS, the same effect is documented by the DigitalOcean community (https://www.digitalocean.com/community/questions/presigned-urls-vs-spaces-cdn-can-i-get-both-private-access-and-edge-caching) and Advanced Web Machinery's write-up of rounding the signing time so repeated renders produce the same URL (https://advancedweb.hu/cacheable-s3-signed-urls/). Gravatar and GitHub serve avatars from public, identifier-keyed, cacheable URLs for exactly this reason (see `research_public_vs_signed_logos.md` section 4); the owner's signed-URL answer deliberately goes the other way for privacy, which means paying the cache cost.

## 3. What to carry into the spec (summary)

1. Validate with `check_logo_safety`-style layering: extension, declared size, bounded read, `verify()` plus second open under `bomb_warnings_as_errors()` and `truncated_images_rejected()`, format allowlist, dimension cap. Split into a shared "is this a safe image" function and an upload-only rule so the serve/render side can reuse it. Do not copy the logo's "EXIF kept" decision.
2. Re-encode (strip EXIF after orienting, bound dimensions, produce one or two fixed sizes) before storing; reject HEIC with a helpful message.
3. New alias in `user_uploads`' bucket with its own purpose; key `.../{user_id}/...` prefixed by the user; extension chosen by the server; add to `SIGNED_URL_PURPOSES`, `build_storages()`, base `STORAGES`; do not touch `_OVERWRITE_PURPOSES`. Fixed output format means the key can be stable per user, but because the alias does not overwrite, replace needs the `QuestionAnswerFile.save()` pattern (read previous name through `_base_manager`, delete after save).
4. Erasure on user delete must be explicit code and tested; Django will not delete the object.
5. Signed URLs: record the cost (no browser cache, new URL each render), pick a TTL, consider caching the URL in Django's cache per user for a short TTL to stabilise it, and confirm what a deactivated user's old thread still shows (answer: keep the picture).
6. Consumers (avatar template) must tolerate a missing file and an invalid file and fall back to initials without a 500 (QA of the logo proved the pattern).
7. Form UX: Remove and Replace controls with real tap targets, a client-side size check that actually blocks submit, and a server error under Django's global upload cap so the user sees a field error, not a bare 400.
8. Do not add scanning or moderation seams.

status: ok · reason: spec archive and web incidents reviewed; git log not available with the tools given
