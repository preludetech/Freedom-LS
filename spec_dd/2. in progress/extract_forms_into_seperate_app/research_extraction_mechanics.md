# Research: what the extraction actually costs

## Executive summary

**Five table renames, one hand-written content-type migration, one new abstract-only app, one
bundled-plugin re-sync, and a sequencing constraint against three in-flight specs.** None of it is
hard, and the database side is a non-issue: this lands **before**
`final_pre_deploy_db_structure_cleanup`, whose migration reset regenerates every `0001_initial`
afterwards, so there is no data to preserve, no backfill and no content-type surgery — only a code
break to document. The abstract-base question — which the prior research correctly
calls a must-resolve for any extraction proposal — is answered here by a small **`content_base`**
app that owns the bases and nothing else: abstract models mean zero tables and zero migrations, so
it carries no deadline, and it turns what would be a mutual `content_engine ↔ form_engine`
dependency into a DAG. The single-transaction importer stays whole in `content_engine` and imports
form models across the boundary; the pydantic registry moves to `content_base`, so neither app owns
the registry both register into. The migration hazard is specific and well-precedented:
`RenameContentType` fires only for `RenameModel` **within one app label**, so a cross-app move
silently orphans every row keyed on `django_content_type`, and the recipe for fixing that already
exists in this repo.

---

## 1. The abstract bases — answered explicitly

`Form` and `FormPage` extend `TitledContent`; `FormContent` extends `MarkdownContent`;
`FormQuestion` extends bare `BaseContent`; only `QuestionOption` is a plain `SiteAwareModel`
(`content_engine/models.py:421,456,485,503,552`). The bases live at `models.py:55-143` and also
serve `Topic`, `Activity`, `Course` and `CoursePart`.

The three options, restated from `research_forms_app_extraction.md` §2 with a decision:

| Option | Assessment |
|---|---|
| Move the bases down to `site_aware_models` | **No.** `site_aware_models` is 83 lines of site FK and UUID PK with zero authoring vocabulary. `file_path`, `meta`, `tags`, `slug`, markdown `content` are content-authoring concepts. This pollutes a clean foundational layer, and `Topic`/`Course` would import from the lower layer too — so it does not even localise the change. |
| Keep the bases in `content_engine`, import them from `form_engine` | **Workable, but not the best answer.** Costs one `form_engine → content_engine` edge which, alongside the loader's `content_engine → form_engine`, makes the two apps mutually dependent for no gain. |
| Duplicate the bases in `form_engine` | **No.** Contradicts CLAUDE.md's "avoid repeating code", and the two copies would drift. |
| Put the bases in the existing `base` app | **No, and this one is a trap.** `base` has no `models.py`, sits at the bottom of the graph with zero runtime deps, and `content_engine → base` already exists — so it looks ideal. But `BaseContent` extends `SiteAwareModel`, which adds `base → site_aware_models` against an existing `site_aware_models → base`. That is a real cycle, worse than the one being fixed. |
| **A new `content_base` app owning the bases and nothing else** | **Yes — recommended.** |

**Decision: a `content_base` app.** Both `content_engine` and `form_engine` depend on it; neither
depends on the other for bases.

**Why it is nearly free.** Abstract models produce no tables and no migrations, and Django does not
require an abstract model's module to be in an installed app at all — `ModelBase.__new__` raises the
"doesn't declare an explicit app_label" `RuntimeError` only for non-abstract models. Register it
anyway, with `apps.py` and `label = "freedom_ls_content_base"`, for two reasons: `panel_framework`
is existing precedent for an installed app with zero models, and `/ds:app_map` builds the graph from
"every directory containing an `apps.py`", so an unregistered package would be invisible in the one
document this change exists to improve.

**What it buys.**

- The graph becomes acyclic: `content_engine → content_base`, `form_engine → content_base`,
  `content_engine → form_engine`.
- It carries **no deadline**, so it can land ahead of the extraction and shrink the deadline-bound
  cut to concrete models only.
- It dissolves §2's registry dilemma outright (see below).

**What it does not buy, stated plainly.**

- It removes today's cycle; it does not prevent one. The loader edge stays, so any future
  `form_engine → content_engine` import re-creates the pair — `compliance-exam-remediation`'s
  "reference relevant content" is exactly that. A string FK reference
  (`"freedom_ls_content_engine.Topic"`) avoids the Python import, but `/ds:app_map` is ast-based, so
  such a dependency would be real and *invisible* — worse for graph honesty than a visible edge.
