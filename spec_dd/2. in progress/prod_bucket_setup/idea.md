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

## Which splits R2 can actually enforce

The target is Cloudflare R2 only. That is settled, and it changes the answer, because on S3 a
bucket policy could grant anonymous `s3:GetObject` on `bucket/public/*` alone and all of this would
be prefix work.

R2 enforces per bucket: anonymous public read, API token scoping, CORS, jurisdiction. It enforces
per prefix: lifecycle expiry, Bucket Locks, event notifications, and by extension backup fan-out and
per-user erasure. So a difference in expiry, immutability, backup or erasure policy is not a reason
for a second bucket. A difference in who can read without logging in, or in where the bytes are
allowed to sit, is.

Token scoping looks like a third reason and mostly isn't. A token does scope to a set of named
buckets and nothing finer, so a bucket is the only unit of least-privilege credentials R2 offers.
That buys separation where two principals hold different tokens. FLS has one. The web process, the
`django-tasks` worker and `content_save` all run the same settings module from one environment file,
so splitting five ways splits variables inside a single `.env` rather than splitting trust.

A bucket boundary still limits reach. A credential that escapes through a log line or a traceback
gets one bucket instead of all of them. That is worth exactly one split, around the files that name
a person.

Aliases and buckets are still not the same thing. Bucket count follows what R2 can enforce; alias
count follows what the settings layer needs to say differently, which is more.

## The layout

One question picks a bucket: can this file be read without logging in. A second question picks an
alias inside it: what does the settings layer have to say about this file that it doesn't say about
its neighbours.

| Bucket | Contents | Read policy | Names a person |
|---|---|---|---|
| `fls-prod-public` | Organisation logos, future public branding, future learner certificates | Anonymous read, custom domain, CDN cached | Once certificates ship |
| `fls-prod-course-media` | `content_engine.File`: images, PDFs, video | Private, signed URLs | No |
| `fls-prod-user-data` | Cohort reports, future user uploads and profile pictures | Private, signed URLs or streamed by Django | Yes |

Those names are values, not constants. Each bucket's name reaches the settings module through
environment variables, so the table records the names production will be handed rather than
anything the code contains. The `prod` in each name is the environment, and staging runs the same
split under `fls-staging-`.

**`fls-prod-public`** is everything served without a login. Branding is identical bytes for every
viewer, often rendered before the viewer has authenticated. Merging it into course media is the
tempting cut and the wrong one: Cloudflare's cache key includes the query string and a fresh
signature is minted per render, so browser and CDN both miss on every request, on an asset that
appears on every course card. Going public costs little, since `Organisation.id` is a UUIDv4, public
R2 buckets don't expose listing, and R2 charges no egress.

Certificates belong here rather than in a bucket of their own. Verification hands over the PDF
itself, so a certificate needs anonymous read, a custom domain and a CDN cache. Those are per-bucket
properties, this bucket already has all three, and they are the whole set a separate certificates
bucket would be created to reproduce. A certificate does name a learner, unlike branding, but the
protection that answers for is an unguessable object key, and a key is a prefix concern. The merge
does force one thing: this bucket's jurisdiction gets decided on the certificate's terms rather than
the logo's, and jurisdiction is fixed at creation.

**`fls-prod-course-media`** is rebuildable, holds no personal data, and is the one bucket whose read
policy might still change. The signed-URL caching argument that sends logos to a public bucket
applies to course images too, which appear on every course card. Whether to act on it is a separate
decision on a separate spec; keeping course media out of `fls-prod-user-data` is what keeps the
decision available, because anonymous read cannot be granted to part of a bucket.

**`fls-prod-user-data`** holds every file that is about or from an identified person: cohort reports
today, user uploads and profile pictures later. It is the one bucket the two immutable per-bucket
properties argue for. It is the only candidate for EU jurisdiction, which R2 fixes at creation and
cannot scope to a prefix, and it is the one bucket worth a token that reaches nothing else.

