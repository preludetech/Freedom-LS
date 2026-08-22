# Research: model-by-model inventory

## Executive summary

Across the 38 concrete models in 11 active apps (plus 2 dormant, uninstalled apps that own no table
today), the great majority are correctly shaped and correctly placed — this is not a codebase that
needs a rewrite. Three findings carry real weight and should be **do-now**: first, three separate
fields (`UserCourseRegistration.collection`, `CohortCourseRegistration.collection`,
`RecommendedCourse.collection`, all in `freedom_ls/student_management/models.py:58,112,304`) are named
`collection` while every one of them is a hard FK straight to `content_engine.Course`, never to a
`CoursePart` or any other collection type — the generic name belongs only to
`ContentCollectionItem.collection` (`content_engine/models.py:393`), which really is a GFK to
`Course|CoursePart`; the two later, better-designed apps `course_applications` and `course_interest`
already call the equivalent field `course` (`course_applications/models.py:37`,
`course_interest/models.py:33`), so this isn't even a consistent legacy convention to preserve, it's a
straight rename to match a pattern the codebase has already converged on elsewhere. Second,
`RecommendedCourse` (`student_management/models.py:293-319`) is the third member of a family of
"pre-registration intent" models — alongside `CourseApplication` and `CourseInterest` — that the other
two members each got their own single-model app for, while this one is buried inside the large,
soon-to-be-renamed `student_management`/`learner_management` app; extracting it into its own small app
now, mirroring `course_applications`/`course_interest`, costs nothing today and avoids it forever
looking like the odd one out. Third, two small constraint-naming/coverage inconsistencies are cheap to
fix now and expensive to notice later: `Cohort`'s unique constraint is literally misnamed
(`unique_cohort_name_per_site` on a `(site_id, organisation, name)` tuple,
`student_management/models.py:24-28`) and `CourseInterest`'s unique constraint omits `site` where
`CourseApplication`'s equivalent constraint includes it (`course_interest/models.py:41-44` vs.
`course_applications/models.py:46-50`). Everything else is either already correctly shaped, already
owned and being fixed by one of the three in-flight sibling specs (flagged inline as "covered by X"
rather than repeated), explicitly and deliberately deferred by the model's own docstring
(`CourseApplication`, `CourseInterest`), or a real but low-priority gap that is cheap to leave alone
because the abstraction it would need already exists (`Activity` has no `ActivityProgress`, but
`CourseItemProgress` is already an abstract base built to support exactly that addition later at zero
structural cost). No model surveyed needs deleting, and the two dormant apps (`app_authentication`,
`xapi_learning_record_store`) own zero tables today — commented out of `INSTALLED_APPS`
(`config/settings_base.py:99-100`) with no migrations directory in either — so they carry no pre-deploy
DB risk and are out of scope for a database-structure cleanup by definition.

## 1. `accounts`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `User` (`accounts/models.py:67`) | The one site-scoped person model; every learner, educator and admin | FK target of nearly every other model in the codebase | Keep as-is | Subclasses `SiteAwareModelBase`, not `SiteAwareModel`, so it alone has a `BigAutoField` int PK while every other model gets a UUID PK (`site_aware_models/models.py:78-82`). That inconsistency is real but is explicitly the sibling **PK-type consistency** research unit's territory — cite it there, not here. |
| `SiteSignupPolicy` (`accounts/models.py:137`) | Per-site signup configuration | One-to-one-ish via `unique_signup_policy_per_site` on `site` | Keep as-is | Correctly scoped, correctly placed; it's account/signup policy, not a generic site-config model. |
| `LegalConsent` (`accounts/models.py:161`) | Append-only consent record | FK `user` (`CASCADE`) | Keep as-is | Deliberately append-only (`save()` rejects updates, `models.py:194-206`), already well hardened. |

## 2. `content_engine`

