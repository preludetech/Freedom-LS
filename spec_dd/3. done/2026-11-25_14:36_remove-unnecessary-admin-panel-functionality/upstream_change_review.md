# Upstream-change review: remove-unnecessary-admin-panel-functionality

direction: changed

## What main gained

The finished spec `reference-material-content-1-authoring` (31 commits) added the `CourseReferencePart` model (migration `0016_course_reference_part.py`), a `reference:` list in course frontmatter loaded by `content_save`, new validation, and a `danger_content_delete` count. It also changed shared base files (`content_base/schema.py`, `content_engine/schema.py`) and the `fls-content` plugin. None of that touches an app boundary in `docs/app_structure.md`.

The one overlap with this spec is the admin. Batch 8 added `CourseReferencePartInline` (a read-only unfold `TabularInline`) to `freedom_ls/content_engine/admin.py` and put it on `CourseAdmin.inlines`. It has these concrete facts:
- `freedom_ls/content_engine/tests/test_admin.py` gained `TestCourseReferencePartInline`, which imports `CourseReferencePart` and `CourseReferencePartFactory`. Deleting `content_engine/admin.py` makes this test class dead. Delete it, and delete the whole `test_admin.py` if nothing else survives.
- `CourseReferencePart` is a new `content_engine` model with a `CourseReferencePartFactory`. The "every removed model is unregistered" parametrised test must include it. It was registered only as an inline, so `is_registered` is already False. List it anyway, so the test covers every content_engine model.
- `claude_plugins/fls-dev/skills/admin-interface/SKILL.md` line 17 cites `CourseReferencePartInline` in `content_engine/admin.py` as the example of an unfold inline. That file will no longer exist.
- `docs/product/admin-interface.md` line 165 says a course's admin page lists its reference parts. That page goes away.
- Other main changes outside the admin (`danger_content_delete`, the deadlines and learner_progress invariant tests, `content_save`) do not touch the admins this spec edits. `form_engine/admin.py`, `learner_management/admin.py`, `deadlines/admin.py` and `learner_progress/admin.py` are not in the overlap list.

## Why it matters for this spec

The done spec `spec_dd/3. done/2026-11-22_16:35_reference-material-content-1-authoring/1. spec.md` (Admin section, line 114) explicitly decided that the course admin shows its reference parts read-only. Its plan Slice 8, and the product doc line it required, follow from that. This spec's Purpose says content "must not be viewed in the admin" and deletes `content_engine/admin.py` whole. That reopens the done decision. It is not a conflict of mechanism, because the inline simply goes with the file. But this spec's Decisions section never records that the reference-parts view is being given up on purpose. Nor does it say that no other screen replaces it. Educators lose the only place that showed which parts are reference parts. Nothing in `spec_dd/1. next/roadmap.md` says the inline is a prerequisite. The reference-material-content-3-educator-reference spec only mentions the inline as a precedent. The spec also fails to name the two artifacts above that cite the inline, and its docs list (`admin_interface.md` resource) does not include the skill file.

## What to change

- `1. spec.md`, Decisions: add a bullet that the read-only `CourseReferencePartInline` from `reference-material-content-1-authoring` is removed with `content_engine/admin.py`, that it has no replacement, and that `reference-material-content-3-educator-reference` is where reference parts get an educator-facing view.
- `1. spec.md`, Testing: say that `CourseReferencePart` is in the parametrised unregistered list. Say that `content_engine/tests/test_admin.py` (including `TestCourseReferencePartInline`) is deleted with the admin.
- `1. spec.md`, Documentation and downstream: add `claude_plugins/fls-dev/skills/admin-interface/SKILL.md` line 17 (replace the `CourseReferencePartInline` example with a surviving inline, e.g. one in `deadlines/admin.py`) and `docs/product/admin-interface.md` line 165 (delete the reference-parts sentence). Add the removed inline to the upgrade-notes list of capabilities leaving the admin.
- `spec_dd/1. next/` reference-material-content-3 idea (if it names the admin inline as an existing deliverable): note the inline no longer exists.

status: ok
