# Research: Cloudflare R2 platform constraints for the four-bucket layout

Scope: verify/refute the load-bearing platform claims behind the proposed
`fls-prod-public` / `fls-prod-course-media` / `fls-prod-learner-uploads` /
`fls-prod-generated` split. Target platform is **Cloudflare R2 only** (no S3
parity effort). All claims are cited against `developers.cloudflare.com/r2/`
unless marked otherwise; community/blog sources are marked lower-confidence
with a date.

---

## 1. Object versioning — THE CRITICAL QUESTION

**VERDICT: Refuted.** R2 has **no object versioning** of any kind, bucket-level
or otherwise, as of this research (2026-08-24).

- The R2 S3-API-compatibility reference explicitly lists `GetBucketVersioning`
  and `PutBucketVersioning` in its **unimplemented/unsupported** operations
  table — i.e. even the S3-compatibility shim does not fake versioning.
  https://developers.cloudflare.com/r2/api/s3/api/
- `ListObjectVersions` / `GetObjectVersion` do not appear in the R2 API
  surface at all (not implemented, not documented) —
  https://developers.cloudflare.com/r2/api/s3/api/
- Community feature-request threads confirm versioning has been requested
  repeatedly and is **not currently available**; as of a Cloudflare staff
  reply reported December 2025, it is on a roadmap with no committed date
  (lower confidence, community post, not an official docs page):
  https://community.cloudflare.com/t/r2-object-versioning-and-replication/524025
  https://community.cloudflare.com/t/r2-immutability/545347

**The idea's premise — "object versioning on" as a per-bucket protection for
`fls-prod-learner-uploads` — is factually wrong for R2 today. It cannot be
implemented as stated.**

### What R2 actually offers instead

Cloudflare R2 has a distinct, non-versioning feature called **Bucket Locks**
(WORM-style retention, not multi-version history):
https://developers.cloudflare.com/r2/buckets/bucket-locks/

- Prevents **deletion and overwriting** of objects in a bucket for a
  specified retention period, or indefinitely.
- Configurable **per-prefix** (rules without a prefix apply bucket-wide; up
  to 1,000 rules per bucket), via Dashboard, Wrangler CLI, or API.
- Retention can be: a fixed duration (e.g. 90 days), until a target date, or
  indefinite.
- Applies to new *and* existing objects; overlapping rules resolve to the
  **longest** retention.
- Takes precedence over lifecycle-expiry rules (a locked object won't be
  deleted by a lifecycle rule until the lock expires).
- **Important side-effect:** a bucket cannot be emptied/deleted while lock
  rules are in force — this has operational implications for any
  staging-teardown or bucket-recreation workflow.
- This is retention/immutability, **not** version history: a locked object
  still can't be overwritten, but there is no way to browse or restore prior
  versions of an object the way S3 versioning allows. It protects against
  accidental *deletion*, not against accidental *overwrite-and-need-the-old-
  content-back* unless overwrite itself is what's being blocked.

Other partial mitigations worth naming (none are "versioning"):
- **Event notifications** (see Q8) can fan out object-create/delete events to
  a Worker that copies objects to a separate backup bucket or bucket prefix
  — a manual/roll-your-own poor-man's-versioning, not a first-class feature.
  https://developers.cloudflare.com/r2/buckets/event-notifications/
- Per-learner **prefixes** plus a **separate backup bucket** (cross-bucket
  copy on write, via a Worker/notification pipeline) is the closest
  Cloudflare-native equivalent to "protect irreplaceable uploads," and it
  works the same whether learner uploads live in their own bucket or a
  prefix of a shared bucket — it is not bucket-boundary-dependent.

---

## 2. Lifecycle / object expiry rules

**VERDICT: Refuted (as a bucket-separation rationale).** Lifecycle rules
support prefix-level scoping, not just bucket-level, which weakens the case
for a dedicated `fls-prod-generated` bucket purely to get auto-expiry.

- R2 Object Lifecycle rules support two actions: **transition** (Standard →
  Infrequent Access) and **expire/delete**.
  https://developers.cloudflare.com/r2/buckets/object-lifecycles/
- Rules are configured on a bucket's lifecycle configuration but **can be
  filtered by object key `Prefix`**, so a single bucket can have one rule
  expiring `reports/` after N days while another prefix (e.g.
  `learner-uploads/`) has no expiry rule at all. Confirmed on the official
  docs page and corroborated by third-party SDK docs showing prefix-filtered
  lifecycle rules in practice:
  https://developers.cloudflare.com/r2/buckets/object-lifecycles/
  https://alos.no/cfnet/articles/accounts/r2/lifecycle.html (lower
  confidence, third-party SDK docs, undated but current as of R2's present
  lifecycle API)
