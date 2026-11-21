# R3: educator interface and reference material

Facts and risks only. Paths are relative to the repo root. Read against
`spec_dd/1. next/reference-material-content/idea.md`.

## 1. How the educator interface shows a Course's content today

### The page
- Section: `CourseConfig` (`freedom_ls/educator_interface/panels/course/config.py`), `url_name = "courses"`,
  `instance_view = CourseInstanceView`. Instance access: `CourseConfig.authorise_instance` raises
  `OrganisationScopeDenied` unless the course is in `courses_visible_to(user, organisation)`.
- `CourseInstanceView` (`panels/course/instance_view.py`) is one `CoursePanelStack`, no `TabSet`. Four
  stacked panels, in order: `details` (`CourseDetailsPanel`, `panels.py`), `content`
  (`CourseContentPanel`, `content_preview.py`), `cohorts` (`CourseCohortRegistrationsPanel`) and
  `learners` (`CourseLearnerRegistrationsPanel`) (the last two in `data_table_panels.py`).
- `panels/course/data_tables.py` is not about content: `CourseDataTable` (the list, counts of cohorts,
  learners, interest) and the two registration tables. None of it touches `Course.items`.

### The outline
- `CourseContentPanel` (title "Course content", `table_key = "outline"`, template
  `templates/educator_interface/panels/course_content.html`) is a `DataTablePanel` backed by
  `get_row_sequence` returning `outline_rows(course)`; the table is `CourseOutlineTable`
  (`has_child_rows`, `compact`, columns #, Title, Type, Actions, each its own
  `educator_interface/partials/course_outline_*.html`).
- `outline_rows(course)` builds a list of `OutlineRow` dataclasses (`kind` is `course | part | topic | form | page`):
  1. a first "Course details" row (`kind="course"`);
  2. one row per `course.collection_items()` (the learning path, `Course.items`), built by
     `_outline_item_rows`: a `CoursePart` is a group row whose children are `part.collection_items()`
     (or a note row "No items in this part."); a `Form` with more than one page is a group of page rows;
     anything else is a `topic` row;
  3. if the path is empty, a note row "No content in this course yet.".
  Numbers are `1.`, `1.1`; one flat nested walk, no depth cap beyond what the data holds (`_outline_item_rows`
  recurses into any part child).
- The outline pre-fetches `pages` for every form using `_all_collection_items` (recursive flatten of
  `course.collection_items()`).
- `entry_count` (the table footer, "N course outline items") uses `_outline_content_count`: every row at
  every depth except the details row and notes. A reference section merged into the same `OutlineRow`
  list would be counted in "course outline items".
- Whole panel is withheld when `_preview_available` is false (`is_course_available_to_organisation`,
  `learner_management/queries.py`): the template shows "Content preview isn't shared with your
  organisation." (`data-testid="preview-withheld"`), `outline` returns `[]`, `get_actions()` returns `[]`.
- A banner shows when `course.table_of_contents_in_development`.

### How a topic preview is reached
- Row button: `course_outline_actions.html` renders a `<c-modal-trigger>` to
  `{{ row_action_urls.preview_content }}?{{ object.preview_query }}`. `row_action_urls` is built by the
  framework from the panel's actions (`panel_framework/panels.py:254-266`); the URL is
  `ctx.base_url + "/__actions/preview_content"` (`panel_framework/actions.py:147,235`). So the URL is
  the course instance page URL plus the panel's `__actions/preview_content`, an HTMX GET only
  (non-HTMX raises `Http404`).
- Identity of the topic: the **`ContentCollectionItem` pk**, in `?item=<uuid>`; a Form page adds
  `&page=<FormPage pk>`. Not the index, not the slug. The course details row uses the sibling action
  `preview_course_details` with no query.
- `PreviewContentAction.get_context_data` finds the item with
  `next(item for item in _all_collection_items(course.collection_items()) if item.pk == pk)`. Its docstring
  states the contract: "the target is found among the authorised course's own collection items, so an id
  from any other course is as missing as a made-up one." A `CoursePart` item is a 404 (nothing to show).
  Template: `educator_interface/modal/content_preview.html` (wide modal, "<title> (Preview)", chip
  "Topic"/"Form"/"Form page", `child.rendered_content` in the reading column).
- **Risk (hard):** a reference Topic's `ContentCollectionItem` has `collection = <reference CoursePart>`,
  and that part is reached from a Course only through the new `CourseReferencePart`, not `Course.items`.
  `_all_collection_items(course.collection_items())` never sees it, so every reference Topic preview
  404s until the lookup also walks the reference parts. The same lookup is also what keeps another
  course's item id a 404, so a widened lookup must still be scoped to this course's reference parts
  (and a shared part, attached to several courses, must stay reachable only through a course that
  lists it).
