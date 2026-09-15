# Feature: Common learner management actions

Educator-facing actions for the everyday work of looking after learners — the things an administrator
currently has to open the Django admin to do, or cannot do at all.

**Sequencing: this comes after `better_course_progress_tracking` lands.** The cohort-move action below is
specified in terms of that work's progress-record model, and cannot be written against `main`.

## Why

Cohort membership is only editable through the Django admin's `CohortMembershipInline`
(`learner_management/admin.py:152`). There is no educator-facing way to add a learner to a cohort, remove
one, or move one — and no unregister flow anywhere in the product. Every routine learner-management task
either needs a superuser in the admin or needs a developer.

The `panel_framework` already has the machinery for this: `PanelAction`, `FormPanelAction`,
`CreateInstanceAction`, `EditAction`, `DeleteAction` (`panel_framework/actions.py`), with `CreateCohortAction`
(`educator_interface/views.py:793`) as the worked example. The gap is which actions exist, not how to build
one.

## The action we know we want: move a learner between cohorts

Move a learner from one cohort to another **within the same organisation**.

> **Note — `better_course_progress_tracking` has since settled this, and three bullets below are stale.**
> Its spec decides that **nothing but an explicit retake retires a course progress record**: membership
> deletion, registration deactivation and learner deactivation all leave it alone. So the destructive
> sequence described in the next two paragraphs no longer happens, and this feature is no longer where
> the mitigation lands.
>
> What changes here:
>
> - **The transfer step is provenance, not data preservation.** A same-organisation move destroys
>   nothing on its own, so re-pointing the record's `cohort_registration` (option 1) is bookkeeping —
>   worth doing so the record names the registration it now sits under, but no longer load-bearing.
>   Option 3 is effectively what shipped; option 2 has nothing left to defer.
> - **"Retire progress for courses the old cohort granted and the new one does not" now contradicts
>   that spec** and has to be re-decided here. If it is wanted, it is an explicit named action, not a
>   side effect of the move.
> - **"Creation stays lazy, as it is today" is no longer true.** Records are created at registration
>   and fanned out per learner, so creating the destination `CohortMembership` already mints a record
>   for every active course registration that cohort holds. The move does not need to start anything;
>   it needs to not be surprised that something started.
>
> The "be visible: the educator should see what will happen to the learner's progress before
> confirming" bullet survives unchanged, and gets easier — the honest answer is now "nothing is lost".

Today this is two separate admin operations — delete the old `CohortMembership`, create the new one. Under
`better_course_progress_tracking` that sequence is destructive: a course progress record's life follows the
registration that granted it, so deleting the membership retires the record and the learner's next visit
resolves a different registration and starts a fresh pass from zero. A learner 60% through a course loses
that 60% because an educator moved them between cohorts.

That idea records the loss as an accepted consequence and names this feature as where the mitigation lands
— see its "Decisions carried over from the spec phase" section, which also carries a caveat aimed squarely
at this case: a cohort move is a human click producing *two automatic writes*, so it is the comparison
logic, not the click, that decides whether the learner keeps their work. Its
`research_enrolment_bound_progress_lifecycle.md` surveys how other systems handle the same problem and
favours option 1 below.

What the action must do:

- Take a learner and a destination cohort in the same organisation, in one transaction.
- Preserve in-flight course progress for any course both cohorts grant. A same-organisation move does not
  change which `Learner` row is in play, so the record's `(learner, course)` identity is unchanged and their
  existing progress record is still the right one — the move re-points it at the destination cohort's
  registration rather than retiring it.
- Retire progress for courses the old cohort granted and the new one does not. That is a genuine loss of
  access and the existing rule is correct there.
- Start nothing eagerly for courses only the new cohort grants — creation stays lazy, as it is today.
- Carry over, or deliberately not carry over, cohort deadlines (`CohortDeadline`). Decide in the spec phase.
- Be visible: the educator should see what will happen to the learner's progress before confirming.

Deciding *how* the progress record survives the move is a design question for the spec phase, and it
interacts with `better_course_progress_tracking`'s resolution rule rather than sitting beside it. The
options weighed so far:

1. A transfer step inside the move action that re-points the progress record's `cohort_registration`.
   Smallest change; leaves the destructive path open to anyone who does the move the manual way.
2. Deferring the retirement check to `transaction.on_commit`, guarded by "does the learner still hold any
   active registration for this `(course, organisation)`?". Makes any single-transaction move safe, including bulk
   admin actions, not just this one action.
3. Treating the registration FK as current-registration bookkeeping rather than identity, so resolution
   re-points and resumes instead of retiring. Collapses the resolution rule from three cases to two, at the
   cost of needing an explicit trigger for retakes.

**Cross-organisation moves are out of scope.** Organisation is part of the progress record's identity key, so
a learner moving between organisations holds a different `Learner` row and *should* start a fresh progress
record — that is `better_course_progress_tracking` working as designed, not a bug to fix here.

## TODO: research what else belongs here

Before specifying, survey what learner-management tasks LMS administrators and educators actually do day to
day, and which of them FLS should own. The list below is a starting point, not a decision — it is what came to
mind, not what research found.

Research should cover:

- What comparable systems (Moodle, Canvas, Open edX, TalentLMS, Docebo, LearnDash) expose as first-class
  learner-management actions, and which ones users complain about not having.
- Which actions are genuinely common versus which are long-tail admin work that the Django admin should keep.
- Bulk versus single-learner: which of these are only useful in bulk, and what that implies for the UI.
- Audit and reversibility expectations — which of these an administrator is expected to be able to undo or
  explain after the fact.
- Where each action belongs: educator interface action, Django admin, or management command.

Candidates to evaluate, all unvalidated:

- Add a learner to a cohort / remove a learner from a cohort.
- Register or unregister a learner for an individual course. There is no unregister flow anywhere today.
- Reset a learner's progress on a course, or start them on a fresh pass deliberately — the explicit retake
  trigger that `better_course_progress_tracking` leaves unbuilt.
- Extend or override a deadline for one learner within a cohort.
- Deactivate or reactivate a learner's account, and what that means for their progress and cohorts.
- Bulk-add learners to a cohort, e.g. by pasting or uploading a list of email addresses.
- Invite or re-invite a learner, and resend a verification email.
- Merge two accounts for the same person.
- Transfer a whole cohort's learners to another cohort.

## Constraints

- Every action is organisation-scoped and site-aware. `Cohort` carries an `organisation` directly;
  `LearnerCourseRegistration` and `CohortMembership` reach one through `learner.organisation`, and
  `CourseProgress` will too once `better_course_progress_tracking` re-keys it onto `Learner`. Nothing here
  may let an educator reach across organisations.
- Permissions go through `role_based_permissions`, consistent with existing panel actions.
- `learner_management` must not import `learner_progress` at runtime — `docs/app_structure.md:80-85` lists
  no such edge (the dashed `learner_management -.-> learner_progress` at `:126` is a test-only import). Any
  progress-side effect of an action follows whatever signal or resolver route
  `better_course_progress_tracking` settles on for retirement.
- Actions that change access must fire the relevant webhook events, matching the existing
  `course.registered` pattern (`learner_management/models.py:128-159`).

## Out of scope

- Anything that changes course *access* rules. `is_registered_for_course` and the `COURSE_ACCESS_BACKEND`
  backends stay organisation-blind.
- Cross-organisation learner moves.
- Self-service actions for learners. This is educator- and administrator-facing.