Reports and uploads share it because everything separating them is prefix-scopable. Reports want
lifecycle expiry under `cohort_reports/` and uploads must never be auto-deleted; R2 filters expiry
rules by prefix. Uploads are irreplaceable originals from untrusted uploaders and want immutability;
Bucket Locks take prefixes too, and take precedence over expiry. R2 has no object versioning at all,
so version history has to be built either way, and the event-notification fan-out that builds it is
also prefix-filtered. Per-learner prefixes under `user_uploads/` turn a right-to-erasure request
into a scoped delete, which works the same in a shared bucket as in a dedicated one. Profile
pictures need `.url` to render, so private here means no anonymous read, not stream-only.

## Decisions taken

- **Cloudflare R2 only**, and production is greenfield. No S3 parity requirement, no object
  migration in scope.
- **The public bucket sets `Cache-Control` at upload.** R2 has no bucket-level default, and a public
  bucket without the header gets none of the caching that justified creating it.
- **Aliases are always declared at the settings layer**, never silently fallen back to at the model
  layer. App-level resolvers become one-liners with no exception handling. The silent fallback is
  what turns a missing settings key into learner PII in a public bucket, and `W001` is only a
  warning, so replicating that shape across every alias would replicate the failure once per alias.
- **No per-site or per-organisation buckets.** Tenancy is a prefix concern and a bucket per tenant
  means credential sprawl. `organisation_logo_upload_to` and `report_upload_path` already prefix by
  pk.
- **Certificate PDFs are served publicly, from the branding bucket.** Verification hands over the
  PDF itself rather than a rendered attestation page, so the object needs anonymous read and cannot
  live with the reports. Three constraints go back to
  `spec_dd/1. next/certificates/idea.md`: uuid-derived object keys, a `certificates/` prefix keeping
  them clear of branding, and whatever consent a site needs before a learner's name sits at a URL
  anyone can open.
- **Every bucket name is read from the environment, one variable per alias.** This layout fixes
  what each bucket is for. It does not fix what any of them is called. No bucket name appears in
  the settings module, so the same code runs against production, staging and a downstream project's
  own buckets, and renaming a bucket becomes a deploy-config change instead of a release. There is
  a variable per alias rather than per bucket, so two of them carry the same value and a project
  that wants a bucket per alias changes values rather than code. An unset variable falls back to the
  shared bucket, which is the collision the system check exists to catch.
- **Staging gets its own buckets, not a prefix inside production's.** A token scopes to named
  buckets, so shared buckets would hand staging credentials that reach production objects. Buckets
  are named `fls-<env>-<purpose>`, and the variables naming them carry no environment of their own,
  so the environment appears in the value and nowhere else. Staging must not copy production's
  Bucket Locks, or it can never be torn down and rebuilt.
- **Reports upload to `cohort_reports/`, not `reports/`.** The prefix does two jobs: it keeps report
  keys clear of `user_uploads/` in the shared bucket, and it is what R2 attaches a lifecycle expiry
  rule to. Naming the artifact rather than the app keeps both true when the bucket gains a third
  kind of file. Nothing is deployed, so there is nothing to move.

## Out of scope

- Implementation and the settings design itself. `notes_for_the_spec.md` holds the constraints the
  spec shouldn't have to rediscover.
- Per-request access-controlled media downloads, tracked in `docs/product/roadmap.md`. It would
  reduce the reliance on signed-URL privacy but doesn't change how many buckets are needed.
- Certificates and user document uploads as features. This idea only reserves their place.
- Data residency and file erasure mechanics, handed to `spec_dd/1. next/user-data-retention-idea.md`,
  which today covers DB-row retention and never mentions buckets. It should know that R2 jurisdiction
  is fixed at creation and cannot be scoped to a prefix, so the only free moment to act on it is
  before these buckets exist.

## Research

- `research_r2_platform_constraints.md`. Bucket versus prefix scoping, and the absent features.
- `research_django_storages_multi_alias.md`. Declaring `STORAGES` aliases and resolving them safely.
- `research_public_vs_signed_logos.md`. The caching cost of signed URLs on branding assets.
- `research_fls_storage_surface.md`. Every FLS file field, template and admin form touching storage.
