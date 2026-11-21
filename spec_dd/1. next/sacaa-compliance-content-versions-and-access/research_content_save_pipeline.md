# Research: the content save pipeline today

Scope: codebase only. Files read: `freedom_ls/content_engine/management/commands/content_save.py` (CS), `content_validate.py`, `validate.py`, `schema.py`, `moved_children.py`, `freedom_ls/dev_tools/management/commands/danger_content_delete.py`, models in `content_engine/models/`, `form_engine/models.py`, plus greps of callers, tests, docs and the glossary. Items not verified are marked "not checked".

## How the command works today

- `command(path, site_name)` (CS, bottom): two positional args, one path and one site name. It calls `validate(path)` then `save_content_to_db(path, site_name)`. There are no flags. `content_validate` is `validate(path)` only.
- `validate(path)` (validate.py ~1218): path must exist. It scans with `get_all_files`, calls `parse_single_file` on every .md/.yaml/.yml (pydantic schema errors collected per file), then cross-file passes (category references, widget references, children lists, due-date placements, form conditions, question sections, article images). All errors are reported together in one ValueError. It returns quietly (warning only) when no content files are found. It never touches the database and never checks uuids.
- `save_content_to_db(path, site_name)` is `@transaction.atomic` and is called directly by tests and downstream projects. It does the following in order:
  - Looks up `Site` by `name`.
  - Re-parses everything.
  - Re-runs the placement checks (`validate_children_lists`, `validate_due_date_placements`, `validate_question_sections`). It does not re-run the full `validate()`.
  - Saves non-content files through `save_file_to_db`, then the image cache manifests.
  - Saves in this order: CourseCategories, Topics, Activities, Articles, Courses, CourseParts, Forms, FormPages with their FormContent, FormQuestion and QuestionOption.
  - Replaces question sections, binds `Course.application_form`, upserts `ContentCollectionItem` rows, reconciles `CoursePartChildDueDate`, runs `moved_children` / `carry_placement_due_dates`, and sends the `collection_items_synced` signal.
- Everything is an upsert by uuid and site (`save_with_uuid` -> `update_or_create(id=uuid, site=site)`). No uuid means `create()` plus a write-back into the source file.

## 1. `--generate-uuids`

Entities that get a uuid written back today:

| Entity | Writer | Notes |
|---|---|---|
| Topic, Activity, Article, Course, CoursePart, Form, FormPage, FormContent, FormQuestion | `save_with_uuid(update_file=True)` -> `update_file_with_uuid` | .md files get frontmatter. YAML files get the uuid on the first document section that lacks one. |
| QuestionOption | `update_file_with_option_uuids`, called from `save_form_question` | Written by index inside the owning question's YAML section. The question uuid must already be in the file. |
| CourseCategory (entries in the `COURSE_CATEGORIES` document) | `update_file_with_category_uuids` | Written by entry index. `update_file=False` per entry, one file rewrite per file. |
| File (non-content assets) | none | Keyed by `(site, file_path)`, no uuid. The model has no uuid in the frontmatter sense. |
| ContentCollectionItem, CoursePartChildDueDate | none | Derived rows, not authored. |

- Schema: `uuid: str | None` is optional on `content_base/schema.py` `BaseBaseContentModel` (line 34), the option schema in `form_engine/schema.py` (line 187) and the category entry in `content_engine/schema.py` (line 216). The validator never requires it, so the "missing uuid" check does not exist anywhere yet.
- Where an early check could sit:
  - `validate.py` runs on parsed items with no DB, and `content_validate` and the offline `claude_plugins/fls-content/validate` copy share that shape. It already collects all errors at once. Options and category entries are visible there too: `item.options[*].uuid`, `item.categories[*].uuid`. Putting the check here would also change `content_validate` unless it is made conditional.
  - `save_content_to_db` re-parses and re-runs placement checks before any write. A check there covers callers that bypass `command()`, and it is the same place the "checked here as well as in the command's validate()" comment already justifies. A check after parsing and before `save_file_to_db` fails before any storage write.
  - A flag in the signature of `save_content_to_db(path, site_name)` is needed in any case. Tests, `freedom_ls/tests/demo_content_fixtures.py` and downstream code call it directly.
