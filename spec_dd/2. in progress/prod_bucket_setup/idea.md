# Production object storage: how many buckets, and what goes where

FLS's production settings declare one media bucket. Three kinds of file would write into it, with
three different access patterns and three different sensitivity levels. One of them is cohort
report PDFs naming learners and their quiz answers.

Production has not been stood up yet. This idea settles the target bucket layout before it is, and
before the set of file-owning features grows. Learner document uploads, certificates and profile
pictures are all on the roadmap, so placing files correctly now costs nothing.

## The defect

`GeneratedReport.file` resolves its storage through `get_reports_storage()`, which reads
`REPORTS_STORAGE_ALIAS` (default `"reports"`) and falls back to `storages["default"]` when that key
is absent. `config/settings_prod.py` declares only `default` and `staticfiles`, so
`freedom_ls_reports.W001` fires and report PDFs would land in the same bucket as public-facing
course images. Step 6 of the `basic_reports` upgrade notes told downstream projects to fix exactly
this. FLS's own production settings never did.

Nothing has leaked, because nothing is deployed. It is a settings bug rather than an incident, with
no misplaced objects to move, and it has to be fixed before the first production deploy whether or
not the rest of this idea is adopted.

## Current state

One bucket. `config/settings_prod.py` reads a single `AWS_STORAGE_BUCKET_NAME` and wires it to
`STORAGES["default"]` through `build_s3_media_storage()`, targeting Cloudflare R2. Static files were
never in a bucket; WhiteNoise serves them off `STATIC_ROOT`.

There are exactly three file-storing fields in the repo. Two pass no `storage=` and fall to
`default` implicitly.

| Consumer | Field | Storage | Reaches the browser via |
|---|---|---|---|
| Course assets | `content_engine.File.file` | none, implicit `default` | signed URL, direct to storage, from four cotton templates |
| Organisation logos | `organisations.Organisation.logo` | none, implicit `default` | signed URL, direct to storage, from `course_toc_header.html` |
| Cohort reports | `reports.GeneratedReport.file` | `get_reports_storage()` | `FileResponse` from `download_report_view`, streamed behind a per-cohort permission check |

Only one of FLS's two logo concepts needs a bucket. `HEADER_LOGO_STATIC_PATH` is a static path
served by WhiteNoise. `Organisation.logo` is the per-tenant uploaded one.

## Why buckets, not prefixes

The target is Cloudflare R2 only. That is settled, and it changes the answer, because on S3 a
bucket policy could grant anonymous `s3:GetObject` on `bucket/public/*` alone and most of this would
be prefix work.

R2 enforces per bucket: anonymous public read, API token scoping, CORS, jurisdiction. It enforces
per prefix: lifecycle expiry, Bucket Locks, event notifications. Token scoping is what drives the
layout, because a token scopes to a set of named buckets and nothing finer, making a bucket the only
unit of least-privilege credentials R2 offers. Buckets are free and effectively uncapped.

Aliases and buckets are still not the same thing. Alias count follows access policy; bucket count
follows what R2 can enforce.

## The layout

Two questions decide where a file goes: what credentials should write it, and how it reaches the
browser. Files answering both the same way share a bucket.

| Bucket | Contents | Written by | Read policy |
|---|---|---|---|
| `fls-prod-public` | Organisation logos, future public branding | Admin, through the browser | Public read, custom domain, long CDN cache |
| `fls-prod-course-media` | `content_engine.File`: images, PDFs, video | Operator, from the content repository | Private, signed URLs |
| `fls-prod-learner-uploads` | Future: application attachments, learner documents, profile pictures | Learners, through the browser | Private, signed URLs |
| `fls-prod-generated` | Cohort reports, future certificates | The task worker | Private, no public read, streamed by Django |

