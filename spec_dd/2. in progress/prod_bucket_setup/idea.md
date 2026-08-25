# Production Object Storage — How Many Buckets, and What Goes Where

FLS runs one media bucket in production. Three different kinds of file are writing into it,
with three different access patterns and three different sensitivity levels. One of them —
cohort report PDFs containing named learners and their quiz answers — is there by accident,
because the alias that was supposed to redirect it was never declared.

This idea settles the target bucket layout before the set of file-owning features grows.
Learner document uploads, certificates, and profile pictures are all on the roadmap, and each
one is cheaper to place correctly now than to migrate later.

> **Research status.** Four research files sit next to this idea:
> `research_r2_platform_constraints.md`, `research_django_storages_multi_alias.md`,
> `research_public_vs_signed_logos.md`, `research_fls_storage_surface.md`. They verified the
> platform claims this idea originally rested on, and **two of them were refuted** — see
> *What the research changed*. The four-bucket conclusion survives; most of its reasoning
> does not, and has been rewritten.

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

**The defect is a pattern, not an incident.** The silent fallback is what converted a missing
settings key into learner PII in a public bucket, and `W001` is a `Warning` — it does not fail
`manage.py check`, and it is trivially silenced. Replicating that shape across four aliases
would replicate the failure four times. The fallback design is therefore part of this idea's
scope, not an implementation detail; see *Decisions already taken*.

## Current state

One bucket. `config/settings_prod.py:114` reads a single `AWS_STORAGE_BUCKET_NAME` and wires it
to `STORAGES["default"]` through `build_s3_media_storage()`
(`freedom_ls/deployment/storage.py`), targeting Cloudflare R2.

Static files are not in a bucket and never were — WhiteNoise serves them
(`config/settings_base.py:145`, `config/settings_prod.py:139`) off `STATIC_ROOT`.

There are exactly three file-storing fields in the entire repo. Two of them pass no `storage=`
at all and so fall to `default` implicitly; only `reports` uses an alias.

| Consumer | Field | Storage | How bytes reach the browser |
|---|---|---|---|
| Course assets | `content_engine.File.file` (`freedom_ls/content_engine/models.py:590`) | **none — implicit `default`** | Signed URL, direct to storage, from four cotton templates |
| Organisation logos | `organisations.Organisation.logo` (`freedom_ls/organisations/models.py:31`) | **none — implicit `default`** | Signed URL, direct to storage, from `course_toc_header.html:28` |
| Cohort reports | `reports.GeneratedReport.file` | `get_reports_storage` | `FileResponse` in `download_report_view` (`freedom_ls/reports/views.py:109`) — streamed through Django behind a per-cohort permission check, never `.url` |

Two corrections the audit made to this table's earlier version:

- **Four templates read `content_engine.File.file.url`, not three** — `picture.html:35` and `:95`,
  `pdf-embed.html:21`, `file-download.html:17`, and `card.html:32`.
- **The organisation logo template named here previously did not exist.** There is no
  `course_organisation_chip.html`; the only reader is
  `learner_interface/templates/learner_interface/partials/course_toc_header.html:28`.

**Both admin change forms are an unlisted signed-URL read path.** `FileAdmin`
(`freedom_ls/content_engine/admin.py:274`) and `OrganisationAdmin`
(`freedom_ls/organisations/admin.py:20`) expose the raw field, so Django's `ClearableFileInput`
renders a `Currently: <a href="{{ value.url }}">` link for both. Reports deliberately do not —
`reports/tests/test_admin.py:106` asserts `report.file.url` never appears in the changelist. The
spec should confirm the staff-only admin surface is acceptable for the other two rather than
assume admin never touches storage URLs.

Note that FLS already has two distinct logo concepts, and only one of them needs storage.
`HEADER_LOGO_STATIC_PATH` (`freedom_ls/site_aware_models/config.py:16`, consumed by
`reports/render.py` and `accounts/email_utils.py:426`) is a **static path**, already
WhiteNoise-served — the audit confirmed both resolve it through the staticfiles finders and
neither ever touches object storage. `Organisation.logo` is the per-tenant **uploaded** one.

## What the research changed

The original version of this idea justified the layout on three properties it claimed were
bucket-level on R2: anonymous public read, object versioning, and API-token scoping. Verified
against Cloudflare's docs:

| Claim | Verdict |
|---|---|
| Anonymous public read is per-bucket, not prefix-scopable | **Confirmed.** No native prefix-level public toggle; the alternatives are Cloudflare Access or a Worker in front of the bucket. |
| Object versioning is available and bucket-level | **Refuted.** R2 has no object versioning at all — `GetBucketVersioning`/`PutBucketVersioning` are explicitly unimplemented in its S3 API. |
| API-token scoping is bucket-level | **Confirmed, and narrower than assumed.** Tokens scope to a set of named buckets. There is **no** prefix-level scoping, so a bucket is the *only* unit of least-privilege credentials on R2. |
| Lifecycle expiry needs its own bucket | **Refuted.** Lifecycle rules are prefix-filterable, so "reports expire, uploads don't" works inside one bucket. |

