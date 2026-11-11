# Research: what the existing codebase touches, reuses and conflicts with

Scope: verify `idea.md` against current code; report drift, reuse, conflicts. The sibling files
`research_existing_referral_tracking.md`, `research_attributable_events.md` and `answers.md` were read
and are not repeated; where this file confirms or corrects them it says so.

## 1. Drift in `idea.md` references (verified against the current tree)

| idea.md says | Now | Impact |
| --- | --- | --- |
| `_start_application` at `course_applications/views.py:32-49`; takes `(course, user)` and creates on `get_or_create` | Now `views.py:84-120`, signature `_start_application(course, *, user=None, anonymous_applicant=None)`. It has **three callers**: `:168` (signed-in `apply`), `:459` and `:629` (both `anonymous_applicant=`). The `get_or_create` `_, created` result is discarded (`:103`) and followed by `select_for_update` + form-progress creation. | The "created branch" hook needs the `created` flag surfaced (today `app, _ =`). Two of three callers have **no user** (see 2.1). |
| `initiate_course_access` uses `update_or_create` at `learner_interface/views.py:864-868` | Now `views.py:1033-1101`. No `update_or_create` there. It calls `self_register(request.user, organisation, course)` (`learner_management/learner_actions.py:348-368`) which returns `bool` (`change == "registration.added"`), and then `record_course_self_registered(request, course)` on `created` (`:1093-1097`). | The registration row is not in scope at the view; `self_register` returns only a bool. Hook would need the row (or the call placed inside `_ensure_registration`, `learner_actions.py:~330-345`, which does get_or_create then reactivation). Reactivation is still not "created", so the idea's rule survives; its cited mechanism does not. |
| `partial_express_interest` at `course_interest/views.py:58`, `deferred_express_interest` at `:116` call `get_or_create` | Both go through a shared helper `_express_interest(request, course)` (`views.py:28-33`): `get_or_create(...)` then `if created: record_interest_expressed(request, course)`. Views are at `:37` and `:111`. Delete-and-recreate is at `:101` (not `:89`). | One call site, not two. Natural home beside `record_interest_expressed`. |
| `CourseInterest` toggle delete at `:89` | `:101` | cosmetic |
| `mock_site_context` at `freedom_ls/conftest.py:135-174` | `conftest.py:231` (`site` fixture at `:198`, `site_aware_request` at `:291`) | cosmetic |
| `referral_tracking` depends on `accounts`, `base`, `site_aware_models` only; "gains none" | `docs/app_structure.md:223-226,335` shows `referral_tracking --> accounts, api, base, site_aware_models`. The `api` edge came from `referral_tracking/api.py` (shipped by `apis-for-lead-monitoring-3-referral-data`). Also `accounts -.-> referral_tracking` is a test-only edge (`:255`, from `accounts/tests/test_admin.py:16-17`). | The success criterion "shows `referral_tracking` still depending on `accounts`, `base` and `site_aware_models`, and nothing else" is already false. Also the GFK argument ("exactly this dependency set") is now off by `api`. |
| `role_based_permissions/models.py:90-95`, `:91`, `:117` for `ObjectRoleAssignment` | Class at `:83`; `object_id = CharField(max_length=255)` at `:95`; `target` GFK `:96`; the `(content_type, object_id, role, is_active)` index at `:118` (not `(content_type, object_id)`). | Pattern still valid; the "index per precedent" claim should say precedent indexes the 4-tuple, not the pair. |
| Receiver `record_attribution_on_signup` `signals.py:21`; best-effort `signals.py:28-41`; `apps.py:10-14` | Confirmed exact. | none |
| `models.py:53` OneToOne, `:91-103` guard, `CAPS`, `ATTRIBUTION_KEY_FIELDS` | Confirmed (`:52`, `:91-103`). | none |
| `middleware.py:81-82`, `:51-52`; `capture.py:198-212`, `:57-70`, `:74-87`; `codes.py:64-74`; `counters.attribution_key_hash` | All confirmed. | none |
| Tests `test_middleware.py:65-78 / 81-88 / 143-155 / 243-256`, `test_capture.py:174-181 / 264-279`, `test_models.py:26-33`, `test_admin.py:94-105` | Names confirmed; lines moved by 1-15 (`test_middleware.py:66,79,143,244`; `test_models.py:27`; `test_admin.py:79`). Note the signup tests are in `test_signals.py` and `test_signup.py` is not in the glob listing; research file cited `test_signup.py` which does not exist -- the equivalent is `tests/test_signals.py`. | Use names, not line numbers, in the spec. |
| `docs/product/referral-codes.md` "that the referral-codes work owes" | **Exists now** (`docs/product/referral-codes.md`). | The doc task changes: update/link it, do not write it. `signup-attribution.md`'s stale "Partner referral codes" Not-Built line should be re-checked. |
| `spec_dd/1. next/apis-for-lead-monitoring-6-conversions/idea.md:51` points at `spec_dd/1. next/referral-attribution-over-time/1. spec.md` | The spec now lives under `2. in progress/`. | Reverse pointer to fix when this lands. |

