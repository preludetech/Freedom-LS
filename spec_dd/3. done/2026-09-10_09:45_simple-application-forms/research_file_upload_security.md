# Research: file upload security for application forms

Scope: everything between "the applicant picked a file" and "a reviewer safely opens it". The five
decisions in the task brief (admin-only review, quarantine seam with no shipped scanner, deletable by
design, replace-deletes-old, `user_uploads` storage alias) are taken as given and not re-argued below.

Vocabulary used here: `CourseApplication`, `FormProgress` (the sitting), `QuestionAnswer` (one answer
within a sitting), `FormQuestion` / `QuestionType` (`form_engine/enums.py:11`, `form_engine/schema.py:13`).
A file answer needs a new `QuestionType.FILE` and a file-carrying field on `QuestionAnswer` — that
field does not exist yet (today `QuestionAnswer` has only `selected_options` and `text_answer`,
`freedom_ls/form_engine/models.py:572`). This research treats "the upload" as living on that answer
row; the plan is free to choose the exact field/model shape, but the checks below assume something
identifiable as *one answer's file, with a scan state* exists.

---

## 1. Validation on the way in

Order matters because each check is there to avoid doing the next, more expensive one on garbage:

1. **Extension allowlist** (`FileExtensionValidator`, cheap, checked first). This is a UX filter, not
   a security boundary — `freedom_ls/organisations/validators.py:1-9` says so explicitly for logos,
   and the same is true here: a `.png` extension proves nothing about the bytes behind it.
2. **Declared size** (`UploadedFile.size`), checked *before* reading the body into memory — mirrors
   `validate_organisation_logo`'s `size = file.size or 0` check ahead of any read
   (`freedom_ls/organisations/validators.py:114-122`).
3. **Real size**, bounded read: read at most `MAX_BYTES + 1` bytes so an uploaded file that lies about
   its own size (or a handle with no size at all) still cannot be pulled into memory unbounded
   (`organisations/validators.py:129`, same pattern).
4. **Magic bytes / real type**, decisive check:
   - **JPEG/PNG**: `Image.open(io.BytesIO(raw)).verify()` then a second `Image.open()` for
     dimensions/format, exactly `check_logo_safety` (`organisations/validators.py:56-102`), reused
     for the ID/passport allowlist (`{"JPEG", "PNG"}` — see §6 for why WebP is dropped here).
   - **PDF**: no Pillow support. Check the first bytes for the PDF magic number (`b"%PDF-"`) by hand.
     This is a five-byte comparison, not a library.
5. **Re-encode** (images only — see §2). PDF has no equivalent step; that gap is named plainly in §5.

**Why both browser-supplied `Content-Type` and the original filename are untrusted:** the
`Content-Type` header is whatever the browser's file picker guessed from the extension on the
applicant's own machine, sent unverified — the applicant's browser is not a party FLS has any reason
to trust, and OWASP's File Upload Cheat Sheet says the same: never trust it, verify by content
instead. The original filename is equally applicant-controlled free text; interpolating it into a
storage key is exactly the path-traversal/overwrite vector `organisations/models.py:20-32`'s
`_logo_upload_path` docstring calls out and refuses to do (see §5, path traversal).

**Is a new dependency (`python-magic`) warranted? No — decisively.** Two reasons:

- For the image half of the allowlist, Pillow is already a hard dependency of this codebase and
  `check_logo_safety` already does a *stronger* check than `python-magic` would: `python-magic`
  reads a signature and returns a MIME guess, but does not decode the file, so a JPEG with a valid
  header and a corrupted body still passes it. Pillow's `.verify()` + full re-decode (needed anyway
  for re-encoding, §2) subsumes what `python-magic` would add and catches more.
- For the PDF half, `python-magic` gives back `application/pdf` from the same five magic bytes a
  hand-rolled check reads directly — no dependency earns its keep for a five-byte comparison, and
  `python-magic` additionally requires the system `libmagic` shared library, an OS-level dependency
  this codebase carries nowhere else. FLS's own convention (CLAUDE.md, and the shape of every
  existing validator in this tree) is to avoid a dependency that is not carrying real weight.