Three further findings that the layout now has to account for:

- **Bucket Locks replace versioning.** R2's nearest equivalent is WORM-style retention that
  blocks delete and overwrite for a period or indefinitely. It is *prefix*-scopable, so it does
  not itself imply a bucket boundary — and it blocks emptying or deleting a locked bucket, which
  has real teardown implications for any staging environment that mirrors production.
- **`Cache-Control` is per-object metadata on R2**, set at upload. There is no bucket default. The
  public bucket's long CDN cache is therefore an *application* requirement — the upload path must
  set the header — not something that falls out of making the bucket public.
- **Bucket jurisdiction (EU/US data residency) is immutable at creation** and not prefix-scopable.

Cost and count are a non-issue: up to 1,000,000 buckets per account, no per-bucket billing, no
egress fees.

## The constraint that drives the layout

`build_s3_media_storage()` takes one `querystring_auth` and one `custom_domain` for the whole
alias, so today every file in the bucket is forced into an identical access policy. Course
media and organisation logos genuinely want different ones.

The target is **Cloudflare R2 only** — this is a settled constraint, not an assumption, and the
spec need not preserve AWS S3 parity. That matters, because on S3 a bucket policy can grant
anonymous `s3:GetObject` on `bucket/public/*` alone and much of this would be prefix work. On R2
it cannot.

What is genuinely **bucket-level** on R2, and therefore what a bucket boundary buys:

- Anonymous public read (custom domain or `r2.dev`)
- API token scoping — the only least-privilege lever available
- CORS policy
- Jurisdiction, fixed permanently at creation

What is **prefix-level**, and therefore what a bucket boundary does *not* buy:

- Lifecycle expiry rules
- Bucket Locks (retention/immutability)
- Event notifications

Storage **aliases** and **buckets** are still not the same thing, and the spec should keep them
separate — the alias count is driven by access policy, the bucket count by what R2 can enforce.

## The layout — four buckets

Four buckets. Now that lifecycle and versioning have dropped out as justifications, the split
rests on two questions asked of every file: **what credentials should be able to write it**, and
**how does it reach the browser**. Where two kinds of file answer both the same way they share a
bucket; where they diverge on either they do not.

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
is a per-bucket property. This is the layout's strongest surviving justification.

Merging these into the private course-media bucket is the tempting cut and the one to refuse.
The caching claim was checked and holds: Cloudflare's default cache key includes the full query
string, and a fresh signature is minted per render, so both the browser and the CDN miss on every
request — on an asset that appears on every course card and every cohort list row.

The exposure this accepts is smaller than first assumed. `Organisation.id` is a UUIDv4
(`freedom_ls/site_aware_models/models.py:80`), so logo URLs are not enumerable; public R2 buckets
do not expose object listing to anonymous callers, so an attacker cannot walk the keyspace; and
R2 charges no egress, so hotlinking costs nothing. Treating branding as public and user content
as signed is also the conventional split — Gravatar, GitHub avatars and Slack workspace icons all
work this way.

One implementation requirement follows and should not be lost: **the upload path must set
`Cache-Control` explicitly**, because R2 has no bucket-level default. A public bucket without it
gets none of the caching benefit that justified creating it.

Note the narrow scope. `HEADER_LOGO_STATIC_PATH` is a static path served by WhiteNoise and stays
there. Only the uploaded per-tenant logo needs a bucket.

### `fls-prod-course-media` — course assets

Holds `content_engine.File`: the images, PDFs, video and audio referenced from course content.
Highest read volume of the four, and by a wide margin.

It is separate for two reasons. First, it is **rebuildable** — course assets are loaded from the
content repository by an operator rather than uploaded through a browser
(`docs/product/security-and-data-handling.md:52`), so the bucket needs no backup policy and no
erasure workflow. It is a cache of the content repository. Second, it should not share credentials
with anything holding personal data: it is the bucket most exposed to the public internet through
signed links, and the one whose token is most widely distributed.

Files stay private with signed URLs, matching the behaviour documented at
`docs/product/security-and-data-handling.md:82`.

### `fls-prod-learner-uploads` — files learners give us

Reserved for work not yet built: application-form attachments (`docs/product/roadmap.md:53`),
learner-supplied documents, and profile pictures. The application-forms draft
(`spec_dd/0. drafts/application-forms/idea.md:134`) already specs a private `FileField` with a
non-guessable pk-based path, a `scan_status` seam and `superseded` replace-history, which is
independent evidence for this bucket's shape.