- Write-back is not rolled back with the transaction (files on disk). Note in the CS comment: "a file already sent to storage does not [roll back]".
- Who relies on auto-write:
  - `freedom_ls/content_engine/tests/management/commands/test_content_save.py` (about 4,000+ lines, 204 `uuid` mentions) has explicit write-back tests: `test_first_load_writes_the_uuid_back_and_stores_the_fields`, `test_saving_form_questions_and_text_adds_uuids_to_file`, `test_saving_form_question_options_saves_uuids_to_file`, `test_uuid_write_back_touches_only_entries_lacking_one`, `test_uuid_less_entry_whose_slug_is_taken...`, `test_a_question_first_loaded_without_a_uuid_keeps_its_sections_on_reload`, plus `make_temp_file`-based tests that load uuid-less files.
  - Other tests that call `save_content_to_db` or `content_save` directly: `content_engine/tests/{test_signals,test_moved_children,test_icon_validation,models/test_courses,demo_content/test_articles,demo_content/test_question_sections}.py`, `deadlines/tests/test_signals.py`, `educator_interface/tests/invariants/test_course_shares.py`, `course_access/tests/test_loader.py`, `blog/tests/test_views.py`, `dev_tools/tests/*`. Whether each loads uuid-less fixtures is not checked.
  - `demo_content/` already carries uuids (grep: 123 `^uuid:` lines across 73 files). It is loaded read-only by `demo_content_fixtures.loaded_demo_content` (`save_content_to_db(settings.BASE_DIR / "demo_content", site.name)`). Whether every demo item (all options, all category entries, all form questions) has a uuid is not checked. A new default-fail would break this fixture if any are missing.
  - The documented workflow (`docs/product/content-editing-workflow.md` line 19) says "On the first run of `content_save`, a UUID is written back". Docs and the `claude_plugins/fls-content` skills describe this and would change.

## 2. Organisations

- `_resolve_organisations(slugs, field, file_path, site)` (CS ~640) is called twice from `save_course`, for the `organisations` and `shared_with` frontmatter lists (slugs). It queries `Organisation._base_manager.filter(site=site, slug__in=slugs)`. An empty list returns `[]`. A missing slug raises `ValueError("Unknown organisations [...] in <field> of <file> on site '<name>'. Valid organisation slugs: [...]")`. This happens mid-transaction, so it rolls back the DB writes but not file write-backs or storage writes already done. The check runs when the Course is saved, after Topics/Activities/Articles and after non-content files are stored.
- Then `course.organisations.set(...)` and `course.shared_with.set(...)` replace the links.
- The `Organisation` model (`freedom_ls/organisations/models.py`, line 63): `SiteAwareModel` plus `TimestampedModel`, `name` (max 150) and `slug` (SlugField, `allow_unicode`), with unique `(site, slug)` (`unique_organisation_slug_per_site`). Other fields (bio, etc.) are not checked here beyond `bio` being set by `ensure_demo_organisations`.
- Existing creator: `freedom_ls/organisations/utils.py` `ensure_organisation(site, name, slug_base=None) -> (Organisation, created)`. It gets or creates by slug when `slug_base` is given. Otherwise it gets or creates by name and derives a unique slug. `freedom_ls/dev_tools/demo_organisations.py` `ensure_demo_organisations(site)` uses it and is called by `demo_content_fixtures`.
- The frontmatter value is a slug, not a name. The idea says "if an organisation is named that does not exist". A created row needs a name, which the file does not carry. `ensure_organisation(..., slug_base=slug)` would need a name derived from the slug, which is not checked here.
- Debug detection: nothing in CS reads `settings.DEBUG`. `freedom_ls/dev_tools/guard.py` has `require_dev_tools_enabled()` (used by the `danger_*` commands). Its relation to "debug mode" is not checked.

## 3. Single source and removal

Called as: `content_save <path> <site_name>`, one path, site looked up by `Site.name`. `ImageCache(path)` and `File.file_path` / `Model.file_path` are stored relative to that one path. Running it against two different paths for one site works today and the file_path values then lack any source prefix. `validate_question_sections(..., loaded_root=path)` also scopes to one root.

What a run removes today (the full list):
- `CoursePartChildDueDate` rows of every loaded course not re-written this run: deleted (`kept`, `loaded_course_ids`, `.exclude(pk__in=kept).delete()`).
- `FormQuestionTopic` / `FormQuestionCoursePart` section rows of loaded questions: replaced (`replace_question_sections`, `_sync_section_rows`).
- `Course.categories`: `.set()` replace. `Course.organisations` and `shared_with`: `.set()` replace.
- `ContentCollectionItem`: never deleted. `moved_children.py` docstring: "A sync never removes the row a moved child left behind". `moved_children` only detects unambiguous moves of rows in loaded collections and carries due dates (`carry_placement_due_dates`). A left-behind row for a dropped child stays. `viewable_collection_items()` is used there.
- Nothing is removed for: a deleted Topic/Activity/Article/Course/CoursePart/Form/FormPage/FormContent/FormQuestion/QuestionOption/CourseCategory/File file. `_resolve_condition` explicitly notes "questions dropped from the YAML and options re-created without a uuid leave stale rows".
- A removed option or question stays served: `FormQuestion` and `QuestionOption` rows are fetched by relation (`related_name="options"`, `"questions"`).

