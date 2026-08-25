---
name: reference-form-engine-app-move-db-repair
description: Migrating a populated dev DB across the content_engine -> form_engine app move without losing form data, and the dangling-ContentType breakage it leaves behind
metadata:
  type: reference
---

A dev DB created before the form_engine extraction landed cannot just be
`migrate`d: the branch ships **no data migration**, so applying it as-is drops
every Form/FormPage/FormContent/FormQuestion/QuestionOption and orphans every
FormProgress/QuestionAnswer. Symptom before migrating:
`ProgrammingError: relation "freedom_ls_form_engine_form" does not exist`
from any qa_ command that touches a quiz. Symptom mid-way:
`IntegrityError ... form_id ... is not present in table
"freedom_ls_form_engine_form"` while applying `learner_progress.0002`.

The old and new tables have **identical column sets**, so the data can be
carried across by hand. Do it with Django's historical model state (the old
models no longer exist in code) rather than raw SQL:

```python
from django.db.migrations.executor import MigrationExecutor
old_apps = MigrationExecutor(connection).loader.project_state(
    ("freedom_ls_content_engine", "0014_course_table_of_contents_in_development")
).apps
OldForm = old_apps.get_model("freedom_ls_content_engine", "Form")
```

Order that works (each `migrate` step is its own command):

1. Copy definitions Form -> FormPage -> FormContent -> FormQuestion ->
   QuestionOption into `freedom_ls.form_engine.models` via
   `NewModel._base_manager.bulk_create`, preserving pks.
2. `manage.py migrate freedom_ls_learner_progress 0002` (FK repoint; now finds
   its targets).
3. `manage.py migrate freedom_ls_form_engine` (creates the new progress tables).
4. Copy FormProgress / QuestionAnswer / the `selected_options` through rows
   (`QuestionAnswer.selected_options.through`) across.
5. `manage.py migrate` (drops the old tables).

**Freeze auto timestamps around step 4.** `bulk_create` runs `pre_save`, so
`start_time` (auto_now_add) and `last_updated_time` (auto_now) get stamped with
`now()` and the backdating every at-risk fixture depends on is destroyed. Flip
`field.auto_now = field.auto_now_add = False` on the concrete fields for the
duration.

## The dangling ContentType — the part that is easy to miss

Moving a model between apps changes its ContentType. Django auto-creates the
`freedom_ls_form_engine` rows and **leaves the `freedom_ls_content_engine` ones
behind**, and nothing rewrites the GenericFKs already pointing at them. Every
`ContentCollectionItem.child_type` for a quiz still points at a ContentType
whose `model_class()` is now `None`, so `Course.children()` raises

    AttributeError: 'NoneType' object has no attribute '_base_manager'

i.e. **every course containing a quiz is broken in the browser too**, not just
in the QA commands. Fixed by
`manage.py qa_repair_form_engine_content_types` (in qa_helpers): it repoints
`child_type` / `collection_type` onto the form_engine ContentTypes. Idempotent.
It deliberately leaves the stale ContentType and Permission rows alone (they
were held by no user or group; deleting them is a separate decision).

Scan for other holders before assuming ContentCollectionItem is the only one:
iterate `apps.get_models()` for FKs to ContentType and count rows pointing at
the old ct ids. On the report-branding DB only `auth.Permission` (20 unheld
rows) and `ContentCollectionItem` (30 rows) referenced them.
