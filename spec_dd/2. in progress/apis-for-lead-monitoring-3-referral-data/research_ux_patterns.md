# Research: UX (developer-experience) patterns for referral-data endpoints

Scope: what script authors and operators need from `docs/api.md` (child 1) when it gains the four referral endpoints. Project facts come from `docs/api.md` and `idea.md`. External points are from the pages cited at the end. Where I rely on general industry convention rather than a page I read, I say so.

## What child 1 already fixed (follow it)

- Docs shape: shared "Syncing data" section (pages, `updated_since`, deletions, one httpx example), then one section per endpoint with a small table (API scope, List, Detail, Filters), a Fields table (Field / Type / Notes) and a prose "what moves X" section.
- Errors: `{"detail", "code"}`; 403 for a valid key lacking the scope, with the detail naming the scope; 404 only for "no row with that id on this key's site". Branch on status and `code`.
- Sync recipe: upsert by `id`, expect repeats, checkpoint at max timestamp minus 5 minutes, advance only after `next` is null, first run sends no filter.
- Gap: the scope table lists `referral_data` as `ReferralCode`, `ReferralCodeHit`, `SignupAttribution`; `FirstTouchCount` is missing and needs adding. The "Only `users` has an endpoint" sentence also needs updating.

## 1. Incremental sync recipes

- Common pattern across APIs: checkpoint on the last value seen, re-ask from that value inclusively, upsert by id, and overlap the window to absorb late commits. Stripe's list API gives cursor paging (`starting_after`, `has_more`) and relies on client auto-pagination helpers; it has no "changed since" on most lists, so incremental sync there is via the events feed (Stripe pagination page).
- For append-only logs (hits, signup attributions) the recipe is simple: checkpoint = last timestamp seen, inclusive filter, upsert by `id`. The 5-minute margin from child 1 still applies for late commits.
- For mutable daily aggregates (first-touch counts) the established pattern, e.g. analytics reporting APIs such as GA4's Data API, is a date range rather than a change feed, plus a warning that recent days are still moving. (GA4 page confirms absolute `startDate`/`endDate` ranges; its freshness wording was not in the part I read, so treat "recent days change" as general convention.) Recommended doc shape:
  1. State plainly there is no changed-since signal for counts: `count` rises through the day and nothing records it.
  2. Give a lookback rule as a number: on each run, ask from `today - N days` (N a documented constant, e.g. 2 or 3; spec to choose) and overwrite by `id` (or by `(day, key_hash)`).
  3. Say a day older than N is treated as final but a periodic full pull (no filter) corrects drift, mirroring child 1's deletions advice.
  4. Checkpoint is a date, not a datetime; the example should compute `date.today() - timedelta(days=N)` instead of "max seen minus 5 minutes", so the example differs from the users loop on purpose.
- Referral codes: "full pull every run, upsert by `id`" with one sentence on why (small table, `hit_count`/`label`/`is_active` change in place, no `updated_at`).
- Put a small "which recipe for which endpoint" table at the top of the referral section: Endpoint | Order | Filter | Recipe (full pull / checkpoint / lookback). Script authors scan for this first.

## 2. Documenting withheld fields and data caveats

- Pattern: a short "Not returned" line under the Fields table naming each withheld field and the reason class (personal or device identifier, not needed to attribute a lead), plus a pointer to where it still lives (admin export, `view_` permission). Child 1 does this for users in one sentence ("Passwords ... are never returned"); do the same, listing all five names, so a script author searching for `client_ip` finds the answer.
- Say "not returned under any key or scope" to head off requests to add it.
- Caveats work best as a dedicated "Known data caveats" subsection, each caveat as: what you will see, why, what to do. For this effort:
  - `hit_count` is a counter on the code, not `COUNT(*)` of the hit log; they can disagree. Rule of thumb for scripts: use `hit_count` for the lifetime total as the site recorded it, use the hit log for per-day or per-source analysis, and never expect them to reconcile.
  - Hits can be pruned (`prune_referral_code_hits`), so old hits may be missing while `hit_count` still includes them; a full pull can legitimately return fewer rows than before. Deletions are not visible to the filter (inherited).
  - `is_machine_fetch` hits are in the log; tell script authors to filter on it when counting human visits (the field exists for this; wording should be checked against `docs/product/referral-codes.md`).
  - Signup attribution is first-touch only, one per user.
  - First-touch counts with `is_overflow` true are a catch-all bucket; explain what that means in one sentence and that `key_hash` identifies the key combination.
