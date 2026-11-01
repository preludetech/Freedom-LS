# Research: codebase impact of the deadline consequence policy

Question: what in the existing FLS codebase does `deadlines-2-consequence-policy` touch, reuse or
conflict with? Facts from the tree at HEAD of this worktree (spec 1 is merged). Paths relative to the
repo root. Project words follow `.claude/sdd/config.md` vocabulary: model and field names as in code.

## 0. Headline findings

1. **Spec 1 is done and merged** (`spec_dd/3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue/`).
   The idea's "two lock paths today" no longer exist: spec 1 deleted `is_item_locked_by_deadline`,
   `_apply_deadline_locking`, `DEADLINES_ACTIVE` and `learner_management/deadline_utils.py`. Nothing
   locks on a deadline now. Spec 2 builds the one closing decision fresh, onto read paths spec 1 left.
2. **Spec 1 shows "Missed deadline" unconditionally** in four places that spec 2's "mark overdue"
   switch must reach (section 3.5).
3. **`form_start` and `form_fill_page` build their course index without deadlines** (they pass
   `course_progress` only to `_blocked_item_redirect`). A closed-item decision read from the index
   would not reach them unless they pass `course_deadlines` too (section 4).
4. **The results page and `form_submit_and_exit` both call `_course_access_redirect`**, so ending
   access through `CourseAccessDecision.can_access_content` would turn them away, against the idea's
   "results pages stay ungated". `course_finish` has no access gate at all (section 4).
5. **Best home app: `freedom_ls/deadlines`** (spec 1 decision 1: "Specs 2 to 7 add to it"). Needs one
   new dependency edge, `deadlines -> organisations` (section 9).

## 1. Spec 1, as built (names that spec 2 reads)

App `freedom_ls/deadlines` (label `freedom_ls_deadlines`, in `INSTALLED_APPS` at
`config/settings_base.py:126`). Files: `models.py`, `resolver.py`, `queries.py`, `admin.py`,
`signals.py`, `factories.py`, `templatetags/deadline_tags.py`, migrations `0001_initial`,
`0002_learnerdeadlineoverride`. There is **no `config.py`, no `checks.py`, no loader** in it yet.

- Content defaults (spec 1 Content loading): `ContentCollectionItem.due_date` (`DateField`),
  `due_time` (`TimeField`), `due_days_after_registration` (`PositiveIntegerField`), all nullable
  (`content_engine/models/courses.py:569-571`); `Course.time_limit_days` (`PositiveIntegerField`,
  null, `courses.py:241`); `Course.display_time_limit()`.
- Overrides (`deadlines/models.py`): `CohortDeadlineOverride` (FK `cohort_registration` to
  `CohortCourseRegistration`, `related_name="deadline_overrides"`) and `LearnerDeadlineOverride` (FK
  `course_progress` to `CourseProgress`, `related_name="deadline_overrides"`). Both carry
  `collection_item` (null means the course time limit), `kind` (`DeadlineKind`: `fixed`, `relative`,
  `none`), `due_date`, `due_time`, `due_days_after_registration`, `replaced_value`, `set_by`, `reason`.
  Conditional `UniqueConstraint`s per (layer FK, item) and per layer FK for the time limit. There is
  **no per-individual-registration override**: the learner layer keys on `CourseProgress`.
- Resolver (`deadlines/resolver.py`): `DeadlineSource` (`content`, `cohort_registration`, `learner`),
  `DeadlineValue`, `DeadlineLayer`, `ResolvedDeadline(due_at, source)`, `NO_DEADLINE`,
  `due_instant(...)`, `resolve_deadline(layers, registration_date, tz)`, `is_overdue(resolved,
  completed, now)` (`now > due_at`), `registration_date_of(course_progress, tz)` (date part of
  `CourseProgress.created_at` in the site zone), `CourseDeadlines(items, time_limit)`,
  `course_deadlines(course_progress)`, `course_deadlines_for(records)` (constant query count; reads
  the site zone once from `records[0].site`).
- Site zone: `site_aware_models/time_zones.py` (`site_time_zone`, `site_zone_text`,
  `shows_time_zone_to_learners`), model `SiteTimeZoneConfig` (one row per site).
- Display: `local_time` tag in `deadlines/templatetags/deadline_tags.py`; "Deadline" / "Missed
  deadline" wording (never "Due"/"Overdue"); `<c-chip variant="error">Missed deadline</c-chip>`.
- Admin: inlines appended to `CohortCourseRegistrationAdmin.inlines` and `CourseProgressAdmin.inlines`
  from `deadlines/admin.py` (the lower apps never import `deadlines`); `DeadlineOverrideFormSet`
  stamps `set_by` and `replaced_value`; read-only "Effective deadlines" on `CourseProgressAdmin`.
- Signal: `content_engine.signals.collection_items_synced`, received by
  `deadlines/signals.py::carry_over_deadline_overrides`.
