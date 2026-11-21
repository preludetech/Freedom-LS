# R1: content loader, schema, call sites, docs, demo content

Facts and risks only, no plan. Paths are repo-relative. Vocabulary: collection item = a `ContentCollectionItem` row; child = the object it holds; placement = a child's row in a collection; part placement = a course's collection item whose child is a `CoursePart`.

## 1. How `content_save` discovers children

### Explicit `children:` OR auto-discovery, never both

`collection_children(collection)` in `freedom_ls/content_engine/validate.py` is the single rule, shared by the validator and the loader:

- If `collection.children` is non-empty, the listed entries are the children, in list order. Each is `(resolve_author_path(collection.file_path, entry.path), entry)`.
- Otherwise `auto_discovered_children(collection.file_path)` supplies the children, with entry `None`.
- A non-empty `children:` list turns auto-discovery off entirely. An omitted or empty list turns it on.
- `Course.children` and `CoursePart.children` in `schema.py` use `default_factory=list`. An explicit `children: []` is therefore the same as omitted, and auto-discovers.

`auto_discovered_children` is non-recursive. It lists the entries beside `course.md` or `part.yaml`, sorted by name, skipping anything starting with `_` or `.`:

- A `.md`, `.yaml` or `.yml` file becomes a child, except the collection file itself, `COURSE_CATEGORIES` and `ARTICLE` files.
- A subdirectory contributes one child from its direct files only. `FORM`, `COURSE` or `COURSE_PART` wins and is the directory's `course.md`, `form.md` or `part.yaml`. Otherwise it is the first `TOPIC` or `ACTIVITY` file.
- A subdirectory with no direct content file contributes nothing.
- Numbering matters only because the sort is by name. Nothing requires a number.

All files are loaded regardless of placement. `get_all_files` rglobs everything under the root except `_`/`.` names, README.md and CLAUDE.md. `save_content_to_db` saves every Topic, Activity, Course, CoursePart and Form it parses, whether or not a collection places it. Placement is a separate step.

### How the loader writes placements

In `content_save.py`, `save_content_to_db`:

1. `for collection, schema_item in collections_data` loops over courses and parts. For each child from `collection_children`, it runs `ContentCollectionItem.objects.update_or_create(site, collection_type, collection_id, child_type, child_id, defaults={order, due columns})`.
2. A child path that was not loaded raises `ValueError` and rolls back the atomic load.
3. A second pass reconciles `CoursePartChildDueDate` rows for nested `children:` on part placements. These are deleted when no longer named, but only for courses in this load.
4. `moved_children(site, written, loaded_collections)` and `carry_placement_due_dates` run, then `collection_items_synced` is sent.

**Collection items are never deleted by the loader.** The `moved_children.py` docstring says so: "A sync never removes the row a moved child left behind". A child dropped from `children:` keeps its collection item, still in `Course.items`. Only a move (same child, one left-behind row, same course) is detected, and then only to carry deadline overrides and part-placement dates. A dropped child leaves its old collection item in place.

### `moved_children.py`

- `_CoursesOfCollections.placing(row)` maps a written collection item to the courses it sits in. If the row's collection is a course, that is the course. If the collection is a part, it is every course with a collection item placing that part (a `ContentCollectionItem` query on `collection_type=Course, child_type=CoursePart, child_id=part`).
- A part that no course places returns `[]`. Collection items written into a reference-only part are never examined for moves.
- `_left_behind` reads `course.viewable_collection_items()`. This is the learning path only, so it would never see reference rows.
- `carry_placement_due_dates` queries `ContentCollectionItem._base_manager` for course-to-part placements. It is course-rooted.
- A move of a topic from a learning part into a reference part (or the reverse) is not detected. The deadline overrides on the stale collection item are not carried. Reference carries no deadlines, so this is probably harmless.

### The `../` placement

`demo_content/functionality_demo_course_parts_placement/course.md` has an explicit `children:` entry `path: ../functionality_demo_course_parts/02. Core Concepts/part.yaml`, with a nested `children:` list of per-placement due dates.

- Paths resolve relative to the declaring file via `resolve_author_path` and `content_key` (a `Path.resolve()`).
- `content_by_path` is keyed the same way, so a part outside the course directory works provided it is under the loaded root.
- The part is saved once. The collection item `course -> part` is per course. Part-to-topic collection items belong to the part and are shared by every course that places it.
- Nested paths in a part placement are relative to the part's own directory, not the course's.
- `validate()` handles a part outside the validated path through `_ParsedByPath`, which parses it from disk on demand.
- A part outside the content_save root fails: `Collection ... names a child at ... that was not loaded`.

