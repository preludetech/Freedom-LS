# Research: Data-model patterns & reference implementations for referral/campaign/event tracking

Scope: **only** the data-model question — how to shape the tables that record inbound
referral/UTM hits and the subsequent behaviour (page/course views, express interest, apply,
register, signup) of the visitor who arrived on them. Attribution *logic* (which touch gets
credit) is deliberately out of scope — see the separate attribution-models research doc. The
recommendation here assumes **"store all touches, decide attribution at query time."**

## 1. Event stream vs state rows — recommendation

Two rows types cover this cleanly; don't try to force it into one table:

### `ReferralVisit` (a.k.a. Touchpoint) — the inbound hit

One row per observed inbound hit that carries a referral code and/or UTM params (i.e. created
by middleware/view code when the query string contains `?ref=` or `utm_*`, not on every
request). This is the "who/where/when did this traffic arrive" record:

- `code` (nullable `CharField`, indexed) — the external referral/affiliate code from `?ref=`
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` (all nullable
  `CharField`, `utm_campaign` indexed alongside `code`)
- `landing_path` / `landing_url` — first page hit
- `referrer` — HTTP `Referer` header, best-effort
- `anonymous_id` (indexed) — a stable pseudonymous ID minted into a cookie/session on first
  sight, so later touches and later conversions from the same browser can be tied together
  before signup
- `user` — nullable FK to `AUTH_USER_MODEL`, `null=True, blank=True`, back-filled at signup/login
  (see §4)
- `ip_address` (`GenericIPAddressField`, matches the existing `LegalConsent.ip_address`
  convention) and `user_agent` (`TextField`)
- `created_at` (`auto_now_add=True`, indexed) — this *is* the timestamp; no `updated_at`, the row
  never changes after insert
- `site` + `id` (UUID pk) — inherited from `SiteAwareModel`

### `TrackedEvent` (a.k.a. conversion/interaction event) — what the visitor did

One row per observed behaviour (`page_view`, `course_view`, `express_interest`, `apply`,
`register`, `signup`, …), FK'd back to the `ReferralVisit`/session that produced it:

- `event_type` (`CharField` + choices, mirrors the `event_type` string catalog pattern already
  used for webhooks — see §3)
- `visit` — FK to `ReferralVisit` (nullable if you ever want to record organic-traffic events
  too, but for this feature every row will have one, since we only track behaviour *after* a
  referral hit)
- `user` — nullable FK, same back-fill story as `ReferralVisit.user`
- `anonymous_id` — denormalised copy from the visit for cheap querying without a join
- `object_type` / `object_id` (nullable, e.g. `"course"` / course UUID) — lets one table cover
  `course_view`, `express_interest`, `apply`, `register` without a table-per-event-type
- `metadata` — `JSONField(default=dict)` for event-specific extras (keeps the table stable
  across new event types, at the cost of not being able to index inside it — fine for
  store-only-for-now)
- `created_at` (`auto_now_add=True`, indexed)

This is an **append-only, two-table event stream**, not a mutable "state" model (there is no
"current campaign" field on `User` to update-in-place). That matches the product framing
directly: "record what visitors do," not "compute a summary." It also matches the only
append-only precedent already in this codebase, `LegalConsent` (`freedom_ls/accounts/models.py`
lines 189–234): `auto_now_add` timestamp, no `updated_at`, a `save()` guard that raises if
`_state.adding is False` on an existing pk (necessary because `SiteAwareModel` assigns a UUID pk
at construction time, before insert, so `pk is not None` alone can't detect "this is an update").
Reuse that same guard on both new models.

Rejected alternative: a single flat table with nullable "hit-only" columns and event columns
together. It works for pure serial-per-request data but tries to double as both a
low-cardinality dimension (the referral hit: code/UTM/IP/UA, set once) and a high-cardinality
fact (every subsequent action). Splitting them means the hot conversion-event insert path
doesn't have to write IP/UA/UTM strings on every row, and querying "give me all events for this
code" doesn't require re-parsing UTM fields off every event row — it's one join to the visit.

## 2. Reference implementations & prior art

| Project | What it captures | What to borrow |
|---|---|---|
| [`django-utm-tracker`](https://github.com/yunojuno/django-utm-tracker) ([PyPI](https://pypi.org/project/django-utm-tracker/)) | Two-phase middleware: stashes `utm_source/medium/campaign/term/content` + click IDs (`gclid`, `fbclid`, `msclkid`, `aclid`, `twclid`) in `request.session` while anonymous, then persists a `LeadSource` row once the user authenticates. Custom extra tags go in a `JSONField`. | The **session-then-persist** pattern for the anonymous→user gap, and the click-ID field list if UTM param support should extend beyond the 5 standard `utm_*` keys. Also the idea of a `JSONField` "custom tags" bucket instead of adding a column per new tracking param. |
| [`django-reflinks`](https://github.com/HearthSim/django-reflinks) | `ReferralHit` (one row per follow of a referral link — user FK if logged in, else a UUID stashed in a cookie for anonymous) + `ConfirmedReferral` (a thin "this hit converted" marker row referencing the hit, used to trigger point-crediting). | Almost exactly the shape recommended in §1: a **hit table** plus a separate **conversion marker** referencing it, rather than one wide table. Confirms cookie-based anonymous ID as the standard way to bridge anonymous→identified without waiting for signup. |
| `django-referral`, `django-affiliate`, `pinax-referrals`, `django-simple-referrals` (surveyed via [Django Packages referrals grid](https://djangopackages.org/grids/g/referrals/)) | Mostly built around *creating and managing* referral links/codes inside Django (link generation, multi-level trees, crediting). | Not directly reusable — this project deliberately keeps code management on an external system — but confirms the "hit row that a user gets linked back to" shape is the norm across the ecosystem. |
| **GA4 event/BigQuery export** ([GA4 traffic-source attribution reference](https://www.kevinleary.net/blog/google-analytics-attribution-traffic-source/), [BigQuery export reference](https://www.digitalapplied.com/blog/ga4-bigquery-export-2026-marketing-analytics-reference)) | Separates `traffic_source` (user-scoped, first-touch), `collected_traffic_source` (raw, event-scoped — the actual UTM/click-ID params present on *this* event), and `session_traffic_source_last_click` (session-scoped, attribution already applied). | The key lesson: **store the raw per-event/per-touch source data (`collected_traffic_source`) separately from any attributed/summarised source**, and compute attribution views on top rather than baking one attribution choice into the base tables. This directly supports "store all touches, decide attribution later." |
| **Segment `track`/`identify` spec** ([Track spec](https://segment.com/docs/connections/spec/track/), [Identify best practices](https://www.twilio.com/docs/segment/connections/spec/best-practices-identify)) | Every event carries `anonymousId` and/or `userId`; `identify` calls later attach a known `userId` to a previously-anonymous `anonymousId`, and analytics tooling stitches history across the switch. | This is the industry-standard shape for exactly the "anonymous browsing → linked to User at signup" requirement: every row (hit or event) should carry `anonymous_id` from creation, and `user` gets populated later without rewriting the `anonymous_id`. Don't try to migrate/merge anonymous rows into "belonging to" the user by deleting the anonymous marker — keep both, per Segment's approach. |
| **Matomo** ([database schema](https://developer.matomo.org/guides/database-schema), [log-data guide](https://developer.matomo.org/guides/log-data)) | `log_visit` (one row per visit — visitor id, campaign/referrer fields, first/last action time) + `log_link_visit_action` (one row per action within a visit, FK to the visit) + `log_action` (a deduplicated catalog of distinct URLs/page titles referenced by id). | Same visit/action split as recommended, at a *session* grain rather than per-hit. The `log_action` dedup-catalog idea is worth keeping in mind for `object_type`/`object_id` on `TrackedEvent` if page/course-view volume ever needs it, but is not needed at "store only" scale — plain FK/string columns are fine to start. |
| `django-analytical` ([PyPI](https://pypi.org/project/django-analytical/)) | Mostly template-tag glue for embedding third-party trackers (GA, Segment, Matomo, etc.) into pages — it doesn't own a data model itself. | Not a data-model reference; skip. Mentioned only to rule it out, since it's the most commonly-suggested "Django + analytics" package. |

## 3. Hooking existing domain events (grounded in this codebase)

This app already has a clean, established pattern for "something happened, record/notify it":
`fire_webhook_event(event_type, payload)` (`freedom_ls/webhooks/events.py`) plus a flat
`(event_type, label)` catalog in `FLS_WEBHOOK_EVENT_TYPES`
(`freedom_ls/base/webhook_event_types.py`). Existing call sites to hook `TrackedEvent` creation
alongside, without duplicating logic:

- `CourseInterest.save()` (`freedom_ls/course_interest/models.py`) — currently no webhook fired;
  this is the `express_interest` conversion point.
- `CourseApplication.save()` (`freedom_ls/course_applications/models.py`) — currently no webhook
  fired; this is the `apply` conversion point.
- `UserCourseRegistration.save()` (`freedom_ls/student_management/models.py:66-94`) — already
  fires `course.registered` via `fire_webhook_event` on first save (`is_new` guard using
  `self._state.adding`); this is the `register` conversion point — write the `TrackedEvent` row
  from the same `is_new` branch.
- `AccountAdapter.save_user()` (`freedom_ls/accounts/allauth_account_adapter.py:134-154`) —
  already fires `user.registered` on commit; this is the `signup` conversion point, and also
  **the** back-fill trigger for §4 (nullable `user` FK on both `ReferralVisit` and
  `TrackedEvent`).

Recommendation: model `event_type` on `TrackedEvent` as a plain `CharField` with a `choices`
tuple mirroring the `FLS_WEBHOOK_EVENT_TYPES` shape (`referral_hit`, `page_view`, `course_view`,
`express_interest`, `apply`, `register`, `signup`), not as a new webhook-catalog entry — these
are internal tracking rows, not outbound webhook payloads, so they don't need
`validate_event_type()` / the webhook registry. Keep the two concepts (webhook event types,
tracking event types) as separate string catalogs even though the *names* overlap conceptually,
since a "how-to-fire-a-webhook-to-an-external-endpoint" concern is orthogonal to
"record-a-row-for-later-querying." (A later feature could fire a webhook per tracked conversion
too, but that's not requested here — "store only for now.")

All new models subclass `SiteAwareModel` (`freedom_ls/site_aware_models/models.py`) for the UUID
pk + automatic `site` FK, consistent with every other domain model surveyed above
(`CourseInterest`, `CourseApplication`, `UserCourseRegistration`, `LegalConsent`).

## 4. Anonymous → User back-fill

Both `ReferralVisit.user` and `TrackedEvent.user` are `nullable` FKs, populated at signup/login
by the same mechanism as `django-utm-tracker`'s `LeadSourceMiddleware` and Segment's `identify`
call: look up existing rows by `anonymous_id` (from the tracking cookie/session) and
`.update(user=...)` them once the identity is known, rather than moving/copying data. This means:

- `anonymous_id` must be set on **every** row from creation (never backfilled itself) — it's the
  only reliable join key across the anonymous period.
- The `user` FK is a pure enrichment column, filled in later; nothing else about the row
  changes, keeping this compatible with the append-only guard from §1 (an `UPDATE ... SET
  user_id = ...` via `QuerySet.update()` bypasses `save()` entirely, so it doesn't fight the
  `LegalConsent`-style single-writable-field-at-insert guard — but if that guard is copied
  verbatim it will need to tolerate this one legitimate later write, e.g. by using
  `.update(user=...)` rather than `instance.save()` for the back-fill, since bulk `update()`
  already bypasses the custom `save()` per the comment on `LegalConsent`).
- Do the back-fill query once, at `save_user()` (signup) and again at login if anonymous
  browsing can precede login-with-existing-account — confirm which flows are in scope before
  spec time; both hook points already exist (`AccountAdapter.save_user`, allauth's login
  signals) so this is an implementation detail, not a data-model concern.

## 5. Indexing / query / volume considerations

"Store only for now, keep it queryable" implies indexes chosen for the query shapes that will
matter even without a dashboard yet: "show me everything for code X," "show me this user's
journey," "show me this anonymous visitor's journey."

- `ReferralVisit`: index `code`, index `anonymous_id`, index `created_at` (for time-bounded
  exports), index `user` (nullable FK — Django indexes FKs by default). Composite index on
  `(code, created_at)` if "volume for campaign X over time" becomes a common query.
- `TrackedEvent`: index `anonymous_id`, index `user`, index `event_type`, index `created_at`,
  and the FK to `visit` (indexed by default). Composite `(visit, event_type)` if "did this visit
  convert" checks are frequent.
- **Volume split is deliberate and already baked into the two-table design**: `ReferralVisit`
  rows are created only when a referral/UTM param is present on the request — low-to-moderate
  volume, one per (session, code) roughly. `TrackedEvent` rows, if `page_view` is included, can
  be high-volume (every page view from every referred visitor, indefinitely retained with no
  cleanup job yet specified). Two mitigations to weigh at spec time, not decided here:
  - Keep `page_view`/`course_view` as `TrackedEvent` rows but consider whether **every** page
    view needs a row, or only page views on courses (`course_view`), given `page_view` is the
    one type explicitly called out as volume-risky and the others (`express_interest`, `apply`,
    `register`, `signup`) are naturally low-volume (bounded by real conversions).
  - If raw high-volume hits ever need to be separated from low-volume conversions physically
    (e.g. different retention/partitioning), the two-table split already gives a natural
    boundary — `ReferralVisit` (or a possible future `PageViewEvent`) could later move to a
    separate, more aggressively-pruned table without touching the conversion (`express_interest`
    /`apply`/`register`/`signup`) rows in `TrackedEvent`. Not needed for the "store only" phase;
    noted so the two-table shape doesn't get collapsed into one wide table that would make this
    harder later.

## 6. Concrete model sketch

```python
class ReferralVisit(SiteAwareModel):
    """Append-only record of an inbound hit carrying a referral code and/or UTM params."""

    code = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    utm_source = models.CharField(max_length=128, null=True, blank=True)
    utm_medium = models.CharField(max_length=128, null=True, blank=True)
    utm_campaign = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    utm_term = models.CharField(max_length=128, null=True, blank=True)
    utm_content = models.CharField(max_length=128, null=True, blank=True)
    landing_path = models.CharField(max_length=512)
    referrer = models.CharField(max_length=512, null=True, blank=True)
    anonymous_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="referral_visits",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # save() guard mirroring LegalConsent: append-only, no updates except the
    # user back-fill, which should go through .update(user=...) not .save().


