# Research: codebase (question sections)

Question: what in the existing codebase does this work touch, reuse or conflict with? All paths are under the worktree root. Settled user answers (`answers.md`) are taken as given.

## Headline findings

1. A path names a **file**, not a content row. `resolve_author_path(declaring_file, author_path)` returns the resolved file path; the loader looks that key up in `content_by_path`. A CoursePart is the file `part.yaml`; a Topic is `content.md` or a `NN. name.md` file. One new key can therefore name either, and the loader tells them apart by the type of object in `content_by_path`.
2. The load order already suits the feature: topics, activities, courses and parts are saved **before** forms, pages and questions. `content_by_path` is complete for them when questions save. `save_form_question` does not receive `content_by_path` today, so the loader needs it passed down or a post-pass.
3. A form placed in no course **already loads**, pages and questions included. The demo application form is the live example. Idea fact (b) is confirmed: no loader change is needed for unplaced forms.
4. `content_save` **never deletes** a content row. A question dropped from a file stays in the database and still renders on its page. `QuestionAnswer.question` is PROTECT, and the loader's own comments say stale rows exist. Idea fact (a) is confirmed. The spec must say what a stale question's section link means.
5. `save_with_uuid` builds the model kwargs from the pydantic dump and **raises** if a key is not a model field. A new pydantic key `sections` has to go in `exclude_fields`, as `options`, `when` and `children` do.
6. The offline validator is a bundled, patched **copy** of `freedom_ls/content_engine/validate.py` and the schemas, re-synced by `/update_claude_plugin_fls_content`. A new schema field and validator function must land in both, plus `form-files.md`.

## (a) How author paths resolve; part vs topic; rename and move

- `freedom_ls/content_engine/validate.py:46` `content_key(path)` is `Path(path).resolve()`, the one normalised key for every lookup. `:56` `resolve_author_path(declaring_file, author_path)` is `content_key(Path(declaring_file).parent / author_path)`. The path is relative to the **declaring file's directory**, and must end in the target's file name.
- The loader keys `content_by_path[content_key(item.file_path)]` for topic (`content_save.py:1017`), activity (`:1024`), course (`:1038`), part (`:1045`) and form (`:1055`). Articles are deliberately not added (`:1028`).
- `children:` is resolved by `collection_children` (`validate.py:697`), shared by the validator and the loader "so the two never disagree". A miss raises at `content_save.py:1210`: "Collection '...' names a child at {path} that was not loaded".
- **A path can name a CoursePart or a Topic.** Both are in `content_by_path`. A `Course`, `Activity` and `Form` are in it too, so the new check has to reject them by type: `isinstance(obj, (CoursePart, Topic))`. Precedent for a type check on a resolved path: `content_save.py:1150` ("which is not a loaded FORM"), and `validate.py:683-694` and `:815` for `_DUE_DATE_CHILD_TYPES = {TOPIC, FORM}`.
- Example paths, from a question page file in `demo_content/functionality_demo_course_parts/02. Core Concepts/03. knowledge-check/1. page.yaml`: the part is `../part.yaml`; a topic is `../01. key-ideas/content.md`.
- **The declaring file differs by level.** A per-question key resolves against the page YAML file (`FormQuestion.file_path` is the page file). A form-level default lives in `form.md`. Both sit in the same directory (`validate_form_conditions` groups pages by `file_path.parent == form dir`, `validate.py:1020`; the loader does the same at `content_save.py:1067`), so one relative path means the same thing at both levels.
- **Rename or move of the target.** There is no path-follow logic anywhere. Moving or renaming the target file makes the old path resolve to nothing, and the load **errors** (same as a stale `children:` entry). The row's identity survives because the target keeps its `uuid` in its own file (`save_with_uuid` update_or_create on `id=uuid`, `content_save.py:329`). The author must update the path in the form file. This is the behaviour the user chose ("same as a broken `children:` reference"); the spec should state it, and state that a stale path never silently re-links.
- **Rename or move of the form file.** Paths are relative, so moving a form directory without its target breaks every relative path in it. Moving both together keeps them valid.
- **Re-placement of the target** (a renewal course placing the same part again) changes only `ContentCollectionItem` rows, never the part or topic row. A link to the row survives. Nothing here needs to know about placements.