- Permission gate: no per-action capability. Both preview actions set `capability = None`; the gates are
  (a) the section/instance gate (organisation scoping + `authorise_instance`) and (b) action
  availability: `get_actions()` returns `[]` when `_preview_available` is false, which is what makes a
  preview URL 404. A reference preview reuses this gate if it is exposed as an action of the same panel;
  a new panel/action needs its own `preview_available` withholding, or it leaks a library course's
  content to an organisation that holds only a registration on it (the `test_organisation_isolation.py`
  and `test_course_shares.py` invariants cover the existing actions).

## 2. Where a Reference section would naturally sit

Skills: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md` and `.../educator-interface/SKILL.md`.

Rules that bear on it:
- "Each panel does one job. A tab that does several jobs is a `PanelStack` of panels, one per job"; "A
  panel's title is the only heading for its job; nothing inside the panel repeats or nests a heading for
  a different job."
- The outline is "a numbered list with an action on each entry ... a data table inside
  `.panel-data-table`", `has_child_rows` + `get_child_rows`, `CourseOutlineTable` "is the worked
  example", `compact = True`. A group row is a part with its children; "An empty group shows its note as
  a child row."
- educator-interface skill, "Course outline and content previews": "lists the course outline as the
  panel framework's ordered-list data table, with a "Preview" button on every row"; the course details
  is the first row; a part is a group row; the type chip reads "Topic", "Form", "Form page" or "Course
  details"; previewed content sits in `max-w-reading`.
- Child rows cannot be combined with `row_detail_template_name` and cannot have bulk actions.

What the code and skills allow, as facts (not a decision):
- **A separate panel** in `CoursePanelStack.children` (after `content`) is the shape the skill's
  one-job-per-panel rule implies. It can reuse `CourseOutlineTable` and `OutlineRow` (a reference part is
  a `kind="part"` group row with topic children; `_outline_item_rows` already does this), and must own its
  own `table_key` (two tables on one page keep their own query-string slice) and its own empty and
  withheld handling. It needs its own `preview_available` or must share `CourseContentPanel`'s.
- **A section inside the existing outline**: the rows are one flat tree with one counter and one "Course
  details" first row. Rows would need a divider and a separate numbering (the learner outline numbering
  `1.`/`1.1` implies reference rows should not continue the path's numbers). A section heading inside a
  panel conflicts with the panel-framework rule "nothing inside the panel repeats or nests a heading for a
  different job", and the outline skill text describes exactly one list. No existing code has a
  non-numbered section in the outline.
- The educator-interface skill says nothing about reference material; the Placement table and "Course
  outline and content previews" section would need a line for it (skill edits go in `claude_plugins/fls-dev`,
  the FLS overlay; nothing FLS-specific in the generic plugins).
- The "Preview" modal reads `child.content_type == "FORM"` to pick the Form chip, otherwise "Topic", so a
  reference Topic previews with no template change; reference parts hold topics only (idea), so no Form
  path is needed for them.
- `CourseContentPanel.entry_count`, `outline`, `preview_available` and `get_actions` are on one class; a
  second panel would duplicate or factor the `preview_available` gate.

Library-only course in this page:
- `outline_rows` appends the note "No content in this course yet." whenever `Course.items` is empty. For a
  library course that note is **misleading** (the course has content, in Reference); it would need to
  consider reference parts too.
- `CourseDetailsPanel` "Lessons" row reads `course.lesson_count()` (`Course.lesson_count`,
  `content_engine/models/courses.py:544`, from `viewable_items()` = learning path only). For a library
  it is 0, and `get_rows` only drops values equal to `""` or `empty_value_display`, so a `0` is probably
  shown as "Lessons 0" (not verified by running). Not a crash; misleading for a library. The same
  `lesson_count` feeds the learner details page (`content_engine/course_details.py:9-11`, "0 lessons"), and
  `PreviewCourseDetailsAction` reuses `course_details_context`.

## 3. Other educator pages: per-course counts and per-item progress, for a course with an empty learning path

Every reader below takes the learning path (`viewable_items()` / `viewable_collection_items()` /
`collection_items()`); none walks anything else, so reference material is invisible to all of them
(good: it must not count). The question is what an empty path does.

| Surface | Code | Library-only course (empty path) |
|---|---|---|
| Course progress percentage | `learner_progress/utils.py:24 calculate_course_progress_percentage` | Returns 0 (`if not completable: return 0`). No division. Misleading only as "0%". |
| Cohort report (completion, per-learner counts) | `reports/gather.py:274 _completion_percentage`, `_completion_counts` over `reports/indexes.py:238 build_course_catalogue` (`reg.course.viewable_items()`) | Docstring: "0 rather than a division error for an empty course". Empty, not crash. Shows 0% complete, 0 of 0 items; no catalogue entries for the course. |
| At-risk flags | `reports/at_risk.py:70 NoRecordedActivityRule`, `:114 InactiveForDaysRule` | Explicitly guarded: `total_item_count == 0` returns no flag ("a cohort registered for no course, or for an empty one"). Inactive rule only fires when `last_completed_at` exists; `completed_item_count >= total_item_count` (0 >= 0) also returns no flag. Safe, and correct for a library. |
| Cohort "Course completion" panel | `educator_interface/views.py:1198 CohortCourseCompletionPanel` (moves to `panels/cohort/panels.py` in refactor-6) | Counts `CourseProgress` rows and `completed_time` not-null; `percentage = ... if record_count else 0`. Learner side sets `completed_time` only in the course finish flow (`learner_interface/views.py:2327`), which a library never reaches, so a library course reads "0 of N completed" for ever: not a crash, misleading ("N learners have not completed" a thing with nothing to complete). Whether `CourseProgress` rows are minted for library registrations is by registration, not by items (`learner_progress/utils.py ensure_course_progress_record`), so they are. |
| Learner Courses tab / table cell / quick view | `views.py:387 learner_course_summaries` (-> `panels/learner/...` in refactor-5), `templates/.../data-table-cells/learner_courses.html:12`, `quick_views/learner.html:28`, `LearnerCoursesPanel` (`reporting.py:255`) | Show the stored `CourseProgress.progress_percentage`. A library shows "0%" or "No progress yet" for ever. Not a crash. |
| Move-learner preview | `learner_progress/queries.py:203 move_progress_preview` | "continues at 0%". Cosmetic. |
| Dashboard attention list | `educator_interface/panels/dashboard/` using the same `reports` gatherers | Same guards as the cohort report; not read in detail. |
| Deadlines "outline" | Not in the educator interface: `freedom_ls/deadlines/admin.py:295,426`, `admin_views.py:144`, `forms.py:103`, `models.py:69,579` all read `course.viewable_collection_items()` and `resolver.py:211,224` queries `ContentCollectionItem.objects.filter(...)` directly. | Empty path means an empty deadline outline; no crash found. The idea's risk stands: the resolver code that "assumes every part has a placement in a course" is in `deadlines/resolver.py` (not read in full here, see R-deadlines research if any); a reference-only part has no placement. |

Summary for the idea's "learner side must handle an empty path" list, from the educator side: no crash
found in any reader above; the failure mode is a perpetual "0%"/"0 of N completed"/"No progress yet"
for a library registration, plus the "No content in this course yet." note and "Lessons 0" in the course
page itself. Whether libraries should show completion at all is a product decision, not a code defect.

## 4. Django admin

`freedom_ls/content_engine/admin.py`:
- `CourseAdmin` (line 185) and `CoursePartAdmin` (line 264) extend `SiteAwareModelAdmin`; both carry
  `inlines = [ContentCollectionItemInline]`, a `GenericTabularInline` (line 159) over the learning path
  (`child_type`, `child_id`, `order`, due fields read-only).
- With no inline, a `CourseReferencePart` is invisible on the course's admin page and its only admin
  surface would be a changelist of its own (it is a new model, and the idea says it is "the only new table";
  an unregistered model has no admin at all). The repo's own convention is to register inline editors
  for through models (e.g. `CoursePartChildDueDateInline`, `ContentCollectionItemInline`), so an inline
  on `CourseAdmin` for `CourseReferencePart` (FK `course`, with `course_part` and `order` as fields) is
  the pattern in use.
- `fls-dev:admin-interface` rules (`claude_plugins/fls-dev/skills/admin-interface/SKILL.md`): admin classes
  extend `SiteAwareModelAdmin`; "Inlines use `SiteAwareTabularInline` or `SiteAwareStackedInline`";
  never expose `site`; the ds `admin_unfold.md` says use Unfold's `TabularInline` and
  `autocomplete_fields` for FK/M2M.
  - **Discrepancy:** `SiteAwareTabularInline`/`SiteAwareStackedInline` do not exist in
    `freedom_ls/site_aware_models/` (grep for `Inline` there returns nothing), and the existing
    `CoursePartChildDueDateInline` uses Unfold's plain `TabularInline`. The skill and the tree disagree;
    per project rules the skill text is the source of truth for new code, so the spec must say whether to
    create the site-aware inline base or follow the existing practice.
  - `autocomplete_fields = ["course_part"]` is possible: `CoursePartAdmin` already sets
    `search_fields = ("title", "subtitle", "description")`.
  - `ContentCollectionItemInline.can_delete = False`, `has_delete_permission` is `False` on
    `CourseAdmin` and `CoursePartAdmin`: delete is a deliberate project stance (deletion goes through
    `danger_content_delete.py`, per the idea's "things to check"). The inline's delete flag is a policy
    decision, as it is in `ContentCollectionItemInline`.
  - `CourseAdmin` has `readonly_fields` for loader-managed fields (`slug`, `visibility`, ...): the loader
    writes course data from `course.md`, so an inline that edits reference parts competes with the
    loader's `reference:` key. `ContentCollectionItemInline` is editable today (`extra = 1`) with the
    same overlap, so there is a precedent for an editable inline over loader-owned data.
- `CoursePartAdmin` (which part is used as reference) has no reverse view; an inline over
  `CourseReferencePart` on `CoursePartAdmin` (the part's side) is optional, not required for the educator
  interface.

## 5. Collisions with the educator-interface-refactor specs

Status: `educator-interface-refactor-4-course` has landed (`panels/course/` exists with `config.py`,
`content_preview.py`, `data_table_panels.py`, `data_tables.py`, `instance_view.py`, `panels.py`; templates
are still in the flat `templates/educator_interface/{panels,partials,modal}/`).
`-5-learner` is in `spec_dd/2. in progress/`; `-6-cohort` and `-7-cleanup` are in `spec_dd/1. next/`.

Neither -5 nor -6 moves any file in `panels/course/` (grep of the three ideas and the -5 todo for
`panels/course`, `CourseConfig`, `course_content`, `content_preview`, `outline` finds none, apart from -7's
mention of `educator_tags.py`). Files a Reference section would touch and who else touches them:

- `panels/course/content_preview.py`, `panels/course/instance_view.py`, `panels/course/panels.py`,
  `panels/course/config.py` (only if section config changes): **no collision**; not moved by -5/-6/-7.
  Note `educator_interface/tests/panels/course/test_content_preview.py` is the mirrored test home.
- `educator_interface/templates/educator_interface/panels/course_content.html` and the
  `partials/course_outline_*.html` and `modal/content_preview.html` templates: not moved by any of the
  three (the refactor is "No ... template path changes" in -6 and -7).
- `panels/common/tables.py` (`_course_title_column`, `_registration_columns`, ...) used by
  `panels/course/data_tables.py`: a shared home; relevant only if the Reference section reuses a column
  helper.
- **Possible collisions:**
  - `freedom_ls/educator_interface/views.py` still holds `LearnerCourseSummary`/`learner_course_summaries`
    (V:379-412), `CohortCourseCompletionPanel` (V:1198), and `reporting.py` holds `LearnerCoursesPanel`:
    these are the surfaces in section 3 whose wording would change if a library course gets special
    treatment. -5 moves the learner ones (`LearnerCourseSummary`, `learner_course_summaries` and
    `educator_tags.py` per its idea line 81), -6 moves `CohortCourseCompletionPanel` into
    `panels/cohort/panels.py`. A spec that edits them for libraries must wait for or rebase onto those moves.
  - `educator_interface/urls.py`, `views.py` (shell) and the flat `actions.py`/`filters.py`/
    `quick_views.py`/`reporting.py`: -7 deletes or trims them. A Reference section, being in
    `panels/course/`, needs none of them; adding anything to a flat module would be lost to -7.
  - Shared test files `tests/test_views.py` and `tests/test_actions.py` are being split by each spec;
    tests for the Reference section belong in `tests/panels/course/` (exists already).
  - `test_organisation/mirroring_baseline.txt`: every new module under `panels/course/` needs its mirror
    test file; -7 clears remaining `educator_interface` lines.
- The educator-interface skill edit (Course outline section) is outside all three specs' file lists
  except -7's `SKILL.md:41` (`filters.py` mention); a one-line conflict risk only.

## Risks, short list
1. Reference topic previews 404 unless the preview lookup in `PreviewContentAction` is widened to the
   course's reference parts; the lookup is also the cross-course isolation guard.
2. The "No content in this course yet." note and the "Lessons" count read as empty/zero for a library.
3. `entry_count` / `_outline_content_count` and `OutlineRow` numbering assume one path; reference rows
   need separate counting and numbering or they inflate "course outline items".
4. A new panel or action must reuse the `_preview_available` withholding (organisation registered-only
   courses), or a reference preview leaks content across organisations.
5. Cohort and learner progress surfaces show "0%" / "0 of N completed" / "No progress yet" for a library
   registration for ever; no crash anywhere (guards exist in `_completion_percentage`,
   `calculate_course_progress_percentage`, `at_risk.py`, and the `record_count` check).
6. Admin skill requires `SiteAwareTabularInline`, which does not exist; existing code uses Unfold's
   `TabularInline`.
7. Deadlines code (`deadlines/resolver.py:211,224`, `admin.py`, `forms.py`, `models.py`) is outside the
   educator interface and is not analysed in depth here.

status: ok