class TrackedEvent(SiteAwareModel):
    """Append-only record of one behaviour by a (possibly anonymous) referred visitor."""

    EVENT_TYPE_CHOICES = [
        ("page_view", "Page view"),
        ("course_view", "Course view"),
        ("express_interest", "Expressed interest"),
        ("apply", "Applied"),
        ("register", "Registered"),
        ("signup", "Signed up"),
    ]

    visit = models.ForeignKey(
        ReferralVisit, on_delete=models.CASCADE, related_name="events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, db_index=True)
    anonymous_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tracked_events",
    )
    object_type = models.CharField(max_length=32, null=True, blank=True)
    object_id = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

Both subclass `SiteAwareModel` (UUID pk + auto `site` FK,
`freedom_ls/site_aware_models/models.py`); both get the `LegalConsent`-style append-only
`save()` guard (`freedom_ls/accounts/models.py:222-234`) adapted to permit the one legitimate
`user` back-fill path via `.update()`.

## Open questions for spec time (not resolved here)

- Whether `page_view` (as opposed to `course_view` only) is actually needed given the volume
  note in §5.
- Exact mechanism for minting/persisting `anonymous_id` (cookie vs Django session key) — a
  middleware concern, not a data-model concern, but affects whether `anonymous_id` values are
  stable across browser restarts.
- Whether `TrackedEvent` conversions (`express_interest`/`apply`/`register`/`signup`) should also
  fire an outbound webhook event (extending `FLS_WEBHOOK_EVENT_TYPES`) — explicitly out of scope
  per the "store only for now" product decision, but the model shape doesn't preclude adding it
  later since it would just be an additional `fire_webhook_event()` call at the same hook points
  listed in §3.

status: ok
