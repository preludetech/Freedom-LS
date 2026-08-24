---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS   # hard: add "freedom_ls.content_base" (before freedom_ls.content_engine)
  - INSTALLED_APPS   # hard: add "freedom_ls.form_engine" (after freedom_ls.content_engine)
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: extract_forms_into_seperate_app

Forms now live in their own app. The form definition models, the attempt/marking layer, their admin,
factories, schema and helpers have moved out of `content_engine` and `learner_progress` into a new
`freedom_ls.form_engine`, and the shared abstract content bases plus the pydantic schema registry
have moved into a new `freedom_ls.content_base`.

**This is a structural refactor plus two bug fixes.** No URL paths change, no template files move, no
new user-facing functionality. What changes is import paths, app labels, database table names,
permission strings — and one behavioural substitution (a custom signal in place of a `post_save`
receiver).

**There are no compatibility shims and there will not be any.** Nothing re-exports `Form` from
`freedom_ls.content_engine.models`. The break is deliberately loud: every stale import raises
`ImportError` at startup. Two places where it is **silent** are called out under Breaking changes —
the form runner template override and the `KeyError` → `ValueError` contract change. Read those two
even if you skim the rest.

**Before you go further: this release cannot be migrated onto a database you intend to keep.**
Seven tables change name because their app label changed, and FLS ships **no** data migration for
that — see manual step 2.

## Breaking changes