- The cycle it removes was never an `ImportError` risk. `content_engine/models.py` never imports
  form models; only `content_save.py` and `content_tags.py` do, lazily. The win is legibility and
  clearing `/fls-dev:plan_structure_review`, not a crash avoided.

**Naming: `content_base`, not `content_engine_base`.** Two apps depend on it; naming it after one of
them reads as "form_engine depends on content_engine", which is the confusion it exists to remove.

Two things to record rather than fix:

- **The bases are doing two jobs.** `BaseContent` mixes identity (`meta`, `tags`) with
  file-provenance (`file_path`), and `TitledContent` adds `slug`. A `FormPage` is not its own file
  and carries a `file_path` it does not need; a `FormQuestion` extends `BaseContent` purely for
  those three fields. If admin-authored forms ever land, the base should split into a file-backed
  half and a not-file-backed half. **Out of scope for the extraction**, and listed here so the plan
  does not quietly do it.
- **`calculate_path_from_root`** (`models.py:77-101`) lives on `BaseContent` and is used by
  `get_file_by_path`/`get_content_by_path` to resolve relative image references inside form pages.
  It travels with the base, so nothing breaks — but it is the concrete reason a form page needs
  `file_path` today.

---

## 2. The pydantic registry and the validator hook

One registry: `BaseBaseContentModel._registry` is populated by `__init_subclass__(content_type=...)`
(`schema.py:59-75`) and exported as `SCHEMAS = BaseContentModel._registry` (`schema.py:336`).
`validate.py:100` does `SCHEMAS.get(content_type)` on a single walk of the content tree.

One form-shaped hook in the generic parser: `parse_yaml_file` (`validate.py:187-191`) calls
`first_model.derive_content_type(data)`, and the only implementation is
`schema.FormPage.derive_content_type` (`schema.py:274-278`), which maps a YAML document to
`FORM_CONTENT` or `FORM_QUESTION` by whether it has `content:` or `question:`.

**Decision: the registry moves to `content_base`, and is not forked.** `BaseBaseContentModel`,
`BaseContentModel`, `MarkdownContentModel`, the `ContentType` `StrEnum` (`schema.py:13-23`) and
`_registry`/`SCHEMAS` go to `content_base/schema.py`. Course schema classes stay in
`content_engine/schema.py` and form schema classes move to `form_engine/schema.py`; both subclass
the shared bases and so register into one registry that neither app owns. `ContentType` keeps all
its members — splitting the enum buys nothing and breaks `validate.py`'s single lookup.
`FormPage.derive_content_type` travels with the form classes; `validate.py:187-191` already calls it
polymorphically off the registry, so no code there changes.

Make sure both schema modules are imported at app-ready time, or their content types silently vanish
from `SCHEMAS` (risk 2 below).

**Alternative if a structure review rejects the `content_engine → form_engine` edge:** a
settings-string content-type registry, the same idiom as `COURSE_ACCESS_CONFIG_VALIDATOR`
(`config/settings_base.py:428-436`), where `config` names the modules to import for registration and
`content_engine` never names `form_engine`. This is strictly more machinery; recommend the direct
import first and keep this in the back pocket.

---

## 3. The importer

`save_content_to_db` (`content_save.py:492-698`) is one `@transaction.atomic` linear pass:

1. `get_all_files` → `parse_single_file` for every `.md`/`.yaml`/`.yml`; everything else becomes a
   `File` row.
2. Group by `content_type` and save in fixed order: Topics → Activities → Courses → CourseParts →
   Forms → FormPages → FormContent/FormQuestion/QuestionOption → `ContentCollectionItem` children.
3. `save_with_uuid` (`content_save.py:193-271`) is the shared generic saver: pydantic `model_dump`,
   validate field names against `model_class._meta.get_fields()`, `get_unique_slug`,
   `update_or_create` by UUID, else create and **write the UUID back into the source file**.

