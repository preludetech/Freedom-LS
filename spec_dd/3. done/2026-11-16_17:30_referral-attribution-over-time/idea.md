# Spec: referral attribution over time

## Purpose

Attribution is captured once, at account signup. `SignupAttribution` is a `OneToOneField` on the user
(`freedom_ls/referral_tracking/models.py:53`), written by the `user_signed_up` receiver from a cookie
frozen on the visitor's first tracked landing. A second landing changes nothing: `_site_to_mint_for`
returns `None` the moment a valid cookie exists (`middleware.py:81-82`), so the cookie, the tally and
the eventual row all describe one instant that may be months before anything happened.

That is enough to say an account came from a code. It is not enough to pay anyone. A person who
arrived through one partner's code, came back weeks later through another's, and then applied for a
course looks identical to a person who arrived once and never came back. A partner who converted an
already-aware visitor is invisible, and a second course applied for a year later carries the same
attribution as the first.

Referral payouts are coming. This work records **a timeline of touches per person**, and freezes
which codes were in play at each learner-initiated course sign-up, so the question "which referral
code was in play when this person applied for this course" has a recorded answer rather than a
reconstruction.

## Terminology

| Term | Status | Meaning / source |
| --- | --- | --- |
| `AttributionTouch` | coined | One tracked landing recorded against one account. The existing app already calls a tracked landing a "touch" (`FirstTouchCount`, `first_touch_from_request`, `docs/product/signup-attribution.md`); this is that touch, kept per person and in order, rather than tallied. |
| `Conversion` | coined | One moment worth attributing: an account signup, or a learner-initiated course application, expression of interest or self-registration. The industry word, and nothing in FLS uses it. |
| **in play** | coined | Of a referral code at an instant: carried by an `AttributionTouch` for that user, on that site, at or before the instant, and no older than the attribution window. |
| **live touch** | coined | A touch recorded straight to a row because the visitor was authenticated when it happened, as against one carried in the cookie and flushed later. |

"Registration" stays the FLS word for course access. A `Conversion` is not a registration; it is the
record of what was in play when one happened.

## Scope

**In.** A per-user `AttributionTouch` timeline, fed by three paths: the cookie flushed at signup, the
cookie flushed at login, and live writes while authenticated. A cookie that carries a bounded list of
touches rather than only the first. A `Conversion` row per attributable moment, holding the first and
last codes in play, frozen. Hooks in the three learner-initiated sign-up paths. Read-only admin and
CSV export over both models. A prune command for unreferenced touches.