### What a parallel `reference:` key would touch

Facts about the current code:

- `Course` in `content_engine/schema.py` has `extra="forbid"`. A `reference:` key currently fails validation as an unknown field. It must be declared on the schema.
- `save_course` calls `save_with_uuid(Course, ..., exclude_fields={"children","categories",...})`. `save_with_uuid` raises `ValueError` for any dumped field that is not a model field. `reference` would have to be added to that exclusion set.
- `Child` (and so `children:`) is `PlacementDueDate` plus a nested `children` list. It carries `due_date`, `due_time`, `due_days_after_registration`, `no_due_date` and `children`. A `reference:` entry typed as `Child` would accept due keys silently. Rejecting them needs either a narrower entry model or a validator.
- `collection_children` has no notion of a second list. The loader loop, `validate_children_lists` (named twice), `validate_due_date_placements`, `_nested_list_errors` and `moved_children` all key off `item.children`.
- The bundled offline validator `claude_plugins/fls-content/validate/schema.py` and `validate.py` is a hand-synced copy of `content_engine/schema.py` and `validate.py` ("re-sync via /update_claude_plugin_fls_content"). It has its own tests in `claude_plugins/fls-content/validate/tests/test_validator.py`. Every schema or validator change has to be mirrored there.
- The entry-point check list in `validate(path)` and the pre-save check list in `save_content_to_db` are two separate lists: `validate_children_lists`, `validate_due_date_placements`, `validate_question_sections`. A new reference validator has to be added to both. `save_content_to_db` repeats these checks because fixtures and downstream projects call it directly.
- `reference:` placement writing must reconcile (replace) rows. There is no precedent in this file for deleting collection items, but there is for replace semantics: `course.categories.set`, `organisations.set`, and the `CoursePartChildDueDate` delete-not-kept pass.

### Would a `reference/` directory inside a course directory be picked up as learning-path content?

- **With an explicit `children:` list:** no. Only listed paths are placed. The files are still loaded and saved as rows (parts, topics), but nothing places them in `Course.items`.
- **With `children:` omitted or empty (auto-discovery):** `reference/` is a subdirectory, so it is inspected. `auto_discovered_children` looks only at the directory's direct files. With the layout in the idea (`reference/1. regulations/part.yaml`), `reference/` itself has no direct content file, so it contributes nothing. It is ignored, but by accident of nesting, not by design.
- **If `reference/` held a direct `part.yaml`, `course.md`, `form.md`, `content.md` or other content file,** auto-discovery would adopt that file as a learning-path child. The idea's layout does not do this, and no code protects against it.
- **A library-only course** (empty learning path) is the sharpest case. An author who omits `children:` gets auto-discovery over the course directory. Any numbered part or topic they leave beside `course.md` becomes learning-path content. A truly empty learning path in a directory with only `reference/` works today only because `reference/` has no direct content file.
- `reference` is not a skipped name (only `_`/`.` prefixes are), so everything under it is loaded.
- The whole-tree load also means parts and topics under `reference/` get saved rows today, with slugs from `get_unique_slug(model_class, site, slugify(title), uuid)`. These are unique per site, not per course.

## 2. Schema and validation: where rules live

