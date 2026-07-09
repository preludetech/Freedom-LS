# Research: Django Tasks durable backend — package naming (`django-tasks` vs `django-tasks-db`)

## Summary / recommendation

**The idea already names the correct package.** `django-tasks-db` (PyPI: `django-tasks-db`,
`INSTALLED_APPS` entry `django_tasks_db`, backend path `django_tasks_db.DatabaseBackend`) is a
real, currently-maintained package that does exactly what P0(3)/P1(6) describe: a Postgres-backed
(via Django's ORM, no Redis/Celery/broker service), admin-visible, opt-in `TASKS` backend for
Django's built-in Tasks framework, with a `db_worker` management command for the out-of-process
worker.

**Do not substitute Jake Howard's `django-tasks` package for it.** `django-tasks` (PyPI:
`django-tasks`, maintainer RealOrangeOne / Jake Howard) is the reference implementation that
Django 6's core `django.tasks` was merged from, and it remains maintained as a *backport* for
Django <6 plus a "playground" for features not yet stable enough for core — but **as of its own
`0.12.0` release it no longer ships a `DatabaseBackend` or `db_worker` command itself**. That
functionality was extracted into the separate `django-tasks-db` package at the same `0.12.0` cut.
So "install `django-tasks` to get the durable backend" is no longer true; you must install
`django-tasks-db`.

One nuance worth recording (resolved, not a blocker): `django-tasks-db`'s backend module is
implemented against the third-party `django_tasks` package's own base classes (it depends on
`django-tasks>=0.12.0` as a library), but it ships a `compat.py` that explicitly also recognizes
Django core's `django.tasks.base.Task` alongside the third-party one — i.e. it was deliberately
built to work as a `TASKS` backend for Django 6 **core**'s `django.tasks`, not only for the
separate `django_tasks` app. This matches FLS's actual code: `freedom_ls/webhooks/events.py`
already does `from django.tasks import default_task_backend, task` (core), and
`config/settings_base.py` has `"django.tasks"` (core, with the dot) in `INSTALLED_APPS` — not the
third-party `"django_tasks"`. Flipping `TASKS.default.BACKEND` to `"django_tasks_db.DatabaseBackend"`
and adding `"django_tasks_db"` to `INSTALLED_APPS` should therefore work as a pure settings change
against the existing `django.tasks`-based webhook code, as the idea claims — no code port. This is
corroborated by a named third-party production user (see below) running exactly this combination
(Django 6 core `django.tasks` `@task` decorator + `django_tasks_db` backend) for ~6 months.

**One flag for the human:** `django-tasks-db` is young as a *standalone* package — PyPI shows a
single release, `0.12.0` (2026-02-06); before that the code lived inside `django-tasks` itself.
This is a real, if recent, extraction by a credible maintainer (Jake Howard is the DEP‑14 author
and a Django Software Foundation member-of-the-month), not a fly-by-night fork — but it supports
the idea's own framing of "opt-in importable primitive a project turns on," not "shipped default."
Recommend pinning the exact version in `pyproject.toml` (not `>=`) given the single-release
history, and re-checking for point releases before recommending it as a template default.

## Evidence

### 1. Jake Howard's `django-tasks` package — what it is today

- PyPI: `django-tasks` — current description: "A backport of Django's built in Tasks framework."
  Classifiers show explicit support for Django 5.2 and 6.0; Python ≥3.10;
  `Development Status :: 5 - Production/Stable`.
- GitHub: `RealOrangeOne/django-tasks` — same description. Its own README states: "Prior to
  `0.12.0`, `django-tasks-db` and `django-tasks-rq` were also included to provide database and RQ
  based backends" — confirming the split happened at `0.12.0` and both backends were spun out into
  their own repos/packages (`django-tasks-db`, `django-tasks-rq`).
- As of `0.12.0`, `django-tasks` ships only `DummyBackend` and `ImmediateBackend` — the same two
  backends Django 6 core ships. There is **no `DatabaseBackend` and no `db_worker` command left in
  this package**.
- Its `__init__.py` shows it is a **fully independent implementation**, not a thin re-export of
  Django core: it defines its own `TaskBackendHandler` reading `settings.TASKS`, its own
  `Task`/`TaskResult`/`TaskContext` classes, and its own `task` decorator, all under the
  `django_tasks` (underscore) namespace, entirely separate from Django core's `django.tasks`
  (dotted) namespace. Its own `INSTALLED_APPS` entry is `"django_tasks"`, distinct from Django
  core's `"django.tasks"` entry.
