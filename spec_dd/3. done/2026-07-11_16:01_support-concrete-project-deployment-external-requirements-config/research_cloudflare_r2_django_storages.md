# Research: Cloudflare R2 media storage via django-storages

## Summary

Cloudflare R2 exposes an S3-compatible API, so `django-storages`'
`storages.backends.s3.S3Storage` (boto3-based) works with R2 with a handful of
R2-specific settings. The two things most deployments get wrong are:

1. **R2 does not support S3 ACLs at all** (bucket- or object-level). Any
   `default_acl` / `x-amz-acl` value on `PutObject` is rejected/unsupported.
   Public access must instead come from a *publicly-exposed bucket*
   (`r2.dev` dev subdomain or a connected custom domain), not from
   `public-read` ACLs.
2. **Recent boto3 (>= 1.35.99) sends checksum headers R2 doesn't implement**
   (`x-amz-sdk-checksum-algorithm`, `x-amz-checksum-crc32`, etc.), which R2
   rejects with `InvalidArgument` / "Unsupported header" errors on upload.
   This must be worked around via `client_config`.

FLS's existing `settings_prod.py` S3 block (`bucket_name, access_key,
secret_key, endpoint_url, region_name, default_acl, signature_version`) is
close to correct but needs: `region_name = "auto"`, `default_acl` dropped
entirely (not just left `None` via env, since R2 doesn't want the parameter
sent at all in some client paths), a `client_config` checksum workaround, and
(if serving media publicly) `custom_domain` + `querystring_auth = False`.

## 1. Correct S3Storage OPTIONS for R2

Per the official django-storages Cloudflare R2 doc, follow the base
Amazon S3 backend docs with these R2-specific exceptions:

- `endpoint_url`: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
  (the account ID is the Cloudflare account ID, not the bucket name).
- `access_key` / `secret_key`: an R2 **API token's** key ID / secret (created
  under R2 > Manage API Tokens), not a global Cloudflare API key.
- `region_name`: R2 only has one logical region, `"auto"`. Cloudflare's own
  compat notes say an empty value or `"us-east-1"` alias to `auto`, but you
  should set it explicitly to `"auto"` for clarity and to avoid boto3
  region-inference quirks.
- `signature_version`: `"s3v4"` (this is what the existing code already has
  — correct, keep it).

Reference: https://django-storages.readthedocs.io/en/latest/backends/s3_compatible/cloudflare-r2.html

## 2. ACLs — the big gotcha

Cloudflare's own S3-compatibility matrix states plainly that R2 does **not**
implement object/bucket ACL operations:

- `PutObjectAcl`, `GetObjectAcl`, `GetBucketAcl`, `PutBucketAcl`: unimplemented.
- Canned ACLs on `PutObject` (the `x-amz-acl` header, e.g. `public-read`,
  `private`) are also unimplemented — R2 ignores/rejects them.

Practical implication for `default_acl` / `AWS_DEFAULT_ACL`:
- **Do not set `default_acl` to any ACL string** (`public-read`, `private`,
  etc.) for R2 — it has no effect and, depending on client/library version,
  can trigger an error response rather than being silently ignored.
- The safest setting is to **omit `default_acl` entirely** (don't pass the
  key at all) rather than passing `None` from an unset env var — some
  django-storages/boto3 code paths treat an explicit `None` differently from
  a missing key, and either way there is no reason to send an ACL header to
  R2.
- Similarly avoid `AWS_S3_OBJECT_PARAMETERS` entries that imply ACL grants.
  `CacheControl`, `ContentType`, etc. object parameters are fine — R2 does
  support those since they're plain object metadata, not ACL grants.

### How to actually make media public on R2 (two approaches)

**A. Public bucket (recommended for a public media library like FLS course
content):**
- Enable the bucket's "Public Development URL" (an `r2.dev` subdomain) for
  quick testing — Cloudflare explicitly says r2.dev is rate-limited and
  "should only be used for development purposes", not production.
- For production, connect a **custom domain** to the bucket (R2 bucket
  Settings > Custom Domains > Add, pointing e.g. `media.example.com` at the
  bucket via Cloudflare DNS). This is the supported production path and also
  gets you Cloudflare's cache/edge features in front of the bucket.
- With a public bucket + custom domain, django-storages just needs to know
  the domain to build public URLs from (`custom_domain`) — see §3. No ACLs,
  no signing, needed at read time.

**B. Signed/presigned URLs (private bucket):**
- Leave the bucket unlisted/private (no public dev URL, no custom domain
  serving raw contents) and let django-storages generate presigned GET URLs
  per request (the default S3Storage behavior when `custom_domain` isn't
  set and the bucket isn't public) — this uses `querystring_auth=True`
  (the default) so URLs carry a time-limited signature.
- This is heavier (a signed request per file, shorter cache lifetimes,
  cannot be cached cleanly by Cloudflare/browsers as a stable URL) — usually
  only worth it for content that must stay access-controlled at the storage
  layer rather than at the Django view layer.
- Given FLS already gates media access through the LMS's own auth (student
  enrollment, course visibility, etc. — access control happens at the
  Django view layer, not the storage layer), **the public-bucket +
  custom-domain approach (A) is the better fit** unless there's a
  requirement for storage-level access control independent of the app.

References:
https://developers.cloudflare.com/r2/api/s3/api/ ,
https://developers.cloudflare.com/r2/buckets/public-buckets/

## 3. `AWS_QUERYSTRING_AUTH` / custom domain for clean, cacheable URLs

If serving public media (approach A above):
- Set `custom_domain` to the domain connected to the bucket, e.g.
  `"media.example.com"`. django-storages then builds media URLs as
  `https://media.example.com/<key>` instead of hitting the R2 API endpoint
  with a signed query string.
