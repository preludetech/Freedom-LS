# Research: API foundation for apis-for-lead-monitoring

## 1. Codebase

- DRF is NOT installed. `djangorestframework` appears nowhere in `pyproject.toml` deps (`pyproject.toml:7-41`). The only hit is an isort section mapping `"django" = ["django", "rest_framework"]` (`pyproject.toml:289`). `rest_framework` is not in `INSTALLED_APPS` (`config/settings_base.py:74-152`).
- ninja: `django-ninja>=1.5.0` is a dependency (`pyproject.toml:13`). Real use is one file: `freedom_ls/xapi_learning_record_store/api.py:3` (`Router`, a `/hello` site-check and a stub POST returning "todo", `# TODO: Authentication` at line 13). `freedom_ls/learner_interface/apis.py` is all commented out (lines 1-10). `config/urls.py:36,41-44,75-77` has the `NinjaAPI` mount commented out, so nothing is routed. `xapi_learning_record_store` is not in INSTALLED_APPS (only a comment at `settings_base.py:105`). Ninja is effectively dead code. The user asked for DRF, so ninja is not the base. Removing the dependency is a separate decision (not in scope, flag it).
- Existing machine auth: none. A case-insensitive grep for api key, token, Bearer and X-API found only unrelated hits. `webhooks` is OUTBOUND only: `WebhookSecret` (`freedom_ls/webhooks/models.py:428`) holds secrets for rendering into outgoing requests, and `secret = secrets.token_urlsafe(48)` (line 95) plus `webhooks/signing.py` sign outbound payloads. `health` has an unauthenticated view. `allauth[headless]` is installed but its urls are commented out (`config/urls.py:90`). Its headless token strategy is session-oriented, not a fit for scripts.
- Reusable secret-storage pattern: `django-fernet-encrypted-fields` (encrypts reversibly, so not suitable for API keys, which should be hashed). `argon2-cffi` is present (a hasher is available).
- Site resolution (`freedom_ls/site_aware_models/models.py`):
  - `CurrentSiteMiddleware` (`middleware.py:10-36`) puts the Django `HttpRequest` on a thread local. It is in MIDDLEWARE (`settings_base.py:176`) and runs for every request, including API requests with no session.
  - `SiteAwareManager.get_queryset` (`models.py:118-129`) filters by `get_cached_site(request)`. `get_cached_site` (`models.py:37-83`) uses `FORCE_SITE_NAME` if set, otherwise `django.contrib.sites.get_current_site(request)`, which is the request host (`DisallowedHost` becomes `UnknownSite`, and then the manager does NOT filter, `models.py:127`). So yes, the site comes from the request host (or the pinned FORCE_SITE_NAME), never from the user or session. A token-authenticated request is scoped correctly by host. The DRF `Request` wraps the same HttpRequest, so the thread local still applies.
  - Consequence for the foundation: a credential must be stored with a `site` FK. Authentication must reject a key whose site differs from `get_cached_site(request)`. Otherwise a key issued on site A used against host B reads B's data, because the manager filters by host and not by key. Also, `UnknownSite` fails open for queries, so the API needs an explicit `isinstance(site, Site)` guard (ALLOWED_HOSTS already blocks most cases).
  - `User` is not obviously site-aware (to verify in the spec: `accounts` is "site-aware user model" per CLAUDE.md). Check that the users endpoint is site-filtered.
  - Docs: `claude_plugins/fls-dev/resources/multi_tenant.md:11-17`.
- Role-based permissions (`freedom_ls/role_based_permissions`): roles are config-defined (`types.py:31-39`, `Role.permissions` is a frozenset of Django permission strings). Assignments are `SystemRoleAssignment` (`models.py:9`), `SiteRoleAssignment` (`:47`, site-aware) and `ObjectRoleAssignment` (`:83`, guardian-backed). Helpers are in `utils.py` (`assign_site_role` line 353, `get_object_roles` line 106). A credential can be tied to a permission in two ways. (a) Key belongs to a user, who holds a site role that includes a new permission such as `export_lead_data`. A DRF permission class calls `user.has_perm`. This reuses the existing machinery, audit trail and role sync. (b) Key carries its own scope list. (a) is the better fit and (b) is YAGNI. A new permission must be added to the roles config and `sync_role_permissions` must be run.
- App settings (`freedom_ls/base/app_settings.py:18-59`): per app, a `config.py` subclasses `AppSettings` with `declared_settings = {NAME: Setting(default, required)}`, read as `config.NAME` and overridden by Django settings (example `webhooks/config.py:7-15`). `required_settings_errors` (line 62) gives system checks. A new `api` app would declare e.g. `API_ENABLED` (default False), `API_PAGE_SIZE`, `API_THROTTLE_RATES`. Enabling is also by INSTALLED_APPS plus URL include.
- URL mounting: `config/urls.py:63-91` is the demo/default project URLconf, where each app is `path("x/", include("freedom_ls.x.urls"))`. Apps need `app_name`. Concrete projects write their own URLconf and include the FLS app urls themselves (this is the pattern; `config/` is the in-repo example). The API app should therefore ship `freedom_ls/api/urls.py` with `app_name="api"` and be included at `api/` in `config/urls.py`. Note the learner_interface catch-all (`config/urls.py:84`), so the api include must go before it.
- Audit log: `freedom_ls/audit_log/writer.py:33` `record_entry(action, actor, target, target_label, organisation, ...)` writes one `AuditLogEntry`. Actions are a validated registry (`actions.py:92-135`, extensible via `AUDIT_LOG_EXTRA_ACTIONS`). It is built for per-object change events, requires a `target` Model and an organisation, and `site` is derivable. It is NOT suited to per-request read logging (every export page would be a row; `record_run_summary` is for bulk runs). Reasonable fit: log credential lifecycle events (`api_key.created`, `api_key.revoked`), and optionally one summary per export run. Per-request access logging belongs in a lightweight "last_used_at" field and the normal request log.

