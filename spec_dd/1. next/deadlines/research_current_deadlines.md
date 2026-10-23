# Research: the current deadline implementation and what a replacement builds on

Scope: facts only, from the code at HEAD of `main` (2026-10-23). No recommendations; constraints are flagged as such.

## 1. The current implementation

All in the `learner_management` app (`freedom_ls/learner_management/`). Three models, one resolver module, one setting.

### Models (`models.py`, all `SiteAwareModel, TimestampedModel`)

| Model | Attaches to | Extra |
|---|---|---|
| `CohortDeadline` | `cohort_course_registration` FK (`CohortCourseRegistration`, related_name `deadlines`, CASCADE) | applies to every member of the cohort for that course registration |
| `LearnerDeadline` | `learner_course_registration` FK (`LearnerCourseRegistration`, related_name `deadlines`, CASCADE) | the individually registered learner |
| `LearnerCohortDeadlineOverride` | `cohort_course_registration` FK (related_name `deadline_overrides`) plus `learner` FK (`Learner`) | per-learner override within a cohort; `clean()` requires a `CohortMembership` for (learner, cohort) |

Every model has the same four fields:

- `content_type` FK to Django `ContentType` (nullable, `SET_NULL`), `object_id` `UUIDField` (nullable), `content_item` GenericForeignKey. Both null means a whole-course deadline.
- `deadline` `DateTimeField` (absolute datetime, no timezone logic beyond Django's), `is_hard_deadline` `BooleanField(default=True)`.

Constraints: a conditional `UniqueConstraint` per item (`unique_cohort_deadline_per_item`, `unique_learner_deadline_per_item`, `unique_learner_cohort_override_per_item`) applies only when content_type and object_id are both non-null. Uniqueness of the whole-course row (null content type) is enforced only in `clean()`, so it is not a database constraint and factories/`.create()` bypass it.

What a deadline points at: the content child itself (`Topic`, `Form`, `CoursePart`), by `ContentType` + that child's UUID pk. It does NOT point at a `ContentCollectionItem` (the placement), and there is no deadline on `Course` as an item (course-level is the null-content-type row), `Activity` or `Article`. The admin inlines accept any content type and any UUID with no validation that the object belongs to the course (`LearnerDeadlineInline`, `CohortDeadlineInline`, `LearnerCohortDeadlineOverrideInline`, `fields = ["content_type", "object_id", "deadline", "is_hard_deadline"]`). `docs/app_conventions.md` ("Generic foreign key object_id type") names the deadline GFKs as `UUIDField` examples.

Migration: models live in `learner_management/migrations/0001_initial.py` (history was reset to a single 0001 in the rename work); 0002 to 0006 follow. Removal needs a new migration (never edit existing ones).

### Hard/soft semantics

- Hard (`is_hard_deadline=True`): once `deadline <= now`, an incomplete item is locked (learner cannot open it). Completed items are never locked. Soft: only a badge; never locks.
- Only item-level locking exists. There is no "course expired" lock and no overall time limit. A whole-course (null content type) hard deadline is a fallback that applies to every item lacking its own deadline, so it locks the whole course's incomplete items.
- No consequence other than the lock; no notification, no reminder, no educator signal, no extension model, no pause.
- Defaults in factories: `is_hard_deadline = False`, `deadline = now + 30 days`.

### Effective deadline resolution (`deadline_utils.py`)

- `EffectiveDeadline` dataclass: `deadline: datetime`, `is_hard_deadline: bool`, `source: str` (display string only).
- `get_effective_deadlines(user, course, content_item=None) -> list[EffectiveDeadline]`: per-item. First calls `learner_for_course(user, course)` (`queries.py`) to pick the single `Learner` (cohort registration beats individual; tiebreak by `registered_at`), so deadlines are scoped to one organisation's `Learner`, never merged across organisations (done in `better-course-progress-tracking`). Then:
  - Cohort registrations (`CohortMembership` of that learner with `learner__is_active=True`, `CohortCourseRegistration` `is_active=True` for the course): override for item > `CohortDeadline` for item > course-level override > course-level `CohortDeadline`.
  - Individual registrations (`LearnerCourseRegistration` `is_active=True`, no `learner__is_active` filter on purpose): `LearnerDeadline` for item > course-level `LearnerDeadline`.
  - Returns one `EffectiveDeadline` per registration that yields one. `is_item_locked_by_deadline(user, course, content_item, is_completed)` takes the latest hard deadline across that list (most permissive) and locks if it is `<= now`.
  - Cohort-registration filtering in `deadline_utils` uses `CohortCourseRegistration.is_active` only, NOT `cohort.is_active` (unlike `access_granting_cohort_registrations()`); `educator-interface-6-cohort-administration` deliberately left this (deadlines out of scope; "a cohort deadline in an inactive cohort still applies to a member who has access another way").
- `get_course_deadlines(user, course) -> dict[(content_type_id | None, object_id | None), list[EffectiveDeadline]]`: bulk version for the table of contents (same resolution from prefetched indexes). Duplicated logic in `_resolve_*` and `_resolve_*_from_index` (two copies of the priority rules).
- `queries.py` has no deadline code; it only supplies `learner_for_course` / `latest_registration` / `access_granting_cohort_registrations` and a docstring mention of deadlines (`latest_registration`).

### Config

`learner_management/config.py`: `LearnerManagementConfig(AppSettings)` with one declared setting `DEADLINES_ACTIVE` (default `True`), documented in `docs/product/configuration-and-extension.md`. Read in `learner_interface/views.py` (view_course_item) and `learner_interface/utils.py` (`get_course_index`). The done spec `2026-02-21_16:30_deadlines_deactivate` says: when off, no deadline queries, no badges, no locking; admin/educator unaffected; do not change the default or override in settings files (mock in tests).

### Admin (`admin.py`)

`LearnerDeadlineInline` on the learner-registration admin, `CohortDeadlineInline` + `LearnerCohortDeadlineOverrideInline` (labelled "User Deadline Override") on the cohort-course-registration admin, and standalone `CohortDeadlineAdmin`, `LearnerDeadlineAdmin`, `LearnerCohortDeadlineOverrideAdmin` (all `SiteAwareModelAdmin`, with `get_*_name`/`get_content_item` display methods). The educator interface does not manage deadlines (docs and roadmap: "deadline management is done in the Django admin").

### Factories (`factories.py`)

`CohortDeadlineFactory`, `LearnerDeadlineFactory`, `LearnerCohortDeadlineOverrideFactory` (all `SiteAwareFactory`).

## 2. Removal inventory

### Code (non-test)

| Path | What is deadline-related |
|---|---|
| `freedom_ls/learner_management/models.py` | the three models (lines ~217-372) and `DjangoContentType`/`GenericForeignKey` imports they alone use |
| `freedom_ls/learner_management/deadline_utils.py` | whole file |
| `freedom_ls/learner_management/config.py` | whole file exists only for `DEADLINES_ACTIVE` (check nothing else imports `learner_management.config`; it is the only declared setting) |
| `freedom_ls/learner_management/admin.py` | imports; the three inlines (~367-422); inline wiring (`inlines = [LearnerDeadlineInline]` ~390, `[CohortDeadlineInline, LearnerCohortDeadlineOverrideInline]` ~461); three standalone admins (~469-590) |
| `freedom_ls/learner_management/factories.py` | imports and three factories (~127-205) |
| `freedom_ls/learner_management/queries.py` | docstring on `latest_registration` mentions deadlines (wording only) |
| `freedom_ls/learner_management/migrations/` | a new migration deleting the three models; 0001 stays |
| `freedom_ls/learner_interface/views.py` | import of `is_item_locked_by_deadline` (~59); the lock block in `view_course_item` gated on `config.DEADLINES_ACTIVE` (~991-1002, redirects to `course_detail`); `_is_content_item_completed` (~1777) exists only to feed that lock (docstring: "decides whether a hard deadline locks the item"); comments at ~717, ~1024, ~1505 (quiz result access after deadline closes the quiz) |
| `freedom_ls/learner_interface/utils.py` | imports (`EffectiveDeadline`, `get_course_deadlines`); deadline lookup in `get_course_index` (~484-492); `_get_deadlines_for_item` (~556), `_apply_deadline_locking` (~583, sets `status = BLOCKED`, `url = None`), the `deadlines_map` parameter threaded through `create_child_dict_with_flattened_index` (~602-760), `"deadlines"` key in child dicts; docstring ~82 mentions a hard-deadline-blocked item. NOTE: `BLOCKED` status is shared with the sequential-unlock gate; only the deadline-driven assignment goes. |
| `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html` | `{% partialdef deadline-badges %}` (lines 3-~20) and the three `{% partial deadline-badges %}` uses (~89, ~117, ~138) |
| `freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html`, `course_detail.html` | use the `deadline` icon name for non-deadline things (coming-soon eyebrow; "Duration" stat) |
| `freedom_ls/icons/semantic_names.py`, `icons/mappings.py` | semantic icon `"deadline"` (maps to `clock` in four icon sets). Also used by `base/templates/403_csrf.html` (`icon="deadline"`), so the name is in use outside deadlines |
| `freedom_ls/role_based_permissions/registry.py` | 12 commented-out permission lines (~79-90) for the three models |
| `freedom_ls/base/static/base/js/interface-swap-fallback.js` | a comment only (line 2: "a deadline-lock redirect to course detail") |
| `freedom_ls/qa_helpers/management/commands/` | `qa_create_soft_deadline.py`, `qa_create_learner_deadlines.py`, `qa_create_half_nulled_deadlines.py`, `qa_create_deadline_overrides.py`. Also `qa_reset_learner_progress.py` and `qa_create_quiz_progression_block.py` matched `overdue/BLOCKED` (check for deadline cleanup) |

Not touched: `freedom_ls/deployment/worker.py` / `tests/test_worker.py` use `deadline` for a monotonic-time heartbeat cap, unrelated. No JS/static/demo-content/educator_interface/reports/`learner_progress` non-test code references the models (the educator interface rebuild already dropped deadline display; `educator_interface/templates/.../panels/cohort_needs_attention.html` holds a TODO comment: "list the learners ... who need an educator's attention, such as stalled or overdue progress, once something computes that"; `panel_framework/templates/cotton/panel-attention-list.html` is the generic list). `demo_content/` has no deadline references. Do not delete that TODO.

### Tests

- `learner_management/tests/test_deadline_utils.py` (whole file), `test_models.py` (134 hits, deadline model tests mixed with others), `test_admin.py` (23 hits), `test_queries.py` (one docstring hit ~226), `scenario_world.py` (matched the expiry/duration grep; check for deadline scenario helpers).
- `learner_interface/tests/views/test_course_player.py` (44 hits: imports of `CohortDeadlineFactory`/`LearnerDeadlineFactory` ~67-71, `test_a_deadline_lock_ignores_a_completion_in_another_course` ~3236, `test_course_index_includes_deadline_data` ~3795, `test_expired_hard_deadline_locks_incomplete_item` ~3821 and neighbours), `test_course_detail.py` (4 hits, `LearnerDeadlineFactory` ~1169).
- `learner_progress/tests/test_signals.py` ~589-592: admin POST data with `deadlines-TOTAL_FORMS` etc. management-form keys for the inline; breaks when the inline goes.
- `contrib/conformance/tests/test_timestamped_models.py` lines 48-51: the three models are listed in an explicit allowlist/exceptions set (`freedom_ls_learner_management.CohortDeadline`, `LearnerCohortDeadlineOverride`, `LearnerDeadline`); must be updated. `contrib/conformance/tests/test_app_labels.py` ~67-97 has `_STALE_NAMES = ("UserCohortDeadlineOverride", ...)` and a tree-scan test; the old name only appears in that test, not the models; removal does not break it but its comment names the class.
- `spec_dd/1. next/test-organisation-and-hygene-13-learner-interface-part-1/idea.md` lists `test_deadline_integration.py` (no longer exists in the tree; only stale `.pyc` remain). Stale `__pycache__` dirs under `freedom_ls/student_management/` and `student_interface/` also mention deadlines (untracked noise).

### Docs, skills, plugin text

- `README.md` lines 45, 46, 107-109 ("### Deadlines"), 121, 125, 129, 217.
- `docs/product/`: `learner-experience.md` (lines 17, 283-290 "Deadlines" section), `educator-interface.md` (16, 132), `configuration-and-extension.md` (150, `DEADLINES_ACTIVE`), `reports.md` (76: "Deadlines are not shown"), `learner-tracking.md` (42), `multi-tenancy-and-isolation.md` (27), `roadmap.md` (9, 74, 134-141), `README.md` (20, 22). `docs/product/_build/` holds generated output (`out.txt`, `x/word/document.xml`) with the same text.
- `docs/app_conventions.md` 124-131 (GFK section cites deadline GFKs).
- `.claude/skills/domain-glossary/SKILL.md` lines 50, 67 (table row for the three models with stale line numbers), 79, 192-193.
- `.claude/skills/notifications/SKILL.md` lines 23, 55 (a deadline-approaching reminder is listed as "Yes, if built").
- `claude_plugins/fls-dev/`: `resources/admin_interface.md:73` (cites `LearnerDeadlineAdmin`), `resources/factory_boy.md:29` (cites `CohortDeadlineFactory` as the GenericFK example), `resources/testing.md:29`, `agents/qa-data-helper.md` (2), `commands/do_qa.md:59` ("a past hard deadline" as blocking data), `skills/icon-usage/SKILL.md:29`. `claude_plugins/django-stack/` mentions deadlines generically (testing, factory_boy, code-reviewer) as examples; those are generic and not FLS references except where they copy FLS examples.
- `.claude/agent-memory/fls-dev-qa-data-helper/` has many notes on deadline fixtures (`reference_learner_deadline_admin_fixtures.md`, `reference_half_nulled_deadline_contenttype.md`, `reference_learner_visible_deadlines.md`, plus mentions in `MEMORY.md`); `.claude/agent-memory/ds-code-reviewer/MEMORY.md` (6). These are agent memory files.
- `claude_plugins/sdd/commands/implement_plan.md:34` mentions deadlines.
- Done specs reference the models heavily (history, not edited).

### Roadmap statements already made about deadlines

- `spec_dd/1. next/roadmap.md` 92 and 111: deadlines "left alone" and out of scope for the educator-interface specs 1-12; "a separate rework follows". `educator-interface-full-polish/idea.md:13` repeats this.
- `corporate-readiness/README.md` item 13 (see section 5).
- `user-communication-7-email-digests/idea.md:82` puts deadline-approaching reminders and any periodic-scan event out of scope, and rules out any scheduler inside FLS (no Celery beat, django-q, APScheduler). `notifications` SKILL lists deadline reminders as an allowed category.

## 3. Registration and progress model a new design builds on

### Registration and membership (`learner_management/models.py`)

- `Learner(user, organisation, is_active, created_at)`: unique per (site, user, organisation). Enrolment hangs off `Learner`, not `User`. `is_active=False` means removed from the organisation.
- `Cohort(organisation, name, is_active)`.
- `CohortMembership(cohort, learner)` + `TimestampedModel` (`created_at`/`updated_at`): unique (learner, cohort); `clean()` forbids cross-organisation. No `is_active`; leaving a cohort deletes the row.
- `LearnerCourseRegistration(course, learner, is_active, self_registered, registered_at)`: unique (site, learner, course). `registered_at` is `auto_now_add`. Has no `TimestampedModel`, so no `updated_at`; `loaded_is_active` is tracked via `from_db` to tell a reactivation from a no-op. `course` is `on_delete=PROTECT`.
- `CohortCourseRegistration(course, cohort, is_active, registered_at)`: unique (site, course, cohort). Cohort-wide, so `registered_at` is the cohort's registration date, not a learner's start. Per-learner "joined" for the cohort path is `CohortMembership.created_at`, or `CourseProgress.created_at`.
- Flags: `Learner.is_active`, `Cohort.is_active`, `*Registration.is_active`, `OrganisationMember.is_active`. `access_granting_cohort_registrations()` = registration active AND cohort active; every access read uses it (the progress fan-out in `learner_progress` deliberately reads only the registration flag, so an inactive cohort's members keep records).
- Resolution helpers (`queries.py`): `learner_for_course(user, course) -> ResolvedRegistration(learner, registration)` (cohort registration wins over individual; `.order_by("-is_active", "-registered_at")`), `latest_registration`, `registrations_of(learner)`, `is_registered_for_course_expression`, `members_keeping_access`, `courses_losing_access` and `courses_gaining_access`. A learner may hold multiple registrations for one course (one per organisation; two cohorts).

### Progress records (`learner_progress/models.py`)

- `CourseProgress(learner PROTECT, course PROTECT, learner_registration XOR cohort_registration (both PROTECT, CheckConstraint "exactly one"), created_at, started_at, last_accessed_time, completed_time, progress_percentage, last_accessed_item -> ContentCollectionItem SET_NULL)`. One per (registration, learner). Minted on registration (`ensure_course_progress_record`, signals in `learner_progress/signals.py`) and self-healed on first open of the player (`_ensure_player_course_progress`). Comment in the model: `created_at` is the registration date; `started_at` is the first content access (stamped once in `view_course_item`); nothing may read one for the other. A cohort move (membership delete + create) mints a fresh record; roadmap lists "re-point or accept fresh pass" as an open unknown for spec 7/8/10.
- `TopicProgress(course_progress, collection_item SET_NULL, topic PROTECT, start_time auto_now_add, last_accessed_time auto_now, complete_time)`: unique per (course_progress, collection_item). Keyed to the placement.
- `CourseFormAttempt(course_progress, collection_item SET_NULL, form_progress OneToOne to form_engine.FormProgress)`: many attempts per placement; the quiz/form completion is on `FormProgress`.
- Completion events fire webhooks (`course.registered`, completion events); `course.registered` also raises a notification when the registrant is not the actor.
- "Start" timestamps that exist: `LearnerCourseRegistration.registered_at`, `CohortCourseRegistration.registered_at`, `CohortMembership.created_at`, `CourseProgress.created_at`, `CourseProgress.started_at` (first content access), `TopicProgress.start_time`. No per-learner "enrolled on" for the cohort path other than membership/progress `created_at`.

### Course access decision

- `settings.COURSE_ACCESS_BACKEND = "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"` (`config/settings_base.py` ~617), resolved by `course_access/loader.py` and wrapped in `VisibilityEnforcingBackend`. Contract in `course_access/backends.py`: `CourseAccessBackend.get_access(*, user, course) -> CourseAccessDecision(cta_label, cta_url, can_self_register, can_access_content, ...)`, plus `is_accessible_for_free`, `get_access_badge`, `get_access_type`, `filter_visible`, `validate_course_config`, `get_dashboard_contributions`. `can_access_content` is the content gate.
- The core backend `FreeOnlyCourseAccessBackend`: `can_access_content` is true exactly when `is_registered_for_course(user, course)` (an active registration direct or via active cohort and active learner). `Course.access_config` is a backend-private JSON blob (not to be read outside the backend; only the content loader reads `application_form`); the backend validates it with `validate_course_config` and keys are whitelisted via `_ALLOWED_CONFIG_KEYS` (core allows only `access_type`; the applications backend widens it).
- `view_course_item` gates with `_course_access_redirect(request.user, course)` (hidden-course 404 + content-access gate), then ensures progress, then the deadline lock, then the sequential-unlock gate. A blocked entry in the course index sends the learner to `course_detail`, not `course_home` (which resumes to the last accessed item).
- Course prices (done spec `2026-09-19_17:02_course-prices`): `Course.price_*` fields are display-only; "FLS takes no payment, and a price changes nothing about registration, access, CTAs or the access backend's own badge and copy". There is no paid access, no purchase, no subscription model. The roadmap says a subscriptions feature does not exist and a per-learner level of service stands in for a premium entitlement (roadmap ~213, 240).

### What a "content item" is in `content_engine`

- Models: `Course`, `CoursePart` (a chapter inside a course, itself a collection), `Topic`, `Activity`, `Article` (blog article, not course content), `CourseCategory`, plus `form_engine.Form` (placed in courses as a child; quiz/assessment/application forms). Content base: `BaseContent`/`TitledContent`/`MarkdownContent` (`content_base/models.py`), `file_path`, `slug`, `meta`, `tags`. `SiteAwareModel` pk is `id = UUIDField(primary_key, default=uuid4)` (`site_aware_models/models.py:166`), so all content has UUID pks.
- Placement: `ContentCollectionItem(collection_type, collection_id, child_type, child_id, order, overrides)` (generic FKs both ends, UUID ids, `TimestampedModel`), related to `Course`/`CoursePart` via `GenericRelation` `items`. Viewable items exclude `CoursePart` sentinels (`Course.viewable_collection_items()`; the player index is by position `index`). A course contains parts, and parts contain topics/forms; the same topic or form can be placed twice, and each placement is its own `ContentCollectionItem`. Progress is keyed to the placement; the current deadlines were keyed to the child content row.
- Stability across re-imports (`content_save` command, `content_engine/management/commands/content_save.py`): content items are identified by the `uuid` written back into the markdown/YAML frontmatter on first save (`save_with_uuid` uses `update_or_create(id=uuid)`, then `update_file_with_uuid`; categories and options too), so child content ids are stable provided the file keeps its `uuid:`. The `ContentCollectionItem` row is `update_or_create` on (site, collection, child) with `order`/`overrides` as defaults (~1100), so a placement's id is stable while the same child stays in the same collection; moving a child to another part or removing it creates a new row (or leaves the old row; the sync has no prune step for collection items in the code read), and `last_accessed_item`/`collection_item` FKs are `SET_NULL` for that reason. Slugs are unique per site and derived with `get_unique_slug`. `Course.estimated_duration` is a `DurationField` (display only).
- Content deletion is a deliberate act (`danger_content_delete`; `TopicProgress.topic` and similar are `PROTECT`).

## 4. Existing time limit or access expiry on registrations

None. No expiry/valid-until/end-date/duration/pause field on `LearnerCourseRegistration`, `CohortCourseRegistration`, `CohortMembership`, `CourseProgress` or `Course` (only `Course.estimated_duration`, display-only, and `Course.price_sale_ends_on`, a display date). Registration state is only `is_active` (boolean, no history, no reason, no timestamp for when it was turned off), `registered_at`, and for individual registrations `self_registered`. Expiry-type fields found in `course_applications` (`claims.py`, `views.py`) are application claim-token expiries, unrelated. An inactive registration cuts access but keeps the progress record (progress is PROTECTed; reactivation reuses it).

## 5. Constraints from done specs and corporate-readiness

- `better-course-progress-tracking` (done): progress and deadlines are `Learner`-scoped; a person in two organisations sees each organisation's deadlines separately, never a union (success criterion 9). Progress is bound to the registration, never to `CohortMembership`. Fan-out reads the registration flag, not the cohort flag.
- `educator-interface-6-cohort-administration` (done): inactive-cohort handling deliberately excludes deadlines; the resolver and `access_granting_cohort_registrations()` define what grants access. Spec explicitly leaves the open question of how deadlines treat an inactive cohort's deadlines.
- `deadlines` and `deadlines_deactivate` (done specs): hard/soft as above; completed items never lock; most permissive (latest) wins; `DEADLINES_ACTIVE` default true and not to be overridden in settings; educators/admin keep config access when off. The earlier spec's original constraints (for reference when replacing): course-level row unique per registration, per-learner override only for cohort members.
- `user-communication-1-notifications-core` (done): deadline events were out of scope and deferred; the `comms` app (`freedom_ls/comms/notify.py`, `raise_notification`) and `.claude/skills/notifications/SKILL.md` define when to notify (reminders with real cost qualify; actor must not be the recipient). `user-communication-7-email-digests` says no scheduler is built into FLS and events come from features raising them through the notifications API; deadline-approaching events produced by a periodic scan are explicitly its non-goal, so the scan that raises them belongs to the deadlines work. Existing periodic mechanism: `deployment/housekeeping.py` sweeps (`run_housekeeping_sweeps`, `fls_run_housekeeping` command, scheduled externally) and a background task worker (`deployment/worker.py`, Django tasks, `DBTaskResult`).
- `course-prices` (done): payments and paid access do not exist; "pausing a subscription" in the idea has no payment-side counterpart in FLS.
- `corporate-readiness/README.md`:
  - Item 13 ("Due dates relative to an event"): "`CohortDeadline.deadline` and its siblings are fixed datetimes"; wants "due 30 days after registration" or "within 14 days of start date"; "has to agree with rules (12) and recertification (11)"; "The educator interface effort also says a deadline rework is coming separately. Fold this into it." It also says the work depends on HR attributes (item 9: department, role, manager, start date per `Learner`, not per `User`).
  - Item 11 (Recertification): "FLS keys course progress records on the registration that minted them. So a new cycle is most naturally a new registration with a new `CourseProgress`, which keeps the old record as evidence. That needs designing deliberately, and it's the same question the retakes deferral put off. Settle it once for both." Attaches a validity period to a course or certificate and opens a new cycle before expiry, with reminders.
  - Item 12 (rule-based automatic registration) output should be ordinary `CohortCourseRegistration`/`LearnerCourseRegistration` rows so nothing downstream changes.
  - Item 14 (line-manager view and escalation: email when someone on the team goes overdue) and item 15 (scheduled/emailed reports; move at-risk rules out of code) are adjacent consumers of overdue/at-risk data. Notification email (`user-communication-2-notification-email`) is the delivery path for reminders.

status: ok
