# Research: data sources for the lead-monitoring API

Repo root `/home/sheena/workspace/lms/freedom-ls-worktrees/main`. Paths below are relative to it.

## 0. Headline findings

- No DRF in the project yet (`pyproject.toml:39` has `django-import-export`; `rest_framework` appears only at `pyproject.toml:289`, a tool config entry; `config/urls.py:36` has a commented-out `ninja` import). The API needs `djangorestframework` added, an auth scheme, and a URL include. Nothing to reuse.
- No `student_*` apps exist. `learner_management` and `learner_progress` are the only ones. `course_access` is just a backend-selector (`freedom_ls/course_access/__init__.py:16`), no models.
- No soft delete anywhere in these models. Rows are hard-deleted (mostly CASCADE; registrations and progress are PROTECT). An incremental pull cannot see deletions.
- Site isolation: `SiteAwareManager` filters by the *request's* site only when a request is bound to the thread (`freedom_ls/site_aware_models/models.py:118-129`); with no request it returns everything. A token-authenticated API must therefore decide which site it serves (host-based, or a token bound to a site) and must not rely on ambient filtering by accident. `User` has its own `UserManager` with the same behaviour (`freedom_ls/accounts/models.py:26-34`).
- The six existing admin exports are the field list the scripts consume today (section 3). Only `CourseApplication` and `User` came from the `more_lead_admin_exports` spec; referral exports predate it. There is no admin export today for course registrations, course progress, course interest, or form attempts. "Course registrations" and "course progress" are new data for scripts.

## 1. Models per resource

All IDs are UUID (`SiteAwareModel`, `site_aware_models/models.py:166-170`) except `User` (integer pk, `accounts/models.py:79-82`). `TimestampedModel` = `created_at` (auto_now_add) + `updated_at` (auto_now) (`site_aware_models/models.py:173-185`).

