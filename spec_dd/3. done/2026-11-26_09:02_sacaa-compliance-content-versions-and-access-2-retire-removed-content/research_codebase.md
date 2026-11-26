# Research: codebase seams for retiring removed content

Spec dir: `spec_dd/2. in progress/sacaa-compliance-content-versions-and-access-2-retire-removed-content`.
Read first: `idea.md`, `answers.md`. All paths relative to the worktree root. Retired state is the
nullable `retired_at` timestamp (answers.md). Terms follow the domain glossary: **retired**
(content sense), **deactivated/inactive** (an `is_active` flip), **removed** (deleted row).

## 0. Headline findings

1. The `content_save` pipeline already has every id it needs in hand at write time, but discards
   some (FormContent, Files). The retire pass belongs at the end of `_write_sources`, after the
   `for source in sources` loop and before the `ContentSave` row is created (all inside the
   existing `@transaction.atomic`).
2. Learner reads funnel through a few choke points: `Course.collection_items()` /
   `CoursePart.collection_items()` (outline, `children()`, `viewable_*`), `FormPage.children()`
   plus `form.pages.all()` / `question.options.all()` (form tree), and the course-level
   querysets (`get_all_courses`, `Course.objects` in `learner_interface/views.py`,
   `filter_visible`). The same choke points feed educator and report code that must keep seeing
   retired rows, so a blanket default-manager filter is wrong (section 6).
3. The pinned-paper rule ("attempt pins at start") collides with `served_path()`, which rebuilds
   a paper from live `page.children()` and `child.options.all()`. If the retired filter sits in
   `FormPage.children()` or on the default manager, a retired question inside a pinned paper
   silently drops out and is reported as `has_missing_served_items` (section 3).
4. `save_with_uuid` uses `model_class.objects.update_or_create(id=..., site=site)`. A default
   manager that hides retired rows would make un-retire an `IntegrityError` (create of an
   existing pk). Section 1.
5. Course completion has one choke point (`completable_items` -> `viewable_collection_items`),
   but `CourseProgress.progress_percentage` is stored, and `completed_time` is stamped by a view.
   A retire does not fire any recalculation today. The existing `part_placement_removed` signal
   and `recalculate_course_progress_on_placement_removal` are the precedent to reuse (section 4).

## 1. The `content_save` pipeline

File: `freedom_ls/content_engine/management/commands/content_save.py` (2104 lines).
`common.py` beside it is empty.

### 1.1 Where upserts happen

- `save_with_uuid(model_class, item, site, base_path, ...)` (line ~293): the generic upsert. With
  a uuid it runs `model_class.objects.update_or_create(id=uuid.UUID(item.uuid), site=site,
  defaults=fields)`; without one it `create`s and (if `update_file`) writes the uuid back to the
  file via `update_file_with_uuid`. `fields` come from `item.model_dump(exclude_none=True)`, so
  a `retired_at=None` default must be passed explicitly (an `extra_fields` kwarg, as
  `save_form_page` passes `condition_option` even when None) or put in `defaults` inside
  `save_with_uuid` itself. That single spot clears `retired_at` for every model that goes
  through it, which is the un-retire half of the spec for free: Topic, Activity, Article,
  Course, CoursePart, Form, FormPage, FormContent, FormQuestion, QuestionOption and
  CourseCategory all call `save_with_uuid`. Note `model_field_names` validation
  (`invalid_fields`) is against the model, so a new field is safe as long as it is not in the
  pydantic schema.
- Wrappers: `save_topic`, `save_activity`, `save_article` (also `_refuse_article_slug_collisions`),
  `save_course_categories` (loops `save_with_uuid` per entry, `file_path=relative_path`),
  `save_course`, `save_course_part`, `save_form`, `save_form_page`, `save_form_content`,
  `save_form_question` (options saved inside via `save_with_uuid(QuestionOption, ...)`, returned
  as `saved_options`).
- `File` is the exception: `save_file_to_db(file_path, site, base_path, cache)` uses
  `File.objects.get_or_create(site=site, file_path=relative_path, defaults=...)` and, for an
  existing row, mutates columns then `file_obj.file.save(..., save=True)`. It has no uuid
  (`freedom_ls/content_engine/models/files.py`, unique `(site, file_path)`). To un-retire a File,
  set `retired_at=None` in the `not created` branch (and persist it in the same `file.save`).
  It returns only an `ImageEncodeDecision`, not the `File`; the retire pass needs the file paths
  (`relative_path`) too, so `_write_source`'s loop over `source.all_files` must also collect
  `relative_path` values (`str(file_path.relative_to(source.path))`).