## (b) content_save load order and cross-file references today

`save_content_to_db` (`content_save.py:945`, `@transaction.atomic`) order:

1. Parse every file (`:963-965`).
2. Pre-write validation: `validate_children_lists` and `validate_due_date_placements` (`:970-975`). Raises one `ValueError` of every error "before anything is written". **A new reference validator belongs in this list**, because `command()` runs `validate(path)` first (`:1275`) but `save_content_to_db` called directly (as every `test_content_save.py` test does) does not.
3. Non-content files (images) (`:978`).
4. Course categories (`:1010`), Topics (`:1015`), Activities (`:1022`), Articles (`:1030`), Courses (`:1036`), CourseParts (`:1043`), Forms (`:1052`), then form pages, content and questions per form directory (`:1072-1132`).
5. `application_form` binding (`:1142`), which is the existing cross-file reference by author path, resolved with `content_by_path` after forms are saved and erroring with `ValueError` on a non-Form.
6. Collection children / `ContentCollectionItem` placement (`:1160`), due-date reconciliation (`:1221`).

So by step 4's question loop every topic and part row exists and is in `content_by_path`. `save_form_question` (`:730`) takes `item, form_page, site, base_path, order, condition_option` only, so it needs the resolved targets (or `content_by_path`) passed in, or a post-pass like step 5. `_resolve_condition` (`:661`) is the precedent for a per-question reference resolved from "this run's saved objects rather than the database", erroring with `ValueError` naming the file.

**Required error text.** The user answer says "naming the question and the missing target". `children:` names the collection and the resolved path; `validate.py:578` `_reference_error` already has header/field/problem/given-value/fix layout, and `_condition_error` (`:900`) labels the question via `_target_label` (`:919`: `question "..."`). Reuse those.

**Reading outside the validated path.** `_ParsedByPath` (`validate.py:717`) parses a key from disk on first use when it was not in the validated set, so a single-directory validate run can still check a target in a sibling directory. A section link check needs the same, since a form can point at a part outside its own directory.

**uuid write-back interaction.** `update_file_with_uuid` (`:122`) re-serialises the first section without a `uuid` using `yaml.dump(..., Dumper=PreservingDumper)`, which sorts keys and drops comments but keeps an extra list-of-strings key intact. The new key survives. Existing behaviour, not a new problem.

## (c) A form placed in no course (idea open fact b)

**Confirmed: loads today.** Evidence:

- `save_content_to_db` saves every `FORM` item (`content_save.py:1052-1057`) and registers `forms_by_dir[item.file_path.parent]`. Pages are attached to a form by **directory** (`:1064-1069`), never by a collection item. Placement is never consulted.
- Live example: `demo_content/functionality_demo_application_form/` is not listed in any course's `children:`. A course names it only through `access_config.application_form` (`freedom_ls/content_engine/tests/demo_content/test_application_form.py:35`). Its pages and questions load, including a `file_upload` question (`:63`).
- Test with a temp directory: `test_content_save.py:1060` `test_a_course_binds_the_application_form_its_access_config_names` loads a form directory with no placement.
- Caveat the spec should note: a directory beside a course's `course.md` with no `children:` list **is** auto-discovered as that course's child (`validate.py:61` `auto_discovered_children`). A "bank form" therefore must sit **outside** any collection directory that auto-discovers, or be listed in no `children:` and live under an `_`-prefixed name (skipped, so **not loaded at all**, `validate.py:37`). Put it in a sibling directory of the courses, as the application form is.
- No code change is needed for the answer "bank forms must work". The spec can still add a test that a section link on an unplaced form's question resolves and stores.

## (d) Does content_save delete dropped questions; what PROTECTs answers (fact a)

**Confirmed: no deletion.**

