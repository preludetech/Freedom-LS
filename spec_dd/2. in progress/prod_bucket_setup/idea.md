# Production Object Storage — How Many Buckets, and What Goes Where

FLS runs one media bucket in production. Three different kinds of file are writing into it,
with three different access patterns and three different sensitivity levels. One of them —
cohort report PDFs containing named learners and their quiz answers — is there by accident,
because the alias that was supposed to redirect it was never declared.

This idea settles the target bucket layout before the set of file-owning features grows.
Learner document uploads, certificates, and profile pictures are all on the roadmap, and each
one is cheaper to place correctly now than to migrate later.

## The immediate defect

`GeneratedReport.file` (`freedom_ls/reports/models.py:73`) resolves its storage through
`get_reports_storage()` (`:36`), which looks up `REPORTS_STORAGE_ALIAS` — default `"reports"`
(`freedom_ls/reports/config.py:79`) — and **falls back to `storages["default"]` when that key
is absent**.

`config/settings_prod.py:136` declares only `default` and `staticfiles`. So:

- `freedom_ls_reports.W001` (`freedom_ls/reports/checks.py:39`) is firing in production.
- Report PDFs are landing in the same bucket as public-facing course images.

This is exactly the failure the check was written to catch, and step 6 of the `basic_reports`
upgrade notes told downstream projects to fix it. FLS's own production settings never did.
`docs/product/security-and-data-handling.md:140` currently describes the private-storage
behaviour as configured, which is not true of this deployment.

Fixing this is worth doing whether or not the rest of this idea is adopted.

## Current state

One bucket. `config/settings_prod.py:114` reads a single `AWS_STORAGE_BUCKET_NAME` and wires it
to `STORAGES["default"]` through `build_s3_media_storage()`
(`freedom_ls/deployment/storage.py`), targeting Cloudflare R2.

Static files are not in a bucket and never were — WhiteNoise serves them
(`config/settings_base.py:145`, `config/settings_prod.py:139`) off `STATIC_ROOT`.

Three consumers share the one bucket:

| Consumer | Field | How bytes reach the browser |
|---|---|---|
| Course assets | `content_engine.File.file` (`freedom_ls/content_engine/models.py:590`) | `{{ file_obj.file.url }}` in `picture.html`, `pdf-embed.html`, `file-download.html` — signed URL, direct to storage |
| Organisation logos | `organisations.Organisation.logo` (`freedom_ls/organisations/models.py:31`) | `{{ course_organisation.logo.url }}` in `course_organisation_chip.html` — signed URL, direct to storage |
| Cohort reports | `reports.GeneratedReport.file` | `FileResponse` in `download_report_view` (`freedom_ls/reports/views.py:109`) — streamed through Django behind a per-cohort permission check, never `.url` |

Note that FLS already has two distinct logo concepts, and only one of them needs storage.
`HEADER_LOGO_STATIC_PATH` (`freedom_ls/site_aware_models/config.py:16`, consumed by
`reports/render.py:181` and `accounts/email_utils.py:426`) is a **static path**, already
WhiteNoise-served. `Organisation.logo` is the per-tenant **uploaded** one.

## The constraint that drives the layout

Three properties are bucket-level rather than prefix-level on R2: anonymous public read (via
custom domain), object versioning, and API-token scoping.

`build_s3_media_storage()` takes one `querystring_auth` and one `custom_domain` for the whole
alias, so today every file in the bucket is forced into an identical access policy. Course
media and organisation logos genuinely want different ones.

Worth being precise about the cloud, because it changes the answer:

- **On S3**, a bucket policy can grant anonymous `s3:GetObject` on `bucket/public/*` alone, so
  the public/private split can be prefix-scoped and several aliases can share a bucket.
- **On R2**, which is what `deployment/storage.py` is built for (it handles R2's absent ACLs
  and defaults `region_name` to `"auto"`), public access is granted per-bucket through a custom
  domain or `r2.dev` subdomain. There is no prefix-scoped anonymous read.

