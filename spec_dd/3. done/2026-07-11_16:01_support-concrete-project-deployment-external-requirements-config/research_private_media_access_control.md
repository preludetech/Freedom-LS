# Research: Private media on R2 — one private bucket + signed URLs

## Summary

The R2 storage decision hinges on one question: **is course media access-controlled
today, or not?** The sibling doc `research_cloudflare_r2_django_storages.md` (§2, §7)
recommends a *public bucket + custom domain* on the premise that *"FLS already
access-controls media at the Django view layer."* That premise is **wrong for the media
bytes themselves**. FLS gates course *pages*, never the *files*. A public bucket would
therefore make every application-gated course's PDFs and images permanently, publicly
retrievable by anyone with the URL.

Decision: **one private R2 bucket, served via django-storages signed URLs**
(`querystring_auth=True`, no `custom_domain`). No public bucket. This closes the leak with
zero application-code changes. The strictly-stronger per-request view-proxy gate is
recorded as deferred future work, not built here.

## 1. The gap — view-layer gating protects pages, not bytes

- **One media field, no privacy flag.** Every uploaded course asset — images, documents,
  video, audio — is a single `content_engine.File.file` `FileField`
  (`freedom_ls/content_engine/models.py:584`). The `File` model has no
  `is_public`/`is_private`/visibility field; its only fields are `file`, `file_type`,
  `file_path`, `original_filename`, `mime_type`, and the `site` FK. Upload paths are flat
  and guessable — `content_engine/{stem}{pk}{ext}` (`file_upload_handler`,
  `content_engine/models.py:564-571`).

- **Media is only ever a direct `file.url`.** It is never streamed through a
  permission-checked view. Every reference renders the raw storage URL:
  - `content_engine/templates/cotton/picture.html:35,95` — `<img src="{{ file_obj.file.url }}">`
  - `content_engine/templates/cotton/card.html:32` — `<img src="{{ file_obj.file.url }}">`
  - `content_engine/templates/cotton/file-download.html:17` — `href="{{ file_obj.file.url }}"`
  - `content_engine/templates/cotton/pdf-embed.html:21` — `src="{{ file_obj.file.url }}"`

  Searches for `FileResponse`, `sendfile`, `X-Accel`, `StreamingHttpResponse`, or
  `django.views.static` in views find **nothing** for media. `nginx.conf:10-13` serves
  `/media/` with a bare `alias` and carries the comment
  *"NOTE: This is not secure - the media files are public."*

- **Course access gates pages, not files.** The `COURSE_ACCESS_BACKEND` seam
  (`freedom_ls/course_access/backends.py`) returns a `CourseAccessDecision` with
  `can_access_content`, and the `student_interface` views (`view_course_item`,
  `course_home`, `course_detail`, `initiate_course_access`) redirect unregistered learners
  away from the **player pages**. The existing **application-gating** backend
  (`freedom_ls/course_applications/backends.py`, `access_type == "application_gated"`)
  returns `can_access_content=False` until the applicant is registered. None of this ever
  runs when a browser fetches `file.url` — the media bytes bypass `get_access()` entirely.

**Consequence:** with a public bucket + custom domain (stable, unauthenticated URLs), a
gated course's PDF/image is retrievable by anyone who knows or guesses its flat,
`pk`-based path — regardless of enrollment or application status. That is the exact leak
this work must avoid.

## 2. Why one private bucket (not two)

- **Static is already handled without object storage.** CSS/JS ship via WhiteNoise
  (`CompressedManifestStaticFilesStorage`, `config/settings_prod.py:220-222`); logos are
  static assets referenced by `static()` (`HEADER_LOGO_STATIC_PATH` /
  `EMAIL_LOGO_STATIC_PATH`, `site_aware_models/config.py`). Nothing "always public" needs
  a public bucket.
- **There is no per-file public/private classification** on the `File` model, and no code
  path that distinguishes a public course thumbnail from a gated internal PDF. Routing
  files to different buckets would require introducing that classification plus routing
  logic — a new, larger feature, and unrequested. Per project conventions, don't build
  functionality that isn't asked for.
