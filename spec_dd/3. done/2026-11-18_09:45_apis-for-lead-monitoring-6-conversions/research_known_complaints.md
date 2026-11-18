# Research: known complaints with attribution/conversion APIs and incremental-sync list APIs

Scope: what would change the spec for the attribution touches and conversions endpoints. Sources are vendor docs and forums (indicative, not authoritative); items marked "(general practice)" come from well-known API-design practice, not a fetched source.

## Complaint themes and what each means for the spec

### 1. Missed rows in incremental sync (the biggest one)
- Complaint: a cursor on a timestamp steps past rows that become visible after that timestamp, so they are never read. Typical cause: the timestamp is set at transaction start but the row commits later, so an in-flight row gets an earlier `recorded_at` than rows already read. Fivetran, Airbyte and others answer with lookback windows or safety lags.
- Relevance: the idea settles on `recorded_at` as the paging key. That is only safe if `recorded_at` is not assigned before commit. If it is a default `timezone.now()` taken when the object is built and the insert runs in a longer transaction, a concurrent writer can commit a row with a `recorded_at` earlier than one a script has already read.
- Spec changes:
  - State the guarantee precisely: no loss as long as rows commit in near `recorded_at` order, and document a recommended overlap (the script re-requests from `last recorded_at` minus a small margin, or simply uses the inclusive `updated_since` and dedups by id). The idea's inclusive boundary already helps with ties; add an explicit "dedup by id" line.
  - Check how `referral-attribution-over-time` sets `recorded_at` (auto_now_add at save time is better than a value computed earlier) and whether flush writes (`signup_flush`, `login_flush`) happen inside one transaction with bulk create, where many rows share or precede a commit time. Consider a documented lookback instead of promising "misses nothing".
  - Equal timestamps: `(recorded_at, id)` ordering needs a UUID id tiebreak that is stable; confirm the cursor encodes both values and not only the time. (general practice)
- Sources: https://fivetran.com/blog/building-efficient-data-pipelines-with-incremental-updates , https://docs.airbyte.com/platform/connector-development/connector-builder-ui/incremental-sync , https://support.fivetran.com/hc/en-us/community/posts/42642461765783-Add-configurable-lookback-window-for-Oracle-Fusion-Field-Service-Activities-sync , https://help.twig.so/rag-scenarios-and-solutions/data-integration/incremental-sync

### 2. Null or missing timestamps hide rows from the filter
- Complaint: never-modified rows with a null "updated" field are skipped by `updated_since`. Fix: periodic full reconcile.
- Relevance: `recorded_at` is non-null on append-only rows, which avoids this. Spec should say a script can always do a full unfiltered read (no `updated_since`) as the reconcile path, and that the list is stable for that purpose.
- Source: https://www.apihelpcenter.flxpoint.com/docs/guides/syncing-data-incrementally

### 3. Late-arriving events versus the cursor
- Complaint (ad platforms, GA4): conversions arrive days late and attribution credit changes after the fact, so yesterday's numbers move.
- Relevance: here late events are in two forms. (a) Touches written at signup/login with an old `occurred_at` (already handled: cursor is on `recorded_at`). (b) A conversion whose first/last touch resolution depended on a touch flushed after the conversion; check whether `referral-attribution-over-time` ever re-resolves or edits a conversion. The idea says rows are never changed; if any code path updates a conversion's touches, the "written since" guarantee breaks. Spec should state this as an assumption and have a test or a check against the sibling spec.
- Spec changes: document that a conversion may reference a touch whose `recorded_at` is later than the conversion's own (if that is possible), so a script joining by id must tolerate a touch not yet seen. Decide whether `first_touch` id is always present in the list when the conversion is, and say so (documented join-order tolerance: read touches then conversions, or retry).
- Sources: https://www.cometly.com/post/conversion-lag-reporting-issues , https://readme.anytrack.io/docs/attribution-delays , https://www.relevantaudience.com/google-ads-en/google-ads-attribution-ignores-late-offline-conversions/

