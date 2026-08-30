# Research: model-by-model inventory

39 concrete models across 12 apps that own tables, plus two dormant apps (`app_authentication`,
`xapi_learning_record_store`) that own zero tables today, and twelve installed-or-adjacent apps that
have never owned a model at all. No model surveyed is dead, duplicated, or needs deleting. No
`db_table` is set anywhere in the tree (confirmed by exhaustive grep), so every table name below is the
Django default, `<app_label>_<model_name_lower>`.

## Apps that own zero tables

Checked, not missed. `content_base` and `site_aware_models` define abstract model bases only
(`BaseContent`/`TitledContent`/`MarkdownContent` at `freedom_ls/content_base/models.py:10,59,79`;
`SiteAwareModelBase`/`SiteAwareModel` at `freedom_ls/site_aware_models/models.py:53,79`). Both are
`abstract = True`, and neither app has a `migrations/` directory. `base`, `course_access`,
`deployment`, `educator_interface`, `health`, `icons`, `learner_interface`, `markdown_rendering`,
`panel_framework`, `qa_helpers` have no `models.py` at all.

## Dormant apps have zero tables and are out of scope

Neither is in `INSTALLED_APPS` (`config/settings_base.py:99-100`, both lines commented out) and
neither has a `migrations/` directory.

- `app_authentication.Client` (`freedom_ls/app_authentication/models.py:8`) is a real model with a
  plaintext `api_key` `CharField`, one uncommented `INSTALLED_APPS` line away from shipping with no
  hashing or rotation story. It owns no table; nothing to restructure here.
- `xapi_learning_record_store`'s `models.py` is entirely commented-out sketch code
  (`freedom_ls/xapi_learning_record_store/models.py:1-37`). Its `AppConfig.name` is `freedom_ls.xapi`
  (`freedom_ls/xapi_learning_record_store/apps.py:6`), already anticipating the rename
  `xapi_implementation` will do; nothing to fix here either.

## Every model that owns a table

PK type is UUID for every model below except where stated otherwise. Every `SiteAwareModel` subclass
gets `id = UUIDField(primary_key=True, default=uuid.uuid4)`
(`freedom_ls/site_aware_models/models.py:79-80`).

### `accounts` (label `freedom_ls_accounts`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `User` (`accounts/models.py:67`) | `freedom_ls_accounts_user` | `BigAutoField` (int) | Keep | Extends `SiteAwareModelBase`, not `SiteAwareModel`, and `AccountsConfig` sets `default_auto_field = BigAutoField` (`accounts/apps.py:5`), the only model in the tree with an integer PK, deliberately (PK-type consistency is the field-hardening sibling's territory, not re-litigated here). |
| `SiteSignupPolicy` (`:137`) | `freedom_ls_accounts_sitesignuppolicy` | UUID | Keep | Correctly scoped, one row per site (`unique_signup_policy_per_site`, `:152-154`). |
| `LegalConsent` (`:161`) | `freedom_ls_accounts_legalconsent` | UUID | Keep | Append-only by `save()` guard (`:202-206`); correctly placed. |

### `organisations` (label `freedom_ls_organisations`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `Organisation` (`organisations/models.py:58`) | `freedom_ls_organisations_organisation` | UUID | Keep | Deliberately minimal tenancy-layer model; nothing to revisit. |

