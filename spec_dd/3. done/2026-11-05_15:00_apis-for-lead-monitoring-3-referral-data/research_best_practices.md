# Research: best practices for a read-only referral-data sync API

Builds on `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md` (auth, cursor envelope, `/api/v1/` naming already settled). Source note: items marked (fetched) were read this run; items marked (knowledge) are from memory of the cited doc and should be verified before a spec quotes them.

## 1. Incremental sync: append-only logs vs in-place aggregates

**Append-only logs (hits on `hit_at`, signup attributions on `signed_up_at`)**
- Checkpoint on the last `(timestamp, id)` seen, not on the timestamp alone. Ask again with an inclusive `>=` bound on the timestamp. Inclusive is the safe choice: rows sharing the boundary timestamp are returned again, and the consumer dedupes on `id` (upsert by primary key). Exclusive `>` silently loses rows that share the checkpoint timestamp or that commit just after a row with a later timestamp. State this in the docs: "bounds are inclusive; expect the last row(s) of the previous page again; upsert by id."
- Residual risk of a timestamp checkpoint on a log: a row stamped earlier than the checkpoint but committed later (long transaction, clock skew, `hit_at` set by app code rather than DB). For hits written by a request handler this window is seconds. Best practice is a small overlap: the client re-asks from `checkpoint - a few minutes` and dedupes by id. Document it as a recommendation; it costs nothing because upsert is idempotent. (Knowledge: standard "overlap/lookback" pattern.)
- Stripe is the model: `created[gte]`-style range filters plus cursor lists, objects immutable once created, so no separate "modified" signal is needed. https://docs.stripe.com/api/pagination (knowledge)
- Deletions (pruned hits) are invisible to any since-filter. Say so in the docs. Pruned hits are only a problem for a consumer that treats the API as the system of record; consumers should store what they have pulled and never expect old hits to be re-served.

**Cursor pagination stability**
- DRF `CursorPagination` wants an ordering field that is unchanging, unique or nearly unique, non-null, indexed, not a float; non-unique fields "will generally still work" but can give missing or duplicate records. It copes with ties best when a unique tie-break is part of the ordering, so use `ordering = ("hit_at", "id")` (and `("signed_up_at", "id")`, `("day", "id")`, `("created_at", "id")`). (fetched) https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- Practical consequences for the spec: `signed_up_at` and `hit_at` must be non-null and indexed (check `ReferralCodeHit.hit_at`, `SignupAttribution.signed_up_at`; add an index in a migration if absent). `day` is hugely non-unique (many rows per day), so the `id` tie-break matters most there. Note DRF's cursor encodes an offset within runs of equal values, so a page boundary inside a large tie group is the weak spot; UUID `id` ordering is stable but arbitrary, which is fine for tie-breaking.
- Ordering and filtering on the same field (as the idea settles) means the filtered result is a contiguous suffix of the ordering, so cursor paging through a filtered set is consistent.
- Cap `page_size` and keep the default modest; return `next` only, as DRF cursor does.

**Date vs datetime filter parameters**
- For a `DateField` (`FirstTouchCount.day`) use a date-typed filter (`YYYY-MM-DD`, django-filter `DateFilter`/`lookup_expr="gte"`), and reject datetimes with a 400 rather than truncating silently. The datetime resources take ISO 8601 datetimes with offset. Whether the same query-param name is reused is a spec decision; the principle is the name should say what it filters. Options: keep one name (e.g. `since`) with type depending on resource and document it per resource, or use `day_gte` / `day_lte` for the date resource and a datetime name for the others. A single name with differing types is the less discoverable choice; explicit `day_from`/`day_to`-style names avoid a reader assuming a datetime. Google Analytics Data API uses `startDate`/`endDate` as inclusive date ranges, a precedent for inclusive date bounds. https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/DateRange (knowledge)
- Naive datetime input should be rejected or interpreted as UTC and documented; do not guess the server timezone.

**Timezone for date buckets**
- A `day` is a bucket in some timezone, and the API must say which one. Find which timezone `FirstTouchCount.day` is computed in (likely `timezone.localdate()` under `TIME_ZONE`, or UTC) and state it in the docs and schema description. Do not convert it; consumers joining hits (UTC datetimes) to day counts will otherwise disagree around midnight. Ship the timezone name in the docs, not per row. GA4 does the same: reports are in the property's configured timezone, stated in docs. https://support.google.com/analytics/answer/9333790 (knowledge)

