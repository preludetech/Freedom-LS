# Reviewer verdicts on requirements

Spec 6 of 11 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Reviewers accept a submitted requirement or turn it down, with a reason and an optional note to the applicant. Before they confirm, the review screen shows what the applicant will be asked to do next. Requirements can hold back approval or registration, so a reviewer's verdicts decide when an application can be approved and when the applicant is registered.

## Why

Requirements are only a to-do list for the applicant until a reviewer can clear them. Without verdicts nothing holds back approval, a rejected document has no path back to the applicant, and staff-verification steps (checks done off-platform) have nowhere to be recorded.

## What is settled

**The verdict**

- A reviewer accepts a submitted requirement, or turns it down with a rejection reason and an optional free-text note for the applicant. One accept is enough.
- The reviewer says what is wrong, never what happens next. The resolver reads the reason and produces the consequence.
- Before confirming, the review screen runs the resolver on the proposed verdict and shows "the applicant will be asked to: …".
- The verdict and the reconcile run happen in one transaction.
- Staff-verification requirements have no applicant action. A reviewer marks one done, which is an accept.

**Rejection reasons**

- Reasons are Python, not database rows. Each has a reason code, a reviewer label and an applicant explanation of what to do next. The wording can be overridden through templates.
- This spec defines the reason shape and ships a generic set any resolver can use: unreadable, wrong document, expired, name does not match.
- Reasons specific to a document type arrive with document types in `multi-step-course-applications-7-upload-requirements`.

**Holding back**

- An application cannot be approved while a requirement that holds back approval is not accepted.
- After approval, while requirements that hold back registration are outstanding, the application sits in a new state, "approved, conditions outstanding". The approval outcome from `multi-step-course-applications-3-approval-outcome` runs when the last such requirement is accepted, with that reviewer as the actor.
- On an intake course (`multi-step-course-applications-10-intake-courses`) approval registers nobody, so requirements that hold back registration hold back the reviewer's onward course registrations instead. The register actions stay unavailable, with the reason shown, until the last such requirement is accepted.
- Requirements that hold nothing do not affect either step.
- The application-level "changes requested" state from the old draft is not built. Only the requirement is turned down.

**Audit and notification**

- Every verdict is written to `audit_log`: the reason code in the details, the note as the reason. The actor is the reviewer.
- A claimed applicant gets an in-app notification when a requirement is turned down. Accepting raises none, unless the accept completes approval, in which case the approval outcome's own signal to the applicant is the only one raised and no second is added. The notification skill's checklist is answered in the spec.
- Anonymous applicants cannot receive in-app notifications. Requirements already assume a claimed account.

## Open until the spec

- The exact name of the "approved, conditions outstanding" state.
- Whether a reviewer can reverse a verdict, and what a reversal does to an applicant who has already acted on a turn-down.

## Out of scope

- Document types, uploads and their own reasons: `multi-step-course-applications-7-upload-requirements`.
- Either-or requirement groups: `multi-step-course-applications-8-choices`.
- More than one sign-off on a requirement.
- Email to anonymous applicants about verdicts.

## Resources

- `spec_dd/1. next/multi-step-course-applications-10-intake-courses/idea.md`: intake courses and the registrations section whose actions this spec holds back.
- `spec_dd/1. next/multi-step-course-applications/idea.md`: "Application requirements" and "Reviewer verdicts", and the rejected-qualification walk-through.
- `spec_dd/1. next/multi-step-course-applications-5-requirements-and-resolver/research_requirements_and_forms.md`: sections 5 and 6 (reconcile hook, verdict inside the same transaction).
- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md`: sections 2 and 4 (`course_access` and what accepted means, `audit_log`).
- `spec_dd/1. next/multi-step-course-applications-7-upload-requirements/research_uploads.md`: section 6 (document types and reasons).
- `spec_dd/1. next/multi-step-course-applications/research_help_requests.md`: section 2 (notifications for verdicts).
- `claude_plugins/fls-dev/skills/notifications/SKILL.md`.