Models that would need a retired state, because file-sourced and never pruned: Course, CoursePart, Topic, Activity, Article, Form, FormPage, FormContent, FormQuestion, QuestionOption, CourseCategory, File, and the derived `ContentCollectionItem`. The two idea-level groupings: whole content items disappearing, and (separately) a question or option changing.

Existing status-like fields (grep of `content_engine/models/`, `form_engine/models.py`, `content_base/models.py`):
- `Course.visibility` (`CourseVisibility`: PUBLISHED, COMING_SOON; more values not checked, `courses.py` line 54) and `Article.visibility` (`ArticleVisibility`: PUBLISHED plus others, `articles.py` line 17). Both are file-authored.
- No `is_active`, `archived`, `retired` or version/revision field on any content or form model. `BaseContent` (`content_base/models.py` line 11) is `SiteAwareModel, TimestampedModel` and the uuid is the pk `id`. `TitledContent` and `MarkdownContent` extend it.

What references content from learner data (deletion safety):
- `FormProgress.form` PROTECT (`form_engine/models.py` ~290).
- `QuestionAnswer.question` PROTECT (~749). `QuestionAnswer.selected_options` is a plain M2M to `QuestionOption`: deleting an option drops the through row silently, so the record of what was chosen is lost. `QuestionOption.question` is CASCADE, so deleting a question's options or a FormPage cascades. There is no snapshot of question text or option text on the answer.
- `FormPage`/`FormContent`/`FormQuestion.condition_option` RESTRICT to `QuestionOption`. `FormPage.form` CASCADE, `FormQuestion.form_page` CASCADE.
- `TopicProgress.topic` PROTECT; `CourseProgress.course` PROTECT, and it PROTECTs the registration that granted it (`learner_progress/models.py`).
- `LearnerCourseRegistration.course` and `CohortCourseRegistration.course` PROTECT (`learner_management/models.py` ~278, ~324). `RegistrationRule.course` PROTECT. `Course.application_form` and `CourseApplication` -> form progress RESTRICT (`course_applications/models.py` ~130).
- Deadlines: `CourseDeadlineConfig.course` is a OneToOne; cohort and learner deadline overrides use `course`. `deadlines/models.py` on_delete behaviour is not checked. `CoursePartChildDueDate` and `ContentCollectionItem` are site-aware rows with FKs to content.
- `audit_log` targets use a generic FK with `target_content_type` PROTECT and `target_object_id` as a char field (no FK to the content row).
- `danger_content_delete.py` shows the working order: first delete `QuestionAnswer`, `CourseFormAttempt`, `FormProgress`, `TopicProgress`, `CourseProgress`, the two registration types, plus optional `CourseApplication` and `RegistrationRule`; then Forms, FormPages, FormContent, FormQuestions, QuestionOptions, Topics, Activities, Courses, CourseParts, Articles, ContentCollectionItems, Files. It states that progress PROTECT is "deliberate". It uses `model.objects.all()` (the site-aware manager). It does not touch CourseCategory, `FormQuestionTopic` (cascade on question), `CoursePartChildDueDate`, or `Course.organisations`. Whether `objects.all()` covers every site is not checked.

## 4. Git

- No GitPython. `subprocess` with git appears in `freedom_ls/accounts/legal_docs.py` (reads a git blob at HEAD, `subprocess.run`, line 75) and `build_legal_docs_manifest.py`. Filesystem-only git reads (no binary) are in `freedom_ls/base/git_utils.py`: `get_current_branch`, `get_head_commit` (reads `HEAD`, loose refs, `packed-refs`, worktree `gitdir:` and `commondir`; docstring says it must work in Docker images without a `git` binary). `deployment/checks.py` only mentions the SHA in a Sentry message. `image_cache.py` mentions git only in comments (the cache manifests are meant to be committed). Tests with git helpers: `accounts/tests/_git_helpers.py`, `base/tests/test_git_utils.py`, and `content_engine/tests/demo_content/test_form_link.py` (matched by the git grep, purpose not checked).
- Callers of `content_save` / `save_content_to_db` and what a git requirement would break:
  - Command: documented usage `content_save <path> <site>` in `docs/product/content-editing-workflow.md`, `claude_plugins/fls-content/*`, `claude_plugins/fls-dev/commands/update_product_docs.md`, `docs/api.md`, `docs/how tos/custom-content-widgets.md`. Each doc points at either `demo_content` or an author's repo.
  - `freedom_ls/tests/demo_content_fixtures.py`: `save_content_to_db(settings.BASE_DIR / "demo_content", ...)`. That is inside the FLS repo, which is a git repo in dev but may be uncommitted/dirty during development, and the path is a subdirectory, not a repo root.
  - Tests that write content to `tmp_path` and call `save_content_to_db` directly (`test_content_save.py`: 132 `tmp_path|git|test uuid` matches, and the others listed in section 1). A tmp dir is not a git repo, and the `make_temp_file` tests write uuid-less files, so a clean-tree, origin-clear check would break all of them unless injected or bypassed.
  - QA helpers (`qa_create_*` under `freedom_ls/qa_helpers/management/commands/`) mention `content_save demo_content <site>` in docstrings/error messages, e.g. `qa_create_dev_org_baseline`, `qa_create_educator_interface_seed`. Several others contain the match (`qa_create_admonition_scenarios`, `qa_create_course_price_scenarios`, `qa_create_coming_soon_sections` and more). Which of them call the function rather than name it was not checked.
  - Also in the match list: `freedom_ls/dev_tools/tests/*`, `danger_clear_all_course_progress.py`, `import_contracts.toml` and baselines under `test_organisation/` (a module-boundary contract), `content_engine/admin.py`, `content_engine/schema.py`, `form_engine/schema.py` and `content_engine/validate.py` (mentions in comments).
  - No `create_demo_data`, shell script, Dockerfile or yml in the repo mentions `content_save` (grep of `create_demo_data*`, `*.sh`, `Dockerfile*`, `*.yml`, `.github/**` returned nothing).
