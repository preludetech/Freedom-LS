# Research: known complaints about read-only key-authenticated export APIs

Scope: what API consumers and DRF implementers complain about, and what this spec (users endpoint plus the shared foundation) should do. Items marked (web) have a cited source. Items marked (experience) come from general practice and were not verified with a source in this run.

## A. Consumer complaints

| # | Complaint | Evidence | What the spec should do |
|---|---|---|---|
| A1 | Key shown once and lost, with no recovery | (experience) | Keep show-once (already settled). Admin issue screen must say clearly "copy it now". Document that the remedy is issue a new key and revoke the old one. No "reveal" feature. |
| A2 | Cannot tell which key is which | (experience) | Key model needs a required human `name`/label (who or what script uses it), a non-secret prefix or last 4 characters shown in admin lists and audit log entries, `created_at`, `last_used_at`. Never log the key itself. |
| A3 | Keys silently expire | (experience) | Show expiry in admin list, with a filter for "expiring soon". Expired and revoked keys must still return the same generic 401 (settled), but docs should list "expired or revoked" as a cause of 401. Make expiry optional and visible. Email warnings are out of scope, so say that. |
| A4 | Unclear 401 versus 403 | (experience) | 401 for missing, malformed, unknown, expired, revoked or wrong-site key, with a `WWW-Authenticate: Bearer` header. 403 only for a valid key lacking the endpoint scope. Use a stable JSON error body with a machine-readable `code`. The 403 body may name the missing scope, because the key is already authenticated. Document the table in the docs page. |
| A5 | Rate limits without `Retry-After` | (web) DRF throttling docs, see References | DRF sets `Retry-After` on 429 by default (from `wait()`). Add a test asserting the header. Document the 429 and the retry rule in the Python example (sleep for `Retry-After`). Consider `X-RateLimit-*` headers as nice to have, but do not build them unless asked. |
| A6 | Cursor pagination cannot jump or resume, and breaks when ordering changes | (web) DRF pagination docs, discussion 7888 | Cursors are opaque and short-lived in meaning: document that a client resumes by saving the `next` URL, and for a fresh run by using `updated_since` as a watermark. Document that cursors must not be stored across API versions or ordering changes. Ordering `(updated_at, id)` is fixed and not client-selectable (no `ordering` query param). Say plainly that there is no page-number jump or total count. |
| A7 | Missing rows with `updated_since`: ties, clock skew, transaction commit order | (web) ERP.net incremental pull, MemberJunction watermark overlap, singer tap-shopify PR 197 | Four rules. (1) `updated_since` is inclusive (settled), so ties at the boundary are re-read, not lost. (2) `updated_at` must be set by the server at write time. Check that every write path touching user data, including `QuerySet.update()` and `bulk_update`, also sets `updated_at`, otherwise rows are never returned. Data-source research already flags hazards. (3) A transaction that commits late with an earlier timestamp can be missed. Document that consumers should subtract an overlap (suggested 5 minutes) from the stored watermark and upsert by `id` idempotently. (4) Consumers should advance the watermark only after the full run succeeds, using the max `updated_at` seen, not the client clock. The example script must do (3) and (4). |
| A8 | No deletion feed | (web) Elementary and ERP.net note tombstones are how feeds handle this; (experience) | Already out of scope. Docs must say so prominently: deleted users never appear, and a full re-sync is the only way to detect deletions. Expose `is_active` so deactivation is visible. Leave a roadmap pointer, not code. |
| A9 | Inconsistent timestamps and timezones | (experience) | All timestamps UTC ISO 8601 with `Z` or offset, one format across every resource. Set `USE_TZ` rendering explicitly in the DRF settings and test the format. `updated_since` parser must accept the same format, require a timezone, and return 400 with a clear message on a naive or invalid value. Make the 400 body name the parameter. |
| A10 | Breaking changes without versioning | (experience) | `/api/v1/` prefix (settled). Docs state the policy: adding fields and endpoints is non-breaking, removing or renaming needs `v2`. Explicit field lists (settled) guard against accidental additions. Consumers should ignore unknown fields. Commit the generated OpenAPI schema and add a test or CI diff so schema changes are deliberate. |

## B. DRF implementer complaints

