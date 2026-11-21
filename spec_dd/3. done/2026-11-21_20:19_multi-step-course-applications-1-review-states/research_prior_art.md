# Research: prior art for application states, review and withdraw

Scope: what earlier FLS specs and code settled that `multi-step-course-applications-1-review-states` must honour or not repeat. Sources are in-repo only (no web sources). Limits: I had no shell, so git history was not read; the done specs and current code stand in for it. The earlier draft `educator-interface-full-polish/application-review-ui/` is no longer in the tree, so it is known only through `research_review_foundations.md`.

Short version:

1. The state field was deliberately held back by three earlier specs, and each left a seam. This spec fills them (section 1).
2. The unconditional unique constraint was made unconditional on purpose in the anonymous-applications spec. Turning it partial touches claim, query, backend and view code that all assume one row per account and course (section 2).
3. `updated_at` is a stored column bumped by hand; a `save()` with `update_fields` that omits `updated_at` will not move it (section 3).
4. The audit log is staff-only and append-only, and keeps names forever. That is why the applicant's own submit and withdraw are not audited (section 4).
5. Organisations: an application FK makes `organisation_of` and `record_entry` work with no extra code, but the choice of organisation has to respect the organisation-courses spec (section 5).
6. The old draft's design is mostly stale; the new idea already rejected the right parts (section 6).
7. Answers to the four up-front questions are in `answers.md` and have knock-on effects for the idea's text (section 7).

---

## 1. The state field was reserved, three times

- `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/1. spec.md` (lines ~162, ~472-477) and `2. plan.md` (~523-530) created `unique_application_per_site_user_course` as a plain constraint. They said the review spec "REPLACES" it with an active-state partial index and adds `state`, decision fields, audit models and a `application_state_changed` signal. The seam is a NOTE block in the model docstring.
- `spec_dd/3. done/2026-09-10_09:45_simple-application-forms/research_draft_and_submit_semantics.md` (section 1) told that spec not to add `state`, `status`, `is_submitted` or `submitted_at` to `CourseApplication`, because they belong to the review spec. It chose "derive draft vs submitted from `FormProgress.completed_time`", and said review could later make `state` agree with it. That derived `is_submitted` is what this spec now flips to "state is the one source".
  - Lesson: `completed_time` (when the sitting was finished) and the new state's submit time are two facts. Keep them from drifting: set state in the same place `form_progress.complete()` runs (`application_check_answers`). The idea already says this.
  - The same file says `FormProgress` ties to a `Form` with `strategy=CATEGORY_VALUE_SUM`, and a direct FK `CourseApplication.form_progress` exists because `(user, form)` lookups can return the wrong sitting. Do not resolve sittings by `(user, form)` in new code.
- `spec_dd/3. done/2026-11-05_12:26_apis-for-lead-monitoring-2-course-applications/1. spec.md` (Out of scope, and the `CourseApplicationApiSerializer` bullet) lists "application review state, decisions and the `view_application` permission" as out, and says `is_submitted` and `submitted_time` "read the model properties, never re-deriving them, so they follow when the application review work adds a `state`". Keep those two serializer fields reading the model; change the properties, not the serializer logic.
- The model, `apply` and `application_status` NOTE blocks quote the old review plan (FSMField, `ApplicationNote`, `ApplicationStateTransition`, `view_application`). The idea says rewrite them. Check the model docstring NOTE still points at `FSMField(protected=True)`; it is stale and the rewrite must say TextChoices plus service functions.

Do not repeat: `research_review_foundations.md` section 8 shows the old draft's `FSMField(protected=True)` fights `get_or_create`, bulk updates and data migrations. Nothing in `pyproject.toml` or `freedom_ls/` uses an FSM library, and the roadmap records "no FSM library".

## 2. The unique constraint and one-application-per-account assumptions

- `freedom_ls/course_applications/migrations/0006_unconditional_unique_application_per_site_user_course.py` removed and re-added the constraint on `("site", "user", "course")`. It was made unconditional in the anonymous-applications work (`spec_dd/3. done/2026-10-12_18:37_ananomous-course-applications/`) so that `claims.attach_to_user` can rely on at most one application per account and course. `research_review_foundations.md` section 8 warns the old draft's "drop the base constraint, add the partial index" is the wrong starting point.
- Places that assume one row, all of which this spec edits:
  - `claims.attach_to_user` (`claims.py` ~330-377): looks up `held` with `.filter(user, course).exclude(pk=application.pk).first()`. "A submitted beats a draft; between two drafts the incoming one wins." If `held.is_submitted`, the incoming application is erased with its applicant (`erase_anonymous_applicant`). A discarded draft goes with its sitting (`_discard_draft`). The user row is locked first because the application lookup locks nothing when the account holds none. Keep that user-row lock when you rewrite the rule.
  - Consequence to specify: with a partial index, a held `rejected` or `withdrawn` application must not make the incoming one disappear. The lookup should narrow to active states, or the closed row is ignored and the incoming one attached. That is the idea's open question about a claim-time rule beyond "prefer the active one".
  - `queries.get_application_for_course` uses `.first()`; it is called from `backends.py` (~131), `views.py` (~163, ~964) and the tests in `tests/test_queries.py`. All need "prefer the active application" ordering (and a closed one only when none is active, for the "apply again" CTA).
  - `views._start_application` uses `get_or_create` then `select_for_update`. With a partial index and a closed row, `get_or_create(site, user, course)` will find the closed row or raise `MultipleObjectsReturned`. It must create a new row when only closed ones exist.
  - `tests/test_models.py` ~76 and `tests/test_views.py` ~3733 pin the old rule and need rewriting.
