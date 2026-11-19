# What approval does

Spec 3 of 10 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

When a reviewer approves a `CourseApplication`, what happens next is the deployment's call. A
setting names a class that decides it, and FLS ships a default class that registers the applicant for
the course. A deployment that wants something else (a hand-off to another system, a manual step)
swaps the class and leaves the rest of the review flow alone.

The default outcome makes the applicant a `Learner` in the application's organisation and gives them an
individual `LearnerCourseRegistration` for the course, in the same transaction as the approval. The
approve dialog tells the reviewer what approval will do, in words that come from the outcome class.
The applicant's status page says they are registered and links to the course.

## Why

Today nothing happens on approval: a staff member reads the application in the Django admin and
registers the person by hand in the educator interface. With reviewers approving in the inbox, that
hand-off is the step most likely to be forgotten, and the applicant is left waiting on an approval that
gives them nothing. Registering automatically closes the loop. Making it a seam keeps FLS usable by
deployments whose approval means something other than course registration.

This reverses the old draft's position that approval is not enrolment.

## What is settled

- What approval does is a deployment seam in the house pluggable pattern: a setting naming a class, with
  a default in the app's `config.py`; a cached loader with its test-cache-clearing fixture; a plain base
  class (not an abstract base) whose methods raise `NotImplementedError`; a frozen `*Decision`-style result
  if the outcome needs to return one; a boot-time check that the dotted path imports and subclasses the
  base; and a conformance probe in `freedom_ls/contrib/conformance/` for downstream deployments.
- FLS's default outcome registers the applicant. The `Learner` is made in the application's organisation
  (through `ensure_learner`, or `add_learner` when the user already exists). The registration is made
  through `register_for_course` with the reviewer as actor. It is individual: no cohort is involved.
- Registration happens in the same transaction as the state change to approved, so a failure leaves the
  application unapproved. It writes the existing registration audit entries and fires the existing
  webhooks.
- The outcome is idempotent. An existing active registration is fine: approval does not fail and does
  not register twice.
- A course that is not open to the application's organisation refuses the approval. The approve dialog
  shows a clear message (the cause is `CourseNotOpenError`) and the application's state does not change.
- An unclaimed application cannot be approved. `multi-step-course-applications-1-review-states`
  already refuses it, so the outcome only ever sees an application with a user.
- The approve dialog states what approval will do, taken from the outcome class, so a deployment's
  own outcome describes itself.
- The applicant's status page says they are registered and links to the course.
- No second notification is sent. The existing `course.registered` notification covers the applicant.
- Registration is one callable function, so `multi-step-course-applications-6-reviewer-verdicts` can
  hold it back while registration-holding requirements are outstanding and call it later when they
  are accepted.

## Open until the spec

- `add_learner` for an existing user, or `ensure_learner` plus a hand-written `learner.added` entry.
  `add_learner` reuses more (entry and webhook) but is built around email matching and account creation.
- The setting's name.
- Whether a deployment outcome can decline approval (return a refusal the way a `*Decision` can),
  or can only act after approval succeeds.

## Out of scope

- The review states, the claim rule, and the reviewer screens (`multi-step-course-applications-1-review-states`,
  `multi-step-course-applications-2-reviewers-and-inbox`).
- Holding registration back for requirements (`multi-step-course-applications-6-reviewer-verdicts`).
- Registering into a cohort, and any new notification or webhook.

## Resources

- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md`, section 2 ("What
  automatic registration on approval needs").
- `spec_dd/1. next/multi-step-course-applications-5-requirements-and-resolver/research_requirements_and_forms.md`, section 1 (the
  house pattern for pluggable behaviour).
- `claude_plugins/fls-dev/skills/app-settings/SKILL.md`.
- `freedom_ls/learner_management/learner_actions.py` (`register_for_course`, `add_learner`) and
  `freedom_ls/learner_management/utils.py` (`ensure_learner`).
