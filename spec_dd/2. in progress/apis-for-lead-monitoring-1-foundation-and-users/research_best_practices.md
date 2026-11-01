# Research: best practices for the read-only, key-authenticated lead monitoring API

Scope: adds to `research_api_foundation.md` (codebase, auth package comparison, basic DRF conventions) and `research_comparable_apis.md` (vendor comparison). Does not repeat them. Items marked [fetched] were read from the cited page in this run. Items marked [knowledge] are established practice from memory of the cited standard or vendor doc and were not re-fetched; verify before quoting in a spec.

Note on the idea's decisions: the idea settles "key not tied to a user" and "scopes on the key", which supersedes the earlier research's suggestion (owner service user plus `user.has_perm`). Recommendations below assume the idea.

## 1. Key format

Recommendation: `<prefix>_<identifier>_<secret>`, for example `fls_live_<key_id>_<secret>` is overkill; use `flsk_<public_id>.<secret>`.

- Prefix `flsk_` (fixed, FLS-branded, ends in `_`). Reason: GitHub's prefix plus underscore separator makes tokens distinguishable from random hex or SHA strings and cut secret-scanning false positives to about 0.5% on the prefix alone [fetched, GitHub blog]. Also lets users and scanners recognise a leaked key in a repo or log.
- Identifier: a short non-secret public id (8 to 12 chars, random, unique, indexed) stored in clear on the row. Reason: lookup by indexed id, not by hashing every candidate and not by scanning; also lets the admin list and the audit log reference a key without exposing the secret (Stripe shows only the key's tail; the djangorestframework-api-key package uses a prefix id the same way) [knowledge].
- The random part comes from `secrets.token_urlsafe(32)` (256 bits, CSPRNG). Reason: at 128+ bits it cannot be brute-forced, so storage can use a fast hash (see section 2).
- Optional checksum (GitHub appends a CRC32 in Base62 in the last 6 chars so a scanner or the server can reject typos and fake tokens offline, with no DB hit) [fetched]. Reason to include: cheap early rejection of garbage before touching the DB, and fewer false positives if the operator registers the prefix with GitHub secret scanning partner programme. Reason to skip: it adds a parsing step and is not a security control (CRC is not secret). Recommendation: skip in v1 unless the project wants to join secret scanning; keep the format versionable via the prefix (`flsk_`, later `flsk2_`).
- Do not put site, scope or expiry data in the key text; keep them in the row so revoke/rescope needs no re-issue.
- Show the full key once, at issue, in the admin (a message on the issue response, not a stored/readonly field). Store only prefix/id (clear) and hash.

## 2. Hashing and comparison

Recommendation: store `sha256(full_key)` hex (or HMAC-SHA256 with a server-side pepper from env) in a unique column; look the row up by public id, then compare with `hmac.compare_digest` / `secrets.compare_digest`.

- Slow hashes (PBKDF2, Argon2, bcrypt, scrypt) exist to resist brute force on low-entropy passwords. Django's docs frame them for passwords [fetched]. For 256-bit random keys a fast hash is the established choice and a slow KDF only adds per-request CPU (an auth check per API request, and a DoS lever) for no security gain [knowledge; Django docs page does not address tokens]. Knox likewise uses SHA-512 digests [from earlier research]. Argon2 being installed is not a reason to use it here.
- Salting is not needed for high-entropy random secrets; a per-deployment HMAC pepper is optional hardening (a DB-only leak then cannot even be checked offline). Pepper must come from env, never code (project rule).
- Do not use Django `make_password`/`check_password` for keys: per-request cost of PBKDF2 at ~1M iterations (hundreds of ms) would dominate scripts that page quickly.
- Lookup by public id then constant-time compare of the hashes. Because the hash is of a high-entropy secret, direct `filter(key_hash=sha256(candidate))` is also acceptable (DB index lookup timing leaks nothing usable), but id-then-compare keeps the compare constant-time and gives a place to record which key failed. Pick one and test it.
- Timing/enumeration: make unknown-id, wrong-secret, revoked, expired and wrong-site all return the identical 401 body and headers. For unknown id, still run one dummy hash and compare so response time is similar [knowledge, OWASP authentication guidance]. Internal reason (revoked vs expired vs wrong site) goes to a non-secret server-side signal only (key id, never the secret or header).
- Reject early on malformed header (no `Bearer`, extra tokens, wrong prefix) with the same 401. DRF `get_authorization_header` plus `.split()` pattern: exactly two parts, scheme case-insensitive `bearer`.

## 3. `last_used_at` writes

Recommendation: debounce. Update only when the stored value is older than a threshold (suggest 5 to 15 minutes; one hour is fine for audit purposes), using a single conditional `UPDATE ... WHERE id=%s AND (last_used_at IS NULL OR last_used_at < now - threshold)` via `queryset.filter(...).update(...)`.

- Reason: a script paging 1000 pages would otherwise write 1000 rows to the same hot row; row lock contention on one key and write amplification on a read-only API. Debounce bounds writes to one per key per window.
- The conditional `update()` is atomic, needs no `select_for_update`, skips `save()` signals and does not touch `updated_at` of anything else. Use `update()` so it does not bump any `auto_now` field that other code might treat as "key changed".
- Alternative: write on a cache with a TTL (`cache.add("apikey:seen:<id>", 1, timeout)`) and only hit the DB if `add` succeeds; cheaper still but needs the shared cache anyway. Keep the DB-conditional update as the source of truth.
- Document the precision: `last_used_at` is "within the debounce window", not exact. Retention: it is a timestamp on the key, deleted with the key; state this in `security-and-data-handling.md`.
- Update it only after a fully successful authentication (valid, unexpired, unrevoked, site matches), never on failure, so an attacker cannot make a key look in use.

## 4. Expiry and revocation semantics

- Revoked is checked on every request (no caching of "valid" beyond the request) so revoke takes effect immediately. If the key row is ever cached for speed, TTL must be seconds and revoke must invalidate it.
- Store `revoked_at` (nullable timestamp) rather than a bare boolean: gives who/when for free alongside the audit entry. Same for `expires_at` (nullable). A key is active iff `revoked_at is None and (expires_at is None or expires_at > now)`. Compare against server `timezone.now()`; expiry is exclusive at the instant.
- Revocation is one-way: a revoked key is never un-revoked (issue a new one). Reason: simpler audit story, avoids resurrecting a leaked key.
- Prefer requiring or defaulting an expiry (for example default 1 year, admin may clear it) because a leaked key reads all of a site's learners. Idea says optional; defaulting the admin form field is a cheap compromise [recommendation].
- Rotation: allow overlapping active keys per site so an operator can issue new, switch the script, then revoke old. No uniqueness constraint on (site, name).
- Deleting a site's key row should be disabled in admin in favour of revoke, so the audit trail and `last_used_at` remain.
- Admin issue/revoke audit entries must carry the key public id and name, never the secret.

## 5. 401 vs 403 and WWW-Authenticate

- 401 for "could not authenticate" (missing, malformed, unknown, wrong secret, revoked, expired, wrong site, unresolvable site). 403 for "authenticated but the key lacks the scope". This matches RFC 9110 (401 must carry a challenge) and RFC 6750 for Bearer (`insufficient_scope` is a 403) [knowledge].
- DRF quirk: DRF returns 403 instead of 401 unless the first authentication class defines `authenticate_header()`. Implement `authenticate_header(self, request)` returning `'Bearer realm="api"'` so unauthenticated requests get 401 with `WWW-Authenticate: Bearer realm="api"` [DRF authentication docs, knowledge]. Same string for all 401s.
- RFC 6750 allows `error="invalid_token"` in the challenge. Prefer the bare challenge with no `error=` for failures to avoid enumeration (a distinct `invalid_token` for expired vs unknown would leak state). Missing-header case: bare challenge is the RFC-prescribed form anyway.
- Use one fixed error body, for example `{"detail": "Authentication credentials were not provided or are invalid."}`. DRF's default messages differ between "not provided" and "invalid token"; override via `AuthenticationFailed` with one message everywhere.
- 403 body for missing scope may name the needed scope; the caller is authenticated, so this is not enumeration, and it helps the script author. Do not leak other scopes or other keys.
- Site mismatch is 401, not 403 and not 404: from outside it must look like any bad key.
- Add `Cache-Control: no-store` (and `Vary: Authorization`) on API responses so proxies do not cache keyed data across callers [knowledge].
- Failed-attempt throttling: also throttle unauthenticated attempts per IP (a separate small throttle) because per-key throttling does not apply when the key is unknown. django-axes is installed; do not wire it to the API unless needed, a throttle is simpler. Note: IP behind a proxy needs correct `NUM_PROXIES` / `X-Forwarded-For` handling or all clients share one bucket.

## 6. Never log the Authorization header

- Django and DRF do not log headers by default, but these do: Sentry (`sentry-sdk` is present; its default `send_default_pii=False` strips `Authorization`, `Cookie` and similar, but custom `before_send` or `send_default_pii=True` changes that), reverse proxy/nginx access logs with custom formats, `django.request` debug 4xx/5xx error emails (Django's `SafeExceptionReporterFilter` hides settings and post vars, not all headers; the technical 500 page in DEBUG shows META including `HTTP_AUTHORIZATION`) [knowledge].
- Recommendation: add a test asserting `Authorization` is not in the Sentry event (scrubbing rule in `before_send` or `EventScrubber` denylist), never include `request.META`/`headers` in any log line or audit `extra`, and log only key public id. Do not echo the received key in error responses. Do not put keys in URLs (so they are not in access logs); the idea already forbids query-string keys.
- Never store the secret anywhere after issue, including admin "readonly fields" and `__str__`/`repr` of the model (use public id/name). Exclude the hash column from admin forms and from `list_display`.

## 7. Incremental sync pitfalls (`updated_since`)

These are the load-bearing correctness issues; most are not covered in the earlier research.

1. Inclusive boundary: use `updated_at >= since` (settled). Reason: an exclusive bound loses rows that share the checkpoint timestamp. Cost: the last row of the previous sync is returned again, so consumers must upsert by id (idempotent). Document "at-least-once, upsert by id".
2. Same-timestamp ties: many rows can share an `updated_at` (bulk update, `auto_now` in a single transaction uses distinct `now()` per statement but a bulk `update()` shares one value). Ordering on `(updated_at, id)` makes the order total; cursor pagination then must treat the pair as the position. DRF `CursorPagination` only orders by the fields given and uses "position plus offset" for non-unique values [fetched], so with `ordering = ("updated_at", "id")` ties are broken deterministically. Verify with a test that creates more than one page of rows with an identical `updated_at`.
3. Clock skew: `updated_at` is set by the app server's `timezone.now()` (Django `auto_now`), not the DB. With several app servers, clocks differ by milliseconds to seconds, so a row can be written with an earlier timestamp than one already seen. Mitigation: consumers overlap their window (see 5); servers should run NTP; do not hand out the server clock as the checkpoint. Alternative that avoids this: compute timestamps in the DB (`Now()`), but that is a model-wide change and out of scope.
4. Out-of-order commits ("rows appear in the past"): transaction A takes `updated_at = 10:00:00.5` then commits at 10:00:03; transaction B has `updated_at = 10:00:01` and commits at 10:00:02. A consumer that synced at 10:00:02.5 and stored checkpoint 10:00:01 will see B but never see A if the checkpoint advanced past 10:00:00.5. Long transactions make the gap larger. This is the well-known "watermark vs commit order" problem with timestamp-based change capture [knowledge; discussed widely, see Postgres/CDC write-ups]. Mitigations:
   - Consumer-side overlap window: after a successful sync, set the checkpoint to `max(updated_at seen) - overlap` (recommend at least 5 minutes, longer than the longest expected transaction and clock skew), and upsert by id. Document this in the docs page and the Python example; this is the pragmatic standard answer.
   - Server-side safety: ensure `updated_at` is never set long before commit, i.e. keep write transactions short (ATOMIC_REQUESTS and bulk jobs can hold a transaction open for minutes).
   - Optional server mode: serve only rows with `updated_at <= now - safety_lag` (for example 30 seconds) so rows still in flight are not skipped. This trades freshness for correctness; worth considering as a default because it removes the common case without client cooperation. Apply it consistently or the cursor ordering breaks. Decide in the spec; simplest is overlap documentation only.
5. Checkpoint from the data, not from the wall clock: the script should store the max `updated_at` it received, never "the time I started". Document it in the example.
6. Cursor vs `updated_since` interaction: the cursor encodes position within one query; a script must not reuse a stale cursor after changing the filter. Cursors are only valid for the same filter and ordering; tell consumers to follow `next` within a run and use `updated_since` between runs.
7. Mutations during a paging run: rows updated mid-run move to the end (their `updated_at` increases), so they are returned again later in the same run (duplicates, never lost). That is the reason the order is `updated_at` ascending and not creation order. Do not order descending for sync.
8. `updated_at` coverage: a user row's `updated_at` does not change when a related row (profile, registration) changes unless the code touches it. For derived resources (progress, conversions) define which model's `updated_at` drives `updated_since` or annotate `Greatest(...)` across related tables; missing this silently drops changes. Needs a per-resource test ("child changed, parent returned"). Also `queryset.update()` and `bulk_update()` bypass `auto_now`; any code path updating these tables that way must set `updated_at` explicitly. Index `(updated_at, id)` per resource table; confirm a model has `updated_at` at all (earlier research flagged `User` as not obviously having one).
9. Deletions are invisible (settled). State the documented workaround: consumers do a periodic full resync (for example weekly) and diff the id set.
10. Parameter validation: reject a non-ISO or naive datetime with 400 (422 is not used by DRF validation by default); require timezone, or treat naive as UTC and say so. Return timestamps in UTC with `Z`/offset.

## 8. Cursor pagination in DRF

- Subclass `CursorPagination` once in the API app: `ordering = ("updated_at", "id")`, `page_size = 100`, `page_size_query_param = "page_size"`, `max_page_size = 1000` (values for the spec to confirm). DRF's docs list the requirements for the ordering field: unchanging, unique or nearly unique, non-nullable, not float, indexed; and note the `-created_at` style example [fetched].
- Important tension to record in the spec: DRF's docs say the ordering field should be unchanging, set once on creation. `updated_at` changes on every update, so a row moving between pages mid-run is expected (see 7.7). It is acceptable for sync because duplicates are tolerated and none are lost, but it differs from the documented ideal. Say so and rely on the `id` tiebreak.
- `max_page_size` is not a documented `CursorPagination` option in the DRF docs page [fetched]. In the source, `CursorPagination` inherits `get_page_size` using `page_size_query_param` and `max_page_size`, so it works, but confirm against the installed DRF 3.17 with a test that `?page_size=100000` is capped.
- `ordering` must be a tuple/list on the pagination class; a `ordering` filter backend on the view can override it. Do not install `OrderingFilter` on these views; fixed order is a sync correctness property.
- Cursor is opaque base64; never document its structure. A large `offset` can occur when many rows share an `updated_at`; DRF caps via `offset_cutoff = 1000` (default), which can raise a 404 "Invalid cursor" on pathological ties. Keep `(updated_at, id)` as a tuple so ties are rare; test with a bulk-updated cohort of more than 1000 rows sharing a timestamp (a real scenario: a bulk admin action or migration touching `updated_at`). If this is realistic, raise `offset_cutoff` or use a custom keyset pagination on the pair [knowledge of DRF source; verify].
- Envelope: DRF CursorPagination returns `{next, previous, results}` and no `count` (no COUNT query). Keep it; document `next` as an absolute URL and tell clients to follow it verbatim (it also preserves filters).
- Make sure `get_queryset` is already filtered by site before pagination and uses `select_related`/`prefetch_related`; assert query count in a test (N+1 detection) at page size max.
- Behind a reverse proxy, `next` URLs are built from the request host and scheme; set `SECURE_PROXY_SSL_HEADER` and a correct Host so `next` is `https://` and on the right site host. Otherwise the follow-up request goes to http (leaking the bearer key) or the wrong host.

## 9. Throttling

- Use a custom throttle subclassing `SimpleRateThrottle` (or `ScopedRateThrottle`) whose `get_cache_key` returns `throttle_<scope>_<key public id>`, not IP. Authenticated requests only reach it after auth, so the `request.auth` is the key object. Put the scope name in settings `DEFAULT_THROTTLE_RATES`.
- Add a second, unauthenticated-attempt throttle keyed on IP for 401 storms (see 5); `AnonRateThrottle` semantics but applied before auth failure responses. Note DRF runs throttles after authentication and permission checks (`initial()` order: authentication, permissions, throttles), so failed-auth requests are not throttled by view throttles at all. The IP throttle for bad keys must therefore be done inside the authentication class or a middleware, which is a real gap in a naive setup.
- Shared cache is mandatory in production: DRF throttles use Django's cache backend [fetched]. `LocMemCache` is per process (each gunicorn worker has its own counter, so the effective limit is rate times worker count, and it resets on restart), so it is only "okay for simple setups" [fetched]. Use Redis, Memcached or the database cache backend in the concrete project's `CACHES`; the DB cache is acceptable for a low-volume machine API. Add a system check or an app setting that warns if the cache backend is LocMem and the API is enabled in non-DEBUG. Check `config/settings_base.py` `CACHES` for what the demo project does.
- DRF throttles "are open to race conditions" and may let a few extra requests through [fetched]; fine for abuse protection, not for billing. Do not describe them as strict quotas.
- Rates: scripts that page full tables need headroom. Suggest `60/min` sustained per key for a 100-row page, with `100/min` for burst; or `1000/hour`. Tie the numbers to the maximum page size: a full sync of 100k rows at 100 per page is 1000 requests, which at 60/min takes ~17 minutes; document it, or raise page size/rate. Rates configurable via the app setting (`API_THROTTLE_RATES`).
- Responses: DRF returns 429 with `Retry-After: <seconds>` when the throttle defines `wait()` (the built-in rate throttles do) [fetched]. Tell the script author to honour `Retry-After` in the Python example (sleep then retry), and to back off with jitter on 429/5xx. Optional `X-RateLimit-*`/`RateLimit-*` headers are not provided by DRF; the IETF `RateLimit` header fields draft is still a draft, so skip in v1 [knowledge]. `Retry-After` is enough (RFC 6585 for 429) [knowledge].
- Throttle after auth means a revoked key's requests cost no cache entries; good.

## 10. Versioning

- URL path prefix `/api/v1/` via a plain `path("api/v1/", include(...))`, as already planned. The earlier research said `URLPathVersioning` is only needed once v2 exists; agree. Additive changes (new fields, new endpoints, new optional filters) stay in v1; removing/renaming a field, changing a type or semantics needs v2. Document this contract and that clients must ignore unknown fields. Never reuse a field name for a different meaning. Keep the scope names stable (they are stored on keys). Add a `Deprecation`/`Sunset` header only when a v2 exists.

## 11. DRF settings hardening

Recommended `REST_FRAMEWORK`:

- `DEFAULT_RENDERER_CLASSES = ["rest_framework.renderers.JSONRenderer"]` (no browsable API, no `BrowsableAPIRenderer`, and do not include `rest_framework` templates in INSTALLED_APPS exposure beyond need). With JSON only, `?format=api` and Accept `text/html` fall back to JSON or 406. Set `URL_FORMAT_OVERRIDE = None` so `?format=` cannot select a renderer.
- `DEFAULT_PARSER_CLASSES = []` is possible for read-only, or `[JSONParser]`; with GET/HEAD/OPTIONS only there is nothing to parse. `http_method_names = ["get", "head", "options"]` on the base viewset, and also `ReadOnlyModelViewSet`. Note OPTIONS metadata in DRF returns field descriptions; set `DEFAULT_METADATA_CLASS` to a minimal one (or `None`) if you do not want serializer structure exposed (it is behind auth either way).
- `DEFAULT_AUTHENTICATION_CLASSES = [ApiKeyAuthentication]` only. No `SessionAuthentication` (settled). `DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.IsAuthenticated"]`-equivalent default of deny, e.g. a project `HasApiKey` class, set globally so a forgotten per-view setting fails closed (DRF's own default is `AllowAny`, which is the dangerous one). Per-view `required_scope = "users"` consumed by a single `HasScope` permission class on the shared base viewset. Global default plus a base-class attribute is safer than per-view everywhere. Add a test that iterates the router/URL patterns under `/api/` and asserts that each view has an auth class and a non-`AllowAny` permission and a declared scope.
- Important: `IsAuthenticated` checks `request.user and request.user.is_authenticated`. A key not tied to a user means `request.user` is `AnonymousUser`, which makes `IsAuthenticated` always fail. Options: return a lightweight authenticated principal object from `authenticate()` (a non-model class with `is_authenticated = True`, a `site` and the key), or write a permission class that checks `isinstance(request.auth, ApiKey)`. The latter is simpler and avoids pretending a key is a user. Also set `UNAUTHENTICATED_USER = None` so nothing accidentally uses `AnonymousUser` semantics [knowledge; DRF settings docs]. Verify nothing in the project (middleware, `request.user` in templates/logging) assumes a real user on API requests.
- `DEFAULT_THROTTLE_CLASSES` and `DEFAULT_THROTTLE_RATES` globally, so a new viewset is throttled by default.
- `DEFAULT_PAGINATION_CLASS` set to the cursor class and `PAGE_SIZE` unset (cursor class sets its own); `DEFAULT_FILTER_BACKENDS = [DjangoFilterBackend]`.
- `EXCEPTION_HANDLER`: custom or default; make sure 500s return a generic JSON body, never a stack trace. `DEBUG` HTML 500 pages must never be reachable in prod (settings_prod).
- `TEST_REQUEST_DEFAULT_FORMAT = "json"`; `DATETIME_FORMAT = ISO_8601` (default); `COERCE_DECIMAL_TO_STRING` default true.
- CSRF: `APIView.as_view` marks views csrf-exempt; with no session auth there is no cookie-based path, so this is fine [earlier research agrees].
- Include `django.contrib.sites` host check: keep `ALLOWED_HOSTS` strict; the earlier research's `UnknownSite` fail-open must be an explicit auth rejection.

## 12. drf-spectacular with a custom authentication scheme

- Without an extension, custom auth classes produce a warning and are omitted from the schema [fetched]. Write an `OpenApiAuthenticationExtension` with `target_class = "freedom_ls.<api_app>.authentication.ApiKeyAuthentication"`, `name = "ApiKeyAuth"`, and `get_security_definition` returning `{"type": "http", "scheme": "bearer", "bearerFormat": "flsk_<id>.<secret>", "description": "..."}` (OpenAPI 3 http bearer, not `apiKey in header`; the doc example uses `apiKey` but http bearer is the accurate model for `Authorization: Bearer`) [fetched for the class shape; scheme choice is recommendation].
- The extension module must be imported at startup: import it in the app's `AppConfig.ready()` [fetched].
- Serve the schema from `SpectacularAPIView` with `SERVE_PERMISSIONS` and `SERVE_AUTHENTICATION` set to the API key classes so it is behind the same auth (these are on drf-spectacular's Settings page, not re-fetched; verify names). Setting `SERVE_AUTHENTICATION` matters: its default falls back to DRF defaults, which here would already be the key class, but being explicit prevents drift. The schema endpoint should need no scope or a dedicated trivial one; decide in the spec.
- Because `SpectacularAPIView` renders YAML/JSON, add its renderers explicitly if the global renderer list is JSON only; check `?format=json` and Accept handling. Do not add `SpectacularSwaggerView`/`SpectacularRedocView` (settled).
- Set `SPECTACULAR_SETTINGS`: `TITLE`, `VERSION`, `SERVE_INCLUDE_SCHEMA = False`, `COMPONENT_SPLIT_REQUEST` not needed (read-only), `SCHEMA_PATH_PREFIX = "/api/v1"`, and `ENUM_NAME_OVERRIDES` if choices collide. Scopes can be documented per operation via a `@extend_schema` or a small `AutoSchema` subclass that adds the `required_scope` to the operation description; the `security` entry may carry the scope as an OAuth-style list but for http bearer keep it in the description.
- Tests: a CI test that generates the schema with `--validate --fail-on-warn` equivalent (`manage.py spectacular --validate --fail-on-warn`) so an unannotated serializer method field or missing extension fails the build; and a test that the schema endpoint returns 401 without a key. Annotate `SerializerMethodField` with `@extend_schema_field`.

## 13. Further hardening and process

- Enforce HTTPS: the idea says "docs say HTTPS only". Also consider an authenticator check that refuses (401, same body) when `not request.is_secure()` in production (honouring `SECURE_PROXY_SSL_HEADER`); the key is already burnt on first hit over http, so the refusal only reduces repeat exposure; keep it cheap and tested.
- Per-site view of keys: admin list filtered to `site=current` for site admins; a site admin must not see or issue keys for another site (multi-tenant pitfall in the admin itself, not just the API). Keys must be issued for the admin's own site only.
- Guard `request.auth.site` against `FORCE_SITE_NAME` semantics noted in the earlier research.
- Test list (beyond the earlier research): header variants (lowercase scheme, double spaces, empty token), constant error body across all failure reasons, debounced `last_used_at`, revoked effective on the next request, expiry boundary, tie handling across a page boundary, `?page_size` cap, out-of-order `updated_at` fixture, throttle cache key is the key id, 429 includes `Retry-After`, schema behind auth, every `/api/` route fails closed.
- Python example hygiene: read the key from an environment variable, never hard-code (project rule); use `httpx.Client` with a timeout; follow `next` verbatim; upsert by id; checkpoint = max `updated_at` minus overlap; honour `Retry-After`.

## 14. Summary of concrete recommendations

1. Key = `flsk_<public_id>.<secret>`; 256-bit `token_urlsafe` secret; SHA-256 (optionally HMAC with env pepper) at rest; lookup by public id; `compare_digest`; shown once.
2. No slow hash for keys.
3. Debounced conditional `UPDATE` for `last_used_at` (5 to 15 min), only after successful auth.
4. `revoked_at` and `expires_at` timestamps; revoke is final; checked every request; default expiry in the admin form.
5. All auth failures: identical 401 with `WWW-Authenticate: Bearer realm="api"` and one message; missing scope 403; implement `authenticate_header`.
6. Scrub and never log `Authorization`; log only the key public id; test the Sentry scrubbing.
7. `updated_since` inclusive, at-least-once, upsert by id, consumer checkpoint = max seen minus overlap (5 minutes minimum); optionally a server safety lag; per-resource `updated_at` coverage tests; `update()`/`bulk_update()` bypass hazard.
8. `CursorPagination` ordering `("updated_at", "id")`, explicit page size and verified max cap, composite index, tie test beyond `offset_cutoff`.
9. Per-key throttle on key id, shared cache required (LocMem is per process), separate IP throttle for failed auth done outside the DRF throttle phase, honour `Retry-After` and 429.
10. URL versioning by plain include; additive-only within v1.
11. REST_FRAMEWORK: JSON renderer only, `URL_FORMAT_OVERRIDE = None`, key auth only, default-deny permission (do not rely on DRF default `AllowAny`), `UNAUTHENTICATED_USER = None`, throttles and pagination global, an every-route-fails-closed test.
12. drf-spectacular: `OpenApiAuthenticationExtension` (http bearer) imported in `ready()`, schema served behind key auth, validate in CI with fail-on-warn.

## References

- GitHub, Behind GitHub's new authentication token formats (prefix, checksum, entropy) [fetched]: https://github.blog/engineering/platform-security/behind-githubs-new-authentication-token-formats/
- DRF pagination, CursorPagination (ordering requirements, ties) [fetched]: https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- DRF throttling (cache backend, LocMem, race conditions, Retry-After) [fetched]: https://www.django-rest-framework.org/api-guide/throttling/
- drf-spectacular customization, OpenApiAuthenticationExtension [fetched]: https://drf-spectacular.readthedocs.io/en/latest/customization.html#specify-authentication-with-openapiauthenticationextension
- drf-spectacular settings (SERVE_PERMISSIONS, SERVE_AUTHENTICATION) [not re-fetched]: https://drf-spectacular.readthedocs.io/en/latest/settings.html
- Django password storage (slow hashers are for passwords) [fetched]: https://docs.djangoproject.com/en/5.2/topics/auth/passwords/
- DRF authentication (`authenticate_header` yields 401 vs 403) [knowledge]: https://www.django-rest-framework.org/api-guide/authentication/
- DRF settings (`UNAUTHENTICATED_USER`, `URL_FORMAT_OVERRIDE`, defaults) [knowledge]: https://www.django-rest-framework.org/api-guide/settings/
- RFC 6750, Bearer Token Usage (WWW-Authenticate, insufficient_scope) [knowledge]: https://www.rfc-editor.org/rfc/rfc6750
- RFC 9110, HTTP Semantics (401 challenge, Retry-After) [knowledge]: https://www.rfc-editor.org/rfc/rfc9110
- RFC 6585, 429 Too Many Requests [knowledge]: https://www.rfc-editor.org/rfc/rfc6585
- OWASP REST Security Cheat Sheet (API keys, no keys in URLs, generic errors) [knowledge]: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- OWASP Authentication Cheat Sheet (uniform responses, timing) [knowledge]: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Stripe API keys and restricted keys (prefix, display of key tail) [knowledge]: https://docs.stripe.com/keys
- Sentry Python data scrubbing (`send_default_pii`, `EventScrubber`) [knowledge]: https://docs.sentry.io/platforms/python/data-management/sensitive-data/

status: ok