- Its maintainer states the package's forward purpose explicitly (Jake Howard's blog,
  "django.tasks exists"): the package continues to exist because Django 6 core doesn't
  retire the need for pre-6.0 support, and because it "acts as a playground — a place to develop
  and launch features without needing to go through Django's review process" before those features
  are proposed for core. He is explicit that the database backend was, at that point, **not yet
  stable enough for core**: *"The database backend will absolutely come in time — it just needs
  more features and finishing touches before it's stable enough for the likes of Django itself."*
- **Conclusion for Q1:** yes, `django-tasks` was and is closely related to Django 6 core (it's the
  literal source DEP‑14 implementation Django 6 merged), and yes it is still maintained — but it no
  longer ships the durable backend or worker command. Installing `django-tasks` alongside Django 6
  today would **not** get you a durable backend; it would only get you a parallel, separate
  Immediate/Dummy-only task framework duplicating what core already provides. It is the wrong
  package to name for this purpose.

### 2. `django-tasks-db` — does it exist, is it real/maintained/production-viable?

- **PyPI**: `django-tasks-db` exists. Latest (and, as of this research, only listed) version is
  **0.12.0**, released **2026-02-06**. Summary: "An ORM-based backend for Django Tasks." Declared
  support: Django 4.2, 5.0, 5.1, 5.2, 6.0; Python ≥3.10 (up to 3.14 per classifiers); license
  BSD‑3‑Clause; author/maintainer **Jake Howard (TheOrangeOne / RealOrangeOne)** — the same person
  who wrote DEP‑14 and the `django-tasks` backport, and a listed DSF member of the month
  (2025-08). This is not an unrelated/unknown maintainer.
- **GitHub**: `RealOrangeOne/django-tasks-db`. Package layout is a standard Django app:
  `apps.py`, `models.py`, `admin.py`, `backend.py`, `signal_handlers.py`, `compat.py`, `utils.py`,
  a `migrations/` directory, and a `management/commands/` directory (containing at least
  `db_worker` and `prune_db_task_results`). 106 watchers/stargazers, 16 forks, ~198 commits at time
  of research — an active repo, not abandoned, though (per djangopackages.org) only "1 total
  release" is recorded there, consistent with the PyPI history.