Form-specific pieces: `save_form`/`save_form_page`/`save_form_content`/`save_form_question`
(`content_save.py:355-417`); `update_file_with_option_uuids` (`content_save.py:144-190`), which
back-writes `QuestionOption` UUIDs into the page YAML; the **directory-parent join**
(`content_save.py:546-603`), which indexes forms by directory (`forms_by_dir[file_path.parent]`) and
attaches pages by matching parent, with page order from the alphabetical filename sort; and the
collection auto-scan (`content_save.py:641-647`), where `FORM` is treated as a collection file
alongside `COURSE`/`COURSE_PART`.

**Decision: the loader stays whole in `content_engine` and imports the form models.** One
`content_engine → form_engine` edge, in exchange for one transaction, one `content_by_path` map and
one validation walk. Forking it into two coordinating importers that share a path map across an app
boundary is more coupling, not less — the prior research is right about that. Note this is the same
shape `application-forms/idea.md:68-74` already proposed for its own config models; the difference is
that it points at a shared primitive rather than at a consumer app.

`danger_content_delete.py` deletes all ten models in one list and needs the same import.

---

## 4. Migrations

### The renames

Nothing in `content_engine` sets `db_table`; names derive from
`label = "freedom_ls_content_engine"` (`content_engine/apps.py:7`). Five tables move:

```
freedom_ls_content_engine_form            -> freedom_ls_form_engine_form
freedom_ls_content_engine_formpage        -> freedom_ls_form_engine_formpage
freedom_ls_content_engine_formcontent     -> freedom_ls_form_engine_formcontent
freedom_ls_content_engine_formquestion    -> freedom_ls_form_engine_formquestion
freedom_ls_content_engine_questionoption  -> freedom_ls_form_engine_questionoption
```

Plus, if `FormProgress` and `QuestionAnswer` move as recommended, two more out of
`freedom_ls_learner_progress`, and the auto-generated M2M through table for
`QuestionAnswer.selected_options`.

### Why the hazard does not apply here

Ordinarily this is the expensive part, and it is worth stating so a future reader does not
re-discover it the hard way. Django's content-type fixing machinery
(`contenttypes.RenameContentType`) fires **only** for `migrations.RenameModel`, and only within one
app label. There is no `RenameApp` operation and no mechanism for cross-app moves. Stale
`django_content_type` rows are left in place while `create_contenttypes` inserts fresh ones
alongside them, silently orphaning:

- `ContentCollectionItem.child_type` / `collection_type` (`content_engine/models.py:400-404`) —
  this is what puts a `Form` inside a `Course`.
- `CourseProgress.last_accessed_content_type` (`learner_progress/models.py`).
- The three deadline models in `learner_management`, whose GenericFKs point at `Topic`/`Form`.
- `educator_interface/views.py:438` — `DjangoContentType.objects.get_for_model(Form)` for
  `CohortDeadline` / `UserCohortDeadlineOverride` lookups.
- guardian object permissions, `auth_permission`, `django_admin_log`,
  `ObjectRoleAssignment.content_type`.

Plus the second-order effect `learner-terminology-rename` documented:
`sync_role_permissions._ensure_permissions_exist` resolves permissions through the content type, so
against a stale table it **creates duplicates** rather than finding the existing rows. The GFK
*mechanism* keeps working across an app move — it is keyed by `(app_label, model)` — which is
exactly why stale rows are dangerous: nothing errors, the pointers just resolve to the wrong place
or to nothing.

**None of it applies to this extraction**, because the extraction lands *before*
`final_pre_deploy_db_structure_cleanup`:

- FLS's own databases are rebuilt from scratch (per-branch dev databases via `branch_to_db_name`).
- No downstream project has run `migrate` against a database it intends to keep.
- The reset that follows deletes every app's migrations and regenerates `0001_initial`, so the
  migration history this move creates is discarded anyway.

**So: no data migration, no backfill, no `django_content_type` surgery, no role re-sync.** Drop the
dev database, recreate it, `migrate`, and re-import `demo_content/`. Whatever `makemigrations`
emits for the move is throwaway — do not spend effort making it elegant.

Authored content survives a rebuild for free, because it is file-backed: `content_save` re-imports
`demo_content/` and `save_with_uuid` writes UUIDs back into the source files, so `Form`, `FormPage`,
`FormQuestion` and `QuestionOption` identities are stable across the drop. The only loss is learner
attempt data (`FormProgress`/`QuestionAnswer`), which exists in dev only.

### What still needs writing down