- Keep caveats factual and "documented, not corrected", matching the idea.

## 3. Example Python loop

- Reuse child 1's `get_page` (429 handling) and follow-`next`-verbatim loop; do not write a second style. Parameterise rather than copy: a generic `iter_rows(client, path, params)` generator that yields rows is the form script authors reuse (and pandas can consume: `pd.DataFrame(iter_rows(...))`). Suggest the spec add this generator to the shared section only if it does not change child 1's tested example; otherwise show it once in the referral section.
- One extra example is enough: first-touch counts with the date lookback, because it is the one recipe that differs. Hits and attributions are "the users loop with a different field name"; a table row saying which field to checkpoint on is sufficient.
- Examples should be runnable end to end with env vars `FLS_BASE_URL`, `FLS_API_KEY`, as child 1 does, and save the checkpoint only after the run completes.

## 4. Error shapes: 403 vs 404 for missing scope

- Child 1 already returns 403 with a scope-naming detail for a valid key without the scope, and 404 only for a missing row on the key's site. Keep it: the key holder is authenticated, so the existence of the endpoint is not a secret, and a 403 that names the scope tells the operator exactly what to fix (add `referral_data` by rotating the key). Returning 404 for scope failures is used where resource existence must be hidden (the project's own browser-facing rule for organisation scope), which does not apply to a documented API.
- Doc point: state that all four referral endpoints, list and detail, give the same 403, and that a row from another site is a 404 on detail (never a 403, so ids cannot be probed across sites).
- The `code` for the 403 should be stable and listed (check what child 1 emits, e.g. `permission_denied`), so scripts can branch on `code`.

## 5. Naming the date filter param

Options seen in the wild:
- `updated_since` / `modified_since` / `since`: datetime semantic "changed at or after"; common in CRM and issue-tracker APIs. (General convention; not re-fetched.)
- `created[gte]` / `created[lt]`: range operators, Stripe style (Stripe API docs; the pagination page I fetched did not show them).
- `start_date`/`end_date` or `date_from`/`date_to`: used by reporting/analytics APIs for day-grained windows (GA4 uses `startDate`/`endDate` in `dateRanges`).
- `day__gte`: Django-filter lookup spelling; natural for Django developers and self-describing, but exposes ORM spelling and implies a family (`__lte`, `__lt`) the API may not offer.

Whether to keep one name across resources: the usual DX argument is yes, because script authors write one loop and `docs/api.md` tells them "every list endpoint filters the same way". Counter-argument: `updated_since` on hits would be a lie, because nothing was "updated"; hits are filtered on `hit_at`, attributions on `signed_up_at`, counts on `day`. The roadmap and idea already say the filter name is open for first-touch counts (roadmap line 734).