| # | Complaint | Evidence | What the spec should do |
|---|---|---|---|
| B1 | `CursorPagination` with non-unique ordering fields gives duplicates or skips | (web) DRF pagination docs, PR 5459, discussion 7888 | DRF's "position plus offset" cursor copes with ties in a single field, but users report problems when several ordering fields are used and the first is non-unique. Spec: pagination subclass sets `ordering = ("updated_at", "id")` and a test creates many rows with identical `updated_at` (batch create) and asserts a full walk returns every row exactly once, with a page size smaller than the tie group. If the test fails with DRF's built-in class, the spec must call for a custom cursor on the `(updated_at, id)` tuple (keyset). Do not trust the docs alone. |
| B2 | `CursorPagination` and filter interaction | (web) discussion 7888; (experience) | `updated_since` filter applies before pagination, the cursor encodes only position, so changing filter parameters between pages is undefined. Document that all query parameters must stay identical across pages (the `next` URL already carries them). Test that a filtered walk works. Cursor pagination reorders by `ordering`, so `django-filter`'s `OrderingFilter` must not be enabled. Also the cursor pagination `ordering` attribute must not be overridden by view-level `ordering_fields`. |
| B3 | Throttling with `LocMemCache` is per process, not shared across gunicorn workers | (web) DRF throttling docs, Django ticket 27641, reintech guide | The effective limit multiplies by the worker count. This is the open question in the idea. Spec should require a shared cache (Redis, Memcached or database cache) for any deployment where throttling matters, state it in the app setting docs, and add a startup check (Django system check) that warns when the throttle cache is `LocMemCache` and the API app is enabled. Use a dedicated named cache alias for throttling. DRF throttles are non-atomic, so the limit is fuzzy; document that. |
| B4 | Throttle cache key is per user or per IP, not per API key | (web) DRF throttling docs; (experience) | `UserRateThrottle` and `AnonRateThrottle` key on user or IP. Keys here have no user, so write a custom `SimpleRateThrottle` whose `get_cache_key` returns the key's database id (never the raw key or hash in cache keys, to avoid secrets in cache). Unauthenticated requests should be throttled by IP before auth failure to slow key guessing, and failed auth must not be free. Test that two keys on the same IP have independent buckets. |
| B5 | `last_used_at` write amplification | (experience) | Writing on every request means a row update per call, row lock contention and extra WAL. Update at most once per interval (suggest 5 to 15 minutes): compare in memory and issue a conditional `UPDATE ... WHERE last_used_at < now - interval`, with `update_fields` so `updated_at` is not touched and no admin audit noise is created. State precision in the docs (last used, accurate to the interval), and record this in the retention paragraph of the security doc. |
| B6 | drf-spectacular schema problems with custom authentication | (web) drf-spectacular issues 99, 387, 626, customization docs | An authentication class with no extension logs a warning and is dropped from the schema, so the security scheme is missing. Spec: register an `OpenApiAuthenticationExtension` for the key class (HTTP bearer scheme), set `SPECTACULAR_SETTINGS` explicitly, and run `spectacular --validate --fail-on-warn` in a test or CI step. The schema endpoint itself needs the key authentication and a scope decision (suggest any valid key, no particular scope). Custom pagination and filter classes need schema support too, or the cursor and `updated_since` parameters are undocumented. Add `extend_schema` where the serializer is not discoverable. |
| B7 | N+1 queries | (experience) | Users has no heavy relations now, but the foundation sets the pattern. Add a `django_assert_max_num_queries` test per endpoint, and require `select_related`/`prefetch_related` (settled). Fixed query count regardless of page size. |
| B8 | OPTIONS metadata leaks information | (experience) | DRF `SimpleMetadata` on OPTIONS lists renderer, parser and field details. Even though auth is required, set `DEFAULT_METADATA_CLASS = None` or a minimal class, or restrict OPTIONS to the same auth. OPTIONS is settled as allowed, so return only `Allow` and no serializer field metadata. Test that an unauthenticated OPTIONS gets 401. Note that the CORS preflight is not needed because consumers are scripts; do not add CORS. |
| B9 | HEAD handling | (experience) | DRF routes HEAD to the GET handler, so it runs the full query and throttles like GET. Acceptable, but test that HEAD returns the same status, headers and no body, is authenticated and counts against the throttle. |
| B10 | Browsable API and session auth leak through defaults | (experience) | Set `DEFAULT_RENDERER_CLASSES` to JSON only, `DEFAULT_AUTHENTICATION_CLASSES` to the key class only (settled). Because FLS is site-aware, the queryset manager must filter by the key's site, never the request user. Add a test that a session cookie alone returns 401. |
| B11 | Large page sizes and unbounded `page_size` params | (experience) | Cap `max_page_size` (settled). Reject, do not clamp silently, invalid values like 0 or negative. Choose a default of about 100 and a cap of about 500 to 1000 for a first version. |

## C. Summary of spec decisions to record

1. Key model fields: name, prefix, hash, site, scopes, expires_at, revoked state, created_at, last_used_at.
2. Error contract: 401 versus 403 table, `WWW-Authenticate`, stable JSON `code`.
3. Throttle: custom per-key throttle keyed on key id, shared cache required, system check for `LocMemCache`, `Retry-After` tested.
4. Pagination: fixed `(updated_at, id)` ordering, a tie test, no client ordering, no total count.
5. `updated_since`: inclusive, timezone-aware, 400 on bad input. Docs prescribe overlap window and idempotent upserts, and the example script does both.
6. `last_used_at` is throttled to one write per interval.
7. Schema: authentication extension, validate with fail-on-warn, committed schema diff.
8. OPTIONS minimal, HEAD tested, JSON renderer only.
9. Docs: state the no-deletion-feed limit, HTTPS only, versioning policy and how to rotate keys.

## References

- https://www.django-rest-framework.org/api-guide/pagination/ (cursor pagination, position plus offset design; recalled, the search snippet quoted it)
- https://github.com/encode/django-rest-framework/pull/5459/files
- https://gh.nn.ci/encode/django-rest-framework/discussions/7888 (mirror of the DRF discussion on cursor pagination with non-unique first ordering field)
- https://www.vincentschmalbach.com/defining-stable-ordering-rules-for-cursor-pagination/
- https://dev.to/loburets/cursor-pagination-how-to-do-and-pitfalls-5gon
- https://www.django-rest-framework.org/api-guide/throttling/
- https://code.djangoproject.com/ticket/27641
- https://reintech.io/blog/throttling-rate-limiting-django-rest-framework
- https://docs.erp.net/dev/domain-api/data-sync/incremental-pull.html
- https://docs.memberjunction.org/v6/api/variables/_memberjunction_materialization.WATERMARK_SAFETY_OVERLAP_MS.html
- https://github.com/singer-io/tap-shopify/pull/197
- https://docs.elementary-data.com/api/incremental-sync
- https://support.fivetran.com/hc/en-us/community/posts/38277616619927-Connector-Improvement-Incremental-Update-Sync-Handling
- https://github.com/tfranzel/drf-spectacular/issues/99
- https://github.com/tfranzel/drf-spectacular/issues/387
- https://github.com/tfranzel/drf-spectacular/issues/626
- https://drf-spectacular.readthedocs.io/en/stable/customization.html

status: ok