The break is real at the **code** level even though it is free at the data level: import paths, app
labels, table names, template paths and permission codenames all change, and downstream projects
referencing `freedom_ls.content_engine.models.Form` must edit their own code.

**Decided posture: loud break, no compatibility shims.** `upgrade_notes.md` is still required —
model it on `spec_dd/3. done/2026-08-22_15:42_learner-terminology-rename/upgrade_notes.md`, but only
its find-and-replace table and its `INSTALLED_APPS`/settings sections. **Its §9 and manual step 5
(the `django_content_type` / role-key recipe) have no analogue here and must not be copied in** —
carrying them across would tell downstream projects to perform surgery on a database that is about
to be reset anyway.

The one line that does need to be loud: *rebuild your database; do not try to migrate it.*

Current state for reference: `content_engine` has 15 migrations (including a `0010_` collision and a
merge migration); `learner_progress` has one; `course_applications` has one.

---

## 5. Everything else that has to move or re-sync

- **`claude_plugins/fls-content/validate/schema.py`** — a hand-patched bundled copy of
  `content_engine/schema.py` carrying every form pydantic model verbatim, with two documented
  course-only patches. Re-sync via `/fls-dev:update_claude_plugin_fls_content`. Its sibling docs
  (`skills/content-types/resources/form-files.md`, `skills/conventions/SKILL.md`,
  `skills/widget-reference/resources/c-content-link.md`) describe the form authoring contract and
  need review if any path or vocabulary changes. (`fls-content-plugin/` at the repo root contains
  only orphaned `__pycache__` — no source.)
- **Factories.** `content_engine/factories.py:71-132` moves. 20+ external test modules import course
  and form factories from the same module, so this is a wide but mechanical sweep, including
  `freedom_ls/conftest.py:204-212`'s `course_with_scored_quiz` fixture.
- **Tests.** `content_engine/tests/test_form_save.py` moves wholly; most of
  `test_content_save_save_with_uuid.py` (556 lines) moves; `test_content_save_course.py` stays but
  asserts on `Form` rows; `test_calculate_path_from_root.py` and `test_course_viewable_items.py` use
  `FormFactory` incidentally as a `BaseContent` carrier. In `learner_progress/tests/`,
  `test_scoring.py`, `test_form_progress_score_quiz.py`,
  `test_form_progress_score_category_value_sum.py`, `test_save_answers.py` and
  `test_quiz_free_text_questions.py` move; `test_course_progress.py` and `test_completion_signal.py`
  stay and need the signal rewiring.
- **`qa_helpers`** — roughly 16 management commands import `Form`, the form factories,
  `FormStrategy` or `QuestionType`.
- **`docs/app_structure.md`** — regenerate with `/ds:app_map`, and expect the plan to be gated by
  `/fls-dev:plan_structure_review`, which diffs new edges against the graph and inserts
  `> **Structure concern:**` callouts. Pre-declare the seven.
- **`docs/product/`** — `roadmap.md` currently says the authored application form is "not built";
  `learner-tracking.md` and `educator-interface.md` describe quiz results. Run
  `/fls-dev:update_product_docs`.
- **`upgrade_notes.md`** — required. Use `/fls-dev:update_upgrade_notes`; the structured
  front-matter fields (`requires_migrations`, `changed_settings`, `changed_template_paths`, …) are
  visible in any `spec_dd/3. done/*/upgrade_notes.md`.

---

## 6. Sequencing against other specs

**`content_snapshots` and `compliance-form-randomization` are paused until after deployment and are
out of scope.** Both touch this exact tree, and both were previously the strongest sequencing
constraint on this work; with them paused, the constraint is gone. This also voids two of the four
"queued work" objections in `research_forms_app_extraction.md` §4 — the claim that extraction makes
`content_snapshots` "strictly worse to implement" no longer bites, because that spec will be written
against whatever tree exists when it resumes.

What remains:

