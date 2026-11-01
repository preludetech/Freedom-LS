# Research: codebase impact of per-placement due dates

Facts only, with file:line. Spec 1 is done at `spec_dd/3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue/` (the idea cites the old in-progress path).

## 1. Schema: `Child`, `children:`, `DueDateFields`

- `freedom_ls/content_engine/schema.py:185-193` `Child(BaseModel)`, `extra="forbid"`, fields `path: Path` (required) and `overrides: dict[str, Any] | None`. `overrides` is free-form; no key is validated or read.
- `Course.children` (`schema.py:365`) and `CoursePart.children` (`schema.py:508`) are `list[Child]`. There is **no string form**: a bare string entry fails pydantic (no pre-validator was found). Only the object form `- path: ...` exists, in both the app schema and the plugin's copy (`claude_plugins/fls-content/validate/schema.py:321-329`, `children` at `:647` and `:833`).
- `extra="forbid"` means `due_date:` on a `children:` entry fails today in both schemas. Both `Child` copies must change (the plugin keeps its own copy, including its own `DueDateFields` at `validate/schema.py:~180-225`).
- `freedom_ls/content_base/schema.py:70-117` `DueDateFields(BaseModel)`: `due_date` (must be exactly `date`, not datetime), `due_time` (must be a quoted `HH:MM` string), `due_days_after_registration` (`ge=0, strict`). `_one_kind_of_due_date` (after-validator) rejects date+days together and a time with neither; its messages use `getattr(self, "file_path", None)`, so on a `Child` (no `file_path`) the prefix would read `None:`. `DUE_DATE_FIELD_NAMES = frozenset(DueDateFields.model_fields)` (`:120`).
- `DueDateFields` is mixed into the topic/activity? schema at `content_engine/schema.py:105` (topic) and `form_engine/schema.py:43` (form). `Course` does **not** mix it in (course takes only `time_limit_days`, `schema.py:433`). Course and part schemas therefore carry no due fields of their own.

## 2. Loader: `content_save.py`

- `due_date_columns(schema)` (`:363-366`): `{name: getattr(schema, name, None) for name in DUE_DATE_FIELD_NAMES}`; writes None for each absent field, which is how removal works. `save_topic` excludes `DUE_DATE_FIELD_NAMES` from the Topic row (`:369-373`), so the dates exist only on collection item rows.
- `time_limit_days` clear: `save_course` passes `time_limit_days=item.time_limit_days` explicitly and excludes it from the dump (`:585-601`), so None overwrites.
- Collection item sync, `save_content_to_db` `:1056-1186`:
  - `children_list` is `list[tuple[Path, dict | None]]` of `(resolve_author_path(schema_item.file_path, child.path), child.overrides)` (`:1072-1075`). Auto-discovery (when no children) appends `(content_key(...), None)` (`:1101`, `:1142`).
  - `resolve_author_path` (`:487-489`) = `content_key(declaring_file.parent / author_path)`; `content_key` = `Path(...).resolve()` (`:477-484`). Paths are relative to the declaring file (`course.md` / `part.yaml`), not the part's directory in general; e.g. the test uses `../shared.md` from `part-a/part.yaml`.
  - Write (`:1157-1168`): `ContentCollectionItem.objects.update_or_create(site, collection_type, collection_id, child_type, child_id, defaults={"order", "overrides", **due_date_columns(schema_by_path.get(child_path))})`. Due columns come from the **child's schema** (`schema_by_path`), not from the `Child` entry; `overrides` comes from the entry and is written every load (None included).
  - The lookup key is `(site, collection, child)`, so the same child listed twice in one collection collapses to one row (second pass overwrites `order` and columns). Placing a child in two different parts yields two rows (test `_write_timed_course`, `test_content_save.py:2771-2802`).
  - Unknown child: `content_by_path.get(child_path)` falsy raises `ValueError("Collection '<title>' names a child at <path> that was not loaded")` (`:1176-1182`), inside the atomic load. Docs: `docs/product/content-editing-workflow.md:112`.
  - After the loop, signal `collection_items_synced.send(sender=ContentCollectionItem, site, created, written)` (`:1184-1185`); receiver `freedom_ls/deadlines/signals.py:20-67` moves override rows from a stale row to the new row for the same child in the same course.
  - Order of passes: `collections_data` is filled for COURSE_PART (`:965`) and COURSE before item sync (`:958`); parts are saved before the children loop, so both a course's and a part's schema are available when items are written. `schema_by_path` is available for any loaded file.

## 3. Model: `ContentCollectionItem` (`freedom_ls/content_engine/models/courses.py:557-599`)

