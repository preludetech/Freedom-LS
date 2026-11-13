# Upstream-change review: learner-facing-ux-refinements

direction: changed

## What main gained
`organisation-courses` (finished: `spec_dd/3. done/2026-10-27_20:02_organisation-courses/`). A course can belong to organisations (`Course.organisations`, `Course.audience`), the audience gate hides organisation courses from learners outside them, and `content_engine` now depends on `organisations` in `docs/app_structure.md`. That app-boundary edge does not touch anything this spec moves (`base`, `icons`, `course_applications`, `learner_interface`), so it is not what changes the direction.

The signal that matters is in `learner_interface`. Main added the cotton component `organisation-byline.html` and renders it in `partials/course_card.html` under the title, fed by `course.card_organisation` (stamped by `get_current_courses` for in-progress cards, and for discovery cards when the course has exactly one organisation). `docs/product/learner-experience.md` now says: "Dashboard cards name the organisation, so same-titled versions of a course can be told apart."

## Why it matters for this spec
The done spec took the decision that dashboard course cards carry the organisation byline. Its scope line reads: "An organisation byline on learner-dashboard cards." (`1. spec.md` section 3, In). Its purpose is to tell same-titled courses of two organisations apart, and its Playwright flow asserts that at every `QA_VIEWPORTS` size. Its Out list is: "The organisation byline on the all-courses list, the markdown embed card, completed cards and the course detail page."

This spec's Requirement 2 replaces the card grid with `partials/course_row.html` rows below `lg`. Each dashboard section renders the grid as `hidden lg:grid` and the row list as `lg:hidden`. The row has no byline, so on phones and tablets the dashboard stops naming the organisation. That reopens a decision of a finished spec. It is not a deliberate trade-off, because this spec's text never mentions organisations.

- The Decisions table says the row "already renders every `listing_status`", so it is a full replacement for the card. That claim is now false.
- Scope: the row sits on the dashboard, where the byline is required. The all-courses page also uses `course_row.html`, and the done spec keeps the byline off the all-courses list. This is not a conflict if the byline is driven by `course.card_organisation`. The all-courses view never stamps that field, and the component renders nothing for an empty value.
- The existing byline tests use `get_by_text(...).first`, so they would pass on the hidden card copy and would not catch this gap.

Artifacts holding the decisions:
- `spec_dd/2. in progress/learner-facing-ux-refinements/1. spec.md`: Decisions row 1, Requirement 2 (the `course_row.html` bullet), Testing, Documentation.
- `spec_dd/2. in progress/learner-facing-ux-refinements/2. plan.md`: "Existing code to reuse" (line 36, "reuses `course_row.html` as is"), Slice 2 (the `course_row.html` edit) and Slice 3.
- The implemented `freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html`.

## What to change
- `1. spec.md`, Requirement 2: add that `partials/course_row.html` renders `<c-organisation-byline :organisation="course.card_organisation" />` under the title, as `course_card.html` does. Say the byline shows only where `card_organisation` is stamped, so the all-courses page, which keeps no byline per `organisation-courses` section 3 Out, is unchanged. Amend the Decisions row 1 reason to mention the byline.
- `1. spec.md`, Testing: add a case that each dashboard section's row list shows the byline for a course with a `card_organisation` (in-progress and a single-organisation discovery course). Add a case that the all-courses rows show none. Rewrite any count-based organisation assertion to allow for the two layouts, and assert on the `lg:hidden` row list.
- `1. spec.md`, Documentation: note in the `learner-experience.md` Dashboard text that the byline appears on the compact rows as well as the cards. Add to the upgrade notes that a project shadowing `course_row.html` must merge the byline line.
- `2. plan.md`: change Slice 2 or Slice 3 (the `course_row.html` edit) to add the byline include, plus the test files above. Fix the "reuses `course_row.html` as is" sentence in "Existing code to reuse".
- Code, `freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html`: add the byline component. Place it so it does not break the stretched-link row. Check the `course-row-shell` layout at 375px for overflow. The component already truncates the name, and the `min-w-0` it uses needs a flex parent. Extend `learner_interface/tests/playwright/test_organisation_course_flow.py` to check the byline in the visible layout at 375 and 768px.

status: ok