## 2. Conflicts and unconsidered interactions

### 2.1 Anonymous applications (biggest gap in the idea)
`anonymous-course-applications` has shipped. `CourseApplication.user` is nullable, with an
`anonymous_applicant` alternative; `_start_application` is called with no user from `:459` and `:629`.
A `Conversion` requires a `user` FK, so an anonymous application cannot convert at start. It is attached
later: `claims.attach_claimed_application` (`claims.py:211-267`) and `attach_to_user`
(`:318-339`, sets `application.user`), and `course_applications/receivers.py:149`
`adopt_anonymous_applications_on_login` (a `user_logged_in` receiver). The idea's decision "an
application converts when it is started" has no answer for these: `created_at` is the anonymous start,
touches exist only in the cookie (not yet rows), and the account may not exist. Decide: convert at
claim/attach (with `occurred_at=created_at`), or skip anonymous applications.

### 2.2 `claims.py:262` fires `user_signed_up` itself
For an unclaimed-owner claim, `claims.py:258-262` calls `user_signed_up.send(sender=User, request=request, user=user)`
"so the attribution receiver keeps its best-effort handling". So `record_attribution_on_signup` already
runs on a claim, with the claiming request's cookie. The new signup flush and `account_signup`
conversion will fire there too, with `signed_up_at` = now. Also `announce_user_registered` is separate.

### 2.3 Second `user_logged_in` receiver
`course_applications/receivers.py:149` already receives `user_logged_in` (django.contrib.auth). Receiver
order is not guaranteed; if a conversion is recorded in an anonymous-application adopt at login (2.1),
the touch flush from the new `referral_tracking` login receiver must run first. Not an issue if the
conversion is deferred out of the receiver.

### 2.4 Existing analytics hooks sit at the same four sites
`course_access/analytics_events.py:44-57`: `record_interest_expressed`, `record_application_submitted`,
`record_course_self_registered`. Interest and self-registration already fire exactly once, on `created`
(`course_interest/views.py:31-33`; `learner_interface/views.py:1096-1097`). `record_application_submitted`
fires at `course_applications/views.py:171, 466, 834`, i.e. on **submission** (`:834` is the check-answers
completion path), not on start. That is the opposite choice to the idea's "converts when started"; both
exist in the same view module, so the spec must say why they differ. These helpers import only
`base.analytics_events` and `course_access`; a `referral_tracking` call is an alternate precedent for
"the one call at created".
Webhook precedent: `fire_webhook_event` (`user.registered` from `accounts/allauth_account_adapter.py:~135`,
`course.registered` from `learner_progress/signals.py`). `CourseApplication` and `CourseInterest` fire no
webhook.

### 2.5 The word "conversion" is already taken
- `freedom_ls/google_tag/google_ads.py:1-49`, `context_processors.py:23-29`, `tests/test_google_ads.py`:
  "Google Ads conversion tracking": `parse_conversion_labels`, `conversion_send_to`, setting
  `GOOGLE_ADS_CONVERSION_ID`, `GOOGLE_ADS_CONVERSION_LABELS`. A conversion there is an ad-platform
  event mapped from an analytics event name.
- `spec_dd/1. next/server-side-conversion-tracking/idea.md`: "FLS's conversion events" sent to Meta CAPI,
  TikTok Events API, Google Measurement Protocol. Mentions moments away from the browser "such as staff
  and cohort registrations", which this spec deliberately excludes. It also says
  `referral_tracking` "already captures some [click IDs]" -- the new touch deliberately drops click
  identifiers (`gclid`, `fbclid`...), so server-side conversion tracking cannot read them from
  `AttributionTouch`; they stay only on `SignupAttribution`.