It is separate because these are **irreplaceable originals supplied by untrusted uploaders**.
Nothing else in the system shares that combination. Concretely:

- **Narrow write credentials.** Bytes arrive from the public internet, so the token that can
  write here should reach nothing else. On R2 this is only expressible as a bucket boundary.
- **Erasure boundary.** Prefixed per learner, so a right-to-erasure request becomes a scoped
  delete rather than a search across mixed content.
- **Protection against accidental loss.** This is the only bucket where losing an object loses
  data that cannot be regenerated. ~~Object versioning~~ — **not available on R2**. The nearest
  native mechanism is **Bucket Locks**, and because they are prefix-scopable they are available
  whether or not this is its own bucket. If genuine version history is ever required, it has to be
  built: an event notification driving a Worker that copies objects to a backup bucket.

Profile pictures need `.url` to render, so this bucket must permit signed reads — it is private
in the sense of no anonymous read, not stream-only.

Two R2 details the spec will need if browser-side uploads are ever built here: presigned URLs max
out at 7 days, cannot be used with custom domains, and **POST-based (HTML form) presigned uploads
are not supported on R2** — an S3 `createPresignedPost`-style browser upload will not work.

### `fls-prod-generated` — reports and certificates

Holds `GeneratedReport.file` today and certificates once built.

**These stay separate from learner uploads**, but the original reasoning for that no longer holds
and is replaced. Lifecycle expiry does *not* require a bucket boundary — prefix-scoped rules would
do — and neither does anything about versioning, which does not exist. What remains:

- **Different writer, and that is now the load-bearing argument.** Reports are written by the
  `django-tasks` worker, never by a web request. Because R2 token scoping is bucket-granular with
  no prefix option, giving the worker credentials that reach nothing else *requires* a separate
  bucket. This is the only mechanism R2 offers.
- **Different access pattern.** Reports are streamed through `download_report_view`
  (`freedom_ls/reports/views.py:109`) behind a per-cohort permission check and never reach the
  browser as a storage URL, so **nothing needs to read this bucket except the application
  itself** — no public read, no custom domain, no signed-URL path. The narrowest credentials in
  the deployment.
- **Opposite retention pressure**, still true and still worth stating, but now as a *policy*
  difference rather than a platform constraint: reports want expiry (the gap admitted at
  `docs/product/security-and-data-handling.md:17`), learner uploads must never be auto-deleted.
  Separate buckets keep a destructive lifecycle rule from sitting one misconfiguration away from
  irreplaceable data, even though prefixes could technically express it.

Certificates carry one open question, recorded below.

### What should not be considered

