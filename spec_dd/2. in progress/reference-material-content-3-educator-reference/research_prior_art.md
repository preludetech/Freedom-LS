# Prior art: educator "Reference" panel on the course page

Scope note: the worker had no shell, so `git log` was not run. Findings come from the done specs, the skills and the code.

## Here: what earlier specs decided and what QA found

### `educator-interface-course-content-preview` (done 2026-11-12)
Path: `spec_dd/3. done/2026-11-12_11:54_educator-interface-course-content-preview/`.

- **Decided.**
  - The outline is the panel framework's ordered-list data table, with a "Preview" button on every row.
  - The course details are the first row.
  - A part, or a form with more than one page, is a group row. Each page of a multi-page form is its own row.
  - Type chips read "Topic", "Form", "Form page" and "Course details".
  - Previewed content sits in the reading column (`max-w-reading`), inside a wide modal ("<title> (Preview)").
  - Previews write no progress. QA checked the counts of TopicProgress, CourseProgress, FormProgress, QuestionAnswer and AuditLogEntry before and after, and they were unchanged.
- **QA.** `qa_report.md` has 0 bugs and all pass, at 1920, 768 and 375. Test 8.2 was skipped. The relevant passes:
  - 2.3: chevrons collapse children and reload reopens all groups.
  - 2.4: an empty part shows the child row "No items in this part."
  - 2.6: preview URLs are `.../courses/<pk>/__panels/content/__actions/preview_content?item=<uuid>`, with `&page=` for form pages.
  - 9.1 to 9.5, the isolation probes. All were 404:
    - no HX-Request;
    - another course's item;
    - a part item;
    - a malformed or zero uuid;
    - POST;
    - another organisation's educator;
    - a superuser on a foreign-organisation course.
  - 11.x: no horizontal overflow on mobile, and Preview buttons are 44px on mobile.
- **Observations to carry over.**
  - At 1920 the Preview button sits at the far right of the actions column, far from short titles. This was recorded as a pass, per the panel-framework data-table rule.
  - Every `#app-modal` reserves a scrollbar gutter, so its right padding reads wider than the left. This was recorded as a pass.
  - The seed put the content-link in "Reading", not "Welcome".
- **Upgrade notes.** They list template changes in `modal_host.html` (`data-modal-size="wide"`, bottom fade) and `table_toolbar.html`, and a Tailwind rebuild. New templates need a Tailwind rebuild.

### `educator-interface-course-list-shows-too-much` (done 2026-11-19), which introduced withholding
- The plan added `_preview_available(request, course)`. It wraps `is_course_available_to_organisation`.
- `CourseContentPanel.preview_available` is a `cached_property`. When it is false:
  - `outline` returns `[]`;
  - `get_actions()` returns `[]`, which is what makes a preview URL a 404 (actions resolve only from `get_actions()`);
  - the template shows `<c-panel-empty-state message="Content preview isn't shared with your organisation." data-testid="preview-withheld">`.
- QA found one bug (B1): an inactive registration on a no-longer-shared course had no Reactivate button. It was left unresolved as a product decision. It is not about previews, but it shows that "registered only" courses are an edge that QA exercises. Run tests at the `preview_available` boundary (shared, owned, registered-only).

### `educator-interface-refactor-4-course` (done 2026-11-21)
- It built `panels/course/`: `config.py`, `content_preview.py`, `data_table_panels.py`, `data_tables.py`, `instance_view.py` and `panels.py`.
- `CoursePanelStack` order is details, content, cohorts, learners. Panels keep their own `table_key` (the outline uses `outline`), and the framework gives each table its own query-string slice.
- The grep found no bug or regression notes in its QA, todo or upgrade notes.

### `reference-material-content-1-authoring` (done 2026-11-22)
- It added `CourseReferencePart(course, course_part, order)`. `Course.items` stays the learning path.
- QA: all pass, 0 bugs, in the Django admin only.
  - The reference parts inline is read-only.
  - A second `content_save` is stable.
  - The demo course "Reference Material" has parts Airspace Rules (two topics, Airspace Classes and No-fly Zones, which "(0)" and "(1)" are positions of) and Glossary (1).
  - Use it for QA seed data: `content_save ./demo_content DemoDev`.
- Roadmap decisions that bind this spec:
  - reference parts hold topics only, one level deep;
  - a topic may sit in both a learning-path part and a reference part, and only a whole part is barred from both lists of one course.
