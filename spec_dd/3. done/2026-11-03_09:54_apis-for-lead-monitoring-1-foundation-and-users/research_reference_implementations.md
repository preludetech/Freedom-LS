# Research: reference implementations for a scoped, hashed, shown-once API key

Scope: how real code solves the credential (model, generation, storage, lookup, admin issuance, scope check, `last_used_at`) plus DRF pagination and schema-auth. Complements `research_api_foundation.md` (codebase, auth options table, DRF conventions) and does not repeat it. Fetched 2026-11-01. Items marked "not verified" were not visible in the fetched source.

## 1. djangorestframework-api-key (florimondmanca)

- Maintenance: latest release 3.1.0 on 2025-04-04 (previous 3.0.0 on 2023-10-19, 2.3.0 on 2023-01-19). About 19 months with no release. Classifiers stop at Django 5.2 (changelog says 5.0 to 5.2), no Django 6. 12 open issues, 6 open PRs. The README warns that breaking changes occur between majors and that the package "is NOT meant for authentication" of users. Rejection reason holds: stale, no Django 6 declared, no site/scope/last-used support.
- Model (`AbstractAPIKey`): `id` (CharField 150, pk, = prefix + hashed_key), `prefix` (CharField 8, unique), `hashed_key` (CharField 150), `created` (indexed), `name` (50), `revoked` (bool), `expiry_date` (nullable). No scopes, no tenant, no last-used. Abstract base lets a project add a FK (e.g. site).
- Generation: key is `prefix.secret` (8 random chars, `.`, 32 random chars). `KeyGenerator.generate()` returns `(key, prefix, hashed_key)`. Only prefix and hash are stored.
- Hasher: `Sha512ApiKeyHasher`, unsalted `sha512$$<hexdigest>`, docstring says never use it as a password hasher; justified because the secret is high entropy. Verify uses `constant_time_compare`. Legacy hashes fall back to Django `check_password` and are transparently upgraded on verify (this leaves the pk inconsistent with the hash, a wart).
- Lookup: `get_from_key` does `key.partition(".")`, selects non-revoked rows by `prefix`, then `is_valid(key)` (hash verify). Expiry is checked in the manager `is_valid`, not in `get_from_key` (a footgun if called directly).
- Permission: `HasAPIKey` is a DRF *permission*, not an authenticator. `KeyParser` reads `Authorization: Api-Key <key>` (keyword overridable) or a custom header setting. Missing key gives False (so DRF returns 403 unless an authenticator sets a 401 challenge). Custom model via subclassing `BaseHasAPIKey` and setting `model`.
- Admin: `save_model` on create calls `assign_key(obj)`, saves, then `messages.add_message(WARNING, ...)` containing the raw key. The message is rendered on the next page and never persisted. `prefix` is always read-only; once revoked, `name`, `revoked`, `expiry_date` become read-only. Revoked cannot be undone (model `_validate_revoked` raises).
- last_used: none.

Borrow: `prefix.secret` format, prefix as indexed lookup column, unsalted SHA-256/512 plus `constant_time_compare` for high-entropy secrets, one-way revoke, admin message-once flow, revoked rows frozen read-only. Avoid: pk derived from hash, hasher migration code (no legacy), permission-not-authentication split (no 401).

## 2. DRF TokenAuthentication and authtoken admin

- Header `Authorization: Token <key>` (keyword case-insensitive). Parse flow: no header or wrong keyword returns None (try next authenticator); keyword with no credential, or spaces in token, or bad bytes raises `AuthenticationFailed`; then `authenticate_credentials` does `select_related('user')` lookup by key, "Invalid token." if missing, "User inactive or deleted." if inactive; returns `(user, token)`. `get_model()` allows a custom model exposing `key` and `user`.
- Model/storage: the Token key is the plaintext primary key, one per user, `created` only. No hashing, expiry, scopes (from DRF docs knowledge; internals not in the fetched file).
- Admin (`TokenAdmin`): `list_display = ('key', 'user', 'created')`, `fields = ('user',)`, `list_filter = ('created',)`, `actions = None`. The key is always visible in the list, which is the opposite of shown-once.
- last_used: none.

Borrow: the exact error flow of header parsing (None vs AuthenticationFailed), `select_related` on the bound object, `get_model()` hook for testability. Note: an authenticator needs `authenticate_header()` returning a scheme (`Bearer`) for DRF to emit 401 rather than 403.

## 3. django-rest-knox