Trade-off summary for the spec:
- A. One name (`updated_since`) everywhere, documented as "the field the endpoint is ordered by". Pros: one loop; matches child 1 wording and the effort's "inclusive changed-since filter". Cons: misleading name on append-only logs; on `first-touch-counts` it takes a date, not a datetime, so the type differs per endpoint (needs a clear doc line and a 400 message that names the accepted format).
- B. Same name on the datetime resources, a different one (`day_from`/`date_from`, or `day__gte`) on first-touch counts. Pros: honest about the lack of a change signal on counts (the idea says the API "does not claim a changed-since signal that does not exist"); the type matches the name. Cons: breaks the "one loop" promise.
- Weigh: idea says counts have no change signal, which argues for B on counts; but the idea also says the effort's filter "works on those three resources against the same field they are ordered on", which argues for A. A middle path: accept `updated_since` on the two datetime resources and a distinctly named date filter on counts, and in the shared docs table list "Filter" per endpoint (child 1's per-endpoint table already has a Filters row). Recommendation leans B for counts, with the error message and docs making the difference visible; the spec decides.
- If a date is accepted where a datetime is expected elsewhere, document the exact format (`YYYY-MM-DD`), that it is inclusive, and which timezone defines the day (the site's or UTC); this is the common source of off-by-one days in scripts and should be in the Fields notes for `day`.

## 6. Nested vs flat foreign keys

- Flat, with id plus a readable sibling (`referral_code` = id, `referral_code_text` / `code`; `user` = id, `user_email`) is what script authors prefer for CSV and pandas: `pd.DataFrame(rows)` or `csv.DictWriter` works with no flattening, `pd.json_normalize` is not needed, and columns join on the id. Nested objects (`{"referral_code": {"id": 3, "code": "abc"}}`) read cleanly in JSON but force `json_normalize` and produce dotted column names. (General convention and pandas behaviour; no single page cited.)
- Stripe leaves the related object as an id string by default and expands only on request (`expand`), another vote for ids by default (Stripe API docs, general knowledge).
- The idea's wording ("ids with the readable value beside them") matches the flat form. Naming points for the spec:
  - Keep the field named `referral_code` as the id (the idea says the id, and the admin export column name is `referral_code`), not renamed to `referral_code_id`; a rename breaks "same names as the export" (the export column holds text, so this one needs an explicit note in the docs that the API's `referral_code` is the id while the export's holds text).
  - Pick one pattern for the readable value and use it on all resources: `<fk>_<attr>`, e.g. `referral_code_text`... but note the code model's own field is `code`, so `referral_code_code` reads badly; `referral_code_text` as the idea names it is acceptable. For users, `user_email` follows the same pattern.
  - On signup attributions and first-touch counts the `referral_code` field already exists as a plain field in the export (check the model: whether it is an FK or text). If it is a text copy of the code, the spec must not collide with the hit resource's meaning of the same name; document the difference per resource in the Fields tables.
  - Id-plus-email only for the user (no name) is the minimal choice and matches the export; adding name later is allowed in v1 (new fields are additive), so deferring it is safe.
- Nullable FKs (user deleted, code removed) should return `null` for both the id and the readable sibling; document it.

## 7. Filters on referral codes

- With a full pull of a small table, a script filters client-side. Convention in similar APIs: no filters on tiny reference lists, since each filter is a documented, tested promise. An `is_active` filter is cheap and common, but adding it later is allowed within v1 (filters only grow), so omitting it now carries no cost to script authors. Lean to none.

## Doc layout recommendation

1. Update the scope table (add `FirstTouchCount`) and the "Only users has an endpoint" sentence; add a row per endpoint to a short "which recipe" table.
2. One section per resource using the Users template: header table, Fields table (types, null rules, notes for FK siblings and `day`), "Not returned" line where relevant.
3. A "Referral data: sync recipes" subsection (full pull / checkpoint / lookback) and a "Known data caveats" subsection.
4. One new example (lookback loop) reusing child 1 helpers.
5. Update `docs/product/security-and-data-handling.md` with the returned field list and the five withheld fields.

## References

- Stripe pagination (cursor paging, `has_more`, auto-pagination helpers): https://docs.stripe.com/api/pagination
- Google Analytics Data API basics (absolute date ranges `startDate`/`endDate`, rows of dimension and metric values in column order): https://developers.google.com/analytics/devguides/reporting/data/v1/basics
- Project: `docs/api.md`, `spec_dd/2. in progress/apis-for-lead-monitoring-3-referral-data/idea.md`, `spec_dd/1. next/roadmap.md` (line 734 open question on first-touch filter spelling).
- Not fetched, stated as general convention: `updated_since`/`since` naming, django-filter lookup spelling, pandas `json_normalize` behaviour.

status: ok
