---
name: reference-background-tasks-dev
description: Dev needs NO db_worker — settings_base pins django TASKS to ImmediateBackend, so report PDF rendering runs inline in the request
metadata:
  type: reference
---

QA plans for the reports app routinely say "start `db_worker`". In this project
that is a no-op in development:

- `config/settings_base.py` sets
  `TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}`.
- `config/settings_dev.py` does **not** override `TASKS`. Only
  `settings_prod.py` swaps in the durable DB-backed backend.
- Verified at runtime: `manage.py shell -c "print(settings.TASKS)"` under
  `config.settings_dev` returns the ImmediateBackend dict.

`freedom_ls/reports/views.py` calls `default_task_backend.enqueue(...)` (via a
`transaction.on_commit` lambda) into `reports/tasks.py`'s `@task()`. With
ImmediateBackend that executes synchronously during the request, so a
GeneratedReport is finished by the time the response returns.

`manage.py db_worker` DOES exist (from `django_tasks_db`, in INSTALLED_APPS),
but starting it in dev processes an empty queue. Report "no worker running,
none needed" rather than launching one.