## 2. Auth options (checked on PyPI 2026-11-01)

| Option | Maintenance / Django 6 | Hashed | Expiry | Revoke | Scope | Fit |
|---|---|---|---|---|---|---|
| DRF `TokenAuthentication` | in DRF core; DRF 3.17.1 (24 Mar 2026) adds Django 6.0 | No, plaintext in DB | No | delete row | one token per user, no site/scope | Poor: no hashing, no expiry |
| django-rest-knox 5.1.0 (12 Jul 2026) | active; classifiers 4.2-6.0, py>=3.10 | Yes (SHA-512 digest) | Yes (TTL) | Yes | multiple tokens per user, tied to a user; token created by a login | Good, but designed around login-issued tokens |
| djangorestframework-api-key 3.1.0 (4 Apr 2025) | no release for 19 months; classifiers stop at Django 5.2 | Yes (hashed, prefix id) | Yes (`expiry_date`) | Yes (`revoked`) | key per client, not tied to a user; abstract base can add FK site | Best semantic match (admin issues a key to a script), but stale |
| django-oauth-toolkit 3.4.1 (21 Aug 2026) | active; Django 6.0 | Yes (client secret hashed since 2.x) | Yes (short-lived tokens) | Yes | Yes (scopes) | Overkill; script needs token round-trip, large surface, more models |

Recommendation: django-rest-knox is the most defensible choice on maintenance, but the issuing flow ("a site admin issues a key to a script") is closer to api-key. Recommended: do NOT depend on the stale api-key package; instead write a small `ApiKey` model (site FK, owner service user FK, prefix, argon2/SHA-256 hash of a `secrets.token_urlsafe` key, `expires_at`, `revoked_at`, `last_used_at`, `created_by`) plus a ~40-line DRF `BaseAuthentication` returning `(owner_user, key)`. The model then follows FLS conventions (SiteAwareModel, admin issuing action showing the key once, audit entries) and uses no unmaintained dependency. If the spec wants zero custom crypto, choose knox (`AuthToken` created via an admin command for a service user, TTL set). The deciding factor is the site binding and admin-issued flow, which knox and api-key both lack out of the box, so the custom model costs about the same as wrapping them. Script usage: `Authorization: Bearer <key>` header (constant-time hash compare on the prefix-looked-up row).

## 3. DRF conventions

