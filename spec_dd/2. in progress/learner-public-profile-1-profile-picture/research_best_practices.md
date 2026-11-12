# Research: best practices for user-uploaded profile pictures (Django + S3-compatible storage)

Scope: the `best_practices` topic for spec `learner-public-profile-1-profile-picture`. Settled inputs: private bucket, short-lived signed URLs, Pillow installed, no thumbnail library, deactivated users keep their picture, superseded files are deleted.

Sourcing note: the points below come from the cited documents as I know them. I did not re-fetch the pages in this run. Numeric recommendations (sizes, expiry) are conventional choices, flagged as "suggested", not mandated by a source. Verify the cited pages before quoting them in the spec.

## 1. Accepted formats

- Allow-list only: JPEG, PNG, WebP. GIF is optional; accept it only if you flatten it to a single frame. Reject everything else, including SVG, HEIC and AVIF (browser support and Pillow plugins are uneven).
- Allow-list the types, never block-list. OWASP: "List allowed extensions. Only allow safe and critical extensions for business functionality", and validate content type and file signature, not only the extension.
- Decide the type by having Pillow decode the file (`Image.open(...).format`), not from the extension or the client's `Content-Type` header, both of which the client controls.

## 2. Size and pixel limits (suggested)

- Max upload size: 5 MB is typical for avatars (2 to 10 MB is the common range). Enforce in two places: `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` are not per-file limits, so check `UploadedFile.size` in the form `clean_*` method, and cap at the web server (nginx `client_max_body_size`).
- Max pixel dimensions on input: about 4096 x 4096, or a pixel-count cap of about 16 to 25 million. Check `image.size` after `Image.open` (this reads only the header) and before `load()`.
- Minimum dimensions: optionally 100 x 100 or similar, to avoid a pixelated avatar.
- Reuse the repo's existing logo validator and `freedom_ls/base/images.py` decode guard (see idea.md) so limits and errors stay consistent.

## 3. Re-encode and resize on upload

Re-encoding is the strongest single control. It discards anything that is not pixel data (polyglot payloads, trailing bytes, metadata, embedded scripts in odd chunks) and gives one predictable stored format.

- Square crop vs fit: avatars are displayed in circles or squares, so store a centre-cropped square. `PIL.ImageOps.fit(img, (N, N), Image.Resampling.LANCZOS)` does centre crop plus resize. Fit-with-letterbox would show bars in a round avatar. The idea says no cropping UI, so an automatic centre crop is the simple option; it can cut off heads on very wide or tall photos, which is an accepted trade-off. Never upscale: if the source is smaller than the target, do not enlarge; either reject below the minimum or crop to the largest square.
- Orientation: call `ImageOps.exif_transpose(img)` before cropping, so phone photos with an EXIF orientation tag are not rotated wrongly once EXIF is stripped.
- Target sizes (suggested): one stored size of 512 x 512 covers the header (about 32 to 40 px), chips and a public profile (about 128 to 256 px) on 2x screens. Without a thumbnail library, storing one master and letting CSS scale it is the simplest. Only add a second 128 px rendition if page weight in messaging lists matters; two renditions double the delete and key logic.
- Output format: WebP (quality about 85) is smaller, supports transparency and is universal in current browsers. JPEG (quality 85, `optimize=True`, progressive) is the conservative choice. Pick one format for all uploads. Convert modes first: `convert("RGB")` for JPEG; for PNG/WebP with alpha either keep RGBA in WebP or paste on a white background for JPEG. Palette (`P`) and CMYK images need conversion too.
- Animated GIF/WebP: take frame 0 only (do not save with `save_all`), or reject animation.
- Save into `io.BytesIO`, wrap in `ContentFile`, and store with the server-chosen name and extension matching the output format.

## 4. Stripping EXIF / GPS