- Dirty-tree collisions inside the pipeline: write-back of uuids modifies the content files, and `ImageCache.write_manifests()` writes manifests under `CACHE_DIR_NAME/` inside the content dir during the run (CS echoes "Commit them alongside the content change"). So a clean-tree check at start is the only point where "no uncommitted changes" can hold, and a run that generates uuids or cache entries leaves the tree dirty by design.
- `image_cache` and content paths are relative to the single `path`. Several paths mean a decision on how `file_path` values, `File.file_path` and `ImageCache(path)` are keyed per source (not checked in detail).

## 5. "retired" and neighbouring words

Glossary (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, "Words with an existing meaning" table):
- **retired**: used twice with a defined meaning, and cannot simply be taken for content. In the `is_active` row, "list entries retired from the pickers (`JobTitle`, `Department`, `Location`)" are the one exception to deactivating/inactive: those are **retired**. Another use is "Retired" as a note on old words (`OrganisationMember`, "suspend"). So "retired" already means "a list entry hidden from pickers, `is_active=False`" for three models.
- **is_active**: the house flag, with the rule "setting to False is deactivating, the state is Inactive". Content models have no `is_active`.
- **archived**, **version**, **revision**: no matches in the glossary skill. As model fields, grep of content/form/content_base models found no `version` or `revision` either. Not checked: other apps (`grep` was limited to the glossary and the four model dirs).
- **removed**: reserved for actually deleted rows. **visibility** is taken by `Course.visibility` and `Article.visibility` (published, coming soon): a content "retired" state is another axis from visibility.
- **paused_content / content_snapshots**: `spec_dd/0. paused/content_snapshots/0. idea.md` is referenced by the idea but not read in this unit.

## Implications for the cut (natural boundaries)

1. `--generate-uuids` (early fail, default False) is self-contained in CS and `validate.py`. It touches: the flag on `command` and `save_content_to_db`, the missing-uuid check across all nine kinds plus options and category entries, and the docs. The blast radius is tests that load uuid-less files (`test_content_save.py`, the `make_temp_file` helpers) and any demo_content item that lacks a uuid.
2. Debug-mode organisation creation is one function (`_resolve_organisations`) plus a debug test. It depends on a "debug mode" definition and on deriving a name from the slug. It is independent of the other items.
3. Multi-path plus single-source plus git check is a separate unit from retirement. It touches the `command` signature, `get_all_files`/`ImageCache`/`file_path` keying, and the dirty-tree interaction with uuid and image cache write-back. It is the largest blast radius for tests and the QA/demo flow.
4. Retired state is its own unit and needs a model-by-model decision: which models get the flag (the file-sourced list in section 3), what the load marks (a diff of what is in the DB for the site vs the files loaded in this run), and how learner-facing queries (`viewable_collection_items`, question serving, registrations) exclude retired rows. `ContentCollectionItem` pruning and `moved_children` interact with it: a left-behind row is today kept, not removed. Retire is the safe choice against the PROTECT / answer rows, and `danger_content_delete` stays the only deleter.
5. Question/option versioning is distinct from retiring and shares one precondition: `QuestionAnswer` stores only `question` and a M2M to options with no text snapshot, and `QuestionOption` rows are updated in place by uuid. Anything that records "which version they answered" needs a place to hold the answered text or a version row, and the load needs to detect a change on update (today `update_or_create` overwrites silently). It also needs a git hash source, where `base/git_utils.get_head_commit` reads one for the FLS repo only (not for an arbitrary content path).
6. The educator interface permission, audit logging and admin removal in the idea are separate from the content save pipeline and were not researched here.

status: ok
