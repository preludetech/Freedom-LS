# Research: Public vs Signed Organisation Logos (Cloudflare R2)

Scope: settle whether `Organisation.logo` should be served from a genuinely public R2 bucket
(`fls-prod-public`) or stay behind signed URLs in a private bucket, for the `prod_bucket_setup`
idea. Target cloud is Cloudflare R2 only.

Codebase facts used below (verified in this worktree, not inferred):

- `Organisation` extends `SiteAwareModel`, whose `id` is `models.UUIDField(primary_key=True,
  default=uuid.uuid4, editable=False)` (`freedom_ls/site_aware_models/models.py:80`). Organisation
  pks are **UUIDv4**, not sequential integers.
- `organisation_logo_upload_to` writes to `organisations/{instance.pk}{ext}`
  (`freedom_ls/organisations/models.py:17-25`) — the pk is the only path component, no filename
  interpolation.
- `build_s3_media_storage()` (`freedom_ls/deployment/storage.py`) already takes `querystring_auth`
  and `custom_domain` as independent per-alias options wired straight into
  `storages.backends.s3.S3Storage` — the public/private choice is a config toggle, not new code.
- Prior research (`spec_dd/3. done/.../research_cloudflare_r2_django_storages.md`) already
  established: R2 has no ACLs, public access is bucket-level via custom domain, and
  `querystring_auth=False` + `custom_domain` set is what turns off signing entirely.

## 1. Is the caching claim actually true?

**Yes — a fresh signed URL on every render is a genuine cache miss at both the browser and any
CDN in front of R2, by default.** This is not a theoretical concern; it is standard, well-documented
behaviour of both HTTP caching and Cloudflare's cache key.