### 4. Counts disagree with dashboards or exports
- Complaint: API totals differ from the vendor dashboard or admin because of different attribution windows, time zones, "today" being partial, filtered-out statuses, or different dedup rules. Pinterest forum threads on API vs Ads Manager are typical.
- Relevance: the admin export and admin "code in play" filter are the comparison points. The spec should:
  - Pin the filter semantics of `referral_code` (either first or last, per answers.md) in the docs, and name that the admin filter matches it.
  - Return `window_days` per row (already settled) so a script knows the window that applied; state that the API does not recompute under a different window.
  - Return ISO 8601 UTC timestamps and document the timezone; admin display may be in local time, a classic cause of day-boundary mismatches.
  - Decide whether the list is paginated without a total count (a count that disagrees under concurrent writes is a complaint) and document that counts are not offered, or offer an explicit `count` knowingly.
  - Add a test that the API row set for a site equals the admin export row set for the same site, so the two cannot drift.
- Sources: https://clickflare.com/blog/why-your-conversions-dont-match-across-platforms , https://community.pinterest.biz/t/total-conversions-mismatch-between-ads-manager-and-reporting-api-v5/42309 , https://whitelabelcoders.com/blog/why-does-my-affiliate-dashboard-show-incorrect-metrics/

### 5. First-touch versus last-touch confusion
- Complaint: users assume "the" referrer is one value and are surprised by two codes; credit disputes arise when a script silently picks the wrong one. Little authoritative source material; mostly general practice.
- Spec changes:
  - Document precisely in the endpoint description and OpenAPI: first = earliest touch in the window, last = most recent touch before the conversion, both bounded by `window_days`, and what "blank" means (nothing in play, a recorded answer).
  - Say that the first and last code can be equal, can differ, and that the code on the conversion is frozen at resolution time and may differ from the code currently on the touch row or the user's current attribution (child 3 signup attribution). Without that, scripts compare child 3 and child 6 and report a mismatch.
  - Keep three filters from answers.md and document their precedence: `referral_code` combined with `first_referral_code` is an AND of filters.
  - Case and normalisation of codes in filters (exact match as stored; say whether case-insensitive). (general practice)

### 6. Deleted targets, users and codes
- Complaint: rows vanish or break after the target is deleted; scripts see dangling ids, or orphaned history disappears and totals shrink between pulls.
- Relevance: `target_label` frozen is the right answer. The spec should state what happens to rows when a user is deleted (touch/conversion FK behaviour in the sibling spec: cascade, set null, protect?). If cascade, rows silently disappear and there is no deletion feed (out of scope), so a script's mirror drifts. Spec should state this as a known limit in the docs and in the security page, and say that `user` may be null if the sibling uses SET_NULL. Also: a referral code later deleted or renamed: the codes on rows are frozen strings, so filter by string, not by a live code record.
- Note the prune command is out of scope but would also cause disappearance; the docs should state that old touches may be pruned and the API is not an archive.

### 7. Pagination drift
- Complaint: offset pagination shows duplicates or skips rows when data is inserted between page requests; cursor with a snapshot bound is the fix. Twig suggests bounding a run by a snapshot timestamp.
- Relevance: the idea already chooses a cursor on `(recorded_at, id)`, which suffers no offset drift for append-only data. Remaining issues: a cursor that is not opaque, expiring cursors, a cursor combined with changed filters, and page size changes mid-walk. Spec should say: cursor is opaque, valid only with the same filters, an invalid cursor returns 400 with a clear message, and order is ascending (oldest first) so new rows land at the end. Confirm ascending vs descending default, since a script following forward needs ascending.
- Source: https://help.twig.so/rag-scenarios-and-solutions/data-integration/incremental-sync

