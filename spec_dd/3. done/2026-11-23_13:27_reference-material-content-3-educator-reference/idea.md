# Educator reference: reference parts in the course page and their preview

Spec 3 of 4 in the Reference material effort. Read the "Reference material" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An educator who opens a course in the educator interface sees the course's reference parts and
their topics in a Reference section of the course page, apart from the learning-path outline, and
can preview any reference topic from there. The preview is the one learning-path topics already
use.

## Why

Reference material is meant to be visible to educators like other content. Today the course page
lists only `Course.items`, so reference parts attached by `reference-material-content-1-authoring`
would be invisible to the people who review a course, and a reference topic's preview would 404
because the preview lookup walks only the learning path.

## What is settled

- **Placement.** The Reference section is its own panel in the course page's panel stack, titled
  "Reference", directly after the "Course content" panel. The panel-framework skill gives each
  panel one job and the only heading for it, and the educator-interface skill describes the outline
  as exactly one list, so a divided section inside the outline panel is ruled out.
- **Rows.** A reference part is a group row with its topics as child rows, in the same outline table
  shape as the learning path, with a "Preview" button on each topic row. Rows are numbered within
  the section (`1.`, `1.1`), not continuing the learning path's numbers. A reference part with no
  topics shows the group's empty note, as a learning-path part does.
- **No deadline or progress columns.** Reference rows carry neither, as the learning-path outline
  already carries neither.
- **Counts.** Reference rows are not counted in the "Course content" footer's "course outline
  items"; the Reference panel's own footer counts its rows.
- **Preview.** A reference topic opens in the same wide content preview as a learning-path topic,
  titled "<title> (Preview)" with the "Topic" chip and the content in the reading column.
- **Permission and withholding.** The Reference panel obeys the same organisation scoping and the
  same `preview_available` withholding as "Course content": an organisation that holds only a
  registration on a course sees the same "Content preview isn't shared with your organisation."
  note and no preview actions, so a reference preview URL is a 404 there too.
- **Lookup scope.** The `PreviewContentAction` lookup is widened to the course's own reference
  parts only. A collection item from another course stays a 404, and a part shared by several
  courses is reachable only through a course that lists it.
- **Course area.** The work stays in `panels/course/`, which the `educator-interface-refactor-*`
  specs do not move, so it does not collide with them.
- **Skill.** `claude_plugins/fls-dev/skills/educator-interface/SKILL.md` ("Course outline and
  content previews" and its visual checklist) gains the Reference section; the generic plugins
  are untouched.

## Open until the spec

- Whether the Reference panel shows when the course has no reference parts: nothing at all (the
  likelier choice, since most courses have none) or a panel with an empty state.
- How the two panels share the `preview_available` gate and the outline table, so the withholding
  cannot drift apart.
- Whether the empty-state note in "Course content" changes for a course whose learning path is
  empty but which has reference parts. That is library wording and belongs to
  `reference-material-content-4-library-courses`; the spec only confirms nothing here blocks it.

## Out of scope

- Library-only course wording ("Lessons 0", "No content in this course yet", "0 of N completed",
  "0%"): `reference-material-content-4-library-courses`.
- The Django admin inline for reference parts: `reference-material-content-1-authoring`.
- Learner-side reference reading: `reference-material-content-2-learner-reference`.
- Editing, reordering or attaching reference parts from the educator interface.
- Forms, PDFs and files in reference, and nesting deeper than part, then topics.

## Resources

- `spec_dd/1. next/reference-material-content/idea.md` (the original brief)
- `spec_dd/1. next/reference-material-content/research_educator_content.md` (sections 1, 2 and 5:
  the outline, the preview lookup and its isolation contract, placement options, collisions)
- `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`
- `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`
