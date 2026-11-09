# Research: best practices for extensions and pause

Topic `best_practices`. Builds on the landscape file (b, c) and sentiment file (b, c, implications 2, 3, 5, 7, 8); those are not repeated. Source note: findings come from established documentation and well-known patterns; URLs were not re-fetched in this run, so treat the quotes-free summaries as recall of those pages.

## Findings first

1. **Store pause and extension records; derive the shift at read time. Do not keep an accumulated shift field as the source of truth.** An optional cached total is fine, but the records win.
2. **Two models, one shared shift shape.** `Pause` (start, planned_resume, ended_at, reason, actor, status) and `DeadlineExtension` (scope, days or to-date, reason, actor). Each yields "whole days to add to a target". The resolver sums them. One model for both would force nullable columns that mean different things.
3. **A pause's effective end is `min(ended_at, planned_resume)` when read.** An open pause with no planned resume runs to "now" for display but is not counted in a shift until it ends (the clock is stopped, nothing opens anyway). A planned end in the past is treated as ended at that instant.
4. **Round the pause up to whole days once, per pause, from its effective end.** Never round the sum. Add days to the local calendar date in the site timezone, not 24h multiples.
5. **Extensions stack, each row immutable, with revoke as a new state rather than delete.** Express "to this date" by converting to N days at grant time, and store both the request and the computed days.
6. **Due and close move together in a single write path** (one function, one transaction), and the resolver derives close from due plus grace, so they cannot disagree.
7. **Webhooks: past-tense `resource.verb`, thin-but-useful payload, a stable event id, and a persisted "fired" marker so a lazy transition fires exactly once.**
8. **Admin: intermediate-confirmation action with a form (reason required), whole thing in `transaction.atomic`, the row lock on the learner's registration.**
9. **Tests: freeze time with time-machine or freezegun, test each boundary at the instant, one second either side, and across DST.**

## 1. Modelling pauses

