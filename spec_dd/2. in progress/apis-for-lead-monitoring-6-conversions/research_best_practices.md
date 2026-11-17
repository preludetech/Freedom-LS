# Research: best practices for a read-only, cursor-paginated feed of touches and conversions

Scope: what would change or confirm the spec. References are the well-known public docs, cited from
background knowledge (not re-fetched in this run).

## 1. Paging key: write time vs event time

- Incremental-sync feeds must page on a monotonic, server-assigned key. Event time is client-influenced and arrives late, so a watermark on it silently skips rows. This is the standard reasoning behind "high-water mark on ingestion time" in ETL/CDC practice, and APIs such as Stripe (`created` + `starting_after` object id), Shopify (`since_id`, `updated_at_min`) and Segment/Snowplow (collector/ingest timestamp vs device timestamp) expose both times but sync on the server one.
  - https://docs.stripe.com/api/pagination
  - https://shopify.dev/docs/api/usage/pagination-rest
- **Confirms the idea**: paging on `(recorded_at, id)`, returning `occurred_at` as data only, is the established design.
- **Caveat that should shape the spec**: `recorded_at` is only a safe watermark if it is assigned at commit-visible order. With `default=now` set in application code, a long transaction can commit a row with an earlier `recorded_at` after a reader has already passed that time (the "in-flight transaction" gap). Mitigations the spec should pick from:
  1. Document that scripts should re-read with an overlap window (e.g. start from `last_recorded_at - a few minutes`) and de-duplicate by `id`. Cheapest, and works because `updated_since` is inclusive and ids are stable.
  2. Or have the spec state the guarantee honestly: "no row is missed provided rows are written in short transactions; use an overlap for safety".
  Either way, say so in the docs page and OpenAPI description; do not promise "misses nothing" unqualified.
- Flush paths (`signup_flush`, `login_flush`) write many rows in one transaction with possibly one `recorded_at` each or a shared one. The cursor tiebreak on `id` must be total-order stable: a UUID primary key is unique but not insertion-ordered, which is fine for tiebreaking as long as the ordering is `(recorded_at, id)` consistently in both the filter predicate and the `ORDER BY`. A shared `recorded_at` across a batch must not straddle a page boundary lossily: use a keyset predicate `(recorded_at, id) > (cursor_at, cursor_id)`, not offset and not `recorded_at >` alone.
- Inclusive `updated_since` plus a cursor: the first request uses the inclusive filter; later pages use the opaque cursor, which encodes `(recorded_at, id)`. A script that restarts from its stored `recorded_at` re-receives rows at that exact instant, so docs must say "de-duplicate by id".

## 2. Cursor mechanics

- Use opaque, signed-or-encoded cursors over keyset, not offset or page numbers (stable under inserts, constant cost). DRF `CursorPagination` does this but its `ordering` is a single-field default tuple; ordering `("recorded_at", "id")` is supported as a tuple, but DRF's cursor encodes only the first field's position plus an offset, which is **not** a true composite keyset and degrades when many rows share one `recorded_at` (the flush batches case). The spec should require a true composite `(recorded_at, id)` keyset (custom pagination class) or test the shared-timestamp batch explicitly.
  - https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
  - https://slack.engineering/evolving-api-pagination-at-slack/
- Needs an index on `(recorded_at, id)` (and site) for each model; otherwise deep pagination sorts. Per-site filtering means the index should lead with site where the site FK exists, or the query planner should be checked in the spec's tests.
- Capped page size, with a documented default and maximum; reject over-limit rather than silently clamping is acceptable either way, but the choice should be written down (the idea says "capped").
- Ascending order only for sync feeds. A "newest first" option is a different use case; omit it (matches "don't build what's not requested").
- Do not return a total count (a `COUNT(*)` on a growing table is costly and unstable under append). Provide `next` only.

## 3. Late-arriving events

- Treat lateness as a property of the data, not a paging concern: return both times, document that `occurred_at` can be older than rows already read, and tell consumers to order the timeline client-side. This matches the Snowplow/Segment/analytics convention (event time for analysis, ingest time for transport).
  - https://docs.snowplow.io/docs/understanding-your-pipeline/canonical-event/ (collector vs device timestamps)
- `recorded_via` is a good signal; the spec should state what each value means for trust (live = near real time; flush = recorded at signup/login, possibly long after `occurred_at`).
- Conversion `first_touch`/`last_touch` ids may reference touches recorded in a **later** page or an earlier one than the conversion itself. Because touches are flushed before the conversion is resolved this is usually earlier, but the spec should say a script must not assume a referenced touch has already been read, and should join after syncing both lists (or tolerate a missing id). This also bears on the open question "flat lists vs embedding": flat lists with ids are fine **if** the join contract is documented; embedding would duplicate rows and break the append-only paging semantics, so keep flat.

## 4. Filter design

- Keep filters to equality on indexed columns plus the one time bound. Established APIs avoid free-form query languages for sync endpoints.
- The answer already given (`referral_code` matching first OR last, plus exact `first_referral_code` and `last_referral_code`) is consistent with the admin. Spec points:
  - Name `referral_code` consistently across both resources; on touches it is the touch's own code, on conversions it is the either-match. State this difference in the OpenAPI description, because the same parameter name has two meanings.
  - Either-match is an `OR` over two columns and cannot use a single plain index; for a large table consider whether both columns are indexed (two indexes, planner uses BitmapOr) or accept the cost. Flag it in the spec as a performance note, not a blocker.
  - Case sensitivity and blank: define whether the code match is exact/case-insensitive following how child 3 treats codes; and whether an empty value (`first_referral_code=`) means "no filter" or "nothing in play". Recommend: empty means no filter; do not add a "has no code" filter unless requested.
  - Unknown or malformed filter values (bad UUID for user, unknown `kind`) return 400 with a clear message, not an empty list; an empty list for a valid but unmatched value.
  - `kind` should validate against the enumerated values and list them in the OpenAPI schema (choices).