**Scope note:** whether the `Form`/`FormPage`/`FormContent`/`FormQuestion`/`QuestionOption` cluster
should move to its own app is the explicit subject of a sibling research unit (forms-app extraction).
Every row below states a per-model verdict on naming and relationships only; app-placement for the
forms cluster is intentionally left to that unit and not re-litigated here.

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `Topic` (`content_engine/models.py:145`) | A markdown lesson/content unit | Reverse `progress_records` from `TopicProgress` | Keep as-is | Correctly named, correctly scoped (`unique_together = ["site", "slug"]`). |
| `Activity` (`content_engine/models.py:159`) | A content type distinct from Topic/Form (category + difficulty level) | None — no progress model references it | **Do-later (leave alone for this cut)** | Confirmed by grep and by `spec_dd/3. done/2026-08-21_20:12_basic_reports/research_fls_data_availability.md:12,30,76-78`: there is **no `ActivityProgress` model anywhere**, and `calculate_course_progress_percentage` (`student_management/utils.py:44-54`) only counts `TOPIC` and `FORM` content types — an `Activity` placed in a course's content tree is permanently untracked, not even "not started". This is a genuine content-type-without-a-progress-model gap ("absence of a model is the problem"), but it is cheap to leave for whenever Activity tracking is actually built: `CourseItemProgress` (`student_progress/models.py:36-73`) is already an abstract base purpose-built so a new `ActivityProgress(CourseItemProgress)` subclass is close to free to add later. Building it now would be exactly the "fancy feature" scope creep the idea explicitly rules out. |
| `Course` (`content_engine/models.py:172`) | The top-level ordered content container a learner registers for | `items` `GenericRelation` to `ContentCollectionItem`; reverse `user_registrations`, `cohort_registrations`, `recommendations`, `applications`, `interests`, `progress_records` | Keep as-is | All its reverse `related_name`s already correctly say "course" (`user_registrations` etc. — see §3, §5, §6) even though three of the *forward* FKs pointing at it are misnamed `collection`. The mismatch is on the other end, not here. |
| `CoursePart` (`content_engine/models.py:347`) | A chapter/section within a Course, itself an ordered container | `items` `GenericRelation` to `ContentCollectionItem`; reachable as a *child* of `Course` only via `ContentCollectionItem`, no direct `course` FK | Keep as-is | No direct FK back to its owning Course is a deliberate consequence of the generic placement model (a `CoursePart`, like a `Topic`/`Form`, is technically shareable across courses today, unexercised) — this is the shared-content design `better_course_progress_tracking` already discusses (`research_shared_content_across_courses.md`, referenced in that idea). Not this unit's call to change. |
| `ContentCollectionItem` (`content_engine/models.py:381`) | The through/placement model: orders a child content item within a Course or CoursePart, with per-placement overrides | Double GFK: `collection` (→ Course\|CoursePart) and `child` (→ Topic\|Activity\|Form\|CoursePart) | Keep as-is | This is the one place `collection` is the *correct* name — it genuinely is generic over two collection types via GFK, unlike the three misnamed FKs in §3. `collection_id`/`child_id` are `UUIDField`s consistent with every content model's UUID PK, so no GFK-key-type inconsistency here (contrast `ObjectRoleAssignment.object_id`, a `CharField` — see §4, sibling territory). |
| `Form` (`content_engine/models.py:421`) | A scored/quizzable content type | `pages` reverse from `FormPage`; reverse `progress_records` from `FormProgress` | Keep as-is (placement question owned by forms-extraction sibling) | — |
| `FormPage` (`content_engine/models.py:456`) | A page within a Form | FK `form` (`CASCADE`) | Keep as-is (forms-extraction sibling) | — |
| `FormContent` (`content_engine/models.py:485`) | Static text within a form page | FK `form_page` (`CASCADE`) | Keep as-is (forms-extraction sibling) | — |
| `FormQuestion` (`content_engine/models.py:503`) | A question within a form page | FK `form_page` (`CASCADE`); reverse `options` | Keep as-is (forms-extraction sibling) | — |
| `QuestionOption` (`content_engine/models.py:552`) | An answer option for a `FormQuestion` | FK `question` (`CASCADE`); M2M target of `QuestionAnswer.selected_options` | Keep as-is (forms-extraction sibling) | — |
| `File` (`content_engine/models.py:580`) | An uploaded content asset (image/doc/video/audio) | None inbound; referenced by path from markdown content | Keep as-is | The only uploaded-file model in the whole non-dormant codebase pre-`Organisation.logo`; already unique on `(site, file_path)`, PK-based storage path (`file_upload_handler`, `models.py:570-577`). No structural issue. |

