# Research: UX patterns (admin key issuing and developer experience)

There is no end-user UI. The UX surfaces are the Django admin key flow and the developer experience of the API.

## Repo facts

- django-unfold IS used: `config/settings_base.py` lines ~87-100 list `unfold.apps.BasicAppConfig`, `unfold.contrib.*`, with `unfold.contrib.import_export` before `import_export`.
- FLS admin rules (`claude_plugins/fls-dev/skills/admin-interface/SKILL.md`): every admin extends `SiteAwareModelAdmin` (Unfold `ModelAdmin` re-exported); the `site` field is never shown or editable (excluded automatically); inlines use `SiteAwareTabularInline`/`SiteAwareStackedInline`. The ds skill says use `readonly_fields`, `fieldsets`, `@admin.register`, and read the unfold theme resource (`admin_unfold.md`) before writing admin code.
- Consequence: "choose site" in the idea cannot be a form field in the admin. The site comes from the request host (as for every FLS admin), so the admin form must not offer a site picker. The spec should say the key is issued on the admin host's site. Flag this against the idea's "choose site" wording.

## 1. Show the secret once

Patterns seen:
- djangorestframework-api-key: after creating a key in the admin, the full key appears once in a success message banner (messages framework). The list then shows only the prefix, for identification. Lost key means generate a new one.
- GitHub, Stripe, Sentry: a dedicated screen or modal right after creation shows the token with a copy button and a "you will not be able to see this again" warning. Afterwards only a prefix or last characters are listed.

Options in Django admin:
- A. Messages framework (`messages.success` from `save_model`/`response_add`). Cheap and idiomatic. Risk: the message is stored in the session or cookie storage, so the secret may be persisted in the session store or cookie. It also vanishes on reload, and a warning-styled message is easy to miss. Mitigate with a message-level `mark_safe` of nothing (escape it), and a `<code>` wrapper only through `format_html`.
- B. Dedicated confirmation page: `response_add` renders a one-off template (not redirected, so the secret is never stored in the session or in a URL) with the key in a monospace box, a copy button, and "Store this now, it cannot be shown again". Slightly more code, no secret in session storage, clearer UX. Render with a POST response, set `Cache-Control: no-store`.

Recommendation: B (dedicated page rendered directly from `response_add`, no redirect, `no-store`). If the spec wants minimal scope, A is acceptable but should state the session-storage trade-off. Either way: generate the plaintext key in `save_model` only on create, keep it on the admin instance (e.g. `obj._plaintext_key`) for the response, store only the hash and a short prefix, and never put it in the audit log.

## 2. Naming and prefix

- Require a human `name`/label (e.g. "Nightly CRM sync"). Stripe/GitHub/Sentry all require a name; it is what admins recognise later. Not unique-constrained per site is fine, but warn on duplicates or make unique per site for clarity.
- Key format with a recognisable prefix and a short public identifier, e.g. `flsk_<8-char-id>.<secret>` (Stripe `sk_live_`, GitHub `ghp_`, DRF-api-key `prefix.secret`). Benefits: secret scanners can detect leaks, the admin can show the public part, and lookup is by prefix then constant-time hash compare. Show the prefix in the list as `flsk_ab12cd34...`.
- List columns: name, prefix, scopes, created, last used, expires, status (Active / Expired / Revoked as a coloured Unfold label or `display` with `label=`), created by if tracked.

## 3. Revoke: action vs field

- Stripe "roll/delete", GitHub "delete", Sentry "revoke": revoke is a deliberate, irreversible action rather than a casual checkbox.
- Recommendation: store `revoked_at` (nullable timestamp, plus optionally `revoked_by`), not a bare boolean: gives audit data for free. Expose it as an admin action ("Revoke selected keys") and as a button on the change page (Unfold `actions_detail`), not as an editable field. Keep `revoked_at` read-only.
- Confirmation: Django admin actions that need confirmation use an intermediate confirmation page (as the built-in delete does). Use that for the revoke action: list the keys affected, a "Revoke" submit and cancel. The detail-page button should go through the same confirmation page. Write one audit-log entry per key revoked.
- Do not allow un-revoke; issue a new key instead. Keep the revoke confirmation text explicit about immediate effect on scripts.
- Disable the built-in "delete selected" for keys (or leave only for superusers) so the audit trail and `last_used_at` survive; revocation is the supported removal path.