| Resource | App.Model (file:line) | Key fields / FKs | Site-aware | Timestamps for "changed since" | Soft delete |
| --- | --- | --- | --- | --- | --- |
| Users | `accounts.User` (`accounts/models.py:78`) | `email` (unique), `first_name`, `last_name`, `is_active`, `is_staff`, `is_superuser`, `last_login`; `site` FK (via `SiteAwareModelBase`, not UUID) | yes, own manager | `created_at`, `updated_at`, `last_login` | no (`is_active` is a flag, not deletion) |
| Email verified | allauth `EmailAddress` | not a project model; `verified`, `email`, `user` | no | none | no |
| Consent | `accounts.LegalConsent` (`:179`) | user FK, `document_type`, `document_version`, `consent_method`, `ip_address`; append-only | yes | `timestamp` only (append-only, so created == changed) | no |
| Authenticated application | `course_applications.CourseApplication` (`course_applications/models.py:84`) | `user` FK (null), `anonymous_applicant` 1:1 (null), `course` FK, `form_progress` 1:1 (null, RESTRICT); properties `is_submitted`, `submitted_time`, `is_email_verified`, `applicant_email`, `applicant_name` (`:158-211`) | yes | `created_at`, `updated_at`; draft to submitted is `form_progress.completed_time` (so a submission does not necessarily bump `CourseApplication.updated_at`) | no |
| Anonymous application | `course_applications.AnonymousApplicant` (`:29`) | `course` FK, `email`, `first_name`, `last_name`, consent evidence (`terms_version`, `consent_ip_address`, `consented_at`), `user` FK (null until claimed), `claimed_at`, `claim_email_sent_at`, `claim_link_version` | yes | `created_at`, `updated_at` | no. Not exported on its own; it appears through `CourseApplication.anonymous_applicant` (done spec `more_lead_admin_exports/1. spec.md:30-32`) |
| Application answers | `form_engine.FormProgress` (`form_engine/models.py:239`), `QuestionAnswer` (`:667`), `QuestionAnswerFile` (`:717`), `FormQuestion` (`:136`), `QuestionOption` (`:218`) | `FormProgress`: `form`, `user` (null for anonymous), `start_time`, `last_updated_time` (auto_now), `completed_time`, `scores` JSON. `QuestionAnswer`: TimestampedModel | yes (FormProgress, answers); Form/Question are content, via `BaseContent` | `FormProgress.last_updated_time`; answers `updated_at` | no |
| Referral links | `referral_tracking.ReferralCode` (`referral_tracking/models.py:158`) | `code`, `label`, `notes`, `destination`, `inactive_destination`, `is_active`, `hit_count`, `last_hit_at` | yes | `created_at` only. **No `updated_at`**: editing `label`/`is_active`/`hit_count` leaves no changed-since signal except `last_hit_at`. A pull must be full-refresh for this table (small) | no. Codes never deleted (admin refuses); `is_active` flag |
| Referral hits | `ReferralCodeHit` (`:233`) | `referral_code` FK (PROTECT), `door` (`go`/`d`), `is_machine_fetch`, no personal data | yes | `hit_at` (append-only, indexed `site,hit_at`) | prunable by command (`prune_referral_code_hits`); count on `ReferralCode.hit_count` does not reconcile with log (`:182-194`) |
| Signup attribution (first touch per user) | `SignupAttribution` (`:45`) | 1:1 `user`; `advert_code`, `referral_code`, `utm_source/medium/campaign/content/term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `landing_path`, `referer`, `raw_query`, `first_seen`, `ga_cookie`, `fbp_cookie`, `fbc_cookie`, `client_ip`, `user_agent`, `signed_up_at` | yes | `signed_up_at` (append-only; save raises on update `:91-103`) | no |
| Daily first-touch tally | `FirstTouchCount` (`:112`) | `day`, attribution key fields, `is_overflow`, `key_hash`, `count`; no personal data | yes | none (`day` only; `count` is mutated in place, no `updated_at`). Re-pull recent days | no |
| Course interest | `course_interest.CourseInterest` (`course_interest/models.py:16`) | `user` FK, `course` FK | yes | `created_at` only. Toggle-off deletes the row (`referral-attribution-over-time/1. spec.md:297-301`), so deletions invisible | hard delete |
| Course registration (individual) | `learner_management.LearnerCourseRegistration` (`learner_management/models.py:239`) | `learner` FK (to `Learner`, which has `user` + `organisation`), `course` FK (PROTECT), `is_active`, `self_registered`, `registered_at` | yes | `registered_at` only. **No `updated_at`**: deactivate/reactivate not detectable by timestamp | no (`is_active`) |
| Course registration (cohort) | `CohortCourseRegistration` (`:277`) | `cohort` FK, `course`, `is_active`, `registered_at` | yes | `registered_at` only | no |
| Learner (user-in-organisation) | `learner_management.Learner` (`:150`) | `user`, `organisation`, `is_active`, `created_at` | yes | `created_at` | no |
| Cohort and membership | `Cohort` (`:129`, Timestamped), `CohortMembership` (`:214`, Timestamped) | membership: `cohort`, `learner` | yes | `created_at`/`updated_at` | no (membership hard-deleted) |
| Rule-made registration flag | `registration_rules.RuleRegistration` (`registration_rules/models.py:103`) | 1:1 `registration`, `rule_name`, `is_retracted`; optional app | yes | none | SET_NULL on rule |
| Organisation | `organisations.Organisation` (`organisations/models.py:63`) | `name`, `slug`, `is_default` | yes | Timestamped | no |
| Course progress | `learner_progress.CourseProgress` (`learner_progress/models.py:106`) | `learner` FK, `course` FK, exactly one of `learner_registration` / `cohort_registration`, `progress_percentage` (int, indexed), `started_at`, `last_accessed_time`, `completed_time`, `last_accessed_item` | yes | `created_at` (= registration date), `started_at`, `last_accessed_time`, `completed_time`. **No `updated_at`**; `last_accessed_time` is written by the player and deliberately not auto_now (`:134-137`), so `progress_percentage` can change (background recalculation) without any timestamp moving | no |
| Topic progress | `TopicProgress` (`:59`) | `course_progress` FK, `collection_item` FK (null), `topic` FK, `start_time`, `last_accessed_time` (auto_now), `complete_time` | yes | `last_accessed_time` is auto_now, so it is a usable changed-since | no |
| Form attempt in a course | `CourseFormAttempt` (`:243`, Timestamped) | `course_progress` FK, `collection_item`, 1:1 `form_progress` (gives `completed_time`, `scores`) | yes | `created_at`/`updated_at`; plus `form_progress.last_updated_time` | no |
| HR attributes | `hr_attributes.LearnerHRAttributes` (`hr_attributes/models.py:145`), `JobTitle`/`Department`/`Location` | per-learner HR data | yes | not read | out of scope (the Users export spec excluded HR attributes, `more_lead_admin_exports/1. spec.md:33-34`) |

Legacy/duplicate apps: none found. `student_*` does not exist. `freedom_ls/learner_*` is the only family. `registration_rules`, `hr_attributes`, `course_recommendations` and `course_access` are optional or infrastructure and not needed for the six requested resources, except `registration_rules.RuleRegistration` if a script wants "registered by a rule".

## 2. What "other referral data" can cover

Existing, already exported from admin (`referral_tracking/admin.py:49,85,119,230` all `SiteAwareExportModelAdmin`):
1. `SignupAttribution`: first-touch attribution per user (UTM, advert code, referral code, click ids gclid/fbclid, landing path, referer, cookies, IP, user agent). Contains personal-ish data (IP, user agent, GA/Meta cookie ids): the API must decide whether to expose it.
2. `FirstTouchCount`: daily denominator for conversion rates (anonymous).
3. `ReferralCodeHit`: hit log per code (anonymous).
4. `ReferralCode` is the "referral links" resource itself.

Related but not currently exported:
5. `CourseInterest`: a lead signal (user + course + `created_at`).
6. Registration `self_registered` flag: separates learner-initiated from staff-made registrations.
7. `AnonymousApplicant` consent evidence (versions, IP, `consented_at`) and claim state (`claimed_at`, `claim_email_sent_at`): funnel state of anonymous leads (applied, emailed, claimed).
8. `LegalConsent` records.

Not yet existing (will arrive with the roadmap items in section 5): `AttributionTouch` timeline and `Conversion` (frozen first/last referral code per signup/application/interest/registration). Marketing channel classification is derived, not stored.

Note on linking leads to attribution: `SignupAttribution` hangs off `user`, and an anonymous application has no user until claimed. So an anonymous application can only be tied to attribution after the claim (`AnonymousApplicant.user`, `claimed_at`). Anonymous applications carry no attribution of their own today.

## 3. Existing admin exports and their columns

Base: `freedom_ls/site_aware_models/admin_exports.py`. `SiteAwareModelResource` excludes `site` (`:90-91`), renders datetimes as ISO 8601 with offset (`IsoDateTimeWidget :43-51`), dates ISO (`:54-58`), booleans `TRUE`/`FALSE` (`:61-72`). `FormulaSafeCSV` escapes formula-trigger cells and headers and prepends a BOM (`:27-40`; `base/csv_safety.py`). The CSV format and BOM are spreadsheet concerns that an API should not carry over; the formula-escaping question needs a decision (JSON consumed by scripts should arguably not be escaped).

Permission model of the exports: gated on the model's Django `view_` permission (`more_lead_admin_exports/1. spec.md:44-47`), site scoped by request.

| Export | Source (file:line) | Columns, in order |
| --- | --- | --- |
| Users | `accounts/resources.py:17-27,30-58` | `id`, `email`, `first_name`, `last_name`, `is_active`, `is_staff`, `email_verified` (Exists on allauth `EmailAddress`, verified and `email__iexact`), `created_at`, `last_login`. Never password, groups, permissions, `is_superuser`. |
| Course applications | `course_applications/resources.py:25-34,37-111`; answers `form_engine/exports.py` | `id`, `applicant_email`, `applicant_name`, `is_email_verified`, `course` (title, not pk), `is_submitted`, `submitted_time`, `created_at`; then one answer column per `FormQuestion` across all forms in the export (keyed by question id; header is question text, suffixed ` (<form title>)` then ` (<n>)` on clash; option text joined with `; `; file upload gives filename only; date/time stored ISO text; blank if unanswered). Includes anonymous and draft rows. Builds all rows in memory in `before_export` (`:73-98`). |
| Signup attribution | `referral_tracking/resources.py:19-24` (no `fields`, so every model field) | `id`, `user` (email), `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `landing_path`, `referer`, `raw_query`, `first_seen`, `ga_cookie`, `fbp_cookie`, `fbc_cookie`, `client_ip`, `user_agent`, `signed_up_at` |
| First-touch counts | `:27-29` | `id`, `day`, `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `is_overflow`, `key_hash`, `count` |
| Referral codes | `:32-34` | `id`, `code`, `label`, `notes`, `destination`, `inactive_destination`, `is_active`, `hit_count`, `last_hit_at`, `created_at` |
| Referral code hits | `:37-44` | `id`, `referral_code` (code text), `door`, `is_machine_fetch`, `hit_at` |

Gaps relative to the idea: no export exists for course registrations, course progress, topic progress, form attempts/scores or course interest. Registration-form answers (`SiteSignupPolicy.additional_registration_forms`), `LegalConsent`, HR attributes and signup attribution in the Users export were explicitly kept out of the Users export (`more_lead_admin_exports/1. spec.md:33-34`).

Export design points that matter for an API:
- Application answers are the only wide/dynamic shape. Choices: (a) nested `answers` array per application (`question_id`, `question_text`, `type`, `value`), which is the natural JSON shape and avoids unstable column names; (b) flat. Recommend nested. The question-id keyed identity (`:48-51` of the done spec) maps directly.
- Course exported as title, not id; an API should expose course id plus title.
- Anonymous applications already tell apart by `anonymous_applicant` / `user` null; `applicant_email`/`applicant_name` are computed properties, so serializers must `select_related("user","anonymous_applicant","course","form_progress")` as the resource does (`course_applications/resources.py:64-71`).

## 4. Progress granularity available

| Level | Model | What it gives |
| --- | --- | --- |
| Course | `CourseProgress` | `progress_percentage`, `started_at`, `last_accessed_time`, `completed_time`, grant (individual or cohort registration), `last_accessed_item`. One row per learner per registration. |
| Topic | `TopicProgress` | per placement (`collection_item`): `start_time`, `last_accessed_time`, `complete_time`. |
| Form attempt | `CourseFormAttempt` -> `FormProgress` | per attempt (retakes allowed, many per placement): `start_time`, `completed_time`, `scores` JSON. Quiz scores are `{"score","max_score"}` (`form_engine/models.py:285-296`); category scored forms nest by category (`:478-540`). `scores` shape varies by scoring strategy, so it must be emitted as raw JSON. |
| Answers | `QuestionAnswer` | per question; heavy and personal. Probably only for applications, not for course attempts. |

Forms can be sat outside a course (no `CourseFormAttempt`); application sittings are such (`form_progress` on `CourseApplication`).

Progress queries need `learner -> user` join for identity: `CourseProgress.learner` is a `Learner` (user + organisation), not a user. Scripts will want `user_id`/`email` and `organisation` flattened.

## 5. Not-done specs that change these models

From `spec_dd/1. next/roadmap.md:656-661`:

| Spec | State | What it adds | Effect on the API |
| --- | --- | --- | --- |
| `referral-attribution-over-time` (`1. spec.md` exists, three new app edges to approve at plan time, `roadmap.md:656`) | next, no dependency | New `AttributionTouch` (`user`, 7 key fields, `landing_path`, `occurred_at`, `recorded_at`, `recorded_via` live/signup_flush/login_flush, `key_hash`; spec `:117-144`) and `Conversion` (`user`, `kind` account_signup/course_application/course_interest/course_registration, generic target, `target_label`, `occurred_at`, `first_touch`/`last_touch`, `first_referral_code`/`last_referral_code`; spec `:146-174`). Admin plus export for both (`:318-338`). `SignupAttribution` unchanged. | This is the real "other referral data" for payouts. A referral API spec should either come after it or reserve a place for it. `Conversion` is the ideal single endpoint for lead/payout monitoring (`target_label` avoids generic FK resolution; spec `:157`, `:334-336`). Both append-only with `occurred_at`/`recorded_at`, so incremental pulls work (use `recorded_at` as the cursor, not `occurred_at`, since flushed touches happen before they are written). |
| `referral-tracking-referer-host-normalisation` | next, none | Helpers: `normalised_host`, `referer_host`. No model. | None directly. Could add a derived `referer_host` field. |
| `referral-tracking-marketing-channels` | next, depends on host normalisation | Pure classifier of a first touch into channel/platform/basis. Settled: "adds no new capture" (`idea.md`). | Derived field on attribution output only if stored or computed in a serializer. Decide whether API exposes it. |
| `referral-tracking-external-referer-first-touch` | next, depends on host normalisation | Opt-in first touch for untagged external-referer visits; must agree with the touch list in `referral-attribution-over-time`. | More `SignupAttribution`/touch rows with only a `referer`; no new fields. |
| `server-side-conversion-tracking` | next, depends on `tracking-pixels` | Outbound conversion events to Meta/TikTok/Google; click ids, tokens. Idea only, no models decided. | No effect on a read API. Does not need to be waited on. |

Also relevant: `course_applications/models.py:84-101` note says application review will add `state`, `submitted_at`, `decided_at`, `decided_by` and a `view_application` permission; `multi-step-course-applications/idea.md` exists in `1. next`. Serializers should expose derived `is_submitted`/`submitted_time` through one property so they follow when `state` lands.

## 6. Size and natural groupings

Distinct read-only resources implied (all list plus detail, or list only):

| # | Resource | Source model(s) | Depends on apps |
| --- | --- | --- | --- |
| 1 | users | `User` (+ allauth `EmailAddress` annotation) | accounts |
| 2 | course applications (user-held and anonymous in one list, with nested answers) | `CourseApplication`, `AnonymousApplicant`, `FormProgress`, `QuestionAnswer` | course_applications, form_engine, content_engine |
| 3 | referral codes | `ReferralCode` | referral_tracking |
| 4 | referral code hits | `ReferralCodeHit` | referral_tracking |
| 5 | signup attributions | `SignupAttribution` | referral_tracking, accounts |
| 6 | first-touch counts | `FirstTouchCount` | referral_tracking |
| 7 | course interests | `CourseInterest` | course_interest |
| 8 | course registrations (individual and cohort, perhaps one merged list with a `source`/`kind`) | `LearnerCourseRegistration`, `CohortCourseRegistration`, plus `Learner`/`Cohort` for identity | learner_management |
| 9 | course progress | `CourseProgress` | learner_progress |
| 10 | topic progress | `TopicProgress` | learner_progress |
| 11 | course form attempts (scores) | `CourseFormAttempt`, `FormProgress` | learner_progress, form_engine |
| later | attribution touches, conversions | new models | referral_tracking (after `referral-attribution-over-time`) |

Roughly 9 to 11 endpoints now, 2 more after attribution-over-time. Items 3-6 are one cluster (a single app, four near-identical flat serializers). Items 8-11 are one cluster (learner_management + learner_progress, shared `learner -> user`/`organisation` flattening). Items 1, 2 and 7 each stand alone.

Suggested cut by user-visible outcome (a script author can ...):

1. API foundation plus users: DRF install, versioned URL prefix, token authentication for non-human clients, permission class tied to the existing `view_*` permissions (matching the admin exports' rule), per-site scoping that works without ambient request, pagination (cursor or keyset on a stable key), `updated_since` filter convention, throttling, OpenAPI schema, test helpers. Ships one real resource (users) so it is demonstrably usable from a Python script. The idea's "secure and accessible from Python scripts" requirement lives here and the decisions are the risky part (token model: DRF `TokenAuthentication` has one token per user, no expiry or scopes; alternatives are a custom hashed-key model bound to a site, or `djangorestframework-simplejwt`/OAuth client-credentials).
2. Course applications (anonymous and authenticated, with answers). Largest single serializer; carries the dynamic answers shape and PII risk (file upload names only).
3. Referral data: codes, hits, signup attribution, first-touch counts. Mirrors the four existing referral exports; mostly flat.
4. Registrations and course interest: leads' enrolment. Needs identity flattening and a decision on individual vs cohort registrations.
5. Progress: course progress, topic progress, form attempts. Needs the changed-since decision because there is no `updated_at` on `CourseProgress`.
6. (After `referral-attribution-over-time`) conversions and touches.

Hazards to carry into the specs:
- Incremental pulls: only `User`, `CourseApplication`, `AnonymousApplicant`, `Cohort`, `CohortMembership`, `Organisation`, `TopicProgress`, `CourseFormAttempt`, `QuestionAnswer`, `FormProgress` have a reliable changed-since field. `ReferralCode`, `CourseInterest`, both registration models and `CourseProgress` do not; either add `updated_at` (migration; `TimestampedModel` is the shared mixin, but `referral_tracking` is deliberately outside `TIMESTAMPED_MODELS` per `referral-attribution-over-time/1. spec.md:142-144`) or define those as full or created-since pulls. This decision should be taken once, in the foundation spec.
- Deletes are invisible to incremental pulls (CourseInterest toggle, memberships, hit pruning).
- `CourseApplication.updated_at` does not move when the sitting is submitted (`FormProgress.completed_time`), so "changed since" for applications needs `max(updated_at, form_progress.last_updated_time)` or a documented rule.
- PII: `SignupAttribution` has `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie`; `AnonymousApplicant` has `consent_ip_address`. The admin exports expose these to anyone with the view permission; the API decision (include, omit, or separate permission) should be explicit. Existing doc to update: `docs/product/security-and-data-handling.md` (named in the done spec `:179-181`).
- Query shape: copy `filter_export` prefetches (`course_applications/resources.py:61-71`) into the view's queryset, and pin query counts with `django_assert_num_queries`, as the admin export tests do.
- Do not reimplement formula-escaping, BOM or TRUE/FALSE: those are CSV concerns, not JSON.
- CLAUDE.md rules apply: no `Any`, type hints, no ABCs unless asked, `app_name` in each `urls.py`, kebab-case URL paths, snake_case names; and `claude_plugins/django-stack` stays generic (a generic DRF helper would need project values via config only).

status: ok · reason: complete; DRF absent from project, no student_* apps, no soft delete found
