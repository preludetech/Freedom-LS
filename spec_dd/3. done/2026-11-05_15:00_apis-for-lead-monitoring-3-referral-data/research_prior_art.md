# Research: prior art for the referral data API endpoints

Question: what has already been tried for this, here or elsewhere, and what happened?

Limit: no shell, so no `git log`. Done-spec artefacts and code stand in for history. Commit ids quoted are the ones the QA reports cite.

## 1. Here

### 1a. No earlier referral API exists

Referral data has only ever been read through the four admin CSV exports (`referral_tracking/resources.py`). The API effort's only shipped piece is spec 1 (done 2026-11-03). Specs 2, 4 and 5 are in progress as ideas only (their `todo.md` is all unticked, no spec yet), so they hold no lessons yet, only the conventions they share with this spec.

### 1b. Decisions already taken that bind this spec

From `referral-links` (done 2026-09-12):
- Hits hold no personal data by design. A hit is `door`, `is_machine_fetch`, `hit_at`. Machine-fetch verdict is kept, the UA is not.
- `hit_count`/`last_hit_at` exclude machine fetches, but the log keeps every hit. `hit_count` never goes down. Pruning (`prune_referral_code_hits`, run by the operator, across every site) empties the log and leaves the counters. So `hit_count` and the hit log do not reconcile by design. The spec's help text says `hit_count` is an upper bound on human use, not a scan count.
- Codes are never deleted (admin refuses delete, direct GET of delete URL is 403). Deactivation is `is_active`.
- `ReferralCodeHit.hit_at` is `auto_now_add`, indexed `(site, hit_at)`; `SignupAttribution.signed_up_at` is `auto_now_add`, indexed `(site, signed_up_at)`. Both timestamps are taken in Python at write time. The hit write happens inside `transaction.atomic()` (`hits.py:120`), so the timestamp precedes the commit (see section 2).
- `ref` alone is tracked as free text with no `ReferralCode` lookup (QA 6.2), so `SignupAttribution.referral_code` and `FirstTouchCount.referral_code` can hold text that matches no `ReferralCode` row. The API must not assume a join. This is why the hit exposes the code's id and text, but the attribution exposes `referral_code` as plain text.
- The upgrade day splits `FirstTouchCount` rows: `key_hash` is over `ATTRIBUTION_KEY_FIELDS`, which gained `referral_code`, so one campaign can appear on two rows for the same day. Counts are comparative; no rehash. A consumer summing by campaign key must group by the key fields, not assume one row per key per day.
- Rolling back after the referral-links upgrade discards live attribution cookies. Not API relevant, but it shows `first_seen` on attributions can be older than the data in the tally.
- The code `api` is reserved, so `/api/` cannot collide with a referral code.

From `more_lead_admin_exports` (done 2026-10-29):
- Referral exports are gated by view permission only, with no export permission. The API replaces that with a per-key `referral_data` scope.
- Data minimisation rule (`research_best_practices.md`): export only the columns needed, never tokens or IP addresses. The Users export honours it. The referral exports predate the rule and still carry `client_ip`, `user_agent` and cookie ids on the attribution export. That is the gap this spec's omission closes for the API (the admin export stays unchanged by decision).
- The CSV-only concerns (BOM, formula escaping) are not carried into JSON. The roadmap hazard list says the same.
- Bug found in QA (B1): a late fix-up commit (73dfcc590) moved `SpreadsheetBooleanWidget` into the shared `SiteAwareModelResource`, so `ReferralCode` `is_active` now exports `TRUE`/`FALSE` and not `1`/`0`, against the spec, plan and QA plan. Resolved by decision: keep TRUE/FALSE everywhere and update the docs. Lesson: a shared-base change reaches resources the spec said were untouched, and the upgrade notes missed it. For the API: serialise booleans as JSON `true`/`false` and do not inherit export widgets. The idea's phrase "same names as the export" means column names only.
- The export test file `referral_tracking/tests/test_resources.py` is what pins export columns. A test that the API field list equals the export columns minus `site` (plus the explicit additions and omissions) would catch drift the same way.