- The only `.delete()` calls in `content_engine/management` are an image file (`content_save.py:916`) and the stale `CoursePartChildDueDate` rows (`:1247-1253`). Questions, options, pages, topics and parts are written with `update_or_create` / `create` and never removed.
- `_resolve_condition` states it: "questions dropped from the YAML and options re-created without a uuid leave stale rows" (`content_save.py:667-670`).
- Test evidence for the same policy on another type: `test_deleting_the_file_and_reloading_leaves_the_row` (`test_content_save.py:205`).
- A dropped question therefore still has its `FormPage` FK and still appears in `FormPage.children()` (`form_engine/models.py:112`, `self.questions.all()`), so it renders. Its section link row also remains. A consequence for the later features: a stale question carries a live section link. The spec for this feature should say the loader neither cleans nor ignores it and leave pruning to the later specs, or name it as a known limit.
- PROTECT chain: `QuestionAnswer.question = ForeignKey(FormQuestion, on_delete=PROTECT)` (`form_engine/models.py:728`); `FormProgress.form` is PROTECT (`:290`); `QuestionOption` is CASCADE from its question (`:263`); `condition_option` FKs are RESTRICT (`:104`, `:145`, `:181`). Deleting a question that has answers raises `ProtectedError`. Deleting a question with none cascades its options (and, with a new M2M, its through rows).
- **A question without a `uuid` is created fresh on every load until the first load writes one back** (`save_with_uuid`: `create` then `update_file_with_uuid`, `:333-336`). It is written back on the first load, so its second load is `update_or_create` on the same id. If the write-back fails or the file is read-only the question is re-created each load. Section links on a question re-created each load are replaced each time (see (f) replace semantics), so they cannot accumulate, but the old row stays as a stale question.

## (e) Pydantic schemas, validator, docs that must change

Schemas (all `extra="forbid"` via `BaseBaseContentModel`, `content_base/schema.py:25-26`):

- `freedom_ls/form_engine/schema.py:40` `Form(BaseContentModel, MarkdownContentModel, DueDateFields)`: add the form-level default key here. It already has a `model_validator` pattern (`validate_quiz_fields`).
- `:145` `FormPage(BaseContentModel)`: only `when`. No change unless the author may set a per-page default (not asked).
- `:176` `FormQuestion(BaseBaseContentModel)`: add the per-question key. Existing pattern for a reference-bearing field: `when: Condition | None` with `WHEN_DESCRIPTION` (`:139-148`), and `Child`/`PlacementDueDate.path: Path` (`content_base/schema.py:135`). A list of paths is `list[Path]`, matching how `Child.path` is typed.
- A content-type quirk: `FormQuestion` has **no** `title`; `FormPage.derive_content_type` (`:150`) selects `FORM_QUESTION` when a section has a `question` key. A new key must not break that.
- **Distinguish "not set" from "set to empty".** The user wants a form default that a question overrides. `save_with_uuid` already drops `None` and uses `model_fields_set` for `tags` (`content_save.py:293-298`). Use `None` (absent) for "inherit" and `[]` for "explicitly none" if the spec wants an empty override; that is a spec decision, but the schema must be able to say it.
- **`save_with_uuid` will raise** ("Fields present in frontmatter but don't exist in Django model", `:311-322`) unless the new key is excluded: `save_form_question` already passes `exclude_fields={"options", "when"}` (`:749`), `save_form` passes `DUE_DATE_FIELD_NAMES` (`:657`), `save_course_part` passes `{"children"}` (`:650`). Add the new key to the question and form exclusions. If the form default is not stored as a model field, it must be excluded in `save_form` too. `model_field_names` uses `_meta.get_fields()`, which includes M2M and reverse relations, so a model field named exactly like the pydantic key would **not** raise but would be handed a list of `Path`s in `update_or_create(defaults=...)` and fail. Name them differently or exclude.

Validator (`freedom_ls/content_engine/validate.py`) must gain one cross-file function, called from both `validate()` (`:1137-1148`) and the pre-write list in `save_content_to_db` (`:970`). Model it on `validate_form_conditions` (`:1003`, reports every error, labels the question) and `_ParsedByPath` (`:717`, reads targets outside the validated path). Rules: target exists; target is a `COURSE_PART` or `TOPIC` (not a course, activity or form); optionally no duplicate in one list (as `validate_children_lists` does, `:837`). The form default and each question are checked with their own declaring file.

Bundled copy:

- `claude_plugins/fls-content/validate/validate.py` and `schema.py` are mirrored, patched copies (`schema.py` header, `validate.py:1`). The header "Patches applied" lists in both files are authoritative; `claude_plugins/fls-dev/commands/update_claude_plugin_fls_content.md:36,51` names the six mirrored source paths, including `form_engine/schema.py` and `content_engine/validate.py`. Both change here, so the spec needs a re-sync step.
- The copy has its own `FormQuestion` at `claude_plugins/fls-content/validate/schema.py:1186` and `Form` at `:884`, and `resolve_author_path` at `validate.py:118`. Tests: `claude_plugins/fls-content/validate/tests/test_validator.py` (runs the script as a subprocess, so it covers the copy; the core tests in `freedom_ls/content_engine/tests/test_validate.py` cover the original). Both need tests.
- The pydantic schemas are also exercised for key lists in `freedom_ls/content_engine/tests/test_schema.py`.

Docs:

- `claude_plugins/fls-content/skills/content-types/resources/form-files.md`: FORM frontmatter table (`:13-27`), FORM_QUESTION fields table (`:116-130`), a section explaining the path rule and the override, and an example. The QUIZ example (`:35-43`) is the natural place to show the default. The `when` section (`:295-358`) is the layout model for a new section.
- `claude_plugins/fls-content/skills/content-types/resources/course-files.md` is where `children:` path semantics are described; link to it rather than repeat.
- No `docs/` page lists form fields (`decimal_places` appears only in the plugin and `update_claude_plugin_fls_content.md`), so the plugin docs are the only authoring documentation to update, plus `.claude/ds` / `fls-dev` references if any list the mirrored sources.
- Demo content: `demo_content/functionality_demo_course_parts/02. Core Concepts/03. knowledge-check/` is a QUIZ form inside a part and a ready fixture for a demo; `form.md` there has `quiz_pass_percentage`.

## (f) Storing a many-to-many to two content types

Facts:

- `FormQuestion` is `BaseContent` = `SiteAwareModel + TimestampedModel` (UUID pk, required `site` FK). `CoursePart` and `Topic` are `TitledContent`, also `SiteAwareModel`, UUID pk.
- App direction: `form_engine` may import `content_engine`; the reverse is forbidden (`content_engine/models/courses.py:22-24`), though `Course.application_form` already points at `freedom_ls_form_engine.Form` by string. A model in `form_engine` pointing at `content_engine.Topic` and `CoursePart` is in the allowed direction. `content_engine/models/__init__` exports must be checked, not assumed.
- **Generic-FK precedent:** `ContentCollectionItem` (`content_engine/models/courses.py:572`) holds `child_type` (FK to `ContentType`, CASCADE) + `child_id` (UUID) + `GenericForeignKey`, with an index on the pair. It is a `SiteAwareModel`, and the loader writes it with `site=site` explicitly (`content_save.py:1188-1198`) because "the load runs with no request". There is **no** `GenericRelation` on `Topic`, so deleting a Topic leaves orphan `ContentCollectionItem` rows pointing at nothing. (`Course` and `CoursePart` have a `GenericRelation` only for the collection side, `items`.) That is the existing "what happens on delete" for generic links, and it is the behaviour a generic link would inherit: nothing cascades and nothing blocks.
- **Plain M2M precedent:** `Course.categories = ManyToManyField("freedom_ls_content_engine.CourseCategory", blank=True)` (`courses.py:161`) and `QuestionAnswer.selected_options` (`form_engine/models.py:729`). The loader uses `collection.categories.set(CourseCategory._base_manager.filter(site=site, slug__in=...))` at `content_save.py:1168`, explicitly commented as "a replace, not a merge" and the one place a load removes something. `_base_manager` is used because the default manager is `SiteAwareManager`, which filters by the thread-local request and so does nothing in a loader but is the wrong thing to rely on. An auto-created through table has **no `site` column**, which matches how these existing M2Ms behave.

Options for the spec to choose between (this research does not choose):

| Option | Real FK integrity | Delete behaviour | Cost |
|---|---|---|---|
| Two plain M2M fields on `FormQuestion`, one to `Topic` and one to `CoursePart` | Yes, DB-enforced | Deleting a target removes its through rows (auto-through CASCADE); the question is left with fewer links, silently | Simplest; two relations to query and merge; matches the `categories` precedent and `.set()` replace-on-load |
| One through model with two nullable FKs (Topic, CoursePart) and a check constraint "exactly one" | Yes | Choose CASCADE/PROTECT/SET_NULL per FK | Extra model; a `SiteAwareModel` through needs `site=` set by the loader and a unique constraint per (question, target) |
| One generic through model, `ContentType` + UUID, like `ContentCollectionItem` | No | Orphans, as `ContentCollectionItem` does today | One relation for both types; no DB integrity; needs a site-aware row and an orphan policy |