**In-place-mutated daily aggregates (`FirstTouchCount`)**
- With no `updated_at`, no honest "changed since" exists. Standard answer is a lookback/trailing re-pull: each run re-reads the last N days and upserts by `id` (or by natural key `(day, key_hash)`). Size N to how long counts can still change; a dbt-style write-up says match the window to the data-arrival SLA (48 h late data -> 2-3 day lookback) and warns records arriving after the window closes are missed. (fetched via search) https://adriennevermorel-astro.pages.dev/notes/late-arriving-data-lookback-window-pattern/ ; a daily-sync doc suggests re-reading about the last 7 days. https://docs.hologrow.ai/marrow-data/data-fetch-periods
- For this API: counts rise through the current day and are only written at first-touch time, so past days should be final except for a late signup or overflow row. Recommend: re-pull from `today - 2` (documented default; consumer's choice), always including today and yesterday, and treat today's row as provisional. Full history can be re-pulled at will since the table is one row per day x key.
- Use the checkpoint on `day` inclusive, so re-pulling a day is just asking `>=` that day; rows are idempotent upserts. Same as the Fivetran/Airbyte "fixed overlap on each sync" approach. https://support.fivetran.com/hc/en-us/community/posts/38277616619927-Connector-Improvement-Incremental-Update-Sync-Handling (fetched via search)
- `is_overflow` rows and `key_hash`: expose both as-is and document that overflow rows lump keys that exceeded the cap, so per-campaign sums are lower bounds when overflow is present. Document `key_hash` as an opaque stable bucket id, safe as a natural-key component with `day`.

## 2. Full pull of small mutable tables (`ReferralCode`)

- For a small reference table that mutates in place, the normal pattern is no filter, deterministic order, re-read everything and replace/upsert. HubSpot's and Stripe's list endpoints for small objects (products, prices) behave this way, with `limit` + cursor. Deterministic ordering `(created_at, id)` makes paging stable even while rows change, because ordering fields are immutable (matches DRF's "unchanging" requirement; `hit_count` / `label` would be bad ordering fields).
- Tell consumers to replace-then-upsert by `id` each run, and to treat a referral code that disappears from the full pull as not expected (codes are never deleted).
- Filters: a lone `is_active` filter is cheap, harmless and consistent with django-filter use elsewhere, but since a full pull is the contract and the table is small, adding it is functionality nobody asked for (project rule: don't build unrequested functionality). Lean none unless the spec has a consumer for it.
- Expose `hit_count` and `last_hit_at` as "counter values as of the read", not as a derived total; see section 5.

## 3. Privacy and data minimisation

**Principle**: only expose what the purpose needs (GDPR Art. 5(1)(c) data minimisation; POPIA condition 3 / s.10 "minimality"). A key scoped to "where did leads come from" does not need device fingerprints. Withholding `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie` is consistent with that, and keeping them behind the admin `view_` permission is a sound separation (field-level gating by privilege is also how Moodle's `viewuseridentity` and Stripe restricted keys work, per the earlier research).
- GDPR Art. 4(1) defines personal data including an "online identifier"; Recital 30 names IP addresses, cookie identifiers and "other identifiers such as radio frequency identification tags" as online identifiers that, combined with unique identifiers and other server-received information, may leave traces used to profile and identify people. https://eur-lex.europa.eu/eli/reg/2016/679/oj (Recital 30; knowledge). CJEU Breyer (C-582/14) held that a dynamic IP is personal data for a site operator when the operator has legal means to identify the person via others' data. https://curia.europa.eu/juris/liste.jsf?num=C-582/14 (knowledge)
- POPIA s.1 defines "personal information" to include information relating to an identifiable person, with "online identifier" and "e-mail address" in the enumerated examples, so the same reading applies to IP, cookie ids and e-mail. https://popia.co.za/section-1-definitions/ (knowledge; verify the list wording)
- Cookie ids (`_ga`, `_fbp`, `_fbc`): treated as personal data by most commentary, as they are persistent per-browser pseudonymous identifiers; ePrivacy consent rules apply regardless. Academic work shows `fbclid` can be combined with `_fbp` to link browsing to an account. (fetched via search) https://arxiv.org/pdf/2208.00710.pdf ; commentary summary https://www.cookieyes.com/blog/ip-address-personal-data-gdpr/
- **gclid / gbraid / wbraid / fbclid**: no regulator ruling found (search turned up none; verify). Reasoned position: they are per-click, ad-platform-issued identifiers that the platform can map to a specific user/browser and ad account. On the regulator-agnostic test (can the holder or a party with lawful means link it to a person?), they are pseudonymous online identifiers, which GDPR treats as personal data, especially when stored beside user id and email as in `SignupAttribution`. Stored with the user's email in the same row the API returns, they are personal data in context. Conclude: treat as personal data of lower sensitivity than IP/cookie ids; they are the minimum needed to reconcile conversions with Google/Meta ad accounts (offline conversion upload uses gclid), so there is a purpose-based argument to keep them for lead monitoring and payouts. Record this decision and its reason in `docs/product/security-and-data-handling.md`. (judgement, not authority)
- **referer and raw_query / landing_path**: not identifiers by themselves, but `raw_query` is free-form and can contain anything the visitor's link had: emails, tokens, `fbclid`/`gclid`, password-reset or magic-link tokens, other trackers' ids. `referer` can include a full URL with query strings from the previous site. Best practice is to treat them as potentially personal and as potentially secret-bearing. The idea already settles that they are returned. The spec should therefore (a) say so in the security doc, (b) not add a transformation (derived fields are out of scope), and (c) flag as a risk that `raw_query` is returned verbatim. If any stripping exists at capture time, document it; if not, note the gap. OWASP: do not carry secrets in URLs, but data already captured stays captured. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html (knowledge, "data to exclude" list includes tokens/session ids)
- **Email on a signup attribution**: it is the join key the scripts need; return `user` as `{id, email}` only. Adding name is extra personal data with no stated need (minimisation); the export carries email only, so mirror that.
- **Retention**: hits are pruned, signup attributions are not; a "data subject erasure" would hit `SignupAttribution` rows, and erased users' rows would be missing from the API with no tombstone (the effort already accepts this for deletions). Mention it in the docs.
- Because scoping is all-or-nothing per `referral_data`, key holders see email + click ids + raw query for every user. Name this in the docs so operators grant the scope knowingly. Log key id per request (already in child 1).

## 4. Foreign keys: id plus label

- Return the id for joins and a readable label beside it. Stripe returns the id by default and an expanded object only on request (`expand[]`). https://docs.stripe.com/api/expanding_objects (knowledge). For a fixed, small payload, flat sibling fields are simpler and cheaper than expand and avoid N+1 (use `select_related`).
- Convention for this effort: `referral_code` = the code's id (UUID string) and a sibling `referral_code_code` or `code` for the text. A name like `referral_code_code` is ugly; `code` on a hit reads naturally, as the idea says "the code text". For the user: `user_id` + `user_email`, or a nested `user: {id, email}`. Choose one style across the four resources and child 1 (check what child 1 did for registrations). Flat siblings are friendlier for CSV/pandas consumers (`json_normalize` copes either way). Do not rename the underlying FK field, since export names are the stated baseline.
- Label denormalisation caveat: labels can change (code text is probably immutable, email is not). Consumers should key on the id.
- Null FKs: `SignupAttribution.referral_code` may be blank/null (organic signups); say whether the id is null and the text is null or empty. Use null for absent relations, never empty string for ids.

## 5. Documenting reconciliation gaps (counter vs pruned log)

- State plainly in the endpoint docs, once, near the top of the referral section:
  1. `ReferralCode.hit_count` is a running counter incremented at hit time. It is not computed from the hit log.
  2. `prune_referral_code_hits` deletes old hits; the counter is not decremented. So `count(hits for code) <= hit_count`, and the gap grows with pruning.
  3. Machine fetches (`is_machine_fetch`) may or may not be counted in `hit_count`; state which (check the model/hit logging code) so a consumer can reproduce the number from hits.
  4. Race/duplicate effects on the counter, if any exist. State the known direction of error.
  5. Which number to trust for what: `hit_count` for lifetime volume; the hit log for recent time-series, only within the retention period. Also give the retention period and the prune command's default if it has one.
- Precedent: Stripe's docs and BigQuery export docs mark such known gaps in the field description ("approximate", "may not equal..."). Put the same text in the OpenAPI field `description` (drf-spectacular) as well as the prose page, so the schema tells the truth. (knowledge)
- A test pinning the documented behaviour is worth adding (e.g. a code with a counter greater than its surviving hits serialises both values unchanged), so a future "fix" is a deliberate decision.
- Similarly document: `last_hit_at` is a counter-side value and may be later than the newest surviving hit; `FirstTouchCount.count` vs `SignupAttribution` rows can differ for the same day/key because of overflow bucketing and any signups before counting began.

## 6. Checklist for the spec

- Orderings: `(created_at,id)`, `(hit_at,id)`, `(signed_up_at,id)`, `(day,id)`; ordering fields non-null, indexed.
- Since-filter: inclusive on the ordered field; date-typed for `day`; invalid input is 400; naive datetimes rejected or read as UTC.
- Docs: dedupe by id; overlap of minutes on logs; lookback of at least 2 days on first-touch counts, today provisional; full re-pull of referral codes.
- Day bucket timezone stated.
- Withheld fields listed in the security doc with the reason; click ids, `raw_query`, `referer` and email explicitly named as returned and as personal data; decision recorded.
- Reconciliation notes in both prose and schema descriptions; no behaviour changes.

## References

- https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination (fetched)
- https://docs.stripe.com/api/pagination ; https://docs.stripe.com/api/expanding_objects
- https://adriennevermorel-astro.pages.dev/notes/late-arriving-data-lookback-window-pattern/
- https://docs.hologrow.ai/marrow-data/data-fetch-periods
- https://support.fivetran.com/hc/en-us/community/posts/38277616619927-Connector-Improvement-Incremental-Update-Sync-Handling
- https://eur-lex.europa.eu/eli/reg/2016/679/oj (GDPR Art. 4(1), 5(1)(c), Recital 30)
- https://curia.europa.eu/juris/liste.jsf?num=C-582/14 (Breyer)
- https://popia.co.za/section-1-definitions/
- https://www.cookieyes.com/blog/ip-address-personal-data-gdpr/
- https://arxiv.org/pdf/2208.00710.pdf
- https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/DateRange
- https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Not legal advice; no regulator guidance specific to gclid/fbclid was found.

status: ok