- Date-range filters beyond `updated_since`: an `updated_until`/`recorded_before` upper bound is useful for backfills but not needed for incremental sync; recommend not offering it unless child 1 does (consistency with the effort, and "don't build what's not requested"). Filtering on `occurred_at` stays excluded as already settled.
- Combine filters with AND; document that `updated_since` combined with filters still pages on `(recorded_at, id)`.
- Use `django-filter` or explicit validated query serializer rather than ad hoc `request.GET`, so errors and schema come out uniformly (follow whatever child 1 uses).

## 5. Privacy of tracking data

- Data minimisation: explicit allow-list serializers (already settled). Add a test that asserts the exact field set of each resource, so a future model field cannot leak by default. This is the single most valuable guard and is cheap.
- Treat the referral code, UTM values and `landing_path` as personal data in combination with a user id: they reveal browsing and acquisition history of an identified person. Under GDPR/POPIA this is still personal data even without IP or cookie id. Practical consequences for the spec:
  - Scope-gate (done), site-isolate (done), throttle (done), and state purpose and retention in `docs/product/security-and-data-handling.md`.
  - `landing_path` can contain query strings or path segments with tokens (e.g. password-reset or invite tokens, email addresses in query params) if the recorder stores more than the path. Verify what the recorder stores; if query strings are possible, the spec should require stripping them at read time or confirm they are never stored. Name this as a risk to check, since "landing_path" is the likeliest accidental leak.
  - UTM free-text fields are attacker-controllable (anyone can craft a link). Return them as plain JSON strings, never rendered as HTML by the docs example; note that consumers must treat them as untrusted input (CSV/formula injection when scripts write them to spreadsheets).
  - `target_label` holds an account email for `account_signup`: that is personal data, and it stays after the user changes email or is deleted. Decide whether returning it duplicates what child 3 returns for the user (open question 2), and whether a deleted user's conversions remain readable (the idea says yes, via the frozen label). Flag the retention/erasure implication: the label is the one place that outlives an account deletion; the spec should record that this is deliberate or that erasure requests need handling elsewhere. The API itself has no deletion feed (out of scope), so a script that cached a row will never learn of an erasure; document that.
  - Return the user as id only unless child 3 returns email; mirror child 3 exactly to avoid one endpoint becoming a wider leak than the other.
- Audit: log key id and path for access to personal-data scopes only if the project already does so for child 3 (the repo rule is "no logging unless asked"; do not add it here).
- Responses carrying personal data should send `Cache-Control: no-store` (or `private`), so shared proxies do not retain them. Check whether child 1 sets this; if not, it is a spec-level addition.
  - https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
  - https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/ (excessive data exposure: explicit field lists)

## 6. Behaviour when the source models are absent or empty

- Empty list with 200 is the expected, conventional answer for "feature present, no rows". If `referral-attribution-over-time` is not installed, the models do not exist, so the view cannot query. Options: (a) the routes are not registered and return 404; (b) routes registered and return empty 200. Prefer (a) only if the effort already handles optional apps that way; otherwise (b) gives scripts a stable contract and an OpenAPI schema that does not vary by install. Because the idea says FLS is designed to be installed into other projects, and these models ship in an FLS app, the realistic case is "installed, no rows", so empty 200 is right. Spec should confirm which app the models live in and that a migration dependency makes "not installed" impossible; if so, drop the question.

## 7. Other points that would change the spec

- Idempotent, deterministic reads: GET only, `HEAD` and `OPTIONS` allowed (settled); return `405` with `Allow` header for others.
- Page response shape: `{next, previous?, results}`; for sync feeds `previous` is unnecessary. Follow child 1's envelope rather than deviating.
- Append-only guarantee should be enforced or at least asserted: if the models can be updated or deleted by the admin or the prune command (out of scope but present in the sibling spec), the "written since == new or changed since" claim breaks for deletions. State explicitly that deletions (prune) are invisible to the feed, and that scripts should treat the feed as additive. If any code path can `update()` a touch or conversion row (for example, backfills), `recorded_at` would not advance and scripts would miss the change; spec should state that such changes are not supported or must be done by inserting a new row.
- Time precision: store and serialise `recorded_at` with microseconds and timezone (ISO 8601 with offset), and have the `updated_since` parser accept the same format. Truncating to seconds in the output while filtering at microsecond precision produces duplicates or gaps at the boundary.
- Throttle numbers and page size caps should be tested with a dataset larger than one page where several rows share an identical `recorded_at` (flush case): the single most likely bug source for this endpoint.

## Summary of spec-changing recommendations

1. Qualify the "misses nothing" claim; recommend an overlap window and de-dup by id in the docs.
2. Require a true composite `(recorded_at, id)` keyset pagination, tested with many rows sharing one `recorded_at`; do not rely on DRF's default `CursorPagination` offset behaviour.
3. Index `(recorded_at, id)` (site-leading if applicable) on both models.
4. Document that touch ids referenced by a conversion may not yet have been read; flat lists stay.
5. Document `referral_code` semantics difference between touches and conversions; 400 on invalid filter values; no date-range filters beyond `updated_since`.
6. Add a field-allow-list test per resource; check `landing_path` never holds query strings or tokens; document `target_label` email retention and no erasure feed.
7. `Cache-Control: no-store` on responses (if child 1 does not already).
8. Settle the "not installed" question as empty 200 or drop it if the models always ship with the app.
9. Document that deletions and in-place edits are invisible to the feed.

status: ok · reason: complete