### `learner_management` (label `freedom_ls_learner_management`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `Cohort` (`learner_management/models.py:32`) | `..._cohort` | UUID | Keep model; **rename constraint** | `unique_cohort_name_per_site` (`:40-44`) is on `(site_id, organisation, name)`, not `(site_id, name)`. The name is stale from before the organisations cut. Rename it to `unique_cohort_name_per_organisation`. Constraint names persist in the database. The rename is free now and cheap forever; left alone, it keeps misdescribing itself to the next reader. |
| `Learner` (`:51`) | `..._learner` | UUID | Keep | The `(user, organisation)` join row the rest of enrolment hangs off (`unique_learner_per_organisation`, `:73-77`). Correctly placed and named. |
| `CohortMembership` (`:83`) | `..._cohortmembership` | UUID | Keep | Keyed `(learner, cohort)` (`:88-93`); `clean()` enforces same-organisation membership (`:95-102`). |
| `LearnerCourseRegistration` (`:108`) | `..._learnercourseregistration` | UUID | **Rename `collection` → `course`** | Settled (premise 1). Field at `:111-115`, constraint `unique_learner_course_registration` at `:120-126`. This is the highest-blast-radius rename in the inventory: 106 files under `freedom_ls/` reference `.collection`/`collection=`/`collection_id` (grep), mixed with the legitimately generic `ContentCollectionItem.collection`, so the two must be told apart during the sweep. At the database level a metadata-only rename costs the same forever; the cliff is that FLS ships as a library, so once a downstream project's own code reads `.collection` off this model, the rename becomes a breaking API change instead of an internal one. |
| `CohortCourseRegistration` (`:132`) | `..._cohortcourseregistration` | UUID | **Rename `collection` → `course`** | Same finding, same file, `:135-139`; constraint `unique_cohort_course_registration` at `:146-152`. |
| `CohortDeadline` (`:158`) | `..._cohortdeadline` | UUID | Keep | Hangs off `CohortCourseRegistration` (`:161-165`); GFK `content_type`/`object_id` nullable-pair means "whole course" (`clean()`, `:186-197`). Correct shape; see the deadline-triplication note below. |
| `LearnerDeadline` (`:205`) | `..._learnerdeadline` | UUID | Keep | Hangs off `LearnerCourseRegistration` (`:208-212`). Renamed from `StudentDeadline` by the landed `learner-terminology-rename` spec; already the current name, nothing further to do. |
| `UserCohortDeadlineOverride` (`:252`) | `..._usercohortdeadlineoverride` | UUID | **Class name is wrong for its own field** | Its only person-identifying field is `learner = models.ForeignKey(Learner, ...)` (`:260`), not a `User`. That field was set by `learners-associated-with-organisations`, which re-keyed it but left the class name from before that spec landed. Every other model in this file that touched a person during that spec (`LearnerCourseRegistration`, `CohortMembership`) already carries `learner` in its name; this one alone still says `User`. A class rename here is metadata-only in Postgres (the table name changes, nothing about the columns does) and touches 12 files today (admin, factories, `deadline_utils.py`, tests, `educator_interface/views.py`, one `qa_helpers` command), all internal to FLS and none of them downstream-project code yet, because FLS has never deployed. That is exactly the same cliff as the `collection` rename, on a smaller footprint: free today, a breaking rename for any downstream project that has already imported this class name after deploy. `UserCohortDeadlineOverride` → `LearnerCohortDeadlineOverride` (or `CohortDeadlineOverride`, since `cohort_course_registration` already names the cohort side) is a do-now-priced item this cut should decide on, not defer. |
| `RecommendedCourse` (`:319`) | `..._recommendedcourse` | UUID | **Rename `collection` → `course` now; app extraction is do-later, not deadline-pressured** | Third member of the "pre-registration intent" family alongside `CourseApplication` (own app, `freedom_ls_course_applications`) and `CourseInterest` (own app, `freedom_ls_course_interest`), both single-model apps with explicit "deliberately minimal and standalone" docstrings (`course_applications/models.py:1-7`, `course_interest/models.py:1-7`). `RecommendedCourse` is structurally identical (`user` FK, `course`-to-be FK, `created_at`) and depends on nothing `course_applications`/`course_interest` don't already depend on, so extracting it to its own app (e.g. `course_recommendations`) adds no new dependency-graph edge. The `collection` field rename (`:330-334`) is the same do-now item as the other two: cheap now, a downstream-breaking rename later. The app move is a different kind of cost. Moving a model between apps after real rows exist needs a state-only migration (`SeparateDatabaseAndState` or equivalent) to keep the table's data while its app-label lineage changes, which Django supports but is genuinely more work than "delete migrations, write a fresh `0001_initial`", the option this project's still-empty database makes available today. That extra cost is real but bounded and well-trodden, so it does not carry the same "point of no return" weight as the `collection` rename. `idea.md`'s own sequencing already places both the `RecommendedCourse` move and the field rename before the project-wide migration reset (Decision 4), which is the cheapest possible moment to do the move. After that reset, it is still doable, just no longer free. Do the field rename now; do the app move at the same time as (or immediately before) the migration reset, not after it. The commented-out `form_progress` FK (`:335-337`) documents a real, deliberately-deferred future link to a `FormProgress`, confirmed present and unaltered by any landed spec. It is not a TODO/`@claude` comment; leave it exactly as is. |