- **Dependencies** (`pyproject.toml`): `Django>=5.2`, `django-tasks>=0.12.0`, `typing_extensions`,
  `django-stubs-ext`; optional extras for `mysql` (`mysqlclient`) and `postgres`
  (`psycopg[binary]`). So Postgres is a first-class supported target (matches FLS's stack), and
  `django-tasks` is pulled in transitively as a library dependency (see compatibility note above) —
  a project does **not** need to add `django_tasks` (third-party) to its own `INSTALLED_APPS` or
  import from it; only `django_tasks_db` needs to be added.
- **Production evidence**: a third-party production write-up (the same blog post the idea already
  cites, Better Simple, 2026-05-06, "Using Django Tasks in production") documents the Djangonaut
  Space website running Django 6 core's `django.tasks` `@task()` decorator together with
  `django_tasks_db` in `INSTALLED_APPS` and `TASKS = {"default": {"BACKEND":
  "django_tasks_db.DatabaseBackend"}}`, stating: *"The Djangonaut Space website has been using the
  Django Tasks framework and django-tasks-db in production successfully for about six months
  now."* The post's worker invocation is `python3 manage.py db_worker` (equivalently `python3 -m
  manage db_worker` in the post's exact phrasing). It also explicitly cites the admin-visibility
  benefit: *"with the database backend, you can monitor the progress of your tasks in the admin.
  You can see which tasks are scheduled, completed, and have errored."*
- **Conclusion for Q2:** real, on PyPI, actively maintained by a credible/central maintainer in
  this exact ecosystem, with at least one documented real-world production user running it
  against Django 6 core's task framework (not just the third-party backport) for roughly half a
  year. It is young as an independently-versioned package (single release so far) but is not
  vaporware or an unmaintained fork.

### 3. Which is the correct importable primitive for FLS?

**`django-tasks-db` is correct; the idea should keep this name, not switch to `django-tasks`.**
`django-tasks` (Jake Howard's backport/reference package) is the wrong recommendation for this use
case: since the `0.12.0` split it has no `DatabaseBackend` and no `db_worker` command at all, and
adopting it on Django 6 would mean running a second, redundant, Immediate/Dummy-only task
framework alongside Django's own core one — no durable backend gained, and a confusing dual
`django.tasks` (core) / `django_tasks` (third party) coexistence for no benefit. `django-tasks-db`
is the package that actually contains the durable, Postgres-backed backend and worker, is designed
to (and per the production blog post, does) interoperate with Django 6 core's `django.tasks`, and
is what the idea already names in its P0(3) settings snippet.

### 4. Worker command, broker requirement

- Command: **`db_worker`** (a `manage.py` management command shipped inside `django_tasks_db`'s
  `management/commands/` directory), not `worker`. Confirmed identically across the PyPI page, the
  GitHub README, and the third-party production blog post.
- It runs against whatever database Django's `DATABASES["default"]` points at via the ORM — for
  FLS that's the existing Postgres instance. **No separate broker service** (no Redis, no
  RabbitMQ, no Celery) is required; the worker is a long-running Python process polling/consuming
  from the database. This matches the idea's "Postgres as broker, no Redis/Celery" framing.
- The README documents Django's `runserver`-style autoreload applying to the worker in `DEBUG`
  mode, with an explicit warning that this is **not recommended in production** because tasks may
  not be stopped cleanly on reload — worth calling out in FLS's own docs/worker-container
  guidance (P3) so operators don't run the dev-reload path in the shipped `worker` container.

### 5. Admin visibility

Confirmed at the code level (the package ships `admin.py` alongside `models.py`) and confirmed by
the third-party production account quoted above: tasks are visible in Django admin as
scheduled/completed/errored. This holds for `django-tasks-db` specifically (not something the idea
is inferring from a different package).

### 6. Migrations / tables / small-VPS gotchas

- `django_tasks_db` is a full Django app with its own `migrations/` directory — adding it to
  `INSTALLED_APPS` and running `manage.py migrate` creates its own results/task tables. This needs
  to be an explicit step in FLS's upgrade docs (P1(6)) — "flip `TASKS`" alone is insufficient;
  `INSTALLED_APPS` + `migrate` are also required.
- The package ships a **`prune_db_task_results`** management command for retention/cleanup of
  completed task rows. On a small single VPS with a small Postgres volume, this should be wired
  into a periodic job (cron, or the worker's own scheduler) — otherwise the task-results table
  grows unbounded, mirroring the same "unbounded growth on a small VPS" risk class the idea already
  flags for logs (P0(2)/P3 log caps). Worth calling out alongside the P3 "worker container
  present-but-disabled" scaffolding.
- The worker is a separate long-running process (matches the idea's "worker container present but
  disabled by default" plan) — it must not be run via the `DEBUG` autoreload path in production
  (see above).
- `django-tasks-db` declares Postgres support via an optional `postgres` extra
  (`psycopg[binary]`) — FLS already depends on `psycopg`/postgres, so this is additive, not a new
  driver dependency class, but confirm the extras marker is actually pulled in
  (`django-tasks-db[postgres]` vs relying on FLS's existing `psycopg` install) when wiring the
  `pyproject.toml` dependency.

### 7. Is "importable opt-in primitive, not shipped default" technically sound given maturity?

Yes — this is the right call given the evidence, not overcaution. Signals supporting "opt-in, not
default":
- The package is genuinely young as an independently versioned artifact: **one PyPI release**
  (`0.12.0`, 2026-02-06) as of this research, having only just been extracted from `django-tasks`.
- Its own author's public framing (pre-split) was that the database backend "needs more features
  and finishing touches before it's stable enough for the likes of Django itself" — i.e. even the
  maintainer did not consider it core-quality at the time of extraction.
- Real production mileage exists (~6 months per one named adopter) but is a single documented
  case, not broad ecosystem validation yet.

Signals against treating this as disqualifying:
- The maintainer is about as credible as it gets for this specific problem domain (DEP‑14 author,
  the person Django 6's own Tasks framework was sourced from).
- The package is a straightforward, standard-shape Django app (models/migrations/admin/management
  command) with no exotic runtime dependencies, low architectural risk if it needs to be swapped
  later (it's isolated behind the `TASKS` setting).

Net: naming it as FLS's **recommended opt-in upgrade path**, documented and scaffolded but not
defaulted-on, and pinning an exact version rather than a floating `>=`, is the appropriate level of
caution for a package with this maturity profile. This matches exactly what the idea already
proposes in P0(3)/P1(6) — no change of recommendation needed there.

## Open questions for the human to decide

1. **Version pinning policy.** Given the single-release history, should FLS's template/`pyproject.toml`
   pin `django-tasks-db` to an exact version (`==0.12.0`) rather than a floating constraint, and
   who re-verifies compatibility on each Django point release?
2. **`compat.py` behavior under future Django releases.** The compatibility shim
   (`django_tasks_db/compat.py`) hardcodes recognition of both `django.tasks.base.Task` (core) and
   `django_tasks.base.Task` (third party) via a `try/except ImportError`. This is sound today but
   is exactly the kind of shim that can silently stop covering a case if Django's internal
   `django.tasks.base` module path is refactored in a later Django release — worth a
   compatibility-check note in FLS's own upgrade-Django-version checklist.
3. **Does FLS need `django-tasks` (third party) in `INSTALLED_APPS` at all?** Current evidence
   (README + dependency graph) says no — only `django_tasks_db` needs to be in `INSTALLED_APPS`;
   `django-tasks` is a transitive library dependency used internally by `django_tasks_db`'s
   `backend.py`/`compat.py`. Worth a smoke test against a real FLS checkout before this ships,
   since this research is based on documentation/source reading, not an actual `pip install` +
   `migrate` + `db_worker` run in this repo.
4. **Retention/pruning cadence** for `prune_db_task_results` on the target small VPS — not
   specified anywhere in upstream docs found during this research; FLS will need to pick a default
   (e.g. daily cron, N-day retention) as part of the P3 worker-container scaffolding.

## References

- [django-tasks-db on PyPI](https://pypi.org/project/django-tasks-db/)
- [django-tasks-db on GitHub (RealOrangeOne/django-tasks-db)](https://github.com/RealOrangeOne/django-tasks-db)
- [django-tasks-db `backend.py` (raw source)](https://raw.githubusercontent.com/RealOrangeOne/django-tasks-db/master/django_tasks_db/backend.py)
- [django-tasks-db `compat.py` (raw source)](https://raw.githubusercontent.com/RealOrangeOne/django-tasks-db/master/django_tasks_db/compat.py)
- [django-tasks-db `pyproject.toml`](https://github.com/RealOrangeOne/django-tasks-db/blob/master/pyproject.toml)
- [django-tasks-db on djangopackages.org](https://djangopackages.org/packages/p/django-tasks-db/)
- [django-tasks on PyPI](https://pypi.org/project/django-tasks/)
- [django-tasks on GitHub (RealOrangeOne/django-tasks)](https://github.com/RealOrangeOne/django-tasks)
- [django-tasks `__init__.py` (raw source)](https://raw.githubusercontent.com/RealOrangeOne/django-tasks/master/django_tasks/__init__.py)
- [django-tasks `pyproject.toml`](https://github.com/RealOrangeOne/django-tasks/blob/master/pyproject.toml)
- [Jake Howard, "django.tasks exists" (TheOrangeOne blog)](https://theorangeone.net/posts/django-dot-tasks-exists/)
- [Better Simple, "Using Django Tasks in production" (2026-05-06) — cited by the idea document](https://www.better-simple.com/django/2026/05/06/using-django-tasks-in-production/)
- [Django 6.0 Tasks framework documentation](https://docs.djangoproject.com/en/6.0/topics/tasks/)
- [DSF member of the month — Jake Howard](https://www.djangoproject.com/weblog/2025/aug/03/dsf-member-of-the-month-jake-howard/)
- [DEP 0014: Background Workers — Django weblog](https://www.djangoproject.com/weblog/2024/may/29/django-enhancement-proposal-14-background-workers/)
- Repo files read for grounding: `config/settings_prod.py`, `config/settings_base.py`,
  `freedom_ls/webhooks/events.py`,
  `spec_dd/2. in progress/support-concrete-project-deployment/idea.md`

status: ok