## 3. `organisations`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `Organisation` (`organisations/models.py:28`) | The tenancy layer below Site, above Cohort/registration | FK target of `Cohort.organisation`, `UserCourseRegistration.organisation`; reached transitively by everything else per that spec's Decision 2 | Keep as-is | Freshly shipped (`spec_dd/3. done/2026-08-21_09:09_organisations`), deliberately minimal, deliberately no delete/merge/membership object. Nothing here needs revisiting. |

## 4. `role_based_permissions`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `SystemRoleAssignment` (`role_based_permissions/models.py:9-43`) | A global (non-site) role grant | FK `user` (`CASCADE`), `assigned_by` (`SET_NULL`) | Keep as-is | Deliberately not a `SiteAwareModel` (own docstring says so, `models.py:10-14`) — correct, since a system role is global by definition. |
| `SiteRoleAssignment` (`role_based_permissions/models.py:46-77`) | A per-site role grant | FK `user`; `SiteAwareModel` | Keep as-is | Correctly scoped and named. |
| `ObjectRoleAssignment` (`role_based_permissions/models.py:80-118`) | A per-object role grant via GFK | GFK `target` (any model); `SiteAwareModel` | Keep as-is; one known field-type inconsistency already flagged | `object_id` is `CharField(max_length=255)` (`models.py:92`) rather than `UUIDField`, unlike every content-engine/student-management GFK (§2, §5). This is the exact "GFK key types" item the fixed-decisions brief already names as sibling (field-hardening) territory — flagged here for completeness, not re-decided. |

## 5. `student_management` (renamed `learner_management` by the terminology sibling — see note)