- `File.objects` is used in articles (`articles.py` `with_image_files`, `image_file`) and
  `content_tags.py` (`get_file_by_path`, lines ~153-158) for markdown embeds. A retired File is
  still referenced by existing markdown until the markdown changes; decide whether a retired File
  stops resolving in learner pages (the idea's list does not name File reads). The
  `audio_file` view (`content_engine/views.py`) serves any `File` by pk "regardless of
  publication state", so it is another learner-facing read of File.

### 1.2 Where "seen" ids can be recorded

`_write_source(source, site)` (line ~1282), called once per source path from `_write_sources`.
Saved instances exist at these points:

| Model | Variable in `_write_source` | Captured today |
| --- | --- | --- |
| CourseCategory | `categories` (from `save_course_categories`) | discarded after a log line |
| Topic / Activity | `topic`, `activity` | in `content_by_path` |
| Article | `article` | not in `content_by_path` ("never a collection child") |
| Course / CoursePart | `collection` | in `content_by_path` and `collections_data` |
| Form | `form` | in `content_by_path`, `forms_by_dir` |
| FormPage | `form_page` | local only |
| FormContent | return of `save_form_content` | discarded |
| FormQuestion / options | `question`, `saved_options` | question goes in `sections_by_question`; options only inside the per-question dict |
| File | not returned | only a status |

So the retire pass needs `_write_source` to return (or accumulate into a passed-in object)
`dict[type[Model], set[UUID]]` of seen ids plus a `set[str]` of seen file paths. `_write_source`
currently returns `tuple[list[ImageEncodeStatus], list[str]]` and `_write_sources` aggregates
`removal_lines`; the same pattern carries the retire counts out for printing after the
transaction. Ids are always real after save (a uuid-less item gets a generated pk under
`--generate-uuids`; without it the run is refused earlier by `_refuse_missing_uuids`), so
"present in the run" can be the saved instance's pk rather than the file's uuid string.

`_write_sources` (line ~1659, `@transaction.atomic`) order today: parse all sources ->
placement validators -> `_refuse_missing_uuids` (when `generate_uuids=False`) ->
`_refuse_relative_path_collisions` -> `for source in sources: _write_source` -> create
`ContentSave` + `ContentSaveSource`. Spec 1 made it one atomic call over several paths; the retire
pass fits after the loop, so it sees the union of all paths and rolls back with everything else
(a later failure retires nothing, as the idea requires).

### 1.3 Retire pass mechanics

- Retire = `Model._base_manager.filter(site=site, retired_at__isnull=True).exclude(pk__in=seen)
  .update(retired_at=now)`; un-retire is the upsert writing `retired_at=None`. One statement per
  model: 12 models, so about 12 `update()` calls. Use `_base_manager` with an explicit `site`
  (the loader runs with no request; the file already does this for `Organisation`, `CourseCategory`
  and slug checks).
- Scope hazard: "file-sourced" rows only. Courses/Topics etc. created by hand in the admin or by
  QA helpers (`freedom_ls/qa_helpers/management/commands/qa_create_*`) and by test factories have
  no source file. The idea says "any file-sourced row". `BaseContent.file_path` is
  `CharField(max_length=500)` with no default and not blank, so every row has one, but QA
  helpers write placeholder paths (e.g. `qa_create_served_paper_scenario` does
  `CourseCategory.objects.filter(pk=category.pk, file_path="").update(...)`). A run against a
  dev database would retire all QA fixtures. The spec must say whether rows with
  `file_path=""` (or not under any given path) are exempt.
- `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption` are children of a `Form`. Retiring a
  `Form` leaves the children un-retired unless the pass also retires them (they are not seen
  either, since their files are gone, so they retire on their own via the same rule). A question
  that still exists in a file but whose parent page was deleted is the odd case: the file is
  still in the run, so it is seen and its page is seen.
- Slug and path uniqueness hold for retired rows: `unique_<model>_slug_per_site` constraints
  (`Course`, `CoursePart`, `Topic`, `Activity`, `Form`, `Article`, `CourseCategory`) and
  `unique_file_path_per_site`. Retired rows keep their slug, so a new item whose title slugifies
  to a retired row's slug gets `-2` via `get_unique_slug` (uses `_base_manager`, so it already
  counts retired rows). For `Article` and `CourseCategory` the slug is authored and never
  suffixed: `_refuse_article_slug_collisions` and `_refuse_category_slug_collisions` (both
  `_base_manager`) will refuse a new item reusing a retired row's slug and name the owning uuid.
  That is correct but the error text should say the owner is retired.
- Reference/relations rewritten by the run (existing, no change): `CoursePartChildDueDate`
  deleted for loaded courses (`kept`), `CourseReferencePart` deleted when not listed
  (`sync_reference_parts`), `Course.categories`/`organisations`/`shared_with` `.set()`,
  `FormQuestionTopic`/`FormQuestionCoursePart` replaced
  (`replace_question_sections`, `_sync_section_rows`). A retired Topic/CoursePart keeps its
  `FormQuestionTopic` rows because nothing in the run touches rows of questions not in the
  run. Per-question sections of a retired question are likewise left.
- `ContentCollectionItem` rows: never deleted by the run (`moved_children.py` docstring, section
  3 of the earlier research file). `moved_children._left_behind` iterates
  `course.viewable_collection_items()`, so if retired children are filtered in that accessor a
  retired child's left-behind row is invisible to move detection. A retired child is by
  definition absent from `written`, so it cannot be the target of a move; this is harmless but
  worth a test.
- The idea's recommendation for a drawing page ("fail the save with a validation error naming the
  page when fewer than N items remain") must be evaluated in the same pass, after the retire set
  is known and before commit. It needs the page's draw `N`, which is not in the code yet
  (`sacaa-compliance-3-question-pools` is in progress, no `draw` field anywhere in
  `freedom_ls/form_engine`). Either this spec states the rule and spec 3 builds the check, or
  the check is a hook this spec leaves empty (idea says "that spec builds it").

### 1.4 What spec 1 changed (done spec `sacaa-compliance-content-versions-and-access-1-content-save-safety`)

Per `spec_dd/3. done/2026-11-22_10:30_.../upgrade_notes.md` and the code:

- `content_save` takes several source paths (`paths: nargs=-1`), refuses a non-clean git tree
  (`check_committed`, `check_source_paths`, `check_has_content`), refuses missing uuids unless
  `--generate-uuids` (`_refuse_missing_uuids`, `missing_uuids`), refuses duplicate relative paths
  across sources (`_refuse_relative_path_collisions`), and records `ContentSave` and
  `ContentSaveSource` (`freedom_ls/content_engine/models/content_saves.py`, migration
  `content_engine/migrations/0015_...`). The migration number to follow is therefore 0016 or
  later in `content_engine`; check the directory before naming.
- `save_content_to_db(paths, site_name, *, generate_uuids=True, source_commits=None)` is also
  called directly by fixtures and downstream projects and defaults to no git check. The retire
  pass will run for every such caller too, so tests and QA fixtures that call it with a partial
  content set will start retiring rows. Search for callers before deciding whether the retire
  pass is opt-out (a keyword like `retire_missing=True`).
- Output pattern to copy: `removal_lines` collected in `_write_source`, returned through
  `_write_sources`, echoed in `save_content_to_db` after the transaction ends, so a rolled-back
  run printed nothing. The retired/un-retired counts go the same way (answers.md: counts in the
  output, no per-row audit entry).
- `_write_source` no longer calls `validate`; per-source validation is in `command()` and
  `_write_sources` placement validators. `content_validate.py` is a separate command; it reads
  files only and needs no change unless it should preview what would retire (not asked).
- Single source: spec 1 already treats the call as the whole source, so the retire rule "not in
  any path of this call" needs no new input.

