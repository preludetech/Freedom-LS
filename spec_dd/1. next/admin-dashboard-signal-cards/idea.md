# Idea: signal cards on the admin index

## What

The Django admin index shows a row of "signal cards", one per thing a site operator watches:
signups, course registrations, course applications and course interest. Each card shows the count
for the last 7 days next to the previous 7 days, and lists the five newest entries with a short flag
where one applies (for example "Unverified email" or "Not submitted"). The signups, course
applications and course interest cards link to the matching admin changelist. The course
registrations card links to the educator interface's course list instead, because the
`LearnerCourseRegistration` admin is gone; each course there holds its learner registrations table.
A card shows only when the user has view permission on its source model. A project adds its own
cards through an extension point that pairs a permission with a builder.

## Why

The admin index is the first page an operator sees, and today it is only a list of models. To see
whether signups or applications are moving, the operator opens each changelist and filters by
date. Every concrete project that runs a live site wants this summary, and the generic cards read
only FLS models. FLS already depends on django-unfold, whose `dashboard_callback` hook is the
natural place to put them.

## Reference implementation

First-Class-LMS (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`):

- `apps/admin_dashboard/dashboard.py`: the card and entry dataclasses, the window helpers, the card
  builders, `CARD_BUILDERS` and `dashboard_callback`
- `apps/admin_dashboard/templates/admin_dashboard/dashboard.html`
- `templates/admin/index.html`
- `apps/admin_dashboard/tests/test_dashboard.py`

Its lead forms card and the lead profile and lead list context keys are specific to the project.
They stay there and register through the extension point.

## Settled

- The signups, course registrations, course applications and course interest cards come into FLS.
  The lead forms card stays in the project.
- The course registrations card links to the educator interface's course list, not an admin
  changelist. The other three cards link to their admin changelists.
- Each card is gated on its source model's view permission.
- A project adds cards through a registry of (permission, builder) pairs and does not override the
  template to add them.
- The project deletes its copies of the generic cards and helpers once FLS ships them.