- Browser HTTP caching is keyed on the full URL, including the query string. AWS SigV4 presigned
  URLs carry `X-Amz-Date`, `X-Amz-Expires`, and `X-Amz-Signature` in the query string, and the
  signature is derived from the signing timestamp, so a URL regenerated even a second later is
  byte-different. The community discussion on this exact pattern (S3 signed URLs behind
  Cloudflare) confirms it: "cache miss on S3 presigned URLs" is a reported, expected outcome —
  [Cloudflare Community: Cache miss on S3 presigned URLs](https://community.cloudflare.com/t/cache-miss-on-s3-presigned-urls/832774).
- Cloudflare's own cache key documentation states plainly that the **default cache key is host +
  path + full query string**, and the default caching level ("Standard") "delivers a different
  resource each time the query string changes" — [Cloudflare Cache docs: Cache keys](https://developers.cloudflare.com/cache/how-to/cache-keys/index.md),
  [Cloudflare Cache docs: Caching levels](https://developers.cloudflare.com/cache/how-to/set-caching-levels/).
  So even if the logo bucket sat behind Cloudflare's CDN via a custom domain, the CDN would treat
  every distinct signature as a distinct object and re-fetch from R2 origin each time, exactly
  like the browser.
- The mechanism is well characterised outside Cloudflare too: "unique query parameters in a
  presigned URL defeat CDN cache key matching... every presigned URL is unique per signature, so
  CDNs cannot share a cache entry across users" —
  [DigitalOcean Community: Presigned URLs vs. Spaces CDN](https://www.digitalocean.com/community/questions/presigned-urls-vs-spaces-cdn-can-i-get-both-private-access-and-edge-caching).
  django-storages itself has an open issue tracking exactly this: presigned URLs are generated at
  request time, so "a user refreshing the page will receive a new link each time, and the browser
  cache does not work" —
  [django-s3-storage #138: Caching with pre-signed url](https://github.com/etianen/django-s3-storage/issues/138),
  [django-storages #1222: Customisable expiration for s3 backend](https://github.com/jschneier/django-storages/issues/1222).

**On the "are the bytes actually re-downloaded" sub-question**: yes. A cache miss at either layer
means the request goes all the way to R2 for object bytes, not just a URL-string difference with
the same cached body reused. R2 has no egress fee (§3), so the *dollar* cost of re-fetching is
zero, but the *cost in requests and latency* is not: every render is a full network round trip
to R2's origin (tens of milliseconds at minimum, more on a cold edge) plus a Class B (read)
operation, at $0.36 per million —
[Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) via
[EgressCost.com: Cloudflare R2 Pricing 2026](https://egresscost.com/cloudflare/). For a chip that
renders on every course card and every cohort list row — i.e. potentially dozens of times per page
view, times every page view, times every learner — that is a lot of avoidable origin round trips
for an asset (a tenant's logo) that changes essentially never. The dollar cost is negligible at
FLS's likely scale; the latency and TTFB cost to every list/card render is the real one, and it is
paid on every single request instead of once. **Inference**: the actual, felt cost is "every course
card does a live network fetch instead of an instant cache hit," not "we're spending real money on
egress."

## 2. Can signed URLs be made cacheable?

**Yes, with a specific known technique (expiry bucketing), but django-storages does not support it
out of the box, and it trades away some of what "signed" is supposed to buy you.**

- **Rounded/bucketed expiry** — the standard name for this pattern. The signing timestamp
  (`X-Amz-Date`) is truncated backward to a fixed interval (e.g. every 10 minutes) before signing,
  so every request within that window produces an identical signed URL, which both the browser and
  a CDN can then cache normally. Detailed walkthrough (JavaScript, but the mechanism transfers
  directly to SigV4/boto3): "every signed-URL that is generated within some window of time has to
  use the same exact expiration date... the expiration time must exceed the rounding interval" —
  [Advanced Web Machinery: Cacheable S3 signed URLs](https://advancedweb.hu/cacheable-s3-signed-urls/).
  Independently documented pattern in Lucee/ColdFusion contexts too —
  [Ben Nadel: Calculating A Consistent Cache-Friendly Expiration Date For Signed-URLs](https://www.bennadel.com/blog/3686-calculating-a-consistent-cache-friendly-expiration-date-for-signed-urls-in-lucee-5-3-2-77.htm).
  **Not natively supported by django-storages or boto3's presigner**: neither exposes a
  "sign as-of this timestamp" parameter; the reference implementation above resorts to mocking the
  system clock (`timekeeper`) around the signing call, which is a hack, not a supported API. To do
  this properly in FLS would mean a custom `Storage.url()` override that calls
  `generate_presigned_url` with a manually rounded `X-Amz-Date`, or vendoring the SigV4 canonical
  request construction — real code to write and maintain, not a settings flag.
  **Security cost**: the URL is now valid, and stable, for the *entire bucket window*, not just
  from the moment of generation. Anyone who captures one instance of the URL can predict and reuse
  it until the bucket's `Expires` lapses; if the interval is an hour, that is effectively an
  hour-long shared secret handed out to every viewer simultaneously, which is a materially weaker
  guarantee than "each render gets its own short-lived credential." For non-sensitive content
  (a logo) this cost is close to irrelevant; for sensitive content it substantially narrows the gap
  between "signed" and "public."
- **Server-side caching of the generated URL** (Django cache, keyed by organisation) sidesteps
  needing the rounding trick for *browser* caching within a single app instance's cache TTL, because
  every request served from that cache entry gets byte-identical URL text — but this only helps if
  the cache TTL is coordinated with the URL's own `Expires`, and it still does nothing for a shared
  CDN cache in front of R2 unless the URL served to *different users* is also identical, which
  requires exactly the same bucketing as above. In practice this is the same fix, moved from
  "signing time" to "Django cache expiry," with the same tradeoff.
- **Long `querystring_expire` alone does not fix this.** `AWS_QUERYSTRING_EXPIRE` (default 3600s)
  controls how long the signature stays valid, but the signature is still generated fresh, at
  request time, on every call — the *validity window* being longer doesn't make the *URL* the same
  across two separate renders. This is confirmed by the FLS codebase itself:
  `build_s3_media_storage()` takes `querystring_expire` as a plain integer with no rounding logic
  (`freedom_ls/deployment/storage.py:15,30`) — stretching that number does not change the fact that
  each call to `.url` mints a new signature at the current instant.
  Reference: [django-storages: Amazon S3 backend, `AWS_QUERYSTRING_EXPIRE`](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html).
- **Serving through a Django view or a Cloudflare Worker** that fetches from R2 with the app's own
  credentials and streams/proxies the bytes to the client would let the *view's* response carry a
  stable, cacheable URL (e.g. `/organisations/<uuid>/logo/`) with its own `Cache-Control`, entirely
  decoupled from R2 signature churn. This is real and works, but it means every logo render now
  costs a Django request (or Worker invocation) in the hot path of every course card and cohort
  row — the same n+1-per-render cost the idea is trying to eliminate, just moved from "R2 signing"
  to "app server." It only pays off if the view/Worker response itself is then cached at the edge
  by URL — which brings you straight back to "this endpoint needs to behave like a public,
  cacheable URL," i.e. functionally the same as the public-bucket answer, with extra moving parts.

**Bottom line on Q2**: the mitigations exist, but the only one that gets genuine CDN-level caching
without new infrastructure is rounding the signature to a time bucket, and django-storages/boto3
do not support it as a configuration flag — it is custom signing code with a real (if modest for a
logo) security tradeoff. There is no cheap, supported way to have a private signed logo that
caches as well as a public one.

## 3. What is actually exposed by a public logo bucket?

**For FLS specifically: negligible. The pk is a UUIDv4 (not enumerable), listing is not possible on
a public R2 bucket, and R2 egress is free — so the only real exposure is "a logo URL is a
permanent, guessable-if-leaked pointer to a specific tenant," which is a low-severity, plausible-
deniability-adjacent confidentiality question, not a security hole.**

- **Enumerability — resolved concretely for this codebase, not hypothetically.** Organisation pks
  are UUIDv4 (`freedom_ls/site_aware_models/models.py:80`), and the logo path is
  `organisations/{pk}{ext}` with no other identifying token. A UUIDv4 has 122 bits of randomness;
  brute-force guessing a valid key is computationally infeasible —
  [OWASP: Insecure Direct Object Reference](https://owasp.org/www-community/attacks/insecure_direct_object_reference)
  and the broader IDOR literature agree that "switching from sequential integers to UUIDs reduces
  enumeration speed" to the point of being a practical mitigation, even though it is not a formal
  authorization control (see below) — [SentinelOne: What Is IDOR?](https://www.sentinelone.com/cybersecurity-101/cybersecurity/insecure-direct-object-reference/).
  **If FLS (or a downstream fork) ever changed to sequential integer pks**, this would flip:
  sequential IDs make enumeration trivial and leak record count/creation order, and automated tools
  can walk thousands of IDs in seconds — [AppSecure: IDOR Vulnerabilities](https://www.appsecure.security/blog/idor-vulnerabilities-detection-exploitation-and-impact).
  The conclusion below is contingent on the UUID pk holding; it should be called out explicitly if
  this idea is later generalised to a non-UUID entity.
- **What a leaked/guessed logo URL discloses**: the image bytes are a corporate mark that is, for
  the overwhelming majority of organisations, already public on the open web (their own site,
  LinkedIn, Companies House, etc.) — so disclosing the *bytes* is not new information. What could be
  new information, in a narrow set of cases, is **the existence of the tenant relationship
  itself** — i.e. confirmation that "Organisation X uses FLS," which some clients (a school running
  a confidential pilot, a company that hasn't announced a vendor) might not want disclosed ahead of
  their own announcement. This is a **product/confidentiality judgment call, not a technical
  vulnerability** — it is analogous to a "customer logos" wall being opt-in in some SaaS contracts.
  **Inference**: because the pk is a UUID and there's no listing, this is only exploitable by
  someone who already has the URL (e.g. it leaked in a screenshot, an email, or another disclosure)
  — it is not exploitable by scanning or crawling.
- **Object listing on a public R2 bucket: not possible, confirmed against Cloudflare's own docs.**
  "Currently, public buckets do not let you list the bucket contents at the root of your
  (sub)domain" — [Cloudflare R2 docs: Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/).
  This is the critical distinguisher the idea asked for: a public R2 custom domain serves *known
  keys only*; it does not expose a `ListObjectsV2`-style directory listing to anonymous callers.
  Combined with UUID pks, that means an outside party cannot discover the set of tenant logos at
  all — they can only fetch a logo if they already have (or can guess, which they functionally
  cannot) the specific UUID. A misconfiguration research writeup on R2 buckets corroborates the
  general shape of the risk (unauthenticated `r2.dev` exposure of *known* files, missing
  authorization middleware for sensitive files) without contradicting the no-default-listing
  behaviour —
  [Intigriti: Hacking misconfigured Cloudflare R2 buckets](https://www.intigriti.com/researchers/blog/hacking-tools/hacking-misconfigured-cloudflare-r2-buckets-a-complete-guide).
- **Hotlinking and egress cost: confirmed free, not a cost concern.** "R2 does not charge egress
  fees for data transferred to the Internet... egress is always free" —
  [Cloudflare R2: Egress-Free Object Storage](https://www.cloudflare.com/products/r2/),
  corroborated by [EgressCost.com: Cloudflare R2 Pricing 2026](https://egresscost.com/cloudflare/)
  and Cloudflare's original [R2 announcement](https://blog.cloudflare.com/introducing-r2-object-storage/).
  So even if a third party hotlinked an organisation's logo from their own site, FLS would pay
  nothing in egress — the only cost is Class B read operations at $0.36/million, immaterial for an
  asset this small and this rarely changed. **This removes what is normally the biggest practical
  argument against public buckets (uncontrolled bandwidth cost) entirely for R2.**

## 4. What do comparable multi-tenant SaaS products do?

**"Public bucket/CDN for branding assets (logos, avatars), private + signed for user content" is
the conventional, well-established split — logos specifically are treated as public by default
across the industry, with no authentication required to fetch them.**

- **Gravatar** — the longest-standing example — serves avatar images from a public, unauthenticated
  URL keyed only by a hash of the user's email
  (`https://gravatar.com/avatar/{hash}`), explicitly documented as requiring no authentication —
  [Gravatar Avatar API docs](https://apis.io/apis/gravatar/avatar-api/), [Gravatar](https://gravatar.com/).
  This is the same shape as the FLS proposal: an identifier-keyed image URL served publicly for
  fast, cacheable rendering everywhere the avatar appears.
- **GitHub** serves user/org avatars from `avatars.githubusercontent.com/u/{id}`, a public CDN path
  that is not gated by auth and is explicitly built for hot-path rendering across every page that
  shows a user or org — corroborated by community discussion of the avatar pipeline —
  [GitHub Community: Gravatar profile picture not displayed on GitHub](https://github.com/orgs/community/discussions/53616).
- **Slack** serves workspace/team icons from `avatars.slack-edge.com`, a dedicated CDN hostname
  (backed by CloudFront) separate from Slack's authenticated app traffic —
  [Netify: avatars.slack-edge.com hostname info](https://www.netify.ai/resources/hostnames/avatars.slack-edge.com).
  This mirrors the FLS proposal's shape exactly: a dedicated, cacheable, unauthenticated hostname
  carved out specifically for branding/identity images, kept separate from the app's private
  content paths.
- **General S3 practice write-ups** on splitting a bucket's ACL by content type independently
  confirm the pattern: "if you need a file to be truly public (like a company logo), set
  `ACL: public-read`... for user uploads, always use `ACL: private`" —
  [dev.to: Share Your AWS S3 Private Content With Others, Without Making It Public](https://dev.to/idrisrampurawala/share-your-aws-s3-private-content-with-others-without-making-it-public-4k59).
  This is the S3-ACL-era version of exactly the split the idea proposes; R2's lack of prefix-level
  ACLs (established in prior FLS research) is what forces it to be a *bucket* split rather than an
  object-flag split, but the underlying industry convention — public branding, private content —
  is the same one FLS would be following, not inventing.

**Conclusion for Q4**: FLS's proposed split (public bucket for logos/branding, private signed
buckets for course media, learner uploads, and generated reports) matches how comparable products
handle the same category of asset. No example was found of a mainstream SaaS product treating
tenant/user branding logos as sensitive, signed content.

## 5. Does the choice change the bucket count?

**Yes, directly — this is the one concrete, structural consequence of the decision.** If logos stay
signed, `fls-prod-public` has no remaining reason to exist and the layout drops from four buckets to
three.

**Public branch (current idea, 4 buckets)**:

| Bucket | Contents | Read policy |
|---|---|---|
| `fls-prod-public` | Organisation logos; future public branding | Public read, custom domain, long `Cache-Control` |
| `fls-prod-course-media` | `content_engine.File` | Private, signed URLs |
| `fls-prod-learner-uploads` | Future learner documents/profile pictures | Private, signed URLs |
| `fls-prod-generated` | Cohort reports, certificates | Private, streamed by Django |

**Signed branch (3 buckets)**: `Organisation.logo` moves into `fls-prod-course-media` — both are
private-signed, admin/operator-supplied (not learner-uploaded), and non-personal. The idea document
itself identifies this as "the tempting cut" for exactly this reason
(`idea.md:98`), and rejects it solely on the caching argument this research file exists to test.
With logos merged in:

| Bucket | Contents | Read policy |
|---|---|---|
| `fls-prod-course-media` | `content_engine.File` **+ Organisation logos** | Private, signed URLs |
| `fls-prod-learner-uploads` | Future learner documents/profile pictures | Private, signed URLs |
| `fls-prod-generated` | Cohort reports, certificates | Private, streamed by Django |

**What is lost in each branch**:

- **Staying public (4 buckets) loses**: one more bucket to provision, one more credential/token to
  scope, one more custom domain and DNS record to manage per deployment, and (per §2/§3) a
  permanently guessable-if-leaked URL for every organisation's logo, with the residual — low but
  non-zero — "existence of tenant relationship" disclosure from §3.
- **Merging into course-media (3 buckets) loses**: real caching. Per §1/§2, every logo render stays
  a live, uncached fetch against R2 unless the rounded-signature technique (§2) is implemented and
  maintained as custom signing code django-storages does not provide. That cost recurs on every
  course-card and cohort-row render, forever, for every deployment, versus a one-time bucket
  provisioning cost paid once per environment.

This is the real shape of the tradeoff: **one extra bucket to provision, versus a caching
degradation that is paid continuously, in the hot path, for the lifetime of the product** — not
"public is a security risk," which §3 shows is not really true for this codebase.

## Recommendation

**Stay public. Keep `fls-prod-public` as its own bucket, exactly as the idea specifies.** The
caching claim in the idea is verified true (§1), the only real mitigation for keeping logos signed
is custom, unsupported signing code with its own security tradeoff (§2), the actual exposure of a
public logo bucket is negligible given FLS's UUID pks and R2's no-listing/no-egress-fee behaviour
(§3), and this is the conventional choice made by every comparable product examined (§4). The one
real cost — provisioning a fourth bucket and custom domain — is a one-time, per-deployment setup
cost, not a recurring one, which is a good trade against a caching penalty that recurs on every
render for the life of the product.

What would flip this call:

- **If Organisation pks were ever changed from UUIDv4 to a sequential/guessable identifier**, the
  enumeration risk in §3 becomes real (trivial crawling of all tenant logos), and the "existence of
  tenant relationship" disclosure stops being "only exploitable if the URL already leaked" and
  becomes "trivially discoverable by anyone." That alone would be enough to revisit this
  recommendation.
- **If FLS ever needs to represent an organisation whose relationship with the platform is
  contractually confidential** (an NDA'd pilot, a white-label deployment that must not reveal the
  underlying vendor) as a routine rather than exceptional case, a per-organisation "logo visibility"
  flag routed through the private bucket (accepting the caching cost for that minority of tenants
  only) would be more defensible than a blanket policy change.
- **If django-storages/boto3 later ships first-class support for rounded/bucketed presigned-URL
  expiry** (§2), the caching argument weakens considerably and the calculus shifts back toward "one
  fewer bucket to operate," since the security cost of a signed-but-cacheable URL is small for a
  non-sensitive asset like a logo.

status: ok