From `referral-links` QA:
- B1 (fixed in e7682f4): the `ReferralCode` change form 500ed with `NoReverseMatch` for a stored code that no longer matches `CODE_PATTERN` (e.g. `has_underscore`, created past validation). Lesson for the API: stored codes can predate current rules. A serializer must not compute a `/go/` URL by reversing. Return `code` as stored, and do not add a `go_url` field (the idea does not ask for one; adding it would reintroduce this 500).
- Hit counting is cache-throttled per IP (`REFERRAL_TRACKING_HIT_LOG_LIMIT`, default 30 per hour, in Django's default cache) and Playwright's headless UA is flagged `is_machine_fetch`. Test data for hits must set `is_machine_fetch` and `hit_at` explicitly, and tests that exercise the real hit path must clear the cache with the tables.
- Per-code exact-count assertions were fragile because any probe request inflates counters. API tests should build rows through factories, not through `/go/`.

From spec 1 (done 2026-11-03), QA and lessons:
- Convention set: each endpoint lives in `<app>/api.py`, registers with `freedom_ls.api` router; viewset base `ReadOnlyApiViewSet` with `required_scope`; `site_queryset()` filters on `request.auth.site` (never the host-filtered manager); explicit field lists; envelope `{"next", "results"}`; keyset pagination on `("updated_at", "id")`, opaque cursor, `page_size` clamped (default 100, max 500); `UpdatedSinceFilterSet` filters `updated_at__gte`, ISO 8601 with a timezone, naive/unparseable is 400 naming the parameter; JSON errors `{"detail","code"}`; `Cache-Control: private, no-store`; OPTIONS returns only the view name; throttle 600/min per key, 429 with `Retry-After`.
- Spec 1's pagination and filter are hard-wired to `updated_at`. Spec 3 needs the same machinery on `hit_at`, `signed_up_at`, `day` and `created_at`. This is the biggest spec-3 work: either generalise `ApiKeysetPagination` and the filter (take the ordering field name as a class attribute) or subclass them. Spec 1's own pagination test (1,500 users with one identical timestamp) is the pattern to repeat for hits and first-touch counts, where many rows share a timestamp or a date. For first-touch counts the cursor field is a `DateField`, so the cursor encoding and `__gte` parsing for a date are new code. The idea leaves the parameter spelling open.
- The viewset's schema pass: during schema generation `site_queryset()` returns `none()`. Run `manage.py spectacular --validate --fail-on-warn` for the new endpoints, since spec 1 made it a test.
- `freedom_ls_api.E001` fails any registered viewset without `required_scope`. All four need `ApiScope.REFERRAL_DATA`. The scope's description in `scopes.py` lists `ReferralCode`, `ReferralCodeHit`, `SignupAttribution` only; `FirstTouchCount` is missing from that description, so spec 3 needs to add it (stored value unchanged).
- Spec 1 QA: 3 bugs, all admin/UI (key overflow on mobile, scope labels clipped, allauth Email admin not site-scoped). No API behaviour bugs, and the 2.x API checks all passed on the first run. B3 is the transferable one: a third-party admin lists other sites' rows. Spec 3 adds no admin, but the same check applies to any referral admin changes (none planned).
- `accounts → api` created an import loop that was approved. Spec 3 adds `referral_tracking → api` and `referral_tracking → accounts` (the user email on an attribution, already a model FK). Check the import contracts and `docs/app_structure.md` (`/ds:app_map`), since `referral_tracking` is one of the "small apps" the test-organisation work is touching (`test-organisation-and-hygene-6-small-apps`, status next).
- The users endpoint made `User.updated_at` honest by adding a signal on `EmailAddress`. For referral data, the equivalent honesty problem is the opposite: no timestamp exists, and the idea chooses to document it, not to fix it.
- Spec 1 docs say: checkpoint at max timestamp seen minus 5 minutes, advance only after a full run, upsert by `id`, deletions only by periodic full pull. Spec 3 can copy this for hits and attributions, and must tell consumers a different rule for first-touch counts (re-pull recent days) and for codes (full pull).
- The Sentry/Authorization scrub, `last_used_at`, and the shared-cache W001 warning are already done in spec 1 and need nothing here.

From the roadmap and the standalone `referral-attribution-over-time`:
- Conversions and touches go in spec 6 under the same scope, ordered on `recorded_at` not `occurred_at` (flushed touches happen before they are written). This is an existing statement of the same late-write hazard in section 2 and a hint to the author: write rows to the cursor field's order of commit, not event time.
- `SignupAttribution` is unchanged by attribution-over-time, so spec 3's attribution resource stays stable. `referral-tracking-external-referer-first-touch` will add attribution rows with only a `referer`, no new fields. Marketing-channel and referer-host fields are derived and out of scope for spec 3.
- The attribution-over-time spec keeps `referral_tracking` outside the timestamped mixin on purpose (`1. spec.md:142-144`). The idea honours that.

### 1c. Not found

No performance measurements, no load tests, no record of hit-log volume at a real site, and no privacy review of the hit table beyond "no personal data" were found. The hit log is unbounded unless the operator schedules the prune (upgrade notes step 5). A hits endpoint is therefore the one that can grow without limit. Nothing records the largest `ReferralCodeHit` table seen. Spec 3 should treat that as unknown and rely on the keyset index `(site, hit_at)` plus the page cap, and check that `(site, hit_at, id)` is what the query orders on (the existing index lacks `id`; spec 1 added a `(site, updated_at, id)` index on `User` for the same reason). The same question applies to `(site, signed_up_at)` and `FirstTouchCount` `(site, day)`.

## 2. Elsewhere

### 2a. Timestamp cursors over mutable or late-committing data

Failures reported in practice (forum posts and vendor docs, not authoritative post-mortems):
- Commit order differs from ordering key order. A row stamped at time T can commit after a reader has already checkpointed past T, so the reader never sees it. This is the textbook race for timestamp or sequence cursors. See the Postgres mailing-list thread on tracking row updates: https://postgrespro.com/list/id/42391D10.7090908@alexandcarmen.com and the write-up of a cursor race in an offline-first app: https://hackernoon.com/how-a-cursor-race-silently-broke-my-offline-first-app (whose fix is a full re-read).
- Occasional missed rows with a timestamp bookmark while another transaction was open: https://discuss.meltano.com/t/16422771/hi-i-ve-been-seeing-occasional-rows-missed-when-doing-an-inc
- Equal timestamps and inclusive cursors: Airbyte's cursor is read back inclusively, so the last record is re-read to avoid losing rows with the same timestamp, which yields duplicates that the destination must dedupe: https://discuss.airbyte.io/t/incremental-syncing-issues-on-several-connectors/504 and https://discuss.airbyte.io/t/duplicate-rows-issue-with-airbyte-sync/6078.
- Mutated rows whose cursor field does not move are not picked up by incremental syncs: https://docs.squared.ai/guides/data-modelling/sync-modes/cursor-incremental. This is the `FirstTouchCount.count` and `ReferralCode.hit_count` case exactly.
- Mitigations seen: an overlap window on the checkpoint, dedupe by primary key, a stable tie-break (`id`), and a periodic full re-read.

Bearing on this spec:
- `hit_at` and `signed_up_at` are `auto_now_add`, stamped in Python before the enclosing transaction commits (hits are written inside `transaction.atomic()`). A slow commit can land after a script has checkpointed past it. Spec 1's "checkpoint at max seen minus 5 minutes" rule is the right mitigation; the margin applies equally to hits and attributions, and the docs should say it explicitly, since "append-only" does not mean "visible in timestamp order". The idea's claim "ordering on their timestamp is a reliable checkpoint" is true only with that margin.
- The inclusive `>=` filter, together with `(timestamp, id)` ordering, handles equal timestamps. Test it with many rows sharing one timestamp (hits created in a burst by one test, or a single `day` with hundreds of first-touch rows).
- First-touch counts: ordering on `day` with `id` as the tie-break is stable for paging, but `count` changes in place under a reader mid-run, and a row can appear on a day already passed. The documented "re-pull recent days" rule is the standard answer; say how many days (at least the cookie max age does not apply, since the tally is per landing day; use "today and the previous day at least", and later days if the server's timezone differs from the script's).
- `day` is a date in the server's timezone (check `USE_TZ` and which "today" the tally uses). A script in another timezone can mis-slice days. Spell this out in the docs.
- Pruned hits and a `hit_count` that outruns the log are documented, not corrected, so a script that totals hits from the log and compares to `hit_count` will see a mismatch. Say which one is the figure for payouts (neither is: `hit_count` skips machine fetches and the log includes them).

### 2b. Exposing referral data: fraud and personal data

- Affiliate click and referral counts are a known fraud target: bots and click farms inflate click counts, and cookie stuffing sets a tracking cookie with no real click. Signals used to catch it are a blank referrer, a cookie with no click, and no real session behind a referral. Sources: https://growsurf.com/glossary/affiliate-fraud/, https://www.brandverity.com/blog/compliance-part-two-forced-clicks-cookie-stuffing, https://weltpixel.com/blogs/news/how-to-detect-affiliate-cookie-stuffing-on-your-shopify-store, https://www.makeinfluence.com/en/academy/click-fraud-and-cookie-stuffing-in-affiliate-and-influencer-tracking. Bearing on this spec: the API publishes raw, unvalidated counts, and `ref` is free text. The idea already says referral data feeds payouts. Keep `is_machine_fetch` and `is_overflow` visible so a consumer can discount them, say plainly in the docs that counts are not fraud-checked, and do not hide the flags. The hit throttle (30 per IP per hour) shapes the numbers too; the consumer cannot see the throttled hits at all.
- `is_overflow` rows on `FirstTouchCount` are a bucket for keys past a cap. Exposing them keeps totals honest; dropping them would understate the denominator. (Their `key_hash` then is not a unique campaign key.)
- Personal data in referral APIs: the search found no sourced incident. The general rule is OWASP API3:2023 (excessive data exposure and object property level authorisation): return only the properties a client needs, because a scope that covers a whole object hands every property to every holder. https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/ (cited from knowledge, not fetched). This matches the owner's decision to omit `client_ip`, `user_agent` and cookie ids (identifiers that single out a person and the device) from the attribution resource.
- Remaining personal data after the omission, which the idea does not discuss: the attribution carries `user` id and email, `landing_path`, `referer` and `raw_query`. `raw_query` is the visitor's full query string and `referer` a full URL; either can carry a token, an email address or a click id (`gclid`, `fbclid` are already fields). These are free text under the visitor's control, so they can hold anything. Consider whether `raw_query`/`referer`/`landing_path` belong under the same minimisation reasoning, or note that the admin export carries them already and the omission list was a deliberate owner choice.
- The attribution carries the user's email, and a user erased from the site disappears from pulls with no signal (deleted attributions cascade with the user, QA 9.user-delete). Spec 1's rule (consumer owns downstream erasure) applies; the security doc should say so for attributions.

## 3. Lessons for the spec

1. Reuse spec 1's machinery and make it timestamp-field-agnostic. Hits, attributions and first-touch counts need the pagination and the changed-since filter on a field other than `updated_at`. Decide in the spec whether the shared classes are generalised or subclassed, since specs 2, 4, 5 and 6 may need the same (`created_at`, `registered_at`). Coordinate with those specs to avoid merge conflicts in the pagination and filter files.
2. Date cursor on `day` is new. Test cursor round trip, inclusive filter at the boundary, bad values (400 naming the parameter) and many rows on one day.
3. State the checkpoint margin (5 minutes) for hits and attributions explicitly, because their timestamps are taken before commit.
4. For first-touch counts, document the re-pull window in days and the timezone of `day`; for codes, document the full pull and that `hit_count`, `label`, `is_active` can change.
5. Do not compute URLs from stored code text (the `NoReverseMatch` 500 from referral-links QA B1). No `go_url` field.
6. Do not inherit export widgets or the CSV resource classes. API booleans are JSON booleans; the shared export base changed `is_active` rendering late in `more_lead_admin_exports` and surprised the spec.
7. Assert the exact field lists in tests (and that no `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie` key appears), plus site isolation with a row on a second site for each of the four resources, plus query counts (hit and attribution serialisers read `referral_code.code` and `user.email`, so `select_related` is needed; pin it with `django_assert_num_queries`).
8. Hits can grow without limit if the prune is not scheduled. Confirm the keyset index covers `(site, hit_at, id)`, and that the page cap bounds a request. Index changes need a migration, which spec 3 otherwise does not need.
9. Add `FirstTouchCount` to the `referral_data` scope description in `scopes.py`; the shipped text omits it.
10. Docs must say counts are not fraud-checked, name the flags (`is_machine_fetch`, `is_overflow`), and explain that `hit_count`, the hit log and the tally do not reconcile. Update `docs/product/security-and-data-handling.md` (fields returned, fields withheld, and erasure being the consumer's job for attributions).
11. Upgrade notes: any new migration or `INSTALLED_APPS` change is spec 1's. If spec 3 adds an index, it needs a migration note. If it adds no migration it may still need to note the `referral_tracking → api` edge, which concrete projects that do not install the API apps must survive (spec 1: opt-in, `autodiscover_modules("api")`).

## References

- https://postgrespro.com/list/id/42391D10.7090908@alexandcarmen.com
- https://hackernoon.com/how-a-cursor-race-silently-broke-my-offline-first-app
- https://discuss.meltano.com/t/16422771/hi-i-ve-been-seeing-occasional-rows-missed-when-doing-an-inc
- https://discuss.airbyte.io/t/incremental-syncing-issues-on-several-connectors/504
- https://discuss.airbyte.io/t/duplicate-rows-issue-with-airbyte-sync/6078
- https://docs.squared.ai/guides/data-modelling/sync-modes/cursor-incremental
- https://growsurf.com/glossary/affiliate-fraud/
- https://www.brandverity.com/blog/compliance-part-two-forced-clicks-cookie-stuffing
- https://weltpixel.com/blogs/news/how-to-detect-affiliate-cookie-stuffing-on-your-shopify-store
- https://www.makeinfluence.com/en/academy/click-fraud-and-cookie-stuffing-in-affiliate-and-influencer-tracking
- https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/ (not fetched)

status: ok
