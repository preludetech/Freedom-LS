# Codebase research: what educator reference touches, reuses and conflicts with

Facts verified against the current worktree (branch `reference-material-content-3-educator-reference`,
spec 1 landed). Paths are repo-relative. Extends, and does not repeat,
`spec_dd/1. next/reference-material-content/research_educator_content.md`; where this file differs
from it, this file is current.

## 0. What spec 1 left us

- Model: `CourseReferencePart(SiteAwareModel)` in `freedom_ls/content_engine/models/courses.py:680`.
  Fields `course` (FK to `Course`, `related_name="reference_parts"`), `course_part` (FK to
  `CoursePart`, `related_name="+"`), `order`. `Meta.ordering = ["order"]`; constraint
  `one_reference_part_per_course_part` on `(course, course_part)`. Migration
  `content_engine/migrations/0016_course_reference_part.py`. Exported from `content_engine.models`.
  Factory: `CourseReferencePartFactory` (`content_engine/factories.py:134`; builds course and part
  unless given).
- There is NO helper on `Course` for reference rows (no `reference_collection_items()`), and no
  `Course.reference_parts` prefetch convention. `Course.collection_items()` (line 482) is learning path
  only, memoised per instance; `CoursePart.collection_items()` (line 584) is memoised per instance too.
  `Course.viewable_items()`, `lesson_count()`, `includes_assessments()` read the learning path only,
  so reference rows are invisible to every count (good; nothing to guard).
- A reference part is an ordinary `CoursePart`; its topics are ordinary `ContentCollectionItem`s whose
  `collection` is that `CoursePart`. A reference part is not a `ContentCollectionItem` of the course.
  Hence the item id used by the preview (`?item=<ContentCollectionItem pk>`) is the topic's own
  placement in the part, which exists and is unique per placement.
- Validation (spec 1, `content_engine/validate.py:1028 _reference_part_errors`) rejects a non-topic
  child of a reference part and any `due` key, and a part that is both a child and reference of one
  course; `content_save.py:983 sync_reference_parts` writes the rows. So in practice a reference part
  holds topics only and one level, but the DB does not enforce it (admin inline is read-only:
  `content_engine/admin.py:186 CourseReferencePartInline`, on `CourseAdmin.inlines`, line 228).
  Row builders must not crash on a Form or nested part in a reference part, though they need not show
  them specially (see section 2).
