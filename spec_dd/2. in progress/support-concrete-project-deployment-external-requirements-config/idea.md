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
  (disabled for local/dev). The context processor **stays in `base`** (all context processors
  live there, alongside `debug_branch_info`) and reads through `deployment.config` — introducing
  a `base → deployment` edge. See the *base → deployment dependency* decision below.
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
- Ship the official `sentry-debug/` verification endpoint (`trigger_error` → `1/0`), **gated
  staff-only** — it's an unauthenticated guaranteed-500 otherwise.

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
- Media serving: default to a **private bucket + signed URLs** (`AWS_QUERYSTRING_AUTH=True`,
  no `custom_domain`) so `file.url` yields time-limited, non-public URLs. This is required:
  FLS gates course *pages* at the view layer but **not the media bytes** — media is only ever
  rendered as a direct `file.url` (never streamed through a permission-checked view), so a
  public bucket would leak application-gated course files to anyone with the URL. Public serving
  (`AWS_S3_CUSTOM_DOMAIN` + `AWS_QUERYSTRING_AUTH=False`, edge-cacheable) stays **available** for
  a deployment that deliberately opts in, but is **off by default**. See
  `research_private_media_access_control.md`.
- **One private bucket, no public bucket.** Static (CSS/JS/logos) already ships via WhiteNoise,
  and there is no per-file public/private flag on the single `content_engine.File` model — routing
  media across two buckets would be a separate, larger feature (out of scope).
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
| `SENTRY_SEND_DEFAULT_PII` | Sentry | config | store PII for now; scrubbing deferred to a separate spec |
| `AWS_STORAGE_BUCKET_NAME` | R2 | config | also the on/off gate for object storage |
| `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` | R2 | **secret** | R2 API token |
| `AWS_S3_ENDPOINT_URL` | R2 | config | `https://<account-id>.r2.cloudflarestorage.com` |
| `AWS_S3_REGION_NAME` | R2 | config | default `"auto"` |
| `AWS_S3_CUSTOM_DOMAIN` | R2 | config | optional; **unset by default** — only for opt-in public serving |
| `AWS_QUERYSTRING_AUTH` | R2 | config | default **`True`** (private signed URLs); `False` opts into public serving |
| `AWS_QUERYSTRING_EXPIRE` | R2 | config | signed-URL lifetime, default `3600`s; raise for long media |
| ~~`AWS_DEFAULT_ACL`~~ | R2 | — | **removed** — R2 has no ACLs |

## Decided

- **`SENTRY_SEND_DEFAULT_PII`** — store PII for now. FLS handles **learner PII**, and `True`
  attaches user email/username + full request bodies to every event, but for this spec we accept
  that trade-off to keep debugging signal high. The `before_send` scrubbing work is deferred to a
  separate spec (`sentry-pii-scrubbing` in `0. drafts`). This spec only exposes the var; it does
  not build any scrubbing.

- **R2 media privacy** — **private bucket + signed URLs by default**
  (`AWS_QUERYSTRING_AUTH=True`, no `custom_domain`), one bucket only. FLS gates course *pages*
  but not the media *bytes* (media is served as a direct `file.url`, never through a
  permission-checked view), so a public bucket would leak application-gated course files. Public
  custom-domain serving stays available as an explicit opt-in. Signed URLs give storage-layer
  privacy with no app-code change; the stronger per-request view-proxy gate is deferred (see Out
  of scope). Rationale and evidence: `research_private_media_access_control.md`.

- **`base → deployment` dependency** — **allowed.** The PostHog context processor stays in
  `base` and reads through `deployment.config` rather than relocating to `deployment`. Keeping
  it in `base` keeps all context processors in one place (next to `debug_branch_info`) and
  avoids rewiring the `TEMPLATES` `context_processors` path. This adds a `base → deployment`
  app-graph edge, and `deployment` already imports `base` (`AppSettings`/`Setting` from
  `base.app_settings`), so the two form a reciprocal `base ↔ deployment` pair. This is **not** a
  Python import cycle — `base`'s package never imports `deployment` at load; only
  `base/context_processors.py` (a distinct module) does, lazily at template render — and is
  accepted deliberately, so the structure review should treat the `base → deployment` edge as
  approved rather than flag it.

- **`sentry-debug/` gating** — **staff-only**. The endpoint stays wired in every environment
  (so production Sentry wiring can be verified where it actually matters) but is gated behind a
  staff/superuser check, so it's never an unauthenticated guaranteed-500 for anonymous users.
  Chosen over a non-prod-only URL include (can't verify prod) and manual-removal-after-verification
  (not repeatable, leaves nothing to re-verify after config changes).

- **`SENTRY_ENVIRONMENT` / `SENTRY_RELEASE` source** — FLS exposes both as its own explicit
  `deployment.config` settings; it does **not** auto-detect. There is no in-repo signal to reuse
  (`DJANGO_SETTINGS_MODULE` can't distinguish staging from prod — both use `settings_prod` — and
  no git-SHA/release var exists anywhere in `config/` or `freedom_ls/`), and the git SHA only
  exists in the CI pipeline, which is Spec 5 / out of scope. Populating these — mapping the
  pipeline's existing `GITHUB_SHA` and env name onto them — is the deployment's (Spec 5's) job.
  FLS treats an unset `SENTRY_RELEASE` as "no release tag" (SDK default) and enforces
  `SENTRY_ENVIRONMENT` explicitly since the SDK's silent `"production"` default is a footgun.

## Open decisions for the spec

None — all resolved above.

## Out of scope

- Template-repo scaffolding (Dockerfile/compose/Caddy/CI) — that's the parent's **Spec 5**.
- Ops-only credentials with no `freedom_ls` settings surface: **GHCR** tokens, **VPS/SSH** keys,
  **off-box backup** creds — cataloged in `third-party-services.md`, consumed by Spec 5.
- Server-side `posthog-python` SDK, PostHog reverse proxy, Sentry profiling — legitimate future
  work; don't build speculatively, just don't pick names that would collide.
- **Media view-proxy hard gate** — serving every media byte through a Django view that re-runs
  `can_access_content` per request (true per-request enforcement, defeats signed-URL sharing).
  Strictly stronger than signed URLs but a new feature (view + URL, permission wiring, changes to
  all file cotton components, video range-request handling). Deferred to its own spec, like
  `sentry-pii-scrubbing`. This spec ships private-by-default signed URLs only.

## Research

- `research_sentry_django_integration.md`
- `research_cloudflare_r2_django_storages.md`
- `research_posthog_django_integration.md`