| Spec | Interaction |
|---|---|
| `final_pre_deploy_db_structure_cleanup` | **Runs after this.** Owns the migration reset (which is why §4 has no data recipe), the `models/` package split (prerequisite, step 1), and the `Won't do` entry this idea contradicts. Also relevant: its do-now finding 3 turns `FormProgress.form` and `QuestionAnswer.question` from CASCADE to PROTECT, and its do-later list includes a `FormProgress(user, form)` index — both land on models this extraction moves, so **reconcile the two documents before starting**, even though the ordering itself is settled. |
| `better_course_progress_tracking` | Re-keys `FormProgress` to the `ContentCollectionItem` placement rather than the bare `Form`. That is a *course-side* change to a form-side model, and it is the one live item affected by which app owns `FormProgress`. Check its current shape before committing to moving the attempt models; if it lands first the move is unchanged, but the FK it re-keys to lives in `content_engine`, adding a `form_engine → content_engine` pointer that `content_base` does not absorb. |
| `compliance-exam-remediation` (`1. next`, not started) | Wants a `FormQuestion` or per-option pointer at a `Topic`/`Activity` for "reference relevant content" — an ordinary FK today, a cross-app FK afterwards. Not a blocker; listed so it is not discovered mid-plan. |

---

## 7. New-app checklist (house convention)

From `freedom_ls/course_interest/` and `freedom_ls/course_applications/`, the two newest small apps:

- `apps.py` with `name = "freedom_ls.form_engine"` and **`label = "freedom_ls_form_engine"`**.
  `content_base` gets the same treatment (`label = "freedom_ls_content_base"`) but needs no
  `migrations/`, no `admin.py` and no `templates/` — abstract models only.
- `models.py` (or a `models/` package) — models extend `SiteAwareModel`, UUID PK.
- `admin.py` — `SiteAwareModelAdmin` from `freedom_ls.site_aware_models.admin`, `@admin.register`.
- `factories.py` — extend `SiteAwareFactory`; never set `site_id` manually.
- `urls.py` with `app_name = "form_engine"` — URL names snake_case, paths kebab-case. Only needed
  once form identity lands; `content_engine` itself has no `urls.py`.
- `queries.py` for query helpers factored out of views (a real convention here).
- `templates/form_engine/…`, partials under `templates/form_engine/partials/`.
- `tests/` package with `__init__.py`, `conftest.py`, and a `test_collection_safety.py` like
  `course_applications` has.
- `config.py` **only if** the app owns settings — it does not need one on day one.
- Register in `INSTALLED_APPS` (`config/settings_base.py:101-128`), placed with the content apps.
- No `signals.py` importing `Course`. The completion signal is defined in `form_engine` and
  subscribed to in `learner_progress`.

Commits go through `uv run git commit` (pre-commit hooks). Type hints on every function, no `Any`,
modern `X | None` syntax.

---

## 8. Risks and gotchas

1. **One edge still points from `content_engine` at `form_engine`** — the loader and
   `content_tags.get_content_by_path`. With `content_base` there is no return edge, so the graph is
   acyclic today; the risk is that a later change quietly restores the pair. Document the direction
   at both ends in the code, not just in the plan, and re-run `/ds:app_map` when form models grow a
   pointer back into `content_engine`.
2. **Registration timing for the pydantic classes.** If `form_engine/schema.py` is never imported,
   the form content types silently vanish from `SCHEMAS` and content validation starts skipping
   forms instead of failing. Add a test that asserts all four form members resolve through
   `SCHEMAS`.
3. **The ordering against `final_pre_deploy_db_structure_cleanup` is load-bearing, and nothing
   enforces it.** Everything in §4 assumes the reset runs afterwards. If that order ever slips — the
   reset lands first, or a downstream project migrates a database it keeps before this ships — the
   full `django_content_type` recipe comes back, and its failure mode is silent: nothing errors,
   deadlines and collection items just stop resolving. State the dependency at the top of the spec,
   not only here.
4. **`compliance-exam-remediation` points a form field back at `content_engine`.** "Reference
   relevant content" means a `FormQuestion` or per-option FK to a `Topic`/`Activity`. Ordinary
   Django, but it is a second upward pointer and should be listed, not discovered.
5. **The extraction alone unlocks nothing.** If the identity and authorisation seam never follows,
   the outcome is five renamed tables, seven new edges and exactly the same set of capabilities.
   This risk grows now that the database cost has gone: a change that looks free is easy to ship and
   then leave stranded. Any plan for this should state the follow-on explicitly.
6. **`Topic.preview_url()` is already broken** (`models.py:155` reverses
   `content_engine:topic_detail`, but `content_engine` has no `urls.py` and nothing includes one).
   Do not copy that pattern when adding `Form.preview_url()`; fix or delete it while in the area.

status: ok
