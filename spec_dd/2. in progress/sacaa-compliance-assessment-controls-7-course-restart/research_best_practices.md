# Research: best practices for course restart as a registration chain

Scope: established practice for restarting a learner's course while keeping the earlier run immutable and auditable, and modelling runs as a chain of registrations. Fits the owner's decisions in `answers.md`: one registration = one run; a restart supersedes the registration and mints a new one linked back (option C). Labels: (a) stated in a cited source, (b) practice or inference, (?) not verified.

## 1. Prior art: how other systems model "again"

- **Moodle (a):** core course reset can delete data "forever", but the "recompletion" feature and the `local_recompletion` plugin archive completion data and quiz/SCORM attempts instead, keeping or archiving old attempts so the student starts clean. Warwick's guide recommends leaving "Archive completion data" ticked. Archive-not-delete is the accepted pattern for retention. Caveat: the plugin lists support only up to Moodle 4.3 and users report broken archive reports on 5.x, so the archive is a side table that reporting forgets; FLS keeping old rows in place, in the same tables, avoids that.
  - https://moodle.org/plugins/local_recompletion
  - https://warwick.ac.uk/services/digitallearning/support/guides/moodle-guides/mdl-119
  - https://www.github.com/danmarsden/moodle-local_recompletion
- **cmi5 / xAPI (a):** a *registration* is one enrolment instance, and "a new one is created for new enrollments such as recurrent courses or retakes". The registration id persists through completion and review. Within a registration an AU issues at most one Passed and one Completed statement. Sessions are not attempts. So the e-learning standard itself models a retake or recurrence as a new registration with its own completed/passed facts, which matches "one registration = one run" and "`course.completed` once per run". Resume behaviour (Initialized vs Resumed) applies within a registration, not across runs.
  - https://github.com/AICC/CMI-5_Spec_Current/blob/818b03a4bf3d217df168796d35f06c2ba83b1b10/cmi5_spec.md
  - https://adlnet.gov/news/2016/01/08/cmi5-and-the-xapi-scorm-profile
  - SCORM Cloud likewise defines a registration as one learner's instance of one course (https://support.scorm.com/hc/en-us/articles/115000684933-Working-with-launched-xAPI-courses). How SCORM `suspend_data` behaves on a new attempt: not found (?).
- Takeaway (b): the three systems agree that the unit of "a run" is an enrolment/registration, that completion facts belong to that unit, and that a new run gets fresh state while old data stays queryable.

## 2. Regulatory record-keeping expectations

- **SACAA (project facts):** 5-year retention (CAR 141.01.17), Category 3 to 5 "all data kept for 5 years", Category 2 "audit trail" (see `../../1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`). The SA-CATS source of the "two re-writes, redo the course" line was not publicly findable.
- **FAA (a):** 14 CFR 141.101 requires a pilot school to keep a current, accurate record per enrolled student: enrolment date, chronological log, test grades, and the graduation, termination or transfer date; the student may have a copy on request. It states no retention period in the text found. The 1-year retention figure belongs to 14 CFR 142.73 (training centres), "at least 1 year following the completion of training". Neither is the SACAA rule; they show the *content* regulators expect: dated, chronological, per-student, with an end state (graduated / terminated / transferred). A superseded registration with a date and a reason is the equivalent of "terminated" and keeps the chronology.
  - https://www.law.cornell.edu/cfr/text/14/141.101
  - https://www.law.cornell.edu/cfr/text/14/142.73
- **EASA (a, secondary):** ORA.ATO.120 record-keeping: training records kept throughout the course and for three years after completion; the DTO equivalent (DTO.GEN.220) is the same. Verified only through a French DGAC AltMoC and a vendor glossary, not the Easy Access Rules text, so check before citing. Note "after completion": a restarted run that was never completed has no completion date, so retention must be anchored on something that exists (run start, supersede date) or be the longest of the options. The 5-year SACAA rule should be read the same way; the spec should state which date the clock runs from, or decline to build any purge (the idea already leaves deletion to force-delete).
  - https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoC_ORA.ATO_.120.pdf
  - https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoC_DTO.GEN_.220.pdf