**Note on app rename:** `learner-terminology-rename` (in progress) renames this whole app to
`learner_management` and `StudentDeadline` → `LearnerDeadline`. Every row below is written against
today's names and cites what that sibling already covers so it isn't duplicated.

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `Cohort` (`student_management/models.py:16-32`) | A named group of learners within an Organisation | FK `organisation` (`PROTECT`); reverse `course_registrations`, `reports` | Keep the model; **rename the constraint** | `unique_cohort_name_per_site` (`models.py:24-28`) is a stale name from before the Organisation cut broadened it to `(site_id, organisation, name)` — it should read `unique_cohort_name_per_organisation`. Cheap, mechanical, zero behaviour change, exactly the kind of drift this cut exists to catch before it's baked into anyone's memory of "the" constraint name. **Do-now.** |
| `CohortMembership` (`student_management/models.py:35-48`) | A learner's membership in a Cohort | FK `cohort`, `user` (both `CASCADE`) | Keep as-is | Correctly named and scoped; `Learner` (learners-associated-with-organisations sibling) reads this model, doesn't change it. |
| `UserCourseRegistration` (`student_management/models.py:51-106`) | An individual learner's registration for a course | FK `organisation` (`PROTECT`), `collection`→`Course` (`CASCADE`), `user` (`CASCADE`) | **Rename `collection` → `course`** | See executive summary. `better_course_progress_tracking` adds nullable `user_registration`/`cohort_registration` FKs *from* `CourseRun` *to* this model — it does not touch this model's own fields, so the rename is orthogonal and safe to land independently, ideally in the same restructuring pass since both touch this file. **Do-now.** |
| `CohortCourseRegistration` (`student_management/models.py:109-133`) | A cohort-wide registration for a course | FK `collection`→`Course` (`CASCADE`), `cohort` (`CASCADE`) | **Rename `collection` → `course`** | Same finding, same file. **Do-now.** |
| `CohortDeadline` (`student_management/models.py:135-180`) | A deadline for an entire cohort's course registration | FK `cohort_course_registration` (`CASCADE`); GFK `content_item` (→ Topic\|Form, nullable = whole-course) | Keep as-is | Correctly registration-scoped already — `better_course_progress_tracking`'s own idea doc credits this model as the pattern it's completing (`.../better_course_progress_tracking/idea.md:71-73`). See the deadline-triplication note below. |
| `StudentDeadline` (`student_management/models.py:182-227`) | A deadline for an individually-registered learner | FK `student_course_registration`→`UserCourseRegistration` (`CASCADE`); GFK `content_item` | Rename covered by sibling | `learner-terminology-rename` renames this to `LearnerDeadline` with field `learner_course_registration` (`.../learner-terminology-rename/idea.md:83-91`). **Covered by learner-terminology-rename — no action here.** |
| `UserCohortDeadlineOverride` (`student_management/models.py:229-291`) | A per-user override of a cohort deadline | FK `cohort_course_registration` (`CASCADE`), `user` (`CASCADE`); GFK `content_item` | Keep as-is | Correctly modelled; validated in `clean()` against actual cohort membership (`models.py:263-272`). |
| `RecommendedCourse` (`student_management/models.py:293-319`) | A third-party recommendation that a user take a course (created when "a parent fills out a form") | FK `user` (`CASCADE`), `collection`→`Course` (`CASCADE`) | **Extract to its own small app; rename `collection` → `course`** | This is the third member of the "pre-registration intent" family alongside `CourseApplication` and `CourseInterest` (§6, §7) — those two each got a dedicated single-model app with an explicit "deliberately minimal and standalone" docstring; `RecommendedCourse` is structurally identical (user + course + timestamp, no workflow yet) but is buried inside the large `student_management`/`learner_management` app instead. It depends only on `accounts` and `content_engine`, exactly like its two siblings, so extracting it (e.g. to `course_recommendations`) adds no new cross-app edges beyond what it already has. The mechanics of the new app's label/`db_table` naming are the app-labels sibling's job; the *decision* that it deserves the same treatment as its two siblings is this unit's to make. **Do-now** for the rename (trivial); **do-later** for the app extraction, since it is a bigger, non-trivial move (new app scaffolding, import updates, admin re-registration) that is safe to defer without leaving it more expensive later — nothing about deferring it narrows a constraint or loses data. Leave the commented-out `form_progress` FK (`models.py:309-311`) exactly as it is; it documents a real, deliberately-deferred future link to a specific `FormProgress` and isn't a `@claude`/TODO comment, but there's no cleanup value in touching it either. |