- Phone photos carry GPS location, device model and timestamps. For a learner platform with young or vulnerable users this is a privacy issue, and the file may later be shown to anonymous viewers.
- Pillow's `save()` does not copy EXIF unless you pass `exif=`; for JPEG, `icc_profile` is also dropped unless passed. So re-encode from a fresh image and do not pass `exif`/`info`. For belt and braces, build a new image from pixel data (`Image.new(mode, size)` plus `putdata`, or `img.copy()` and clear `img.info`) before saving.
- Apply `exif_transpose` first (section 3) so stripping does not change apparent orientation.
- Test: upload a fixture JPEG with GPS EXIF, then assert `Image.open(stored).getexif()` is empty.

## 5. Decompression bombs and truncated files

- Pillow raises `DecompressionBombWarning` above `Image.MAX_IMAGE_PIXELS` (default about 89 million) and `DecompressionBombError` above twice that. Do not disable the limit (`MAX_IMAGE_PIXELS = None`). Treat the warning as an error in the validator (`warnings.simplefilter("error", Image.DecompressionBombWarning)` in a `catch_warnings` block) or enforce a lower explicit pixel cap by checking `image.size` before `load()`.
- Run `img.verify()` for cheap structural checks, then re-open and `load()` (verify invalidates the image object). `ImageFile.LOAD_TRUNCATED_IMAGES` must stay `False` so truncated files are rejected, which matches the existing decode guard.
- Catch specific exceptions: `Image.DecompressionBombError`, `Image.DecompressionBombWarning`, `UnidentifiedImageError`, `OSError`, `SyntaxError` (Pillow can raise it for malformed PNG chunks), and turn them into `ValidationError`.
- Django's `forms.ImageField` already calls `Image.open(...).verify()` and sets a content type, but it is not enough alone: it does not enforce your size or pixel caps or re-encode.

## 6. Content-type sniffing vs extension

- Never trust the extension or the browser-sent `Content-Type`. Django's `FileExtensionValidator` checks only the name; treat it as a first, cheap filter, not security.
- Sniff via decode: `Image.open(f).format in {"JPEG","PNG","WEBP"}`. Alternatively `python-magic`, but Pillow is already installed and is the authority on whether it can decode the file.
- After re-encoding, ignore the original filename entirely; the stored name and extension come from the server (section 8). This removes path traversal, double-extension (`avatar.jpg.php`) and Unicode-name tricks.
- On the response side, serve with the correct `Content-Type` (S3 object `ContentType` set at upload from the output format) and, for defence in depth, `X-Content-Type-Options: nosniff` on pages. With signed S3 URLs, set `ContentType` explicitly in the storage options (django-storages guesses from the name otherwise).

## 7. SVG rejection

- SVG is XML that can contain `<script>`, event handlers, external references and XXE-style entities; served from a same-origin or credentialed context it enables stored XSS. Pillow cannot open SVG, so decode-based sniffing rejects it naturally, but also do not put `svg` in any extension allow-list or accept `image/svg+xml`.
- Because everything is re-encoded to a raster format, an SVG renamed to `.png` fails the decode step. Add a test with an SVG renamed to `.png` and `.jpg`.
- A private bucket on a different origin from the app plus raster-only output reduces the blast radius further.

## 8. Key naming

- Server-generated, unguessable, never derived from user input: `profile_pictures/<user_pk or user_uuid>/<uuid4>.<ext>` (shape per the `fls-dev:file-storage` skill: user-prefixed, in the user-data bucket). The per-user prefix lets you list and erase everything for one user (GDPR erasure), and the random uuid component prevents enumeration and overwrite collisions.
- A new uuid per upload (rather than a fixed `avatar.webp`) avoids CDN/browser cache staleness on replace and avoids an overwrite race; it does mean the old key must be deleted explicitly (section 9). The idea.md says no existing purpose is reused for its overwrite behaviour, which fits: use a unique key and `file_overwrite = False` semantics.
- Prefer a non-sequential identifier in the prefix if user pks should not be revealed in signed URLs that anonymous viewers see; if the User model has no uuid field, the pk in the key is low risk since the URL is signed, but note it.
- Use `upload_to` as a callable that takes `(instance, filename)` and ignores `filename`'s base name. Django docs on `FileField.upload_to` and `Storage.get_available_name` cover this.

