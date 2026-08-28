# Research: deletion semantics

## Executive summary

`FormProgress.form`, `TopicProgress.topic`, `CourseProgress.course`, `CourseProgress.learner`,
`CourseProgress.learner_registration` and `CourseProgress.cohort_registration` are all `PROTECT`
(`freedom_ls/form_engine/models.py:198-200`, `freedom_ls/learner_progress/models.py:84-86,109-132`).
`danger_content_delete` already clears every progress table before touching content specifically
because of this (`freedom_ls/content_engine/management/commands/danger_content_delete.py:78-91`). This
is the baseline every open question below has to be consistent with.

One CASCADE below it remains live and reachable: `QuestionAnswer.question` → `FormQuestion`
(`freedom_ls/form_engine/models.py:574`). The `FormQuestion` admin exposes ordinary delete
(`freedom_ls/form_engine/admin.py:68-85`), and deleting one `FormQuestion` erases every learner's
answer to it without touching the `Form` the `PROTECT` above defends — this should become `PROTECT`.

Two more CASCADEs — `LearnerCourseRegistration.collection` and `CohortCourseRegistration.collection`
(`freedom_ls/learner_management/models.py:111-115,135-139`) — are **already closed in practice**. Every
registration that has ever been active mints a `CourseProgress` row on `post_save`
(`freedom_ls/learner_progress/signals.py:182-215`), and `CourseProgress`'s grant FKs are `PROTECT` —
Django's delete collector walks the whole graph before executing, so a `Course` delete that would
cascade into such a registration is already blocked before it starts. The only registrations left
exposed are ones that never went active (`is_active=False` from creation, or a raw fixture load,
`signals.py:195-199`), which carry no progress to lose. `PROTECT` directly on both fields is still worth
adding — it is one line, changes no behaviour today, and stops depending on a second model's cascade
policy to do this model's job — but it closes a defence-in-depth gap, not a live one. `RecommendedCourse.collection`,
`CourseInterest.course` and `CourseApplication.course` are correctly `CASCADE`: pre-registration signals
with nothing protected behind them.

`QuestionAnswer.selected_options`' M2M has no `on_delete` lever Django exposes at all — deleting a
`QuestionOption` silently drops the join row from every answer that selected it, `PROTECT` on
`QuestionAnswer.question` notwithstanding. Of the three fixes on the table, locking delete out of the
admin is free, immediate, and is also the one thing that closes this gap and the `QuestionAnswer.question`
gap at once, because both live at the same surface (§6). An explicit `through` model is the one option
that is genuinely cheaper now than after deploy. A frozen answer-text snapshot was already declined for
this cut (`idea.md`, Decision 3) as a feature question, not a schema one.

Three deadline models' `content_type` GFK is `CASCADE` against the codebase's own precedent for a
nullable content pointer — `TopicProgress.collection_item`, `CourseProgress.last_accessed_item` and
`CourseFormAttempt.collection_item` are all `SET_NULL` (`learner_progress/models.py:75-81,147-153,
261-267`) — and each deadline model's own `clean()` already treats a null pair as "whole-course
deadline", so `SET_NULL` degrades into an already-tested state. `WebhookDelivery.endpoint` is `CASCADE`
and reachable — its admin has no delete restriction — while `WebhookDelivery.event` is `CASCADE` but not
reachable through any admin action at all, because `WebhookEvent` and `WebhookDelivery` both already
hard-disable add/change/delete in their `ModelAdmin`. That pattern — disabling delete in the admin rather
than changing the schema — is exactly the fix this file recommends for the content models: the Django
admin fully exposes delete on `Form`, `FormQuestion`, `Topic`, `Course`, `CoursePart` and `FormPage`
today, which contradicts `docs/product/content-editing-workflow.md:19`'s "no admin-side or browser-based
authoring interface", and is the only live surface any of the CASCADEs above ever fire from — re-import
is upsert-only and never deletes, and `danger_content_delete` is a separate, deliberately-named command.

## 1. Content-facing CASCADEs that remain

