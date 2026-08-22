# Research: deletion semantics

## Executive summary

Change nine `on_delete` values from `CASCADE` to `PROTECT` before deploy, and add one small
denormalised column — everything else in the matrix is already correct or is explicitly not this
unit's call. The headline problem is not `QuestionAnswer.question` in isolation (the fact sheet's
framing); it is that **three separate CASCADE chains** all lead to the same place — a hard-deleted
`Form`/`Topic`/`Course` row silently destroying every learner's progress and answers for it, via
`FormProgress.form`, `TopicProgress.topic` and `CourseProgress.course` (`freedom_ls/student_progress/models.py:82-84,512-514,539-541`)
— and fixing only the leaf (`QuestionAnswer.question`, `freedom_ls/student_progress/models.py:489`)
leaves the other two chains open, because deleting a `Form` cascades through `FormProgress` to
`QuestionAnswer` regardless of what `QuestionAnswer.question`'s own policy is. All five should become
`PROTECT`, alongside `UserCourseRegistration.collection` and `CohortCourseRegistration.collection`
(`freedom_ls/student_management/models.py:58-62,112-116`), which are the same class of problem one
level up the object graph. This is cheap and low-risk specifically because there is no production data
yet, and because the codebase already has the correct soft-delete lever for content —
`Course.visibility = HIDDEN` (`freedom_ls/content_engine/models.py:47-52,224-229`) — so a `Course` a
business actually wants to retire was never meant to be hard-deleted while it has real registrations;
`PROTECT` just makes that the enforced behaviour instead of an unwritten convention. Separately, add a
denormalised `question_text`/`selected_option_texts` snapshot to `QuestionAnswer` now (do-now, cheap,
irreversible-to-backfill-later) — this is deliberately **narrower** than the `content_snapshots` spec
(`spec_dd/2. in progress/content_snapshots/0. idea.md`), which snapshots whole content objects for a
different consumer; the two are complementary, not overlapping, and `content_snapshots`'s own open
question ("does `FormProgress` need a content snapshot?", `spec_dd/2. in progress/better_course_progress_tracking/idea.md:143-144`)
should be updated to say `QuestionAnswer` already carries a self-contained one. Three smaller,
independent findings: align `CohortDeadline`/`StudentDeadline`/`UserCohortDeadlineOverride`'s nullable
`content_type` GFK from `CASCADE` to `SET_NULL` to match the precedent `CourseProgress.last_accessed_content_type`
already set (`freedom_ls/student_progress/models.py:554-560`); change `WebhookDelivery.endpoint` from
`CASCADE` to `SET_NULL` so deleting a webhook endpoint config doesn't erase its delivery audit log
(`freedom_ls/webhooks/models.py:379-381`, a new finding not in the brief); and note that Django gives no
`on_delete` lever over `QuestionAnswer.selected_options`'s auto-generated M2M through table
(`freedom_ls/student_progress/models.py:490-492`), which is the strongest argument for the snapshot
column, since it is the only thing that survives a `QuestionOption` being deleted out from under an
answer. `Site` and `Organisation` `PROTECT` (`freedom_ls/site_aware_models/models.py:54`,
`freedom_ls/student_management/models.py:19,56`) are already correct and need no change — keep them,
and note the sibling `learners-associated-with-organisations` spec already extends the same pattern to
its new `Learner.organisation` FK (`spec_dd/2. in progress/learners-associated-with-organisations/idea.md:54-58`).
Everything about *how long* data is kept, *whether* it survives a user's own deletion, anonymisation,
and a canonical `delete_user()` flow is explicitly out of scope and handed to
`spec_dd/1. next/user-data-retention-idea.md` — this unit only decides which FK points get to veto a
delete versus null themselves out.

## 1. The `on_delete` matrix

Every FK and M2M in `freedom_ls/` (non-migration model code), grouped by relationship class. "Recommended"
is a change only where it differs from "Current."