- Set `querystring_auth = False` so that even if `custom_domain` weren't
  set, no `X-Amz-Signature`/`X-Amz-Expires` query params get appended — this
  matters because signed query strings differ per request/session and defeat
  HTTP/edge caching (Cloudflare, browsers) and produce ugly, non-stable URLs
  in HTML.
- With a public custom domain + `querystring_auth=False`, standard
  `Cache-Control` response headers (set via `object_parameters`, see below)
  become effective for edge/browser caching, which is the point of putting
  R2 behind Cloudflare in the first place.

## 4. Env var / config surface for a concrete deployment

| Setting (django-storages OPTIONS key) | Env var (suggested) | Secret or config? | Notes |
|---|---|---|---|
| `bucket_name` | `AWS_STORAGE_BUCKET_NAME` (existing) | config | Also the gate that turns on S3/R2 storage vs FileSystemStorage fallback |
| `access_key` | `AWS_S3_ACCESS_KEY_ID` (existing) | **secret** | R2 API token key ID |
| `secret_key` | `AWS_S3_SECRET_ACCESS_KEY` (existing) | **secret** | R2 API token secret |
| `endpoint_url` | `AWS_S3_ENDPOINT_URL` (existing) | config | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` — account ID is not secret but is deployment-specific config |
| `region_name` | `AWS_S3_REGION_NAME` (existing) | config | Should always resolve to `"auto"` for R2; consider hardcoding `"auto"` rather than reading from env, or default the env var to `"auto"` |
| `custom_domain` | new, e.g. `AWS_S3_CUSTOM_DOMAIN` | config | Only needed if serving media publicly through a connected domain |
| `querystring_auth` | new, e.g. `AWS_QUERYSTRING_AUTH` (bool) | config | `False` when using `custom_domain`/public bucket; `True` (default) for signed-URL mode |
| — (remove) | `AWS_DEFAULT_ACL` (existing) | n/a | **Drop this from config surface entirely** for R2 — see §2 |
| `client_config` checksum workaround | not env-driven, set in code | n/a | See §6 — needs to be a `botocore.config.Config(...)` object, can't come from an env var directly |

Nothing else (no `AWS_S3_OBJECT_PARAMETERS` cache-control values, etc.) is
strictly required, but a `Cache-Control` object parameter is recommended if
media is meant to be edge/browser-cached (see §6).

## 5. Django 6 `STORAGES` setting

The `STORAGES` dict form (introduced in Django 4.2, still current/recommended
in Django 6) is confirmed correct and is exactly what the existing
`settings_prod.py` uses:

```python
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": { ... },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

No Django-6-specific changes are needed here — `STORAGES["default"]` is the
supported mechanism for configuring the default file storage backend, and
FLS's split of `default` (media, R2/FileSystemStorage) vs `staticfiles`
(WhiteNoise) matches the parent spec's intent (media on object storage,
static from the image via WhiteNoise).

## 6. Gotchas

