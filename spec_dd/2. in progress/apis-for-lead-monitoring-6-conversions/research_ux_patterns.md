# Research: UX patterns (developer experience of the touches and conversions lists)

The "user" is a developer writing a lead-monitoring script. The house style comes from `docs/api.md`. The outside references are from my knowledge of those APIs and were not re-fetched this session. Treat them as pointers.

## House style that the spec should match (from `docs/api.md`)

- Every resource section has a header table (API scope, List, Detail, Ordering field, Filters, Recipe), a JSON example, a Fields table (Field, Type, Notes), then prose sections. Notable ones are "What moves `updated_at`" and the caveats.
- A bad query parameter gives a 400 whose body is keyed by the parameter, e.g. `{"updated_since": ["..."]}`. This is stated in the Errors table. The `day_since` text adds "A datetime, or a value that does not parse, is a 400 keyed `day_since`". Filter validation errors for the new resources should follow this and name the expected format.
- Recipes are named and linked: Checkpoint, Full pull, Lookback. Both new resources are append-only on `recorded_at`, so they use **Checkpoint** (as `referral-code-hits` and `signup-attributions` already do). The incremental syncs table needs two new rows.
- The Python example is one loop with a `PATHS` dict of `path: filter field`, a 5-minute margin, and an upsert by `id`. The new endpoints are cheap to add: `"attribution-touches": "recorded_at"` and `"conversions": "recorded_at"`. The example's `datetime.fromisoformat(row[field])` works unchanged because the ordering field is returned in every row. **Spec consequence:** `recorded_at` must be a returned field on both resources (it is). The scope paragraph above the example needs no change, because `referral_data` is already listed.
- `docs/api.md` already says "A field named `referral_code` means different things on different API endpoints". On touches and conversions it is code text. The docs must say so again.
- Inconsistency to resolve: signup attributions return `user` (integer id) plus `user_email`. The learner and interest endpoints return `user_id` plus email. The idea says "the account (as the user's id)" and leaves open whether the email is returned. Recommendation: follow signup attributions, since this is the same `referral_data` family and the `referral_code` caveat is already written there. That means `user` (integer) and `user_email`. Decide once and state it in the spec. The `first_touch` and `last_touch` ids are the other candidates for `_id` naming. See the naming section below.

## Filter naming (what developers expect)

- Stripe, GitHub and Segment-style APIs use a plain field name for exact match (`?kind=course_application`, `?user=412`) and a suffix or prefix for ranges (`created[gte]`, `since`). This repo already uses `updated_since` and `day_since`, inclusive, so range filters beyond `updated_since` are not needed. Offering `occurred_since` would invite the wrong paging key (see late-arriving rows below). Recommendation: do not offer date-range filters on `occurred_at`. Say so in the docs. This is a deliberate gap, not an oversight.
- Filter names should equal field names where possible. A developer sees `first_referral_code` in the row and expects `?first_referral_code=x`. The answers file already settles `referral_code` (either), `first_referral_code` and `last_referral_code`. The user filter should be named for the field returned (`user`, matching signup attributions if that name is chosen). Do not invent `user_id` as a filter when the field is `user`.
- Overloaded `referral_code`: on conversions it means "first OR last". This is the one surprise. The docs should state it in the Filters row and in a short "Filtering by code" section, with the payout-style query as the worked example. Without that, someone filtering `?referral_code=X` and counting rows will double-credit.
- Matching: say whether code matching is case-sensitive. Code text on `referral-codes` is "unique ignoring case", so a developer will ask. **Spec decision needed:** case-insensitive exact match is the least surprising, and it matches how `/go/<code>` resolves. Document whichever is chosen.
- Combining filters is AND. State it once.
- A blank code filter, such as `?referral_code=`, is ambiguous. It could mean "no code in play" (a recorded answer per the idea) or "filter absent". Recommend treating an empty value as a 400 (or documenting it as absent), and giving no way to filter on "no code" unless the spec wants one. Flag this for the spec. The idea says both-blank is a recorded answer, so a script may reasonably want it, and with 400 it can filter client-side.

## Error messages for bad filter values