**Deadline-triplication re-assessment (still won't-do, re-verified against current code):**
`CohortDeadline`, `LearnerDeadline`, `UserCohortDeadlineOverride` are near-identical by shape
(`deadline`, `is_hard_deadline`, `content_type`/`object_id`/`content_item` GFK) but each hangs off a
different registration-shaped FK. `learner_management/deadline_utils.py:39-329` resolves all three by
name in a fixed priority order (override, then cohort deadline, then course-level fallback for cohort
registrations; item-level, then course-level for individual registrations) and bulk-indexes each one by
its own FK-typed registration id (`:264-299`). `Learner` existing now does not change this: all three
models already point at either `Learner` directly (`UserCohortDeadlineOverride.learner`, `:260`) or at
a registration that itself points at `Learner`. Collapsing them into one polymorphic `Deadline` with a
GFK "owner" would replace three FK-indexed lookups on the hot deadline-resolution path with one GFK
lookup, and would force `deadline_utils.py`'s per-type bulk-fetch-and-index pattern into a single mixed
query it cannot easily stay batched under. This is a real behaviour/performance trade-off, not a naming
cleanup. Won't-do stands.

### `learner_progress` (label `freedom_ls_learner_progress`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `TopicProgress` (`learner_progress/models.py:59`) | `..._topicprogress` | UUID | Keep | Keys on `course_progress` + `collection_item` (`:70-81`), not the bare `topic`. `unique_together` is `(course_progress, collection_item)` (`:94-99`), correctly placement-scoped per `better_course_progress_tracking`. |
| `CourseProgress` (`:106`) | `..._courseprogress` | UUID | Keep | Keys on `learner` plus exactly one of `learner_registration`/`cohort_registration`, enforced by a `CheckConstraint` (`:171-183`) plus two partial `UniqueConstraint`s (`:158-170`). `last_accessed_item` is a `ContentCollectionItem` FK (`SET_NULL`), not the resolved child (`:147-153`). The resume-pointer redesign from `better_course_progress_tracking` is fully landed; the old `last_accessed_content_type` GFK is gone. |
| `CourseFormAttempt` (`:242`) | `..._courseformattempt` | UUID | Keep | Bridges `form_engine.FormProgress` into a course: `course_progress` FK (`:254-256`) + nullable `collection_item` FK (`:261-267`) + `OneToOneField` to `FormProgress` (`:268-270`). No uniqueness constraint on the placement is deliberate: many attempts per placement, one row each, matching quiz-retake behaviour. |
| `CourseItemProgress` (`:19`) | *(no table, abstract)* | — | Keep | Abstract base; `TopicProgress` is its only subclass today. This is what makes an `ActivityProgress(CourseItemProgress)` close to free to add later; see below. |

### `content_engine` (label `freedom_ls_content_engine`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `Topic` (`content_engine/models/topics.py:8`) | `..._topic` | UUID | Keep | Correctly named and scoped (`unique_together = ["site", "slug"]`, `:16`). |
| `Activity` (`:22`) | `..._activity` | UUID | Keep model; **no `ActivityProgress`, genuinely deferrable rather than conveniently deferrable** | See the dedicated answer below. |
| `Course` (`content_engine/models/courses.py:31`) | `..._course` | UUID | Keep | `items` `GenericRelation` to `ContentCollectionItem` (`:91-96`); every reverse relation from a registration/application/interest/recommendation model already says "course" on this side (`learner_registrations`, `cohort_registrations`, `applications`, `interests`, `recommendations`). The naming mismatch is entirely on the FK side (`collection`), not here. |
| `CoursePart` (`:227`) | `..._coursepart` | UUID | Keep | No direct FK back to its owning `Course`. It is reachable only via `ContentCollectionItem`, a deliberate consequence of the shared-content design; not this unit's call to change. |
| `ContentCollectionItem` (`:270`) | `..._contentcollectionitem` | UUID | Keep | The one place `collection` is the *correct* name: a genuine GFK over `Course`/`CoursePart` (`:274-282`). `collection_id`/`child_id` are `UUIDField`s (`:281,292`), consistent with every content model's UUID PK, so there is no GFK-key-type inconsistency here. A commented-out `collection_old` FK (`:284-286`) is dead code left over from the pre-GFK design (superseded by migrations `0003`/`0004`); harmless, but worth deleting in the same pass as anything else that touches this file, since it documents nothing a `@claude`/TODO comment would protect. |
| `File` (`content_engine/models/files.py:30`) | `..._file` | UUID | Keep | Unique on `(site, file_path)` (`:53-54`); the only uploaded-content-asset model. |

### `form_engine` (label `freedom_ls_form_engine`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `Form` (`form_engine/models.py:43`) | `..._form` | UUID | Keep | Landed by `extract_forms_into_seperate_app`; not up for discussion (premise 3). |
| `FormPage` (`:78`) | `..._formpage` | UUID | Keep | — |
| `FormContent` (`:107`) | `..._formcontent` | UUID | Keep | — |
| `FormQuestion` (`:125`) | `..._formquestion` | UUID | Keep | — |
| `QuestionOption` (`:172`) | `..._questionoption` | UUID | Keep | — |
| `FormProgress` (`:193`) | `..._formprogress` | UUID | Keep | The sitting itself (answers, score, completion) is course-blind by design, per the domain glossary; bridged into a course via `learner_progress.CourseFormAttempt`. |
| `QuestionAnswer` (`:568`) | `..._questionanswer` | UUID | Keep | `unique_together = ["form_progress", "question"]` (`:581-582`) is the right key. |

### `role_based_permissions` (label `freedom_ls_role_based_permissions`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `SystemRoleAssignment` (`role_based_permissions/models.py:9`) | `..._systemroleassignment` | `BigAutoField` (int) | Keep | Deliberately not `SiteAwareModel` (own docstring, `:10-14`) since a system role is global; `RoleBasedPermissionsConfig.default_auto_field = BigAutoField` (`apps.py:5`) actually takes effect here, unlike on `webhooks` (see below). |
| `SiteRoleAssignment` (`:46`) | `..._siteroleassignment` | UUID | Keep | Correctly scoped, `unique_site_role_per_user` on `(user, site, role)` (`:66-69`). |
| `ObjectRoleAssignment` (`:80`) | `..._objectroleassignment` | UUID | Keep | `object_id` is `CharField(max_length=255)` (`:92`), not `UUIDField`, deliberately, since its target set is open (any model, not just UUID-keyed content). GFK-key-type unification is field-hardening-sibling territory and is a won't-do there for exactly this reason; not re-argued here. |

### `course_applications` (label `freedom_ls_course_applications`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `CourseApplication` (`course_applications/models.py:17`) | `..._courseapplication` | UUID | Keep, exactly as designed | Docstring (`:1-7`) explicitly pre-declares its own future evolution (FSM state, review workflow) and says not to architect it away. Already named `course`, not `collection` (`:37-41`); unique constraint already includes `site` (`unique_application_per_site_user_course`, `:46-50`). This is the model the others should match, not the other way round. |

### `course_interest` (label `freedom_ls_course_interest`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `CourseInterest` (`course_interest/models.py:17`) | `..._courseinterest` | UUID | **Add `site` to the unique constraint** | `unique_course_interest` is on `(user, course)` only (`:41-44`); its structural twin `CourseApplication.unique_application_per_site_user_course` includes `site`. `User` is itself already site-scoped (`UserManager.get_queryset`, `accounts/models.py:24-32`), so this cannot currently produce a live cross-site duplicate, but the constraint should state what is actually guaranteed, and matching its sibling removes a "why is this one different" question. One-line migration, no data risk. Keep the migration separate from anything `better_course_progress_tracking` does to `LearnerCourseRegistration`'s own constraint: different model, different app, no reason to couple the reverts. |

### `reports` (label `freedom_ls_reports`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `GeneratedReport` (`reports/models.py:42`) | `..._generatedreport` | UUID | Keep | FK `cohort` (`:49-53`) only. No independent `organisation` FK: it is reached via `cohort.organisation`, exactly as `CohortCourseRegistration` deliberately has none, per the organisations cut's "derive through the one owning FK" convention. `reports/indexes.py:44-64` still resolves cohort to organisation this way today. |

### `webhooks` (label: none set, defaults to `webhooks`)

| Model | Table | PK | Verdict | Reason |
|---|---|---|---|---|
| `WebhookEndpoint` (`webhooks/models.py:48`) | `webhooks_webhookendpoint` | UUID | Keep model | App-label fix (adding a `freedom_ls_` prefix) is settled premise 2's territory, not re-decided here; flagged for completeness because it changes every table name in this app. |
| `WebhookEvent` (`:366`) | `webhooks_webhookevent` | UUID | Keep | Correctly separated "what happened" from "did it get there". |
| `WebhookDelivery` (`:375`) | `webhooks_webhookdelivery` | UUID | Keep | Unique on `(event, endpoint)` (`:396-404`). |
| `WebhookSecret` (`:415`) | `webhooks_webhooksecret` | UUID | Keep | Unique on `(site, name)` (`:425-426`). |

`WebhooksConfig.default_auto_field = "django.db.models.BigAutoField"` (`webhooks/apps.py:6`) has never
had any effect. Every model in the app is a `SiteAwareModel` with a UUID PK, so the setting is dead
configuration, not a real integer-PK app. Contrast `role_based_permissions`, where the identical
setting genuinely governs `SystemRoleAssignment`.

## The three deadline models and `Learner`

Answered inline in the `learner_management` table above and its follow-up note: merging remains
won't-do, `UserCohortDeadlineOverride`'s class name is the one real naming defect the `Learner` cut
left behind, and it should be renamed in this pass rather than deferred.

## `Activity`/`ActivityProgress`: the honest answer

No `ActivityProgress` model exists anywhere in the tree (grep, whole `freedom_ls/`), and
`reports/indexes.py:227` says so in a code comment: an `Activity` placed in a course is excluded from
`viewable_items()`'s traversal entirely, "taking them out of the completion denominator too (no
ActivityProgress model exists)". `CourseItemProgress` (`learner_progress/models.py:19-56`) is an
abstract base with exactly one subclass, `TopicProgress`, built by its own shape
(`completion_field_name`, `content_item_field_name`, `newly_completed_item()`) to make a second
subclass close to free.