- **Checksum header incompatibility (important, likely to bite in
  production):** boto3 >= 1.35.99 enables data-integrity checksum headers
  by default (`x-amz-sdk-checksum-algorithm`, `x-amz-checksum-crc32`, etc.)
  on S3 requests. R2 does not implement these headers on most operations and
  returns errors like `Unsupported header 'x-amz-sdk-checksum-algorithm'
  received` on `PutObject`. R2 only supports CRC-64/NVME for full-object
  checksums and CRC-32/CRC-32C/SHA-1/SHA-256 for *composite* checksums — not
  the simple per-request headers boto3 now sends by default. Workaround
  (documented in django-storages issue tracker for the same problem with
  Backblaze B2, which is also S3-compatible and affected identically):
  ```python
  from botocore.config import Config

  "client_config": Config(
      request_checksum_calculation="when_required",
      response_checksum_validation="when_required",
  )
  ```
  Add this as an extra `OPTIONS["client_config"]` entry. This can't be
  env-var-driven (it's a Python object), so it should be hardcoded in
  `settings_prod.py` whenever the R2/S3 branch is active, not left as an
  optional knob.
- **CORS**: R2 does implement `GetBucketCors`/`PutBucketCors`/
  `DeleteBucketCors`, so if the frontend ever needs direct browser
  upload/download against the R2 endpoint (rather than always proxying
  through Django), CORS rules can be configured via the R2 dashboard or the
  S3 API exactly like on AWS S3. Not needed for the base case of Django
  writing media server-side and serving via public custom domain/WhiteNoise
  pattern, but worth flagging if any client-side direct-upload feature is
  ever built.
- **Cache-Control headers**: since public media will likely sit behind
  Cloudflare's edge cache (via the custom domain), setting
  `object_parameters = {"CacheControl": "max-age=..."}` (or similar) on
  `S3Storage` is worth doing so uploaded objects get sensible cache headers
  rather than none — otherwise Cloudflare's edge caching behavior for the
  custom domain will depend entirely on its own cache-rules configuration
  rather than origin headers.
- **`r2.dev` is dev-only**: don't rely on it for production public media —
  Cloudflare explicitly documents it as rate-limited/for development; use a
  connected custom domain for production public buckets.
- **API token scope**: R2 API tokens (created in the Cloudflare dashboard
  under R2 > Manage API Tokens) can be scoped to a single bucket with
  read/write or read-only permissions — use a scoped, least-privilege token
  per deployment rather than an account-wide token.
- **`region_name` correctness matters for signing, not routing**: since
  `endpoint_url` fully overrides where requests go, `region_name` for R2 is
  used only in the SigV4 signing calculation — it must be `"auto"` to match
  what R2 expects when validating the signature, not left blank or set to
  an AWS region name.

## 7. Reconciliation note — existing `settings_prod.py` S3 block

Existing block (paraphrased from the codebase):

```python
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
if AWS_STORAGE_BUCKET_NAME:
    AWS_S3_ACCESS_KEY_ID = os.getenv("AWS_S3_ACCESS_KEY_ID")
    AWS_S3_SECRET_ACCESS_KEY = os.getenv("AWS_S3_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
    AWS_DEFAULT_ACL = os.getenv("AWS_DEFAULT_ACL")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")
    default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "access_key": AWS_S3_ACCESS_KEY_ID,
            "secret_key": AWS_S3_SECRET_ACCESS_KEY,
            "endpoint_url": AWS_S3_ENDPOINT_URL,
            "region_name": AWS_S3_REGION_NAME,
            "default_acl": AWS_DEFAULT_ACL,
            "signature_version": "s3v4",
        },
    }
else:
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
```

Assessment against R2 best practice:

- **Backend class** (`storages.backends.s3.S3Storage`): correct, keep.
- **`signature_version: "s3v4"`**: correct, keep.
- **Env-var gating on `AWS_STORAGE_BUCKET_NAME`** with FileSystemStorage
  fallback: reasonable pattern, keep — but this makes the config generic
  S3-or-not rather than R2-specific; that's fine as long as region/ACL
  defaults are R2-safe.
- **`region_name` from a bare env var**: should default to `"auto"` when
  targeting R2 — either hardcode `"auto"` in this settings module (simplest,
  since this deployment's target is specifically R2) or make the env var
  default to `"auto"` (`os.getenv("AWS_S3_REGION_NAME", "auto")`) so a
  concrete deployment doesn't have to know to set it.
- **`default_acl` from `AWS_DEFAULT_ACL` env var**: **should change.** For
  R2 this should not be part of the config surface at all — drop the
  `AWS_DEFAULT_ACL` env var and the `default_acl` OPTIONS key entirely
  (§2). The commented-out `ACL_OPTIONS` list of canned ACL values already in
  the file is AWS-S3-flavored guidance that doesn't apply to R2 and can be
  removed once ACL support is dropped.
- **Missing: checksum workaround.** Add `client_config` with
  `request_checksum_calculation="when_required"` /
  `response_checksum_validation="when_required"` (§6) — without this,
  uploads are likely to fail intermittently or consistently depending on
  the installed boto3 version.
- **Missing: public serving config.** If media should be publicly
  accessible via a custom domain (per parent spec: "media is on object
  storage"), add `custom_domain` and `querystring_auth=False` options,
  sourced from new env vars (§4). If instead signed URLs are wanted, no
  change needed beyond the above (signed is the default when
  `custom_domain` is unset), but this is a decision to be made explicitly
  in the spec rather than left implicit.

### Recommended R2 config block for FLS (illustrative, not final spec)

```python
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")

if AWS_STORAGE_BUCKET_NAME:
    from botocore.config import Config

    AWS_S3_ACCESS_KEY_ID = os.environ["AWS_S3_ACCESS_KEY_ID"]
    AWS_S3_SECRET_ACCESS_KEY = os.environ["AWS_S3_SECRET_ACCESS_KEY"]
    AWS_S3_ENDPOINT_URL = os.environ["AWS_S3_ENDPOINT_URL"]  # https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "auto")
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")  # e.g. media.example.com, optional
    AWS_QUERYSTRING_AUTH = os.getenv("AWS_QUERYSTRING_AUTH", "False") == "True"

    options: dict = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "access_key": AWS_S3_ACCESS_KEY_ID,
        "secret_key": AWS_S3_SECRET_ACCESS_KEY,
        "endpoint_url": AWS_S3_ENDPOINT_URL,
        "region_name": AWS_S3_REGION_NAME,
        "signature_version": "s3v4",
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "client_config": Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }
    if AWS_S3_CUSTOM_DOMAIN:
        options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN

    default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": options,
    }
else:
    default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
```

Note: no `default_acl` / `AWS_DEFAULT_ACL` anywhere in this block.

## Env-var checklist

Secret (never hardcode, never commit):
- `AWS_S3_ACCESS_KEY_ID` — R2 API token key ID
- `AWS_S3_SECRET_ACCESS_KEY` — R2 API token secret

Config (deployment-specific, not secret, but still per-environment):
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_ENDPOINT_URL` (`https://<account-id>.r2.cloudflarestorage.com`)
- `AWS_S3_REGION_NAME` (default `"auto"`)
- `AWS_S3_CUSTOM_DOMAIN` (optional; public media domain)
- `AWS_QUERYSTRING_AUTH` (optional bool; `False` for public/custom-domain
  serving, `True`/default for signed-URL private serving)

To remove from the existing config surface:
- `AWS_DEFAULT_ACL` (R2 doesn't support ACLs — drop this env var and the
  `default_acl` OPTIONS key)

## Gotchas / decisions to make

1. **Public bucket + custom domain vs. private bucket + signed URLs** — needs
   an explicit decision in the spec. Recommendation: public bucket + custom
   domain, since FLS already access-controls media at the Django view layer
   (enrollment/visibility checks), and this is simpler and cacheable.
2. **`client_config` checksum workaround is mandatory, not optional** — this
   should be baked into the settings module unconditionally whenever the
   R2/S3 branch is active, not exposed as a toggle, since it's a
   compatibility fix rather than a deployment choice.
3. **Drop `AWS_DEFAULT_ACL` from the concrete-deployment env-var contract** —
   any downstream project docs / `.env.example` referencing it should be
   updated; setting it to anything will either be a no-op or an error.
4. Whether to hardcode `region_name = "auto"` in code (simpler, since this
   settings module's whole existence in this spec is for an R2 deployment)
   vs. keep it env-driven with an `"auto"` default (keeps the block
   generically "any S3-compatible provider" flavored) — either is fine
   functionally; pick whichever matches the parent spec's stance on
   generic-S3-vs-R2-specific configuration.
5. If a `Cache-Control` header on uploaded media is desired for edge
   caching, add `object_parameters = {"CacheControl": "max-age=..."}` to
   OPTIONS — not required for correctness, but recommended once serving
   media through Cloudflare's cache.

## References

- https://django-storages.readthedocs.io/en/latest/backends/s3_compatible/cloudflare-r2.html
- https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
- https://developers.cloudflare.com/r2/api/s3/api/
- https://developers.cloudflare.com/r2/buckets/public-buckets/
- https://developers.cloudflare.com/r2/api/tokens/
- https://github.com/jschneier/django-storages/issues/1498
- https://github.com/boto/boto3/issues/4435
- https://www.jrbenriquez.com/blog/cloudflare-r2-is-a-smart-choice-for-django-apps-going-out-to-production/

status: ok