## 9. Deleting superseded files

- Django does not delete files when a model row changes or is deleted (since 1.3). You must do it.
- Delete only after the database change commits, with `transaction.on_commit(lambda: storage.delete(old_name))`. Deleting inside the transaction risks losing the file when the transaction rolls back, leaving the row pointing at nothing. Order: save new file, update the row, on commit delete the old file. If the new upload succeeded but the commit fails, you have an orphan new file; acceptable, or clean up in an `except` path.
- Capture the old file name (a string) before saving the new one, since the field instance changes. Delete by name through the field's storage, not through the field instance.
- Cover three paths: replace, remove-without-upload (clear the field, then delete on commit), and user deletion (a `post_delete` receiver or an erasure routine that deletes the whole `<user>/` prefix). Deactivation deletes nothing, per answers.md.
- Deletion failures (S3 outage) should not break the request: catch the specific storage exceptions and leave an orphan, or queue a retry. The project says "Don't add logging unless asked" and "avoid silent failures", so decide this explicitly in the spec; a periodic orphan sweep over the prefix is the usual backstop.
- Tests need `django_capture_on_commit_callbacks(execute=True)` (pytest-django) or `TestCase.captureOnCommitCallbacks`.

## 10. Signed URL expiry vs browser caching

- Signed URLs change on every generation (new signature and expiry), so the browser sees a new URL each page load and never reuses its cache; every avatar is re-downloaded on every page view. This is the main cost of a private bucket.
- Mitigations:
  - Sign with a time-bucketed expiry so the URL is stable within a window. django-storages signs with `AWS_QUERYSTRING_EXPIRE` (default 3600 s) and the time at signing; to get identical URLs within a window you need to round the signing time (custom storage or a cached URL, see next point).
  - Cache the generated URL in Django's cache (`cache.get_or_set(key, ..., timeout=expiry - margin)`), keyed by object name, with timeout shorter than the expiry. That yields a stable URL across requests, so browser caching works, and saves signing work (signing is local HMAC, cheap, so the main gain is the stable URL).
  - Set `CacheControl` on the object (`AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "private, max-age=86400"}`; for a per-alias setting use the storage `OPTIONS` -> `object_parameters`). Images are immutable per key (new uuid on replace), so a long max-age is safe.
- Choose expiry to match the page lifetime: minutes to an hour (django-storages default 3600 s). Too short and an open tab or a cached page breaks images; too long and a leaked URL remains usable. Because the keys are immutable and the image is low sensitivity once shown on a public profile, an expiry of 1 hour with a cached, time-bucketed URL is a sensible default (suggested).
- Pages that are cached or rendered server-side into HTML snapshots (emails, cached fragments) must not outlive the URL expiry. Do not put signed URLs in emails.
- Handle expiry in the UI: an `<img>` that 403s shows a broken image; either keep expiry comfortably longer than page staleness, or add `onerror` fallback to initials (also covers missing files, which idea.md lists as open).
- For anonymous viewers on the public page, signed URLs work without auth; the signature is the authorisation. Only the object key is hidden, so also the public page itself must be the gatekeeper for who can see which user.
- django-storages: `querystring_auth` must be true (default) for private buckets; set `custom_domain` to None (CloudFront signing is different); `signature_version="s3v4"` and `addressing_style` for S3-compatible stores; `url_protocol`/`endpoint_url` per provider.
- Alternatives (streaming via a Django view with `Cache-Control` and `ETag`) allow stable URLs and caching but cost app-server bandwidth. Already decided against in answers.md, listed for completeness.

## 11. Alt text and accessibility