- Model (`AbstractAuthToken`): `digest` (pk), `token_key` (indexed, first `TOKEN_KEY_LENGTH` chars of token, includes prefix), `user` FK, `created`, `expiry` (nullable).
- Generation: configured prefix plus `crypto.create_token_string()`; only `hash_token()` digest stored (SHA-512 per `SECURE_HASH_ALGORITHM`; hashing function itself not in fetched file). Plaintext returned once.
- Lookup (`TokenAuthentication.authenticate_credentials`): query rows by `token_key`; per candidate delete expired tokens (`_cleanup_token`, fires `token_expired`); hash presented token and `compare_digest` against `digest`; optional `AUTO_REFRESH` extends expiry only if beyond `MIN_REFRESH_INTERVAL`; `validate_user` rejects inactive users.
- Admin: not fetched.
- last_used: none in model or auth. `renew_token` only touches `expiry`.
- Borrow: indexed short lookup key, then constant-time digest compare; a throttle-style write interval concept (`MIN_REFRESH_INTERVAL`). Avoid: deleting rows inside authentication (a read-only GET should not DELETE; FLS wants audit retention of expired/revoked keys).

## 4. Sentry

- Token types: personal `sntryu_` + 64 hex (`[a-f0-9]{64}`); organization auth tokens `sntrys_` + base64 payload including org slug + `_` + 43 base64 chars (180 to 250 chars); `sntrya_` and `sntryi_` reserved. Fixed visible prefixes make secret scanning possible (GitHub secret scanning style).
- Model `ApiToken`: `token`, `refresh_token`, `hashed_token`, `hashed_refresh_token` (SHA-256 hex), `token_type`, `token_last_characters` (last 4), `expires_at` (default 30 days), `date_added`. Generation `f"{token_type}{secrets.token_hex(32)}"`. Plaintext exposed once via `plaintext_token` and then replaced with a redacted marker (the fetched `save()` still keeps the raw value in the legacy `token` column during a migration to hashed storage).
- Model `OrgAuthToken`: `token_hashed` (unique), `token_last_characters`, `scope_list` (array of valid scope strings; `org:tokens` forbidden so a token cannot mint tokens), `date_last_used`, `project_last_used_id`, `date_deactivated` (revoked iff set).
- Scope check: scopes held on the token, validated against a registry at write time.
- last_used: debounced via cache key (token id + sha1 of project ids), written at most once per 60 s per token/project.
- Admin issuance: user-facing settings UI, shown once (docs page did not state this; not verified).
- Borrow: human-recognizable prefix, `token_last_characters` (last 4) shown in admin list so a key can be identified without the secret, `date_deactivated` style revoke timestamp (records when), scope validated against a fixed registry, cache-debounced last-used write.

## 5. GitHub fine-grained PATs

- Resource owner (user or org), repository selection (all or selected), per-permission levels (read/write/admin), mandatory-ish expiration (non-expiring allowed unless org policy forbids), org approval gate (pending tokens read public only). Revoke = delete the token; leaked tokens can be revoked via REST API (secret scanning). Docs fetched did not mention shown-once or last-used (not verified here).
- Borrow: the binding to exactly one resource owner (FLS: one site) and explicit named permissions chosen at creation; policy that expiry is the default recommendation.

## 6. Stripe restricted keys

- Types `pk_`, `rk_` (restricted), `sk_`, `sk_org_`; mode embedded in prefix (`rk_live_`, `rk_test_`). Restricted keys carry per-resource permissions (None/Read/Write). Live mode: key shown once and cannot be revealed later for keys you created ("rotate or delete it and create another").
- Operations: edit name/note, expire (immediate), rotate (new key plus old one valid for a grace period up to 7 days), restore access, per-key request logs, access policies (IP/ASN/country).
- last_used: surfaced via request logs and a usage-based limited-access rule (180 days unused for payouts).
- Borrow: shown-once wording ("rotate or delete and create another"), a note field for where the key is stored, rotation = issue new key and revoke old (no in-place regeneration), prefix encoding the environment. IP allow-listing is out of scope (idea excludes it).

## 7. PostHog personal API keys (Django)