| Field | Target | Current | Verdict |
|---|---|---|---|
| `QuestionAnswer.question` (`form_engine/models.py:574`) | `FormQuestion` | CASCADE | **PROTECT** |
| `LearnerCourseRegistration.collection` (`learner_management/models.py:111-115`) | `Course` | CASCADE | Already transitively PROTECTed — make explicit |
| `CohortCourseRegistration.collection` (`learner_management/models.py:135-139`) | `Course` | CASCADE | Same |
| `RecommendedCourse.collection` (`learner_management/models.py:330-334`) | `Course` | CASCADE | Keep |
| `CourseInterest.course` (`course_interest/models.py:33-37`) | `Course` | CASCADE | Keep |
| `CourseApplication.course` (`course_applications/models.py:37-41`) | `Course` | CASCADE | Keep, reassess when application review lands |

**`QuestionAnswer.question`.** Deleting a `FormQuestion` cascades to every `QuestionAnswer` that
answered it, regardless of whether its `Form` has any other progress against it — `FormProgress.form`
being `PROTECT` only stops the whole `Form` from being deleted, it says nothing about one `FormQuestion`
being trimmed off it. This is a live path: `FormQuestionAdmin` (`form_engine/admin.py:68-85`) is a plain
`SiteAwareModelAdmin` with no delete restriction, and deleting a question also cascades its
`QuestionOption` rows (`form_engine/models.py:175-177`, CASCADE), taking any `selected_options` join
rows with it. `PROTECT` closes the FK half of this; it does not close the M2M half (§3).

**`LearnerCourseRegistration.collection` / `CohortCourseRegistration.collection`.** `ensure_course_progress_on_learner_registration`
and `ensure_course_progress_on_cohort_registration` (`learner_progress/signals.py:182-215`) mint a
`CourseProgress` row via `ensure_course_progress_record` on every `post_save` where `instance.is_active`
is true — including the first save. `CourseProgress.learner_registration` and `.cohort_registration`
are `PROTECT` (`learner_progress/models.py:119-132`). Django's `Collector` gathers the full delete graph
(including everything a `CASCADE` would pull in transitively) before executing any delete, and raises
`ProtectedError` the moment it finds a `PROTECT`'d reverse relation anywhere in that graph — so a `Course`
delete that would `CASCADE` into a `LearnerCourseRegistration` with a `CourseProgress` behind it never
reaches the database at all; the whole transaction aborts first. The gap is narrow: a registration
created with `is_active=False` (or loaded via `raw=True` fixture data, `signals.py:191-199,211`) never
gets a `CourseProgress` row, so it has nothing transitively protecting it — but such a registration also
has no progress to lose. `PROTECT` directly on both fields regardless costs nothing today, removes the
reliance on a second model's policy to do this model's job, and covers the never-activated edge case for
free.

**`RecommendedCourse.collection` / `CourseInterest.course` / `CourseApplication.course`.** None of the
three has any progress, answer or registration hanging off it. `RecommendedCourse` is keyed on `User`,
not `Learner`, and is a suggestion, not an enrolment. `CourseInterest` is a "notify me" signal
(`course_interest/models.py:1-7`). `CourseApplication` today holds only `user`, `course` and timestamps
— its own docstring documents that application review will later add `ApplicationNote`,
`ApplicationStateTransition` and a decision state machine (`course_applications/models.py:22-29`); once
an application carries an approve/reject decision, deleting the course out from under it changes from
"discard a stale preference" to "erase a decision record", and that spec should reassess `on_delete`
when it lands. Not this unit's call to pre-empt.

## 2. The already-PROTECT baseline

| Field | Target | on_delete |
|---|---|---|
| `FormProgress.form` (`form_engine/models.py:198-200`) | `Form` | PROTECT |
| `TopicProgress.topic` (`learner_progress/models.py:84-86`) | `Topic` | PROTECT |
| `CourseProgress.course` (`learner_progress/models.py:112-114`) | `Course` | PROTECT |
| `CourseProgress.learner` (`learner_progress/models.py:109-111`) | `Learner` | PROTECT |
| `CourseProgress.learner_registration` (`learner_progress/models.py:119-125`) | `LearnerCourseRegistration` | PROTECT |
| `CourseProgress.cohort_registration` (`learner_progress/models.py:126-132`) | `CohortCourseRegistration` | PROTECT |