**Event records vs accumulated field.** Event sourcing (Fowler, https://martinfowler.com/eaaDev/EventSourcing.html) keeps every change as a record and derives state. For an audit-heavy staff action this is the right fit: the reason, actor and dates survive, a mistaken resume can be voided, and the resolver stays a pure function of records plus base dates. An accumulated `shift_days` integer on the registration is simple and fast but loses who/why, cannot be corrected, and drifts if two writes race. If read cost matters, cache the sum on the registration and recompute from records on any change; never edit the cache by hand.

**Shift computation (pure function).** For a target date `d` (unmet deadline or time-limit end):
`effective(d) = d + sum(days(p) for p in pauses that ended, where p.ended_at >= ... )` plus extensions, applied in chronological order of grant so "on top of the current effective date" is literal. Decide the rule for a pause relative to a deadline: only pauses that ended count, and only for deadlines unmet at that time. "Met" is a fact at resume time, so either (a) freeze the set of shifted deadlines on the resume record (a snapshot of which targets moved), or (b) derive from "unmet at resume instant" using completion timestamps. Option (b) is derivable but fragile if completion is later undone; option (a) is explicit. Flag as a spec decision; (b) avoids storing per-target rows, (a) is safer for audit.

**Open pause.** Model status as a derived value: `open` (no end, or planned_resume in the future), `ended` (explicit resume or planned_resume passed). Explicit resume sets `ended_at = now` and `ended_by`; if a planned resume already passed, `ended_at` defaults to the planned instant, not now (the learner should not lose the days between planned resume and the staff clicking resume late). Enforce at most one open pause per registration with a partial unique constraint on `(registration)` where `ended_at IS NULL`, plus the read-time rule for a passed plan (query for "open" must apply the planned-resume check, so a passed plan counts as ended; creating a new pause must treat it so as well).

**Idempotency of resume.** Resume is a state transition guarded by the lock: `select_for_update` the pause (or registration), if already ended return the existing record without a second shift and without a second event. The analogue is Stripe's idempotent requests (https://docs.stripe.com/api/idempotent_requests). Double click and a planned resume racing a staff resume both resolve to one ended record. Because a derived shift is a function of records, a second resume cannot double-shift; this is the main correctness argument for records over a field.

**Clock and timezone pitfalls** (https://docs.djangoproject.com/en/stable/topics/i18n/timezones/):
- Store instants as aware UTC datetimes; store deadline "dates" as dates, interpreted in the site timezone.
- Pause duration in days: compute `ceil((end - start) / 1 day)` on elapsed seconds, or on local calendar days? Both give "3d 5h to 4 days" for normal days, but a DST change makes a 3d 5h local pause 3d 4h or 3d 6h of elapsed time. Pick one and test it. Recommend: compute from elapsed seconds against 86400 with `ceil`, since the learner-facing promise is "time paused"; add the resulting integer to the calendar date (`date + timedelta(days=n)`), which is DST-safe because it never touches wall-clock time.
- For datetime deadlines (date plus time), shift in local time: convert to site tz, add days to the naive local date/time, localize again (zoneinfo handles the fold). Adding `timedelta(days=n)` to an aware zoneinfo datetime keeps wall time; adding hours would not. Ambiguous or non-existent local times (02:30 on the gap day) need a stated rule.
- A site's timezone changing later would move "end of day"; store the zone used or accept that dates are zone-relative.
- Zero-length pause: ceil(0) = 0 days; decide if a sub-day pause counts as 1 day (answers say rounded up, so any positive duration is at least 1 day; a pause started and ended within seconds is positive, so 1 day, unless the spec exempts it).

## 2. Extension records

- **Stacking:** one row per grant, never overwritten. LearnDash-style replace loses history and surprises staff (sentiment file). Effective date = base + pauses + extensions applied in grant order.
- **Audit trail:** actor, reason, created_at, scope, requested value, computed days, optional `revoked_at/by/reason`. Soft-revoke, no hard delete. Django's own admin LogEntry (https://docs.djangoproject.com/en/stable/ref/contrib/admin/#logentry-objects) records the staff action but not the domain meaning, so keep the domain row.
- **"N more days" vs "to this date" in one record:** two input modes, one stored shape. Columns: `mode` (`days` | `to_date`), `days` (always the effective delta, computed), `requested_date` (nullable, only for to_date). For `to_date`, compute `days = target - current_effective(date)` at grant time and store it; later pauses then shift on top without re-deriving. Reject a to-date earlier than or equal to current effective date (non-positive delta), or allow negative only if shortening is wanted (the idea says extend; don't build shortening).
- **Scope:** single deadline (FK to the deadline target), time limit, or whole course (all unmet deadlines plus time limit). Whole course is the pause maths with a given N; implement as one row with scope `course`, resolved like a resume with the same unmet-at-grant rule, or as fan-out rows in one transaction. A single course-scope row is easier to audit and revoke; fan-out gives per-item history. Spec decision.
- **Due and close move together:** store only a due delta; derive close as due-effective plus the policy grace window, so no row can move one without the other. If close is independently overridable (spec 1), the extension service must write both in the same transaction and a model `clean()`/DB check should assert `close >= due`. Add a test that no resolver output has `overdue and open` or `closed and not overdue` inconsistency.

## 3. Subscription-pause patterns

- **Stripe** pauses collection with a behavior (`keep_as_draft`, `mark_uncollectible`, `void`) and an optional `resumes_at` timestamp (https://docs.stripe.com/billing/subscriptions/pause-payment). The model: pause = a record on the subscription, resume date optional, lazily honoured by the billing engine. Billing period does not slide automatically, which is the opposite of FLS (the clock shifts); the useful part is `resumes_at` as a first-class optional field.
- **Gym and consumer subscriptions** (typical published terms): limited pause count per year, a maximum length per pause (often 1 to 3 months), a minimum notice, a reason (medical, travel) sometimes with proof, the end date extended by the paused time, and at the limit the pause is refused and the member must cancel or contact staff. Some auto-resume at the max length (the planned end is capped, not the pause refused).
- **Spotify and Netflix**: Spotify offers no pause for Premium (account downgrades); Netflix has no pause either, only cancel with the account kept for ten months. They show the other pattern: keep the data, drop the entitlement. Relevant to "past results stay visible".
- **Take-aways for FLS:** capture reason from a short list plus free text; planned resume optional; limits (count, max length) are policy settings that bind self-service only (matches the idea); at a limit self-service is refused with a clear message and staff can override; a max-length cap on a pause with no planned resume could be handled lazily as an implicit planned resume (`start + max_days`), evaluated at read.

## 4. Webhooks

Conventions from Stripe (https://docs.stripe.com/webhooks), GitHub (https://docs.github.com/en/webhooks) and Standard Webhooks (https://www.standardwebhooks.com/):
- **Names:** `resource.verb` in past tense, e.g. `course.paused`, `course.resumed`, `deadline.extended`. Keep verbs consistent with existing events (`course.unregistered`); check the existing event list for naming. Do not put the cause in the name; put it in the payload (`trigger: staff | planned | learner`).
- **Payload:** event id (stable, unique), event name, occurred_at (ISO 8601 UTC), the existing convention ids (user, organisation, learner, course), the record id, `actor` (user id or `null` for automatic), `reason`, and before/after of the changed values: for pause `started_at`, `planned_resume`, `ended_at`, `shift_days`; for extension `scope`, `deadline`, `days`, `previous_effective`, `new_effective`. Include before/after so consumers need not call back; keep payloads small and tolerate additive change.
- **Lazy transitions:** with no sweep, nothing observes a planned resume passing. Options: (1) fire the event the first time the transition is observed on read (side effect on GET, risky, racy); (2) leave to spec 5's sweep, which the idea already assigns; (3) fire from the sweep and also when a staff action observes it. Recommended: reads never fire. Mark the transition in a nullable `resume_event_sent_at` column and let the sweep (and any write path that touches the pause) claim it with a conditional update (`UPDATE ... SET resume_event_sent_at=now WHERE id=? AND resume_event_sent_at IS NULL`), firing only if one row changed. The event's `occurred_at` is the planned instant, with a separate `delivered/detected_at`, so late firing is honest.
- **Duplicates:** consumers must dedupe on event id; producers fire `transaction.on_commit` so a rolled-back action sends nothing and a committed one sends once; the claim column prevents double fire across processes. Give the admin test button sample payloads that mirror real ones and flag them as test (`livemode`-style flag or a `test: true`).

## 5. Admin UX

Django pattern (https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/): an action that returns an `HttpResponse`/render of an intermediate template when the form is not yet confirmed, posts back with `action`, `_selected_action` and `post` markers, validates a `forms.Form` (reason required, days/to-date, optional planned resume), then applies and `message_user`. Alternatives for a single learner: a custom admin view on the change page (`get_urls`, wrapped with `admin_site.admin_view`) with a `ModelAdmin`-style form, which is cleaner than a list action when the target is one registration.
- Show a preview before confirming: old effective date, new effective date, and count of affected deadlines (dry-run of the same service function).
- Require reason; record actor from `request.user`; check permission with `has_change_permission`/a custom permission, not just staff.
- **No half-applied state:** the whole action calls one service function inside `transaction.atomic()`, locks the registration with `select_for_update`, writes the record and any derived rows, and defers notification and webhook to `transaction.on_commit`. Any exception rolls back everything; messages are sent after the commit. Admin changelist actions are not atomic by default per object; `ModelAdmin.changeform_view` is wrapped in a transaction but custom actions and views are not, so wrap explicitly (https://docs.djangoproject.com/en/stable/topics/db/transactions/).
- Bulk selection of registrations in one action should be all-or-nothing, or report per-row results explicitly; the idea keeps cross-learner bulk in spec 6, so limit to one learner here.

## 6. Testing time-based logic

- Use time-machine (https://github.com/adamchainz/time-machine, fast, handles C-level `datetime`) or freezegun (https://github.com/spulec/freezegun); pick whichever the repo already uses and check pytest fixtures. `tick=False` for deterministic assertions; move time inside tests to simulate the read-time evaluation.
- Boundary cases: pause started and resumed in the same second; planned resume exactly now, one second before, one second after; open pause with no plan; explicit resume after planned resume passed (end = planned); double resume; pause shifted exactly 24h (1 day) and 24h+1s (2 days); pause spanning a DST start and end in the site timezone; deadline at end of day and a deadline in the DST gap hour; month and year rollover, leap day; two stacked extensions plus a pause in either order; extension to a date equal to or before the current effective date; whole-course shift with some met and some unmet deadlines; revoked extension.
- Property: effective dates never decrease from a pause; `close >= due`; resolver purity (same records, same output at the same instant).
- Test webhooks and notifications with `django_capture_on_commit_callbacks` (https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.captureOnCommitCallbacks) and assert exactly one fire; a test for the claim column under a simulated race.

## Decisions for the spec (flagged)

- Two models vs one: recommended two.
- Snapshot of shifted targets on the resume record vs derive from "unmet at resume".
- Whole-course extension as a single scoped row vs fan-out.
- Rounding basis: elapsed seconds vs local calendar days.
- Whether reads may ever fire events: recommended never.

## Sources
- https://martinfowler.com/eaaDev/EventSourcing.html
- https://docs.stripe.com/billing/subscriptions/pause-payment
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/api/idempotent_requests
- https://www.standardwebhooks.com/
- https://docs.github.com/en/webhooks
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/actions/
- https://docs.djangoproject.com/en/stable/topics/db/transactions/
- https://docs.djangoproject.com/en/stable/topics/i18n/timezones/
- https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.TestCase.captureOnCommitCallbacks
- https://github.com/adamchainz/time-machine
- https://github.com/spulec/freezegun

status: ok · reason: written from established documentation and patterns; URLs not re-fetched this run