So on R2 the public/private boundary is a bucket boundary. Storage **aliases** and **buckets**
are still not the same thing, and the spec should keep them separate — the alias count is driven
by access policy, the bucket count by what R2 can enforce.

## The layout — four buckets

Four buckets. The split is driven by three questions asked of every file: **who supplies the
bytes**, **how they reach the browser**, and **what happens to them over time**. Where two kinds
of file answer all three the same way they share a bucket; where they diverge on any one of them
they do not.

| Bucket | Contents | Written by | Read policy |
|---|---|---|---|
| `fls-prod-public` | Organisation logos; future public branding | Admin, through the browser | Public read, custom domain, long CDN cache |
| `fls-prod-course-media` | `content_engine.File` — images, PDFs, video | Operator, from the content repository | Private, signed URLs |
| `fls-prod-learner-uploads` | Future: application attachments, learner documents, profile pictures | Learners, through the browser | Private, signed URLs |
| `fls-prod-generated` | Cohort reports; future certificates | The task worker | Private, no public read; streamed by Django |

### `fls-prod-public` — organisation logos and public branding

Holds `Organisation.logo` and anything else that is brand rather than content: identical bytes
for every viewer, no personal data, and often rendered before the viewer has authenticated at
all.

It is separate because it is the only bucket that wants **anonymous public read**, and on R2 that
is a per-bucket property. Everything downstream follows from that: a custom domain, a long
`Cache-Control` max-age, and real CDN caching.

Merging these into the private course-media bucket is the tempting cut and the one to refuse.
Every logo render would become a fresh signed URL, so the query string changes on each request
and both the browser and any CDN miss cache — on an asset that appears on every course card and
every cohort list row.

Note the narrow scope. `HEADER_LOGO_STATIC_PATH` (`freedom_ls/site_aware_models/config.py:16`)
is a static path served by WhiteNoise and stays there. Only the uploaded per-tenant logo needs a
bucket.

### `fls-prod-course-media` — course assets

Holds `content_engine.File`: the images, PDFs, video and audio referenced from course content.
Highest read volume of the four, and by a wide margin.

It is separate for two reasons. First, it is **rebuildable** — course assets are loaded from the
content repository by an operator rather than uploaded through a browser
(`docs/product/security-and-data-handling.md:52`), so the bucket needs no versioning, no backup
policy, and no erasure workflow. It is a cache of the content repository. Second, it should not
share credentials with anything holding personal data: it is the bucket most exposed to the
public internet through signed links, and the one whose token is most widely distributed.

Files stay private with signed URLs, matching the behaviour documented at
`docs/product/security-and-data-handling.md:82`.

### `fls-prod-learner-uploads` — files learners give us

Reserved for work not yet built: application-form attachments (`docs/product/roadmap.md:53`),
learner-supplied documents, and profile pictures.

It is separate because these are **irreplaceable originals supplied by untrusted uploaders**.
Nothing else in the system shares that combination. Concretely, that means:

- **Object versioning on.** This is the only bucket where losing an object loses data that cannot
  be regenerated from the content repository or by re-running a task. Versioning is bucket-level.
- **Erasure boundary.** Prefixed per learner, so a right-to-erasure request becomes a scoped
  delete rather than a search across mixed content. See
  `spec_dd/1. next/user-data-retention-idea.md`.
- **Narrow write credentials.** Bytes arrive from the public internet, so the token that can
  write here should reach nothing else.

Profile pictures need `.url` to render, so this bucket must permit signed reads — it is private
in the sense of no anonymous read, not stream-only.

### `fls-prod-generated` — reports and certificates

Holds `GeneratedReport.file` today and certificates once built.

**These stay separate from learner uploads.** They share an access policy but differ on every
other axis:

