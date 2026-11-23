# Revision dashboard

Follows `learner-interface-features-3-revision-questions`. The user will provide a design.

## What

When the learner clicks **Revision** in the left panel, they see a dashboard instead of going
straight into a session.

- One card for each course the learner is working on that has revision questions
  (`course_has_revision_questions`).
- Each card has a **Start revision** button showing how many questions are due (`ready_count`).
  When nothing is due, the card says when the next questions will be ready (`next_ready_at`) and
  offers a practice session.
- Each card lists the sections the learner has reached, in course order (`bank_sections`). Each
  section shows:
  - whether it is weak (`weak_sections`) or strong;
  - when the learner last revised it (`last_reviewed_at`);
  - a **Revise this section** action, a session limited to that section (the `section` filter on
    `ready_count` and `due_questions`).
- Sections the learner has not reached are not shown.
- Empty state: no course has a finished section yet. The page says so and links to the learner's
  current course.

## Why

The revision screen tells a learner what is due and nothing more. The dashboard shows them where
they are strong and weak in each course, and lets them aim a session at a weak section.

## What is settled

- It reads the queries `learner-interface-features-3-revision-questions` kept for it:
  `bank_sections`, `weak_sections`, `last_reviewed_at`, `next_ready_at`,
  `course_has_revision_questions` and the `section` filter. It does not change how the bank, the
  schedule or the weak flag are worked out.
- `bank_sections` already holds only the sections the learner has finished, so hiding unreached
  sections needs no new logic.

## Open

- What counts as strong: simply "not weak", or "not weak and revised at least N times", with
  too-few-answers left unmarked.
- Whether weak sections come first in a card, or get their own "Revise weak sections" button.
- Whether there is a "Revise everything due" button across all courses.
- Whether a learner with one course skips the dashboard and sees that course's card on its own.
- Layout and copy: the user's design.