- A good message names the parameter, the bad value, and the accepted set or format. Stripe's `invalid_request_error` carries a `param` field, and DRF's per-field list of messages is the same idea.
- For `kind`, the message should list the four values: `account_signup`, `course_application`, `course_interest`, `course_registration`. DRF's default "Select a valid choice" without the list is a common complaint. Spec it as an acceptance criterion: a 400 keyed `kind`, listing the valid values.
- For a malformed `user`, a non-integer gives a 400 keyed `user`. An unknown user id on this site should return an empty list, not a 404 or a 400. A filter that matches nothing is not an error, and a different answer would leak whether a user exists on another site.
- For `updated_since`, reuse the existing message and behaviour. No timezone or unparseable gives a 400 keyed `updated_since`.
- Unknown query parameters: the existing docs say nothing. Silently ignoring a misspelled filter (`?referal_code=`) returns everything and looks like success. This is the most dangerous DX failure for a payout script. Check what child 1 does. If it ignores them, the docs should warn in one sentence and the spec should not diverge from child 1. If child 1 can reject them, rejecting is better. Raise as an open question for the spec.
- Branch on status and `code`, not `detail`, per the existing docs. A 400 body is keyed by parameter, so the spec should not invent a new envelope.

## Late-arriving rows (how to explain it)

- Pattern: name the two clocks. Event-time vs. ingestion-time ("watermark") is the usual framing in streaming docs (Segment's `timestamp` vs `receivedAt`, and Stripe's `created` vs the event delivery time). Here it is `occurred_at` (when it happened) vs `recorded_at` (when we wrote it). The docs should give a three-line definition of each, then a rule: **page and checkpoint on `recorded_at`; sort your own timeline on `occurred_at`.**
- The existing doc style explains with a concrete mechanism. Reuse it: "A visitor lands on Monday with the tracking cookie. They sign up on Thursday. The touch is written on Thursday with `occurred_at` Monday, and `recorded_via` is `signup_flush`."
- A table of `recorded_via` values and what each says about ordering trust would help (`live`: written at the time. `signup_flush` and `login_flush`: written later from the cookie, so `occurred_at` can be older than rows you already read). The idea gives the values and says they tell a reader how far to trust the ordering, but not what exactly the docs should say. Spec it.
- State plainly that a row can arrive with an `occurred_at` older than your checkpoint. A script that checkpoints on `occurred_at` silently loses it. This is the failure to warn against, as a short "Do not" callout.
- The existing 5-minute margin ("rows whose transaction committed late with an earlier timestamp") applies on `recorded_at`. Say it is separate from the late-arrival effect above: the margin covers transaction commit lag (minutes), and `occurred_at` lag can be days. Developers conflate them.
- Within a customer's timeline, a script ordering by `occurred_at` should break ties on `id` or `recorded_at`. Mention it.
- Do not promise that `first_touch` and `last_touch` are stable once a conversion is read. The idea says rows never change, so the docs can say they are final once written. A late flush may mean a conversion is written before a touch that occurred earlier. Check against the attribution spec whether a conversion's resolved first and last touch are fixed at write time, and say so. If they are, there is nothing to re-read. If not, the "append-only" claim needs care.

## Documenting first vs last touch

- Define in one table, not prose:
  - `first_touch` / `first_referral_code`: the earliest touch in play when the conversion was resolved, inside the attribution window (`window_days`).
  - `last_touch` / `last_referral_code`: the latest such touch.
  - Same touch, one touch in play: both ids are equal. Say so, so nobody reads it as a data error.
  - Nothing in play: both ids `null` and both codes `""`. This is a recorded answer (idea). Do not call it missing data.
- Warn that the API does not choose a model: no credit rules, "first" and "last" are what the data records. This matches the out-of-scope line. Add one sentence that a payout script picks first or last itself.
- `window_days` should be explained as the window that applied when the row was resolved, not today's setting. Changing the setting later does not rewrite old rows.
- Reader's decision aid: a tiny worked example with three touches and one conversion, showing the two codes. It earns its space because this is the single most-misread part.
- Join advice: `first_touch` / `last_touch` ids join to the touches list by `id`. Warn that the pruned touch case (prune command out of scope, but possible later) can leave a dangling id. State that the codes on the conversion remain the durable answer. Flag it only if the attribution spec says touches can be pruned (the idea mentions a prune command). If so, the docs should say a touch may be missing and that `first_referral_code` and `last_referral_code` are the copied values.