- `spec_dd/1. next/apis-for-lead-monitoring-6-conversions/idea.md` adopts `Conversion` / "conversions" as
  the referral-attribution model. Settled there: `recorded_at` as the cursor, `target_label` returned,
  no `content_type`/`object_id`, `key_hash` withheld, explicit field list, filters on user,
  `referral_code`, `kind`, first/last code. Compatible with the idea's model; two requirements to carry
  back: `AttributionTouch` and `Conversion` need `recorded_at` indexed (idea indexes `occurred_at`, and
  `(site, kind, occurred_at)`, but not `recorded_at`), and the API's cursor `(recorded_at, id)` wants an
  index on `(site, recorded_at)`. Also note API 3 serializers use `updated_since` mapped to the append
  time (`api.py:123-141`, `signed_up_at`), which is the pattern to extend.
- The idea's terminology table says "nothing in FLS uses it [Conversion]" -- **false** (Google Ads
  conversions, `GOOGLE_ADS_CONVERSION_ID`). A model named `Conversion` in `referral_tracking` alongside
  `google_tag` conversions is a vocabulary collision to resolve (rename to e.g. `AttributedMoment`, or
  document the distinction). The model's `kind` values (`account_signup`, `course_application`,
  `course_interest`, `course_registration`) also differ from `AnalyticsEvent` names
  (`COURSE_ACCESS_REQUESTED`, `COURSE_REGISTERED`) and webhook types (`user.registered`,
  `course.registered`, `course.completed`; `base/webhook_event_types.py`), so a fourth vocabulary.