**Deadline-triplication note (won't-do):** `CohortDeadline`, `StudentDeadline`/`LearnerDeadline`, and
`UserCohortDeadlineOverride` are three near-identical schemas (`deadline`, `is_hard_deadline`,
`content_type`/`object_id`/`content_item` GFK), differing only in which registration-shaped thing they
hang off. Consolidating them into one polymorphic `Deadline` model with a GFK "owner" was considered
and rejected: it would trade three small, explicit, easy-to-query FK-typed models for one generic
model with a GFK on the hot deadline-lookup path, which is a real behaviour/performance trade-off, not
a "cheap pre-deploy" rename — and `better_course_progress_tracking` already treats the current
three-model shape as the *correct* pattern to extend, not a smell to fix (see its idea doc line cited
above). **Won't-do.**

## 6. `student_progress` (renamed `learner_progress` by the terminology sibling)

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `FormProgress` (`student_progress/models.py:76-99`) | One attempt at a Form | FK `form`, `user` (`CASCADE`); reverse `answers` | Keep as-is; restructuring covered by sibling | `better_course_progress_tracking` adds a non-nullable `run` FK to `CourseRun` and moves uniqueness to placement-scoped. **Covered by better_course_progress_tracking.** |
| `QuestionAnswer` (`student_progress/models.py:483-500`) | An answer to one question within a `FormProgress` attempt | FK `form_progress`, `question` (`CASCADE`); M2M `selected_options` | Keep as-is | Correctly scoped, `unique_together = ["form_progress", "question"]` is the right key. |
| `TopicProgress` (`student_progress/models.py:503-524`) | A user's progress through one Topic | FK `user`, `topic` (`CASCADE`) | Keep as-is; restructuring covered by sibling | Gains non-nullable `run` FK, placement-scoped uniqueness. **Covered by better_course_progress_tracking.** |
| `CourseProgress` (`student_progress/models.py:527-571`) | A user's progress through one Course | FK `user`, `course` (`CASCADE`); GFK `last_accessed_item` | Renamed/restructured by sibling | Becomes `CourseRun` with `user_registration`/`cohort_registration` provenance FKs and `is_current`. **Covered by better_course_progress_tracking** — including the `student_progress → student_management` edge that exists solely because `calculate_course_progress_percentage` lives at `student_management/utils.py:15` (verified fact): once `CourseRun` carries its own registration FKs directly, that utility's reason to live outside `student_progress` weakens, which is worth a one-line note in that spec rather than a separate item here. |

## 7. `course_applications`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `CourseApplication` (`course_applications/models.py:17-54`) | A learner's request to access an application-gated course | FK `user`, `course` (`CASCADE`) | Keep as-is, exactly as designed | The model's own docstring (`models.py:1-30`) explicitly pre-declares its own future evolution (FSM state, review workflow, application forms) and says "do not architect these away — leave this model standalone and additive." Already correctly named (`course`, not `collection`) and already includes `site` in its unique constraint (`unique_application_per_site_user_course`, `models.py:46-50`) — the model to match, not to change. |

## 8. `course_interest`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `CourseInterest` (`course_interest/models.py:17-49`) | A learner's expressed interest in a coming-soon course | FK `user`, `course` (`CASCADE`) | **Add `site` to the unique constraint** | `unique_course_interest` is on `(user, course)` only (`models.py:41-44`), while its structural twin `CourseApplication.unique_application_per_site_user_course` (§7) includes `site`. In practice this can't currently produce a cross-site duplicate because `User` itself is already site-scoped (`accounts/models.py:67`, `UserManager.get_queryset` filters by site), but the constraint should say what's actually guaranteed rather than rely on that indirect fact, and matching its sibling model removes a "why is this one different" question for whoever reads both side by side later. One-line migration, no data risk. **Do-now.** |

## 9. `reports`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `GeneratedReport` (`reports/models.py:44-96`) | An async-generated PDF report for one Cohort | FK `cohort` (`CASCADE`), `requested_by` (`SET_NULL`) | Keep as-is | No `organisation` FK, and it shouldn't get one — reachable via `cohort.organisation` exactly like `CohortCourseRegistration` deliberately has no independent `organisation` FK per the Organisation cut's own design (`.../2026-08-21_09:09_organisations/idea.md:27-28`). Consistent with the rest of the codebase's "derive through the one owning FK" convention. |

## 10. `webhooks`

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `WebhookEndpoint` (`webhooks/models.py:48-364`) | A configured outbound webhook target | `SiteAwareModel` | Keep as-is | Mature, already hardened (SSRF checks, secret validation). |
| `WebhookEvent` (`webhooks/models.py:366-372`) | A fired domain event | `SiteAwareModel` | Keep as-is | Correctly separated from delivery (see below). |
| `WebhookDelivery` (`webhooks/models.py:375-412`) | One attempt to deliver one event to one endpoint | FK `event`, `endpoint` (`CASCADE`); unique on `(event, endpoint)` | Keep as-is | Correct split of "what happened" (`WebhookEvent`) from "did it get there" (`WebhookDelivery`) — not a fusion candidate. |
| `WebhookSecret` (`webhooks/models.py:415-430`) | An encrypted per-site secret referenced by templates | `SiteAwareModel`; unique `(site, name)` | Keep as-is | — |

## 11. `app_authentication` (dormant — not in `INSTALLED_APPS`)

| Model | Represents | Relationships | Verdict | Reasoning |
|---|---|---|---|---|
| `Client` (`app_authentication/models.py:8-43`) | An API client credential for external-system authentication | `SiteAwareModel`; self-generating `api_key` | Out of scope — leave dormant | Commented out of `INSTALLED_APPS` (`config/settings_base.py:99`) and has no `migrations/` directory at all — it owns **zero database tables** today, so it carries zero pre-deploy DB risk and there is nothing to restructure. Deciding whether/how to activate `app_authentication` is a feature decision for a future spec, not this cleanup. If it is ever activated, its shape (UUID `SiteAwareModel`, self-generating secret) is already consistent with the rest of the codebase — no structural surprise waiting. |

## 12. `xapi_learning_record_store` (dormant — not in `INSTALLED_APPS`)

No concrete models — `models.py` is entirely commented-out sketch code (`xapi_learning_record_store/models.py:1-37`). Same verdict as `app_authentication`: zero tables, zero pre-deploy risk, out of scope.

## Risks and gotchas

1. **The three `collection` fields are the single highest-value rename in this whole inventory, and it must land before the FK is ever queried from outside `student_management`.** `course_access`, `qa_helpers`, `educator_interface`, `reports`, and every factory/test touching `UserCourseRegistration`/`CohortCourseRegistration`/`RecommendedCourse` currently write `.collection`/`collection=`. This is a field rename, not a new column — it touches every call site, not just the model file, and should be scoped and swept exhaustively (grep for `\.collection\b` and `collection=` across `freedom_ls/`) in the same change, or it will fail loudly (attribute errors) rather than silently, which is the good failure mode but still needs budgeting.
2. **`RecommendedCourse`'s app extraction should not be done in the same change as the `collection` → `course` rename**, even though both touch the same model. Moving a model to a new app changes its migration app-label lineage (a fresh `0001_initial` in the new app, a `DeleteModel`-equivalent in the old one, or a `state_operations`-based move) — that is squarely the squash-vs-rewrite migration-strategy sibling's decision to make, and stacking an app move on top of a field rename in one migration risks conflating two independent judgement calls. Do the field rename first (cheap, self-contained); let the app-extraction land whenever the migration-strategy question is settled.
3. **The `Cohort` constraint rename (`unique_cohort_name_per_site` → `unique_cohort_name_per_organisation`) touches error-message assumptions.** Any test or view that asserts on the constraint name in an `IntegrityError` message (grep for the literal string) needs updating in the same change, or the rename will pass `makemigrations`/`migrate` cleanly but silently break an assertion that was never exercised against the new name.
4. **`Activity`/`ActivityProgress` and the deadline-triplication question are both genuine findings that this cut deliberately leaves alone** — say so explicitly in the refined idea's do-later/won't-do rows rather than letting them read as oversights. Both were evaluated and rejected for this pass on cost/benefit grounds stated above, not missed.
5. **Do not let the `CourseInterest` unique-constraint fix (item 8) get bundled with the `better_course_progress_tracking` sibling's own constraint work** on `UserCourseRegistration` (its idea doc explicitly discusses whether that model's unique constraint needs to change). They are different models in different apps; keep the migrations separate so a revert of one doesn't have to touch the other.

status: ok