- Max 1,000 lifecycle rules per bucket. Deletions happen within ~24 hours of
  the computed expiration, not instantly.
- Bucket locks (Q1) take precedence over lifecycle expiry, so a lock rule
  can be used to prevent a lifecycle rule from firing prematurely, but that's
  an orthogonal mechanism, not lifecycle scoping itself.

**Implication:** "reports must auto-expire, learner uploads must never
auto-expire" is achievable with **one bucket and two lifecycle rules
scoped by prefix** (`reports/` gets an expire rule, `learner-uploads/` gets
none). Separate buckets are not required for this requirement alone.

---

## 3. Anonymous public read — per-bucket only, no prefix-level public ACL

**VERDICT: Confirmed**, with caveats.

- Public read access is enabled per-bucket via one or both of: a **custom
  domain** (bucket proxied through Cloudflare's network/CDN) or the
  Cloudflare-managed **`r2.dev` subdomain** (explicitly documented as
  "should only be used for development purposes," not production).
  https://developers.cloudflare.com/r2/buckets/public-buckets/
- There is **no native mechanism to expose only a prefix within a bucket as
  anonymously public** while keeping the rest private — public/private is a
  bucket-wide toggle in the documented feature set. The public-buckets doc
  does not describe any prefix-scoped public-read capability, and none of
  the R2 API/dashboard docs surfaced one.
  https://developers.cloudflare.com/r2/buckets/public-buckets/
- **Caveats / workarounds that exist but are not "R2 public buckets":**
  - **Cloudflare Access** (Zero Trust) can be layered in front of a custom
    domain to *restrict* who can read, including gating specific paths via
    Access policies — but that's authentication in front of an otherwise
    public/private bucket, not a native R2 public/private-per-prefix switch.
    https://developers.cloudflare.com/r2/tutorials/cloudflare-access/
  - A **Worker in front of the bucket** (using the Workers R2 binding) can
    implement arbitrary per-prefix authorization logic — e.g. serve
    `logos/*` publicly and 403 everything else — but this means the "public"
    surface is a Worker's routing logic, not an R2 bucket setting, and it
    applies equally whether the objects live in one shared bucket or a
    dedicated bucket.
    https://developers.cloudflare.com/r2/api/workers/
  - WAF custom rules / Cache Rules / Bot Management are only available
    behind a **custom domain**, not `r2.dev` — relevant if the public bucket
    needs rate-limiting or bot protection in front of it.
    https://developers.cloudflare.com/r2/buckets/public-buckets/

**Implication:** The rationale "public org-logo bucket must be separate
because R2 makes public/private a bucket-wide switch" **holds** — this is
the one part of the idea's platform assumptions that is solidly correct
without a Worker-based workaround.

---

## 4. API token scoping

**VERDICT: Partly confirmed.** Bucket-level scoping works and can cover
multiple named buckets in one token; there is **no prefix-level scoping**.

- R2 API tokens support four permission tiers:
  https://developers.cloudflare.com/r2/api/tokens/
  - **Admin Read & Write** — full account-wide bucket admin (create/list/
    delete buckets, edit config, read/write/list objects).
  - **Admin Read only** — read-only account-wide, required for R2 Data
    Catalog use.
  - **Object Read & Write** — scoped to a **specific set of named buckets**;
    read/write/list objects only, no bucket admin.
  - **Object Read only** — same bucket-set scoping, read/list only.
- **Bucket-level scoping is only available on the Object Read & Write /
  Object Read only tiers**; the Admin tiers are account-wide (all buckets).
  https://developers.cloudflare.com/r2/api/tokens/
- A single token **can** be scoped to a **set of multiple named buckets**
  (not just one) — so one token could cover, e.g., both
  `fls-prod-course-media` and `fls-prod-generated` if that's ever wanted,
  or a single narrow token can cover exactly one bucket.
  https://developers.cloudflare.com/r2/api/tokens/
- **No prefix-level (path-scoped) token restriction exists.** A token
  scoped to a bucket has access to the whole bucket's object namespace;
  there's no documented way to say "this token may only touch
  `learner-uploads/user-123/*`."
  https://developers.cloudflare.com/r2/api/tokens/
- Object Read & Write / Object Read only permissions are **only usable via
  the S3-compatible API**, not the native Cloudflare REST API — relevant if
  any tooling calls the Cloudflare account API directly rather than boto3.
  https://developers.cloudflare.com/r2/api/tokens/

**Implication:** "Narrow write credentials per bucket" is achievable and is
in fact the **only** way to get narrower-than-account-wide credential
scoping on R2 today, since prefix-level token scoping doesn't exist. This is
a genuine, R2-specific argument *for* separate buckets (it's the sole lever
available for least-privilege credentials), independent of the versioning
and lifecycle claims which don't hold up.

---

## 5. Bucket limits and naming

**VERDICT: Confirmed**, buckets are cheap/unlimited enough that count is not
a constraint; naming rules are simple and don't have a built-in
staging/production concept.

- **Up to 1,000,000 buckets per account.** No per-bucket cost — R2 billing
  is aggregated across all buckets in an account by storage volume and
  operations, not per-bucket:
  https://developers.cloudflare.com/r2/platform/limits/
- Storage: $0.015/GB-month Standard, $0.01/GB-month Infrequent Access. Class
  A ops $4.50/million (Standard), Class B ops $0.36/million (Standard); no
  egress fees. Free tier: 10GB storage, 1M Class A + 10M Class B ops/month.
  (Pricing page, current as of query date, lower confidence than the limits
  docs page since pricing pages update independently of docs):
  https://www.cloudflare.com/products/r2/
- **Bucket naming:** lowercase letters, numbers, and hyphens only; 3–63
  characters; cannot start or end with a hyphen; must be globally unique
  across Cloudflare (not just within your account).
  https://developers.cloudflare.com/r2/buckets/create-buckets/
- Bucket management operations (create/delete/configure) are rate-limited to
  50/second account-wide — irrelevant at LMS scale but note if the CI/deploy
  pipeline scripts bucket creation.
  https://developers.cloudflare.com/r2/platform/limits/
- **No native staging/production or environment concept** in bucket naming
  or R2's data model — this has to be a naming convention you enforce
  yourself (e.g. `fls-staging-public` vs `fls-prod-public`), same as any
  other cloud object store. No R2-specific constraint changes this.
- Up to **100 custom domains per bucket** — more than enough for any
  realistic per-bucket custom-domain need.
  https://developers.cloudflare.com/r2/platform/limits/

**Implication:** account limits and cost structure impose **no penalty** for
having four (or more) buckets instead of one — this part of the idea's
premise is safe regardless of how the versioning/lifecycle questions
resolve.

---

## 6. Caching and custom domains

**VERDICT: Confirmed**, with one operationally important caveat about
default caching when `Cache-Control` isn't set.

- A custom domain attached to an R2 bucket proxies requests through
  Cloudflare's network: first request at a given colo is a cache miss
  (fetched from R2), subsequent requests at that colo are served from cache
  per Cloudflare's cache rules / Tiered Cache.
  https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/
- **`Cache-Control` is per-object metadata**, set at upload time (e.g. via
  the S3 `PutObject` `Cache-Control` header or SDK equivalent) — there is no
  separate "bucket default Cache-Control" documented feature. The FLS
  codebase would need to set this header explicitly on every public upload
  (org logos) if it wants long CDN caching.
  https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/
- **Caveat (not fully resolved by official docs, corroborated by community
  reports):** if no `Cache-Control` is set, Cloudflare's default caching
  behavior for R2-backed custom domains does not guarantee long caching by
  default — official docs note Cloudflare "does not cache all file types by
  default" (e.g. HTML/JSON need an explicit Cache Rule), and community
  threads report 404/negative responses on custom-domain R2 buckets picking
  up unexpectedly long default cache TTLs. Treat "long CDN cache" for org
  logos as something that **must be set explicitly per-object on upload**,
  not assumed from a bucket-level default.
  https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/
  https://community.cloudflare.com/t/r2-with-custom-domain-setup-object-not-found-404-returns-cache-header-with-max-age-of-24-hours-rather-than-a-short-expiry/432485
  (community post, lower confidence, undated report but describes current
  custom-domain behavior)
- **`r2.dev` explicitly does not support caching, WAF, or bot management at
  all** — "You must use a Custom Domain for these features." It is also
  rate-limited and documented as dev/test-only, never production.
  https://developers.cloudflare.com/r2/buckets/public-buckets/
  https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/

**Implication:** the "long CDN cache" behavior the idea wants for
`fls-prod-public` requires (a) a custom domain, not `r2.dev`, and (b)
explicit `Cache-Control` headers set on every uploaded logo by the
application — this is an application-code requirement, not a benefit that
falls out of bucket separation itself. It doesn't argue for or against
separate buckets, but it is a load-bearing implementation detail the idea
doesn't currently call out.

---

## 7. Presigned URLs

**VERDICT: Confirmed.**

- R2 presigned URLs (via the S3-compatible API, SigV4) support an expiry
  from **1 second up to 7 days (604,800 seconds)** — same ceiling as S3's
  presigned URL max.
  https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- Presigned URLs work **only against the S3 API endpoint**
  (`<account>.r2.cloudflarestorage.com`), and explicitly **cannot be used
  with custom domains** — relevant if `fls-prod-course-media` or
  `fls-prod-learner-uploads` ever want a friendlier presigned-URL hostname;
  that's not supported.
  https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- **POST-based (HTML form) presigned uploads are not currently supported**
  on R2 — only presigned `GET`/`PUT`-style requests via query-string
  signing. If any future learner-upload flow assumed an S3
  `createPresignedPost`-style browser form upload, that will not work
  against R2 as documented today.
  https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- Signature parameters (resource, operation, expiry) cannot be tampered
  with post-hoc; modifying any bound parameter invalidates the signature
  (`403 SignatureDoesNotMatch`), same as S3 behavior.
  https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- **Checksum/ACL behavior differences already known to the codebase, and
  confirmed against the official S3-compatibility matrix:**
  - `PutObjectAcl`/`GetBucketAcl`/`PutBucketAcl` and the `x-amz-acl` /
    grant headers are **unimplemented/rejected** — R2 has no ACL model, only
    bucket-level public/private + token scoping (consistent with Q3/Q4).
    https://developers.cloudflare.com/r2/api/s3/api/
  - Checksum support is partial: **CRC64NVME** is accepted for full-object
    checksums; **CRC-32, CRC-32C, SHA-1, SHA-256** are supported only for
    *composite* checksums; several operations are explicitly missing
    `x-amz-checksum-algorithm` / `x-amz-sdk-checksum-algorithm` support. This
    matches the codebase's existing handling of boto3 checksum headers R2
    rejects and confirms it's not a boto3 misconfiguration but a documented
    R2 API gap.
    https://developers.cloudflare.com/r2/api/s3/api/

**Implication:** none of this changes the four-bucket-vs-one-bucket
decision — presigned URL behavior is per-object/per-request, not
per-bucket, and is identical regardless of how many buckets exist.

---

## 8. Other R2 characteristics relevant to the bucket-count decision

**VERDICT: Mixed** — several features are prefix-scopable (weakening the
"must separate into buckets" case), one is jurisdiction-related and bucket-
locked-in (strengthening it in a specific way), billing/CORS are neutral.

- **CORS configuration** is set per-bucket (a bucket's CORS policy is a
  single JSON document covering allowed origins/methods/headers for that
  bucket), not per-prefix. If `fls-prod-course-media` (needs CORS for
  browser-side video/PDF fetches) and `fls-prod-learner-uploads` (needs CORS
  for direct browser upload PUTs) ever needed materially different CORS
  policies, that *is* a real per-bucket-granularity argument for separation
  — CORS cannot be scoped narrower than the whole bucket.
  https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/cors/
- **Event notifications**: rules can be filtered by **prefix and/or suffix**
  within a bucket (e.g. only notify on `reports/*.pdf` creates), delivered
  to Cloudflare Queues, consumed by a Worker. Up to 100 rules per bucket,
  distinct object-create vs object-delete event types. Since these are
  already prefix-scopable, they don't require separate buckets either — a
  single bucket with prefix-filtered notification rules can distinguish
  "generated report was created" from "learner upload was created."
  https://developers.cloudflare.com/r2/buckets/event-notifications/
- **Jurisdictional restrictions** (data residency): a bucket's jurisdiction
  (EU / US / FedRAMP, Enterprise-only for FedRAMP) is set **at creation and
  is immutable thereafter**, and is enforced via a jurisdiction-specific S3
  endpoint hostname. This is **bucket-level and permanent** — if
  `fls-prod-learner-uploads` ever needs EU-only data residency (plausible
  given the idea already flags it for right-to-erasure/GDPR-adjacent
  concerns) while other buckets don't, that requirement **cannot be
  retrofitted onto an existing bucket** and **cannot be scoped to a prefix**
  — this is a genuine, currently-uncontested argument for giving
  learner-uploads its own bucket if EU data residency is ever required.
  https://developers.cloudflare.com/r2/reference/data-location/
- **Billing/egress model** is account-aggregated (Q5) — zero egress fees,
  storage and operations billed per-account regardless of bucket count, so
  splitting into four buckets has no cost penalty and no per-bucket metrics
  cost.
  https://developers.cloudflare.com/r2/platform/limits/
  https://www.cloudflare.com/products/r2/
- **Per-bucket metrics**: R2 exposes bucket-level analytics (storage,
  operations) in the dashboard/GraphQL Analytics API, so splitting into
  four buckets does give cleaner per-purpose observability (e.g. "how much
  are cohort-report PDFs costing us") that a single shared bucket with
  prefixes would require log-based post-processing to reconstruct. Not
  independently re-verified against a dedicated analytics doc in this
  research pass — treat as directionally true based on general R2
  dashboard behavior, not a specifically cited claim.

---

## Implications for the four-bucket layout

**Rationales that survive platform verification:**

1. **Public vs. private is a bucket-wide switch on R2** (Q3) — there is no
   native prefix-level public-read toggle. Splitting `fls-prod-public`
   (org logos) out from everything else is the *only* way to get anonymous
   public read without either exposing the rest of the bucket or building a
   custom Worker-based access-control layer. **This is the strongest
   surviving argument for separation.**
2. **API token scoping is bucket-granular, not prefix-granular** (Q4) —
   least-privilege write credentials (e.g. "the report-generation job can
   only write to `fls-prod-generated`") require bucket boundaries; a
   prefix-scoped token doesn't exist on R2. **Second strongest surviving
   argument**, though a single token *can* cover multiple named buckets, so
   this doesn't strictly require four separate buckets — it requires that
   whatever grouping is chosen be expressible as bucket boundaries.
3. **CORS is bucket-wide, not prefix-scoped** (Q8) — if course-media and
   learner-uploads ever need genuinely different CORS policies, that's a
   real (if currently unconfirmed-as-needed) argument for separation.
4. **Jurisdictional (data-residency) restrictions are bucket-level and
   immutable at creation** (Q8) — if `fls-prod-learner-uploads` needs EU
   data residency, it must be its own bucket from day one; this cannot be
   retrofitted or scoped to a prefix. Worth deciding explicitly now even if
   not implemented immediately, since bucket jurisdiction can't be changed
   later.
5. **Bucket count/cost is a non-issue** (Q5) — up to 1,000,000 buckets per
   account, no per-bucket billing, so there's no platform pressure toward
   consolidation.

**Rationales that do NOT survive and must be corrected in the spec:**

1. **"Object versioning on" for `fls-prod-learner-uploads` is not
   achievable — R2 has no object versioning at all** (Q1). This is the
   single biggest correction needed: the idea's stated protection mechanism
   for irreplaceable learner uploads does not exist on this platform. The
   spec must be rewritten to use one of R2's actual mechanisms instead:
   **Bucket Locks** (prefix-scoped, prevents delete/overwrite for a
   retention period or indefinitely — closest native fit) and/or an
   event-notification-driven backup-copy Worker to a separate bucket. Note
   that Bucket Locks also block emptying/deleting a locked bucket, which has
   deploy/teardown implications for any staging environment that mirrors
   production bucket-lock configuration.
2. **Lifecycle-based auto-expiry does not require a separate
   `fls-prod-generated` bucket** (Q2) — lifecycle rules are prefix-scopable,
   so "reports expire, uploads don't" is achievable with one bucket and two
   prefix-filtered lifecycle rules. If `fls-prod-generated` is kept separate,
   it should be justified by the API-token-scoping argument (Q4, "job that
   writes reports should only be able to write to the reports bucket") or
   the "never served by URL" access-pattern difference, not by a lifecycle
   capability gap — the lifecycle gap doesn't exist.
3. **Event-notification-based auditing of "a report was generated" vs "a
   learner uploaded a file" does not require separate buckets either**
   (Q8) — notification rules are prefix/suffix-filterable within a single
   bucket.

**Net assessment:** the four-bucket layout is still *defensible* on R2, but
for different reasons than the idea states. The strongest surviving
justifications are (a) public/private is bucket-wide so the public-logo
bucket must be separate, and (b) credential scoping is bucket-wide so
buckets are the natural unit for least-privilege write access — not
lifecycle/versioning granularity, which turns out to be prefix-scopable (or,
for versioning, nonexistent) and so doesn't by itself justify a bucket
boundary. The spec's rationale sections for `fls-prod-learner-uploads` (drop
"versioning," replace with Bucket Locks) and `fls-prod-generated` (reframe
around token-scoping/access-pattern rather than lifecycle capability) need
correction before this goes further.

---

status: ok