| Concern | Location |
|---|---|
| `children:` key, entry shape | `content_engine/schema.py`: `Course.children`, `CoursePart.children`, `Child`, `PartChildDueDate` |
| Due keys and `no_due_date` on an entry | `content_base/schema.py`: `DueDateFields`, `PlacementDueDate` (`holds_due_value`, `sets_a_due_key`, `_no_due_date_stands_alone`), `DUE_DATE_FIELD_NAMES` |
| Due keys on a child file | `schema.Topic` includes `DueDateFields`. `Activity` does not. A Form schema in `form_engine/schema.py` carries them too |
| Due-key child-type rule ("only TOPIC or FORM") | `validate.py`: `_DUE_DATE_CHILD_TYPES`, `_direct_entry_errors` |
| Nested `children:` rules | `validate.py`: `_nested_list_errors` (not in a part's own entries, only on a part target, names must exist in the part, topics and forms only, no repeats) |
| Duplicate child in one list | `validate.py`: `validate_children_lists`, `_repeated_indices` |
| Cross-file resolution of entries | `validate.py`: `_ParsedByPath` |
| Part children are only Topic/Form? | **Not validated.** A part's children are auto-discovered or listed with no type check. The only part-children constraint is in `_nested_list_errors` (nested due-date lists) |
| Form `sections:` targets | `validate.py`: `validate_question_sections`, `_SECTION_TYPES` (TOPIC, COURSE_PART) |
| Category references | `validate.py`: `validate_category_references` |
| Both-in-learning-path-and-reference rule | Does not exist. It is a new cross-file rule over `item.children` and `item.reference` |

- A "no due keys on a reference entry" rule fits `schema.py`. A narrower entry class would reject them at parse time.
- "No due keys inside a reference part" and "no Form children in a reference part" are cross-file rules. A part's topics are separate files that carry due keys in their own frontmatter (`save_topic` excludes `DUE_DATE_FIELD_NAMES` from the Topic row and writes them via `placement_due_columns` to the collection item). They belong in `validate.py` beside `validate_due_date_placements`, resolving the part's children with `collection_children` / `_ParsedByPath.children_of`.
- **Tension with sharing:** a part placed in course A's learning path and referenced by course B has one set of part-to-topic collection items. Topic files carrying due keys there are legitimate for A and forbidden by the reference rule for B.
- `content_engine/checks.py` is Django system checks for settings only (E001 to E003: required settings, `DEFAULT_CURRENCY`, `PRICE_LOCALE`). It has no content rules. Reference rules do not belong there.
- There are no model-level checks for content structure. `Course.clean()` covers icon and price only.

## 3. Direct `ContentCollectionItem` queries and part walks (non-test)

Model facts that govern the risk analysis (`content_engine/models/courses.py`):

- `ContentCollectionItem` uses generic foreign keys. `collection_type` and `child_type` are real FKs to Django `ContentType` (CASCADE). `collection_id` and `child_id` are plain `UUIDField`s with no database FK to the object.
- Only `Course.items` and `CoursePart.items` are `GenericRelation`s, on the collection side. Deleting a course or part cascades its own collection items. Deleting a child (topic, form, or a part placed in a course) leaves collection items pointing at it, which are dangling.
- `CoursePart.items` and `CoursePart.collection_items()` give a part's own children with no knowledge of any course.

The one thing every site shares: **a reference-only part has no collection item with `child_type=CoursePart` in any course.** Every query that begins at a course (`course.items`, `collection_items()`, `viewable_collection_items()`, `children()`) never reaches it. Every query that begins at a part and asks "which courses place this part" returns an empty set.

| Site | What it does | Reference-only part (no placement in a course) |
|---|---|---|
| `content_engine/management/commands/content_save.py` (`update_or_create`) | Writes a collection item per child per collection, for every part in `collections_data` | Part-to-topic collection items are written as for any part. Works unchanged. A course-to-part collection item is not written (correct) |
| `content_engine/moved_children.py` (`_base_manager` x2, `viewable_collection_items`) | Move detection (see section 1) | Not mishandled. It yields no courses, so no moves. It silently skips detection |
| `deadlines/resolver.py` `_item_defaults_by_course` (`objects.filter` x2) | Starts from course-level collection items for the given courses, finds part placements, then part-level collection items for the placed parts | Not reached. The part has no course-level collection item. No value is assigned, so reference topics are offered no deadlines. Matches the idea |
| `deadlines/admin.py` (`collection_item` picker) and `deadlines/forms.py` (`ContentCollectionItem.objects.filter(pk__in=viewable_collection_items)`) | Pickers restricted to `course.viewable_collection_items()` | Excluded, correctly |
| `deadlines/signals.py` `carry_over_deadline_overrides` | Moves deadline overrides from `move.stale` to `move.new_row`. Driven by `MovedChild`, so by `moved_children` | Never fires for a reference-only part |
| `deadlines/actions.py`, `deadlines/models.py` | FK to `ContentCollectionItem` for override rows | Reference rows are never offered, so no override rows can name them |
| `learner_progress/models.py` (lines ~77, 154, 274) | `TopicProgress.collection_item`, `FormProgress`-related and `CourseFormAttempt.collection_item`, all `null=True, on_delete=SET_NULL` | Fine if reference viewing writes no progress, as the idea says. If a view reused the existing topic view with a reference collection item, progress would be written against it |
| `learner_progress/attempts.py` | Takes a `collection_item` per attempt | Course-rooted callers only |
| `learner_interface/utils.py` | `get_item_part`, `get_course_index`, `get_resume_index`, `create_child_dict_with_flattened_index` iterate `course.children()` / `viewable_collection_items()` | Not reached. Reference topics are absent from the index, resume, flat position and gating. A part nested in a part is explicitly handled and ignored (line ~810) |
| `learner_interface/views.py` | Topic and form views take `collection_item` from the flat course index | A reference topic has no flat index and no collection item in the course. The existing topic view cannot serve it without a separate view or lookup |
| `educator_interface/panels/course/content_preview.py` | Walks `course.collection_items()`, one level into `child.collection_items()` for parts | Reference parts are not shown. They need their own walk, as the idea says |
| `content_engine/admin.py` | `ContentCollectionItemInline` on `CourseAdmin` and `CoursePartAdmin`; `ContentCollectionItemAdmin` | A reference part shows in `CoursePartAdmin` with its topic collection items. Nothing in the admin shows that a part is a reference of a course |
| `dev_tools/management/commands/danger_content_delete.py` | Counts and deletes Forms, Topics, Activities, Courses, Course Parts, Articles, Collection Items, Files in a fixed order | See below |
| `qa_helpers/management/commands/qa_*` (about 30 files, `ContentCollectionItem.objects` or `_base_manager`, dev seed and QA fixtures) | Create and look up collection items for seeded courses | Out of scope for runtime behaviour. A QA seed for reference material would be new |

Note on counts: grep finds about 30 non-test `ContentCollectionItem.objects` / `_base_manager` call sites, of which 22 are `qa_helpers`. Outside `qa_helpers` and tests, the direct manager queries are `content_save.py`, `moved_children.py` (x2), `deadlines/admin.py` (x2), `deadlines/forms.py` (x2), `deadlines/resolver.py` (x2), plus the factories and `conftest.py` (`course.items.create`). The idea's "about 16" is not far off these.

### Deadline code assumptions

No deadline code was found that assumes every part has a course placement and would fail without one. The resolver builds from the course down, so it never touches a part with no placement. The real hazard is the opposite: a part that is both reference and placed (the idea forbids it) or a reference part shared into another course's learning path. That sharing is allowed, and there the deadline code applies to the other course normally.

### Dangling rows and deletion

- Deleting a `Course` cascades `CourseReferencePart` only if its `course` FK is CASCADE, and the same for `course_part`. PROTECT on `course_part` would make `danger_content_delete` fail unless `CourseReferencePart` is deleted first. The command deletes `Course` before `CoursePart`, and the unordered `models_to_delete` list has no PROTECT handling beyond the comments in the file.
- `danger_content_delete.models_to_delete` lists models for the count and delete. A new model not in it is not counted in "Total items to delete", and relies on cascade.
- Content is never deleted by `content_save`, so a removed file leaves its rows. A rename keeps the row (uuid-keyed). A removed `reference:` entry would leave a `CourseReferencePart` row unless the loader reconciles.
- The existing collection-item staleness has a direct consequence for this feature. A part moved from `children:` to `reference:` keeps its old course-to-part collection item in `Course.items`, so it stays in the learning path in the database. File-level validation ("not in both") passes. The stale row and the new `CourseReferencePart` row coexist, with the effects the idea lists (completion, flat position, deadlines). The existing mechanism offers no cleanup for this. Other stale collection items already behave this way.
- There is no `GenericRelation` from Topic or CoursePart back to collection items as child. Dangling collection items after a child's deletion are an existing condition, not new. A real FK on `CourseReferencePart.course_part` would not dangle.
- Admin deletion of courses, parts, topics, forms and files is disabled (`has_delete_permission` False on `CourseAdmin` and `CoursePartAdmin`; `docs/product/admin-interface.md`), so `danger_content_delete` is the only bulk path.

### Other facts

- `Course.collection_items_flat` / `viewable_collection_items` expand one level into a part (`item.child.collection_items()`). Reference parts are separate, so they do not appear. If a future walk reuses `CoursePart.collection_items()` on a reference part, only the part-to-topic rows come back, which is what the idea wants.
- Slugs: `CoursePart` slug uniqueness is `unique_course_part_slug_per_site` (site, slug), not per course. Two courses with reference parts titled "Regulations" get suffixed slugs. The idea's URL `courses/<slug>/reference/<part_slug>/<topic_slug>/` therefore keys on a slug that can change if another part with that title is loaded earlier. Topic slugs are likewise site-unique.
- Nesting a reference part inside a part (or a part that lists a part) is already tolerated and ignored in learner utils. Nothing validates against it.

## 4. Author-facing docs that would need updating

`claude_plugins/fls-content/` (content-types skill and the rest):

- `skills/content-types/SKILL.md`: the content-type table and conventions (part.yaml lines ~18 and 32).
- `skills/content-types/resources/course-files.md`: the field table (`children` at line ~33), "Child auto-discovery" (line ~72), due keys on `children:` entries (line ~83, ~95-110: where "no due keys on reference" would sit), the `COURSE_PART` section (~440-455), and the `application_form` note (~274, a precedent for "named here, not in children").
- `skills/content-types/resources/file-layout.md`: directory layout (~14-39), role files (~88-98), and "Child auto-discovery" (~110-121). This is where the `reference/` directory and its relationship to auto-discovery are documented.
- `skills/content-types/resources/topic-files.md`: due keys on topic frontmatter (line ~32), relevant to the reference due-key rule.
- `skills/content-types/resources/form-files.md`: `sections:` targets (parts and topics). Reference parts as section targets are not addressed.
- `validate/schema.py` and `validate/validate.py` (plus `validate/tests/test_validator.py`): the bundled standalone validator, a re-synced copy (see section 1).
- `commands/init.md`, `commands/validate-content.md`, `commands/format-content.md`, `agents/content-formatter.md`, `skills/conventions/SKILL.md`, `skills/markdown-conversion/*`: mention children, parts or layout. They need checking for a reference layout, not necessarily changes.

`docs/product/`:

- `learner-experience.md`: "Course Parts (Chapters)" at line ~244, the natural neighbour for a Reference section.
- `content-editing-workflow.md`: lines ~91 and ~118 mention parts and children.
- `admin-interface.md`: line ~16 (deletion rules) and ~157; a reference model would have to be added to what the admin shows.
- `docs/product/_build/` is a build artefact, not source.

`demo_content/README.md` has no mention of the parts demos (no match for `course_parts`), so it needs no change for a new demo unless it indexes them some other way.

## 5. Demo content

Existing relevant courses (`demo_content/`):

- `functionality_demo_course_parts/`: three part directories (`01. Getting Started`, `02. Core Concepts` with a quiz form, `03. Wrapping Up` with a feedback form). `course.md` has no `children:`, so it uses auto-discovery. This makes it the existing demo of "numbered directories, no explicit list".
- `functionality_demo_course_parts_placement/`: the `../` demo. Its only child is `../functionality_demo_course_parts/02. Core Concepts/part.yaml` with per-placement due dates. It also acts as the shared-part demo, but for learning-path placement.
- About 16 other functionality demos (prices, quizzes, widgets, organisations, application-gated). None has a reference-style structure.
- `freedom_ls/content_engine/tests/demo_content/` holds tests that load these courses (test_due_date_placements, test_question_sections, etc., with a `conftest.py`). Editing `functionality_demo_course_parts` or the `Core Concepts` part risks changing assertions in tests that load or count them, notably the due-date placement tests that read `functionality_demo_course_parts_placement`. The `reference-demo` category seen in both course.md files is a category slug, not a feature.

Observations for the choice:

- Adding `reference/` to `functionality_demo_course_parts` (no explicit `children:`) would exercise the auto-discovery ignore behaviour described in section 1. It would also change a course other demos and tests depend on, so its part and topic counts would shift.
- A new demo course gives an isolated target: one course with a learning path and a `reference:` list, with an in-directory reference part. A second course (or the same one) with `../` path sharing a reference part across two courses, and a library-only course (empty learning path, only `reference:`) for the learner-side empty-path work. Library-only matters because no existing demo has an empty `children`.
- Any new demo has to be registered the way the existing ones are, with a uuid in `course.md` and a `categories:` entry that exists in `demo_content/course_categories.yaml`. A demo test in `freedom_ls/content_engine/tests/demo_content/` would sit beside the others.

status: ok