- **ICAO Annex 1:** nothing relevant found (?). Not a source for this spec.

Practice that follows (b): a regulator or auditor asks "show me everything this person did, in order, including failed runs, and who decided the restart and why". The chain plus the audit entry must answer that from stored data without reconstruction.

## 3. Data modelling of re-enrolment chains

- **Superseded state vs soft delete (b):** a soft delete (`is_deleted`, `deleted_at`) says "this should not exist"; it hides rows from default managers and invites purge jobs and admin "restore" buttons. A restart's old run is a true historical fact that must stay visible to staff and auditors. Use an explicit lifecycle state with the *successor pointer* instead of a boolean. The owner's "superseded, distinct from `is_active`" is this. `is_active` already means "may the learner use it now" (deregister/reactivate), so overloading it would let reactivate resurrect a closed run; hence "reactivate refuses it".
- **Successor pointer is the state (b):** prefer `superseded_by` (nullable one-to-one self-FK to the new registration) as the single source of truth, and derive "superseded" from `superseded_by IS NOT NULL`, rather than a status column plus a pointer that can disagree. Back-link ("previous") is the reverse accessor. A one-to-one `superseded_by` makes a branching chain impossible at the database level (a registration has at most one successor, and a successor has at most one predecessor). If a visible `superseded_at` is wanted, store it with a check constraint that both are set together.
- **Chain, not tree:** store links, not run numbers, as the truth. `run_number` is derivable; if stored it is denormalised and can drift on a race. If stored, make (learner, course, run_number) uniqueness part of the invariant check.
- **Reason for the run (start reason):** a small choices field on the run (staff restart now; renewal, refresher later). Keep the restart's free-text reason on the audit entry and, for read convenience, one place only (the idea says "stored on the restart only"). Avoid a nullable column on every registration for restart-only data.
- **Cohort-granted learner (answers.md):** the new individual registration carries `previous_registration` pointing at a `CohortCourseRegistration`, which is a different model. Options: a generic FK (avoid), two nullable FKs with a check "at most one set", or a common parent. Two nullable FKs plus a check constraint matches the existing "exactly one grant" pattern on `CourseProgress`. The cohort registration is shared, so it cannot itself become "superseded"; the per-learner closing must live on the learner's progress record (or a per-learner marker). This is the trickiest seam: the superseded flag of a cohort-granted learner belongs on the learner's `CourseProgress` (closed for that learner only), not on the cohort registration. Design this explicitly and test cohort membership changes (move between cohorts, remove and re-add) against it, since `signals.py` carries records on cohort moves.
- **One current run invariant (b):** at most one non-superseded registration per (site, learner, course) *for individual grants*. Express as a partial unique constraint (section 6). Cohort-granted plus individual-granted coexistence is already allowed today; define "current" via the existing resolution order plus "skip superseded".
- **Readers (b):** put "current run" behind one manager/queryset method (for example `.current()` excluding superseded) and make hand-written `CourseProgress` / registration filters fail review. This is what the repo already says about `course_progress_for`. Reporting should expose the chain as a labelled list ("Run 1: restarted on D by X, Run 2: ...") rather than silently dropping superseded rows.
- **Completion across reruns (b):** completion date, scores and `completed_time` live on the run's progress record and are never rewritten by a later run. "Certified on date D" is answered from the earliest/latest *completed* run, so reporting needs "latest completed run" and "current run" as two distinct notions (a renewal can be current and incomplete while the previous run still evidences certification). Attempt counters and learning-time totals are per run; never aggregate across runs unless a spec says so (the 2-rewrite cap, if built, counts runs by start reason).
- **Webhooks/analytics (b, matches cmi5):** `course.completed` once per run; the restart event carries both ids, as decided.

## 4. Immutability of archived attempts and answers

