# Media and file storage for FreedomLS: Cloudflare R2

**Cloudflare R2 is the right object storage backend for FreedomLS Phase 1.** The user's domain is already on Cloudflare, R2 has zero egress fees, the Johannesburg PoP terminates traffic locally, and the S3-compatible API plugs straight into `django-storages` with a handful of settings. Two buckets (one public, one private), a custom domain on the public bucket for cached delivery, and signed URLs for private files give a clean separation that maps onto FLS's mix of landing-page imagery, profile photos, assignment uploads, and gated course content.

Bottom line up front: **start on R2 now, in two buckets, with `django-storages`, signed URLs for private content, and a `media.<domain>` custom domain for public assets**. Do not start on local disk — the cost of moving later is meaningfully higher than the cost of integrating now.

## 1. R2 vs alternatives at FLS scale

Phase 1 footprint is 5–50 GB across course content, profile photos, assignment uploads, but traffic is read-heavy and spiky (a course launch, a 200 MB video, a marketing push can blow a fixed bandwidth budget). Egress pricing dominates the comparison.

Pricing matrix (May 2026):

| Provider | Storage / GB-mo | Egress / GB | Class A (writes) | Class B (reads) | Free tier |
|---|---|---|---|---|---|
| **Cloudflare R2** | $0.015 | **$0.00** | $4.50/M | $0.36/M | 10 GB, 1M Class A, 10M Class B / mo |
| Backblaze B2 | $0.006 | $0.01 (free via Bandwidth Alliance to Cloudflare) | $0.004/10k | $0.004/10k | 10 GB |
| AWS S3 Standard | $0.023 | ~$0.09 | $5/M | $0.40/M | 5 GB / 12 mo only |
| Vultr Object Storage | $0.018 | $0.01 above included | bundled | bundled | none, $18/mo minimum |
| Local disk | "free" | bound to VPS quota | n/a | n/a | n/a |

Key takeaways:
- **R2 has zero egress, period** — over the S3 API, `r2.dev`, and custom domains.
- **B2 + Cloudflare** is technically cheaper at-rest (2.5× cheaper) but adds vendor and operational complexity for tens-of-cents savings at Phase 1 volume.
- **Vultr Object Storage** is bundled at $18/mo with 1 TB included — wildly over-provisioned for Phase 1.
- **Local disk** turns the VPS stateful, has no CDN, no durability, and burns the VPS bandwidth quota.

