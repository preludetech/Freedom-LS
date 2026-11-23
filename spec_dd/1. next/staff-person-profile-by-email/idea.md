# Idea: a staff person profile, looked up by email

## What

A read-only page for staff that gathers everything FLS knows about one person, looked up by email:
the user account and whether the email is verified, first-touch referral attribution, course
applications, course interest, course recommendations, and course registrations with progress. It
also works for an email that has no account yet, showing whatever records carry that address. A
project can add its own sections, such as its lead form submissions.

## Why

Answering "who is this person and where are they with us?" today means visiting five or six admin
changelists and matching by email. Sales and support staff on every concrete project ask that
question. The data lives entirely in FLS apps (`accounts`, `course_applications`,
`course_interest`, `course_recommendations`, `learner_management`, `learner_progress`,
`referral_tracking`), so FLS is the right home for the page that brings it together.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/admin_dashboard/lead_profile.py`: `lead_profile_for` and its dataclasses
- `apps/admin_dashboard/views.py`: `LeadProfileView` and `can_view_lead_profile`
- `apps/admin_dashboard/templates/admin_dashboard/lead_profile.html`
- `apps/admin_dashboard/tests/test_lead_profile.py`

The lead submissions section depends on the project's lead forms, which `lead-capture-forms` covers.
The pull-in scan only skimmed the view and template, so check them for project data and for the
permission model before reusing them.

## Settled

- Read-only, and for staff only.
- Keyed by email, so it covers people who have no account yet.
- The project keeps its lead submissions section and adds it to the FLS page.

## Open

- Which app it joins (`educator_interface`, `reports` or the admin) and who may see it. It reads
  from many apps, so the new dependency edges need approval against `docs/app_structure.md`.