- **Disposable versus irreplaceable.** A report can be regenerated from the database; a document
  a learner uploaded cannot. Versioning and backup are wanted on one bucket and wasted on the
  other.
- **Opposite retention pressure.** Reports want a lifecycle rule that expires them — the gap
  admitted at `docs/product/security-and-data-handling.md:17` — while learner uploads must never
  be auto-deleted. Sharing a bucket puts a destructive rule one misconfiguration away from the
  data that cannot be recovered.
- **Different writer.** Reports are written by the `django-tasks` worker, never by a web request.

It is also the tightest bucket of the four: reports are streamed through
`download_report_view` (`freedom_ls/reports/views.py:109`) behind a per-cohort permission check
and never reach the browser as a storage URL, so **nothing needs to read this bucket except the
application itself**. No public read, no custom domain, and no signed-URL path — the narrowest
credentials in the deployment.

Certificates carry one open question, recorded below: if verification serves the PDF itself,
they may belong in `fls-prod-public` instead.

### What should not be considered

Per-site or per-organisation buckets. Sites and Organisations are the tenancy layer, but a bucket
per tenant means credential sprawl and runs into R2's bucket limits. Prefix within these buckets
instead — `organisation_logo_upload_to` (`freedom_ls/organisations/models.py:17`) and
`report_upload_path` already prefix by pk.

## Likely scope of the resulting spec

- Per-alias settings in `config/settings_prod.py`: bucket name, credentials, `querystring_auth`
  and `custom_domain` per alias rather than one global set. `build_s3_media_storage()` is already
  alias-agnostic and should need no change.
- A settings-level default that keeps single-bucket and filesystem-only deployments working —
  downstream FLS installations must not be forced to provision four buckets to run.
- A storage alias setting for organisation logos and for `content_engine.File`, matching the
  `REPORTS_STORAGE_ALIAS` pattern, with the same fallback-plus-warning shape as
  `freedom_ls_reports.W001`.
- Declaring the `reports` alias in FLS's own production settings.
- A migration path for objects already written to the single bucket.
- Documentation updates: the env-var table in `docs/deployment-security-checklist.md:184`,
  `docs/product/deployment.md`, and the storage paragraphs in
  `docs/product/security-and-data-handling.md`.
- `upgrade_notes.md` for downstream projects.

## Decisions already taken

These are settled. The spec should implement them, not reopen them.

- **Four buckets, not three.** Generated files and learner uploads stay in separate buckets even
  though they share an access policy, for the retention and versioning reasons set out above.
- **Organisation logos do not merge into course media.** The caching cost is the reason.
- **Learner profile pictures live in `fls-prod-learner-uploads`** and are served with signed
  URLs, not streamed.

## Open questions

- Do organisation logos become genuinely public, or stay signed? Public is better for caching;
  it also means a logo URL is permanently guessable. Probably fine for a corporate mark, but it
  is a product decision, not a technical one.
- Do certificates need a public verification URL? `spec_dd/1. next/certificates/idea.md` calls
  for "verifiable, tamper-evident certificates with a public verify URL". If verification serves
  the PDF itself rather than a rendered attestation page, certificates belong in `public`, not
  `generated`. Resolve this before certificates are built.
- Does the retention/erasure work in `spec_dd/1. next/user-data-retention-idea.md` want to drive
  the bucket boundaries, or inherit them? These two ideas should be sequenced deliberately.
- Are staging and production separate buckets, or separate prefixes? Separate buckets, almost
  certainly, but the env-var shape should make it obvious which is which.

## Out of scope for this idea

- Implementation, and the settings design itself. This file records the decision and its
  reasoning; the spec designs the configuration surface.
- Per-request access-controlled media downloads. Routing every course-file fetch through the
  authorisation check that governs course pages is tracked separately in the roadmap
  (`docs/product/roadmap.md:98`). It would reduce the reliance on signed-URL privacy but does not
  change how many buckets are needed.
- Certificates and learner document uploads as features. This idea only reserves their place.