- **Enforce it in layers (b):**
  1. *Service layer*: every write path that creates or changes an attempt, answer, topic progress or completion resolves the registration/progress through "current" and refuses if superseded.
  2. *Model layer*: a guard in `save()`/`delete()` (or a model mixin) on the child models raising when the owning run is superseded. Bulk `QuerySet.update()` and `bulk_create` bypass `save()`, so add a custom queryset or accept it and test it.
  3. *Database layer*: a trigger is the only real enforcement against raw SQL or a rogue admin; usually judged disproportionate here. Stating the residual risk in the spec is more honest than claiming DB immutability.
  4. *Admin*: make superseded runs and their children read-only (`has_change_permission` / `has_delete_permission` false for superseded; `readonly_fields`). Deletion belongs to the force-delete spec.
- **FK delete behaviour (b):** the parent links should be `PROTECT` so a registration with successors or progress cannot be deleted by accident (the model already uses PROTECT on the grant FKs; `TopicProgress` and `CourseFormAttempt` cascade from `CourseProgress`, so protecting the registration/progress parents is what matters).
- **Do not recompute stored history (b):** percentage recalculation signals (`post_delete`, `post_save`) must not run against a superseded run, or a later content change could alter archived numbers. The content-versions work already pins question versions for answers; rely on it and do not re-score archived answers.
- **Append-only audit (b):** the audit table is the immutable ledger. Prefer no update/delete in its admin and manager, and write inside the same transaction as the state change so the two cannot diverge.

## 5. Audit trail content