### 2.6 Other `1. next` specs touching the same code
- `referral-tracking-external-referer-first-touch`: explicitly "must agree with
  `referral-attribution-over-time`". It mints a touch on an **untagged** GET, which breaks the idea's
  invariants "a landing with no tracked parameter is never recorded, the timeline holds no direct touches"
  and middleware `has_tracked_params` early return (`middleware.py:51-52`). Answers.md settles that this
  spec ships only tagged touches and leaves the field/cookie key to that spec; the cookie list entry
  schema must therefore be extensible (`_is_first_touch_payload` rule "dict values all `str`, keys in
  `COOKIE_KEYS.values()`" is the extension point). Also the idea's `touches_in_play` ignores touches
  with a blank `referral_code`, so external-referer touches would never be "in play" -- consistent but
  worth a sentence.
- `referral-tracking-referer-host-normalisation`: pure helpers on stored Referer. `AttributionTouch`
  stores no referer, so no overlap; only the external-referer spec needs it.
- `referral-tracking-marketing-channels`: classifier over `SignupAttribution`; "adds no new capture".
  No conflict; it could later classify `AttributionTouch` rows (same UTM fields).
- `cookie-banner`: one sentence idea; says nothing about what is gated. Open question in this idea
  ("consent gate overdue") has a candidate sibling but cookie-banner is an informational banner, not a
  consent gate; it does not block the `fls_attribution` set.
- `roadmap.md:229,238-239`: confirms in-progress status, the three-edge approval, and the consent gate
  gap.

### 2.7 Tests that the idea says are replaced -- all confirmed
`test_middleware.py` `test_second_tracked_get_in_the_same_client_leaves_the_cookie_byte_identical`
(`:66`), `..._leaves_the_tally_at_one` (`:79`), `test_a_tracked_get_with_an_existing_valid_cookie_costs_no_query`
(`:143`), `test_a_visitor_holding_the_cookie_is_logged_as_a_hit_and_keeps_the_first_touch` (`:244`). Also
at risk but not listed in the idea: `test_a_tracked_get_with_an_existing_valid_cookie_sets_no_cookie` and
`..._carries_vary_cookie` (the "no Set-Cookie on cookie holder" assertion contradicts append), and the
signup-count tests `test_signup_and_confirmation_together_leave_exactly_one_row` (flush now writes more
rows; `SignupAttribution` stays one, so likely fine). The signal tests live in `tests/test_signals.py`.

### 2.8 Account erasure
`accounts/admin.py:26` `USER_ERASURE_CASCADE_MODELS` is a set that each app adds its user-owning models
to (`referral_tracking/admin.py:81` adds `SignupAttribution`; `course_applications/admin.py:29-30`;
`learner_management/admin.py:279`). The idea adds `AttributionTouch` and `Conversion` with
`on_delete=CASCADE` but does not register them, so the erasure-confirmation page would omit them. Also
`course_applications/receivers.py:130-146` erases unclaimed applicants on user pre_delete; the
Conversion for an erased account vanishes with it, but a `PROTECT` touch FK held by a cascaded
Conversion is fine (both in the same delete collection), worth a test.

## 3. Reuse already in the repo

- `SiteAwareModel`, `get_cached_site`, `SiteAwareExportModelAdmin`/`SiteAwareModelResource`
  (`site_aware_models/admin_exports.py`), `_readonly_field_names`, `SignupAttributionAdmin` shape
  (`admin.py:48-78`), `SignupAttributionResource` `ForeignKeyWidget` email (`resources.py:19-24`).
- Best-effort wrapper: `signals.py:42-47` and `hits.py:64-65` (`transaction.atomic()` + `except
  DatabaseError` + `sentry_sdk.capture_exception`). `record_hit` already does exactly this; a shared
  helper would remove a third copy (CLAUDE.md "avoid repeating code").
- Prune command: `management/commands/prune_referral_code_hits.py` (djclick, `PRUNE_BATCH_SIZE=1000`).
- Config: `AppSettings`/`Setting` in `config.py` (six settings, not four: `HIT_LOG_LIMIT=30`,
  `HIT_LOG_WINDOW_SECONDS=3600` were added after the sibling research was written). Check module has
  only `E001` (`checks.py`); `W001` is free.
- `counters.attribution_key_hash`, `first_touch_from_request`, `lookup_referral_code`.
- Middleware ordering (`config/settings_base.py:171-182`): Session, Auth, CurrentSite, then
  `AttributionCaptureMiddleware`, so `request.user` is resolvable after the view and the live-touch path
  is feasible.
- Existing receiver wiring: `apps.py:10-14` imports `checks` and `signals`; a new `user_logged_in`
  receiver in `signals.py` is connected automatically.
- GFK `ObjectRoleAssignment` precedent is real; target models are `CourseApplication`, `CourseInterest`,
  `LearnerCourseRegistration` (per `learner_management/models.py:109-130`) and `User`.

## 4. Smaller points

- `capture.py` imports `CAPS, SignupAttribution` from `models.py`; `models.py` imports
  `codes.validate_site_path`; `conversions.py`/`resolution.py` as new modules should keep that import
  direction (models cannot import capture).
- `COOKIE_KEYS["utm_term"] = "t"` already exists (`capture.py:43`); the idea's new key `"touches": "t"`
  **collides** with `utm_term`'s short key `t`. `_is_first_touch_payload` requires all keys in
  `COOKIE_KEYS.values()` and all values `str`; `t` is both a valid str-valued key (utm_term) and the
  proposed list key. Needs another short key (e.g. `"ls"`).
- `read_attribution_cookie` returns `{name: payload.get(short, "") for name, short in COOKIE_KEYS.items()}`,
  a `dict[str, str]`; adding a list value breaks that return type (`No Any`, type hints required) and
  `record_signup_attribution` does `**frozen` on it (`capture.py:231-241`), so a list key would be spread
  into `SignupAttribution.objects.create` unless popped. Needs a typed shape (TypedDict or separate
  accessor).
- `set_signed_cookie` is called with no `path`/`domain`; `response.delete_cookie` must match (idea
  already says so). `max_age` shrinking is feasible: Django `read` enforces `max_age` on the timestamp of
  the **signature**, not on `first_seen`. A re-set cookie gets a fresh signature timestamp, so
  `get_signed_cookie(max_age=_cookie_max_age())` would accept it for up to 90 days from the re-set,
  even though the browser expiry is shorter. The idea's non-rolling expiry only holds for the browser
  `Expires`; server-side acceptance rolls unless `read_attribution_cookie` also checks `first_seen`.
- `FirstTouchCount.count` help text and `docs/product/signup-attribution.md` describe "first touch
  minted"; `test_a_landing_whose_cookie_cannot_fit_mints_no_tally` (`test_middleware.py:~190`) still
  governs the mint path.
- `api.py` registers read-only viewsets for the four existing models under `ApiScope.REFERRAL_DATA`;
  API child 6 depends on this spec, so it is a downstream consumer (see 2.5).

status: ok