- **Public course thumbnails still work** from a private bucket: on a public catalogue
  page django-storages simply renders a signed URL for the card image. It is not
  edge-cacheable, but it is correct and requires no new modelling.

So a **single private bucket** is the right shape today. A public bucket only becomes
worthwhile alongside a future per-file public/private feature.

## 3. Signed-URL mechanism & trade-offs

- **How it works.** With `storages.backends.s3.S3Storage`, when `querystring_auth=True`
  (the default) and no `custom_domain` is set, `File.file.url` returns a **presigned GET
  URL** carrying `X-Amz-Signature`/`X-Amz-Expires`. The bucket stays private and
  unlistable, so **no permanent public URL exists** for any object. This is the default
  `S3Storage` behaviour — no application-code changes, no ACLs (R2 has none anyway).
- **Trade-offs (accepted):**
  - Signed URLs are **not edge-cacheable** by Cloudflare/browsers (they change per render)
    and are ugly/non-stable in HTML.
  - A URL, *once rendered into a page*, is **shareable until it expires**. Default expiry
    is `AWS_QUERYSTRING_EXPIRE = 3600` (1 hour). This is acceptable for an LMS.
  - **Long video / large downloads:** a range request issued after the signature expires
    can `403`. If media playback longer than the expiry is expected, raise
    `AWS_QUERYSTRING_EXPIRE`.

## 4. Honest limits — what signing does *not* do

Signing does **not** re-check `can_access_content` on each fetch. Privacy comes from the
combination of:

1. the **bucket being private** (no object is reachable without a live signature), and
2. the **gated page being the only place `file.url` is rendered** (an unregistered learner
   never reaches the player, so never receives a signed URL).

The strictly-stronger option is a **view-proxy hard gate**: serve every media byte through
a Django view that re-runs `can_access_content` per request (streaming the object, or
redirecting to a freshly-minted short-lived signed URL). That gives true per-request
enforcement and defeats URL-sharing, but it is a new feature — a new view + URL, permission
wiring, template changes across all file cotton components, and video range-request
handling. It is **deferred to its own spec**, not built in this config-wiring work.

## 5. Correction to `research_cloudflare_r2_django_storages.md`

That doc's §2 ("How to actually make media public") and §7 recommend approach **A (public
bucket + custom domain)** on the stated ground that *"FLS already gates media access
through the LMS's own auth … access control happens at the Django view layer, not the
storage layer."* Per §1 above, that ground is **incorrect**: the view layer gates pages,
not the media bytes. The correct default is therefore approach **B (private bucket + signed
URLs)**. `custom_domain` + `querystring_auth=False` (public serving) remains **available**
for a deployment that deliberately opts into it, but must be **off by default**.

## 6. Resulting config surface (defaults)

| Setting | Default | Effect |
|---|---|---|
| `AWS_QUERYSTRING_AUTH` | `True` | Signed, private, time-limited `file.url` (the default) |
| `AWS_S3_CUSTOM_DOMAIN` | unset | Public custom-domain serving is opt-in only |
| `AWS_QUERYSTRING_EXPIRE` | `3600` | Raise if long media outlives the signature window |

All other R2-correctness items (drop `AWS_DEFAULT_ACL`, `region_name="auto"`, the
mandatory boto3 `client_config` checksum workaround, keep `signature_version="s3v4"`) are
unchanged from `research_cloudflare_r2_django_storages.md` §6/§7.

## References

- `research_cloudflare_r2_django_storages.md` (this spec folder) — R2/django-storages
  specifics; §2/§7 public-vs-private conclusion corrected here.
- Codebase evidence: `content_engine/models.py:564-571,584`; cotton components
  `picture.html`, `card.html`, `file-download.html`, `pdf-embed.html`; `nginx.conf:10-13`;
  `course_access/backends.py`; `course_applications/backends.py`;
  `config/settings_prod.py:166-223`.
- https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html (`querystring_auth`, `querystring_expire`, `custom_domain`)

status: ok