- Avatar next to a visible name (message participant, table row, chip with the name): decorative, so `alt=""` (and for initials, `aria-hidden="true"`), because the name is already announced. A non-empty alt like "Photo of Jane" is redundant noise. WAI decorative-images guidance applies when the image adds no information the text lacks.
- Avatar as the only identifier (header menu button showing just the avatar): the accessible name belongs on the control (`aria-label="Account menu for Jane Doe"` or visually-hidden text), and the image itself stays `alt=""`. Alternatively give the image `alt="<full name>"` when it is the sole content of a link.
- The public profile heading: usually `alt=""` or `alt="Photo of <name>"`; use the latter only if the name is not adjacent. Do not write "profile picture of" plus the name in repeated lists.
- Initials fallback: a coloured circle with letters. Mark the letters `aria-hidden="true"` when the full name is adjacent, otherwise give the element `role="img"` and `aria-label="<full name>"`. Make sure initials and background meet WCAG 2.2 contrast (text 4.5:1 for small text; 3:1 for large text). Do not vary meaning by colour alone.
- Give `<img>` explicit `width`/`height` (avoid layout shift), `loading="lazy"` for lists, and `decoding="async"`. Keep a visible focus ring when the avatar is within a button.
- Form control: a file `<input>` with a real `<label>`, help text stating accepted types and max size (link with `aria-describedby`), errors announced via the existing form error pattern, and a "Remove picture" checkbox (Django's `ClearableFileInput` convention) or a separate button with a clear label. A current-picture preview with an empty alt next to the label. Because the project uses HTMX, return 422 for validation errors per `CLAUDE.md`.
- Deactivated users: keep the picture (settled). Missing file: render initials, using `onerror` or a safe `url` accessor that catches storage errors and returns None.

## 12. Other practical points

- One shared renderer: a single Cotton component or template tag/helper for "picture or initials" so header, messaging and chips share the choice; the model exposes a method that returns a signed URL or None (with caching, section 10). N+1 risk: signing is local, but do not hit storage per row (`exists()` calls are network calls); never call `storage.exists()` while rendering lists.
- Multipart form needs `enctype="multipart/form-data"`; validate in the form, process (re-encode) in `clean` or `save`, and save the file before commit side effects.
- Run image processing synchronously on a 512 px result; it costs tens of milliseconds, so no task queue is needed. Cap memory by checking size before decoding.
- Test list: oversize file, oversize pixels, decompression bomb, truncated image, SVG renamed, polyglot (valid image plus trailing script), EXIF GPS stripped, EXIF-rotated image upright, replace deletes old key after commit, remove deletes, rollback keeps old file, user delete removes the prefix, missing file falls back to initials.

## References

- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Django: file uploads and `FileField` / `upload_to`: https://docs.djangoproject.com/en/stable/topics/files/ and https://docs.djangoproject.com/en/stable/ref/models/fields/#filefield
- Django `ImageField` form field: https://docs.djangoproject.com/en/stable/ref/forms/fields/#imagefield
- Django `transaction.on_commit`: https://docs.djangoproject.com/en/stable/topics/db/transactions/#performing-actions-after-commit
- Django file upload settings and security notes: https://docs.djangoproject.com/en/stable/ref/settings/#file-upload-max-memory-size
- django-storages S3 backend (querystring_auth, querystring_expire, object_parameters, signature_version): https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
- Pillow `Image.MAX_IMAGE_PIXELS` / decompression bomb: https://pillow.readthedocs.io/en/stable/reference/Image.html and ImageOps.exif_transpose / fit: https://pillow.readthedocs.io/en/stable/reference/ImageOps.html
- Pillow file formats and saving options (WebP, JPEG): https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
- W3C WAI images tutorial (decorative images, functional images): https://www.w3.org/WAI/tutorials/images/
- WCAG 2.2 contrast minimum (1.4.3): https://www.w3.org/TR/WCAG22/#contrast-minimum
- MDN, SVG security / `X-Content-Type-Options`: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options

status: ok · reason: written from established knowledge; cited pages not re-fetched this run, numeric values flagged as suggested