**Out.** Any payout, commission, money or partner-facing anything. No `Organisation` link on
`ReferralCode`, no partner login, no rate or currency: this work records who was in play, and stops
there. A dashboard or conversion-rate view. The two admin lists and their export are the whole
interface, as they already are for signup attribution. A consent gate for the tracking cookie, which
this work makes more necessary and still does not ship (see [Open questions](#open-questions)).
Changing `SignupAttribution`, which keeps its shape, its append-only guard and its read-only admin.
Attributing staff-created registrations and cohort memberships.

## Decisions

- **The timeline is the capture; the frozen pair is the payout record.** Every touch is kept as its
  own row, and each `Conversion` additionally freezes the first and last code in play at that
  instant. Both, because they answer different questions and neither can be recovered from the other
  later: raw touches let a future rule be re-run over history, and the frozen pair means a figure
  someone has already been paid on never silently moves when retention prunes a touch or a rule
  changes.

- **No credit rule is baked in.** A `Conversion` records `first_referral_code` and
  `last_referral_code` side by side and picks no winner. Whoever runs a payout chooses, explicitly,
  in the query they write. Last-click-wins is the affiliate convention and first-click-wins is the
  deliberate alternative; committing to one here would put a policy nobody has set yet into a column
  nobody can change afterwards.

- **A code in play is only ever a referral code.** `first_touch` and `last_touch` on a `Conversion`
  are the earliest and latest touch **carrying a non-blank `referral_code`**, not the earliest and
  latest touch of any kind. A UTM-only landing is still recorded as a touch and is still queryable,
  but it does not displace a partner from a payout. Because a landing with no tracked parameter at
  all is never recorded, the timeline holds no direct touches and "last non-direct" needs no separate
  rule.

- **Only learner-initiated moments convert.** A course application, an expression of interest, and a
  self-service course registration are moments the person acted. An admin registering a learner or
  adding them to a cohort is staff work, and `registered_at` on such a row records when staff acted;
  attributing it would credit a partner for a decision made in the admin months later.

- **A reactivation mints no second `Conversion`.** `initiate_course_access` uses `update_or_create`
  (`freedom_ls/learner_interface/views.py:864-868`) and `registered_at` is `auto_now_add`, so a
  learner re-entering a course an admin had deactivated moves no timestamp and creates no row. The
  conversion is recorded on creation only. The alternative, a second conversion per reactivation,
  would credit a partner twice for one course.

- **An application converts when it is started, not when it is submitted.** `_start_application`
  (`freedom_ls/course_applications/views.py:32-49`) is where the learner acted on the referral; for a
  form-gated course the sitting may be completed weeks later, under touches that had nothing to do
  with the decision to apply. `CourseApplication.created_at` is the conversion's `occurred_at`.

- **`referral_tracking` gains no dependency.** It keeps its `accounts`, `base`, `site_aware_models`
  edges. The three sign-up apps call into it instead, the way every app already calls
  `fire_webhook_event`, and a `Conversion` points at its target through a `GenericForeignKey` so
  nothing is imported back. This is the `ObjectRoleAssignment` pattern
  (`freedom_ls/role_based_permissions/models.py:90-95`), which points at a `Course` from an app with
  exactly this dependency set. Three new edges, named in [Documentation and
  downstream](#documentation-and-downstream), all pointing product app → infrastructure app.

- **A conversion holds code text, not a foreign key to `ReferralCode`.** The shipped decision, kept:
  a hand-typed `?ref=` that matches no row is a real thing that happened and has to be recordable.
  Matching text to a row is `lookup_referral_code(site, code)` (`codes.py:64-74`), which is already
  case-insensitive and site-scoped; a payout query calls it rather than reading a column.

- **The cookie carries the first touch unchanged, plus a list.** The frozen first-touch keys keep
  their current short names and meanings, so a cookie minted before this ships still reads, the way
  `test_a_pre_upgrade_cookie_without_rc_reads_with_a_blank_referral_code`
  (`tests/test_capture.py:264-279`) already establishes. The list is a new optional key.

- **A repeat landing does not extend the cookie's life.** Re-setting it with a full `max_age` would
  turn a 90-day window into a rolling one that never closes for an active visitor. `max_age` is
  recomputed from the frozen `first_seen` each time, so the cookie still dies 90 days after the first
  touch.

- **A subsequent touch tallies nothing.** `FirstTouchCount` counts first touches and is the
  denominator of a conversion rate; incrementing it per repeat landing would corrupt every figure
  already recorded. `increment_first_touch` is reached only on the minting path, as now.

## Requirements

### 1. `AttributionTouch` (`freedom_ls/referral_tracking/models.py`)

A `SiteAwareModel`, append-only, holding no personal data beyond the account it names. No IP, no
user agent, no referer, no raw query string. Those stay a signup-only concern on `SignupAttribution`.

| Field | Type | Note |
| --- | --- | --- |
| `user` | `FK(AUTH_USER_MODEL, on_delete=CASCADE, related_name="attribution_touches")` | Goes with the account, as `SignupAttribution` does. |
| `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` | `CharField(blank=True, max_length=CAPS[...])` | The seven `ATTRIBUTION_KEY_FIELDS`, reusing the existing `CAPS` entries. |
| `landing_path` | `CharField(blank=True, max_length=CAPS["landing_path"])` | Blank on a touch the cookie carried as a list entry. See Requirement 3. |
| `occurred_at` | `DateTimeField(db_index=True)` | When the landing happened, **not** `auto_now_add`: a flushed touch happened before the flush. |
| `recorded_at` | `DateTimeField(auto_now_add=True)` | When the row was written. |
| `recorded_via` | `CharField(max_length=16, choices=TouchSource)` | `live`, `signup_flush` or `login_flush`. What a reader needs to judge how trustworthy the ordering is. |
| `key_hash` | `CharField(max_length=64)` | `counters.attribution_key_hash(*ATTRIBUTION_KEY_FIELDS values)`, reused as-is. Exists to make the row idempotent. |

`Meta`: `UniqueConstraint(fields=["site", "user", "occurred_at", "key_hash"],
name="unique_attribution_touch")`, so a flush that runs twice, signup then login in the same browser,
writes each touch once. `Index(fields=["site", "user", "occurred_at"])` for the resolver.
`Index(fields=["site", "referral_code"])` for the payout query. `ordering = ["-occurred_at"]`.

`save()` carries the same append-only guard as `SignupAttribution` (`models.py:91-103`), verbatim in
shape: raise `ValueError` when `self.pk is not None and self._state.adding is False`, with the same
comment about `_state.adding` and the same note that `QuerySet.update()` bypasses it and the admin is
the second layer.

`TouchSource` is a `models.TextChoices` beside `Door`. The model stays out of `TIMESTAMPED_MODELS`
(`freedom_ls/contrib/conformance/tests/test_timestamped_models.py:28`), like every other model in this
app: it carries domain-meaningful timestamps and a generic pair would invite the wrong one to be read.

### 2. `Conversion` (`freedom_ls/referral_tracking/models.py`)

A `SiteAwareModel`, append-only by the same guard.

| Field | Type | Note |
| --- | --- | --- |
| `user` | `FK(AUTH_USER_MODEL, on_delete=CASCADE, related_name="referral_conversions")` | |
| `kind` | `CharField(max_length=32, choices=ConversionKind)` | `account_signup`, `course_application`, `course_interest`, `course_registration`. |
| `content_type` | `FK(ContentType, on_delete=CASCADE, null=True, blank=True)` | |
| `object_id` | `CharField(max_length=255, blank=True)` | `CharField`, not `UUIDField`, following `ObjectRoleAssignment` (`role_based_permissions/models.py:91`): the targets are four models this app cannot import and must not assume a pk type for. |
| `target` | `GenericForeignKey("content_type", "object_id")` | |
| `target_label` | `CharField(max_length=255, blank=True)` | Frozen at write time: the course title, or the account's email for a signup. The export and the admin list read this and resolve no generic FK, and it survives the target being deleted. |
| `occurred_at` | `DateTimeField(db_index=True)` | Supplied by the caller. |
| `recorded_at` | `DateTimeField(auto_now_add=True)` | |
| `first_touch` | `FK(AttributionTouch, on_delete=PROTECT, null=True, blank=True, related_name="conversions_as_first")` | |
| `last_touch` | `FK(AttributionTouch, on_delete=PROTECT, null=True, blank=True, related_name="conversions_as_last")` | |
| `first_referral_code` | `CharField(blank=True, max_length=CAPS["referral_code"])` | Frozen copy. |
| `last_referral_code` | `CharField(blank=True, max_length=CAPS["referral_code"])` | Frozen copy. |

`PROTECT` on both touch FKs is what makes the frozen pair durable: a touch a payout rests on cannot be
pruned out from under it.

`Meta`: `UniqueConstraint(fields=["site", "kind", "content_type", "object_id"],
name="unique_conversion_per_target")`, so a caller that fires twice records once.
`Index(fields=["content_type", "object_id"])`, per the `ObjectRoleAssignment` precedent
(`role_based_permissions/models.py:117`). `Index(fields=["site", "kind", "occurred_at"])`.
`ordering = ["-occurred_at"]`.

Both codes blank means nothing was in play. That is a recorded answer, not a gap.

### 3. Cookie changes (`freedom_ls/referral_tracking/capture.py`)

**The payload gains one optional key.** `COOKIE_KEYS` gains `"touches": "t"`. Its value is a list of
compact touch dicts, each holding only the seven `ATTRIBUTION_KEY_FIELDS` under their existing short
keys plus `ts`. No `landing_path`, no referer, no raw query, no click identifiers. The frozen
first-touch keys are untouched, so an existing cookie reads exactly as it does today with an empty
list.

**`_is_first_touch_payload` (`capture.py:198-212`) has to stop requiring every value to be a `str`.**
It keeps that rule for every key except `t`, which must be a list of dicts whose keys are all in
`COOKIE_KEYS.values()`, whose values are all `str`, and each of whose `ts` parses with
`datetime.fromisoformat`. Anything else fails the whole payload, which is treated as absent, as now.

**`append_touch(payload, request) -> dict`** builds the compact touch from the request and appends it,
except when its seven key values are identical to the last entry's, or, when the list is empty, to
the frozen first touch. Following the same link twice grows nothing. The list is capped at
`config.REFERRAL_TRACKING_MAX_COOKIE_TOUCHES`; at the cap the **oldest** entry is evicted, so the
first touch and the most recent touch are the two that always survive.

**`set_attribution_cookie` gains a second eviction stage.** Today it sheds non-key fields in
`COOKIE_DROP_ORDER` until the payload fits `COOKIE_MAX_ENCODED_LENGTH` (`capture.py:57-70`). That
cascade runs first, unchanged. If the payload still does not fit, entries of `t` are dropped
oldest-first until it does, never dropping the newest. If a payload holding the frozen first touch and
one touch still does not fit, the function returns `False` and sets nothing, as it does today.

**A `max_age` that does not roll.** `set_attribution_cookie` takes the frozen `first_seen` and sets
`max_age = _cookie_max_age() - (now - first_seen).total_seconds()`, floored at zero; a payload with no
`first_seen` yet (the minting call) gets the full `_cookie_max_age()`. Re-setting the cookie on a
repeat landing therefore never pushes its expiry past 90 days from the first touch.

**Clearing.** `request_cookie_clear(request)` and `is_cookie_clear_requested(request)`, a request-flag
pair shaped exactly like `suppress_capture`/`is_capture_suppressed` (`capture.py:74-87`). The receivers
in Requirement 5 set the flag; the middleware acts on it.

### 4. Middleware changes (`freedom_ls/referral_tracking/middleware.py`)

`AttributionCaptureMiddleware.__call__` keeps its shape. It still reads the first touch off the
request before the view runs, and still writes nothing until the view has returned. It gains three
behaviours.

1. **Honour the clear flag on any request.** The `request.method != "GET" or not
   has_tracked_params(request)` early return (`middleware.py:51-52`) has to run `get_response` and then
   check `is_capture_suppressed`/`is_cookie_clear_requested` before returning, because the signup POST
   and the login POST are neither GETs nor tracked. When the flag is set, `response.delete_cookie(...)`
   with the same name and path the cookie was set under.

2. **An authenticated tracked GET writes a row, not a cookie.** After `get_response` returns, if
   `request.user.is_authenticated`, write one `AttributionTouch` with `recorded_via=live` and
   `occurred_at=timezone.now()`, through the same best-effort wrapper as Requirement 5, and leave the
   cookie alone. `request.user` is read only after the view has returned and only on a tracked GET, so
   an untracked request still resolves no session.

3. **An anonymous tracked GET with a cookie already present appends to it.** Today this path returns
   having done nothing (`middleware.py:81-82`). It now reads the payload, calls `append_touch`, and
   re-sets the cookie. It still mints no `FirstTouchCount` row and issues no query. The first-touch
   branch, where no cookie is present, is unchanged: mint, then tally.

`Vary: Cookie` and the `private, no-store` cache-control on a cookie-setting response apply exactly as
they do now, and now cover the append path too, which also sets a cookie.

### 5. Writing touches and conversions (`freedom_ls/referral_tracking/conversions.py`, new)

Three entry points, all best-effort in the established shape: wrap in `transaction.atomic()` so a
failed insert cannot poison the caller's transaction, catch `DatabaseError`, report it with
`sentry_sdk.capture_exception` and return `None`. Attribution must never be what stops someone
applying for a course, exactly as it must never be what stops a signup (`signals.py:28-41`).

**`record_live_touch(*, request, user, site) -> AttributionTouch | None`** writes one touch from the
request's tracked parameters with `recorded_via=live` and `occurred_at=timezone.now()`, reusing
`first_touch_from_request` for the field values and `attribution_key_hash` for `key_hash`. This is
what the middleware calls for an authenticated visitor.

**`flush_cookie_touches(*, request, user, source) -> list[AttributionTouch]`** reads the attribution
cookie, and writes one `AttributionTouch` per entry: the frozen first touch at its `first_seen`, then
each `t` entry at its `ts`, all with the given `recorded_via`. `get_or_create` against the unique
constraint, so a touch already flushed is not rewritten. It then calls `request_cookie_clear(request)`.
Once the touches are rows against an account the browser copy has done its job, and leaving it would
re-flush the same touches to the next person to sign up on a shared device.

**`record_conversion(*, user, kind, target, occurred_at, target_label) -> Conversion | None`** resolves
the pair and writes the row. Resolution lives in **`referral_tracking/resolution.py`** as
`touches_in_play(*, user, site, when) -> tuple[AttributionTouch | None, AttributionTouch | None]`:
`AttributionTouch` rows for that user and site, `referral_code` non-blank, `occurred_at <= when` and
`occurred_at >= when - config.REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS`, earliest and latest. Both
`None` when nothing qualifies. `record_conversion` uses `get_or_create` on the unique key so a caller
that fires twice is harmless, and copies each resolved touch's `referral_code` into the frozen column.

A caller passes the site implicitly, because these run inside a request, so `SiteAwareModel`'s
ambient site applies. `touches_in_play` takes `site` explicitly anyway, so a shell script or a future
background job can call it without a request.

### 6. The four call sites

Each fires once, on creation only, and each is one call with no error handling of its own. The
best-effort wrapper is inside `record_conversion`.

- **Account signup.** `record_attribution_on_signup` (`freedom_ls/referral_tracking/signals.py:21`)
  additionally calls `flush_cookie_touches(source=signup_flush)` and then `record_conversion` with
  `kind=account_signup`, `target=user`, `occurred_at=attribution.signed_up_at`,
  `target_label=user.email`. The flush runs **before** the conversion so the touches it needs exist.
  `SignupAttribution` is still written first and is unchanged; the first touch is deliberately
  recorded in both places, because the two rows answer different questions and neither is derivable
  from the other.

- **Login.** A new receiver on `django.contrib.auth.signals.user_logged_in`, in the same module,
  connected from the same `ready()` (`apps.py:10-14`). Calls `flush_cookie_touches(source=login_flush)`
  and nothing else. This is what catches an existing account that followed a partner's link and then
  logged in to apply.

- **Course application.** `_start_application` (`freedom_ls/course_applications/views.py:32-49`), on
  the `created` branch of its `get_or_create`: `kind=course_application`, `target=app`,
  `occurred_at=app.created_at`, `target_label=course.title`.

- **Interest and self-registration.** `partial_express_interest`
  (`freedom_ls/course_interest/views.py:58`) and `deferred_express_interest` (`:116`), on `created`
  only, with `kind=course_interest`, `target=interest`, `occurred_at=interest.created_at` and
  `target_label=course.title`. `initiate_course_access`
  (`freedom_ls/learner_interface/views.py:864-868`), on the `created` branch of its
  `update_or_create`, with `kind=course_registration`, `target=registration`,
  `occurred_at=registration.registered_at` and `target_label=course.title`.

A `CourseInterest` row is deleted and recreated when a learner toggles interest off and on
(`course_interest/views.py:89`). Its `Conversion` is not deleted with it, and the new row gets its own.
Two conversions then name the same person and course at two different moments, one pointing at an
object that no longer exists, and both are true records of something that happened. `target_label`
keeps the orphan readable.

### 7. Settings and checks (`freedom_ls/referral_tracking/config.py`, `checks.py`)

| Setting | Default | Governs |
| --- | --- | --- |
| `REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS` | `90` | How far back `touches_in_play` looks. Matches the cookie's life, so a touch that reached a row through the cookie is never already out of window. The affiliate convention is 30 days and the common range is 30 to 90; 90 keeps the two windows the same number, which is the property worth having. |
| `REFERRAL_TRACKING_MAX_COOKIE_TOUCHES` | `10` | Entries in the cookie's `t` list before the oldest is evicted. |

Both declared with defaults in `declared_settings`, neither `required`, so no downstream environment
change is needed.

`checks.py` gains `freedom_ls_referral_tracking.W001`: a warning when
`REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS` is less than `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS`,
because touches flushed at signup would then be recorded and immediately invisible to every
conversion.

### 8. Admin and export (`freedom_ls/referral_tracking/admin.py`, `resources.py`)

Both new admins are `SiteAwareExportModelAdmin`, fully read-only, with `has_add_permission`,
`has_change_permission` and `has_delete_permission` all `False`, and
`readonly_fields = _readonly_field_names(...)`, matching `SignupAttributionAdmin`
(`admin.py:45-77`). Each gets an `AttributionTouchResource` / `ConversionResource`
subclassing `SiteAwareModelResource`, with `user` exported by email through `ForeignKeyWidget`
as `SignupAttributionResource` already does (`resources.py:19-21`).

- `AttributionTouchAdmin`: `date_hierarchy = "occurred_at"`; `list_display` of user, referral code,
  advert code, UTM source, UTM campaign, `occurred_at`, `recorded_via`; `list_filter` on
  `recorded_via`, `utm_source`, `utm_campaign`; `search_fields` on `user__email`, `referral_code`,
  `advert_code`, `utm_campaign`; `list_select_related = ["user"]`.
- `ConversionAdmin`: `date_hierarchy = "occurred_at"`; `list_display` of user, kind, `target_label`,
  `first_referral_code`, `last_referral_code`, `occurred_at`; `list_filter` on `kind`,
  `first_referral_code`, `last_referral_code`; `search_fields` on `user__email`, `target_label`,
  `first_referral_code`, `last_referral_code`; `list_select_related = ["user"]`. No column resolves
  `target`, so a changelist page costs no per-row content-type query.

Filtering `ConversionAdmin` by a referral code and exporting is the payout list. That is the whole
interface this work ships.

### 9. `prune_attribution_touches` (management command)

A `djclick` command shaped on `prune_referral_code_hits`: `--older-than-days N` with
`click.IntRange(min=1)`, deleting across every site in primary-key batches of `PRUNE_BATCH_SIZE`,
printing the total. It deletes only touches no `Conversion` references, through
`.filter(conversions_as_first__isnull=True, conversions_as_last__isnull=True)`, so a touch a payout
rests on is never a candidate, rather than relying on `PROTECT` to raise. Say that in the docstring:
the `PROTECT` is the guarantee and the filter is what keeps the command from tripping over it.

## Testing

The app's existing fixtures carry this: `mock_site_context` (`freedom_ls/conftest.py:135-174`) for
anything touching a `SiteAwareModel`, and `django_assert_num_queries` for the query-count pins.

**Tests that must be replaced, not added to.** Three currently assert the behaviour this work
supersedes, and each asserts equality rather than a bound, so they fail rather than drift:

- `test_second_tracked_get_in_the_same_client_leaves_the_cookie_byte_identical`
  (`tests/test_middleware.py:65-78`) becomes its opposite: a second tracked GET carrying a *different*
  attribution key changes the cookie and appends one entry; one carrying the *same* key still leaves
  it byte-identical.
- `test_a_tracked_get_with_an_existing_valid_cookie_costs_no_query`
  (`tests/test_middleware.py:143-155`) keeps its zero-query assertion for an anonymous visitor, which
  is still the contract, and gains an authenticated sibling that pins the bounded query count of a
  live touch write.
- `test_a_visitor_holding_the_cookie_is_logged_as_a_hit_and_keeps_the_first_touch`
  (`tests/test_middleware.py:243-256`) keeps the frozen first touch and now also expects an appended
  entry.

`..._leaves_the_tally_at_one` (`tests/test_middleware.py:81-88`) is unchanged and becomes load-bearing:
it is what proves a repeat landing still tallies nothing.

**The cookie.** A pre-upgrade cookie with no `t` key reads with an empty list, in the shape of
`test_a_pre_upgrade_cookie_without_rc_reads_with_a_blank_referral_code`. A `t` holding anything but a
list of string-valued dicts fails validation and the whole cookie is treated as absent. Following the
same link twice appends nothing. Following a second link appends one entry. Past
`REFERRAL_TRACKING_MAX_COOKIE_TOUCHES` the oldest entry goes and the newest stays. The multibyte
worst case still fits 4096 bytes with a full list. That test succeeds
`test_a_multibyte_worst_case_cookie_fits_the_browser_limit` (`tests/test_capture.py:174-181`), and it
is the one test keeping this feature inside the browser's hard limit. A payload that cannot fit even with
one touch sets no cookie and mints no tally. Re-setting on a repeat landing never yields an expiry
later than 90 days after `first_seen`, and a cookie whose first touch is already 90 days old is
re-set with a `max_age` of zero rather than a negative one.

**Flushing.** A signup after three tracked landings writes three touches, in order, with
`recorded_via=signup_flush` and the original landing times rather than the signup time. The cookie is
deleted on the signup response. Signing up and then logging in writes each touch once, which is the
unique constraint doing its job. A login with no cookie writes nothing and fails nothing. A signup
with no cookie writes no touches and a conversion with both codes blank.

**Resolution.** With touches at T-60, T-30 and T-1 carrying codes A, B and C, a conversion at T
freezes A and C. A touch after the conversion is ignored. A touch older than the window is ignored,
including for `first_referral_code`, so a conversion outside the window of every touch freezes
nothing rather than reaching past it. A UTM-only touch between two coded ones changes neither code. A
touch belonging to another site, or another user, is never in play.

**Conversions.** Each of the four call sites writes exactly one row with the right `kind`, `target`,
`occurred_at` and `target_label`. Calling a site's path twice writes one row. A reactivating
`initiate_course_access` writes none. An application started before its form is completed converts at
`created_at`, and completing the form later adds nothing. A `DatabaseError` writing a conversion leaves
the application, interest or registration committed and the request successful. That guard keeps
attribution from breaking the product, and it is tested per call site.

**Append-only.** Saving an existing `AttributionTouch` or `Conversion` raises, and the admin change
view persists no modification, in the shape of `test_updating_an_existing_signup_attribution_raises`
(`tests/test_models.py:26-33`) and `test_signup_attribution_change_does_not_persist_modification`
(`tests/test_admin.py:94-105`).

**Pruning.** A touch older than the cutoff and referenced by no conversion is deleted; one referenced
as `first_touch` or as `last_touch` is not; deleting a referenced touch directly raises
`ProtectedError`.

**Admin and export.** Both changelists load, both exports omit `site` and export `user` as an email,
and both 403 without the view permission, in the shape of `tests/test_exports.py:190-198`. A
`ConversionAdmin` changelist page resolves no generic FK, pinned with `django_assert_num_queries`.

**Config.** One assertion per new default, plus the relationship the check enforces: the attribution
window is at least the cookie's life. In the style of `tests/test_config.py`.

## Documentation and downstream

- **Three new edges in `docs/app_structure.md`**, to be approved before code is written, per that
  file's own rule: `course_applications -> referral_tracking`, `course_interest -> referral_tracking`,
  `learner_interface -> referral_tracking`. `referral_tracking` gains none. Regenerate with
  `/ds:app_map`.
- `docs/product/signup-attribution.md` is now a section of a larger story rather than the whole of it.
  Its summary, "How It Works" and "What Is Recorded" sections all state the first-touch-only behaviour
  that this work ends, and its "Not Built" list still names "Partner referral codes", already stale
  since referral codes shipped. It needs rewriting alongside the `docs/product/referral-codes.md` that
  the referral-codes work owes.
- Its **Privacy Obligations** section needs extending, not just updating. A per-person timeline that
  grows for the life of an account is a materially larger footprint under data minimisation and
  storage limitation than one frozen row, and the UK ICO's April 2026 tracking guidance names
  affiliate attribution specifically as a purpose that is *not* strictly necessary and therefore needs
  consent. The **Retention** section has to say that touches are prunable and conversions are not.
- `docs/product/configuration-and-extension.md` gains the two new settings.
- `upgrade_notes.md` for the branch: run `migrate` for two new models; note that existing accounts have
  an empty timeline and their first conversions will freeze nothing, which is expected and not a bug;
  note that cookies already in browsers keep working and start accumulating touches on their next
  tracked landing.

## Open questions

- **A consent gate is now overdue.** FLS still sets the tracking cookie on any tracked landing
  regardless of what the visitor has agreed to. This work does not change that and does not ship one,
  and the ICO's 2026 guidance puts affiliate attribution squarely on the consent-required side, with
  PECR fines now at £17.5m or 4% of turnover. An operator running this in the UK or EU needs an
  answer before it goes live; FLS needs a spec of its own.
- **How long a touch is kept.** `prune_attribution_touches` takes the number as an argument and FLS
  ships no schedule, so today the answer is "forever unless an operator runs it". No regulator gives a
  figure for an attribution timeline specifically; the nearest benchmark is the ~13-month
  analytics-cookie guidance, which is about cookie lifetime rather than database retention. Someone
  has to set a default and defend it.
- **Whether a partner should ever see any of this.** Everything here is admin-only. A partner-facing
  view, and the `ReferralCode`-to-`Organisation` link it would need, were both deliberately left out
  of the referral-codes work and are still out.
- **Self-referral.** Nothing stops a partner using their own code on their own account, and this work
  makes that worth doing for the first time. Detection is out of scope; program terms are not a
  technical control.

## Success criteria

- A person who lands through code A, returns three weeks later through code B, signs up, and applies
  for a course has three rows: two touches and one conversion freezing A as first and B as last.
- An existing account that follows a partner's link, logs in, and expresses interest produces a
  conversion naming that partner's code, with no signup involved.
- Filtering `ConversionAdmin` by a referral code and exporting gives one CSV row per attributable
  moment that code was in play for, with no query written.
- `prune_attribution_touches --older-than-days 400` deletes touches and changes no `Conversion`'s
  frozen codes.
- A `DatabaseError` in attribution leaves the application, the interest and the registration committed
  and the learner's request successful.
- A visitor following the same link twice grows the cookie by nothing and the `FirstTouchCount` tally
  by nothing.
- A cookie whose every tracked value is at its cap in multi-byte characters, carrying a full touch
  list, still fits 4096 bytes.
- `docs/app_structure.md` shows `referral_tracking` still depending on `accounts`, `base` and
  `site_aware_models`, and nothing else.