The user's answer "stored as a real link" favours the first two. A "real link" in the answer reads as a DB foreign key; the generic option is not one. Note also:

- **Site isolation.** `SiteAwareModel.objects` is `SiteAwareManager` (`site_aware_models/models.py:118`), filtering on the thread-local request. A loader has none, so it filters nothing: the loader must itself scope the target lookup to `site` (as `content_by_path` does, because it only holds rows saved this run on this site). A through model that carries `site` must have it written explicitly (`:140` `_set_site_from_request` only fills from a request). Resolving from `content_by_path` rather than querying by slug or path avoids cross-site leakage entirely.
- **Uniqueness.** `Topic` and `CoursePart` slugs are unique per site (`UniqueConstraint(["site","slug"])`, e.g. `CoursePart` Meta at `courses.py:538`), but a path is the author's key, not the slug.
- **Replace on load.** Reuse the `categories.set()` precedent: every load sets the question's links to exactly what the file (or the form default) says. This is what makes "form-level default plus per-question override" stable across reloads: re-resolve the effective set on each load. It also means a hand edit in the admin is overwritten on the next load, as with categories. It means a removed key clears the link, where `save_with_uuid` would otherwise leave a stale value (cf. `content_save.py:692` for `condition_option` and `:742` for `slug`, both written even when absent for this reason).
- **Admin.** `FormQuestionAdmin` (`form_engine/admin.py:134`), `FormQuestionInline` (`:92`) and `FormPageAdmin` (`:200`) are site-aware admins; a new M2M adds a form field there. Decide read-only vs editable; the user said "author in the form file, not in the admin" (idea).
- **Form-level default storage.** The default can be (i) copied onto each question at load (no new column on `Form`), or (ii) stored on `Form` and resolved at read time. (i) matches the replace semantics above and keeps downstream queries on one table. (ii) needs a second relation and a "which wins" rule in every reader. Not decided here.

## (g) What deletes or orphans when a referenced topic or part is removed from content

- **`content_save` never deletes a Topic or CoursePart row** (see (d)). Removing a topic file leaves the row, the placement rows and any section link intact. The only removal path for a topic or part row is the admin, a shell, or a new migration.
- **Removing the file but leaving the form's path** (the case the user cares about): the **form file** now names a missing target, so the load **errors** (user's answer, `children:`-style). The author must then fix the form file. Because the loader is `@transaction.atomic` and the error is raised before any write if the check sits in the pre-write list (`:970-975`), the database is unchanged.
- **Removing a topic from a course's `children:` but leaving its file:** nothing happens to the link; the topic row and its link are untouched. This is the "re-placement" case and is correct.
- **Row deletion in the admin:** with a plain M2M the through rows cascade, so the question silently loses that section. With a generic link the row is orphaned. With `PROTECT` on a through model the admin refuses the deletion. The spec must pick; "no silent loss" favours PROTECT or an explicit decision. There are no other FKs to `Topic` or `CoursePart` in any `models*.py` (grep across `freedom_ls`), so introducing this link adds the first deletion-blocking relation on them.
- **Dropped question rows** keep their links (see (d)). On the later features' side, a deleted-target or stale-question state must be handled by whoever reads the link.

## Conflicts and reuse summary

- Reuse: `resolve_author_path` + `content_key`, `content_by_path`, `_ParsedByPath`, `_reference_error` / `_condition_error` / `_target_label`, `categories.set()` replace-on-load, `exclude_fields`, `model_fields_set`.
- Conflict risks: `save_with_uuid` model-field check; `save_form_question` signature (needs targets); `FormPage` selection by `derive_content_type` (do not add a key that collides with `content`/`question`); the bundled validator copy; `QUIZ` forms (`when` banned there, no effect on this key).
- No conflict: unplaced forms, load order, `form_engine` -> `content_engine` import direction.

## Sources

Local only; no web sources were used.

status: ok