- The second point matters for the lookup: the same `ContentCollectionItem` pk namespace is searched, so widening must stay course-scoped.

### The existing parent research: `spec_dd/1. next/reference-material-content/research_educator_content.md`
Pitfalls to design against. Cites are to that file, sections 1, 2 and 5.
1. **Hard risk.** `PreviewContentAction` looks the item up with `_all_collection_items(course.collection_items())`, which never sees reference parts, so reference previews 404 until the lookup also walks `CourseReferencePart` parts. The lookup is also the cross-course isolation guard. Widen it to this course's reference parts only. The existing docstring promises that an id from another course is "as missing as a made-up one".
2. **Gate must not drift.** The withholding lives on `CourseContentPanel` (`preview_available`, `outline`, `get_actions`). A second panel that omits `preview_available`, or the `get_actions()` empty list, leaks library content to an organisation that holds only a registration. The invariants in `test_organisation_isolation.py` and `test_course_shares.py` cover the existing actions. Add the Reference actions to those.
3. **Action URL carries the panel key.** Actions are panel-scoped, so the second panel's own `preview_content` is at its own `__panels/<key>/__actions/...`. The panel needs its own `table_key`. Two tables on one page keep separate query-string slices (panel-framework skill).
4. **Counting and numbering.** `_outline_content_count` counts every non-course, non-note row at every depth. Merging reference rows into `outline_rows` would inflate "course outline items" and continue the path's numbers. A separate panel and row list avoids both.
5. **Notes rows.** `OutlineRow` with `note` set is how an empty group shows its text ("No items in this part."). A reference part with no topics should reuse it. `outline_rows` appends "No content in this course yet." only for the course panel. Leave it alone for library wording (spec 4).
6. **Preview template.** `modal/content_preview.html` picks the "Form" chip only when `child.content_type == "FORM"`, else "Topic". Reference topics preview with no template change.
7. **Skills.** The panel-framework skill says that a panel's title is its only heading, and the educator-interface skill describes the outline as exactly one list. A divided section inside the outline panel is ruled out, as the idea states.
8. **Collisions.** Nothing in `panels/course/`, `course_content.html`, `partials/course_outline_*.html` or `modal/content_preview.html` is moved by refactor-5, -6 or -7. Put tests under `tests/panels/course/` (`test_content_preview.py` mirrors the module). Every new module under `panels/course/` needs a mirror test file (`mirroring_baseline.txt`). Do not add code to flat `educator_interface` modules, because -7 trims them.
9. **A later effort touches the same gate.** `sacaa-compliance-content-versions-and-access-4-question-access` plans a new organisation-scoped role that gates "the content preview". Keep the Reference preview on the shared gate, so one change covers both panels.
10. **`_preview_available` is not in the stack only once.** It is module-level, exported in `__all__` with the private helpers. A shared helper or base class keeps one source for the gate. The idea leaves how to share it to the spec.

### Skill text to extend
`claude_plugins/fls-dev/skills/educator-interface/SKILL.md`: "Course outline and content previews" (lines 44-58) and the "Visual checklist" (line 79-80). No feedback about previews has been captured into either skill beyond what is listed above. The visual checklist should gain a line, such as a Reference panel after "Course content" with its own numbering, separate from the learning path.

## Elsewhere: instructor-only resources in other LMSs
Brief. These show the common workaround patterns and their traps.
- **Canvas.** Instructors usually keep instructor-only material in an unpublished page. Community answers warn that a hidden link is not access control, and that a published module must not link to the unpublished page. Lesson for FLS: withhold on the server (empty `get_actions()`, 404), not by hiding. Sources:
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Hidden-Instructor-Notes/m-p/63182
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Lock-students-from-accessing-trainer-resources/m-p/649412
- **Moodle.** A hidden section hides everything in it, so teachers use that as a staff-only area. The cost is that the area looks like ordinary content in the editing view. Reference there is a separate section, as the FLS panel will be. Source: https://bookstack.kb.ucla.edu/books/ccle-and-moodle/page/how-are-files-handled-in-moodle-webct-and-sakai
- Common failure: the staff-only area is a hand-made workaround rather than a first-class object, so it gets lost in migration and renames. Hence the FLS decision to make reference parts a model, shown in its own labelled panel.
- The web search was one shallow query, and the results are forum answers. They support the general pattern only.

status: ok · reason: complete from done specs, the parent research and the code; `git log` not run (no shell tool)