- The partial index ignores unclaimed rows (no `user`), so two unclaimed applications for one course are not constrained by it; an anonymous applicant is bound by session, not by this index.

## 3. `updated_at` and the touch helper

From `spec_dd/3. done/2026-11-05_12:26_apis-for-lead-monitoring-2-course-applications/1. spec.md` (Decisions and `receivers.py` section), implemented in `freedom_ls/course_applications/receivers.py` (`touch_application_updated_at`, line ~47):

- `updated_at` is a stored `auto_now` column, bumped by children through `CourseApplication._base_manager.filter(<match>).update(updated_at=timezone.now())`. Precedent: `freedom_ls/accounts/signals.py` `touch_user_updated_at`. `_base_manager` is used so it works with no request and a request on another host.
- `Index(fields=["site", "updated_at", "id"], name="courseapp_site_updated_idx")` backs the `updated_since` keyset paging. A state change that does not move `updated_at` makes the change invisible to lead-monitoring consumers.
- The receivers skip saves that touch only fields the API never returns. New columns this spec adds to the API (`state`, organisation id, decision time) are returned, so any write to them must move `updated_at`.
- Lessons:
  - `application.save(update_fields=[...])` only moves an `auto_now` column when `"updated_at"` is in the list. `claims.attach_to_user` does this correctly (`update_fields=["user", "updated_at"]`). Every state-change service function must do the same, or use a plain `save()`.
  - A `QuerySet.update()` or `bulk_update` does not move it; use the touch helper or set `updated_at` explicitly. The idea says the same.
  - Each receiver adds an UPDATE query to its sender's writes, and the earlier spec updated query-count tests to match. Adding state writes will shift query counts in the API and view tests (`test_api.py` pins a bounded query count with `django_assert_max_num_queries`).
  - The prefetch-heavy API queryset must read `state` and the organisation FK from `select_related` or fields on the row; do not add per-row queries.
- The API spec pinned the exact key set and order of the serializer in tests and documented them in `docs/api.md` (with `freedom_ls/api/tests/invariants/test_api_docs.py` checking the example). Adding `state`, organisation id and decision time means updating the serializer tuple, the OpenAPI schema test, `docs/api.md`, and the security doc if exposure changes.
- That spec's out-of-scope list explicitly kept the admin export's output unchanged; this spec is the first to add a `state` column to the export (`resources.py`), so the "existing export tests pass unchanged" constraint no longer holds for it. Keep `answer_cell` and `answer_value` (`form_engine/exports.py`) untouched.

## 4. Audit log decisions

From `spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/1. spec.md` (Decisions 2, 4, 6) and `freedom_ls/audit_log/README.md`:

- `subjects` is a GIN-indexed array of model keys. An application as target gives a History tab; adding the course as a subject puts the entry on the course History.
- Decision 4: write only when state changed, and inside the action's `transaction.atomic()`, so a refused or rolled-back action writes nothing. This matches the idea.
- Decision 6: deleting a user leaves entries, names included (`actor_label`, `target_label`, old and new names in `learner.renamed`). There is no way to rewrite them in code; erasure of audit data is an operator task (`prune_audit_log`). This is why the idea keeps the applicant out of the audit log and keeps applicant names out of `target_label` and `details`. The README (~line 139) says the audit log "records staff actions only"; self-registration writes nothing. The applicant's own submit and withdraw follow that.
- Raw calls with no actor are logged as "System". This spec's `submit` is the applicant's own act, not staff, and the idea does not audit it. Decide how a system-only submit (a form-less course submitted at creation, or the data migration) is treated: no entry, as the idea says.
- Action codes must be `noun.verb`; `audit_log/tests/invariants/test_vocabulary.py` fails any word not in the glossary's "Changes" section (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`). `moved` exists; `approved`, `rejected`, `withdrawn`, `submitted` (if used) do not, and `application` is a new noun. The idea has this right. Plan: edit the glossary, `FLS_AUDIT_ACTIONS`, `AUDIT_ACTION_GROUPS` and the README table in the same change.
- The reject message is stored on the application, not the audit `reason`, because audit rows are read by anyone holding `view_auditlogentry`. `reason` is capped at 500 characters; `details` holds ids and labels only. Prior art for message-on-model: none in FLS; the nearest is the reason pattern in `learner_actions` (reason in the entry, staff-facing only).
- Webhook split: `audit_log/README.md` "Audit actions and webhook event types" says the audit vocabulary and the webhook types differ. No `application.*` webhook exists (`base/webhook_event_types.py`). The idea rules them out.
- `educator-interface-11-audit-log` built the audit log with 0 bugs in QA (`qa_report.md`); nothing there to avoid beyond the decisions above.