The honest answer is not "it's cheap so do it anyway" or "it's a gap so it must be fixed". It is that
**this gap carries no pre-deploy deadline at all**, for a reason distinct from the abstract-base
argument: `Activity` is wired all the way through the content pipeline (`content_save.py:27,309-310`,
`admin.py:28-29`, `factories.py:30-36`, `schema.py:40-41`) but is not placed in any course today
(`demo_content/` has zero `Activity` files, per grep). Adding `ActivityProgress` later is purely
additive: a new model, a new FK, no existing row to migrate around, because no course places an
`Activity` yet to have progress against. That is categorically different from the `collection` →
`course` rename or the `UserCohortDeadlineOverride` class rename, both of which get strictly more
expensive after a downstream project starts writing code against today's names. Building
`ActivityProgress` now would be scope creep into a feature this idea explicitly rules out; leaving it
unbuilt costs nothing extra by waiting, pre-deploy or post-deploy alike.

## Is `learner_management` the right app name?

It holds `Cohort`, `Learner`, `CohortMembership`, both course-registration models, all three deadline
models, and `RecommendedCourse`: cohorts and enrolment, deadlines, and a recommendation seed.
"Management" is a vague noun but an accurate one for that span, and nothing narrower covers all seven
models without either fragmenting cohorts from registrations (which query and validate against each
other constantly, see `deadline_utils.py` and `CohortMembership.clean()`) or leaving
`RecommendedCourse` stranded with no obvious other home once it is *not* extracted. This question has
no forcing function: renaming an app after deploy costs exactly what `learner-terminology-rename`
already paid to rename `student_management`, a label rewrite across every migration referencing it,
done once, by that spec's own precedent. There is no cost asymmetry that makes this pre-deploy-urgent
the way the `collection` rename or the `webhooks` label fix are. Leave the name as `learner_management`.
If `RecommendedCourse` moves out to its own app per the verdict above, that alone brings the app closer
to "cohorts, learners, registrations, deadlines", a tighter fit for the existing name, not a reason to
rename it.

## Dead, duplicated, or leftover models

None. The only leftover artifact found is the commented-out `collection_old` field on
`ContentCollectionItem` (`content_engine/models/courses.py:284-286`), which is dead code, not a dead
model; call it out for cleanup rather than give it a verdict of its own. No `Student*` model or app
namespace remains anywhere in `freedom_ls/` (grep for `student_management`, `student_progress`,
`StudentDeadline`, `UserCourseRegistration`: no matches). `learner-terminology-rename` finished cleanly.

status: ok