- Neither `python-magic` nor Pillow inspects a PDF's internal object streams for a payload — see the
  PDF gap named in §5. A new dependency would not close that gap; only a scanner (the quarantine
  seam) does.

Pillow + a hand-rolled PDF header check is enough. Sources: [OWASP File Upload Cheat
Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) (allow-list types,
verify by content not by header or extension).

---

## 2. EXIF

A phone photo of an ID carries GPS coordinates (where the applicant was standing), the device make/model,
and sometimes a thumbnail. FLS should strip all of it, unconditionally, for every image upload in this
feature — there is no "corporate asset" exception here the way there is for `Organisation.logo`
(`organisations/validators.py:105-112` deliberately keeps EXIF on a logo because it is admin-uploaded
and re-encoding a transparent WebP risks a visible regression; neither applies to an ID photo: this is
personal data from an untrusted source, not a curated brand asset, and there is no transparency to
protect).

**How:** re-encoding is the mechanism, not a metadata-only strip. Decode with Pillow
(`Image.open(io.BytesIO(raw))`), then `img.save(buf, format=...)` **without** passing an `exif=`
argument — Pillow does not carry EXIF forward on save unless the caller explicitly re-attaches it, so a
plain re-encode already drops it (confirmed by the general practice write-ups, e.g.
[Removing Exif data from images in Django](https://www.gyford.com/phil/writing/2021/10/05/removing-exif-images-django/)).
A metadata-only strip (rewrit the file's EXIF block, leave the pixel data byte-identical) is not the
right choice even though it exists, for the reason below.

**Re-encoding is also the right move for a second, independent reason:** it is the same operation that
neutralises a whole class of malformed-image attacks. `check_logo_safety`'s docstring is explicit that a
header can parse cleanly over a truncated or crafted body, and that decoding the whole stream (not just
the header) is what catches that (`organisations/validators.py:79-84`). A metadata-only EXIF strip
never touches the pixel stream and so buys none of that protection; a full re-encode forces a genuine
decode of the entire image and re-emits fresh, known-good bytes. One operation buys both goals.

**Trade against fidelity:** re-encoding a JPEG at even a high quality setting (recommend quality ≈90)
discards some detail through re-compression, and re-encoding downsamples nothing but does re-quantise.
For a document a reviewer must *read* — text, a photo, a barcode — this is not a real cost: quality 90
JPEG re-encoding is well past the threshold where a human eye reading a passport page notices anything.
Re-encoding is not appropriate for forensic use (verifying the image was not itself doctored before
upload), but that is not what FLS's review step does, and the June predecessor design never claimed it
either. PNG re-encodes losslessly, so there is no fidelity question there at all. This is a real,
acceptable trade, not a free one — name it as such rather than pretending re-encoding is costless.

**PDF has no equivalent.** A PDF can carry an XMP metadata block with the same class of information
(GPS, author, producer software); FLS has no PDF-writing library in this tree and adding one solely to
strip metadata is the same "unwarranted dependency" call as §1 — flag this as an accepted residual
leak for the PDF path, not a solved problem.

---

## 3. The quarantine seam, designed concretely

**States:** `PENDING` (default, set the moment bytes are stored) → `CLEAN` or `REJECTED`. Three states,
not more — a `FAILED`/error state invites exactly the "state nothing ever advances" trap the brief warns
against; a scan that errors should leave the row at `PENDING` (still blocked, retryable) rather than
invent a fourth bucket nothing is designed to drain.

**Who transitions them:**
- Applicant upload → `PENDING`. Immediate, on the upload request itself, independent of whether the
  application has been submitted yet.
- The scan hook (see below) → `PENDING → CLEAN` or `PENDING → REJECTED`.
- A superuser, through an admin action → either direction, as a manual override (see below). Admin
  actions are logged (Django's `LogEntry`), so a manual clearance is auditable by construction.
- Nothing ever moves a file *out of* `CLEAN` or `REJECTED` automatically. A replaced upload does not
  reuse the row's state — decision #4 (replacing deletes the old object) means a new upload is a new
  `PENDING` row from scratch, never a re-scan of the same key.

**What the applicant sees while pending:** nothing scan-related. The applicant's own check-your-answers
page shows "file uploaded: `<original filename as they typed it>`" and nothing else — scan state has no
action for the applicant to take and no reason to be shown to them. This also means:

**An application can be submitted with an unscanned (`PENDING`) upload — yes, deliberately.** Gating
submission on scan completion would mean a stock FLS install (no scanner wired) could never accept a
single application, which is a worse outcome than shipping a review queue full of `PENDING` files. The
one-way submit rule (idea.md: submission is one-way until the review spec's needs-changes round trip)
is unaffected by scan state — scanning is a reviewer-side concern, not an applicant-side gate.

**What the reviewer sees:** mirror `GeneratedReportAdmin.download()` exactly
(`freedom_ls/reports/admin.py:101-108`) — the changelist/detail view renders a download link only when
the file is `CLEAN`; anything `PENDING` or `REJECTED` renders plain text ("Pending scan" /
"Rejected — not available") with no link at all. The download *view* itself must independently re-check
`scan_state == CLEAN` and 404 otherwise (§4) — the absent link is a UI nicety, not the control.

**FLS ships no scanner — so what marks a file clean in a stock install?** Plainly: **a superuser,
manually, through a logged per-object admin action.** Nothing else. Recommend the pluggable seam follow
the house pattern (`COURSE_ACCESS_BACKEND` — `freedom_ls/course_access/config.py`,
`freedom_ls/course_access/loader.py`) exactly:

- A dotted-path setting (e.g. `FILE_SCAN_BACKEND`) resolved once via `import_string`, the same
  `AppSettings`/`Setting` machinery as `CourseAccessConfig` (`freedom_ls/base/app_settings.py`).
- FLS ships a default backend that is a **no-op that never marks anything clean** — it must not
  auto-clear, because an auto-clearing "default" scanner is worse than none: it would silently make
  every install believe files are scanned when they are not. This is the one place where "ship a
  working default" is the wrong instinct; the safe default is inertia, not leniency.
- A management command (e.g. `scan_pending_uploads`) iterates `PENDING` rows and calls the configured
  backend, the same shape as any of this codebase's background-task entry points
  (`freedom_ls/reports/tasks.py`, `freedom_ls/webhooks/events.py`: a thin wrapper delegating to a plain
  function, callable from a task queue or a cron-scheduled invocation — no request context, so it takes
  primitives and re-filters explicitly, following the same rule those two modules document). A
  downstream project wires a real scanner by pointing `FILE_SCAN_BACKEND` at a class that shells out to
  `clamdscan`, or calls a cloud scanning API, and scheduling the management command (cron, a periodic
  task, a queue consumer) — FLS supplies the seam and the command, not the network call.
- Because the default backend never advances anything, add a **system check** in the same family as
  `course_access/checks.py`'s `W001` (`check_preview_overrides_disabled_in_production`,
  `Tags.security`): warn when `DEBUG` is `False` and `FILE_SCAN_BACKEND` is still the shipped no-op,
  naming plainly that uploads will sit `PENDING` forever except for manual admin clearance. This is not
  an error — a deployment that has deliberately chosen manual-only clearance is a legitimate, if
  unusual, choice — but it must not pass silently.
- The manual escape hatch (an admin action, "Mark as clean without scanning" / "Reject") is not a
  fallback for the lazy case — it is the load-bearing default for every stock install until a scanner is
  wired, and it must exist from day one or the feature is unusable without one.

---

## 4. Serving

Mirror `download_report_view` (`freedom_ls/reports/views.py:109-132`) closely; it is the working FLS
precedent for exactly this shape (private file, streamed, permission-checked, admin-only):

```python
def download_report_view(request: HttpRequest, object_id: str) -> FileResponse:
    """Stream a ready report's PDF as a private, never-cached attachment."""
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort__organisation"), pk=object_id
    )
    if not can_view_cohort(request.user, report.cohort):
        raise PermissionDenied
    if report.status != GeneratedReport.STATUS_READY or not report.file:
        raise Http404
    ...
    try:
        file_handle = report.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(file_handle, as_attachment=True, filename=filename)
    response["Cache-Control"] = "private, no-store, must-revalidate"
    return response
```

An application-file view keeps every line of that shape:

- **Who may call it:** wired through `get_urls()`/`admin_site.admin_view(...)` the same way
  `GeneratedReportAdmin.get_urls()` hangs `download_report_view` off the admin namespace
  (`freedom_ls/reports/admin.py:114-134`) — never a public `urls.py`. `admin_view()` only guarantees
  staff status (the comment on `download_report_view` says this explicitly); decision #1 is narrower
  than staff — **superuser only** — so the view must check `request.user.is_superuser` itself and raise
  `PermissionDenied` otherwise, the same "gate is separate and mandatory" pattern
  `generate_report_view` uses for cohort visibility.
- **What it checks, in order:** `get_object_or_404` for the answer/upload row → superuser check →
  **`scan_state != CLEAN` → `Http404`** (this is the one line with no equivalent in
  `download_report_view` — see below) → file handle open, `FileNotFoundError` → `Http404`.
- **How it streams:** `FileResponse(file_handle, as_attachment=True, filename=...)`, identical.
  `filename` must not be built from the applicant-supplied original filename verbatim — derive it
  server-side (e.g. from the application/course/question, with the extension taken from the value
  determined at *upload* time by the magic-byte check, never re-read from user input at download time),
  the same reasoning `download_report_view`'s own `slugify(...)` call embodies.
- **Headers:** `Cache-Control: private, no-store, must-revalidate`, identical. `X-Content-Type-Options:
  nosniff` is already set globally by `SECURE_CONTENT_TYPE_NOSNIFF = True`
  (`config/settings_prod.py:44`), so nothing extra is needed on this response specifically — worth
  naming because it is one of the controls in §5, not because it needs re-adding here.

**Where it must differ:** the scan-state gate. `download_report_view` has nothing equivalent because a
`GeneratedReport` is server-generated, never attacker-supplied — there is nothing to quarantine. An
application file is the one case in this codebase where "the row says the file is ready" is not enough;
"ready" must mean `READY` *and* `CLEAN`, checked every time, not just at upload time.

**Why a signed storage URL is the wrong choice, even though `user_uploads` supports one:**
`user_uploads` is in `SIGNED_URL_PURPOSES` (`freedom_ls/deployment/storage.py:28-30`, alongside
`course_media` and `reports`), so a signed, time-limited direct-to-bucket URL is mechanically available.
It is wrong here for reasons specific to this feature, not a blanket rule against signed URLs elsewhere:

1. **It cannot carry the scan-state check.** A signed URL is minted once and is valid for its whole
   expiry window (`AWS_QUERYSTRING_EXPIRE`, default 3600s). If a background scan later reclassifies the
   file as `REJECTED` *after* a URL was minted but before it expires, the raw bytes are still fetchable
   for the rest of that window — the check happens at mint time, not at fetch time, and this feature's
   whole point is that the check must happen at fetch time.
2. **It cannot express "superusers only, re-checked every time."** A signed URL is a bearer token:
   whoever holds the link gets the bytes, no session, no re-authentication, no re-run of
   `is_superuser`. It can leak through a browser history entry, a forwarded email, a proxy log — none of
   which a Django-streamed, session-checked view is exposed to.
3. `download_report_view` already answered this question for the sibling alias in the same bucket
   (`reports`, same `SIGNED_URL_PURPOSES` membership) by streaming through Django rather than signing —
   this feature is the same shape of file in the same bucket and should not disagree with that existing
   answer.

Streaming through an admin-gated Django view, re-checking permission and scan state on every request, is
the only choice that can express "not until cleared, and only a superuser, every single time."

---

## 5. Threats, concretely

| Threat | Real for this deployment shape? | Control |
|---|---|---|
| IDOR on a file belonging to another applicant | Not applicable to applicants — they have no route to the download view at all; it is admin-only (`admin_view` staff gate). Not applicable to reviewers either: decision #1 is "superusers only," and a superuser is, by definition, meant to see every application. There is no narrower reviewer role yet for a per-application visibility check to be missing from. | Structural: the view is unreachable except through the admin, by a superuser. |
| Applicant replacing a file after submission | **Real, and easy to miss.** The read-only-once-submitted rule lives in the `course_applications` view layer, not the model (idea.md: "the read-only-once-submitted check belongs in the `course_applications` view"). A file-upload POST is one more entry point into that gate — if it is wired as a separate endpoint (e.g. an HTMX file-upload URL distinct from the page-POST flow), it is easy to build without threading the same `form_progress.completed_time is not None` check the other question types get. | Must explicitly re-run the same read-only check before accepting a file POST — not automatic, must be built. |
| Path traversal or key collision via the original filename | Controlled, if the upload path follows `organisations/models.py:20-32`'s `_logo_upload_path` precedent: derive the storage key from the owning row's pk/uuid and a server-determined extension, never interpolate the applicant's filename. (The precedent *not* to copy is `content_engine/models/files.py:13-20`'s `file_upload_handler`, which does interpolate the filename stem — safe there only because the uploader is a trusted content author, not an applicant.) | Real if built carelessly, fully closed by pk/uuid-derived keys — Django's storage backends also reject `..` path components as defence in depth. |
| A zip bomb / decompression bomb | Zip bomb: not applicable — the allowlist (JPEG/PNG/PDF) never accepts an archive format, so there is no route in. Decompression bomb (an image with an absurd pixel count): real, and already solved by reusing `base/images.py`'s `bomb_warnings_as_errors()` / `BOMB_FAILURES` escalation, the same code `check_logo_safety` uses. | Reuse existing image-bomb guard; archive formats excluded by the allowlist. |
| An SVG or HTML file with embedded script, opened by an admin | Real in principle for an admin-facing, session-authenticated surface. Two independent controls: SVG/HTML are not in the allowlist for an ID/passport scan (magic-byte check rejects a renamed SVG regardless of extension); and even a file that slipped through is served `as_attachment=True` with `X-Content-Type-Options: nosniff` already on (`SECURE_CONTENT_TYPE_NOSNIFF = True`), which stops a browser from sniffing an attachment into rendering as HTML. | Allowlist is the primary control; attachment + nosniff is defence in depth. |
| A PDF with an embedded payload | **Real, and unmitigated by FLS's own validation.** Neither the magic-byte header check nor Pillow parses PDF object streams — nothing here can see embedded JavaScript or a malformed-object exploit inside an otherwise well-formed PDF. This is exactly what the quarantine scanner exists for; in a stock install with the no-op backend (§3), this risk rests entirely on the superuser choosing to open it having reason to trust the source. State this as a gap, not a "consideration." | None from FLS's own validation; the quarantine seam (a real scanner) is the only control, and FLS ships none. |
| Content-sniffing turning a download into an XSS in the admin's browser | Same controls as the SVG/HTML row: `as_attachment=True` plus `X-Content-Type-Options: nosniff`. Real control, not theatre — both are actually set. | `FileResponse(as_attachment=True)` + `SECURE_CONTENT_TYPE_NOSNIFF`. |
| An upload to a question that is not a file question | Real, same shape as the pre-existing, not-fixed defect idea.md names for options ("submitted option ids are not checked against the question being answered"). The answer-saving path must check `question.type == QuestionType.FILE` before accepting a file part of the POST and reject (422) a mismatch outright — do not silently drop it. | Must be built; not automatic from the existing `QuestionAnswer` machinery. |
| The file surviving in the bucket after its row is deleted | **Real, and this feature is the first place in FLS that needs to solve it.** Django never deletes the underlying storage object when a model row referencing a `FileField`/`ImageField` is deleted — `Organisation.save()` only handles the *replace* case, by explicit `storage.delete(previous)` (`organisations/models.py:116-134`); nothing in this codebase yet handles the *delete-the-row* case, because `GeneratedReport` and `Organisation` are rarely hard-deleted. Decision #3 ("deletable by design") means deleting a `CourseApplication` (or its `FormProgress`, or one `QuestionAnswer`) must not leave the ID scan sitting in the bucket, or "deletable by design" is false in practice. Neither the admin's `delete()` nor a queryset `.delete()` calls `FieldFile.delete()` automatically. | Must be built: a `pre_delete`/`post_delete` signal or an explicit `delete()` override that calls `file_answer.delete(save=False)` wherever the answer, sitting, or application can be removed. Nothing does this today by default. |

---

## 6. Limits

**Max file size: 10 MB per file**, checked in FLS's own validator (a `check_id_scan_safety`-shaped
function mirroring `check_logo_safety`) — well above a typical modern phone photo (2–8 MB) or a
flatbed-scanned passport page as PDF (usually well under 5 MB), without leaving room for a
decompression-bomb-scale absurdity.

**But: this conflicts with an existing project-wide setting and must be reconciled, not ignored.**
`config/settings_prod.py:53-54` already sets both `DATA_UPLOAD_MAX_MEMORY_SIZE` and
`FILE_UPLOAD_MAX_MEMORY_SIZE` to `5_242_880` (5 MB) — **below** a sensible ID-scan limit. These are
whole-request/whole-file ceilings enforced by Django itself before any view code runs; Django has no
per-view override for them. As it stands today, production would reject a perfectly normal 6 MB phone
photo before FLS's own validator ever sees it. Concrete recommendation: raise both to **8 MB** in
`settings_prod.py` (with a comment naming this feature as the reason), and set the FLS validator's own
per-file `MAX_BYTES` to **6 MB**, leaving headroom under the 8 MB global ceiling for the rest of the
form POST body (CSRF token, other answers, multipart boundaries). Do not raise the global setting to
exactly 10 MB and call it done — the global cap covers the *whole* request, not just this one field.

**Allowed types: JPEG, PNG, PDF.** No WebP (unlike the logo validator's allowlist) — a camera or a flatbed
scanner never natively produces WebP, so including it only widens the sniffed-format allowlist for no
real applicant benefit. No HEIC/HEIF — modern iPhones default to it, but Pillow has no built-in decoder
for it (would need `pillow-heif`, another dependency for the same reason `python-magic` was declined in
§1); reject it explicitly with a message telling the applicant to choose "Most Compatible" / JPEG in
their camera's format setting, rather than adding a dependency to decode Apple's native format.

**Where each is enforced:**
- **Django setting** (`config/settings_prod.py`): `DATA_UPLOAD_MAX_MEMORY_SIZE` /
  `FILE_UPLOAD_MAX_MEMORY_SIZE` — the outer, whole-request backstop (see above).
- **FLS validator** (module-level constants next to the check function, mirroring
  `organisations/validators.py`'s `ALLOWED_EXTENSIONS` / `MAX_BYTES` / `ALLOWED_FORMATS`): the real,
  user-facing size and type limits.
- **Per-question config**: none, deliberately. `FormQuestion` has no file-specific config field today,
  and there is exactly one use case (ID/passport) with no evidence a course author needs a different
  size or type allowlist per form — building that configurability now would be building functionality
  nobody has asked for (CLAUDE.md).
- **Storage**: no enforcement at the storage layer — S3/R2 accepts whatever bytes it is handed up to its
  own service limits, which are irrelevant at this scale. All enforcement is application-side, matching
  the existing logo validator.

**What Django does when `DATA_UPLOAD_MAX_MEMORY_SIZE` is exceeded:** it raises `RequestDataTooBig`, a
subclass of `SuspiciousOperation`, the moment the declared `Content-Length` (or the actual body size)
crosses the limit — before any view code, and therefore before FLS's own validator can produce a
friendly, in-form error. Uncaught, this surfaces as a generic HTTP 400 ("Bad Request") page, not a
validation message attached to the file field. This is exactly why the FLS validator's own limit (6 MB)
must sit comfortably *below* the Django-level ceiling (8 MB): a file the applicant should be told to
resize gets a proper 422/form error from FLS's own check; only a request that is grossly oversized (well
past anything a real ID photo would be) ever reaches Django's blunter 400. Source: [Django
`RequestDataTooBig`
behaviour](https://code.djangoproject.com/ticket/29427) (an unhandled `SuspiciousOperation` becomes a
400 response).

---

## Sources

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
  — allow-list extensions, verify by content not by header, rename on upload, quarantine/scan.
- [Django `FileResponse` / `Content-Disposition` docs](https://docs.djangoproject.com/en/stable/ref/request-response/)
  — `as_attachment=True` behaviour.
- [Django ticket #29427 — `RequestDataTooBig` and unhandled `SuspiciousOperation`](https://code.djangoproject.com/ticket/29427)
- [Removing Exif data from images in Django](https://www.gyford.com/phil/writing/2021/10/05/removing-exif-images-django/)
  — re-encoding through Pillow drops EXIF by default.

---

status: ok