`danger_content_delete` clears `QuestionAnswer`, `CourseFormAttempt`, `FormProgress`, `TopicProgress`
and `CourseProgress` before deleting any content row, in that order, specifically because these
`PROTECT`s exist (`content_engine/management/commands/danger_content_delete.py:78-91`). Every
recommendation in this file that proposes a new `PROTECT` is proposing the same shape of rule this
baseline already enforces, not a new principle.

## 3. The `QuestionAnswer.selected_options` M2M gap

Django generates the through table for `QuestionAnswer.selected_options` (`form_engine/models.py:575-577`)
automatically and exposes no `on_delete` on either of its two FKs. Deleting a `QuestionOption` — whether
directly (`QuestionOptionAdmin`, `form_engine/admin.py:24-29`, no delete restriction) or transitively via
its `FormQuestion` — silently drops the join row from every `QuestionAnswer` that had selected it. No
`on_delete` value on `QuestionAnswer.question` touches this: the M2M is a separate relation with its own
separate, lever-less delete path.

Three fixes were on the table for this cut:

1. **An explicit `through` model**, giving `QuestionOption` its own `PROTECT`'d FK from the join row.
   This is the one option whose cost genuinely differs by timing: today, with zero `selected_options`
   rows in existence, replacing the implicit through table is a bare migration. Once real answers exist,
   the same change needs a data migration that recreates every join row in the new table before dropping
   the old one. This is the option with a real pre-deploy deadline, if it is the one chosen.
2. **A frozen text snapshot** (`question_text` / `selected_option_texts` on `QuestionAnswer`) — the only
   fix that survives the M2M gap without touching `on_delete` at all, since a snapshot taken at answer
   time doesn't care what happens to the `QuestionOption` row afterwards. Already declined for this cut
   (`idea.md`, Decision 3): adding a nullable field costs the same before or after deploy, so there is no
   pre-deploy deadline attached to the field itself — only to *backfilling* real value into it, and that
   gate is "before the first real answer exists" (deploy time), not this cleanup's own deadline. This is
   a feature decision for whichever spec ends up owning answer provenance, not a schema fix.
3. **Lock delete out of the admin** for `QuestionOption` (and `FormQuestion`, which cascades into it) —
   no migration, no schema change, works immediately, and is the only one of the three that also closes
   the plain-FK gap in §1 at the same time, because both gaps are reachable through the exact same admin
   surface. No pre-deploy deadline either way.

**Cheapest: option 3.** It requires no migration and directly targets the one surface every CASCADE in
this file is reachable through (§6). It does not substitute for the `PROTECT` changes in §1 — those still
matter for any path other than the admin, including `danger_content_delete` and any future API — but it
is the fix that costs nothing and closes the most ground per line changed.

## 4. The deadline models' GFK `content_type` FKs

| Field | Target | Current | Verdict |
|---|---|---|---|
| `CohortDeadline.content_type` (`learner_management/models.py:166-171`) | `ContentType` | CASCADE, `null=True` | **SET_NULL** |
| `LearnerDeadline.content_type` (`learner_management/models.py:213-218`) | `ContentType` | CASCADE, `null=True` | **SET_NULL** |
| `UserCohortDeadlineOverride.content_type` (`learner_management/models.py:261-266`) | `ContentType` | CASCADE, `null=True` | **SET_NULL** |

All three pair `content_type` with a nullable `object_id` behind a `GenericForeignKey` naming the
`Topic`/`Form` a deadline applies to. This is the same shape the codebase already resolves with
`SET_NULL` three times over on the concrete side of an equivalent pointer: `TopicProgress.collection_item`,
`CourseProgress.last_accessed_item` and `CourseFormAttempt.collection_item` are all
`on_delete=models.SET_NULL` (`learner_progress/models.py:75-81,147-153,261-267`), each documented as
existing so removing what the pointer names doesn't destroy the record holding it. `CourseProgress`'s
content pointer used to be a bare `GenericForeignKey` (`last_accessed_content_type`); it is now a concrete
FK to `ContentCollectionItem` (`last_accessed_item`), still `SET_NULL`, and that is the current precedent
to match — not the field name above, which no longer exists.

