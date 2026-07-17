---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings: [TASKS, DATABASE_TASKS, INSTALLED_APPS]
requires_package_upgrade: true
changed_packages: ["django-tasks-db==0.12.0"]
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: production defaults to a durable database-backed task backend

Production now defaults to a durable, database-backed task backend
(`django-tasks-db`'s `DatabaseBackend`, ORM on PostgreSQL — no Celery/Redis) instead of the
synchronous `ImmediateBackend`. Background work (today, webhook dispatch) is enqueued to the
database and executed out-of-process by a worker, at-least-once.

Dev and the test suite are unchanged — base settings keep `ImmediateBackend`, so tasks still run
inline with no worker.

## Breaking changes

- **A worker process is now required in production.** With the durable backend as the production
  default, an enqueued task sits in the database until `python manage.py db_worker` picks it up.
  If no worker runs, background work (currently webhook delivery) is accepted but **never
  executes**. This is the shipped default, not opt-in.
- **New unique constraint on `WebhookDelivery(event, endpoint)`.** The constraint migration
  (`webhooks/0010_webhookdelivery_uniq_delivery_event_endpoint`) fails to apply if your database
  already holds historical rows that duplicate `(event, endpoint)`. Fresh/dev databases are fine;
  a live database with duplicates needs a one-off dedupe **before** running the migration.

## Manual steps

- **Install the new dependency.** `django-tasks-db==0.12.0` (exact pin — note it is
  `django-tasks-db`, not `django-tasks`) is added to `pyproject.toml`/`uv.lock`. Run `uv sync` so
  it is installed.
- **Run migrations.** `uv run manage.py migrate` — this applies both the `django_tasks_db` tables
  and the new `webhooks` unique constraint. Dedupe historical `WebhookDelivery` rows first if the
  constraint fails to apply (see Breaking changes).
- **Register the backend app.** If you maintain your own `INSTALLED_APPS`, add `"django_tasks_db"`
  (it ships its own migrations, tables, and admin; tasks become inspectable in the Django admin).
- **Point production at the durable backend.** If you maintain your own production settings layer,
  assign `TASKS = fls_defaults.DATABASE_TASKS` (from `freedom_ls.deployment.settings_defaults`).
  Keep the Django-default on-commit enqueue — do **not** set `ENQUEUE_ON_COMMIT=False`, or the
  worker will read the `WebhookEvent` row before it is committed and drop the event.
- **Run the worker as its own long-lived process/container** — `python manage.py db_worker`. Never
  run it via the `DEBUG` autoreload path in production. The worker container ships enabled by
  default in the deployment template repo.
- **Schedule the retention job.** Run `prune_db_task_results` on a schedule (cron or equivalent).
  The task-results table grows without bound otherwise and becomes a disk problem on a small VPS.