- Demo content to QA with: `demo_content/functionality_demo_reference_material` ("Functionality Demo -
  Reference Material", `content_engine/tests/demo_content/test_reference_parts.py`): one in-course
  `reference/` part and one shared from outside.

## 1. How the educator course page builds its panel stack

- `CourseConfig` (`freedom_ls/educator_interface/panels/course/config.py`): `url_name = "courses"`,
  `instance_view = CourseInstanceView`, `authorise_instance` raises `OrganisationScopeDenied` unless
  the course is in `courses_visible_to(user, organisation)` (an unseen course 404s for every panel
  and every action beneath it).
- `panels/course/instance_view.py`: `CoursePanelStack(PanelStack).children` is a plain dict, order
  = render order: `details` -> `CourseDetailsPanel` (`panels.py`), `content` -> `CourseContentPanel`
  (`content_preview.py`), `cohorts` -> `CourseCohortRegistrationsPanel`, `learners` ->
  `CourseLearnerRegistrationsPanel` (both `data_table_panels.py`). `CourseInstanceView.panel =
  CoursePanelStack`. No `TabSet`: one scrolling page of cards. Adding the Reference panel is one dict
  line, `"reference": CourseReferencePanel`, between `content` and `cohorts`.
- `panels/course/data_tables.py` and `data_table_panels.py` are registration tables; none reads
  `Course.items`. Nothing to touch.
- Child key becomes the URL segment and DOM hook: panels render as `section[data-panel='<key>']`, and a
  panel's actions resolve at `courses/<pk>/__panels/<key>/__actions/<action_name>`
  (`panel_framework/views.py:_resolve_action`: actions resolve from `current.get_actions()` of the
  addressed panel only). So the Reference panel's preview URL is
  `.../__panels/reference/__actions/preview_content`, a different URL from Course content's
  `.../__panels/content/__actions/preview_content`, even though the action class is shared. The test
  helper `_content_action_url` (`educator_interface/tests/helpers.py:289`) hard-codes `__panels/content`.
- `table_key` must be unique within the container, enforced by a system check
  (`panel_framework/checks.py:362 _check_no_duplicate_table_keys`). Course content uses `"outline"`
  (DOM ids `outline-table`, `#outline-table-caption`); Reference needs its own, e.g. `"reference"`.
  `table_key` also namespaces query-string params (`<table_key>-page`).
- `DataTablePanel` backed by a sequence (`get_row_sequence`) forbids search/filters/sortable columns/
  export columns/bulk actions and needs `noun` and `noun_singular` (`panel_framework/panels.py:334
  _check_sequence_table`). `has_child_rows` tables cannot have bulk actions or
  `row_detail_template_name`.
- Template `educator_interface/templates/educator_interface/panels/course_content.html` extends
  `panel_framework/panels/_data_table_base.html`; it overrides `panel_header` (the "table of contents in
  development" info callout, shown only when `preview_available and course.table_of_contents_in_development`)
  and `panel_body` (`{% if preview_available %}{{ block.super }}{% else %}<c-panel-empty-state
  message="Content preview isn't shared with your organisation." data-testid="preview-withheld" />`).
  It reads the context keys `preview_available` and `course` that `CourseContentPanel.get_context_data`
  adds. The "in development" callout is about the learning-path outline and must not be repeated on the
  Reference panel (a reference panel template either does not extend this one as is, or the callout
  needs a flag). Withheld-note `data-testid="preview-withheld"` already exists once per page; a second
  one on the Reference panel would make page-wide selectors ambiguous (existing test scopes its query
  to `section[data-panel='content']`, so it keeps working).
- Outline cell partials (shared, kind-driven, no panel-specific text): `partials/course_outline_number.html`,
  `_title.html` (icon from `OutlineRow.icon`: part -> folder, topic -> topic; sr-only kind label),
  `_type.html`, `_actions.html` (`kind == "course"` -> `row_action_urls.preview_course_details`;
  `elif object.preview_query` -> `row_action_urls.preview_content?<preview_query>`; aria-label
  "Preview <title>"), `_note.html`, `_card.html`. `row_action_urls` is built from the bound panel's own
  `get_actions()` (`panel_framework/panels.py:254-266`), so a Reference panel whose `get_actions()`
  returns only `PreviewContentAction()` would render preview triggers pointing at its own URL, and
  would have no `preview_course_details` key (never used: reference rows are never `kind="course"`).
  No cell partial needs a change.

## 2. The "Course content" outline: rows, numbering, notes, count

All in `panels/course/content_preview.py`.

- `OutlineRow` (frozen dataclass): `number`, `title`, `kind` in `course|part|topic|form|page`,
  `preview_query`, `children`, `note`, `form_title`; `kind_label`, `icon` properties.
- `outline_rows(course)`: prefetches `pages` for every `Form` found by `_all_collection_items(
  course.collection_items())`; first row `OutlineRow(number="", title="Course details", kind="course")`;
  then `_outline_item_rows(item, str(position), nested=False)` for each `course.collection_items()`
  item; if there are none, a `kind="course"` note row "No content in this course yet.".
- `_outline_item_rows(item, number, *, nested)`: takes a `ContentCollectionItem`. `label = number if
  nested else f"{number}."` (so top-level reads `1.`, nested `1.1`). If `item.child` is a `CoursePart`:
  children are `_outline_item_rows(part_item, f"{number}.{position}", nested=True)` over
  `child.collection_items()`, or the note row "No items in this part." (a `kind="part"` row with
  `number=""`, `title=""`, `note=...`). A multi-page `Form` becomes a group of `page` rows; anything else a
  `topic` row with `preview_query=f"item={item.pk}"`.
  - Consequence for reference: a reference part is NOT a `ContentCollectionItem`, so
    `_outline_item_rows` cannot be called on it as it stands. The part branch (lines 107-125) needs to be
    lifted into a function that takes a `CoursePart` and a `number`/`label` (e.g. `_part_row(part, number,
    nested)`), which `_outline_item_rows` then calls for its part case and a new `reference_rows(course)`
    calls for each `course.reference_parts` row. That reuses the empty-part note ("No items in this
    part.") and the topic rows with no copying, and gives the idea's `1.` / `1.1` numbering restarted per
    section for free.
- `_outline_content_count(rows)`: counts every row at every depth except `kind == "course"` and note
  rows. `CourseContentPanel.entry_count` -> `count_phrase(count, noun_singular, noun)`, "" when 0. A
  reference part counts as 1 and each topic as 1, same as a learning-path part. Reference rows are kept
  out of the Course content count simply by being built into a different row list (the panel's `outline`
  does not include them).
- `CourseOutlineTable(DataTable)`: `has_child_rows`, `compact`, `noun = "course outline items"`,
  `noun_singular = "course outline item"`, `card_template_name`, four columns (#, Title, Type, Actions),
  `get_rows` returns every row on one page (`Paginator(queryset, max(len(queryset), 1))`),
  `get_child_rows`, `get_row_label`, `get_row_template_name` (note rows -> `course_outline_note.html`).
  The footer text comes from `noun`: a Reference panel wants its own noun (e.g. "reference items" /
  "reference item"; wording is a spec decision), so it needs its own table class: a plain subclass
  `class ReferenceOutlineTable(CourseOutlineTable): noun = ...; noun_singular = ...` (concrete
  inheritance, not an ABC) or a small override.
- Course-details row and `table_of_contents_in_development` banner belong to Course content only.
- Empty state: for "Course content" the empty case is the note row (a `kind="course"` row with `note`)
  inside the table, not the table's own empty state. For the Reference panel the user chose "show with an
  empty state" (`answers.md`). Two ways: (a) when `course.reference_parts` is empty, return `[]` from
  `get_row_sequence`, so the framework's own empty row (`panel_framework/partials/table_empty.html`,
  `<c-panel-empty-state>` inside the empty row, with the table's `empty_message`, check how
  `DataTablePanel` words it) shows; or (b) return one note row (`kind="part"`/`course`, `note="No
  reference material in this course yet."`) as `outline_rows` does. (b) mirrors existing code and the
  footer count already ignores notes (`_outline_content_count` returns 0, `entry_count` returns ""). (a)
  uses the framework default. Spec should pick one; (b) is the pattern "Course content" already uses.

## 3. `PreviewContentAction` and the preview lookup

- `PreviewContentAction(PanelAction)` (`content_preview.py:360`): `action_name = "preview_content"`,
  `capability = None`, `renders_in_footer = False`, template
  `educator_interface/modal/content_preview.html`. `get_context_data(ctx)`:
  1. `HX-Request != "true"` -> `Http404` (so a plain GET/POST 404s; `handle_submit` always 404s).
  2. `course = ctx.instance`; `pk = uuid_or_404(ctx.request.GET.get("item"))`.
  3. `next(item for item in _all_collection_items(course.collection_items()) if item.pk == pk)`; no match
     -> 404; match whose `child` is a `CoursePart` -> 404.
  4. context `collection_item`, `child`; if `Form`, `_form_preview_context(form, page_pk)` (sets
     `show_answer_key`, `read_only`); a `page` param on a non-form -> 404.
- Isolation contract (docstring plus tests): the target is found only among the authorised course's own
  collection items, so an id from another course, another site, a part row, or a made-up/malformed id is a
  404. Tests: `test_a_preview_of_another_courses_item_is_a_404`, `..._of_an_item_on_another_site_...`,
  `..._of_a_part_row_...`, `..._missing_or_malformed_item_...` in
  `tests/panels/course/test_content_preview.py`.
- Hard constraint on reference: reference topics are not in `Course.items`, so they 404 today. The lookup
  must also walk the course's own reference parts: `course.reference_parts` -> `row.course_part.
  collection_items()` (and `_all_collection_items` over them, to keep the same recursion). Because it
  starts from `course.reference_parts`, "a part shared by several courses is reachable only through a
  course that lists it" and "a collection item from another course stays a 404" hold by construction,
  as long as the lookup never queries `ContentCollectionItem.objects` by pk directly. Note
  `collection_items()` is memoised per `CoursePart` instance; `course.reference_parts.select_related(
  "course_part")` returns fresh part instances per query, so each request pays one query per part for its
  items (the `prefetch_related("child")` inside is one more per content type). The existing query-count
  test (`test_course_content_query_count_stays_bounded_as_children_grow`, line 324) shows how to bound
  this; the reference equivalent should bound per-part, not per-topic, queries.
- Gate: `_preview_available(request, course)` (line 188) =
  `is_course_available_to_organisation(course, request.organisation)`
  (`learner_management/queries.py:334`), false for a course the organisation lists only through a
  registration. `CourseContentPanel.preview_available` (cached_property) feeds `outline` (returns `[]`
  when withheld), the template (withheld note) and `get_actions()` (returns `[]`, which is what makes the
  preview URLs 404: actions resolve only from the panel's own `get_actions()`). Tests:
  `test_the_content_panel_shows_its_outline_only_for_an_available_course` and
  `test_the_preview_actions_answer_only_for_an_available_course` (lines 1149-1193, parametrised on
  `PREVIEW_AVAILABLE` over `course_per_reach_row` in `tests/helpers.py:108`), and
  `test_a_form_page_of_a_course_held_only_through_a_registration_cannot_be_previewed`;
  `tests/invariants/test_course_shares.py:158` (`test_revoking_a_share_makes_the_content_previews_answer_404`,
  parametrised on `["preview_content", "preview_course_details"]`) and `test_organisation_isolation.py`.
- A subtle consequence of sharing one action class between two panels: if `PreviewContentAction` is
  simply widened to walk reference parts, then the *Course content* panel's URL
  (`__panels/content/__actions/preview_content?item=<reference item>`) also resolves a reference topic
  (200), while no row there links to it. It is gated identically (same course, same availability), so it
  is not a leak, but the spec should say whether that is acceptable or whether the action takes a
  constructor argument so each panel's action finds only its own section (see option 3 below).

## 4. Sharing the `preview_available` gate and the outline table

Goal: withholding cannot drift. Constraints: CLAUDE.md "Don't create abstract base classes unless
asked" and "Avoid repeating code". Options, concrete:

1. **Subclass the concrete `CourseContentPanel`.** `class CourseReferencePanel(CourseContentPanel)`:
   inherits `data_table`/`preview_available`/`get_context_data`/`get_actions`; overrides `title =
   "Reference"`, `table_key = "reference"`, `outline` (calls the new `reference_rows(course)` after the
   inherited availability check), `entry_count` noun, and `template_name` (the banner). Pros: the gate,
   the withheld note, the `get_actions()` -> `[]` withholding and the table class are literally the same
   code, so they cannot drift; smallest diff. Cons: `CourseContentPanel` is not abstract but a "Reference
   is-a Course content" relation is slightly off; `outline` is a `cached_property` that returns
   `outline_rows`, so the override has to restructure (a one-line hook method, `build_rows(course)`,
   avoids duplicating the withheld check); the Course details actions (`PreviewCourseDetailsAction`) are
   inherited unless `get_actions()` is overridden, and the Reference panel should offer only
   `PreviewContentAction`. Fits the code best if the small hook is accepted.
2. **Shared module-level functions, two small concrete panels.** Keep `_preview_available` as the only
   gate and add one function used by both panels' `get_actions()`/`outline`, e.g. a function returning
   `[]` when not available. Each panel stays a separate `DataTablePanel` with its own `table_key`,
   `title`, template and table class; both call `_preview_available(request, course)` (already the one
   gate function) and share `CourseOutlineTable` (or a two-line subclass for the noun). Pros: no
   inheritance between panels, matches how `_preview_available`, `_all_collection_items` and
   `outline_rows` are already module-level helpers. Cons: the gate's *use* (empty rows, no actions, withheld
   note) is repeated in each panel, so drift is still possible unless a test pins it: the existing
   parametrised `PREVIEW_AVAILABLE` tests should be extended to the Reference panel so both are checked
   against the same `course_per_reach_row` matrix. Fits the codebase's style (functions over classes) but
   relies on tests, not structure.
3. **One action class, parameterised, plus a shared panel mixin-free helper.** Make
   `PreviewContentAction` look in a section chosen at construction (`PreviewContentAction("path")` /
   `PreviewContentAction("reference")`), implemented as one shared item-lookup function
   `course_section_items(course, section)`; both panels' `get_actions()` return it. Pros: each panel's
   preview URL finds only its own section's items, the isolation contract stays "found among this
   section of the authorised course's items", and the lookup is single-sourced. Cons: more change to the
   action (adds an `__init__`), and `get_action(name)` resolution is by `action_name`, so two instances of
   one name on two panels are fine (resolved per panel) but `walk_interface` and the invariant tests walk
   both, which is exactly the coverage wanted.
- Recommendation for the spec to weigh: option 1 for the panel (or 2 if the preference is no inheritance
  between panels) combined with the lookup of option 3's single-sourced function. The decisive fact is
  that withholding is implemented in three places in one class today (`outline`, template,
  `get_actions`); whichever option is chosen, the Reference panel must get all three, and the template
  `course_content.html` already keys the withheld note off the `preview_available` context key, so a
  Reference template can extend or reuse it with only the banner block changed.
- Out-of-scope reminder from the idea: `outline_rows` empty note ("No content in this course yet.") and
  `Lessons 0` stay as they are (spec 4). Keep `reference_rows` a separate function so spec 4 changing
  `outline_rows`'s empty-note logic does not conflict. Nothing here blocks it: when the path is empty and
  reference parts exist, `outline_rows` still shows the note and the Reference panel still shows the parts.

## 5. Existing tests and the invariants a new panel must pass

Tests that cover these (mirrored under `freedom_ls/educator_interface/tests/panels/course/`):
- `test_content_preview.py` (about 1200 lines; the outline, numbering, group rows, empty states, counts,
  query-bound, Preview triggers, the whole 404/isolation family, form previews, the withheld
  `PREVIEW_AVAILABLE` tests). New Reference tests belong here (or a new mirrored file if a new module is
  created; `test_organisation/mirroring_exemptions.txt` exempts only `tests/invariants/`, so a new module
  under `panels/course/` needs its own mirror test file).
- `test_config.py`, `test_panels.py`, `test_data_tables.py` (same folder): course config, details panel,
  registration tables.
- `tests/helpers.py`: `_interface_url`, `_get_document`, `_content_action_url` (hard-codes
  `__panels/content`; a reference version needs a panel-name argument), `course_per_reach_row(organisation)`
  (rows incl. `"held"`, the registration-only course), `organisation_admin_viewer`.
- `tests/invariants/test_course_shares.py:158`, `test_organisation_isolation.py`,
  `test_panel_template_rules.py` (`WIDE_FRAGMENTS = {"content_preview.html", "course_details_preview.html"}`:
  only these may declare `data-modal-size="wide"`; the reference preview reuses `content_preview.html`,
  so no new template and no change), `test_answer_key_flag.py`.
- Playwright: `tests/playwright/test_course_preview_flow.py`, `test_touch_targets.py`,
  `test_section_smoke.py`.

Invariants a new panel / action must pass (all enumerate automatically, nothing to register):
- `tests/interface_walk.py:walk_interface` walks `CoursePanelStack.get_children()` and every
  `panel.get_actions()`, giving the new panel's path and `__actions/preview_content` to the permission/
  isolation/authorisation invariants (`test_config_authorisation.py`, `test_organisation_isolation.py`,
  `test_permission_matrix.py`'s "every capability reachable" check). The action has `capability = None`,
  as the existing preview actions do; the new panel's own actions list must obey the same.
- Panel-framework checks at class definition and under `manage.py check`: unique `table_key`
  (`_check_no_duplicate_table_keys`), sequence-table rules (`_check_sequence_table`), `noun`/
  `noun_singular` set. `test_system_checks.py::test_call_command_check_passes_under_the_project_urlconf`
  runs them.
- Template invariants (`panel_framework/tests/invariants/test_templates.py`,
  `test_panel_template_rules.py`): no hand-written tables, no hand-styled anchors, no `<c-callout>`
  (use `<c-panel-callout>`), no hand-written touch heights. A new Reference template that only extends
  `_data_table_base.html` and reuses the existing partials adds nothing to check.
- **`test_answer_key_flag.py`: `show_answer_key` may appear only in
  `educator_interface/panels/course/content_preview.py` (plus three form_engine input templates).** If
  the Reference panel code goes to a new module, `_form_preview_context` must stay in `content_preview.py`
  and the new module must not contain the string `show_answer_key`, or the invariant fails.
- `tests/test_check_test_mirroring.py` (mirroring rule) as above.

## 6. Conflicts with other specs

Files this work touches: `panels/course/content_preview.py` (the lookup, the part-row factoring, a new
panel/table class, or a new sibling module), `panels/course/instance_view.py` (one dict entry), a new or
extended template under `educator_interface/templates/educator_interface/panels/`, tests under
`tests/panels/course/` and `tests/helpers.py`, `claude_plugins/fls-dev/skills/educator-interface/SKILL.md`.

- In progress in this repo (`spec_dd/2. in progress/` of main and sibling worktrees): `educator-interface-refactor-6-cohort`,
  `faster-test-runs-5-full-suite-on-github-actions`, `faster-test-runs-6-prune-slow-tests`,
  `learner-interface-features-3-revision-questions`, `remove-unnecessary-admin-panel-functionality`,
  `sacaa-compliance-3-question-pools`, `sacaa-compliance-4-attempt-review`. A grep of their ideas for
  `panels/course`, `content_preview`, `course_outline`, `CourseContentPanel`, `PreviewContentAction`,
  `_all_collection_items` finds none. `educator-interface-refactor-5-learner` has landed
  (`spec_dd/3. done/2026-11-22_12:05_...`). No file collision found with in-progress work. Weak spot:
  `faster-test-runs-6-prune-slow-tests` may delete or merge tests, possibly in
  `test_content_preview.py` (not checked in detail); rebase risk only. `sacaa-compliance-3-question-pools`
  changes form models and `_form_preview_context`'s inputs (question pools) not the outline; low risk.
- In `spec_dd/1. next/`: `sacaa-compliance-content-versions-and-access-4-question-access` changes
  `PreviewContentAction` ("Without the permission the action is not offered and a direct request is
  refused"). **This is the one real collision on the action.** If the Reference panel uses
  `PreviewContentAction` (or a subclass), it inherits that permission gate, which is right (a reference
  topic holds no answer key; the gate would be redundant but harmless). If instead the spec writes a
  separate action class for reference, that spec's gate would not cover it. Also whichever lands second
  rebases the same class.
- `reference-material-content-2-learner-reference` (parallel, ready): works in `learner_interface`
  (player chrome, `course_detail`) and reads `CourseReferencePart`; it touches no educator file. Possible
  shared helper: both specs need "the course's reference parts in order, with their topics". Spec 2 puts
  the query in the learner views; the educator side can stay independent (`course.reference_parts` with
  `select_related("course_part")`), so no ordering dependency. If either wants a shared
  `Course` method, add it in `content_engine/models/courses.py` once; flag it to avoid two helpers.
- `reference-material-content-4-library-courses` (blocked on 2 and 3): touches `outline_rows`'s empty note
  ("No content in this course yet."), `CourseDetailsPanel`'s "Lessons", and the learner/cohort progress
  panels. It needs this spec's Reference panel to exist so the library course's course page still has
  content. Keep `outline_rows` untouched by this spec to avoid a conflict; only the `PreviewContentAction`
  lookup and the new panel are shared surface.
- `educator-interface-refactor-6-cohort` (in progress) and `-7-cleanup` (next): do not move `panels/course/`
  (confirmed by prior research; templates stay flat under `educator_interface/templates/educator_interface/
  {panels,partials,modal}/`). `-7` trims flat modules (`views.py`, `urls.py`, `actions.py`); nothing here
  adds to them. `-7` also edits `SKILL.md:41` (the `filters.py` mention), a one-line merge risk on the same
  skill file.
- `docs/product/educator-interface.md` (lines 12 and ~117-119) describes the course page "outline of its
  content" and a topic preview with a screenshot (`screenshots/educator_course_content_preview.png`); the
  document step will want a line on the Reference section there.
- `.claude/agent-memory/sdd-qa-data-helper/reference_course_content_preview_command.md` and the
  `qa_helpers` commands `qa_create_course_content_preview.py` /
  `qa_create_course_structure_variants.py` build QA courses with outline content; QA for reference needs a
  course with `CourseReferencePart` rows (the demo course above, or the factory).

## 7. What the two skills constrain

`claude_plugins/fls-dev/skills/educator-interface/SKILL.md`:
- "Course outline and content previews": the course page lists the outline "as the panel framework's
  ordered-list data table, with a 'Preview' button on every row"; the details are the first row; a part (and
  a multi-page form) is a group row with children; the chip reads "Topic", "Form", "Form page" or "Course
  details"; previewed content sits in `max-w-reading mx-auto`. The Reference panel's rows satisfy this
  as-is. The "Preview button on every row" statement is already loose (part rows have none).
- Nothing about reference material yet: the section and the "Visual checklist" (the line "The course outline
  has the course details as its first row and a multi-page form expanded into one row per page") need a
  Reference line (rows numbered within their own section, no details row, no deadline/progress columns,
  separate footer count, empty state, withheld note shared). Skill edits live in `claude_plugins/fls-dev`
  only; generic plugins stay untouched.
- The Placement table (control beside the thing it changes) needs nothing: Preview triggers sit on each
  topic row.

`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`:
- "Each panel does one job ... A panel's title is the only heading for its job": rules out a Reference
  heading inside the Course content panel; a second panel titled "Reference" is the shape. A "Reference"
  panel and a "Course content" panel must not nest headings.
- Tables: "A numbered list with an action on each entry (the course outline) is a data table inside
  `.panel-data-table`", "A group row carries the row-detail chevron ... children are the indented rows
  under it, open by default. An empty group shows its note as a child row." `CourseOutlineTable` "is the
  worked example, with `compact = True`." Reference reuses it.
- "Child rows ... cannot be combined with `row_detail_template_name`, and a table with child rows cannot
  have bulk actions." "A sequence-backed table ... pages and shows its empty state, nothing more: no
  `search_fields`, no filters, no sortable column, no export columns ... `noun` and `noun_singular` must be
  set." The table footer states the entry count at the left on a single-page table, from `entry_count`; the
  Reference panel must set its own noun.
- "An empty table shows `<c-panel-empty-state>` inside the data table's empty row, which carries
  `hover:bg-transparent`": the framework's own empty state is available if the spec picks option (a) for the
  empty case.
- "A preview opens in `#app-modal` at the wide size, titled '<title> (Preview)' with its type chip. The
  title says it is a preview, so no callout does." The reference preview reuses `content_preview.html`, so it
  already conforms.
- Buttons: a table row's "Preview" is `size="small" variant="secondary"` in `<c-data-table-actions>`
  (the existing `course_outline_actions.html` does it), two buttons in one row each name their object
  (aria-label "Preview <title>"). Two panels on one page repeat the label "Preview <title>" only if a topic
  is listed in both the learning path and a reference part (allowed by the roadmap assumption), so
  accessible names would duplicate across panels; the title text is identical but the panels have their own
  headings. Worth one sentence in the spec, not a code change.
- Visual checklist and invariants (listed in section 5) apply; QA must also run
  `educator_interface/tests/playwright/test_touch_targets.py` after the panel template changes.

## 8. Open items the spec must decide (facts, not decisions)

1. Panel shape: subclass of `CourseContentPanel` vs two separate panels sharing module-level helpers vs a
   parameterised `PreviewContentAction` (section 4).
2. Whether `PreviewContentAction`, once widened, answers a reference id on the Course content panel's own
   URL (section 3, last bullet).
3. Empty-state mechanism for no reference parts: framework empty row vs a note row (section 2).
4. Footer wording: `ReferenceOutlineTable.noun` / `noun_singular` text.
5. Whether the Reference panel has an in-development banner (recommended no) and whether its withheld note
   reuses `data-testid="preview-withheld"`.
6. How a reference part holding a (DB-possible, validator-banned) `Form` or nested part behaves: the
   reused `_outline_item_rows` handles it (a Form row, a nested group) and the preview handles forms, so no
   special case is needed; just state it.
7. Query cost: reference rows cost one items query (plus the generic `child` prefetch) per reference part,
   as `Course.collection_items()` does for the path; decide the query-count bound for a new test.

status: ok