### 1a. Authored content → learner record (the headline group)

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `FormProgress.form` (`student_progress/models.py:82-84`) | `Form` | CASCADE | **PROTECT** | Deleting a `Form` currently wipes every learner's attempt at it, which then cascades further into `QuestionAnswer` regardless of that FK's own policy. This is the actual headline chain, not the leaf FK alone. |
| `TopicProgress.topic` (`student_progress/models.py:512-514`) | `Topic` | CASCADE | **PROTECT** | Same chain, one model over: deleting a `Topic` wipes every learner's completion record for it. |
| `CourseProgress.course` (`student_progress/models.py:539-541`) | `Course` | CASCADE | **PROTECT** | Deleting a `Course` wipes every learner's whole-course progress and resume state, for every learner ever enrolled. This is the most destructive single CASCADE in the schema. |
| `QuestionAnswer.question` (`student_progress/models.py:489`) | `FormQuestion` | CASCADE | **PROTECT** | Needed independently of `FormProgress.form`: a learner can have an in-progress `FormProgress` with **zero** `QuestionAnswer` rows yet (started, nothing answered — `FormProgress.get_or_create_incomplete`, `student_progress/models.py:133-146`), so `FormProgress.form=PROTECT` alone does not stop an author deleting a single already-answered `FormQuestion` off a `Form` that otherwise still has no full-form deletion in flight. Mirrors Moodle's rule: "not possible to delete a question once a quiz has been attempted" (see §6). |
| `QuestionAnswer.selected_options` (M2M, `student_progress/models.py:490-492`) | `QuestionOption` | implicit CASCADE (auto through table) | **No lever available** — mitigate via the snapshot column (§3) | Django does not expose `on_delete` on an auto-generated M2M through table. Deleting a `QuestionOption` silently drops the join row from any `QuestionAnswer` that selected it — no error, no signal. A custom through model with its own `PROTECT`'d FK would fix this but is new complexity not justified for this unit; the denormalised text snapshot is the pragmatic fix. |
| `UserCourseRegistration.collection` (`student_management/models.py:58-62`) | `Course` | CASCADE | **PROTECT** | One level above progress: deleting a `Course` with active individual registrations should not silently delete registration history. Same "use `visibility=HIDDEN` to retire a course" argument applies (see Exec Summary). |
| `CohortCourseRegistration.collection` (`student_management/models.py:112-116`) | `Course` | CASCADE | **PROTECT** | Same, for cohort-wide registrations. |
| `RecommendedCourse.collection` (`student_management/models.py:304-307`) | `Course` | CASCADE | Keep | Pre-registration recommendation only — no learner interaction recorded yet, low stakes. Inconsistent with the rest of this group in form, but there is nothing here worth protecting. |