## 2. Models to change (field and managers)

Field: `retired_at = models.DateTimeField(null=True, blank=True, db_index=True?)`.

- Abstract bases: `freedom_ls/content_base/models.py` `BaseContent(SiteAwareModel,
  TimestampedModel)` is the parent of `TitledContent`, `MarkdownContent`, and `FormQuestion`
  directly. Putting the field on `BaseContent` covers Course, CoursePart, Topic, Activity,
  Article, Form, FormPage, FormContent, FormQuestion, CourseCategory in one place. The two
  outside it are `QuestionOption(SiteAwareModel, TimestampedModel)`
  (`form_engine/models.py` line 299) and `File(SiteAwareModel, TimestampedModel)`
  (`content_engine/models/files.py`). `ContentCollectionItem` is a third model that has no
  retired state by decision. A small abstract mixin (like `TimestampedModel` in
  `site_aware_models/models.py`, "composed alongside whichever base a model already uses") would
  let `QuestionOption` and `File` share it. CLAUDE.md says "Don't create abstract base classes
  unless asked"; `BaseContent` and `TimestampedModel` already exist, so adding a field to
  `BaseContent` plus a mixin for the other two needs a spec decision.
- One migration per app: `content_engine` (Course, CoursePart, Topic, Activity, Article,
  CourseCategory, File) and `form_engine` (Form, FormPage, FormContent, FormQuestion,
  QuestionOption). Plain `AddField` with null default, no backfill.
- Managers in play:
  - `SiteAwareManager` (`freedom_ls/site_aware_models/models.py`) is the default `objects` on
    every `SiteAwareModelBase`. It filters by the request's site only.
  - `ArticleManager(SiteAwareManager)` with `ArticleQuerySet.published()`
    (`content_engine/models/articles.py`). This is the one existing precedent for a
    visibility filter on a content model: `blog/views.py` calls `Article.objects.published()`
    (lines 9, 28). A `not_retired()` method can follow this pattern, one queryset class and one
    manager per model that needs a shared filter.
  - `Course` has no custom manager. Django reverse relations use the default manager's class
    (`_default_manager`), so `form.pages`, `page.questions`, `page.text_items`,
    `question.options`, `course.items` are all built from `SiteAwareManager`. A filter placed
    in `SiteAwareManager`/`BaseContent` default manager would apply to all of these *and* to
    `update_or_create` in `save_with_uuid`, to `danger_content_delete` (`objects.all()`), to the
    admin (`ModelAdmin.get_queryset` uses `_default_manager`), to reports, and to educator
    pages. Not viable as a blanket filter.
  - Forward FKs (`answer.question`, `progress.form`, `topic_progress.topic`) use
    `_base_manager`, which is not filtered, so learner audit data resolves its content fine.
    Prefetches `prefetch_related("options")` use the reverse manager's default queryset, so
    they follow the default manager.
  - Consequence for the design: add an explicit, named filter (a queryset method such as
    `.not_retired()` on a per-model queryset, or a Q expression helper) and apply it at the
    learner-facing choke points. Educator, admin, report and audit reads stay on the unfiltered
    manager. A shared place for it: `freedom_ls/content_base/` (next to `admin_filters.py`,
    which holds `ContentTagListFilter`, a precedent for a shared content admin filter).

## 3. Learner-facing reads that must exclude retired rows

### 3.1 Course catalogue, list, dashboard, detail

- `learner_interface/utils.py` `get_all_courses()` (line 977): `Course.objects.prefetch_related(
  "organisations")`. The base for `all_courses` view (`views.py` line 801), `_discovery_courses`
  (line 387), and the dashboard sections. Filtering retired here covers the catalogue and
  discovery sections in one edit.
- `get_course_registrations(user)` (utils.py line 406): `Course.objects.annotate(...)
  .filter(_is_registered=True)` is the learner's course list (dashboard in-progress, completed
  courses via `get_completed_courses`, `_annotate_registered_courses`). A retired Course must
  leave it (idea) while the registration keeps `is_active`. Dashboard "learning history" /
  completed courses also read through here (`get_completed_courses` line 986); a completed
  course that later retires leaves the history. State the decision.
- Direct slug lookups in `learner_interface/views.py`, each `get_object_or_404(Course, slug=...)`:
  `course_detail` (880, a `Course.objects.select_related(...)`), `course_home` (1052),
  `initiate_course_access` (1083), `view_course_item` (1465), `form_start` (1922),
  `form_fill_page` (2063), `course_form_complete` (2162), `course_reference` (2394),
  `course_reference_topic` (2413), `course_finish` (2467), `form_submit_and_exit` (2568). Others
  outside the player: `course_applications/views.py` (197, 673), `course_interest/views.py`
  (78, 111, 133). `raise_404_if_unavailable(user, course)` in
  `course_access/visibility.py` is the existing "single chokepoint" called by `course_detail`,
  `course_home`, `initiate_course_access`, and the apply/interest views. Adding
  `if course.retired_at: raise Http404` there is the smallest edit for the page-level gate, but
  `view_course_item` and the other player views call `_course_access_decision` (line 1160) instead
  and not `raise_404_if_unavailable`.
- Access backends: `course_access/backends.py`. `VisibilityEnforcingBackend._visibility_decision`
  (line 432) already returns `_closed_decision()` for hidden courses and wraps every inner
  backend; `filter_visible` (line 529) is the catalogue filter; `get_access`/`get_access_many`
  route through it. A retired course branch placed first in `_visibility_decision` (not exempted
  by registration, unlike HIDDEN, which exempts registered learners) closes the player for
  existing learners and removes `can_self_register`. In `filter_visible` add
  `.filter(retired_at__isnull=True)` (outside the registration exemption). The idea says retired
  "overrides visibility", consistent with putting it before the visibility checks. The wrapper
  is applied by the loader "so no backend can bypass" it, which is why it is the best seam;
  `DeadlineEnforcingBackend` wraps it (line 614).
- `learner_management/queries.py` `courses_visible_to` (564) and `registerable_courses` (591) are
  educator-side (organisation scoped), not learner reads; see section 5.
- JSON-LD in `all_courses` is built from the filtered list, so no separate work.