- The override record answers part of the "grace window interacts with an override" question: it
  holds `kind`, the date fields, `set_by`, `reason`, `replaced_value`. It has **no concept of an
  extension, a grace window or a closed/ended state**. An override simply replaces the `due_at`
  that `resolve_deadline` returns, and a grace window computed as `due_at + grace` follows it.
- Leftover from spec 1 relevant here: a fixed date earlier than registration still applies (spec 1
  decision 7), so an item can be overdue, and with a zero grace window closed, from day one.
- The old Hard/soft split is gone: there is no `is_hard_deadline`. Spec 2 does not inherit "hard"
  as a per-deadline flag; closing is a policy setting, so every item due date follows the policy.

## 2. Reusable pattern: `messaging_policy` layered resolution

Done spec `user-communication-3-messaging-policy` (`spec_dd/3. done/2026-10-10_08:57_...`).

- App `freedom_ls/messaging_policy` (label `freedom_ls_messaging_policy`, `apps.py` imports `checks`
  in `ready()`). Contract in **`comms`** (`comms/messaging_policy.py`: `MessagingPolicy`,
  `MessagingDecision`, `MessagingRefusal`), setting `MESSAGING_POLICY` declared in `comms/config.py`
  with a string default naming `messaging_policy.policy.LayeredMessagingPolicy` (no import edge),
  loader `comms/messaging_loader.py::get_messaging_policy` (`@functools.cache`), cache cleared by an
  autouse fixture in `freedom_ls/conftest.py` (lines ~92-140: course access, rule kind, messaging).
  System checks E003/E004 in `comms/checks.py` copy `course_access/checks.py` E003 (importable,
  subclass of the base, and an `freedom_ls.`-prefixed path must be an installed app).
- Models (`messaging_policy/models.py`): abstract `MessagingFlags` (three `CharField`s over
  `MessagingFlag` `inherit`/`open`/`closed`, one `CheckConstraint` each); `SiteMessagingConfig` (unique
  per site, `UniqueConstraint(fields=["site"])`), `OrganisationMessagingConfig`,
  `CohortMessagingConfig`, `LearnerMessagingConfig` (each `OneToOneField` with
  `related_name="messaging_config"`), `LearnerCourseRegistrationMessagingConfig` and
  `CohortCourseRegistrationMessagingConfig` (one-to-one to the registration, a single flag).
  All `SiteAwareModel, TimestampedModel`.
- Resolver (`messaging_policy/resolver.py`): `LAYER_ORDER = ("learner", "registration", "cohort",
  "organisation", "site", "settings")`; `resolve_flag(layers: Mapping[str, str | None]) ->
  ResolvedFlag(value, source)` takes the first non-`None`, non-`inherit`; `resolved_flag_expression`
  is the SQL twin (`Coalesce(NullIf(F, "inherit"), ...)`). Both are tied to the `MessagingFlag`
  vocabulary and to string flags, so they do not transfer as code: copy the shape, not the module.
  Missing row equals all-inherit; the settings layer always supplies a value.
- Config (`messaging_policy/config.py`): `MessagingPolicyConfig(AppSettings)` with
  `declared_settings` and `Setting(default=...)`; checks (`checks.py`) E001 "settings default names
  exactly the flags and every value resolves" (the settings layer must always decide).