### 1. Two new apps must be in `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    ...
    "freedom_ls.markdown_rendering",
    "freedom_ls.content_base",      # new — before content_engine
    "freedom_ls.content_engine",
    "freedom_ls.form_engine",       # new — after content_engine
    ...
]
```

No system check enforces this, because none is needed: Django raises at model-import time if
`form_engine` is missing, and `content_base`'s abstract bases cannot be imported without it. Both
failures happen at boot, not in production traffic. `content_base` owns zero tables and has no
`migrations/` directory at all.

### 2. Import paths

`content_engine` → `content_base` (abstract bases and the schema registry):

| Old | New |
| --- | --- |
| `from freedom_ls.content_engine.models import BaseContent, TitledContent, MarkdownContent` | `from freedom_ls.content_base.models import ...` |
| `from freedom_ls.content_engine.schema import ContentType, BaseBaseContentModel, BaseContentModel, MarkdownContentModel, SCHEMAS` | `from freedom_ls.content_base.schema import ...` |

`content_engine` → `form_engine` (form definition layer):

| Old | New |
| --- | --- |
| `freedom_ls.content_engine.models` → `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`, `QuestionType`, `FormStrategy`, `FREE_TEXT_QUESTION_TYPES` | `freedom_ls.form_engine.models` (the three enum names also live in `freedom_ls.form_engine.enums`, and are re-exported from `models`) |
| `freedom_ls.content_engine.schema` → `Form`, `FormPage`, `FormContent`, `FormQuestion`, `QuestionOption`, `QuestionType`, `FormStrategy` (pydantic) | `freedom_ls.form_engine.schema` |
| `freedom_ls.content_engine.factories` → `FormFactory`, `FormPageFactory`, `FormContentFactory`, `FormQuestionFactory`, `QuestionOptionFactory` | `freedom_ls.form_engine.factories` |
| `freedom_ls.content_engine.admin` → the form admin classes | `freedom_ls.form_engine.admin` |

`learner_progress` → `form_engine` (attempt and marking layer):

| Old | New |
| --- | --- |
| `freedom_ls.learner_progress.models` → `FormProgress`, `QuestionAnswer` | `freedom_ls.form_engine.models` |
| `freedom_ls.learner_progress.factories` → `FormProgressFactory`, `QuestionAnswerFactory` | `freedom_ls.form_engine.factories` |
| `freedom_ls.learner_progress.scoring` (whole module) | `freedom_ls.form_engine.scoring` |
| `freedom_ls.learner_progress.submissions` (whole module) | `freedom_ls.form_engine.submissions` |
| `freedom_ls.learner_progress.queries` → `attempt_completes_form`, `completed_form_ids_by_user` | `freedom_ls.form_engine.queries` |

`freedom_ls/learner_progress/queries.py` is **deleted**, not emptied — `learner_progress` has no
`queries` module any more.

`learner_interface` → `form_engine`:

| Old | New |
| --- | --- |
| `freedom_ls.learner_interface.utils` → `quiz_verdict`, `count_form_questions` | `freedom_ls.form_engine.queries` |

`freedom_ls/content_engine/models.py` is now a package (`models/courses.py`, `models/topics.py`,
`models/files.py`). Everything that stayed in `content_engine` is re-exported from
`models/__init__.py`, so `from freedom_ls.content_engine.models import Course` is unaffected.

### 3. App labels, table names and permission strings

Seven tables change name, purely because the name derives from the app label:

| Old table | New table |
| --- | --- |
| `freedom_ls_content_engine_form` | `freedom_ls_form_engine_form` |
| `freedom_ls_content_engine_formpage` | `freedom_ls_form_engine_formpage` |
| `freedom_ls_content_engine_formcontent` | `freedom_ls_form_engine_formcontent` |
| `freedom_ls_content_engine_formquestion` | `freedom_ls_form_engine_formquestion` |
| `freedom_ls_content_engine_questionoption` | `freedom_ls_form_engine_questionoption` |
| `freedom_ls_learner_progress_formprogress` | `freedom_ls_form_engine_formprogress` |
| `freedom_ls_learner_progress_questionanswer` | `freedom_ls_form_engine_questionanswer` |

Permission strings move with the label. Any `has_perm(...)`, `permission_required(...)`, group
fixture or role definition in your project that names one of these must be repointed:

- `freedom_ls_content_engine.{view,add,change,delete}_form` → `freedom_ls_form_engine.*`
- `freedom_ls_content_engine.{view,add,change,delete}_formcontent` → `freedom_ls_form_engine.*`
- `freedom_ls_content_engine.{view,add,change,delete}_questionoption` → `freedom_ls_form_engine.*`
- `freedom_ls_learner_progress.{view,add,change,delete}_formprogress` → `freedom_ls_form_engine.*`
- `freedom_ls_learner_progress.{view,add,change,delete}_questionanswer` → `freedom_ls_form_engine.*`

`*_contentcollectionitem` stays on `freedom_ls_content_engine`; `*_topicprogress` and
`*_courseprogress` stay on `freedom_ls_learner_progress`.

Admin URLs move with the label too: `/admin/freedom_ls_content_engine/form/` →
`/admin/freedom_ls_form_engine/form/`, and likewise for the other six models. Bookmarks and any
hardcoded admin links break.

Django `ContentType` rows for the seven models are recreated under the new app label on the rebuild.
`CohortDeadline` / `UserCohortDeadlineOverride` look up `Form` by content type, so a *stale*
content-type row would give a silent wrong answer — another reason step 2 is a rebuild, not a
migrate.

### 4. Course progress now reacts to a custom signal, not `post_save`

`learner_progress` used to recalculate course percentages from a `post_save` receiver on
`FormProgress`. It now listens for `form_attempt_completed`, a `django.dispatch.Signal` defined in
`freedom_ls.form_engine.signals` and sent by `FormProgress.complete()`:

```python
form_attempt_completed.send(sender=FormProgress, user=..., form=...)
```

Hook here if your project reacts to a learner finishing a form. A `post_save` receiver of your own
on `FormProgress` still fires as before — but it fires on every save, not only on completion, and
its sender import has moved (see §2).

### 5. `quiz_percentage()` raises `ValueError` where it used to raise `KeyError` — silent

`FormProgress.quiz_percentage()` now raises `ValueError` when `scores` holds no quiz-shaped result
(a form switched to `QUIZ` after it was sat, or a row written by hand), where it previously let a
`KeyError` escape. Every FLS caller guards on `ValueError`, which is why the old behaviour crashed
`recalculate_progress_percentages` and cohort report generation mid-run.

If your project catches `KeyError` around `quiz_percentage()`, `passed()` or `quiz_verdict()`, that
`except` arm is now dead and the `ValueError` will escape it. Catch `ValueError` instead. Nothing
raises to tell you — this one is silent.

### 6. What deliberately does NOT change

| Unchanged |
| --- |
| URL paths and URL names — `courses/<slug>/…`, the whole form runner route set |
| Template file paths — no template moves; one template's contents changed (see manual step 5) |
| `demo_content/` authoring format — front matter, field names and UUIDs are untouched |
| `content_save` / `danger_content_delete` command names and arguments |
| Model field names, model class names, `Form.strategy` values, scoring behaviour |
| `content_engine` itself — `Course`, `CoursePart`, `Topic`, `Activity`, `File`, `ContentCollectionItem` all stay put |

## Manual steps

1. **Add both apps to `INSTALLED_APPS`** — `freedom_ls.content_base` before `freedom_ls.content_engine`,
   `freedom_ls.form_engine` after it. See Breaking changes §1.

2. **Rebuild the database. Do not migrate a database you want to keep.** FLS ships ordinary
   `makemigrations` output: `content_engine` deletes five models, `learner_progress` deletes two, and
   `form_engine` creates all seven from scratch. Running that against a populated database **drops
   every form, page, question, option and learner attempt**. There is no data migration and none is
   planned — a cross-app model move cannot be expressed safely as one.

   ```bash
   # drop and recreate the database, then:
   uv run python manage.py migrate
   uv run python manage.py content_save        # re-import your content directory
   ```

   Authored form content survives, because it is file-backed and `content_save` writes UUIDs back
   into the source files — form, page, question and option identities are stable across the rebuild.
   **Learner attempt data (`FormProgress` / `QuestionAnswer`) does not survive.** If your project has
   attempt data you cannot lose, stop and take this up before upgrading.

3. **Find-and-replace the import paths** using the tables in Breaking changes §2. Then run
   `uv run python manage.py check` and your test suite — every remaining stale import raises
   `ImportError` at boot.

4. **Repoint any form permission strings** you grant, per Breaking changes §3, and fix any hardcoded
   `/admin/freedom_ls_content_engine/form…` links.

5. **If you override `learner_interface/course_form_page.html`, re-apply two changes to your copy.**
   The runner page form gained a hidden `page_number` field, and the "Leave and submit" button became
   a `type="submit"` button bound to that form via `form="runner-page-form"` with
   `formaction="{{ submit_and_exit_url }}"` and `formnovalidate`, replacing the separate `<form>` that
   used to wrap it:

   ```html
   <input type="hidden" name="page_number" value="{{ current_page_num }}">
   ...
   <c-button variant="primary" type="submit"
             form="runner-page-form"
             formaction="{{ submit_and_exit_url }}"
             formnovalidate
             data-testid="leave-and-submit-button">
       Leave and submit
   </c-button>
   ```

   **This failure is silent.** An override without these keeps rendering and submitting without error
   — it just discards the answers on the page the learner was standing on when they left a
   submit-on-exit form, and scores the attempt without them.

6. **If you override `learner_interface/static/learner_interface/js/alpine-components.js`**, port the
   guard added to the `examRunnerForm` submit handler:

   ```js
   if (event.submitter?.formNoValidate) return;
   ```

   Without it, the required-checkbox gate blocks "Leave and submit" and traps the learner in the exit
   dialog. Run `collectstatic` after upgrading either way.

No package upgrades, no npm installs and no Tailwind rebuild are needed for this release.