## 5. Organisations

- `spec_dd/3. done/2026-10-27_20:02_organisation-courses/` added `Course.organisations` (owners), `Course.shared_with` and `Course.audience`. The idea's rule (one owner: that owner; otherwise the default organisation) follows `research_review_foundations.md` section 3, and `learner_management/queries.py` (`is_organisation_course_expression`, `require_course_open_to`) holds the availability rules. `register_for_course` raises `CourseNotOpenError` if the application's organisation does not own or share the course; spec 3 owns that, not this one.
- `spec_dd/3. done/2026-08-21_09:09_organisations/` (idea, `research_codebase_impact.md`, `upgrade_notes.md`) set the default-organisation invariant: one `is_default` per site, enforced by `one_default_organisation_per_site`. `get_default_organisation(site)` raises `DoesNotExist` if broken, so the data migration must resolve the default per site and not assume one exists for a site with no `Organisation` row (a site created before the receiver ran).
- Migration lesson from `spec_dd/3. done/2026-08-23_17:20_learners-associated-with-organisations/research_migration_and_autocreation.md` and the organisations spec's `research_migration_and_rollout.md`: they backfill in a data migration after adding a nullable FK, then tighten. Follow that three-step shape (add nullable, backfill, then make it non-null if required). The idea does not say whether `organisation` is nullable after the migration; decide in the spec.
- `organisation_of` returns `target.organisation` when the attribute exists, so the FK makes `record_entry` work without code; `PROTECT` on the audit row's organisation means an organisation with applications cannot be deleted if entries exist.
- Multi-tenancy: `CourseApplication` is a `SiteAwareModel`, so lookups from background or API code use `_base_manager` (see the API spec) and the site column stays explicit in constraints (`fls-dev:multi-tenant`; the applying-for-courses plan says "site column explicit").

## 6. What the old review draft got wrong (do not carry over)

Taken from `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md` section 8, with the idea's current stance:

- `changes_requested`, `under_review`, `pick_up`: dropped. The idea and roadmap agree.
- `ApplicationStateTransition`, `ApplicationNote`, `application_state_changed` signal: replaced by the audit log. No notes in v1.
- Guardian grants on submit, a global inbox, Django admin review actions: dropped. The admin stays read-only (`admin.py` has add/change/delete refused, with `CourseApplicationSubmittedFilter` and `EmailVerifiedFilter`); the filter becomes a state filter.
- "Approval is not enrolment": reversed by the effort (approval registers the learner), but that belongs to spec 3.
- Stale QA scaffold: `qa_helpers/management/commands/qa_create_application_review_accounts.py` seeds a staff reviewer for admin pages; leave it, but do not extend it for this spec. Reviewer accounts are spec 2.

## 7. Notes on `answers.md` against the idea

- Reject message required: the service function refuses an empty message, and the field is a required `TextField` or a service-only check. The idea says "carries a message the applicant sees"; the answer makes it mandatory. A data migration needs no value for existing rows (none are rejected).
- Approve and reject act on `submitted` only. A refused transition "raises"; define the exception type once (compare `CourseNotOpenError`, `learner_actions` raising specific exceptions) and reuse it for withdraw from a closed state. The idea also says approving an unclaimed application (`user is None`) is refused.
- The dashboard panel keeps closed (rejected and approved) applications visible. This contradicts the idea's line that `get_active_applications` "narrows to active applications"; the idea's text and the `get_active_applications` docstring both need to change, and the panel needs a closed-state presentation (the reject message). Withdrawn applications are not mentioned: decide whether the panel shows them. That affects `queries.get_active_applications`, `panel_rows` (which already prefetches `course__organisations`), the dashboard partial and its tests.
- Withdraw confirm dialog: use the existing confirm pattern in `fls-dev:templates_and_cotton` and keep withdraw a POST. HTMX validation errors return 422 (project rule).

## 8. Checklist of existing code and tests this spec has to touch

- `course_applications/models.py` (state, organisation, decision fields, constraint, properties, NOTE rewrite).
- `course_applications/views.py` (`_start_application`, `application_check_answers`, `apply`, `application_status`, withdraw view).
- `course_applications/claims.py` (`attach_to_user`), `receivers.py` (`adopt_anonymous_applications_on_login`; touch helper for any bulk update), `queries.py`, `backends.py` (`_gated_decision` CTA).
- `course_applications/api.py`, `resources.py`, `admin.py`, `erasure.py` (erase paths must not leave audit entries naming the applicant; none are written for applicants, so only check).
- `audit_log` (registry, README), glossary skill, `docs/api.md`.
- Data migrations: state per sitting; organisation per course owners; partial unique index replacing `0006`'s constraint.
- Tests that pin the old behaviour: `tests/test_models.py`, `tests/test_queries.py`, `tests/test_views.py`, `tests/test_api.py`, `tests/test_receivers.py`, `tests/test_admin.py`, and the vocabulary invariant.

status: ok