- Admin (`messaging_policy/admin.py`): one `@admin.register`ed `SiteAwareModelAdmin` per model, no
  inlines on the owners' admins, `autocomplete_fields` on the owner field, `list_select_related`.
  (Spec 1 `deadlines` took the other route, inlines from `deadlines/admin.py`. Both precedents exist;
  messaging's is the one built for config rows keyed on owners.)
- Not reusable as is: messaging pools several candidates per sender ("any path resolves open"). The
  idea needs **one** registration to govern (section 5).

Mapping the idea's layers onto models (site, organisation, cohort, course, registration): site
(`SiteTimeZoneConfig`-style unique-per-site row), `Organisation` (`organisations/models.py:58`),
`Cohort`, `Course` (`content_engine`), and `LearnerCourseRegistration` / `CohortCourseRegistration`.
`Cohort` has an `organisation` FK; `Course` does not belong to one organisation (`Course.organisations`
M2M and `audience`, migration `content_engine/0009_course_audience_course_organisations.py`;
`is_in_audience`, `is_course_open_to_organisation` in `learner_management/queries.py`).

## 3. Where the consequences act today

### 3.1 Closing an item (no deadline lock exists)

- Chokepoint pair in `learner_interface/views.py`: `_course_access_redirect(user, course)` (line 1064,
  hidden 404 via `raise_404_if_unavailable`, then `get_course_access_backend().get_access(...)
  .can_access_content`, else redirect to `course_detail`) and `_blocked_item_redirect(user, course,
  index, *, course_index=None, course_progress=UNRESOLVED)` (line 1080), which redirects when
  `current_entry_status(course_index) == BLOCKED`. Both are the existing "one decision" seams.
- `view_course_item` (line 1114): `_course_access_redirect`, `_ensure_player_course_progress`, builds
  `get_course_index(..., course_deadlines=_deadlines_or_none(course_progress))`, then
  `_blocked_item_redirect(..., course_index=course_index)`.
- `form_start` (1454) and `form_fill_page` (1571): `_course_access_redirect`,
  `_ensure_player_course_progress`, then `_blocked_item_redirect(user, course, index,
  course_progress=course_progress)` with **no `course_index` and no deadlines**, so the function
  builds its own index without `course_deadlines`. Any closed state taken from the index misses
  these two unless they are changed to pass deadlines (or the closed decision is separate from the
  index).
- `get_course_index` (`learner_interface/utils.py:463`): takes `course_deadlines`, `now`; each child
  dict has `collection_item_id`, `due_at`, `is_overdue` from `_deadline_keys` (line 566). Status
  vocabulary there: `BLOCKED`, `READY`, `IN_PROGRESS`, `COMPLETE`, `FAILED`. `BLOCKED` is already
  used by sequential unlock, `can_access_content=False` and the part roll-up (`derive_part_status`).
  A closed item set to `BLOCKED` with `url=None` would be indistinguishable from sequential lock;
  the TOC and the redirect read the same status, which is exactly the single-source-of-truth shape the
  idea wants, but a learner-facing reason ("Closed on <date>") needs a new key beside `is_overdue`.
- Topic completion is a POST in `view_topic`, reached only through `view_course_item`, so gating the
  player covers it. Form completion is `form_progress.complete()` in `form_fill_page` after the
  gate. Course completion is in `course_finish` (line 1758), which sets
  `CourseProgress.completed_time` and fires `course.completed`; it calls **neither**
  `_course_access_redirect` nor `_blocked_item_redirect`, and does `_ensure_player_course_progress`.
  A learner whose access has ended could still reach it by URL if the access is enforced only in
  `_course_access_redirect`; decide whether finishing is allowed (it can only complete when every
  item is complete, so "completed items never close" makes it harmless, but the webhook and
  `record_course_completed` would fire after the end date).
- `learner_progress` has no deadline logic; progress recalculation is signal-driven
  (`recalculate_course_progress_on_save`, etc.). Nothing there needs to change for closing.

### 3.2 Ending course access

- `learner_management/utils.py::is_registered_for_course(user, course)` (line 24): direct
  `LearnerCourseRegistration` (active, learner active) or an `access_granting_cohort_registrations()`
  row via an active membership with an active `Learner`. Mirror: `queries.py::
  is_registered_for_course_expression(user)` (line 110). `LEARNER_REGISTRATION_GRANTS_ACCESS`,
  `COHORT_REGISTRATION_GRANTS_ACCESS`, `held_by_active_member` are the predicate pieces.
- Callers of the predicate: `course_access/backends.py::_free_access_decision` (line 227, the only
  place `can_access_content=True` is minted in core), `VisibilityEnforcingBackend._visibility_decision`
  (coming-soon and hidden exemptions, `filter_visible` via the expression),
  `course_access/visibility.py::raise_404_if_unavailable` (hidden exemption),
  `course_applications/backends.py:166` (registered learners get the inner decision),
  `learner_interface/utils.py:356` (`get_is_registered`). Changing the predicate would change all of
  them (section 7).
- Loader: `course_access/loader.py::get_course_access_backend()` (`@functools.cache`) returns
  `VisibilityEnforcingBackend(import_string(config.COURSE_ACCESS_BACKEND)())`. A second wrapper is
  one more line there. `course_access/config.py::CourseAccessConfig` has `COURSE_ACCESS_BACKEND`
  (`required=True`) and the two OVERRIDE settings. `course_access/checks.py` E001 to E003, W001.
- Contract: `CourseAccessDecision(cta_label, cta_url, can_self_register, can_access_content,
  enrolment_summary, acquisition_heading, acquisition_subtext, is_accessible_for_free)`. Callers read
  the first four plus the copy fields; no "why not" field. Additive fields are safe.
- Callers of `get_access` / `get_access_for_request` (non-test): `learner_interface/views.py` lines
  333 (dashboard, inside the per-course loop of `_annotate_registered_courses`), 841
  (`course_detail`), 968 (`course_home`), 1011 (`initiate_course_access`), 1074
  (`_course_access_redirect`, so every player route); `learner_interface/utils.py` `get_course_index`
  consumers pass `can_access_content` in. A wrapper that resolves a registration and deadlines per
  `get_access` call costs several queries per call, and the dashboard loop calls it once per course
  after `course_deadlines_for` already ran in bulk (N+1 risk). `get_access` takes `user`, not a
  request or a resolved record.
- `ensure_course_progress_record`, `learner_for_course` and `course_progress_for` resolve the same
  registration (section 5); `course_progress_by_course_for(user, courses)` is the bulk twin
  (constant three queries, same ordering).

### 3.3 Dashboard course card

`learner_interface/views.py`: `_annotate_registered_courses` (line 305) runs `course_progress_by_course_for`,
`course_deadlines_for`, then per course `backend.get_access(...)`, `_annotate_next_up(...)`, which
stamps `missed_deadline` and `next_deadline` (via `_card_deadline_line`, `CardDeadline`,
`CardDeadlineLine`). When `can_access_content` is False it passes `course_deadlines=None`. Template
`learner_interface/templates/learner_interface/partials/course_card.html` renders the "Missed
deadline" chip and "Next deadline" line. `CourseListingStatus` (`NOT_REGISTERED`, `REGISTERED`,
`IN_PROGRESS`, `COMPLETE`, `COMING_SOON`) has no "access ended" value; `derive_listing_status` is in
`learner_interface/utils.py`. A course whose access ended stays registered, so it stays in the
current-courses list that `get_current_courses` builds, but needs a new state/label. A completed
course is listed via `_annotate_completed_courses`, which does not resolve deadlines.