Each deadline model's own `clean()` already treats a null `(content_type, object_id)` pair as "this is a
whole-course deadline" (`learner_management/models.py:186-197,233-244,286-311`), so `SET_NULL` degrades
a deadline that loses its target into a state the model already validates and displays correctly
(`"Whole course"`, e.g. `models.py:201-202`), rather than deleting the deadline row outright. No live
behaviour changes today: a `ContentType` row is deleted only by `remove_stale_contenttypes`, which fires
after a model is removed from the codebase entirely, not through any admin or content-authoring action.

## 5. Audit trails that die with their subject

| Field | Target | Current | Reachable via admin? | Verdict |
|---|---|---|---|---|
| `WebhookDelivery.event` (`webhooks/models.py:376-378`) | `WebhookEvent` | CASCADE | No — both models hard-disable delete | Keep, inconsistent in principle but dead in practice |
| `WebhookDelivery.endpoint` (`webhooks/models.py:379-381`) | `WebhookEndpoint` | CASCADE | Yes — no override | **SET_NULL** (needs `null=True`) or **PROTECT** |

`WebhookEventAdmin` and `WebhookDeliveryAdmin` both override `has_add_permission`, `has_change_permission`
and `has_delete_permission` to return `False` unconditionally (`webhooks/admin.py:183-194,228-239`), so
neither a `WebhookEvent` nor a `WebhookDelivery` can be deleted through the admin at all — the `CASCADE`
on `WebhookDelivery.event` has no live surface to fire from. `WebhookEndpointAdmin`
(`webhooks/admin.py:22-174`) carries no such override, so an endpoint can be deleted through the ordinary
admin delete action, which cascades away every delivery attempt, status code and response body ever
recorded against it (`webhooks/models.py:382-391`) — the entire audit trail for that endpoint, gone with
a routine "rotate this endpoint" action. This is the one CASCADE in the whole matrix where the data lost
is debugging/compliance evidence rather than learner progress, and it is currently the more reachable of
the two `WebhookDelivery` CASCADEs, not the less. `SET_NULL` needs `endpoint` to become nullable;
`PROTECT` needs nothing added but blocks deleting an endpoint with any delivery history at all, which for
a "disable and replace" workflow may be too strict — `SET_NULL` paired with denormalising
`WebhookEndpoint.url` (`webhooks/models.py:49`) onto `WebhookDelivery` keeps the history self-describing
after the endpoint is gone.

## 6. The live delete surfaces

Content re-import is upsert-only, keyed on the frontmatter UUID
(`content_engine/management/commands/content_save.py`, per `docs/product/content-editing-workflow.md:78`)
— it never deletes a row, so the routine authoring workflow never fires any CASCADE in this file.
`danger_content_delete` is the one command that does, and it is deliberately named to require considered
invocation (`content-editing-workflow.md:80`) and already clears progress first (§2).

The other path is the Django admin, and it contradicts the documented authoring model.
`content-editing-workflow.md:19` states plainly: "There is no admin-side or browser-based authoring
interface." In the shipped code, `TopicAdmin`, `ActivityAdmin`, `CourseAdmin`, `CoursePartAdmin`,
`ContentCollectionItemAdmin` and `FileAdmin` (`content_engine/admin.py`) and `FormAdmin`, `FormPageAdmin`,
`FormQuestionAdmin`, `FormContentAdmin`, `QuestionOptionAdmin` and `QuestionAnswerAdmin`
(`form_engine/admin.py`) are all plain `SiteAwareModelAdmin` registrations with no `has_delete_permission`
override — every one of them supports full delete for any staff user holding the relevant Django
permission. That is a real, working authoring-adjacent surface the docs deny exists, and it is also the
only place (besides `danger_content_delete`) any CASCADE in §1, §3 or §4 can actually fire from.

The codebase already has, and uses, the alternative: `webhooks/admin.py` shows `has_add_permission`,
`has_change_permission` and `has_delete_permission` all overridden to `False` on two models
(`WebhookEventAdmin`, `WebhookDeliveryAdmin`, §5) specifically because they are audit records that
should never be hand-edited or removed through the UI. Applying the same pattern to
`Form`/`FormQuestion`/`QuestionOption`/`Topic`/`Course`/`CoursePart`/`FormPage` — or a narrower version
gating delete only, since add/change on content models may still be wanted — is strictly cheaper than
any of the schema changes in §1 or §3: no migration, no FK, no M2M, and it closes every gap in this file
that routes through the admin in one change, including the one the M2M in §3 cannot otherwise reach. It
does not replace the `PROTECT`/`SET_NULL` changes elsewhere in this file — `danger_content_delete` and
any future API or shell path bypass admin permissions entirely — but between "lock the admin down" and
"leave the docs wrong", locking it down is the cheaper fix, and between "lock the admin down" and "ship a
new `through` model", locking it down is cheaper still.