**`fls-prod-public`** is brand rather than content: identical bytes for every viewer, no personal
data, often rendered before the viewer has authenticated. It is the only bucket wanting anonymous
public read, which on R2 is a per-bucket property. Merging it into course media is the tempting cut
and the wrong one: Cloudflare's cache key includes the query string and a fresh signature is minted
per render, so browser and CDN both miss on every request, on an asset that appears on every course
card. Going public costs little, since `Organisation.id` is a UUIDv4, public R2 buckets don't expose
listing, and R2 charges no egress.

**`fls-prod-course-media`** is rebuildable. An operator loads it from the content repository rather
than uploading through a browser, so it needs no backup policy and no erasure workflow. It also
carries the highest read volume and the most widely distributed token of the four, so it shouldn't
share credentials with anything holding personal data.

**`fls-prod-learner-uploads`** holds irreplaceable originals supplied by untrusted uploaders, a
combination nothing else in the system shares. The token that can write here should reach nothing
else. Prefixing per learner turns a right-to-erasure request into a scoped delete. R2 has no object
versioning at all, so version history would have to be built rather than switched on. Profile
pictures need `.url` to render, so private here means no anonymous read, not stream-only.

**`fls-prod-generated`** is written by the `django-tasks` worker and read by nothing but the
application. `download_report_view` streams the file behind a per-cohort permission check and never
hands out a storage URL, so this bucket needs no public read, no custom domain and no signed-URL
path. The narrowest credentials in the deployment. Reports also want expiry while learner uploads
must never be auto-deleted, and separate buckets keep that lifecycle rule away from irreplaceable
data.

## Decisions taken

- **Cloudflare R2 only**, and production is greenfield. No S3 parity requirement, no object
  migration in scope.
- **The public bucket sets `Cache-Control` at upload.** R2 has no bucket-level default, and a public
  bucket without the header gets none of the caching that justified creating it.
- **Aliases are always declared at the settings layer**, never silently fallen back to at the model
  layer. App-level resolvers become one-liners with no exception handling. The silent fallback is
  what turns a missing settings key into learner PII in a public bucket, and `W001` is only a
  warning, so replicating that shape across four aliases would replicate the failure four times.
- **No per-site or per-organisation buckets.** Tenancy is a prefix concern and a bucket per tenant
  means credential sprawl. `organisation_logo_upload_to` and `report_upload_path` already prefix by
  pk.

## Open questions

- Do certificates need a public verification URL? `spec_dd/1. next/certificates/idea.md` calls for
  one. If verification serves the PDF itself rather than a rendered attestation page, certificates
  belong in `public`, not `generated`. Resolve before certificates are built.
- Separate buckets for staging and production, or separate prefixes? Separate buckets, almost
  certainly, but the env-var shape should make which is which obvious. Bucket Locks block emptying
  or deleting a bucket, so a staging environment mirroring production's lock rules can't be torn
  down and recreated freely.
- Should `report_upload_path`'s `reports/` prefix change now the bucket is dedicated?
  `reports/tests/test_deletion_hygiene.py` asserts on that exact string.

## Out of scope

- Implementation and the settings design itself. `notes_for_the_spec.md` holds the constraints the
  spec shouldn't have to rediscover.
- Per-request access-controlled media downloads, tracked in `docs/product/roadmap.md`. It would
  reduce the reliance on signed-URL privacy but doesn't change how many buckets are needed.
- Certificates and learner document uploads as features. This idea only reserves their place.
- Data residency and file erasure mechanics, handed to `spec_dd/1. next/user-data-retention-idea.md`,
  which today covers DB-row retention and never mentions buckets. It should know that R2 jurisdiction
  is fixed at creation, so the only free moment to act on it is before these buckets exist.

## Research

- `research_r2_platform_constraints.md`. Bucket versus prefix scoping, and the absent features.
- `research_django_storages_multi_alias.md`. Declaring `STORAGES` aliases and resolving them safely.
- `research_public_vs_signed_logos.md`. The caching cost of signed URLs on branding assets.
- `research_fls_storage_surface.md`. Every FLS file field, template and admin form touching storage.