Latency: R2 buckets live in regional storage clusters (`enam`, `weur`, `eeur`, `apac`, `oc`); the Cloudflare PoP in Johannesburg (Cloudflare's first African data centre) is what browsers and the VPS talk to. Cached reads are single-digit ms from JNB. Cache misses and writes round-trip to the storage region (~150–250 ms to `weur`/`enam`). R2 Local Uploads (Feb 2026) terminates uploads at the PoP and replicates async, ~75% faster cross-region writes.

Why R2 specifically for FLS: user already runs the domain on Cloudflare → no new vendor, custom domain is one click, egress to Cloudflare CDN is free, and Workers/Images/Stream are adjacent if needed later.

**Verdict: R2 is the right primary backend.** Keep B2 in mind as a future cold/archive tier above 1 TB.

## 2. Django integration

Use `django-storages[s3]>=1.14.6` (which pulls boto3). Add via `uv add 'django-storages[s3]'`.

Five settings that must be right for R2:

| Setting | Value | Why |
|---|---|---|
| `endpoint_url` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | R2 hostname |
| `region_name` | `auto` | R2 ignores it but SigV4 requires *something* |
| `signature_version` | `s3v4` | R2 only supports SigV4 |
| `addressing_style` | `virtual` | R2 default |
| `access_key` / `secret_key` | from R2 token | Generated under R2 → Manage R2 API Tokens, scoped to specific buckets |

Django 6 `STORAGES` config with three storages: `default` (private media), `public_media` (public via custom domain), `staticfiles`:

```python
import os

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

_R2_COMMON = {
    "endpoint_url": R2_ENDPOINT_URL,
    "access_key": os.environ["R2_ACCESS_KEY_ID"],
    "secret_key": os.environ["R2_SECRET_ACCESS_KEY"],
    "region_name": "auto",
    "signature_version": "s3v4",
    "addressing_style": "virtual",
    "file_overwrite": False,
    "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_R2_COMMON,
            "bucket_name": os.environ["R2_PRIVATE_BUCKET"],
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 3600,
        },
    },
    "public_media": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_R2_COMMON,
            "bucket_name": os.environ["R2_PUBLIC_BUCKET"],
            "custom_domain": os.environ["R2_PUBLIC_CUSTOM_DOMAIN"],
            "querystring_auth": False,
            "url_protocol": "https:",
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
```

Notes:
- `querystring_auth=True` on private = `.url` returns signed URLs. Must be `False` on public, otherwise `?X-Amz-...` defeats CDN caching.
- `file_overwrite=False` so concurrent same-named uploads don't clobber.
- `default_acl=None` — R2 ignores ACLs; bucket-level public/private setting governs access.
- `custom_domain` only set on public storage.
- `location` (key prefix) — use for tenant prefixing not env separation; use separate buckets for envs.

Per-field storage selection:

```python
from django.core.files.storage import storages
class CourseLandingImage(models.Model):
    image = models.ImageField(storage=lambda: storages["public_media"], upload_to="courses/landing/")
```

Models default to `storages["default"]` (the private bucket) — the safe default.

## 3. Public vs private bucket strategy

**Two buckets, not one with mixed objects.** Reasons:

1. Blast radius — misconfigured public flip can only leak already-public assets.
2. R2 public access is bucket-level (no per-object ACLs); mixing modes in one bucket means Worker logic.
3. Different cache rules — public wants long immutable, private must not be cached by intermediaries.
4. Different tokens — public bucket can be read-only for app server.

Layout:

| Bucket | Visibility | Custom domain | Use cases |
|---|---|---|---|
| `fls-<env>-public` | Public via custom domain | `media.<domain>` | Landing imagery, public course thumbnails, site logos |
| `fls-<env>-private` | Private (S3 API only) | none | Assignment uploads, gated course content, profile photos, anything tied to enrolment |

Per-env separation, never share. Profile photos go in **private** even if visible inside a cohort — match the site-aware safe default.

By app: `content_engine` mixed (private-by-default, public for preview material), `student_management` private, `student_progress` private, `accounts` private, marketing public.

## 4. Serving private files

Three patterns:

**A. Signed R2 URLs (recommended).** Django checks auth, generates a presigned GET, redirects/embeds it. Browser fetches direct from R2 edge.

```python
def view_assignment(request, pk):
    upload = get_object_or_404(AssignmentUpload, pk=pk)
    if not user_can_view(request.user, upload):
        raise PermissionDenied
    return redirect(upload.file.storage.url(upload.file.name, expire=300))
```

Pros: no worker held during download, edge-served, simple, works the same in dev/staging/prod. Cons: URL is bearer-token-equivalent for its expiry window (mitigate with short expiries); not suitable for "single-session" stream enforcement (need Cloudflare Stream tokens for that).

**B. Proxy through Django.** Holds a worker for the entire transfer. Acceptable only for sub-MB content (tiny avatar thumbnails). Catastrophic on a small VPS for anything bigger.

**C. X-Accel-Redirect via Caddy.** **Wrong fit here** — files aren't on the VPS disk, so Caddy would have to fetch from R2 (double-hopping bytes), the whole point of R2 is to take bytes off the VPS, and Caddy's X-Accel support is less battle-tested than nginx's. X-Accel is right when files are on local disk; with R2 it's replaced by signed URLs.

**Recommendation: signed URLs, with expiries by content type:**
- Assignment downloads, gated course downloads: 5 min
- Streamed video/audio: 15–30 min (single play session)
- "Download for offline": 1 hour
- Profile photos in lists: 15 min, cache the URL per-request to avoid signing per row

Multi-tenant access check stays in Django (existing site-aware `request.user` + enrolment lookup). Storage layer stays dumb. For pages listing many files, sign lazily via template tag and don't cache the page response aggressively.

## 5. Custom domain + public assets

Attach `media.<domain>` to the public bucket. **Don't CNAME `r2.dev`** — it's rate-limited, has no cache controls, and Cloudflare explicitly discourages it. Custom domains get all of Cloudflare's edge: WAF, cache rules, bot management, hotlink protection. R2-to-custom-domain egress is free.

Setup: Cloudflare dashboard → R2 → bucket → Custom Domains → Connect → `media.<domain>`. CNAME and TLS handled automatically. Add a Cache Rule scoped to `media.<domain>`: "Cache Everything", Edge TTL 1 month, Browser TTL 1 day. Set `Cache-Control: public, max-age=31536000, immutable` on uploads (`object_parameters` block above).

Cloudflare's default cache list only covers images/CSS/JS/fonts — set the explicit Cache Everything rule to cache PDFs/video previews etc. Smart Tiered Cache helps once traffic is non-trivial.

Realistic Phase 1 cost: under $5/month including both buckets. Often under $1.

## 6. Upload patterns

**Through Django**: single auth check, validation/scan/resize before commit, CSRF works, but holds a worker for the whole upload and burns VPS bandwidth twice.

**Direct browser → R2 (presigned PUT/POST)**: bytes never touch VPS, worker holds for ms, scales with concurrent uploads, but validation happens *after* upload (staging-prefix → validate → move pattern) and CSRF is replaced by the URL signature.

**Phase 1 recommendation: hybrid by size.**
- **<5 MB through Django** — avatars, profile photos, document attachments. Simple.
- **>5 MB direct presigned PUT** — videos, large PDFs, bulk uploads. Django returns presigned URL + confirm-callback URL; frontend PUTs then calls confirm; Django HEADs the object to verify and creates the model record.

For Phase 1 you can ship through-Django for everything and document the 5 MB threshold in code so the integration point for presigned PUT is obvious when an educator first hits it.

Virus scanning: out of scope for Phase 1. When needed, Cloudflare Worker on R2 event notification + ClamAV on staging-prefix is the standard pattern. TODO comment in the upload code path.

## 7. Multi-tenant key prefixing

FLS multi-tenancy via Sites + `SiteAwareModel`. Mirror that in the storage layer:

```
<bucket>/sites/<site_id>/
  content/courses/<course_id>/...
  uploads/assignments/<user_id>/<upload_id>/<filename>
  uploads/profiles/<user_id>/<filename>
  misc/
```

`upload_to` callable encodes the site:

```python
def assignment_upload_path(instance, filename):
    return f"sites/{instance.site_id}/uploads/assignments/{instance.user_id}/{instance.pk}/{filename}"
```

Implications: prefix-scoped lifecycle rules (delete tenant on closure: `r2cli rm --recursive bucket/sites/<id>/`), per-tenant analytics via daily prefix-listing, simple `aws s3 cp --recursive` exports for portability. R2 tokens scope to bucket but not prefix — so per-tenant credentials would mean per-tenant buckets, which is overkill. App-server-checks-tenancy is correct.

**Don't put tenant in bucket name** — R2 has a 1000-bucket limit per account and bucket create/delete is heavyweight. Prefixes in one bucket are the standard S3 pattern and align with lifecycle rules.

## 8. Backup strategy

R2 durability is 11 nines (99.999999999%), erasure coding + full replication across data centres in a region, synchronous-write semantics (HTTP 200 only after persistence). Hardware loss is effectively a non-issue.

Backups protect different threats: app bugs (mass-delete migrations), compromised credentials, tenant disputes ("restore this from 6 months ago"), compliance.

**Phase 1 posture:**
- Enable **R2 Object Versioning** on both buckets — S3-style versioning, deletes become delete-markers, prior versions recoverable.
- **Lifecycle rule expiring non-current versions after 90 days** — bounds the versioned storage cost.
- **Restrict the prod app token** to PutObject/GetObject/DeleteObject on specific buckets, no `s3:DeleteBucket`, no admin perms. Token compromise can delete (recoverable via versioning) but not destroy the bucket.
- **Skip cross-vendor replication for Phase 1.** Reconsider when a tenant SLA, multi-TB volume, or audit demands it.
- **Postgres backups matter more than R2 backups** — DB stores the references; without it intact R2 objects are unfindable. Ensure the existing Phase 1 Postgres backup plan covers this.

When/if cross-vendor needed: nightly `rclone sync` R2 → B2 (Bandwidth Alliance keeps egress free). Phase 3 concern.

## 9. Migration path: start on R2 now

Don't start on local disk. Reasons:

1. Migration cost (one-shot copy + dual-write window + per-model storage backend updates + retesting) is a 1–2 week diversion.
2. Local-disk media adds a stateful directory to back up, restore, and migrate when the VPS is replaced. Today FLS is "Postgres + stateless containers" — keep it that way.
3. No CDN — local disk serves Johannesburg-only.
4. R2 is cheaper than the VPS bandwidth quota would be — a single 100 MB course video viewed 200× = 20 GB of VPS bandwidth that R2 would have served for free.
5. Phase 1 R2 cost is <$5/mo, often <$1. There's no saving to defer for.

**Phase 1 sequence:**
1. Create R2 account, four buckets (`fls-prod-public`, `fls-prod-private`, `fls-staging-public`, `fls-staging-private`), per-env tokens.
2. Attach `media.<domain>` and `media-staging.<domain>` custom domains.
3. `uv add 'django-storages[s3]'`, configure `STORAGES` per section 2, env-var the credentials.
4. Update `content_engine` and any `FileField`/`ImageField` to use the right storage.
5. Enable versioning + 90-day non-current lifecycle on prod buckets.
6. **Local dev:** keep `FileSystemStorage` against `media/` by default; toggle R2 with an env var when QAing against R2 specifically. Don't require every dev to have R2 credentials.

Cost ceiling check: 10 tenants × 1,000 students × 500 MB = 5 TB → $75/mo storage + ~$18/mo Class B reads + $0 egress = ~$90/mo at 50× the Phase 1 target. Still cheaper than the VPS bandwidth overage you'd pay serving the same traffic from local disk.

## Phase 1 recommendation, condensed

1. Cloudflare R2 as the object storage backend.
2. Two buckets per env: `fls-<env>-public` (custom domain) + `fls-<env>-private` (signed URLs).
3. `media.<domain>` custom domain on public bucket; "Cache Everything" rule, 1-month edge TTL, immutable Cache-Control on uploads.
4. Signed URLs for private files, Django does the auth check, default 1-hour expiry, 5-min for sensitive content. No proxy through Django (except sub-MB), no X-Accel-Redirect.
5. Through-Django uploads in Phase 1; document 5 MB threshold for future presigned-PUT path.
6. `sites/<site_id>/<category>/...` keys in both buckets.
7. R2 versioning + 90-day non-current lifecycle. No cross-vendor replication yet.
8. Don't start on local disk.
9. Local dev: FileSystemStorage by default, R2 toggleable via env var.

Fits in: one `STORAGES` block, one `public_media_storage()` helper, tenant-prefixed `upload_to=`, one "signed URL after access check" utility. No new app, no new abstraction layer.

## References

- Cloudflare R2 docs — Pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare R2 docs — S3 API compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- Cloudflare R2 docs — boto3 examples: https://developers.cloudflare.com/r2/examples/aws/boto3/
- Cloudflare R2 docs — Public buckets: https://developers.cloudflare.com/r2/buckets/public-buckets/
- Cloudflare R2 docs — Presigned URLs: https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- Cloudflare R2 docs — Durability: https://developers.cloudflare.com/r2/reference/durability/
- Cloudflare R2 docs — Data location & LocationHint: https://developers.cloudflare.com/r2/reference/data-location/
- Cloudflare Cache + R2 interaction: https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/
- Cloudflare blog — Johannesburg DC: https://blog.cloudflare.com/johannesburg-cloudflares-30th-data-center/
- django-storages — Amazon S3 backend: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
- django-storages — multiple S3 backends: https://unfoldadmin.com/blog/configuring-django-storages-s3/
- Backblaze B2 pricing: https://www.backblaze.com/cloud-storage/pricing
- Vultr Object Storage pricing: https://www.vultr.com/products/object-storage/
- Caddy reverse_proxy: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- django-private-storage (reference only): https://github.com/edoburu/django-private-storage
