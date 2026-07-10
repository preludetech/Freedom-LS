# External requirements config — third-party services for concrete deployment

Concrete (submodule-based) FLS production/staging deployments depend on a handful of
externally-hosted services. This work wires **their configuration** into FLS in a consistent,
convention-following way, so a downstream project only has to supply env vars — not copy-paste
settings.

## Context

Supports the parent effort in `spec_dd/2. in progress/support-concrete-project-deployment/`
(decomposed into 5 numbered specs — see its `spec-order.md`). That effort establishes an
importable `freedom_ls/deployment/` home for deployment primitives (Spec 1's
`settings_defaults.py`) and catalogues every external account a deployment needs in
`third-party-services.md`. **This spec owns the in-repo *config wiring* for the three services
that need actual code/settings inside `freedom_ls`** — it does not touch the template-repo
scaffolding (Spec 5) or ops-only credentials.

## Decisions

- **Home:** a new **`freedom_ls/deployment`** app owns this wiring (Sentry init, PostHog config,
  R2 storage config), sitting alongside the parent effort's `settings_defaults.py`. Prod-only
  concerns stay out of `base`.
- **Config convention:** these service settings are **declared in a `deployment` `config.py`**
  using the `app-settings` skill's *"declared only to record ownership"* pattern. The skill's
  general rule is that env-derived secrets / third-party settings stay as direct `settings.X`
  reads; we deliberately opt into declaring them so the app owns defaults (e.g. PostHog host,
  R2 region), optionality, and a single resolution path. `config.py` stays read-only — it never
  mutates `STORAGES`/`INSTALLED_APPS`/etc.; the actual `settings_prod.py` assembly and the
  Sentry `init()` read *through* `config`.
- **Scope:** PostHog, Sentry, Cloudflare R2 — plus a **consolidated env-var / services
  checklist** so downstream deployments have one authoritative contract (building on the parent's
  `third-party-services.md`).

## Services in scope

### PostHog (analytics) — refactor existing crude wiring
Today `freedom_ls/base/context_processors.py::posthog_config` reads `os.environ["POSTHOG_API_KEY"]`
directly and passes it to templates (client-side JS snippet). Two problems: the read bypasses our
settings machinery, and **the key alone is insufficient** — PostHog Cloud is regional, so an
`api_host` is required too (US `https://us.i.posthog.com` vs EU `https://eu.i.posthog.com`).

- Move the config onto `deployment`'s `config.py`: `POSTHOG_API_KEY` (public project token —
  safe in HTML), `POSTHOG_API_HOST` (default US, overridable), optional `POSTHOG_UI_HOST` (only
  for a future reverse proxy).
- The context processor reads through `config` and renders nothing when the key is unset
  (disabled for local/dev). Relocating the context processor from `base` → `deployment` is likely
  (keeps ownership together); confirm the dependency direction in the plan/structure review.
- Per-environment: staging and prod each get their **own project token** (separate PostHog
  projects) — no shared default key committed anywhere.

### Sentry (error tracking) — new
Add `sentry-sdk[django]`; `DjangoIntegration` auto-enables. Init is a **no-op when `SENTRY_DSN`
is unset**, so dev/unconfigured deploys do nothing.

- Init belongs in an **`AppConfig.ready()`** hook (reading `config`), **not** in `settings.py` —
  Sentry's own tracker flags settings-file init as an anti-pattern for layered settings, which is
  exactly FLS's `settings_base → settings_prod` shape.
- Config surface: `SENTRY_DSN` (secret), `SENTRY_ENVIRONMENT` (staging/prod — note the SDK
  silently defaults to `"production"` if unset, a footgun), `SENTRY_RELEASE` (CI-injected git SHA;
  auto-detection is unreliable in containers), `SENTRY_TRACES_SAMPLE_RATE` (low default, e.g.
  `0.1`, for cost control), `SENTRY_SEND_DEFAULT_PII`.
- Ship the official `sentry-debug/` verification endpoint (`trigger_error` → `1/0`), **gated**
  (non-prod / staff-only) — it's an unauthenticated guaranteed-500 otherwise.

### Cloudflare R2 (media object storage) — fix existing S3 block for R2 correctness
`settings_prod.py` already has an S3 block gated on `AWS_STORAGE_BUCKET_NAME` (falls back to
`FileSystemStorage`). It's close but has R2 landmines:

- **Drop `AWS_DEFAULT_ACL` / `default_acl` entirely** — R2 does not implement S3 ACLs; setting one
  is a no-op at best, an upload error at worst. Remove the commented AWS `ACL_OPTIONS` guidance too.
- **Add the mandatory checksum workaround** — recent boto3 (≥1.35.99) sends checksum headers R2
  rejects; set `client_config = Config(request_checksum_calculation="when_required",
  response_checksum_validation="when_required")` unconditionally on the R2 branch. Not a toggle —
  a compatibility fix.
- `region_name` should resolve to `"auto"` for R2 (default it rather than making deployers know).
- Public media serving: recommend **public bucket + custom domain** (`AWS_S3_CUSTOM_DOMAIN` +
  `AWS_QUERYSTRING_AUTH=False` for clean, edge-cacheable URLs), since FLS already access-controls
  media at the Django **view** layer, not the storage layer. Signed-URL mode stays available.
- `STORAGES` is a Django built-in — its assembly stays in `settings_prod.py`; `config.py` only
  owns the service-level defaults/ownership where it adds value.

## Consolidated env-var / services checklist (deliverable)

A single authoritative list of the env vars these three services introduce, marked
**secret vs config**, with defaults — extending / cross-referencing the parent's
`third-party-services.md` so a downstream deployment has one contract to satisfy.

| Var | Service | Secret? | Notes |
|---|---|---|---|
| `POSTHOG_API_KEY` | PostHog | public token | per-env project token; unset = disabled |
| `POSTHOG_API_HOST` | PostHog | config | default `https://us.i.posthog.com` |
| `POSTHOG_UI_HOST` | PostHog | config | optional; only for a reverse proxy |
| `SENTRY_DSN` | Sentry | **secret** | unset = Sentry off |
| `SENTRY_ENVIRONMENT` | Sentry | config | `staging`/`production`; enforce, don't rely on default |
| `SENTRY_RELEASE` | Sentry | config | CI-injected git SHA |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry | config | low default (e.g. `0.1`) |
| `SENTRY_SEND_DEFAULT_PII` | Sentry | config | default off — see open decision |
| `AWS_STORAGE_BUCKET_NAME` | R2 | config | also the on/off gate for object storage |
| `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` | R2 | **secret** | R2 API token |
| `AWS_S3_ENDPOINT_URL` | R2 | config | `https://<account-id>.r2.cloudflarestorage.com` |
| `AWS_S3_REGION_NAME` | R2 | config | default `"auto"` |
| `AWS_S3_CUSTOM_DOMAIN` | R2 | config | optional; public media domain |
| `AWS_QUERYSTRING_AUTH` | R2 | config | `False` for public/custom-domain serving |
| ~~`AWS_DEFAULT_ACL`~~ | R2 | — | **removed** — R2 has no ACLs |

## Open decisions for the spec

- **`SENTRY_SEND_DEFAULT_PII`** default given FLS handles **learner PII** — `True` attaches user
  email/username + full request bodies to every event. Lean off-by-default, possibly with a
  `before_send` scrubbing note; confirm with product/compliance.
- **R2 public-bucket + custom-domain vs private + signed URLs** — recommendation is public +
  custom domain; confirm no requirement for storage-layer access control.
- **`sentry-debug/` gating strategy** — non-prod-only URL include vs staff-only vs
  manual-removal-after-verification.
- **PostHog context-processor relocation** `base` → `deployment` — confirm the cross-app
  dependency direction is clean in the structure review.
- **Where `SENTRY_ENVIRONMENT` / `SENTRY_RELEASE` come from** — reuse an existing deploy env var
  rather than inventing a parallel one; check what the pipeline already sets.

## Out of scope

- Template-repo scaffolding (Dockerfile/compose/Caddy/CI) — that's the parent's **Spec 5**.
- Ops-only credentials with no `freedom_ls` settings surface: **GHCR** tokens, **VPS/SSH** keys,
  **off-box backup** creds — cataloged in `third-party-services.md`, consumed by Spec 5.
- Server-side `posthog-python` SDK, PostHog reverse proxy, Sentry profiling — legitimate future
  work; don't build speculatively, just don't pick names that would collide.

## Research

- `research_sentry_django_integration.md`
- `research_cloudflare_r2_django_storages.md`
- `research_posthog_django_integration.md`
