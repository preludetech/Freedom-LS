# Due dates, course time limit and overdue

Spec 1 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The old deadline implementation is removed and replaced by two kinds of deadline: a due date on a
content item and a time limit on a whole course. A course may have either, both or neither.

An item due date is a fixed date or an offset from the learner's start. The course time limit is
always an offset. Course authors set defaults in the content's frontmatter. Staff override them for
a cohort's registration of a course and for a single learner, in the Django admin. One resolver
turns these layers into the effective due date and time limit end for a learner and a course.

Learners see the result: due dates on the table of contents and course detail, an "overdue" mark on
an item past its due date, the time limit's end on course detail, and overdue state on the dashboard
course card. Overdue is only displayed here. Nothing closes and no access ends.

The course-author side is part of this spec: the frontmatter fields, their validation when content
is loaded, and the `fls-content` plugin, which has to learn them.

## Why

The current implementation cannot say "due 30 days after registration", has no course time limit,
and its only consequence is locking an item. Moodle, TalentLMS, LearnDash and Open edX all offer
both a relative window and per-item dates (landscape file, sections a and f). Corporate readiness
item 13 asks for dates relative to an event and says to fold it into the deadlines rework.

Educators and learners complain about dates that are ambiguous or unexplained: unlabelled time
zones, midnight defaults, overrides that silently stop following the default (sentiment file,
sections d and g). Those are decided here, once, before any consequence depends on a date.

## What is settled

- **The old implementation goes entirely.** That is `CohortDeadline`, `LearnerDeadline`,
  `LearnerCohortDeadlineOverride`, `learner_management/deadline_utils.py`, `DEADLINES_ACTIVE`, their
  admins, the table-of-contents badges and lock, and the four `qa_create_*deadline*` commands. No
  rows are migrated. The inventory of code, tests, docs, skills and plugin text to clean is in
  `research_current_deadlines.md`, section 2. The `deadline` icon name stays, because
  `403_csrf.html` uses it.
- **Two kinds of deadline**: an item due date and a course time limit, in any combination.
- **A deadline attaches to the placement** (`ContentCollectionItem`), not the content row. Progress
  keys on the placement and one topic can be placed twice.
- **Fixed or relative.** An item due date is a fixed date or an offset from the learner's start. The
  time limit is always an offset.
- **The learner's start is `CourseProgress.created_at`**, the registration date on both the
  individual and cohort paths. First access is not offered as an anchor.
- **Layers.** Content default, then the cohort course registration override, then the learner
  override. The learner override beats the cohort course registration, which beats the content
  default. Where several deadlines apply at the same layer, the most permissive wins.
- **One registration governs**: the one `learner_for_course` resolves. A learner in two
  organisations has separate deadlines.
- **Authors set defaults in frontmatter**: relative offsets for items and the course time limit.
  Authors can also set a fixed date on an item.
- **Time.** A due time defaults to the end of the day in the site's time zone. Every date shown
  names its time zone. No user time zone field is added.
- **Overdue is shown, not enforced.** An incomplete item past its due date is marked overdue for
  the learner. A completed item is never overdue.
- **Where learners see it**: the table of contents, course detail and the dashboard.
- **Pause is not here.** The resolver reads a start and a stored override; later specs add shifts
  to it without a second resolver.

## Open until the spec

- **Frontmatter shape.** Whether authored deadlines sit on the course's child list, in `overrides`,
  or on the item. This spec owns the answer; specs 2 and 6 build on it.
- **How an override records its actor and reason**, and whether it follows later edits to the
  default. Specs 3 and 6 build on the answer. The sentiment file (implication 4) asks that an
  override either follows the default or visibly flags that it no longer does.
- **What a re-import of content does** to a placement that moved, given that the sync creates a
  new `ContentCollectionItem` when a child moves collection.
- **How the dashboard card shows overdue** for a course with several overdue items, as far as the
  existing `CourseListingEntry` allows.

## Out of scope

- What happens when a date passes beyond being marked: grace windows, closing an item, ending
  access, and the policy that chooses them (spec 2).
- Extensions, pause and resume, and any change to a date after it is set by an override (spec 3).
- Learner self-pause (spec 4).
- Reminders and educator notifications (spec 5).
- Educator-interface screens for setting deadlines (spec 6). Overrides are made in the Django admin
  here.
- Overdue learners in Needs attention or the cohort report (spec 7).
- Recertification cycles and retakes, score penalties, line-manager views, scheduled reports,
  calendar export.

## Resources

- `spec_dd/1. next/deadlines/idea.md`: the source brief.
- `spec_dd/1. next/deadlines/research_current_deadlines.md`: the old models, the removal inventory,
  registration and progress model, constraints from done specs.
- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: sections 4 and 6, where
  deadlines show in the learner interface and where tests collide.
- `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`: sections a, b and f, how other
  systems attach and override dates and handle end-of-day and time zones.
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: sections d and g.
- `spec_dd/corporate-readiness/README.md` item 13; done specs `2026-02-19_19:25_deadlines`,
  `better-course-progress-tracking`.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:markdown-content`,
  `fls-dev:admin-interface`, `fls-dev:testing`.