### 8. Rate limits and bulk first loads
- Complaint: first full load on a site with large history hits throttles or timeouts; limits are undocumented; no `Retry-After`; capped page size too small to be useful.
- Spec changes: document the per-key throttle values for these resources, return 429 with `Retry-After`, say the max page size, and that touches are likely the larger list (one per landing) so a first sync can take many requests. Consider whether the touch list needs a heavier index on `(site, recorded_at, id)`; confirm the sibling models carry indexes on `recorded_at` and on the filter fields (`referral_code`, `first_referral_code`, `last_referral_code`, `kind`, user). Avoid per-row queries (user email, touch lookups) with select_related, as already intended.
- (general practice)

### 9. Concurrent runs and duplicate processing
- Complaint: two overlapping sync jobs clobber each other's saved watermark, processing rows twice or skipping them.
- Relevance: client-side, but the docs example should show idempotent upsert by id and keep the watermark only after a page is fully processed, and not advance it from a request that failed midway.
- Source: https://help.twig.so/rag-scenarios-and-solutions/data-integration/incremental-sync

### 10. Duplicate events and idempotency
- Complaint: server and client paths double-count; dedup by a shared key.
- Relevance: `key_hash` makes writes idempotent upstream. Spec should state that the API never returns two rows for one logical conversion; if the sibling can produce them, say so. `key_hash` stays hidden, so a script's only dedup key is the row id; confirm that is enough.
- Source: https://clickflare.com/blog/why-your-conversions-dont-match-across-platforms

## Open points from the idea, informed by these complaints
- Flat lists with ids versus embedding: complaints about join drift (item 3) favour keeping flat lists, with a documented rule that a referenced touch may not yet be visible in a script's mirror. Keep flat; add the join-order guidance to the docs.
- User as id only versus id plus email: follow child 3 exactly. Different shapes across resources is itself a common complaint (inconsistent field naming/shape). Do not deviate.
- Date range filters: offer none beyond `updated_since` unless child 1 has them; a bounded range invites the "partial today" count mismatch (item 4). If offered, filter on `recorded_at` only, never `occurred_at`, and name them accordingly (for example `recorded_before`) so nobody assumes event time.
- Project without the sibling installed: confirm an empty list (200, `results: []`), not a 404 or 500; it keeps scripts uniform across projects. Include the resource in the OpenAPI schema in both cases.

## Candidate acceptance checks to carry into the spec
1. Two rows with equal `recorded_at` are both returned across a page boundary, once each.
2. A row committed late with an older `recorded_at` than the cursor: document the behaviour; test the overlap guidance (inclusive boundary returns the boundary row again).
3. A touch whose `occurred_at` is older than rows already read still appears when paging by `recorded_at`.
4. Deleting a conversion's target leaves the row readable with `target_label` intact.
5. API row set equals admin export row set for the site and filters.
6. A key without the scope, and a key for another site, see no rows.
7. Query count does not grow with page size.
8. `referral_code` filter matches first or last; `first_referral_code` and `last_referral_code` match only their own; combined filters AND.
9. Invalid or filter-mismatched cursor returns 400.

## Reference URLs
- https://fivetran.com/blog/building-efficient-data-pipelines-with-incremental-updates
- https://docs.airbyte.com/platform/connector-development/connector-builder-ui/incremental-sync
- https://support.fivetran.com/hc/en-us/community/posts/42642461765783-Add-configurable-lookback-window-for-Oracle-Fusion-Field-Service-Activities-sync
- https://www.apihelpcenter.flxpoint.com/docs/guides/syncing-data-incrementally
- https://help.twig.so/rag-scenarios-and-solutions/data-integration/incremental-sync
- https://clickflare.com/blog/why-your-conversions-dont-match-across-platforms
- https://whitelabelcoders.com/blog/why-does-my-affiliate-dashboard-show-incorrect-metrics/
- https://www.cometly.com/post/conversion-lag-reporting-issues
- https://readme.anytrack.io/docs/attribution-delays
- https://www.relevantaudience.com/google-ads-en/google-ads-attribution-ignores-late-offline-conversions/
- https://community.pinterest.biz/t/total-conversions-mismatch-between-ads-manager-and-reporting-api-v5/42309

status: ok · reason: findings written; sources are vendor docs and forums, first/last-touch and rate-limit items rest on general practice
