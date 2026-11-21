# Library courses

Spec 4 of 4 in the Reference material effort. Read the "Reference material" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A course that holds only reference material, a library, works end to end. A registered learner opens it and lands on the reference listing. Nothing about it shows progress, and it can never be finished. Educators see it as a library, not as a course stuck at 0%.

A library is a `Course` with an empty learning path and only reference parts. It reuses registration, visibility, owning organisations, course shares, the catalogue and pricing. There is no new access model.

Learner side:
- No progress bar or percentage on dashboard or catalogue cards.
- The library stays in the dashboard's course list. There is no separate section.
- The card, `course_home` and the `course_detail` call to action for a registered learner open the reference listing built by `reference-material-content-2-learner-reference`. They no longer 404.
- `course_finish` refuses on a library: it never stamps `completed_time` and never fires `course.completed`.
- `course_detail` drops "0 lessons" and the empty "Course content" section.

Educator side: course, learner and cohort pages show a library as a library instead of "0%", "0 of N completed", "Lessons 0" or "No content in this course yet".

A library-only demo course is added to the demo content.

## Why

Today an empty `Course` has no player entry. `course_home`, `initiate_course_access`, the registered `course_detail` button and the dashboard and catalogue card links all end in a 404 from `view_course_item` at index 1. `course_finish` completes it on a guessable GET and announces a false `course.completed` to integrators. Every figure reads 0% for good. The parent idea (`spec_dd/1. next/reference-material-content/idea.md`) calls for libraries, but they rank below reference documents in existing courses, so this comes last at low priority. Section 3 of `spec_dd/1. next/reference-material-content/research_learner_player.md` lists every place an empty course breaks. No division by zero exists anywhere, so the work is about behaviour and wording, not crashes.

## What is settled

- Assumption: a library is a course with no learning-path children and at least one reference part. It is derived from the data, with no new field. A course with an empty path and no reference parts stays an ordinary empty course.
- A library reuses the registration, visibility, audience, hidden and coming-soon rules, owning organisations, course shares, catalogue and pricing unchanged.
- It shows no progress or completion anywhere: no bar or percentage on dashboard or catalogue cards, and no "Start course" or "In progress" wording that implies progress. It remains in the dashboard course list.
- Entry points go to the reference listing: the dashboard and catalogue card link, `course_home`, the registered `course_detail` call to action and the end of `initiate_course_access`. Unregistered and anonymous visitors see the catalogue and `course_detail` as for any course.
- `course_finish` on a library refuses. It never stamps `completed_time` and never fires `course.completed` or the completion analytics event. A library therefore never reaches Learning history.
- The detail page drops the lesson count, the hero "0 lessons" stat and the empty "Course content" section for a library. It names the reference material so a visitor can see what the library holds.
- Educator course, learner and cohort pages show a library as a library: no "0%", "0 of N completed", "Lessons 0" or "No content in this course yet". The course content outline shows the library's reference parts (built by `reference-material-content-3-educator-reference`). Cohort completion and learner course tables carry no completion figure for a library, and the at-risk and report guards already return nothing for an empty path (`research_educator_content.md`, section 3).
- Paused and ended learners lose reference access as they lose lessons. A library's reference listing is closed to them the same way.
- The demo content gains a library-only course that exercises registration, the card, the reference listing and the educator view.
- Collision: learner and cohort progress panels move in `educator-interface-refactor-5-learner` and `educator-interface-refactor-6-cohort`. The educator wording changes rebase onto them, and are not made in the flat modules those specs empty (`research_educator_content.md`, section 5).
- Depends on `reference-material-content-2-learner-reference` (the listing) and `reference-material-content-3-educator-reference` (the educator outline).

## Open until the spec

- Whether a course time limit can apply to a library. It resolves from the registration and policy, not from items, so it could end access to a library. The research did not verify this (`research_learner_player.md`, section 3). The spec decides whether it is suppressed, allowed or rejected.
- The exact copy for the library label on cards, the detail page and educator pages.
- What the API and webhook payloads report for a library's course progress records: the stored zero and null values as they stand, or an explicit marker.

## Out of scope

- A separate dashboard section for libraries.
- Any tracking of reference reading, for completion or otherwise.
- A new access, enrolment or pricing model for libraries.
- Deeper nesting, PDFs and files, search, and forms in reference, as in the parent effort.

## Resources

- `spec_dd/1. next/reference-material-content/idea.md`: the parent idea, "Library-only courses".
- `spec_dd/1. next/reference-material-content/research_learner_player.md`: section 3 (what breaks for an empty course), section 4 (access).
- `spec_dd/1. next/reference-material-content/research_educator_content.md`: sections 2 and 3 (course page and per-course counts), section 5 (collisions).
- Siblings: `reference-material-content-1-authoring`, `reference-material-content-2-learner-reference`, `reference-material-content-3-educator-reference`.