Per-site or per-organisation buckets. Sites and Organisations are the tenancy layer, but a bucket
per tenant means credential sprawl. Prefix within these buckets instead —
`organisation_logo_upload_to` (`freedom_ls/organisations/models.py:17`) and `report_upload_path`
already prefix by pk. (Note that R2's million-bucket ceiling means the old "runs into bucket
limits" argument was wrong; the credential-sprawl argument is the real one.)

## Likely scope of the resulting spec

- A settings-layer `build_storages()` helper in `freedom_ls/deployment/storage.py` that **always
  emits every alias key**, resolving each from per-alias env vars with fallback to the existing
  shared `AWS_STORAGE_BUCKET_NAME` credentials, and to `FileSystemStorage` when no bucket is
  configured at all. `build_s3_media_storage()` is already alias-agnostic and becomes its
  single-alias building block, unchanged.
- A per-alias env-var naming scheme that keeps a shared-credentials shortcut, makes
  staging-versus-production obvious, and does not break deployments already setting the current
  names.
- Storage aliases for organisation logos and for `content_engine.File`, matching the
  `REPORTS_STORAGE_ALIAS` pattern. `content_engine` already has `config.py` and `checks.py` to
  extend; **`organisations` has neither and needs both created**.
- Every per-field storage assignment goes through a **named module-level callable** — never a bare
  `Storage(...)` instance (django-storages is `@deconstructible`, so bucket names and credentials
  would freeze into migration history) and never a lambda (unserializable). Adding `storage=` to
  the two fields that lack it generates one `AlterField` migration each; those reference only the
  callable's dotted path, so later bucket changes need no migration.
- Declaring the `reports` alias in FLS's own production settings.
- A system check that compares **resolved bucket names** and fires when a privacy-sensitive alias
  resolves to the same bucket as `default`. Today's `W001` only detects a wholly undeclared alias,
  which under the always-declared design becomes the normal unconfigured state — so without this,
  the check that was supposed to catch the original defect would stop catching anything.
- Documentation updates: the env-var table in `docs/deployment-security-checklist.md:184` (already
  incomplete today — it omits `AWS_S3_CUSTOM_DOMAIN`, `AWS_QUERYSTRING_AUTH`,
  `AWS_QUERYSTRING_EXPIRE` and `REPORTS_STORAGE_ALIAS`), `docs/product/deployment.md:56-57`, and
  `docs/product/security-and-data-handling.md:140`. The last of these currently reassures the
  reader about a mechanism that FLS's own production settings do not use.
- `claude_plugins/fls-dev/resources/template_repo_manifest.md:205-206` audits downstream projects
  against the single-bucket shape and needs to grow to N aliases.
- **A new `file-storage` skill in the fls-dev plugin** (`claude_plugins/fls-dev/skills/`,
  following the shape of the existing `multi-tenant` and `app-settings` skills). Four buckets are
  only worth having if new file fields land in the right one, and that decision is made at the
  moment someone adds a `FileField`/`ImageField` — which is exactly when nobody re-reads a spec.
  The skill should describe each bucket and what belongs in it, give the decision rule (*who
  supplies the bytes, how do they reach the browser, can they be regenerated*), and carry the
  mechanical rules that are easy to get wrong: resolve storage through a named module-level
  callable, never a bare `Storage(...)` instance or a lambda; prefix the `upload_to` path by pk
  rather than the uploaded filename; and set `Cache-Control` at upload for anything going to the
  public bucket. Its `description` must trigger on creating or modifying a model file/image field,
  so it fires without being asked for.
- `upgrade_notes.md` for downstream projects, following the `basic_reports` precedent
  (`spec_dd/3. done/2026-08-21_20:12_basic_reports/upgrade_notes.md:208-213`) times three new
  aliases.

**No object migration is needed.** The current bucket is treated as rebuildable — course media
reloads from the content repository and reports regenerate from the database.

## Decisions already taken

These are settled. The spec should implement them, not reopen them.

- **Cloudflare R2 only.** No AWS S3 parity requirement.
- **The existing bucket is rebuildable.** No object-migration path in scope.
- **Four buckets, not three.** Generated files and learner uploads stay separate — justified on
  bucket-granular token scoping and access pattern, *not* on lifecycle or versioning, both of
  which were refuted.
- **Organisation logos become genuinely public**, in their own bucket, behind a custom domain,
  with `Cache-Control` set at upload.
- **Organisation logos do not merge into course media.** The caching cost is the reason, and it
  was verified.
- **Learner profile pictures live in `fls-prod-learner-uploads`** and are served with signed
  URLs, not streamed.
- **Aliases are always declared at the settings layer, never silently fallen back to at the model
  layer.** App-level resolvers become one-liners with no exception handling; the "is this
  configured correctly" question moves to a system check that compares resolved buckets. This
  replaces the `get_reports_storage()` try/except shape that caused the original defect.

## Open questions

- Do certificates need a public verification URL? `spec_dd/1. next/certificates/idea.md` calls
  for "verifiable, tamper-evident certificates with a public verify URL". If verification serves
  the PDF itself rather than a rendered attestation page, certificates belong in `public`, not
  `generated`. The certificates idea is three lines long and cannot settle this; resolve it before
  certificates are built.
- Are staging and production separate buckets, or separate prefixes? Separate buckets, almost
  certainly, but the env-var shape should make it obvious which is which. Note that Bucket Locks
  block emptying or deleting a bucket, so a staging environment mirroring production's lock rules
  cannot be torn down and recreated freely.
- Should `report_upload_path`'s `reports/` prefix change now that the bucket is dedicated? If so,
  `reports/tests/test_deletion_hygiene.py:65` asserts on that exact string.

## Deferred to the retention/erasure spec

`spec_dd/1. next/user-data-retention-idea.md` turns out to be **silent on file storage entirely** —
it covers DB-row retention and anonymisation per model and never mentions buckets or `FileField`s.
So it neither drives nor inherits these boundaries today. Two things should be handed to it rather
than settled here:

- **Data residency.** An R2 bucket's jurisdiction is fixed at creation and cannot be retrofitted or
  prefix-scoped. If EU residency is ever required for learner uploads, that bucket must be recreated
  from scratch and its contents copied. Deliberately out of scope here, but the retention spec should
  know the constraint is permanent and cheapest to act on while the bucket is still empty.
- **Erasure mechanics** for files, which this idea only reserves a prefix boundary for.

## Out of scope for this idea

- Implementation, and the settings design itself. This file records the decision and its
  reasoning; the spec designs the configuration surface.
- Per-request access-controlled media downloads. Routing every course-file fetch through the
  authorisation check that governs course pages is tracked separately in the roadmap
  (`docs/product/roadmap.md:98`). It would reduce the reliance on signed-URL privacy but does not
  change how many buckets are needed.
- Certificates and learner document uploads as features. This idea only reserves their place.
