# Reference material: authoring

Spec 1 of 4 in the Reference material effort. Read the "Reference material" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Authors attach reference parts to a course with a `reference:` key in `course.md`, and `content_save` stores them, validates them and keeps the database in step with the files.

- **Model.** `CourseReferencePart` is a `SiteAwareModel` with a `course` FK, a `course_part` FK and an `order`, unique on `(course, course_part)`. Both are real FKs, so a row cannot dangle. It is the only new table. A reference part is an ordinary `CoursePart` whose children are `Topic` rows placed through `ContentCollectionItem`. `Course.items` stays the learning path and is not touched.
- **Schema.** The `Course` schema gains `reference:`, a list of entries each naming a path. Paths resolve like `children:` paths, so `../` can reach a part in another directory and one part can be shared by several courses. An entry is not a `Child`: it has no due keys and no nested `children:`.
- **Loading.** `content_save` writes one `CourseReferencePart` per entry, in list order, and reconciles on every load: an entry removed from `reference:` deletes its row. The part and its topics are saved as for any other part.
- **Cleanup.** When a part is listed under `reference:`, `content_save` deletes that course's old collection item placing the part, together with the deadline overrides on it and its part-placement due dates, and the save output names what it removed. Without this, a part moved from `children:` to `reference:` stays in `Course.items` in the database, so it still counts toward completion and `progress_percentage`, takes a flat position and is offered due dates.
- **Validation.** Both check lists run the new rules: the one in `validate(path)` and the one `save_content_to_db` repeats for fixtures and downstream projects that call it directly. The rules reject:
  - a due key (`due_date`, `due_time`, `due_days_after_registration`, `no_due_date`) on a `reference:` entry, or on a topic inside a reference part;
  - a child of a reference part that is not a `Topic`: no `Form`, no nested `CoursePart`;
  - a part that is in both `children:` and `reference:` of the same course.
- **Offline validator.** The hand-synced copy in `claude_plugins/fls-content/validate/`, with its tests, mirrors the schema and the rules.
- **Admin.** An inline for `CourseReferencePart` on the course in Django admin, following `fls-dev:admin-interface` (`SiteAwareModelAdmin`).
- **Docs.** The author docs in `claude_plugins/fls-content/` and the product docs in `docs/product/` describe `reference:`, the layout, the rules and the cleanup.
- **Demo.** A demo course with a learning path, one reference part inside its own directory and one `../`-shared reference part. It is registered like the other demos and has a test beside them.

## Why

Courses need reference material that learners can consult at any time without it being part of what they must complete, such as the regulations in a drone-training course. The three sibling ideas (`reference-material-content-2-learner-reference`, `reference-material-content-3-educator-reference` and `reference-material-content-4-library-courses`) all read what this one stores, so authoring comes first. The learning path is walked by around 160 call sites; the separate model keeps reference parts out of completion, gating and deadlines without touching any of them.

The cleanup is part of this spec because the loader never deletes collection items: a part dropped from `children:` keeps its row in `Course.items`. A move into `reference:` would otherwise pass file validation and leave the database contradicting the files.

## What is settled

- Reference parts are attached through `CourseReferencePart(course, course_part, order)`; `Course.items` is unchanged. Reference parts hold topics only, one level deep.
- A real FK on `course_part` means deleting a part cascades its `CourseReferencePart` rows. `CourseReferencePart` is counted and deleted by `danger_content_delete` like the other content models.
- `reference:` entries are paths only. `../` sharing is allowed, and the target must be under the loaded `content_save` root, as for `children:`.
- Auto-discovery: a course directory's `reference/` is never read as learning path content. Today it is ignored only because it holds no direct content file; a direct content file in it would be adopted as a learning-path child. After this spec it is ignored by design. There is no auto-discovery of reference parts: the author lists every one under `reference:`, in the order to show. A course with `children:` omitted still auto-discovers its learning path.
- Reconciliation is replace semantics for `CourseReferencePart` rows: rows not named by the load are deleted for the courses in that load. The cleanup of old placements runs on the same load.
- The cleanup applies only to the course that lists the part. Another course placing the same part in its learning path keeps its collection item.
- The rule against due keys on topics in a reference part applies to every part a course lists under `reference:`. A part that one course places in its learning path with due keys on its topics cannot also be referenced by another course; authors keep reference parts free of due keys.
- A topic may be in both a learning-path part and a reference part of one course. Only a whole part is barred from both lists.
- Deadline resolver, deadline pickers and move detection are course-rooted and never reach a part with no placement, so reference topics get no deadlines and need no change there.
- Reference viewing writes nothing, so the `learner_progress` foreign keys to collection items need no change.
- Reference parts are `Topic` only, so `Form` `sections:` pointing at a reference part's topics are not extended by this spec.

## Open until the spec

- Whether the "part in both lists" and "no due keys in a reference part" rules need the part's topics resolved from disk in the same way `_ParsedByPath` does for a part outside the validated path.
- The exact wording of the save output that names removed items, and whether the removal is reported per course or per part.
- Whether a `reference:` entry that points at a file that is not a part (a topic, a form) fails in the schema or in the cross-file rules.
- Which existing tests that load the demo courses count parts and topics, so the new demo is a new course and leaves `functionality_demo_course_parts` and `functionality_demo_course_parts_placement` alone.
- Which of the other `fls-content` commands, agents and skills that mention children or layout need a line about `reference:` beyond the files named in the research.

## Out of scope

- Learner pages and course chrome (`reference-material-content-2-learner-reference`).
- Educator outline and content preview (`reference-material-content-3-educator-reference`).
- Courses with only reference material and a demo for them (`reference-material-content-4-library-courses`).
- Nesting deeper than part, then topics; PDFs and files; search; forms in reference parts.
- Deleting collection items for children dropped from `children:` in general; only the part listed under `reference:` is cleaned up.
- `qa_helpers` seeds for reference material.

## Resources

- `spec_dd/1. next/reference-material-content/idea.md`: the parent brief.
- `spec_dd/1. next/reference-material-content/research_content_loader.md`: how `content_save` discovers and writes children, where validation lives, the call-site audit, the docs and demo content affected. It moves into this child.
- `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`: vocabulary.
- The `fls-dev:admin-interface` skill: admin conventions.
- Collision: `sacaa-compliance-content-versions-and-access-1-content-save-safety` and `sacaa-compliance-content-versions-and-access-2-retire-removed-content` also change `content_save`, the schema and the validator; whichever lands second rebases.