## Field naming and shape details worth deciding in the spec

- Ids of related rows: `first_touch` and `last_touch` vs `first_touch_id` and `last_touch_id`. The repo mixes `user` (signup attributions) and `user_id` (registrations). Pick `first_touch_id` and `last_touch_id`, because `first_touch` next to `first_referral_code` reads as an embedded object, and the idea defaults to flat ids. If the name is `user` for the account, be explicit in the Notes column.
- `kind` values and `target_label` go in a table: for each `kind`, what `target_label` holds (course title or account email). The idea says "frozen course title or account email". Docs must say it is frozen: it does not follow later renames or email changes. This mirrors the existing "can be stale" notes. Also note that `account_signup` rows carry the email in `target_label`, so it is personal data. Consistent with the existing "Treat them as you would the email address" line.
- Blank strings, never `null`, for codes and UTM (existing rule at the top of Referral data). Keep it.
- A conversions `id` type: the attribution spec decides (UUID or integer). The idea says "the row's own id". The Fields table needs the type, and the docs say "Upsert on this".
- Empty-list behaviour: say that a site with no rows, or without the attribution app's rows, returns `{"next": null, "results": []}`. Confirm it is not a 404 (the idea's open item). Docs line: "An empty list is the answer, not an error."

## Docs structure recommendation (so the spec can list the doc edits)

1. Scope table row for `referral_data`: add `AttributionTouch`, `Conversion`.
2. Intro bullet list: add links for the two endpoints under the referral data line.
3. Incremental syncs table: two Checkpoint rows, filter on `recorded_at`.
4. Checkpoint section: extend the sentence about "never changed once written" to name them, and add a short "Late-arriving rows" subsection (or a link to the one in the touches section). Keep the explanation in one place and link to it.
5. Example: add the two paths to `PATHS`. Add one short second example, or a comment, showing a client-side join of conversions to touches by id and sorting on `occurred_at`. That is the actual job a lead-monitoring script does. Keep it short, because the existing examples are already long. Alternatively, a ten-line snippet that reuses `get_page`, like the lookback example does.
6. Deletions table: two rows. Touches and conversions are removed when the user is deleted (check the attribution spec's FK `on_delete`). The prune command is out of scope, so say "Older touches may be pruned by the operator" only if that command ships.
7. Referral data intro: change "Four API endpoints" to six.
8. Known data caveats: the existing last bullet says "No conversion uploads" because there are no IP or cookie ids. Reword it so it does not read as contradicting a "conversions" endpoint. Say these conversions are site events for attribution, not ad-platform conversion uploads. This is a real confusion risk to name in the spec.
9. `docs/product/security-and-data-handling.md` update, per the idea.

## Things that would change the spec (summary)

- Name the filter parameters after returned fields, and decide `user` vs `user_id` once (follow signup attributions, with `user_email`).
- State case-sensitivity and empty-value handling for the three code filters. State that unknown parameters either 400 or are documented as ignored, matching child 1.
- Acceptance criteria for error bodies: 400 keyed by parameter, `kind` lists valid values, unknown `user` gives an empty list.
- Required docs content: two-clock definition, a `recorded_via` table, first/last/none table with a worked example, and a `window_days` note.
- Resolve the "No conversion uploads" wording clash in the caveats.
- Check the attribution spec on whether touch ids on a conversion can dangle (pruning) and on the FK deletion behaviour, since both feed the Deletions table.

## References

- Existing house style: `docs/api.md` in this repo.
- Stripe API, pagination and errors (`param` on errors, `created` filters): https://docs.stripe.com/api/pagination and https://docs.stripe.com/api/errors
- Segment spec, `timestamp` vs `receivedAt` (event-time vs ingestion-time): https://segment.com/docs/connections/spec/common/
- DRF filtering and validation error shape: https://www.django-rest-framework.org/api-guide/filtering/
- django-filter choice validation: https://django-filter.readthedocs.io/en/stable/ref/filters.html
- Related brief in the repo: `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`

status: ok · reason: complete