Established minimum for a regulated audit entry (b; consistent with the project's "audit trail" and 21 CFR Part 11-style who/what/when/why practice, not verified against Part 11 text here):

- **Who** (actor user id, and a stable display snapshot in case the user is later removed), **what** (action code, e.g. `registration.restarted`), **when** (server UTC timestamp, never client-supplied), **why** (required reason text, validated non-blank after strip, with a sensible length cap), **on what** (learner, course, the closed registration id, the new registration id, run numbers), **from where** (optional: request id/IP only if the existing log already records it).
- **Before/after state** in the details: closed run's status at the moment of restart (untouched, in progress, complete; progress percentage; completion date) so the entry is self-describing even if the data is later queried differently.
- **One entry per restart**, written in the same `transaction.atomic()` as the state change. If a webhook or notification fails, the restart still stands (use `transaction.on_commit` for outward side effects).
- **No edit or delete of entries; no "undo" action.** The owner decided restarts are final. If a mistaken restart must be corrected, the right model is a new, later audited action, not mutating history; that is out of scope but the shape should not preclude it.
- **Counting restarts** from audit entries or from chain length: store chain links as the source of truth, treat the audit entry as the narrative.

## 6. Django-specific practices

Doc source for constraint behaviour: https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (a). `condition` on `UniqueConstraint` makes the uniqueness apply only to rows matching the condition (a partial unique index); `CheckConstraint(condition=...)` is the current keyword (`check` deprecated in 5.1) (a).

- **Conditional UniqueConstraint (a/b):** replace the unconditional `unique_learner_course_registration` (site, learner, course) with the same fields plus `condition=Q(superseded_by__isnull=True)` (name it distinctly, keep the old name's intent). Old superseded rows then stop matching, and exactly one current individual registration per learner and course stays enforced by Postgres. Same pattern for the cohort uniqueness if cohort registrations can ever be superseded (answers.md says they are not; the per-learner close lives elsewhere, see section 3). This is a schema change to an existing constraint, so write a new migration; never edit an existing one (project rule). Check how `get_or_create`, `update_or_create` and any `ON CONFLICT`-style code (CSV import, `_ensure_registration`) behave: Django's `get_or_create` does not know about the partial condition, so such lookups must add `superseded_by__isnull=True` themselves or they will return the superseded row.
- **Exactly-one-successor invariant:** `OneToOneField("self", null=True, on_delete=PROTECT, related_name="previous_registration")` (Django one-to-one on a nullable column permits many NULLs on Postgres). A `CheckConstraint` stops a registration superseding itself (`~Q(pk=F("superseded_by"))` cannot reference pk reliably in all versions; verify, or enforce in the service).
- **Concurrency (b):** two staff clicking restart at once must produce one restart, not two chained registrations. In the service function: `with transaction.atomic():` then `select_for_update()` on the row that serialises the decision, re-read state *after* acquiring the lock, check "not already superseded" and "is active", then write. The idea's template locks the learner row; locking the registration being superseded (and, for cohort grants, the learner's progress record) is the tighter lock, because the partial unique index only guards the new row, not a double-supersede of the old one. Lock in a consistent order (learner, then registration, then progress) to avoid deadlocks. `select_for_update` only works inside `atomic()` and Postgres honours it; `of=("self",)` avoids locking joined rows when `select_related` is used.
- **Idempotency/double-submit (b):** the confirm dialog should disable on submit, and the service should return a clean "already restarted" error when the lock re-read shows a successor, not a 500 from the unique index. Catch `IntegrityError` only as a backstop and re-raise as a domain error.
- **Transaction boundaries (b):** state change, new registration, new `CourseProgress` (via the existing ensure function), copy of deadline config, audit entry: all in one `atomic()`. Webhook, notification and analytics events through `transaction.on_commit()` so a rollback sends nothing.
- **Ensure functions must be run-aware (b):** anything `get_or_create`-ish on registration or progress (`ensure_course_progress_record`, `_ensure_registration`, cohort-move carry) must filter out superseded rows, or they will "resurrect" or hand back archived data. Add a test per such function.
- **Tests worth requiring (b):** double restart (sequential and concurrent with `TransactionTestCase`), restart of untouched/in-progress/complete runs, cohort-granted restart, reactivate refused, writes to archived run refused at service and admin, partial unique constraint rejects two current rows, migration applies on existing data (all existing registrations have `superseded_by` NULL).
- **Migrations (b):** a new nullable FK with no backfill is cheap on Postgres 17; swapping a unique constraint is a brief lock, so drop-and-create in one migration, or create the new partial index first then drop the old one (`AddConstraint` then `RemoveConstraint`) to avoid a window without protection.

## 7. Pitfalls to design against

- Overloading `is_active` for "superseded" (reactivate resurrects it).
- A status boolean plus a pointer that can disagree; prefer one source of truth.
- Readers that filter by hand and silently mix runs (reports, API, admin, deadline jobs).
- Signals that recompute or re-stamp archived runs (percentage, completion, learning time).
- Counting restarts per run number or by audit entries only; the chain can be the count.
- Retention clocks tied to "completion" when a closed run has none.
- The cohort-granted case: a shared cohort registration cannot carry per-learner state.
- Notifications or webhooks firing before commit.

## Sources

- https://moodle.org/plugins/local_recompletion
- https://warwick.ac.uk/services/digitallearning/support/guides/moodle-guides/mdl-119
- https://www.github.com/danmarsden/moodle-local_recompletion
- https://github.com/AICC/CMI-5_Spec_Current/blob/818b03a4bf3d217df168796d35f06c2ba83b1b10/cmi5_spec.md
- https://adlnet.gov/news/2016/01/08/cmi5-and-the-xapi-scorm-profile
- https://support.scorm.com/hc/en-us/articles/115000684933-Working-with-launched-xAPI-courses
- https://www.law.cornell.edu/cfr/text/14/141.101
- https://www.law.cornell.edu/cfr/text/14/142.73
- https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoC_ORA.ATO_.120.pdf
- https://www.ecologie.gouv.fr/sites/default/files/documents/AltMoC_DTO.GEN_.220.pdf
- https://docs.djangoproject.com/en/5.2/ref/models/constraints/
- Project files: `research_course_restart.md`, `answers.md`, `idea.md`, `../../1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md`

status: ok · reason: web-sourced for Moodle, cmi5, FAA, EASA (secondary), Django constraints; Django locking and audit-content points are practice from knowledge, labelled (b)