### 3.4 Course detail and CTA

`course_detail` (line 828): `is_registered = get_is_registered(...)` (the predicate), `decision =
get_access_for_request(...)`; a registered learner gets `_detail_start_url` and `_detail_cta_label`
(progress-based, "Start course" / "Continue" / "Review course") **regardless of the decision**, with
a comment that the two signals deliberately diverge. If access ended is expressed only in
`can_access_content`, the registered branch still offers "Continue" and a start URL that
`view_course_item` then bounces back to `course_detail`: a visible loop that the template/CTA branch
must handle. `course_detail` passes no deadlines (spec 1 decision), shows the "Time limit N days"
cell from `Course.display_time_limit()` (course_detail.html:124). `course_home` (951) redirects to
`course_detail` when `can_access_content` is False.

### 3.5 The mark-overdue switch: every place spec 1 shows "Missed deadline"

1. `deadlines/resolver.py::is_overdue(resolved, completed, now)`: pure, no policy.
2. `learner_interface/utils.py::_deadline_keys` (line 566): sets the row's `is_overdue`.
3. `learner_interface/views.py::_card_deadline_line` (line 139), including the time limit as one more
   "Course" deadline; `COURSE_DEADLINE_TITLE = "Course"`.
4. Templates `partials/course_minimal_toc.html` (lines 4-12, `deadline-badges` partialdef replaced by
   spec 1's inline block) and `partials/course_card.html` (68-74).
   Also `deadlines/admin.py` read-only "Effective deadlines" (no overdue mark; unaffected).
A policy that turns the mark off should still show the date ("Deadline <date>") and
likely keeps counting "next deadline"; that is a design call for the spec, but the four places above
are the whole surface. The policy for a given row needs the resolved layer values per
`CourseProgress`, so `course_deadlines_for` (bulk) is the natural carrier: add the resolved policy
beside `CourseDeadlines`, or a sibling `policies_for(records)`.

## 4. The form attempt flow and the ungated routes

Routes (`learner_interface/urls.py`): `form_start`, `form_fill_page`, `course_form_complete`,
`form_submit_and_exit`, `view_course_item`, `course_finish`.

| View | `_course_access_redirect` | `_blocked_item_redirect` | Comment in code |
| --- | --- | --- | --- |
| `view_course_item` | yes | yes (with its own index incl. deadlines) | writes `last_accessed_item`, `started_at` |
| `form_start` | yes | yes (no deadlines) | gate before minting the attempt and `finalise_stale_incomplete` |
| `form_fill_page` | yes | yes (no deadlines) | "a refused page must write nothing at all"; POST saves answers and completes |
| `course_form_complete` | yes | **no** | "a learner is always entitled to the score they earned, including after the quiz itself has been withheld" |
| `form_submit_and_exit` | yes | **no** | "refusing it would strand that attempt incomplete for good" |
| `course_finish` | **no** | **no** | marks `completed_time`, fires `course.completed` |

Attempt helpers: `learner_progress/attempts.py::get_latest_incomplete(course_progress,
collection_item)`, `latest_attempt`, `completed_attempts`, `get_or_create_incomplete`,
`finalise_stale_incomplete` (finalises stale incomplete attempts for submit-on-exit forms on
`form_start`). `CourseFormAttempt(course_progress, collection_item, form_progress)`;
`FormProgress.completed_time` null means open.

Consequences for the spec:

- "Completed items never close, results pages stay ungated" is currently true for **item** closing
  (these routes skip `_blocked_item_redirect`). It is **not** true for **ending access**: both
  `course_form_complete` and `form_submit_and_exit` run `_course_access_redirect`, which asks the
  backend. If access ended is a `can_access_content=False` decision, a learner loses their results
  page and the submit-and-exit endpoint (the latter strands an open attempt). So either the ended
  state is read where those two routes do not read it, or those two routes get an exemption.
- **Open attempt after "close"**: the only way a learner continues an attempt is `form_fill_page`
  (gated by `_blocked_item_redirect`) and `form_submit_and_exit` (ungated). If a closed item reads
  as `BLOCKED` in the index, `form_fill_page` refuses a POST and the open attempt can only be
  finalised through `form_submit_and_exit`, which exists only for `submit_on_exit` forms and
  redirects save-on-exit forms back to `view_course_item`. Save-on-exit forms would be stranded.
  The index shows an open attempt as `IN_PROGRESS`; a closing rule that exempts `IN_PROGRESS`
  entries (or an open `get_latest_incomplete`) leaves an attempt finishable in `form_fill_page` only,
  and it is cheap because the index already knows the status.
- The page the learner stands on when the date passes: gates read on every request, so enforcement on
  read ends a mid-form session at the next POST (`form_fill_page` POST would be refused if closed).

## 5. Registration resolution, "one registration governs"

- `learner_management/queries.py::learner_for_course(user, course) -> ResolvedRegistration(learner,
  registration) | None` (line 299): cohort registration wins (`access_granting_cohort_registrations()`
  filtered on membership of an active `Learner`, `order_by("-is_active", "-registered_at")`), else
  `latest_registration` (`LearnerCourseRegistration`, `order_by("-is_active",
  "-learner__is_active", "-registered_at")`; it **returns an inactive or removed-learner row if that
  is all there is**).
- `learner_progress/queries.py::course_progress_for(user, course)` and `course_progress_by_course_for`
  resolve through it; `CourseProgress` carries exactly one of `learner_registration` /
  `cohort_registration` (check constraint `course_progress_has_exactly_one_grant`), and a record
  per (registration, learner). `learner_interface/views.py::_ensure_player_course_progress` mints it.
- The policy's registration layer therefore keys on the winning registration: for a cohort win the
  `CohortCourseRegistration` row; for an individual win the `LearnerCourseRegistration` row. The
  chain the idea needs is derivable from the record alone: `course_progress.cohort_registration`
  (`.cohort` then `.cohort.organisation`) or `course_progress.learner_registration.learner.
  organisation`, plus `course_progress.course` and `course_progress.site`. So the policy resolver can
  take a `CourseProgress` (as spec 1's `course_deadlines` does) and the dashboard's bulk
  `course_deadlines_for` shape generalises to it.
- Edge to record: `is_registered_for_course` (the access predicate) is "any path", while
  `learner_for_course` is "one winner". They can disagree: a learner with an active access-granting
  row in organisation B but whose resolved winner is an inactive row in A. `latest_registration`
  orders active first, so with an active row anywhere it wins unless a cohort registration also
  grants; the disagreement only appears when the winner is non-access-granting and nothing else
  is. A policy hung on `learner_for_course` that governs `can_access_content` must handle the
  `None` / inactive winner.
- A learner holding both an individual and a cohort registration has **two** `CourseProgress`
  records; only the cohort one accumulates work (`better-course-progress-tracking`, section
  "Resolving the learner"). Two cohorts both granting: tiebreak `(-is_active, -registered_at)`,
  pinned by a test. Answer for the "keyed on" question: key the registration layer on whichever
  registration `learner_for_course` returns; the other registration's policy row is never read
  while the winner stands.
- Cohort `is_active` is part of the resolver's `access_granting_cohort_registrations()` but spec 1's
  override lookup (`course_deadlines_for`) keys on `record.cohort_registration_id` only, so an
  inactive cohort's overrides still apply to its members' records (spec 1 inherited the earlier
  deliberate choice). Same question will arise for the cohort policy layer.

## 6. Admin and app-settings conventions

- `freedom_ls/site_aware_models/admin.py::SiteAwareModelAdmin` is mandatory (skill
  `fls-dev:admin-interface`): Unfold `ModelAdmin` base, excludes and fills `site`; inlines extend
  `SiteAwareTabularInline` / `SiteAwareStackedInline`. Messaging policy precedent:
  `list_display = ["__str__", *flags]`, `list_select_related`, `list_filter`,
  `autocomplete_fields`, `search_fields`. `ConstraintValidationFormMixin`
  (`site_aware_models/forms.py`) turns conditional unique constraints into form errors (spec 1 uses
  it; one-row-per-owner constraints need it if the owner is chosen on a form).
- The "restore after the time limit ends access" staff action is made in the Django admin here
  (idea). Existing admin actions precedent: `learner_management/admin.py` registration admins;
  `CourseProgressAdmin` and `CohortCourseRegistrationAdmin` already carry spec 1's inlines, so the
  restore action is a natural admin action or a field on the policy/record the admin edits. There is
  **no existing field to record a restored window** on `CourseProgress`, `LearnerCourseRegistration`
  or `CohortCourseRegistration` (no end date, no `restored_at`, no reason).
  `LearnerDeadlineOverride` on the time-limit row (`collection_item=None`, `kind=relative|none`)
  is the nearest existing lever: a staff-written learner override can already move or remove the
  time limit end for one `CourseProgress`, with `set_by` and `reason`. Restoring "opens a new window"
  could be one of those rows plus an audit note, or a new field; spec 3 (extensions) will want the
  same lever.
- App settings (`freedom_ls/base/app_settings.py`, skill `fls-dev:app-settings`): subclass
  `AppSettings`, `declared_settings = {NAME: Setting(default=..., required=False)}`, instance
  `config`; `required_settings_errors(config, app_label)` builds `<app>.E001`. App label literal
  `"freedom_ls_deadlines"`. `deadlines` has no `config.py` yet, so spec 2 adds it. A policy class
  setting follows `MESSAGING_POLICY` (string default, no import edge) or `COURSE_ACCESS_BACKEND`
  (`required=True`, project supplies it). The default-policy values the idea fixes (mark overdue on,
  no grace window, close/end/notify off) are the "settings layer"; messaging's check E001 shows the
  rule: the settings layer must always decide.
- Loader convention: `@functools.cache`, plus a cache-clearing autouse fixture added in
  `freedom_ls/conftest.py` next to the three existing ones.
- Multi-tenant (skill `fls-dev:multi-tenant`): every policy row is `SiteAwareModel`; `SiteAwareManager`
  filters by the thread-local site inside a request only, so any code that runs in a task or sweep
  (spec 5) must use `_base_manager` or explicit `site_id` (precedent: `deadlines/signals.py`
  `_base_manager.filter(site=site...)`). `SiteTimeZoneConfig` is the template for "one row per site"
  (`UniqueConstraint(fields=["site"])`, `site_time_zone_config(site)`); `get_cached_site(request)` in
  `site_aware_models/models.py`.

## 7. Where "access ended" is enforced: what the code says

| Option | Reach | Side effects found |
| --- | --- | --- |
| A. A wrapper around the access backend, applied in `course_access/loader.py` | Every caller of `get_access`: player routes, `course_home`, `course_detail`, dashboard loop, `initiate_course_access`. Visibility exemptions (hidden, coming-soon) stay with `is_registered_for_course`, so an ended learner still reaches a hidden course's detail page and a coming-soon course. | Adds `course_access -> deadlines` runtime edge (`docs/app_structure.md`: `course_access` deps are `accounts, base, content_engine, learner_management`; `deadlines` deps include `learner_progress`; no path from `deadlines`/`learner_progress` back to `course_access`, so no cycle). `get_access` has `(user, course)` only, so it must resolve registration and `CourseProgress` itself; cost per call; dashboard N+1. Results routes and `form_submit_and_exit` are bounced unless exempted (section 4). `course_detail`'s registered branch ignores the decision (section 3.4). The decision for an ended learner must set `can_self_register=False` (the free backend's unregistered branch offers "Enrol for free"; the wrapper must not fall through to it). Pattern fit: exactly `VisibilityEnforcingBackend`, which the idea names. |
| B. Change `is_registered_for_course` / `is_registered_for_course_expression` / `access_granting_cohort_registrations` | Everything that asks "registered" at once, including `filter_visible` (hidden courses vanish for an ended learner), hidden 404, `ApplicationCourseAccessBackend`, `get_is_registered`, `courses_losing_access` / `members_keeping_access` (educator unregister confirmations), messaging peers (`holds_registration_for_any_expression`, `peers_through`, `registrations_of`), `is_registered_for_course_expression` in dashboards. | The predicate is deliberately the single definition, but it is also used for course-peer messaging, hidden-course visibility, the dashboard "registered" classification and educator confirmations, none of which should change on a deadline. It needs the deadline policy resolved inside an `Exists` expression (SQL twin of the resolver), a much larger surface. `course.unregistered` is fired from `post_save` receivers on `is_active`, not from the predicate, so the idea's "no `course.unregistered`" holds either way. The registration stays active in both options. |
| C. A direct call in `learner_interface` (`_course_access_redirect` and the dashboard) | Player routes and dashboard only. `learner_interface` already depends on `deadlines` and `course_access`. | Not a wrapper, so no `course_access -> deadlines` edge; but a downstream backend and `course_applications` views never see it, and `course_home`/`course_detail`/`initiate_course_access` each need the call. The idea states the choice as A or B; C is a third that the dependency table makes cheap. |

The question's own consumers: spec 3 (pause) and spec 4 (self-pause) need a second "no access" reason
(paused) next to "ended"; a `CourseAccessDecision` has no reason field, so a wrapper (A) is where a
reason would be added (additive field on the dataclass; the base contract reads only four fields).

## 8. Notify educators

Setting only. `deployment/housekeeping.py` sweeps are spec 5's seam. `comms.notify.raise_notification`
and `base/notification_categories.py::FLS_NOTIFICATION_CATEGORIES` exist; nothing for spec 2.

## 9. Best home app for the policy models

**`freedom_ls/deadlines`.**

- Spec 1 decision 1: "New app `freedom_ls/deadlines`... Specs 2 to 7 add to it." The roadmap places
  the policy resolver beside the effective-date resolver.
- Dependencies today (`docs/app_structure.md`): `deadlines -> accounts, content_engine,
  learner_management, learner_progress, site_aware_models`. Policy models need `Organisation`, so add
  `deadlines -> organisations` (`organisations -> base, site_aware_models`: acyclic). `Cohort`,
  `CohortCourseRegistration`, `LearnerCourseRegistration` are in `learner_management`; `Course` in
  `content_engine`.
- `messaging_policy` is a separate app because its contract lives in `comms`, which must not import
  `messaging_policy` or `learner_management`. The deadline policy has no such constraint at the
  contract level: the contract class can live in `deadlines` and the loader reads
  `DEADLINE_POLICY` (name is a suggestion, not code). The only upward consumers are
  `learner_interface` (already depends on `deadlines`) and, under option A, `course_access` (new
  edge).
- The app has no `config.py`, `checks.py`, `loader.py`, `conftest.py` fixtures; spec 2 adds them.
  `deadlines/apps.py::ready()` imports `signals` only; add `checks` there as messaging does.
- A separate app (`deadline_policy`) would cost a new entry in `INSTALLED_APPS` (upgrade notes, no
  system check for a missing app, as spec 1's notes warn) for no layering gain.
- Name collision check: "policy" already means `MessagingPolicy`, `SiteSignupPolicy` (accounts);
  "consequence" and "grace" have no hits among model or field names in `freedom_ls/` (checked by grep
  of `class .*Grace`, `grace`).

## 10. Conflicts and collisions to carry into the spec

1. **Idea text out of date**: "the two lock paths today (the player's check and the table of contents
   status) are replaced by one decision". Those were removed in spec 1; the work is "add" not
   "replace". The roadmap's caution ("1, 2, 3 and 4 all edit the player gates; whoever lands second
   rebases") is live: spec 1 left `view_course_item`, `_blocked_item_redirect`, `get_course_index`,
   `course_minimal_toc.html`, `course_card.html`, `_annotate_registered_courses` in the state above.
2. `form_start` / `form_fill_page` pass no deadlines to `_blocked_item_redirect` (section 4).
3. Results page, `form_submit_and_exit` and `course_detail` interact with an access-backend-level
   "ended" decision (sections 3.4, 4, 7).
4. `COURSE_ACCESS_BACKEND` is a *project* setting (`config/settings_base.py` ~617,
   `ApplicationCourseAccessBackend`); a wrapper applied in the loader works for any downstream
   backend, as `VisibilityEnforcingBackend` does. The cache-clearing fixture pattern in
   `freedom_ls/conftest.py` covers a new wrapper only if the loader stays one `functools.cache`.
5. `docs/app_structure.md` is generated (`/ds:app_map`); the conformance/layering checks from the
   test-organisation specs will flag a new `course_access -> deadlines` or `deadlines ->
   organisations` edge until the doc is regenerated. Spec 1 handled the same step for
   `learner_interface -> panel_framework`.
6. `deployment/housekeeping.py` is untouched by spec 2 (enforcement on read, nothing swept).
7. `qa_helpers` already depends on `deadlines` (`qa_create_deadlines_seed.py`); QA data for policy
   rows would extend it. `claude_plugins/fls-dev/commands/do_qa.md` references deadline data.
8. Generic plugins: none of this goes in `claude_plugins/django-stack` or `claude_plugins/sdd`.
9. Docs to touch (from spec 1's list): `docs/product/learner-experience.md`,
   `admin-interface.md`, `configuration-and-extension.md` (new setting), `docs/app_structure.md`,
   `.claude/skills/domain-glossary/SKILL.md` (new models), upgrade notes (new migration, new setting,
   template changes to `course_card.html` / `course_minimal_toc.html`).
10. Test-organisation specs 13/14 may move the player tests that spec 2 must extend
    (`learner_interface/tests/views/test_course_player.py`, `test_dashboard.py`, `test_course_detail.py`,
    `deadlines/tests/`). Move test files in their own commit (roadmap caution).

## 11. Answers the code gives to the idea's "Open until the spec" items

**Layer order between course and organisation, and what each layer holds.**
The code does not decide, but constrains it. Messaging's order is learner, registration, cohort,
organisation, site, settings. For deadlines the idea lists site, organisation, cohort, course,
registration. A `Cohort` belongs to one `Organisation` (`Cohort.organisation`), so cohort-then-
organisation is forced by nesting. A `Course` does not nest under an organisation (`Course.organisations`
is an M2M audience, `is_in_audience`), so the course layer is global to the site's learners across
organisations and "course beats organisation" means a course default overrides an organisation's
choice for every organisation using the course, while "organisation beats course" lets an
organisation override a course for its own learners. Both read from one resolved `CourseProgress`
(it names course, registration, cohort, organisation, site), so either order costs the same
queries. Spec 1's own precedent: the most specific layer (learner) wins outright and the content
default is the lowest; by that analogy the registration-then-cohort-then-course-then-organisation
chain is the natural fit, with course content-sourced, but this is a decision for the spec.
What each layer can hold: the settings layer holds every setting; every layer can hold the four
consequence switches and the grace window; a registration layer carrying the *time limit* ending
and a *course* layer carrying only course-appropriate settings are open. Specs 3, 4 and 6 add pause
and extension settings to the same models, so each setting needs its own unset marker (tri-state
text for flags as `MessagingFlag`, null for the grace window).

**Where "access ended" is enforced.** Section 7. The code favours option A for reach and for the
extension seam (a decision reason for spec 3's pause), with the three cost items: the
`course_access -> deadlines` edge, per-call resolution cost (dashboard loop), and the exemptions for
`course_form_complete`, `form_submit_and_exit` and the registered branch of `course_detail`. Option
B changes the meaning of "registered" for hidden-course visibility, messaging peers and educator
confirmations, none of which should follow a deadline: against the idea's own statement that "the
choice decides who still sees a hidden course". Under A an ended learner keeps seeing a hidden
course (the exemption uses `is_registered_for_course`, unchanged); under B they lose it.

**Whether "close" leaves an in-progress form attempt finishable.** Section 4. The code has two
precedents: `course_form_complete` and `form_submit_and_exit` are exempt so an attempt is not stranded,
and `form_fill_page` is gated so "a refused page writes nothing". Leaving an open attempt finishable
means `form_fill_page` must let through an entry the index shows as `IN_PROGRESS` while still refusing
`form_start` for a new attempt (`get_or_create_incomplete` would mint one) and `view_course_item`
topics. Closing a form that has an open `get_latest_incomplete` attempt is the one case where the two
precedents conflict. Spec 3 (pause, "nothing can be opened while paused") sits on the same decision.

**What the registration layer is keyed on for a learner with both registrations.**
The registration `learner_for_course` returns (cohort wins, tiebreak `(-is_active, -registered_at)`);
`CourseProgress` is bound to exactly one registration, so the same record yields the key. The policy
model is two one-to-one rows (`LearnerCourseRegistration`, `CohortCourseRegistration`) as messaging
did, or one row keyed on `CourseProgress` as spec 1's learner override did. The idea says the
registration layer "covers both `LearnerCourseRegistration` and `CohortCourseRegistration`", which
matches messaging's two models. The unreferenced second registration's policy row is not consulted
while the winner stands; if the winner changes (cohort left, cohort deactivated) the other applies,
as a record per registration already does.

**How the grace window interacts with an override that moves a date.**
Spec 1's override replaces the resolved `due_at`; there is no extension record or per-override grace.
A grace window computed from the resolved `due_at` therefore moves with any cohort or learner
override and with a content default, with no extra code. `none` overrides mean no `due_at`, so
nothing closes or ends. Spec 3's extension (not yet built) will be the thing that "moves a date" in
a way that may or may not restart grace; spec 1's `LearnerDeadlineOverride.reason` / `set_by` /
`replaced_value` cannot tell an extension from a correction. The grace comparison happens on read:
`now > due_at` marks overdue (existing `is_overdue`), `now > due_at + grace` closes or ends. The
site-zone end-of-day boundary (spec 1 decision 3) means a day-granular grace window of N days ends at
`due_at + N days`; a time-of-day grace would not be representable in whole days.

## 12. Reuse list

- `deadlines/resolver.py` (`resolve_deadline`, `course_deadlines_for`, `is_overdue`) for the dates;
  generalise `course_deadlines_for` to also return the resolved policy, or add a parallel bulk call.
- `messaging_policy` models, admin and config/check shape; `comms/messaging_loader.py` and
  `course_access/loader.py` loader shape; `course_access/checks.py` E003 and `comms/checks.py` E003/E004.
- `CourseAccessDecision` additive fields; `VisibilityEnforcingBackend` as the wrapper template.
- `learner_for_course`, `course_progress_for`, `course_progress_by_course_for`, `CourseProgress` as
  the single carrier of registration, cohort, organisation, course and site.
- `site_aware_models/time_zones.py::site_time_zone` for grace boundaries; `SiteTimeZoneConfig` as the
  "one row per site" model template.
- `deadlines/admin.py` inline plus formset pattern for any per-registration row; or messaging's
  standalone `SiteAwareModelAdmin` per model.
- `learner_interface/views.py::_blocked_item_redirect`, `get_course_index`'s status vocabulary,
  `_deadline_keys` as the single read for items.

status: ok
