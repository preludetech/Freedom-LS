# Research: prior art for the lead monitoring API foundation

Question: what has already been tried for this, here or elsewhere, and what happened?

Limit: no shell, so no `git log`. The spec_dd tree and code comments stand in for history. The orchestrator can run `git log -S"NinjaAPI" -- config/urls.py` if commit-level history is wanted.

## 1. Here

### 1a. There has been no earlier API attempt, only a stub and a sketch

- `freedom_ls/xapi_learning_record_store/api.py` is the only live ninja code: a `Router`, a `/hello` site-check using `get_cached_site` with an `isinstance(site, Site)` guard, and a POST that returns the string "todo". It has `# TODO: Authentication` (line 13) and `# TODO, what are tags for?`. It never got authentication, and its app is not in `INSTALLED_APPS`. It is a probe, not an attempt.
- `freedom_ls/learner_interface/apis.py` is a commented-out ninja sketch (imports `Router`, `Schema`, `HttpError` and allauth headless `x_session_token_auth`). The forms extraction research (`spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/research_current_coupling.md:169`) calls it "a dead Ninja sketch for form progress", 136 lines. It was a learner-facing, session-token API, a different problem from machine keys for scripts.
- `config/urls.py:36,41` holds the commented `NinjaAPI` import and mount.
- Why ninja was abandoned: no record exists. Searches of `spec_dd/` found no decision, retro or note explaining it. Every later mention treats it as dead code: the error-pages research (`spec_dd/3. done/2026-09-06_11:53_error-pages/research_rate_limit_surfaces.md:172`) says "no DRF/ninja API with its own throttle classes". The support-concrete-project-deployment plan (`2026-07-17_13:56_.../2. plan.md:243`) says to leave the commented ninja block untouched. The Django 6 upgrade (`2026-03-12_07:10_upgrade-to-django-6`) kept bumping `django-ninja>=1.5.0` (fixing a UUID converter conflict) even though nothing used it. That cost is a small reason to drop it. The most plausible reading is an unfinished experiment, overtaken by the need to authenticate machines (a gap ninja did not fill either). Do not state a reason in the spec; say "no record exists".
- `spec_dd/corporate-readiness/README.md:185-192` (item 7, "A public REST API") records the same state: ninja is a dependency, the API is commented out, there is no token auth and no documented endpoints. It wants "scoped API tokens per organisation. Read-heavy first." This is a different, later effort (HR sync, organisation scoping). The lead-monitoring keys are site-bound, not organisation-bound. The spec should note that its key model must not block a later organisation-scoped design, but must not build it (CLAUDE.md: do not build what is not requested).
- Earlier foundation research (`research_api_foundation.md`) suggested tying a key to a service user and a role permission. The idea overrode this: keys are not tied to a user, with four scopes. That is consistent with the lessons in section 2 below. Also note it said DRF `ScopedRateThrottle`/cache needs a shared cache.
- Other machine credential patterns in the repo: `WebhookSecret` and `webhooks/signing.py` are outbound only. `django-fernet-encrypted-fields` is reversible and unsuitable. `argon2-cffi` is present, but API keys are high-entropy random strings, so a fast hash (SHA-256) with a lookup prefix is normal and cheap per request. Argon2 on every request is wasteful. This is a spec decision to make explicitly.

### 1b. Decisions in the done specs that bear on this

- `more_lead_admin_exports` (done 2026-10-29): admin exports run on `django-import-export` via `SiteAwareExportModelAdmin` and `FormulaSafeCSV`. Export is gated by view permission only. There is no separate export permission, and its prior-art research flagged "applicant data as sensitive" and left a narrower permission deferred in both earlier specs. Its best-practices research (`research_best_practices.md:61-104`) sets the data-minimisation rule: export only the columns needed, never password hashes, tokens or IP addresses, and exclude them from the Users export. The API users resource (explicit allowlist, no password, groups, permissions, `is_superuser`) is the same stance. The API gives a narrower control than the admin has: scopes are chosen per key.
- Same research: the users export touches the user-erasure register `USER_ERASURE_CASCADE_MODELS` in `freedom_ls/accounts/admin.py`. For the API, an erased user disappears from `updated_since` pulls with no signal, which fits the "no deletion feed" decision but means a downstream copy of erased data persists. This is a POPIA/GDPR point for the security doc: the consumer script owns downstream erasure.
- Its prior art also says a task-run or streamed export has no request, so the site-aware manager does not filter ("must filter `site_id=` explicitly", `simple-application-forms/research_application_pii.md:298-302`). API views run in a request, but authentication must still bind the key's site, as the idea says. If a later child uses `.iterator()` or a background job it must filter explicitly.
- `course-applications-admin` (done 2026-10-08) deliberately had no export ("exporting applicant data wasn't asked for"). File uploads sit behind `SuperuserOnlyAdmin`. The idea's "filename only" rule for uploads (spec 2) follows from this.
- `referral-links` (done 2026-09-12): hits hold no personal data by design (`1. spec.md:21`; hit logging research on minimisation). It reserves the code `api` (`1. spec.md:145`, `RESERVED_REFERRAL_CODES` in the plan), so a top-level `/api/` URL does not collide with referral codes. The roadmap's exclusion of `client_ip`, `user_agent` and the cookie ids from the API follows the signup attribution minimisation. `anon-application-improvements`/`ananomous-course-applications` contain no API decisions. `AnonymousApplicant` holds consent IP and timestamps, and its PII is covered by the application PII research (spec 2's concern, not this one).
- Nobody here has yet written `docs/product/security-and-data-handling.md` content on API keys; this spec must.
- Rate limiting: the error-pages research tabulated existing rate-limit surfaces (allauth, axes) and found none for an API. There is no precedent to reuse for throttle rates or a shared cache. Check `CACHES` in settings; `LocMemCache` per process would make DRF throttles ineffective across workers.

