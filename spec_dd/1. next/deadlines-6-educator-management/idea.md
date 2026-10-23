# Educator deadline management

Spec 6 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Panels and actions in the educator interface where staff manage deadlines without the Django
admin. On cohort detail, an educator sets and edits the deadlines of a cohort's course
registration and extends them for the whole cohort. On learner detail, an educator sets and
edits a learner's deadlines for a course, extends them, and pauses or resumes the course.
Extending also works in bulk, over many selected learners, through the bulk-operations framework.
Every action is gated by a new capability and writes an audit log entry, and the learner is told
when staff act on them.

This spec builds on spec 3 (overrides, extensions and the pause records), on
`educator-interface-8-bulk-operations` (multi-select bulk actions on the learner table) and on
`educator-interface-11-audit-log` (the model and its vocabulary).

## Why

Spec 3 gives staff extensions and pause only in the Django admin, which is where a school
administrator should not have to be to help a sick learner. The research found extension is the
chore educators complain about most: Canvas users call per-student, per-assignment extension
"tedious and difficult" and ask for it from the learner's own page and in bulk, and Moodle's
multi-select "Grant extension" is the praised answer. The educator interface rebuild left
deadlines out on purpose, so the panels, capabilities and audit entries are all new.

## What is settled

- **Placement.** On cohort detail, `CohortCoursesPanel` gains the cohort course registration's
  deadlines and its cohort-wide extension. On learner detail, `LearnerRegistrationsPanel` gains
  per-registration actions for extend, pause and resume, shown beside the existing unregister and
  re-register actions. The learner's courses tab lists each course's effective deadlines. A compact
  due or paused summary goes in `LearnerQuickView`.
- **What staff can do.** Set and edit the overrides of a cohort course registration and of a
  learner (the overrides spec 1 defines). Extend, singly or in bulk. Pause and resume any learner,
  with an optional planned resume date. What an extension and a pause do is spec 3's behaviour,
  unchanged: one extension moves due and close dates together, and a pause stops the clock.
- **Bulk extend** is a bulk action on the learner table using spec 8's framework, with the same
  modal, a confirmation stating what will happen to how many, and a server-side permission check
  on every object. It is also offered on a cohort's learners tab.
- **Capabilities.** New permissions are added in `role_based_permissions/roles.py` with a data
  migration, per the file's own note. `organisation_admin`, `cohort_admin` and `site_admin` hold
  the ones that change deadlines, extend and pause. `cohort_viewer` holds only the read capability
  and sees deadlines and pause state with no controls. Panels and actions declare their
  capability and follow the denied experience: a 404 for organisation or instance scope, a 403
  with a message for a visible action no longer allowed, hidden controls otherwise.
- **Audit.** Each action writes one audit log entry per object inside the action's transaction,
  and a bulk run writes one summary entry with the per-object detail. The new actions extend
  spec 11's vocabulary in the past tense. A resume that happens on its planned resume date is a
  system action with a null actor.
- **Notifying the learner.** A staff extension, pause or resume notifies the learner, using the
  categories spec 3 defines. This spec raises them from its actions and adds no category of its own.
- **Dates name their time zone** wherever the panels show or take a date or time, and a due time
  defaults to end of day in the site's time zone.
- **Policy configuration stays in the Django admin.** The panels show the policy in force and its
  limits but do not edit it.
- **Everything is organisation-scoped and site-aware.** No action reaches across organisations.
  The registration that governs a learner is the one `learner_for_course` resolves.
- **Refresh** uses the existing educator events (`LEARNER_CHANGED`, `COHORT_CHANGED`,
  `REGISTRATION_CHANGED`), with HTMX 422 for validation errors.

## Open until the spec

- **Capability granularity.** How many permissions there are (one per action or fewer) and their
  names, within the rule that `cohort_viewer` stays read-only.
- **Where the learner's per-item deadlines sit** on the courses tab, given that
  `educator-interface-10-reporting-dashboards` owns the learner drill-down on that tab.
- **Whether staff must give a reason** for a pause or an extension, or may. The audit log's reason
  is optional everywhere.
- **How an override made here is recorded** (actor, reason, and whether it follows later edits to
  the default), as spec 1 settles it.
- **The shape of the pause and extension records** and how a resume computes the shift, as spec 3
  settles it.
- **The bulk-action target when learners have several registrations** for one course, and how a
  bulk run reports learners it skipped. Only code reading and spec 8's framework answer these.

## Out of scope

- Editing the deadline policy, or any policy screen (Django admin).
- The learner's own pause (spec 4), reminders and the educator overdue notification (spec 5),
  and at-risk lists (spec 7).
- Dates, policy, extension and pause behaviour, and their webhooks (specs 1 to 3).
- Approval or request flows for extensions. Fees for pausing.
- Line-manager views, recertification, scheduled or emailed reports.

## Resources

- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: section 5 (educator interface slots and
  permissions) and section 8 (collisions in `educator_interface/views.py`).
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: section (b) and implications 2, 3 and 8.
- `spec_dd/1. next/educator-interface-8-bulk-operations/idea.md` and
  `spec_dd/1. next/educator-interface-11-audit-log/idea.md`: the framework and the log this spec plugs into.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:template`, `ds:htmx`,
  `brand-guidelines`, `fls-dev:testing`.