### 1b. Content structural parent-child (internal to `content_engine`)

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `FormPage.form` (`content_engine/models.py:461`) | `Form` | CASCADE | Keep | True composition — a `FormPage` has no independent existence. Once `FormProgress.form` is `PROTECT` (§1a), Django's deletion collector transitively blocks this whole chain anyway when any progress exists, because `PROTECT` is checked across the entire collected delete graph, not just the immediate parent. |
| `FormContent.form_page` (`content_engine/models.py:491-493`) | `FormPage` | CASCADE | Keep | Same — pure composition, no evidentiary value on its own (it's instructional text, not a question). |
| `FormQuestion.form_page` (`content_engine/models.py:508-510`) | `FormPage` | CASCADE | Keep | Same; protected transitively via `QuestionAnswer.question=PROTECT` once any answer exists. |
| `QuestionOption.question` (`content_engine/models.py:555-557`) | `FormQuestion` | CASCADE | Keep | Same; see the M2M caveat in §1a — deleting an unanswered option is fine, deleting an answered one silently drops the join row regardless of this FK. |
| `ContentCollectionItem.collection_type` / `.child_type` (`content_engine/models.py:385-391,400-402`) | `ContentType` | CASCADE | Keep | Deleting a Django `ContentType` only happens via `remove_stale_contenttypes` after a model itself is removed from the codebase — at that point the collection-item rows referencing it are already garbage. Correct as-is. |

### 1c. User → their data

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `CohortMembership.user`, `.cohort` (`student_management/models.py:36-37`) | `User`, `Cohort` | CASCADE | Keep | Membership is identity, not evidence — dies with either side. |
| `UserCourseRegistration.user` (`student_management/models.py:63`) | `User` | CASCADE | Keep — **hand off to retention spec** | Whether a deleted user's registration history should be hard-deleted, anonymised, or preserved for business/legal reasons is exactly the question `user-data-retention-idea.md` exists to answer. No premature change here. |
| `UserCohortDeadlineOverride.user` (`student_management/models.py:237`) | `User` | CASCADE | Keep | Per-user override, no independent meaning once the user is gone. |
| `RecommendedCourse.user` (`student_management/models.py:299-303`) | `User` | CASCADE | Keep | Same. |
| `FormProgress.user`, `TopicProgress.user`, `CourseProgress.user` (`student_progress/models.py:85-87,509-511,536-538`) | `User` | CASCADE | Keep — **hand off to retention spec** | This is the sharpest edge of the hand-off: once `PROTECT` is added on the *content* side (§1a), a learner's evidence survives content edits, but still dies immediately if the *user* is deleted, with no canonical `delete_user()` flow deciding whether that's correct. Flagging explicitly, not deciding. |
| `QuestionAnswer.form_progress` (`student_progress/models.py:486-488`) | `FormProgress` | CASCADE | Keep | True composition — an answer has no life independent of its attempt. |
| `LegalConsent.user` (`accounts/models.py:174-178`) | `User` | CASCADE | Keep — **hand off to retention spec** | Already flagged as a deliberate-but-unresolved choice in `user-data-retention-idea.md:5,37`. Nothing new to add here; restating it so the refined idea can point at one place. |
| `CourseInterest.user`, `CourseApplication.user` (`course_interest/models.py:28-32`, `course_applications/models.py:32-36`) | `User` | CASCADE | Keep | Pre-registration preference signals, not evidence. |
| `SystemRoleAssignment.user`, `SiteRoleAssignment.user`, `ObjectRoleAssignment.user` (`role_based_permissions/models.py:16-20,49-53,83-87`) | `User` | CASCADE | Keep | Role grants belong to the user; nothing to protect once they're gone. |

### 1d. Org/site → everything

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `SiteAwareModelBase.site` (`site_aware_models/models.py:54`) | `sites.Site` | PROTECT | Keep | Correct. Site deletion is a whole-tenant decommission, not a normal CRUD action, and virtually every row in the schema is site-scoped — cascading it would be an unrecoverable, silent mass-delete. Forcing an explicit "clear everything on this site first" step is the right friction. |
| `Cohort.organisation` (`student_management/models.py:17-20`) | `Organisation` | PROTECT | Keep | Correct, and organisations "ship with no delete" at the UI layer anyway (`docs/product/roadmap.md:32`) — `PROTECT` is defence-in-depth against a direct ORM/shell/admin-command delete, matching the project's own stated intent (`spec_dd/2. in progress/learners-associated-with-organisations/idea.md:55`: "backs up the admin's refusal to delete organisations"). |
| `UserCourseRegistration.organisation` (`student_management/models.py:54-57`) | `Organisation` | PROTECT | Keep | Same. |
| *(sibling spec, not yet landed)* `Learner.organisation` | `Organisation` | PROTECT (planned) | Keep | `spec_dd/2. in progress/learners-associated-with-organisations/idea.md:54-58` already specifies this consistently with the existing two. No conflict, nothing to add. |

### 1e. Internal parent-child (registrations/deadlines/webhooks/permissions)

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `CohortCourseRegistration.cohort` (`student_management/models.py:117-119`) | `Cohort` | CASCADE | Keep | True composition. |
| `CohortDeadline.cohort_course_registration`, `StudentDeadline.student_course_registration`, `UserCohortDeadlineOverride.cohort_course_registration` (`student_management/models.py:138-142,185-189,232-236`) | respective registration | CASCADE | Keep | True composition — a deadline/override has no meaning without its registration. |
| `CohortDeadline.content_type`, `StudentDeadline.content_type`, `UserCohortDeadlineOverride.content_type` (`student_management/models.py:143-148,190-195,238-243`) | `ContentType` | CASCADE, `null=True` | **SET_NULL** | Inconsistent with the precedent the codebase itself already set: `CourseProgress.last_accessed_content_type` is deliberately `SET_NULL` "so deleting a content model type cannot cascade-delete progress" (`student_progress/models.py:551-556`). These three GFKs are the same shape (nullable, polymorphic pointer to a content item) but were left `CASCADE`. Each model's own `clean()` already treats a null `content_type`/`object_id` pair as "whole-course deadline" (e.g. `student_management/models.py:163-175`) — so `SET_NULL` degrades into an already-handled, tested state, whereas `CASCADE` just silently deletes the deadline/override row outright. Cheap, low-risk, no behaviour change today (`ContentType` rows essentially never get deleted outside `remove_stale_contenttypes`), and closes a real inconsistency before it's copied elsewhere. |
| `WebhookDelivery.event` (`webhooks/models.py:376-378`) | `WebhookEvent` | CASCADE | Keep | True composition — a delivery attempt has no meaning without the event it was delivering. |
| `WebhookDelivery.endpoint` (`webhooks/models.py:379-381`) | `WebhookEndpoint` | CASCADE | **SET_NULL** (+ optionally denormalise `endpoint_url`) | New finding, not in the brief. `WebhookDelivery` is itself an audit/evidence record (delivery attempts, status codes, response bodies — `webhooks/models.py:382-391`) for debugging and compliance. Deleting a `WebhookEndpoint` configuration (e.g. rotating to a new URL) currently erases the entire delivery history for it. Same audit-survives-its-subject principle as everything else in this doc; `WebhookEndpoint` has a `url` field (`webhooks/models.py:49`) that could be denormalised onto `WebhookDelivery` cheaply if the history needs to stay self-describing after the endpoint is gone. |
| `GeneratedReport.cohort` (`reports/models.py:51-55`) | `Cohort` | CASCADE | Keep | Deliberate, product-documented: "removing a report removes its stored file, whether deleted singly, in bulk, or as a consequence of deleting its cohort" (`docs/product/roadmap.md:103`). Correct as shipped; not this unit's call to revisit. |
| `ObjectRoleAssignment.content_type` (`role_based_permissions/models.py:88-91`) | `ContentType` | CASCADE | Keep | Django-internal, essentially never fires; not the same nullable-polymorphic-pointer shape as §1e's deadline models (this one is non-nullable — the row is meaningless without it). |

### 1f. Audit/provenance (already-correct exemplars)

| Field | Target | Current | Recommended | Reason |
|---|---|---|---|---|
| `SystemRoleAssignment.assigned_by`, `SiteRoleAssignment.assigned_by`, `ObjectRoleAssignment.assigned_by` (`role_based_permissions/models.py:23-29,56-62,96-102`) | `User` | SET_NULL | Keep | Correct pattern: the role grant survives, the "who granted it" attribution degrades gracefully. |
| `GeneratedReport.requested_by` (`reports/models.py:56-62`) | `User` | SET_NULL | Keep | Same pattern, correct. |
| `CourseProgress.last_accessed_content_type` (`student_progress/models.py:554-560`) | `ContentType` | SET_NULL | Keep | Already the precedent §1e's three deadline models should have followed. |

## 2. The content-versus-evidence question

This is the substantive decision in this unit. Three options exist for "an author deletes or
re-imports a question — does the learner's answer die with it?":

1. **PROTECT** — refuse the delete outright while any answer exists. Recommended (§1a). This is what
   Moodle does in practice (§6): a question cannot be deleted once a quiz has been attempted; it can
   only be hidden/retired. It costs nothing to add now, it is a one-line schema change, and it converts
   an accidental, silent, unrecoverable data loss into a loud, explicit "you can't do that" — the
   correct default when there is no other safety net.
2. **SET_NULL with a denormalised copy of the question text** — allow the delete, but the answer keeps
   a frozen copy of what it was answering. This is a real alternative and is not mutually exclusive with
   option 1 — see §3, where it is recommended as an *addition*, not a replacement, because it also covers
   the M2M gap that no `on_delete` policy can close (§1a).
3. **Leave it to `content_snapshots`** — do nothing on `QuestionAnswer` itself and let the separate
   `content_snapshots` app (`spec_dd/2. in progress/content_snapshots/0. idea.md`) be the system of record
   for "what did this Form look like on date X."

**What must be decided now vs. what `content_snapshots` subsumes:** the `on_delete` policy (option 1)
is a schema decision that must be made now — it is the one thing in this list that is free today and
requires a downstream migration + admin-workflow change later if deferred. The *structural, full-fidelity*
snapshot (whole `Form` with all `FormPage`/`FormContent`/`FormQuestion`, files referenced, hash-based
versioning, a public `take_snapshot()`/`get_snapshot()` API) is squarely `content_snapshots`'s job and
should not be duplicated here — that app is explicitly scoped to be content-engine-only and consumer-agnostic
(`content_snapshots/0. idea.md:21-23`), whereas a per-answer text snapshot is `student_progress`-local,
tiny, and has no dependency on `content_engine` app boundaries at write time. The two are complementary:
`content_snapshots` answers "what did the whole Form look like," a `QuestionAnswer` snapshot answers
"what exact words was this one answer answering," and the latter is materially cheaper to query (no join
into another app) for the by far most common consumer — showing a learner or educator their own past
answer next to what they picked.

## 3. Should `QuestionAnswer` get a snapshot column now

**Yes.** Add two nullable/blank fields to `QuestionAnswer`, populated at write time in
`FormProgress.save_answers()` (`student_progress/models.py:204-225`, where the answer is already being
constructed from `post_data`):

- `question_text` (`TextField`) — a frozen copy of `question.question` at the moment of answering.
- `selected_option_texts` (`JSONField`, list of strings) — frozen copies of the text of whichever
  `QuestionOption`s were selected, for `multiple_choice`/`checkboxes` questions.

This is exactly the kind of addition the idea.md's background section calls out as "cheap to add now
and impossible to backfill later": once real answers exist without this column, there is no way to
reconstruct what a since-edited or since-deleted question/option said at answer time. It is also the
**only** mechanism that survives the M2M gap in §1a — `PROTECT` on `QuestionAnswer.question` stops the
question itself disappearing, but nothing stops a single `QuestionOption` being deleted (an author
correcting a typo'd option, say) and silently dropping the M2M join row, since Django exposes no
`on_delete` lever on an auto-generated through table. A frozen `selected_option_texts` list is
unaffected by that.

This recommendation should be reflected back into `content_snapshots`'s own open question list
(`spec_dd/2. in progress/better_course_progress_tracking/idea.md:143-144`, "Does `FormProgress` need a
content snapshot?") — the answer for the per-question-answer text is "no, `QuestionAnswer` already
carries its own," narrowing what `content_snapshots` needs to solve for `FormProgress` to the structural
question ("what did the *whole form* look like"), not the per-answer one.

## 4. The site and organisation edges

Covered in full in §1d. Both `PROTECT`s are correct and need no change. The only two points worth
stating explicitly for the refined idea:

- `Site` `PROTECT` (`site_aware_models/models.py:54`) is correct because Site deletion is not a normal
  CRUD action anywhere in this codebase — there is no UI path for it, and virtually every model in the
  schema is site-scoped, so a cascading Site delete would be an unrecoverable, silent, whole-tenant
  data-loss event. Requiring the operator to explicitly clear a site's data first is the only sane
  default.
- `Organisation` `PROTECT` (`student_management/models.py:19,56`) is correct and is, per
  `docs/product/roadmap.md:32` ("No delete or merge — an organisation cannot be removed or combined with
  another once created"), currently unreachable through any product UI at all — the constraint exists
  purely as defence-in-depth against a direct ORM/shell/management-command delete, which is exactly what
  a pre-deploy schema hardening pass should leave in place. The sibling `learners-associated-with-organisations`
  spec already extends the identical pattern to its new `Learner.organisation` FK without being asked to
  (`spec_dd/2. in progress/learners-associated-with-organisations/idea.md:54-58`), which is good corroborating
  evidence this is a settled house convention, not a one-off.

## 5. Explicitly out of scope — hand off to `user-data-retention-idea.md`

The following belong to the retention programme, not this schema-cleanup unit, and are listed here so
the refined idea can say so plainly rather than silently drop them:

- Whether `LegalConsent`, `FormProgress`/`TopicProgress`/`CourseProgress`, `QuestionAnswer`, and
  `UserCourseRegistration`/`CohortMembership` should hard-delete with the user (current default,
  `CASCADE` throughout — see §1c), anonymise in place, or preserve an identity snapshot. This unit
  leaves every user-side FK as `CASCADE`, unchanged, and flags it rather than deciding it.
- A canonical `delete_user(user)` flow, replacing "rely on cascade defaults scattered across the
  schema." `user-data-retention-idea.md:26` already names this as the resulting spec's likely deliverable.
- Retention periods (legal minimum/maximum), a deletion-request/erasure workflow, admin tooling for
  handling erasure requests, and backup propagation of a deletion — none of this touches `on_delete`
  choice at all; it is process and tooling built on top of whatever `on_delete` decides.
- Whether a future `certificates` feature (queued, not yet specced) needs a frozen completion record
  independent of a user's cascade-deletable progress — noted as a real future tension (a certificate
  that legally needs to survive even after the underlying `CourseProgress` is gone), but that is
  `certificates`'s own spec's decision when it lands, not retroactively designed here.

## 6. External check

- Django's `PROTECT` "prevents accidental deletion of referenced objects" and is the generally
  recommended safe default for anything an application cannot afford to silently lose, while `SET_NULL`
  is the right choice specifically when "you want to allow deletion while keeping audit records, but
  acknowledge that the foreign key reference will be lost" — matching exactly the split applied in §1
  (evidence → `PROTECT`, provenance-only attribution → `SET_NULL`). [Foreign Keys On_Delete Option in Django Models — GeeksforGeeks](https://www.geeksforgeeks.org/python/foreign-keys-on_delete-option-in-django-models/), [Django on_delete Explained — Glinteco](https://glinteco.com/en/post/what-does-on_delete-do-on-django-models/)
- Moodle's question bank enforces exactly the `PROTECT` behaviour recommended in §1a/§2 at the product
  level, not just the schema level: "It is not possible to delete a question once a quiz has been
  attempted," and attempting to anyway causes Moodle to "pretend to delete it by hiding it" instead — a
  soft-retire pattern this codebase already has an equivalent lever for at the `Course` level
  (`visibility=HIDDEN`, §1a) but not yet at the `Form`/`FormQuestion` level (out of scope to build here,
  worth flagging for a future content-authoring cut). Existing attempts continue to review correctly
  against the retired question. [Moodle: Can't Delete Quiz Questions](https://moodle.org/mod/forum/discuss.php?d=431534), [Moodle Quiz FAQ](https://docs.moodle.org/30/en/Quiz_FAQ)

## Risks and gotchas

1. **`danger_content_delete` will start failing loudly once `PROTECT` lands.** It unconditionally wipes
   every `Topic`/`Course`/`Form`/`FormQuestion`/etc. row in one transaction
   (`content_engine/management/commands/danger_content_delete.py:33-44,72-80`) with no awareness that
   this could ever be blocked. Today it always succeeds because there is no progress data; the moment any
   learner has answered anything, it will raise `ProtectedError` mid-transaction (the whole transaction
   rolls back, so this fails safe, but the command's messaging doesn't explain why). Update its help text
   once §1a lands so an operator hitting this after deploy gets a clear explanation, not a bare traceback.
2. **The Django admin already exposes full delete on `Form`/`FormQuestion`/`Topic`/`Course`/`CoursePart`/`FormPage`**
   (`content_engine/admin.py:73-90,102-127,142-163,186-225,236-259`) via plain `ModelAdmin` registration —
   this directly contradicts `docs/product/content-editing-workflow.md:19` ("There is no admin-side or
   browser-based authoring interface"). This is the actual live surface the `PROTECT` recommendations in
   §1a defend against; it is worth the plan phase either documenting this admin surface honestly or
   deliberately locking it down, since right now the docs and the code disagree about whether it exists.
3. **`content_save.py` never deletes stale content on re-import** — it is upsert-only, keyed by
   frontmatter UUID (`save_with_uuid`, `content_engine/management/commands/content_save.py:256-259`).
   This means the routine authoring workflow (editing files, re-running `content_save`) essentially never
   triggers the CASCADE chains this doc is concerned about; the only two paths that do are the Django
   admin (risk 2) and `danger_content_delete` (risk 1), both of which are already-deliberate,
   already-rare actions. The `PROTECT` changes in §1a are cheap precisely because they only ever fire on
   those two paths, not on everyday content editing.
4. **`QuestionAnswer.selected_options`'s M2M through table has no `on_delete` lever at all** (§1a) — this
   is a structural Django limitation, not a bug to "fix" here. The snapshot column in §3 is the mitigation,
   not a schema change to the M2M itself; don't let the plan phase chase a custom through-model as a first
   resort.
5. **`PROTECT` is not a free lunch once real data exists.** After deploy, any future decision to let
   content authors genuinely retire a `Form`/`Topic`/`Course` that already has learner history will need a
   deliberate soft-delete/archive flag on those content models (mirroring `Course.visibility=HIDDEN`,
   which does not yet exist for `Form`/`Topic`). That is new feature scope, explicitly not this unit's
   job to design — but the plan phase should say so, so `PROTECT` isn't read as "content can never
   change," only "content can't be hard-deleted out from under evidence."
6. **Do not conflate this unit's `PROTECT` recommendation with `better_course_progress_tracking`'s
   `SET_NULL` decision for placements** — they are different deletion axes. `better_course_progress_tracking`
   (`spec_dd/2. in progress/better_course_progress_tracking/idea.md:96-99`) decides what happens when a
   `ContentCollectionItem` *placement* is removed (a `Topic` unlinked from one `Course` but the `Topic`
   itself still exists) — `SET_NULL`, so the completion record survives with no course to point at. This
   unit decides what happens when the `Form`/`Topic`/`Course` row *itself* is hard-deleted — `PROTECT`. Both
   are correct; they answer different questions and must not be merged into one decision in the plan phase.
7. **`WebhookDelivery.endpoint`'s `CASCADE` (§1e) was not in the task brief's verified-facts list** — it
   is a genuinely new finding from this pass, surfaced by applying the same "does an audit record
   survive its subject" test uniformly across the codebase rather than only where the brief pointed.
   Worth a second look in plan phase in case there are other apps with a similar shape not caught here (a
   full `git grep -A5 'related_name="deliveries"'`-style pass was not exhaustive beyond `freedom_ls/`).

status: ok