## 7. Everything else — no change

**User-side, `CASCADE`, out of scope.** Every FK from a user's own data to `User` stays `CASCADE`,
unchanged: `Learner.user` (`learner_management/models.py:65`), `RecommendedCourse.user` (`:325-329`),
`FormProgress.user` (`form_engine/models.py:201-203`), `CourseInterest.user`
(`course_interest/models.py:28-32`), `CourseApplication.user` (`course_applications/models.py:32-36`),
`LegalConsent.user` (`accounts/models.py:174-178`), and the three `role_based_permissions` assignment
models' `user` fields (`role_based_permissions/models.py:16-20,49-53,83-87`). Whether any of these should
hard-delete, anonymise, or preserve an identity snapshot when a user is deleted is
`user-data-retention-idea.md`'s question, not this unit's.

**Org/site, `PROTECT`, correct.** `SiteAwareModelBase.site` (`site_aware_models/models.py:54`),
`Cohort.organisation` (`learner_management/models.py:33-36`) and `Learner.organisation`
(`learner_management/models.py:66-68`, landed — no longer a sibling-spec plan) are all `PROTECT`,
consistent with `docs/product/roadmap.md:32`'s "no delete or merge" rule for organisations and the
absence of any UI path to delete a `Site`.

**Internal composition, `CASCADE`, correct.** True parent-child relations with no independent existence
on the child side: `CohortMembership.cohort`/`.learner` (`learner_management/models.py:84-85`),
`CohortCourseRegistration.cohort` (`:140-142`), the three deadline models' registration FKs
(`CohortDeadline.cohort_course_registration` `:161-165`, `LearnerDeadline.learner_course_registration`
`:208-212`, `UserCohortDeadlineOverride.cohort_course_registration` `:255-259`), `FormPage.form`
(`form_engine/models.py:83`), `FormContent.form_page` (`:113-115`), `FormQuestion.form_page`
(`:130-132`), `QuestionOption.question` (`:175-177`), `QuestionAnswer.form_progress` (`:571-573`),
`TopicProgress.course_progress` (`learner_progress/models.py:70-72`), `CourseFormAttempt.course_progress`
(`:254-256`) and `CourseFormAttempt.form_progress` (`:268-270`, `OneToOneField`). `ContentCollectionItem.collection_type`
and `.child_type` (`content_engine/models/courses.py:274-280,289-291`) are `CASCADE` to `ContentType` and
correct for the same reason as the deadline models' baseline behaviour today: a `ContentType` row is
deleted only after its model leaves the codebase, at which point the rows referencing it are already
garbage.

**Provenance, `SET_NULL`, correct exemplars.** `SystemRoleAssignment.assigned_by`,
`SiteRoleAssignment.assigned_by`, `ObjectRoleAssignment.assigned_by`
(`role_based_permissions/models.py:23-29,56-62,96-102`) and `GeneratedReport.requested_by`
(`reports/models.py:54-60`) all let the record survive and the "who did this" attribution degrade to
null. `TopicProgress.collection_item`, `CourseProgress.last_accessed_item` and
`CourseFormAttempt.collection_item` (`learner_progress/models.py:75-81,147-153,261-267`) are the current
precedent cited in §4.

**Deliberate, documented, not this unit's call.** `GeneratedReport.cohort`
(`reports/models.py:49-53`) is `CASCADE` by product decision: "removing a report removes its stored
file... as a consequence of deleting its cohort" (`docs/product/roadmap.md:106`).
`ObjectRoleAssignment.content_type` (`role_based_permissions/models.py:88-91`) is `CASCADE` and
non-nullable — the row is meaningless without it, unlike the deadline models' nullable, whole-course-
fallback shape in §4.

status: ok