- Fields: generic FK `collection` (Course or CoursePart: `collection_type`, `collection_id` UUID), generic FK `child` (`child_type`, `child_id`), `order`, `overrides` JSONField(null), `due_date`, `due_time`, `due_days_after_registration` (all nullable; added by migration `content_engine/migrations/0008_contentcollectionitem_due_date_and_more.py`). Indexes `cci_collection_idx`, `cci_child_idx`. No unique constraint on (collection, child).
- Hierarchy: Course -> rows (collection=course) whose child is a CoursePart or a leaf; CoursePart -> rows (collection=part). `Course.collection_items_flat` (`:455-465`) goes **one level only** (course rows, then each part's rows); a part inside a part is not flattened. `viewable_collection_items` (`:467-473`) drops rows whose child is a `CoursePart`.
- **Part item rows are shared**: the rows with `collection=part` belong to the part, not to any course. A part placed in two courses has one set of item rows, referenced by both courses' flat lists. The course->part row is a separate row (collection=course, child=part) per course. Progress and overrides key on the item row pk (`TopicProgress.collection_item`, `CohortDeadlineOverride.collection_item`), so progress on a shared part's topic is already shared across courses.
- Row pk is used as the item id throughout the resolver and admin; a per-placement value therefore cannot be keyed by row pk alone (two courses give the same pk, different values). Overrides themselves are still unambiguous because a cohort registration / course progress belongs to one course.

## 4. `freedom_ls/deadlines/`

- `resolver.py`:
  - `_defaults_by_course(course_ids)` (`:154-198`): query 1 top-level rows for the courses; query 2 part-level rows for the parts those rows place (`collection_id__in=courses_of_part`); query 3 `Course.time_limit_days`. Rows whose child is a part are skipped (`:186-187`). `placed_in` is `[row.collection_id]` for a course row, else `courses_of_part[row.collection_id]` (every course placing that part); the same value is credited to each (`:188-197`). `items` is `dict[row.pk, DeadlineValue | None]` per course.
  - Value built by `DeadlineValue.from_columns(due_date, due_time, due_days_after_registration)` (`:37-53`).
  - Layers (`_layers`, `:205-221`): LEARNER override, COHORT_REGISTRATION override, CONTENT. `resolve_deadline` takes the first layer with a value (`:103-113`). `DeadlineSource` has `CONTENT`, `COHORT_REGISTRATION`, `LEARNER` (`:24-27`) and labels in `admin.py:299-303`.
  - `course_deadlines_for` (`:228-277`): `_defaults_by_course` (3) + cohort overrides (1) + learner overrides (1) = 5 queries; `site_time_zone` is read once. Test budget: `django_assert_max_num_queries(5)` for 6 and 60 items, and for 3 records (`tests/test_resolver.py:399-425`; 6 queries at `:577-581`; policy 8 at `tests/test_policy.py:272`).
- Adding a per-placement layer with no per-item queries: the values would have to be read in bulk, e.g. a column/JSON on the course->part row already loaded in `top_rows` (no extra query), or one extra `filter(course__in=...)` query on a new table (+1 constant query, the test's budget of 5 would need an explicit raise). Inside the loop at `:188-197` the credited value is chosen per `(course_id, row.pk)`, which is where a placement value for that course would replace `value`.
- `queries.py:18-28` `content_default_for(row)` reads `item.due_*` of the single `row.collection_item`, or the course time limit; it has **no knowledge of which course** (the row's course is available as `row.course`, `models.py`). `layers_beneath`/`canonical_beneath` (`:31-70`) call it; admin "Content default" column (`admin.py:272-276`) and "Default changed" note (`:286-296`) use these. `replaced_value` is stamped at save time by `canonical_beneath(instance)` (`admin.py:141`). A placement value would need `content_default_for` to also take the course.
- `admin.py`: `DeadlineOverrideInline` fields/readonly (`:169-186`); item picker `formfield_for_foreignkey` offers `course.viewable_collection_items()` (`:243-249`); `effective_deadlines` (`:336-358`) uses `course_deadlines(record)` and `deadlines.items.get(item.pk)`. Cohort inline `parent_select_related=("cohort_registration__course",)` (`:308`), learner `("course_progress__course",)` (`:313`).
- `signals.py:20-67`: override carry-over on re-sync; considers a part placed in several courses via `_CoursesOfCollections.placing` (`:80-119`).
- Other readers of the item due columns: `qa_helpers/management/commands/qa_create_deadlines_seed.py:157`.
- Tests: `deadlines/tests/test_resolver.py`, `test_queries.py`, `test_admin.py` (many `item.due_*` setups, e.g. `:85`, `:141`, `:358`), `test_signals.py`, `tests/helpers.py`, `factories.py`; content_save due tests `content_engine/tests/management/commands/test_content_save.py:2762-2895` (shared topic in two parts at `:2771-2802`, removal clears columns at `:2828-2844`, form at `:2858-2893`); schema tests `content_base/tests/test_schema.py`, `form_engine/tests/test_schema.py:40`, `content_engine/tests/test_schema.py:610` (`_timed_course`). 25 `children`/`overrides` mentions in `test_content_save.py`.

## 5. Every reader/writer of `ContentCollectionItem.overrides`

- Writer: `content_save.py:1165` (`"overrides": overrides`, from `Child.overrides`), every load.
- Declared: `models/courses.py:579-583`; migration `content_engine/migrations/0001_initial.py:52`.
- Reader: `content_engine/admin.py:149-168` `ContentCollectionItemInline` lists `"overrides"` in `fields` (editable; the three due columns are `readonly_fields`).
- Schema: `Child.overrides` (`schema.py:191`), validator copy `validate/schema.py:327`.
- No other reader (no view, template, resolver, test asserting on its value was found in `freedom_ls`). The domain glossary (`.claude/skills/domain-glossary/SKILL.md:30`, `:71`) names it and says "Never `ContentCollectionItem.overrides`" for deadline overrides. No `demo_content` file sets it.

## 6. `claude_plugins/fls-content` docs and validator

- `skills/content-types/resources/course-files.md:31`: `time_limit_days` row, "A course takes no `due_date` or `due_time`; due dates for individual topics and forms go in those files (see `topic-files.md`, "Due dates")." `:32` `children` row ("Explicit ordered list of child paths; if omitted, auto-discovered alphabetically"); `:69-78` "Children ordering" shows only `- path:` entries; `:431` part table `children` row ("Explicit ordered child list; if omitted, auto-discovered").
- `topic-files.md:21-23` field rows; `:30-33` "Write these in the topic's own `content.md` frontmatter, not in the course's `children:` list."; example `:40-41`.
- `form-files.md:24-26` field rows; `:30` "`form.md`, not in the course's `children:` list."
- `file-layout.md:112,121-122` auto-discovery rules (`_`/`.` prefix skipped). `skills/conventions/SKILL.md:86` note on omitted `children:`.
- Validator: `claude_plugins/fls-content/validate/schema.py` (own `DueDateFields` ~`:180-225`, `Child` `:321-329`, `children` at `:647` and `:833`); tests `validate/tests/test_validator.py:1303-1362` (topic/form due fields, error messages). Plugin must stay generic per CLAUDE.md; `fls-content` is the FLS content-authoring plugin, so FLS schema names there are expected.

## 7. `demo_content/` and docs

- No `course.md` or `part.yaml` in the repo contains a `children:` key (grep over `**/course.md`, `**/part.yaml` found none; the only `children:` text in `demo_content` is prose in a widgets topic). Demo courses auto-discover.
- Due fields today are only in child files of `demo_content/functionality_demo_course_parts/`: `01. Getting Started/01. welcome/content.md` (`due_date: 2024-01-31`), `02. what-to-expect/content.md` (`due_days_after_registration: 7`), `02. Core Concepts/01. key-ideas/content.md` (`14` + `due_time: "17:00"`), `03. knowledge-check/form.md` (`21`), `03. Wrapping Up/02. feedback/form.md` (`30`).
- `docs/product/` has no description of content due dates; its only `children:` mention is `content-editing-workflow.md:112` (unresolved child fails the load).
- Spec 1 Decision 2 (`spec_dd/3. done/.../1. spec.md:46-48`): "Content defaults live on the child's own file, not on the `children:` list... A file placed twice carries the same default on both collection items."

## 8. Overlap with other specs

- `deadlines-2-consequence-policy` (in progress): spec reads the resolved deadline (`1. spec.md`, form close, access end at `:141`, `:268`); no mention of `children:` or the content layer's construction. Its tests/budgets (policy `max_num_queries(8)`) depend on `course_deadlines_for`.
- `design_learner-interface-deadlines`: no match for children/placement/resolver.
- Roadmap (`spec_dd/1. next/roadmap.md:537-538`): spec 8 "edits the content loader and the resolver's content layer, which 2 and 3 read but do not change." Assumption at `:577-578`: a deadline attaches to the placement (`ContentCollectionItem`), not the content row.

## 9. Surprises / conflicts

1. A part's item rows are shared by every course placing it, and `_defaults_by_course` keys by row pk per course. A per-course value for a part's item must be stored off those rows (on the course->part row, or a (course, item) table).
2. `children:` has no string form today; a part placement's "named items by path relative to the part" has no existing field on `Child` (extra is forbidden).
3. A path relative to the part: loader paths resolve relative to the declaring file's directory (`resolve_author_path`), and part children can point outside the part directory (`../shared.md`), so a "path relative to the part" may name an item whose resolved path is not under the part directory. Matching can be on the resolved `Path` of the part's own children.
4. The same part placed twice in one course would hit the `(collection, child)` `update_or_create` and collapse to one row. The same topic placed twice in one collection collapses likewise.
5. Nested parts (a part in a part) are not flattened by `collection_items_flat`, and the resolver (`part_type` check at `resolver.py:186`) assumes one level; a deeper placement would not be reached.
6. `content_default_for` and `layers_beneath` take only the override row, with no course argument; "Content default" and "Default has changed" cannot become placement-aware without it (the course is reachable from `row.course`).
7. `DueDateFields` error messages interpolate `file_path`, which a `Child` lacks (reads `None`).
8. The validator plugin has its own `Child` and `DueDateFields` copies that must be kept in step; `extra="forbid"` rejects any new key until both are changed.
9. `ContentCollectionItemInline` in the content admin lists the editable `overrides` JSON; the three due columns are read-only there.

status: ok