### 3.2 Registration creation for a retired course

Creation sites for registrations:

- `learner_management/learner_actions.py` `self_register` (348) -> `_ensure_registration`
  (~320-345, `LearnerCourseRegistration._base_manager.get_or_create`), guarded by
  `require_course_open_to(course, organisation)` (`learner_management/queries.py` 347).
- `learner_management/utils.py` `register_cohort_for_course` (189), guarded by the same
  `require_course_open_to`.
- `registration_rules/evaluation.py` `apply_rule_changes` (236): builds `LearnerCourseRegistration`
  directly, guarded by `is_course_open_to_organisation(rule.course, rule.organisation)` (line 242).
- Educator pickers: `registerable_courses(organisation)` (queries.py 591), `registerable_courses_for`
  (601), `registerable_courses_for_learner` (610), used by `educator_interface/forms.py` (165,
  182) and `panels/common/bulk_actions.py` (83, 95). The bulk actions and the add-registration
  forms read from these querysets.
- Also `course_applications/` (application flow creating registrations on approval; check its
  `receivers.py`) and `api/` registration endpoints if any; not read in full here.

`require_course_open_to` / `is_course_open_to_organisation` / `open_to_organisation_expression`
is the one existing service-function gate ("the service-function form of the refusal, for every
path that creates or reactivates a registration", docstring at line 347) and raises
`CourseNotOpenError(ValueError)` with `COURSE_NOT_OPEN_MESSAGE`. A retired check cannot just be
folded into `open_to_organisation_expression`, because that expression is also used for audience
and listing (`in_audience_expression`). A parallel `CourseRetiredError` raised by
`require_course_open_to`, plus `.filter(retired_at__isnull=True)` in `registerable_courses`, and
the rules path checking `rule.course.retired_at`, cover creation. Reactivating an existing
registration is also "creation or reactivation" per the docstring; the idea says registrations
"accept no new registrations", and keeps their `is_active` as is. Decide whether reactivating an
existing registration on a retired course is refused (recommend: yes, same path).
`Cohort`-granted `CourseProgress` fan-out (`ensure_course_progress_records_for_cohort_registration`)
is downstream of the registration and needs nothing.

### 3.3 Course outline, children, topic/activity/article pages

- `Course.collection_items()` (`content_engine/models/courses.py` line 482) and
  `CoursePart.collection_items()` (line 584): `list(self.items.prefetch_related("child"))`,
  memoised per instance. Everything else derives from them: `children()`, `children_flat()`,
  `collection_items_flat()`, `viewable_collection_items()`, `viewable_items()`,
  `lesson_count()`, `includes_assessments()`. The player addresses a course item by its 1-based
  index into `viewable_collection_items()` (`view_course_item(request, course_slug, index)`,
  `views.py` 1464-1474); `get_resume_index` (utils.py 415) also maps `last_accessed_item_id` to
  that index. Filtering retired children shifts every later index, so learner bookmarks and the
  `last_accessed_item_id` pointer need the existing "no longer viewable -> first item" fallback
  (documented in `get_resume_index`: "the recorded placement is no longer viewable (deleted,
  unpublished, or removed from the course)"). That fallback already exists, so shifting is
  tolerated, but the URL index of a given item changes.
- The `ContentCollectionItem.child` is a `GenericForeignKey` resolved by `prefetch_related("child")`;
  a retired child is a loaded object whose `retired_at` is set, so the filter is in Python on
  `item.child.retired_at` (not a queryset filter) unless the prefetch is replaced with typed
  `Prefetch` objects per content type. The idea's recommendation ("a collection item whose child is retired is skipped
  when outlines are read, the row gets no retired state") matches a Python-level skip in
  `collection_items()`.
- The retired CoursePart case: a part is a child of a course; a retired part hides its whole
  subtree. `collection_items_flat()` recurses into `item.child.collection_items()` and must skip a
  retired part and everything in it. A Topic that is retired inside a non-retired part is skipped
  by the same rule one level down.
- The educator must keep seeing retired items (`educator_interface/panels/course/content_preview.py`
  `outline_rows`, `_part_row`, `_all_collection_items`, `_course_list_items`, line 182-244, all
  use `course.collection_items()` / `part.collection_items()` directly, no `viewable_*`). Therefore
  `collection_items()` itself should not filter; the filter belongs in a learner-facing
  accessor (an `include_retired` keyword or a separate `learner_collection_items()`), with
  `viewable_collection_items()` filtering by default because ~all its callers are learner or
  completion code. Callers of `viewable_collection_items()` and `viewable_items()` outside
  learner views: `deadlines/admin.py` (295, 426), `deadlines/admin_views.py` (144),
  `deadlines/forms.py` (103), `deadlines/models.py` (69, 579), `deadlines/signals.py` (102),
  `reports/indexes.py` (258), `learner_progress/utils.py` (28), `content_engine/moved_children.py`
  (82), `learner_interface/utils.py` (268, 432, 564, 1102, 1127), `learner_interface/views.py`
  (1471, 1736, 2169). The deadlines admin/forms (staff) and `deadlines.models` validation
  (`elif collection_item not in course.viewable_collection_items()`) will start to treat retired
  items as non-existent; a deadline already set on a now-retired item is kept (row untouched) but
  the admin picker will no longer offer it. Reasonable; list it.
- Reference material: `course_reference_topics` (`learner_interface/utils.py` 1360) reads
  `course.reference_parts` -> `course_part__items` with `ContentCollectionItem.objects.
  prefetch_related("child")` directly, bypassing `viewable_*`; a retired CoursePart and a retired
  Topic need filtering here and in `course_reference`/`course_reference_topic`
  (views.py 2393, 2410), which also look the part up by slug. `educator_interface` reference
  panels read `_reference_parts` (content_preview.py 205).
- Single-topic pages: `Topic.preview_url()` -> `content_engine:topic_detail`, but
  `content_engine/urls.py` and `views.py` define only `audio_file`; there is no standalone topic
  page in `content_engine/views.py`. Topic/Activity/Form pages are served through
  `view_course_item` -> `view_topic`/`view_form` (views.py 1787, 1848) by placement. So "topic
  and activity pages" are covered by the outline filter.
- Articles: public blog, `blog/views.py` `Article.objects.published()` in `article_detail`
  (line 9, `get_object_or_404`) and the index (line 28). Add `not_retired()` to `ArticleQuerySet`
  and chain it where `.published()` is called; `Article.get_absolute_url`, sitemap/`seo` tests
  in `learner_interface/tests/` reference sitemap code (`learner_interface/checks.py`,
  `base/middleware.py`). `articles` embedded as cards in markdown: check
  `content_engine/templatetags/content_tags.py` for article cards (not read).
- Markdown content tags: `content_tags.py` lines ~205-217 resolve `Topic.objects.get(file_path=...)`
  and `Form.objects.get/filter(file_path=...)` for content links inside markdown, and
  `File.objects.get(file_path=...)` (153-158) for pictures and audio. A link to a retired Topic
  or Form from a surviving topic would still resolve. Decide whether the link tags treat retired
  as unresolved.

### 3.4 Forms, question serving, served paper, groups and draws

Relevant files: `form_engine/models.py` (`FormPage.children`, `FormQuestion`, `QuestionOption`,
`FormProgress`), `form_engine/conditions.py` (`SittingPath`, `compute_path`, `served_path`,
`frozen_path`, `full_path`, `sitting_path`, `current_path`, `FORM_TREE_LOOKUPS`,
`SERVED_TREE_LOOKUPS`), `form_engine/served_paper.py` (`build_served_paper`, `_served_children`,
`_served_options`, `shuffle_units`, `shuffle_with_locks`, `ensure_served_paper`),
`form_engine/queries.py` (`count_form_questions`, `page_questions`, `form_questions`,
`answer_groups`).

- **Pages and children**: `FormPage.children()` (models.py 133): `list(self.text_items.all()) +
  list(self.questions.all())` sorted by `order`. It is the one function from which the learner
  page flow, `compute_path`, `served_path`, `frozen_path`, `full_path`, the educator preview,
  scoring (`_quiz_questions`), `page_questions` and `build_served_paper` all read, and some of
  them need retired rows (below). Retired `FormContent`/`FormQuestion` must come out for *new*
  papers; not for pinned ones. Recommend a keyword (`children(include_retired=False)` is
  tempting but `FormPage.children()` is called with no args at ~12 sites, and prefetch
  lookups `FORM_TREE_LOOKUPS` hand it already-fetched managers). The natural split:
  - `build_served_paper` (new paper, quiz sittings) and `compute_path` (unserved sittings:
    surveys/CATEGORY_VALUE_SUM, which never get a `served_paper`, see `ensure_served_paper`
    returning early unless `form.strategy == FormStrategy.QUIZ`) read live children and must
    apply the filter first, before `shuffle_units` and before the draw.
  - `served_path` (pinned paper) must NOT filter: it maps ids from `served_paper["pages"][i]
    ["children"]` through `children_by_id` built from `page.children()`; a retired question
    missing from `children_by_id` is dropped and flagged `has_missing_served_items`. It needs
    the unfiltered children and options (`child.options.all()`, line 331, `live` dict).
  - `frozen_path` (completed sittings that recorded `asked`) and `full_path` (older completed
    sittings) rebuild a past attempt: no filter either, same reasoning as audit.
  - `current_path` calls `served_path` when `served_paper` exists, else `compute_path`.
- **Surveys and other strategies**: unscored forms and CATEGORY_VALUE_SUM have no served paper, so
  an in-progress survey attempt that loses a question mid-sitting is not pinned. The idea's
  "attempt pins at start" is written for papers; for these strategies `compute_path` over the
  filtered live tree is what gets served. State this: a retired question disappears from an
  in-progress survey sitting (it is still on any past `QuestionAnswer`). Alternatively extend
  `ensure_served_paper` to all strategies (not asked; "don't build functionality not requested").
- **Options**: `QuestionOption` retired: `question.options.all()` is read in
  `_served_options` (served_paper.py 57-65), `SittingPath.options_of` fallback (conditions.py
  186-190), `served_path` (331), `question_options` template tag (form_engine_tags.py 64-74),
  scoring `is_quiz_answer_correct(selected_option_ids, question.options.all())`
  (models.py 708, 788, 792) and CATEGORY_VALUE_SUM max value (563). The last group is the
  trap: scoring over live `options.all()` of a retired option would change `max`/`correct`
  results, but a retired option is not "removed from scoring" in a pinned attempt (the served
  option stays). New papers must exclude retired options in `_served_options`; scoring of
  pinned sittings must keep them. If `_served_options` filters and the paper records the option
  ids, `served_path` still resolves them from the unfiltered `live` dict, and
  `is_quiz_answer_correct` over unfiltered `question.options.all()` would count a retired
  correct option as "correct" for new attempts too. Correctness for new attempts needs the
  scorer to restrict to the options on the served paper, or to non-retired options for
  unpinned sittings. This is the highest-risk seam in the spec; call it out for the plan.
- **`max_score` / pass mark**: `FormProgress.compute_quiz_scores` -> `_quiz_questions` uses
  `served.questions()` when pinned (max_score unchanged by a later retirement, as the idea
  says) and `self.form.pages.all()` -> `page.children()` when not pinned (old sittings with no
  `served_paper`: those would lose retired questions from `max_score`, a score regression; an
  in-progress pre-served-paper sitting is rare but the migration state of data should be checked).
  `count_form_questions(form)` (queries.py 62) is `FormQuestion.objects.filter(form_page__form=
  form).count()`: check callers for learner-facing counts (e.g. "N questions" labels) and filter.
  `FormQuestion.question_number()` (models.py 275) iterates `form.pages.all()` /
  `page.questions.all()`: numbering counts retired questions unless filtered; used by what?
  (not traced; `queries.page_questions`/`SittingPath.question_positions` are the numbering used
  for the path).
- **Keep-together groups and draws**: `shuffle_units(children)` (served_paper.py 73) is a pure
  function over the children list: "a run of consecutive children sharing a group is one unit".
  If retired children are filtered out before `shuffle_units`, the rest of a group is already
  served "minus the retired question" (the idea's recommendation) with no extra code, except one
  edge: removing a retired member from the middle of a run can make two same-name runs adjacent
  that were not adjacent before (only possible if the retired member separated them, and the
  validator rejects a split group already: "a `group` value appears in one contiguous run per
  form"; the validator checks authored files, so removing a retired member that was *between*
  them is not possible because a group is one contiguous run). A group left with no members
  vanishes. A group left with 1 member remains a unit of 1. The draw (spec 3) is not built; its
  hook is "filter in `_served_children` before `shuffle_units`" for shuffle and the same call
  site for the draw. `answers.md` says "for a draw, remove the retired question (or its whole
  group, if it was in one) from the pool before the draw" which differs from the shuffle rule
  (retired member only). Note the two rules differ: shuffle serves the group minus the retired
  member; a draw drops the whole group so the group size stays equal ("every item on a drawing
  page carries the same number of questions", pools idea). Build the filter as one function
  `live_children(page)` plus a flag for the draw case so spec 3 can call it.
- **Conditions (`when`)**: a retired question that is the `condition_option.question` source for a
  gated page/content/question: `_condition_holds` uses `option.id in selected.get(option.question_id,
  frozenset())`, and `selected` only grows from children on the path. If the source question is
  retired and filtered from the live children, the gate can never open, silently dropping the
  gated items (the pools idea notes the same problem and bans `when` in drawing forms). The
  `FormPage`/`FormContent`/`FormQuestion.condition_option` FKs are RESTRICT. The retire pass
  needs a validation (error or warning) when a non-retired item gates on a retired option or on a
  retired question's option. Not in the idea; flag as a gap.
- **Answers to retired questions already on file**: `answer_groups` (queries.py 118) walks
  `form.pages.all()` and `page_questions`, and has an existing "Questions no longer on the form"
  group (`FINAL_GROUP_TITLE`) for answers with no page. With retired questions kept on the page
  (unfiltered) and a `retired` flag on the row, the same function can show them marked.
- **Retired Form**: `view_form`/`form_start`/`form_fill_page` reach the form via the placement,
  which is skipped, so the 404 for an in-progress attempt on a retired Form comes from
  `viewable_collection_items()` bounds checks (Http404 "No course item at this index"). The
  `Course.application_form` FK (SET_NULL) and `course_applications/views.py` (815, 841, 932
  `ensure_served_paper`) serve an application form outside any course: a retired application
  `Form` must be refused there (apply flow reads `course.application_form`), plus
  `FormProgress` on standalone forms. The idea's "Form retired -> in-progress attempt cannot
  be resumed" applies to those too.
- `form_engine/views.py` (answer file upload, ~40-70): `get_object_or_404(FormQuestion, ...)` by
  id inside a sitting; a retired question on a pinned paper must still accept answers, so no
  filter there.
- Reports/exports: `form_engine/exports.py` (line 57 `questions: list[tuple[Form, FormQuestion]]`)
  and `reports/indexes.py` `load_quiz_questions` (534-556, `FormQuestion.objects.filter(
  site_id=..., form_page__form_id__in=quiz_form_ids)` plus `prefetch_related("options")`) read all
  questions of a quiz form unfiltered. For the cohort report these should keep retired questions
  (answers were given to them) and mark them (answers.md: "the cohort report and attempt views
  mark answers given to retired questions").

## 4. Progress and completion

- `learner_progress/utils.py`: `completable_items(course)` = `course.viewable_collection_items()`
  filtered to `TOPIC`/`FORM`. `calculate_course_progress_percentage(course, completed_ids)`
  divides completed placements by `len(completable)`. Both the stored percentage and the finish
  page read it, so filtering `viewable_collection_items()` is enough to exclude retired
  children from totals and completion checks, matching the answer ("retired children drop out
  of progress totals and completion checks ... recorded progress is kept but does not count").
- `learner_interface/utils.py` `outstanding_items(course_progress, course)` (247) reads
  `course.viewable_collection_items()` too, and `course_finish` (views.py 2464-2515) stamps
  `completed_time` only when `outstanding_items` is empty. A learner who has finished every
  non-retired item completes on their next visit to the finish page. A learner already holding
  `completed_time` keeps it (a retire never un-completes; the idea is silent, state it).
- A course with every child retired: `completable_items` is empty and
  `calculate_course_progress_percentage` returns 0, which would reset a finished learner's 100.
  `recalculate_course_progress_on_placement_removal` (`learner_progress/signals.py` 146) already
  guards this ("A course left with nothing to complete keeps its records as they are").
- The stored `CourseProgress.progress_percentage` (`learner_progress/models.py` line 143, indexed)
  is only recalculated on a completion or a placement removal. After `content_save` retires a
  topic the stored percentage is stale until the learner's next completion. Reuse the
  precedent: `part_placement_removed` signal (`content_engine/signals.py`, sent from
  `remove_part_placement` in `content_save.py` 968) and its receiver
  `recalculate_course_progress_on_placement_removal`, or call
  `recalculate_progress_percentage(record)` for every `CourseProgress` of every course whose
  tree changed (retired or un-retired) at the end of the run. The management command
  `recalculate_progress_percentages` (`learner_progress/management/commands/`) already does a
  full backfill. Receivers that react to a content signal must live in `learner_progress` (it
  depends on `content_engine`), as the existing one does.
- `reports/indexes.py` `build_course_catalogue` (238) builds the cohort report catalogue from
  `reg.course.viewable_items()`: filtering the accessor removes retired topics/forms from the
  completion denominators (consistent with the answer) but also from the columns, so the report
  would hide the retired item and its recorded progress/answers entirely, which conflicts with
  "educators see retired content marked, not hidden". The plan must choose: reports show retired
  items as marked columns outside the denominator, or leave them out and list them separately.
  `reports/gather.py` (`_completion_counts`, `_completed_items`, `_build_quiz_columns`,
  `build_wrong_answers_by_learner_quiz`) consumes that catalogue.
- Deadlines: `deadlines/models.py` (69, 579) and `deadlines/resolver.py` (211-224
  `ContentCollectionItem.objects.filter(...)`) resolve per-item deadlines; a retired item with a
  stored due date stays in the table. Resolver reads rows directly, so overdue/at-risk
  calculations could still count a retired item as overdue unless it checks retired. Flag.
- `TopicProgress`, `FormProgress`, `CourseFormAttempt` unchanged (kept for audit).

## 5. Educator interface, reports and Django admin

### 5.1 Educator interface (`freedom_ls/educator_interface/`)

No educator file mentions `FormQuestion` or `QuestionAnswer` directly; per-question attempt views
are the Django admin (`form_engine/admin.py` `FormProgressAdmin`, answers change form
`form_engine/templates/admin/form_engine/answers_change_form.html` and `_answers.html` via
`answer_groups`) and the report. The educator panels that list or open content:

- Course list: `panels/course/data_tables.py` `CourseDataTable` reads `courses_visible_to(user,
  organisation)` (`learner_management/queries.py` 564). It includes published available courses
  and any held by a visible cohort/learner registration, so a retired course remains listed
  (good). It needs a column or badge; there is an `is_active` badge module to copy:
  `panels/common/badges.py` (`active_status_badge`, `inactive_badge`, `learner_status_badge`,
  returning `panel_framework.views.StatusBadge("success"|"muted", label)` shown by
  `<c-panel-status-badge>`). A `retired_badge(retired_at)` fits there.
- Course page and outline: `panels/course/instance_view.py`, `panels/course/panels.py`,
  `content_preview.py` (`OutlineRow` dataclass at line 56 has `number, title, kind,
  preview_query, children, note, form_title`; a `retired: bool` field plus a template change is
  how a row gets the mark). `outline_rows`, `_part_row`, `_outline_item_rows`,
  `_form_page_rows` (uses `form.pages.all()`, so page rows would also need the flag),
  `_form_preview_context` (line ~444 `"show_answer_key": True`, builds from `full_path(form)`, so
  retired questions appear in the preview unmarked today), `reference_rows`.
- Learner/cohort pages that list registrations of a course show `registration.course` titles
  (`panels/learner/data_table_panels.py` 165 `Course.objects.filter(...)`; panels under
  `panels/cohort/` including `report_panels.py`, `report_download.py`, `quick_view.py`).
  Course-title cells that appear in lists need the badge. Also `panels/common/filters.py` line 29
  `courses_visible_to(...)` course filter choices (label could carry "(retired)",
  `Course.label_for(organisation)` exists at courses.py 439 and is the place for a retired suffix
  in pickers).
- Registration add forms: `educator_interface/forms.py` 165, 182, `panels/common/bulk_actions.py`
  83, 95 use `registerable_courses*`; retired excluded there (section 3.2).
- Cohort report: `educator_interface/reporting.py`, `panels/common/report.py`,
  `panels/cohort/report_panels.py`, `reports/` app (`indexes.py`, `gather.py`, `checks.py`).
  See section 4 for the catalogue; the report also has a `reports/checks.py` mentioning
  "retired" (unrelated, grep hit only).
- Tests that guard educator panels: `educator_interface/tests/invariants/` (permission matrix,
  org isolation, answer key flag, template rules). A new badge/column must satisfy
  `test_panel_template_rules.py` (not read).

### 5.2 Django admin

- `SiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py` line 25) is the shared base of
  every content admin: a `retired` list filter and column could be added once on a mixin there,
  or per admin. Content admins: `content_engine/admin.py` `TopicAdmin` (34, `list_display =
  ["title","subtitle","file_path"]`, `list_filter=(ContentTagListFilter,)`), `ArticleAdmin` (62),
  `ActivityAdmin` (103), `CourseCategoryAdmin` (131), `CourseAdmin` (209, `list_filter =
  ("visibility","organisations",ContentTagListFilter)`), `CoursePartAdmin` (288),
  `ContentCollectionItemAdmin` (338), `FileAdmin` (362), `FormQuestionWithSectionsAdmin` (387);
  `form_engine/admin.py` `QuestionOptionAdmin` (68) with `QuestionOptionInline` (58),
  `FormContentAdmin` (103), `FormQuestionAdmin` (134), `FormPageAdmin` (200), `FormAdmin` (241),
  plus inlines `FormContentInline` (80), `FormQuestionInline` (92), `FormPageInline` (189).
  `FormProgressAdmin` (320), `QuestionAnswerAdmin` (454, `list_filter = ("question__form_page__
  form","updated_at")`), `QuestionAnswerFileAdmin` (488).
- `content_base/admin_filters.py` `ContentTagListFilter(admin.SimpleListFilter)` is the pattern
  for a `RetiredListFilter`: lookups ("Retired", "Live"), `queryset()` on `retired_at`. Django's
  `DateFieldListFilter` on `retired_at` also works as a quick "retired" filter with
  `list_display` showing the timestamp.
- Admin `get_queryset` uses `_default_manager`, so no change is needed to see retired rows as
  long as the default manager is unfiltered, which is a further reason not to filter it.
- Spec 4 (`question-access`) removes admin question viewing; the admin work here for
  `FormQuestion`/`QuestionOption` is short-lived but the idea still asks for it.

## 6. Shared "not retired" filter: options and constraints

Option A (recommended by the findings): a per-model queryset method plus a Q-expression helper.
`ArticleQuerySet.published()`/`ArticleManager` is the in-repo pattern. For the Course queryset a
`.live()`/`.not_retired()` method on a new `CourseQuerySet`, and an `_is_not_retired` Q for
joins (`Q(course__retired_at__isnull=True)`). Apply explicitly at: `get_all_courses`,
`get_course_registrations`, `VisibilityEnforcingBackend.filter_visible`,
`registerable_courses`, `CourseCategory` filter in `learner_interface/views.py` line 635
(`CourseCategory.objects.filter(show_on_dashboard=True)`) and the course categories join in the
catalogue (a retired category "leaves the catalogue filters"; `Course.categories` M2M and
`dashboard_category` FK to a retired category: the course stays, the category does not show).
Option B: a default-manager filter on `SiteAwareManager`. Rejected above: it breaks
`update_or_create` un-retire, `danger_content_delete`, the admin, the reports and every educator
read, and silently changes reverse-relation prefetches the pinned-paper code relies on.
Option C: an `include_retired` parameter on `Course.collection_items()`/`children()` and
`FormPage.children()`. Needed in addition to A for the in-memory tree walkers, because those
are not querysets. Both memoised per instance (`_collection_items_cache`, `_children_cache`),
so the flag is part of the cache key.

## 7. Glossary

`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, section "Words with an existing
meaning" (table at line 238). Rows that matter:
- **is_active** (line 247): ends with "... and a list entry retired from the pickers (`JobTitle`,
  `Department`, `Location`)... The one exception is the list entries, which are **retired**."
  So "retired" is already the word for a hidden-not-deleted `is_active=False` list entry.
- **suspend** (253): "Retired." in a different sense (a retired word, "Pausing a learner's
  course is a `CoursePause`"). Another existing use of the word "retired" in the table, as a
  note on a retired term. The new row for the content sense must keep the three apart.
- **removed** (249): "A row that was actually deleted" - the content-save "removal lines" in
  `content_save.py` use "Removed part placement", a real delete; no conflict, but a retire
  count in the output must say "retired", not "removed".
- **withdraw**, **deactivate** (255): the idea's carve-out ("kept apart from deactivated and
  inactive") matches the glossary's `is_active` guidance.
- The spec also needs the domain-vocabulary source in the plugin (`claude_plugins/sdd/resources/
  domain_vocabulary.md`) read; not changed here. The glossary lives in the FLS overlay
  (`claude_plugins/fls-dev`), so editing it respects CLAUDE.md's rule that generic plugins stay
  project-free.

Correction to the idea: `CourseVisibility` has three values, `PUBLISHED`, `COMING_SOON` and
`HIDDEN` (`content_engine/models/courses.py` line 54-59); `ArticleVisibility` has `PUBLISHED`,
`HIDDEN`. The idea says "published, coming soon". The retired axis still overrides all of them,
and a hidden course already exempts registered learners, which retired must not.

## 8. Existing research read

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_content_save_pipeline.md`
  section 3 (what a run removes today) and section 5 ("retired" words): still accurate against
  the current code, including the `moved_children` left-behind behaviour. Its description of
  `content_save` as "one path" is out of date since spec 1.
- `.../sacaa-compliance-content-versions-and-access-3-question-versions/
  research_question_version_seams.md` section 7: "Retired mid-draw ... a sitting's draw is
  persisted at start (`served_paper`), so a question retired after the draw stays in that
  sitting's paper" (consistent with section 3.4 here; the seams file's implication 3 says
  "block from serving" = a retired flag honoured in `build_served_paper()` and
  `compute_path()`, which matches the choke points above), implication 10 ("apply the retire
  filter before shuffling and drawing; define behaviour for a retired member of a keep-together
  group; validate pool size after retirement"), and "Educator preview reads the full form; it
  should show retired questions marked or hide them (decision)" - answers.md settles it as shown
  and marked.
- Shuffle (`spec_dd/3. done/2026-11-21_11:09_sacaa-compliance-2-shuffle/1. spec.md`) is merged:
  `form_engine/served_paper.py` already holds `shuffle_units`, `shuffle_with_locks` and the
  per-scope RNG; `FormContent.group` and `FormQuestion.group` exist. The idea's
  "`sacaa-compliance-2-shuffle` reads the live question tree" is implemented by
  `build_served_paper`, which calls `prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)` and
  reads `form.pages.all()`/`page.children()`/`question.options.all()`: the three call sites to
  filter. Question pools (`spec_dd/2. in progress/sacaa-compliance-3-question-pools/idea.md`)
  is not built (no `draw` key in the code).

## 9. Conflicts and decisions the spec must make

1. Where the retired filter lives (explicit queryset/accessor filter, section 6) and the
   `include_retired` flag on the in-memory tree accessors, because educators need the same tree
   unfiltered.
2. Served paper vs live tree: filter only in `build_served_paper`, `compute_path` and the
   learner accessors; never in `served_path`, `frozen_path`, `full_path`, scoring of pinned
   sittings, `answer_groups`, exports and reports. Scoring `is_quiz_answer_correct` over
   `question.options.all()` for sittings with no pinned paper must also treat retired options
   (section 3.4).
3. Surveys and other non-QUIZ sittings have no served paper, so "attempts pin at start" does not
   hold for them.
4. `content_save` scope: rows with no source file (QA fixtures, hand-made rows), direct callers of
   `save_content_to_db` with partial content, and a `--dry` style safeguard are open (a run
   against the wrong path retires the entire site; there is no preview). The earlier research
   (`research_prior_art.md` in this spec dir, not read here) may cover safeguards.
5. Course progress after a retire: stored `progress_percentage` is stale; reuse
   `part_placement_removed`-style signal or a recalculation at the end of the run. Also whether a
   course finish stamps `completed_time` for a learner who has now only retired items left, and
   whether an already completed course stays completed.
6. Educator report: whether retired items remain as marked columns outside the denominator
   (`reports/indexes.py build_course_catalogue`, `load_quiz_questions`).
7. Items that depend on retired parents: gates (`condition_option` onto a retired question's
   option), `Course.application_form` pointing to a retired form, `Course.dashboard_category` and
   `categories` pointing to a retired category, markdown links/embeds to retired Topic/Form/File,
   `FormQuestionTopic`/`FormQuestionCoursePart` section rows, deadlines on a retired item.
8. Slug and path reuse: a retired row keeps its slug and file path; a new item with the same slug
   gets `-2` (derived slugs) or is refused (article and category slugs); a File at a retired
   path un-retires, since `(site, file_path)` is the key.
9. URL index shift: the player's `index` into `viewable_collection_items()` changes when a
   retired child is removed; `get_resume_index` already falls back to the first item.
10. New migration: `content_engine` after `0015_contentsave_contentsavesource`, and a
    `form_engine` migration; both `AddField`, nullable.
11. Docs: `docs/product/content-editing-workflow.md` and the `fls-content` plugin skills
    (`claude_plugins/fls-content/skills/content-types/...`, `commands/`) describe `content_save`;
    `claude_plugins/fls-dev/resources/markdown_content.md` too. Each needs a retire note, plus an
    upgrade-notes file with `requires_migrations: true` (format as in spec 1's
    `upgrade_notes.md`).

status: ok
