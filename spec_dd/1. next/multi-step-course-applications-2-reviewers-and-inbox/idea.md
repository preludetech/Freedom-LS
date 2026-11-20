# Application reviewers and the review inbox

Spec 2 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Organisation reviewers get an applications inbox and a review screen in the educator interface. They approve or
reject an application, and move it to another organisation.

## Why

Today nobody can decide a `CourseApplication` except by reading it in the Django admin and registering the person by hand.
`multi-step-course-applications-1-review-states` gives an application a state and an `Organisation` and the service
functions that approve and reject it, but no screen calls them. Reviewers are organisation staff, not Django staff, so
they need their own role and an inbox that matches the educator interface's per-organisation scope.

## What is settled

**The role**
- A new organisation-level staff role, working name `application_reviewer`, grants a new review capability. The check is
  `can()` against the application's `Organisation`, not a guardian object permission.
- `organisation_admin` and `site_admin` hold the same capability, so they can review too.
- The role reaches the educator interface: `organisations_accessible_to` admits a holder who has no other capability.
  It appears in the Staff UI's role lists (offered, shown and filterable) and in the permission-matrix invariant.
- Several people can hold it. One decision from any one of them is enough.

**The inbox**
- Per organisation, under the educator interface's organisation URL scope. An application outside the user's scope is a 404.
- Lists submitted and decided applications, never drafts, oldest submitted first.
- Search, a state filter and a period filter, and a quick view for each row.
- Built on the panel framework as a new area written directly in `panels/applications/`.
- Only the capability decides whether the section is visible.

**The review screen**
- Applicant identity: the applicant's email and name. For an unclaimed application the email is shown with an "address not confirmed" marker.
- The course, the application form answers read-only, and a History tab from the audit log.
- Each action shows only when the application's state and the reviewer's capability allow it.
  - **Approve** asks for confirmation. It is refused for an unclaimed application, and the reason is shown.
  - **Reject** requires a message the applicant will see.
  - **Move to another organisation** offers only organisations that the reviewer can access, where the reviewer holds the review capability and
    the course is open to the organisation. It is refused once the application is approved, and every move is audited.
- Approve here only changes the state. `multi-step-course-applications-3-approval-outcome` makes approval register the applicant.
- The Django admin stays read-only.

**Notifications** (decided per the notifications skill)
- No notification on submit: the inbox is the surface reviewers work from.
- A claimed applicant gets an in-app notification when their application is approved or rejected. An unclaimed applicant has no account to notify.

## Open until the spec

- Whether a move also shows in the source organisation's audit log, or only in the destination's.
- Which nav group the applications section sits in.

## Out of scope

- Bulk decisions, internal notes, assignees and email.
- Applicant-side states and the withdraw action (`multi-step-course-applications-1-review-states`).

## Resources

- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md`, sections 3, 4, 6, 7, 8 and 9.
- `spec_dd/1. next/multi-step-course-applications/idea.md`, "Who reviews: organisation roles".
- Skills `fls-dev:panel-framework`, `fls-dev:educator-interface`, `fls-dev:notifications`.