- DRF 3.17.1 supports Django 6.0 (https://simple-repository.app.cern.ch/project/djangorestframework, https://browniebroke-drf.readthedocs.io/en/latest/community/release-notes/). Python>=3.10 fine for 3.13. Verify with a test run on Django 6.0.x.
- Versioning: URL path via `URLPathVersioning` or simply a `path("api/v1/", include(...))` namespace; `DEFAULT_VERSIONING_CLASS` is only needed once v2 exists. Prefer the plain include.
- Read-only: `ReadOnlyModelViewSet` (or `ListModelMixin` only; exports mostly need list plus retrieve), `DefaultRouter`. Permission classes `[IsAuthenticated, HasExportPermission]`. Default `DEFAULT_RENDERER_CLASSES = [JSONRenderer]` (drops the browsable API, no UI wanted), `DEFAULT_PARSER_CLASSES` unneeded, and `http_method_names = ["get", "head", "options"]`.
- Pagination: `CursorPagination` ordered on `(updated_at, id)` (stable under concurrent inserts and efficient on big tables, no COUNT); page-number/limit-offset get slow and skip or duplicate rows during a long export. Needs a unique, indexed ordering field. Cursor cannot jump to a page, which is fine for scripts. Set `page_size` and `max_page_size`.
- Filtering: `django-filter` 26.2 (3 Oct 2026; Django 5.2, 6.0, 6.1) with `DjangoFilterBackend` and a shared `updated_since` filter (`updated_at__gte`) for incremental sync. Deletions are not visible through `updated_since` (note for the spec).
- Throttling: DRF `ScopedRateThrottle` or `UserRateThrottle` with rates in config (cache-backed, so needs a shared cache in multi-process deployments; check CACHES).
- OpenAPI: `drf-spectacular` 0.30.0 (6 Jul 2026; Django 6.0). `SpectacularAPIView` at `/api/v1/schema/`, restricted to the same auth (no Swagger UI needed). The `manage.py spectacular` command can generate the file in CI. Also gives a drift-check test.
- Serializer naming: explicit `fields` lists (never `__all__`), snake_case, ISO 8601 UTC timestamps, UUIDs as strings, expose stable identifiers (uuid), nested ids not nested objects, one serializer per resource in `serializers.py`. Use `select_related`/`prefetch_related` in `get_queryset` (CLAUDE.md rule).
- Scripting: provide a short documented `requests`/`httpx` example (httpx already a dependency) with a page-following loop.

## 4. Security

- HTTPS: prod already has `SECURE_SSL_REDIRECT`, HSTS, secure cookies (`config/settings_prod.py:21-47`). A redirect on a POST/GET with a Bearer header may leak the key on a plain-http first hit, so docs must say "https only" and the key should be considered burnt if used over http. Optionally reject non-secure requests in the authenticator (when `not request.is_secure()` and not DEBUG).
- CSRF: irrelevant to header-token auth. DRF `SessionAuthentication` is the only thing that enforces CSRF, so set `DEFAULT_AUTHENTICATION_CLASSES` to the key class ONLY (no session auth, so a logged-in browser cannot be abused cross-site). CsrfViewMiddleware stays for the rest of the site; DRF views are csrf_exempt by default via `APIView.as_view`.
- Axes (`axes` is installed, `settings_base.py:151`) should be considered for repeated failed key attempts; rate throttle covers it basically. Authentication failures should return a generic 401 with no enumeration.
- Rate limiting: see throttling above. Throttle by key id, not IP.
- Audit: record key issue/revoke in `audit_log` (new action codes through `AUDIT_LOG_EXTRA_ACTIONS` or FLS actions); keep `last_used_at` on the key; a read-access log is not what audit_log is for (see section 1).
- PII: users, applications, referrals are personal data. Export only an explicit allowlist of fields, no password hash, no free-text answers by default. `csv_safety.py` exists in base (relevant only if CSV rendered; JSON only avoids it). Per-key `expires_at`, least-privilege permission, and site binding limit blast radius. Consider that a leaked key reads ALL learners of a site; require expiry and show the key once.
- Secrets: never log the Authorization header (Sentry is enabled, `sentry-sdk`; scrub). Store only the hash.

## 5. What the foundation spec must deliver

Roughly (in dependency order):
1. `api` app skeleton: `apps.py`, `config.py` (AppSettings: enabled flag, page size, throttle rates), `urls.py` with `app_name`, mount in `config/urls.py` before the catch-all, DRF + django-filter + spectacular added to deps and settings (`REST_FRAMEWORK` dict), INSTALLED_APPS, import-linter contract if the repo enforces them.
2. Credential model + migration, hashed storage, expiry, revoke, `last_used_at`, site binding, admin issue/revoke with show-once and audit entries.
3. Authentication class (Bearer header, site-match check, `UnknownSite` guard), permission class tied to a new role permission, the roles-config change and `sync_role_permissions`, tested.
4. Shared base: read-only base viewset, cursor pagination class, `updated_since` filterset mixin, throttle, JSON-only renderer, error format, schema endpoint, ordering/serialiser conventions documented.
5. A tiny `health`/`whoami`-style endpoint (returns site and key metadata) to prove the whole stack, plus the Python client example docs, and tests for: no key, bad key, expired, revoked, wrong site, missing permission, throttle.

Size: the foundation is about 3-5x one resource endpoint. A resource endpoint after the foundation is a queryset, serializer (explicit fields), filterset and a router line (~50-100 lines plus tests, each with a site-isolation and PII-field test). Recommended spec order: (1) foundation with a whoami endpoint, (2) users, (3) course registrations and progress (or applications), (4) referrals; resource specs are independent of each other and can be parallelised after the foundation.

## Open items for spec writers
- Decide knox vs custom `ApiKey` (recommendation: custom, section 2).
- Confirm `User` queryset site filtering for the users endpoint.
- Decide whether to delete the dead ninja dependency (separate, not blocking).
- Check a shared cache exists for throttling in the default settings.

## Sources
- https://simple-repository.app.cern.ch/project/djangorestframework
- https://browniebroke-drf.readthedocs.io/en/latest/community/release-notes/
- https://pypi.org/pypi/djangorestframework-api-key/json
- https://pypi.org/pypi/django-rest-knox/json
- https://pypi.org/pypi/drf-spectacular/json
- https://pypi.org/pypi/django-filter/json
- https://pypi.org/pypi/django-oauth-toolkit/json

status: ok · reason: complete