## 2. Elsewhere

Evidence quality note: web search returned few primary post-mortems. Items marked (inferred) are reasoned from what was found, not directly sourced.

### 2a. LMS platforms

- Moodle web service tokens are user-tied. CVE-2011-4583 exposed tokens for disabled services and users who had lost authorisation; CVE-2016-7038 kept tokens valid after a password reset, and the stated remedy was manual per-user revocation, not scalable. A 2026 advisory (MOBILE-5071) shows a token leak via the mobile app reading stored sites' tokens. Lessons: tokens that outlive the thing that justified them are the recurring failure; ship revocation and expiry from day one; no user tie means no password-reset or staff-departure coupling, but also nobody's departure revokes the key, so `last_used_at` and expiry must do that job. Source: https://access.redhat.com/security/cve/CVE-2011-4583, https://vulert.com/vuln-db/CVE-2016-7038, https://moodle.org/security/index.php?lang=nl. I could not confirm how Moodle treats tokens of deleted or suspended users.
- Canvas rate-limits per access token (leaky bucket, 403 "Rate Limit Exceeded", `X-Rate-Limit-Remaining` header), and Instructure advises one token per application because concurrent calls on one token exhaust the bucket. Canvas also pushes OAuth for apps that act for many users, and some institutions restrict personal user tokens as a stability and security risk. Lessons: per-key throttling matches industry practice (idea already says so); consider one key per consuming script, and document that concurrent calls on one key share the budget; return rate-limit headers and use 429 with `Retry-After` (DRF does the latter), not Canvas's 403, since this spec uses 403 for scope refusal and the two must be distinguishable. Sources: https://community.canvaslms.com/t5/Canvas-Developers-Group/API-Rate-Limiting/bc-p/255856, https://tdx.umsystem.edu/TDClient/66/MOOnline/KB/ArticleDet?ID=2193. No sources found on what happens to a Canvas user token when its user is removed.
- Thinkific: 120 requests/minute per site and at most 10 in flight, 429 above. Teachable: pages conflict (100/min Admin API, 360/min OAuth API per school), 429 with limit, remaining and reset headers. Lessons: hosted LMS APIs throttle low, per site, so a reporting script is expected to be paced; cap page size and document a polite polling interval. No incremental-sync complaints surfaced for either. Sources: https://support.thinkific.dev/hc/en-us/articles/4422684774935-REST-API-Rate-Limits, https://docs.teachable.com/docs/rate-limits.
- Open edX, LearnDash: no usable findings from this search; not covered.

### 2b. Incremental sync with `updated_since`