- Model `PersonalAPIKey`: `id` (random pk), `user` FK, `label` (40), `description`, `mask_value` (nullable, 11 chars, display like `phx_...abcd`), `secure_value` (unique, 300, the hash), `created_at`, `last_used_at`, `last_rolled_at`, `expires_at`, `scopes` (ArrayField of strings), `scoped_teams` (int array, nullable), `scoped_organizations` (nullable). `is_expired` property.
- Generation: `phx_` prefix (keys before 2021-06 were bare 43-char strings, detected by regex `^[A-Za-z0-9_-]{43}$`).
- Hashing: current mode `("sha256", None)`, adopted 2024-02; earlier PBKDF2 (260k and 390k iterations) accepted for legacy lookup. Hash is deterministic so lookup is a direct unique `secure_value` equality query (no prefix lookup needed; prefix is for display and scanning). This is the notable difference from api-key/knox, which look up by prefix then compare.
- Authentication (`PersonalAPIKeyAuthentication`): header regex `^Bearer\s+(\S.+)$`; also body and query string (PostHog accepts them; FLS must not). `validate_key` in `transaction.atomic`: hash per mode, `filter(user__is_active=True).get(secure_value=...)`; DoesNotExist leads to `AuthenticationFailed`; expired raises a distinct error (FLS wants a single generic message instead); legacy hash re-saved under `select_for_update()`.
- Scope check: not in the authenticator. Done by a separate `APIScopePermission` (not fetched). Team/org scoping likewise sits in the permission layer.
- last_used_at: `if key.last_used_at is None or now - last_used_at > timedelta(hours=1): save(update_fields=["last_used_at"])`. At most one UPDATE per hour, no cache needed (compares against the already-loaded row value).
- Borrow: SHA-256 of a `secrets.token_urlsafe`/hex secret with unique-column equality lookup (simple, constant-ish time via the DB index, no per-row compare loop), `mask_value`, scopes as a list validated against a registry, time-compared throttled `last_used_at` using `update_fields` (works with no shared cache, unlike Sentry's cache debounce). Avoid: key in query string/body, multiple distinct error messages.

## 8. Saleor app tokens (multi-tenant style; django-tenants / Wagtail not found as a relevant key implementation)

- `AppToken`: `app` FK, `name`, a token column (unique, 128 chars, hashed with Django `make_password`), `token_last_4`. Manager `create()` returns the model and the plain token together, and the plain token is available only at creation. Permissions are on `App` (M2M to Django `Permission`), not on the token; `App.is_active` False yields no permissions. Saleor's auth looks up by `token_last_4` then checks the hash (not verified in fetched file), an expensive per-row slow-hasher check. FLS should not copy that: a salted slow hash is wrong for a high-entropy secret and costs CPU on every request.
- Borrow: tenant/owner object (App) holds the grants and the active flag, tokens hang off it; `(obj, raw)` return signature from the manager.
- django-tenants and Wagtail: no first-party API-key model found; both rely on the host/schema for tenant selection, which matches FLS's host-based `CurrentSiteMiddleware` and the idea's requirement that key site must equal the host site.

## 9. DRF CursorPagination with an ordering tuple

- Requirements from DRF docs: ordering field should be unchanging, unique or nearly unique, non-null, not a float, indexed. Default ordering is `-created`. `ordering` may be a string or a list/tuple. `OrderingFilter` on the view can override it (disable for FLS by not adding the filter backend). Cursor encodes position plus offset so duplicate timestamps are handled, and a second field (`id`) is the tiebreaker. Forward/back only, no jump, no COUNT, no slowdown on large tables.
- Caveat for FLS (analysis, not from the docs): `updated_at` changes on update, which breaks the "unchanging" rule. A row updated mid-crawl moves to the end and is returned again later (duplicate, never lost), which is acceptable for incremental sync, and `updated_since` plus idempotent upsert on the client handles it. Document it. Ascending order is needed, so set `ordering = ("updated_at", "id")`, and mixed asc/desc tuples are unsupported in cursor, so keep both ascending. `updated_at` needs a DB index (composite `(updated_at, id)` helps) and `auto_now`. Set `page_size`, `max_page_size` via a subclass with `page_size_query_param`.

## 10. drf-spectacular authentication extension

- A custom authenticator is ignored with a warning unless an `OpenApiAuthenticationExtension` subclass sets `target_class` (path or class) and `name` and returns a definition from `get_security_definition(auto_schema)`.
- For a Bearer key return `{"type": "http", "scheme": "bearer", "bearerFormat": "<prefix>"}` (OpenAPI 3 spec form; the docs example shows only the `apiKey`/header variant, so the bearer form is from the OpenAPI spec, not the fetched page). Put the extension in a module imported at startup (the app's `ready()` or the `authentication.py` the schema module imports).
- To keep the schema behind the same auth, `SPECTACULAR_SETTINGS` has `SERVE_PERMISSIONS` and `SERVE_AUTHENTICATION`, and `SERVE_PUBLIC` (not verified on the fetched page; verify in the spec's test).

## What to borrow for FLS

1. Key format `<prefix>.<secret>` or a fixed visible prefix (`flsk_`) so secret scanners and humans can recognise it; prefix stored in an indexed column (api-key, Sentry, PostHog).
2. Secret from `secrets.token_urlsafe(32+)`; store an unsalted SHA-256 hex digest of the whole key (PostHog, Sentry, api-key). Do not use `make_password`/argon2 (Saleor): high-entropy secrets need no slow hash, and a slow hash on every request is a DoS surface. Compare with `hmac.compare_digest`.
3. Lookup: either unique equality on the hash (PostHog) or prefix lookup then constant-time compare (api-key/knox). With a hash-equality lookup only a single query is needed; keep prefix (or last 4) for admin display.
4. Fields: `site` FK, `name`, `prefix` or `last_characters`, `key_hash` (unique), `scopes` (list validated against the four-name registry, like Sentry/PostHog), `expires_at` nullable, `revoked_at` nullable (records when, one-way), `last_used_at`, `created_by`, `created_at`. Skip refresh tokens, rotation grace periods, IP policies, user FK.
5. Admin: create via `save_model` that generates the key, stores the hash, then `messages.warning` with the raw key (api-key flow). Prefix/hash/site read-only after creation; revoked rows fully read-only; no key column in list_display (unlike DRF authtoken); show prefix/last 4, scopes, expiry, last_used_at, revoked state. Write `api_key.created` and `api_key.revoked` audit entries from the same admin paths. Revoke via action or the `revoked_at` field, not delete.
6. Authenticator, not a permission class, so failures give 401 with `WWW-Authenticate: Bearer`: parse `Authorization` only (reject other places), None on missing or wrong scheme, one generic `AuthenticationFailed` message for malformed, unknown, expired, revoked, wrong-site (DRF TokenAuthentication flow, PostHog without its distinct messages). Return `(AnonymousUser-like, key)`; scopes enforced by a separate permission class reading `view.required_scope` and returning 403.
7. last_used_at: PostHog's compare-and-save with `update_fields` at most hourly (or a few minutes), no cache dependency; mention Sentry's 60 s cache debounce as the alternative. Keep it out of the audit log.
8. Cursor pagination subclass: `ordering = ("updated_at", "id")`, composite index, capped `max_page_size`; document the re-appearance of rows that were updated mid-crawl.
9. drf-spectacular: an `OpenApiAuthenticationExtension` with an HTTP bearer scheme for the key authenticator; schema view uses the same authentication.
10. Throttle by key: a `SimpleRateThrottle` subclass whose `get_cache_key` returns the key id (`request.auth.pk`), noting it needs the shared cache (DRF throttles use the Django cache).

## References

- https://github.com/florimondmanca/djangorestframework-api-key
- https://raw.githubusercontent.com/florimondmanca/djangorestframework-api-key/master/src/rest_framework_api_key/models.py
- https://raw.githubusercontent.com/florimondmanca/djangorestframework-api-key/master/src/rest_framework_api_key/crypto.py
- https://raw.githubusercontent.com/florimondmanca/djangorestframework-api-key/master/src/rest_framework_api_key/admin.py
- https://raw.githubusercontent.com/florimondmanca/djangorestframework-api-key/master/src/rest_framework_api_key/permissions.py
- https://pypi.org/pypi/djangorestframework-api-key/json
- https://raw.githubusercontent.com/encode/django-rest-framework/master/rest_framework/authentication.py
- https://raw.githubusercontent.com/encode/django-rest-framework/master/rest_framework/authtoken/admin.py
- https://www.django-rest-framework.org/api-guide/pagination/
- https://raw.githubusercontent.com/jazzband/django-rest-knox/master/knox/models.py
- https://raw.githubusercontent.com/jazzband/django-rest-knox/master/knox/auth.py
- https://docs.sentry.io/api/auth/
- https://docs.sentry.io/security-legal-pii/security/token-formats/
- https://raw.githubusercontent.com/getsentry/sentry/master/src/sentry/models/apitoken.py
- https://raw.githubusercontent.com/getsentry/sentry/master/src/sentry/models/orgauthtoken.py
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- https://docs.stripe.com/keys
- https://raw.githubusercontent.com/PostHog/posthog/master/posthog/models/personal_api_key.py
- https://raw.githubusercontent.com/PostHog/posthog/master/posthog/auth.py
- https://raw.githubusercontent.com/saleor/saleor/main/saleor/app/models.py
- https://drf-spectacular.readthedocs.io/en/latest/customization.html

status: ok