## 4. Read-only after issue

- Make everything except name read-only after creation (`get_readonly_fields` returns all of site, prefix, hash, scopes, expiry, last_used_at, created_at, revoked_at when `obj` exists). Changing scopes or expiry on a live key is the main way to surprise a running script; the safer pattern (GitHub fine-grained tokens allow scope edits, Stripe restricted keys allow permission edits) is a choice. Recommendation: scopes and expiry immutable after issue (revoke and reissue); name editable. Simple and auditable.
- Revoked or expired keys: fully read-only, including name (`has_change_permission` false, or all fields read-only). Add `has_add_permission` per normal; never show the hash field at all (exclude it).
- Add form: name, scopes (multi-select checkboxes over the four names, with a one-line description of each), expiry (optional date-time, with help text; consider offering a default such as 90 days and "no expiry" explicit, per GitHub's expiry-first design). Do not allow an expiry in the past (form `clean`).
- `last_used_at`: update at most once per interval (e.g. a minute or hour) to avoid a DB write on every request; say in the docs that it is approximate. This is a write on a read-only API's hot path.

## 5. Error response bodies

- DRF default: `{"detail": "Authentication credentials were not provided."}` with a `WWW-Authenticate: Bearer` header on 401 (requires the authentication class to define `authenticate_header`; otherwise DRF turns 401 into 403). Easy to miss: the custom authentication class must return `"Bearer"` from `authenticate_header`.
- RFC 9457 problem details (`application/problem+json`, members type/title/status/detail/instance, extension members allowed). Pros: standard, machine-readable `type`. Cons: needs a custom exception handler and renderer content type; contradicts "JSON renderer only" slightly; the packages are small but add a dependency.
- Recommendation: keep DRF's `{"detail": "..."}` for 401/403/404/405/429 and add a stable machine code for the cases scripts branch on, via a custom exception handler that returns `{"detail": str, "code": str}` (DRF exceptions already carry `.get_codes()`). For validation errors (400) use DRF's field-keyed dict: `{"updated_since": ["Enter a valid date/time."]}` and `{"cursor": ["Invalid cursor."]}` (DRF's cursor pagination raises NotFound "Invalid cursor" 404 by default; the spec should decide: recommend overriding to 400 with `{"cursor": [...]}` since a bad cursor is a client input error).
- 401: one generic message for every failure (missing, malformed, unknown, revoked, expired, wrong site), e.g. `{"detail": "Invalid or missing API key.", "code": "authentication_failed"}`; never distinguish, per the idea.
- 403 missing scope: `{"detail": "This API key does not have the 'users' scope.", "code": "permission_denied"}` (naming the needed scope is helpful and not a leak, since the key is already authenticated).
- 429: `{"detail": "Request was throttled. Expected available in N seconds."}` plus the `Retry-After` header (DRF sets it). Document that scripts must honour `Retry-After`.
- Never echo the key or Authorization header in any error body. Never return HTML error pages under `/api/`: ensure 404/500 JSON for the API prefix.
- `updated_since` parsing: accept ISO 8601 with timezone; reject naive datetimes (400) or document them as UTC. Recommend rejecting naive input to avoid silent timezone bugs.

## 6. Pagination envelope

- DRF `CursorPagination` returns `{"next": url|null, "previous": url|null, "results": [...]}`; no count (cheap, correct for cursor). GitHub uses `Link` headers; Stripe uses `{"object":"list","data":[...],"has_more":bool}` plus `starting_after`.
- Recommendation: keep the DRF default envelope (next/previous/results, absolute URLs, cursor opaque). Document: follow `next` until null; do not build cursors; do not assume page sizes. Page size via `page_size` query param with a capped maximum (document default and cap; values above the cap are clamped, not an error, which is DRF's behaviour).
- Incremental sync guidance, to put in the docs: store the max `updated_at` seen; next run use `updated_since=<that value>` (inclusive, so expect to see the boundary record again; upserts by `id` must be idempotent); ordering is `(updated_at, id)` ascending so a crash mid-run can resume from the last stored value; deletions are not reported, so periodically do a full resync if deletions matter.
- Cursor pagination keeps `updated_since` and other query params in `next` links; check that in a test.

## 7. Docs page

What good getting-started docs do (Stripe, GitHub):
- Start with a working request in under a minute: authentication, then first call, then pagination, then errors.
- Copy-paste, runnable code with the placeholder visible and the key read from an environment variable (never hardcoded).
- State base URL form per site, HTTPS only (and "a key sent over http is compromised, revoke it"), versioning under `/api/v1/`.
- Explain scopes in a table (scope, endpoints), rate limits and `Retry-After`, error shape with examples, and the OpenAPI schema location.

Suggested httpx example (the spec can adapt):

```python
import os
import httpx

BASE_URL = "https://your-site.example.com/api/v1"
headers = {"Authorization": f"Bearer {os.environ['FLS_API_KEY']}"}

def fetch_all(path: str, params: dict[str, str] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    url: str | None = f"{BASE_URL}{path}"
    with httpx.Client(headers=headers, timeout=30) as client:
        while url:
            response = client.get(url, params=params if url.endswith(path) else None)
            if response.status_code == 429:
                time.sleep(int(response.headers.get("Retry-After", "5")))
                continue
            response.raise_for_status()
            body = response.json()
            rows.extend(body["results"])
            url = body["next"]
    return rows

users = fetch_all("/users/", {"updated_since": "2026-01-01T00:00:00Z"})
```

(Spec writers: the example must use `import time`, keep the type hints rule, and avoid re-sending params on `next` URLs because they already contain them; the snippet above is a sketch to be tested, not final. Consider testing the docs example in the test suite so it cannot rot.)

- Keep the docs a single page that each resource child extends with one section; structure it with a stable per-resource template (scope required, filters, fields table, example).
- OpenAPI: drf-spectacular schema served at e.g. `/api/v1/schema/` behind key auth. Set `SPECTACULAR_SETTINGS` title/version/description, declare the bearer security scheme (a small `OpenApiAuthenticationExtension` for the custom auth class so the schema shows `bearerAuth` http/bearer), document `updated_since` and error responses (401/403/429) globally via a postprocessing hook or per-view `extend_schema`. Fail the CI build on schema warnings (`spectacular --validate --fail-on-warn`) so every resource child stays documented. Because the schema needs a key, the docs page should say how to fetch it (`curl -H "Authorization: Bearer ..."`). Note the schema requires some scope or none: recommend any valid key, no scope.
- Fields documented from serializer `help_text` so the schema and the docs table agree.

## Summary of concrete recommendations

1. Admin: Unfold `SiteAwareModelAdmin`; no site picker (site from host); flag the idea's "choose site" wording.
2. Show the key once on a dedicated no-redirect, no-store page rendered by `response_add`; messages framework is the fallback with a session-storage caveat.
3. Key format `flsk_<public id>.<secret>`; store hash plus prefix; list shows prefix, name, scopes, last used, expiry, status label.
4. Name required; scopes and expiry immutable after issue; revoked or expired keys fully read-only; no un-revoke.
5. Revoke via admin action with a confirmation page, plus a detail-page button; `revoked_at` timestamp; one audit entry per revoke and per issue; no plaintext in the audit log.
6. Errors: DRF `{"detail", "code"}`; 401 generic and always with `WWW-Authenticate: Bearer`; 403 names the missing scope; 429 with `Retry-After`; 400 field-keyed for `updated_since` and `cursor` (override DRF's 404 on a bad cursor); JSON for all `/api/` errors.
7. Pagination: DRF default next/previous/results; document inclusive `updated_since` and idempotent upserts.
8. Docs: one page, env-var key, httpx loop honouring `Retry-After`, scope table, error examples, HTTPS-only warning, tested example; spectacular schema with bearer security scheme and validate in CI.
9. Throttle `last_used_at` writes.

## References

- https://github.com/florimondmanca/djangorestframework-api-key/blob/master/docs/guide.md (key shown once in an admin success message; prefix for identification)
- https://www.rfc-editor.org/rfc/rfc9457.html (problem details members, media type, extension members)
- Repo: `claude_plugins/fls-dev/skills/admin-interface/SKILL.md`, `claude_plugins/django-stack/skills/admin-interface/SKILL.md`, `config/settings_base.py`
- Stripe, GitHub, Sentry and DRF behaviours (token screens, list envelopes, `authenticate_header`, `Retry-After`, cursor 404) are from background knowledge, not fetched this session; verify against their docs before citing in the spec.

status: ok