- Missing rows come from (i) writes whose `updated_at` is set before commit, so a long transaction becomes visible after a client's checkpoint has moved past its timestamp (inferred; not directly sourced); (ii) clock skew or NTP steps moving timestamps backward; (iii) rows with a null cursor field; (iv) rows changed without touching `updated_at` (`QuerySet.update()`, `bulk_update`, signals that skip `auto_now`).
- Mitigations seen in docs: save the sync start time as the next checkpoint (not the end time) so a failed or slow run can be retried; re-read the boundary and dedupe by id (the idea's inclusive `updated_since` does this); page on a stable sort key so concurrent updates do not duplicate or lose rows; sequence cursors beat timestamps where clock issues matter. Sources: https://docs.askelephant.ai/bulk-exports, https://docs.getmatter.com/api/pagination, https://www.techinterview.org/post/3233468501/lld-cursor-based-sync/ (design sketch, not production-verified), https://www.mintlify.com/dlt-hub/dlt/api/sources/incremental.
- Bearing on this spec: document that clients should store the request start time minus a safety margin and dedupe by `id`; state that `updated_at` must reflect all user-visible changes (e.g. `last_login` is on User: does a login bump `updated_at`? If not, `updated_since` will miss `last_login` changes, a concrete hazard for the users resource); state the null-handling rule for the cursor field; and test that `(updated_at, id)` ordering across equal timestamps does not skip rows at page boundaries (DRF `CursorPagination` has had duplicate/skip bugs with non-unique ordering on the first field, which is why `id` is the tiebreak).

### 2c. Multi-tenant leaks through APIs

- The class of failure is broken object level authorisation: an endpoint trusts a value in the request (id, header) to pick the tenant. An OnSecurity pentest write-up found a single HTTP header exposed every customer's user data on a multi-tenant platform. Tenant isolation rests entirely on the authorisation code. Sources: https://onsecurity.io/article/pentest-files-how-a-single-http-header-unlocked-every-customers-data/, https://securityboulevard.com/2023/05/cross-tenant-data-leaks-ctdl-why-api-hackers-should-be-on-the-lookout.
- I found no sourced post-mortem of a leak that started with a leaked LMS API key.
- Bearing on this spec (local facts from `research_api_foundation.md` plus the above): the key's site binding must be the authority, not only the host. The idea's rule that the key's site must match the request host, and that unresolved sites are rejected, is right, because `SiteAwareManager` filters by host and fails open on `UnknownSite`. Add a test per resource: key for site A, host B, and a row on each site, with an assertion that no site-B row appears. The viewset queryset should filter by `key.site` explicitly (belt and braces), not only rely on the manager. Never read the tenant from a request header or query parameter.

### 2d. Credential hygiene (general practice, partly inferred)

- Show once, store only a hash, keep a visible non-secret prefix so admins can tell keys apart and so the lookup is indexed. Hash comparison should be constant time. Return identical 401s for unknown, expired and revoked keys. Use a recognisable prefix format so secret scanners can find leaked keys (GitHub secret scanning supports custom patterns; inferred, not searched).
- Moodle's record shows revoke-on-incident must be one admin action and effective immediately: do not cache key validity beyond seconds.
- `last_used_at` written on every request creates a write per read and row contention on a hot key; update it at most once per interval (e.g. a minute) (inferred).

## 3. Lessons to carry into the spec

1. No prior attempt to learn from; the ninja code never had auth. Say in the spec "no record of why ninja was dropped" and delete it. The corporate-readiness item 7 mentions ninja too, so update that gap text or leave a note that DRF replaces it.
2. Keep the key unattached to people (Moodle's coupling failures), but compensate with expiry, `last_used_at` and an admin list that shows stale keys.
3. Throttle per key, return 429 with `Retry-After`, keep 403 for missing scope; document one key per script and a polling interval. Decide whether `CACHES` is shared (no precedent in repo).
4. For `updated_since`, make `updated_at` honest for the users resource (check `last_login` and `email_verified` changes), document checkpoint-with-overlap, and test page-boundary behaviour with equal timestamps.
5. Test cross-site isolation as a first-class case, with explicit `site` filtering in the queryset.
6. Personal data: data minimisation as in the done export specs; document in `docs/product/security-and-data-handling.md` that consumers own downstream erasure, since deletions are invisible.
7. Hash choice: fast hash with prefix lookup is enough for random keys; avoid Argon2 per request.

## References

- https://access.redhat.com/security/cve/CVE-2011-4583
- https://vulert.com/vuln-db/CVE-2016-7038
- https://moodle.org/security/index.php?lang=nl
- https://community.canvaslms.com/t5/Canvas-Developers-Group/API-Rate-Limiting/bc-p/255856
- https://tdx.umsystem.edu/TDClient/66/MOOnline/KB/ArticleDet?ID=2193
- https://support.thinkific.dev/hc/en-us/articles/4422684774935-REST-API-Rate-Limits
- https://docs.teachable.com/docs/rate-limits
- https://docs.askelephant.ai/bulk-exports
- https://docs.getmatter.com/api/pagination
- https://www.techinterview.org/post/3233468501/lld-cursor-based-sync/
- https://www.mintlify.com/dlt-hub/dlt/api/sources/incremental
- https://onsecurity.io/article/pentest-files-how-a-single-http-header-unlocked-every-customers-data/
- https://securityboulevard.com/2023/05/cross-tenant-data-leaks-ctdl-why-api-hackers-should-be-on-the-lookout

status: ok
