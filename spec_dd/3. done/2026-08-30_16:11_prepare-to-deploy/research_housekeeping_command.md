# Research: satisfying `COMPOSE-8`'s `run_housekeeping` properties

Scope: the eight properties bound on `run_housekeeping` in
`/home/sheena/workspace/first_class/infrastructure/docs/app_repo_contract/compose.md`
(`COMPOSE-8`, "housekeeping" subsection). Per the idea's decisions, FLS ships its own
full housekeeping command under an FLS-owned name (distinct from `run_housekeeping`,
which is the downstream's wrapper), and FLS does not do the Sentry cron-monitor
check-in — only error reporting via `sentry_sdk.capture_exception`.

## 1. `prune_db_task_results` internals

Source: `.venv/lib/python3.13/site-packages/django_tasks_db/management/commands/prune_db_task_results.py`.
It is a plain `BaseCommand` (not djclick).

Argument surface (`prune_db_task_results.py:42-76`):

- `--backend` (optional, default `DEFAULT_TASK_BACKEND_ALIAS` = `"default"`). Validated by
  `valid_backend_name`, which resolves it through `task_backends[val]` and rejects any
  backend that is not a `DatabaseBackend` (`prune_db_task_results.py:22-29`). FLS has exactly
  one task backend, aliased `"default"`, backed by `django_tasks_db.DatabaseBackend`
  (`freedom_ls/deployment/settings_defaults.py:49-51`, `DATABASE_TASKS`), so the default is
  already correct for FLS and this flag never needs to be passed.
- `--queue-name` (optional, default `DEFAULT_TASK_QUEUE_NAME` = `"default"`). Accepts a
  comma-separated list of queue names, **or the literal string `"*"` to mean every queue**
  (`prune_db_task_results.py:51-57`, `111-115`). This is the exact value COMPOSE-8's first
  bullet calls out: passing `--queue-name=*` is what makes the sweep prune results on every
  queue rather than only `default`.
- `--min-age-days` (optional, default `14`). Minimum age, in days, of a **successful** result
  before it is prunable (or of any finished result, if `--failed-min-age-days` is not given).
- `--failed-min-age-days` (optional, default `None`, meaning "same as `--min-age-days`").
  When set, failed results get their own retention window, independent of successful ones
  (`prune_db_task_results.py:105-123`).
- `--dry-run` (flag). Counts matching rows and logs the count instead of deleting
  (`prune_db_task_results.py:125-129`).

What "finished" means to it: it starts from `DBTaskResult.objects.finished()`
(`prune_db_task_results.py:111`), which is the union of `successful()` and `failed()`
(`django_tasks_db/models.py:81-82`) — i.e. status `SUCCESSFUL` or `FAILED` only. `READY` and
`RUNNING` rows are never touched by this command regardless of age.

The age filter it actually applies (`prune_db_task_results.py:117-123`):

```python
if failed_min_age is None:
    results = results.filter(finished_at__lte=min_age)
else:
    results = results.filter(
        Q(status=TaskResultStatus.SUCCESSFUL, finished_at__lte=min_age)
        | Q(status=TaskResultStatus.FAILED, finished_at__lte=failed_min_age)
    )
```

`finished_at` is set by `DBTaskResult.set_successful()` / `set_failed()`
(`django_tasks_db/models.py:229-263`), so it is always populated on a `finished()` row.

## 2. `DBTaskResult` schema — statuses, and detecting a late unpicked task

Source: `.venv/lib/python3.13/site-packages/django_tasks_db/models.py`.

**(a) Finished/prunable statuses.** `TaskResultStatus` (imported from the separate
`django_tasks` package, `.venv/lib/python3.13/site-packages/django_tasks/base.py:50-61`) has
four values: `READY`, `RUNNING`, `FAILED`, `SUCCESSFUL`. There is no `SCHEDULED` status —
"scheduled but not yet due" is represented as `READY` with a future `run_after`, not as a
separate state. `finished()` = `FAILED | SUCCESSFUL` (`models.py:75-82`); that is exactly
what `prune_db_task_results` prunes and matches the contract's "finished task results."

**(b) Detecting a late, unpicked task.** The relevant fields are:

- `status` — `models.py:95-100`.
- `run_after` — `models.py:118`. **Not nullable.** When a task is enqueued without an
  explicit `run_after` (the ordinary, non-scheduled case), `Task.run_after` is `None`
  (`.venv/lib/python3.13/site-packages/django_tasks/base.py:82`), and a `pre_save` signal
  handler substitutes the sentinel `get_date_max()` (year 9999) before the row is saved:
  `django_tasks_db/signal_handlers.py:9-12`, using `django_tasks_db/models.py:55-58`'s
  `get_date_max()`. So `run_after == get_date_max()` means "no schedule — run as soon as
  a worker polls it"; any other value of `run_after` is a genuine scheduled time.
- `enqueued_at` — `models.py:102`, `auto_now_add=True`. Set once, at creation, for every row
  (scheduled or not).
- `backend_name`, `queue_name` — for scoping the check the same way the worker/prune commands
  do, if that scoping is wanted.

`django_tasks_db`'s own `ready()` queryset (`models.py:62-70`) shows the shape the worker
itself uses to pick up work:

```python
def ready(self) -> "DBTaskResultQuerySet":
    return self.filter(status=TaskResultStatus.READY).filter(
        Q(run_after=get_date_max()) | Q(run_after__lte=timezone.now())
    )
```

A task is "due" the moment it satisfies that filter. To ask "has a due task sat unpicked for
more than an hour," the housekeeping sweep needs the same due condition but anchored an hour
in the past, and — because the sentinel `get_date_max()` is not itself a real "due since"
timestamp — it has to fork on which branch of the `Q` a row is in:

```python
one_hour_ago = timezone.now() - timedelta(hours=1)
late_unpicked = DBTaskResult.objects.filter(status=TaskResultStatus.READY).filter(
    Q(run_after=get_date_max(), enqueued_at__lte=one_hour_ago)
    | Q(run_after__lt=get_date_max(), run_after__lte=one_hour_ago)
)
```

- First branch: an un-scheduled (immediate) task is "due since" the moment it was enqueued,
  so lateness is measured from `enqueued_at`.
- Second branch: a scheduled task (`run_after` a real, non-sentinel datetime) is "due since"
  its `run_after`, so lateness is measured from `run_after` itself, and a `run_after` still in
  the future never matches `run_after__lte=one_hour_ago` — which is exactly how "a scheduled
  task not yet due is not late" (COMPOSE-8) falls out for free rather than needing a special
  case.

Nothing in `django_tasks_db` ships this query as a reusable method; the two-branch `Q` above
is a query the housekeeping command would have to build itself against `DBTaskResult` (or
`django.tasks`'s public queryset, if one is exposed) — this file only reports the fields and
shape, not an implementation.

## 3. `clearsessions` and FLS's session backend

Django's built-in `clearsessions` (`.venv/lib/python3.13/site-packages/django/contrib/sessions/management/commands/clearsessions.py`)
does exactly one thing: `import_module(settings.SESSION_ENGINE).SessionStore.clear_expired()`,
and re-raises `NotImplementedError` as `CommandError` if the configured engine doesn't support
it (`clearsessions.py:13-21`).

FLS never sets `SESSION_ENGINE` anywhere in `config/settings_base.py`,
`config/settings_prod.py`, or `freedom_ls/deployment/settings_defaults.py` (confirmed by
grep across the repo — no hits). Django's own default is
`django.contrib.sessions.backends.db`. FLS also defines no `CACHES` setting, so there is no
cache-based session backend in play either. That makes `django.contrib.sessions.backends.db`
the actual engine in force in every FLS environment, including production.

That backend's `SessionStore.clear_expired()` (`.venv/lib/python3.13/site-packages/django/contrib/sessions/backends/db.py:190-192`) does:

```python
cls.get_model_class().objects.filter(expire_date__lt=timezone.now()).delete()
```

— a plain `DELETE FROM django_session WHERE expire_date < now()`. **This is not a no-op
under FLS's actual configuration.** COMPOSE-8's premise ("Django expires the session cookie
rather than the row … without this container both grow for the life of the stack") matches
FLS exactly: `django_session` really does accumulate one row per login/session and only this
sweep (or an equivalent direct delete) empties it.

If a downstream project overrides `SESSION_ENGINE` to `cached_db` the sweep still works
(`cached_db` subclasses the db backend's `clear_expired`); only `cache` (pure-cache) or
`signed_cookies` backends make it a no-op (their `clear_expired()` raises
`NotImplementedError`, turned into `CommandError` by the command itself), and FLS ships
neither.

## 4. Independent failure of the two sweeps — Django idioms

**`call_command()` vs. calling the underlying code directly.** `call_command()`
(`django.core.management.call_command`) is the right tool here, and is already FLS's house
idiom for invoking one management command from another/from a test (see §6). It runs the
target command through its own `create_parser()`/argument-type pipeline, so
`prune_db_task_results`'s `--backend` (needs `valid_backend_name` resolution) and
`--queue-name="*"` are handled exactly as they would be from the CLI, with no need to
reimplement that coercion by importing the `Command` class and calling `.handle()` with
pre-resolved objects. Critically, **`call_command()` does not catch `CommandError`** — that
catch-and-`sys.exit` behaviour lives only in `BaseCommand.run_from_argv()`
(`.venv/lib/python3.13/site-packages/django/core/management/base.py:403-430`), which
`call_command()` does not go through. A `CommandError` (or any other exception) raised inside
`prune_db_task_results.handle()` or `clearsessions.handle()` propagates to the caller as an
ordinary Python exception when invoked via `call_command()`. That is what makes independent
failure possible: wrap each of the two `call_command()` calls in its own `try/except`, so one
sweep's exception never prevents the other sweep's `call_command()` from running.

**Reaching Sentry for a caught exception.** Because the two sweeps are wrapped in `try/except`
specifically so a failure doesn't propagate and abort the other sweep, Sentry's automatic
Django integration (which reports exceptions that escape uncaught) never sees them — the
exception is swallowed by our own `except`. It must be reported explicitly at the point of the
`except` block via `sentry_sdk.capture_exception(exc)`
([Sentry Python usage docs](https://docs.sentry.io/platforms/python/usage/),
[Top Level API](https://getsentry.github.io/sentry-python/api.html)). FLS's Sentry init
(`freedom_ls/deployment/sentry.py:8-18`) is a no-op when `SENTRY_DSN` is unset (dev/CI), so
`capture_exception` is always safe to call unconditionally — it just does nothing without a
configured DSN. `sentry_sdk` is already a direct dependency
(`pyproject.toml:36`, `sentry-sdk[django]>=2.64.0`).

**Exit code once both sweeps have run.** `CommandError.__init__` takes a `returncode=1`
default (`base.py:36-38`). When the *housekeeping command itself* (not the two sweeps it
calls) is invoked the normal way — `python manage.py <fls_housekeeping_command_name>` —
Django's `ManagementUtility.execute()` reaches it through `fetch_command(...).run_from_argv(...)`,
so if the housekeeping command's own `handle()` ends by raising `CommandError` (e.g. after
recording that one or both sweeps failed), `run_from_argv` catches it, prints it to stderr,
and calls `sys.exit(e.returncode)` — a clean non-zero exit
(`base.py:419-430`). Any *uncaught* exception (not `CommandError`) from `handle()` instead
propagates all the way out of `run_from_argv`/`execute_from_command_line`, and the Python
interpreter's default unhandled-exception behaviour — print traceback to stderr, exit code 1
— applies; either path satisfies "exits non-zero if any sweep failed," but raising
`CommandError` deliberately (rather than letting a raw exception escape) is the idiom that
also gets the "print it sensibly to stderr" behaviour Django built for this exact case
(`base.py:403-409`).

## 5. Idempotency and safety

Both sweeps are pure "delete rows matching an already-dead-state filter" operations, with no
ordering dependency between them and no interaction with in-flight work:

- `prune_db_task_results` only ever touches rows already in `FAILED`/`SUCCESSFUL` — never
  `READY` or `RUNNING` — so a currently-executing or not-yet-run task can never be deleted out
  from under it (`django_tasks_db/models.py:75-82`, `prune_db_task_results.py:111`). Running
  it twice in a row: the first run deletes every row matching the age filter; the second run's
  identical filter matches zero rows and `results.delete()` on an empty queryset is a no-op
  (`prune_db_task_results.py:127-129`).
- `clearsessions` → `SessionStore.clear_expired()` is `DELETE ... WHERE expire_date < now()`
  (`django/contrib/sessions/backends/db.py:190-192`). Re-running it after it has already
  deleted everything expired as of the first run simply matches nothing new (until more
  sessions expire). There is no state this command can corrupt by running twice, and no time
  of day it is unsafe to run — it never touches an unexpired (live) session row.

Both are supported directly by the "safe to run at any time, and safe to run twice" bullet:
neither sweep has a precondition on system state beyond "some rows may or may not match its
delete filter," which is true at every point in the stack's lifetime.

## 6. House conventions — command style and testing

**BaseCommand vs. djclick.** All FLS management commands under `freedom_ls/*/management/commands/`
use one of the two, and the split tracks who/what invokes the command:

- **`djclick`** (`import djclick as click`, `@click.command()`) is used for commands with
  richer CLI ergonomics aimed at a human operator or QA scripting — e.g.
  `freedom_ls/site_aware_models/management/commands/create_site.py`,
  `freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py`, and every
  command under `freedom_ls/qa_helpers/management/commands/`. Errors are raised as
  `click.ClickException` and tests assert on them with `pytest.raises(ClickException, ...)`
  (`freedom_ls/role_based_permissions/tests/test_management_commands.py:9,217`).
- **`BaseCommand`** (`django.core.management.base.BaseCommand`, `CommandError`) is used for
  infra/build-time commands invoked programmatically or from tooling rather than typed by a
  human at a shell each time — e.g.
  `freedom_ls/base/management/commands/write_active_theme_css.py` (invoked from the npm
  tailwind scripts) and `freedom_ls/accounts/management/commands/build_legal_docs_manifest.py`
  (invoked at build time). Both raise `CommandError` for expected failure conditions rather
  than a bare exception.

A daily-loop, container-invoked command with no human ever typing flags at it — the shape
`run_housekeeping`/its FLS-owned wrapper is — sits squarely in the `BaseCommand` half of that
split, matching `write_active_theme_css` and `build_legal_docs_manifest` rather than the
djclick-based operator/QA commands. `prune_db_task_results` and `clearsessions` themselves are
also both plain `BaseCommand`s upstream, for the same reason.

**Testing convention** (`claude_plugins/fls-dev/skills/testing/SKILL.md`, and observed in
`freedom_ls/role_based_permissions/tests/test_management_commands.py` and
`freedom_ls/learner_progress/tests/test_recalculate_progress_percentages.py`):

- Tests live at `freedom_ls/<app_name>/tests/test_<module>.py`.
- Commands are invoked via `django.core.management.call_command("<name>", ...)`, never by
  shelling out to `manage.py`.
- stdout is captured with `StringIO()` + `contextlib.redirect_stdout` when a test needs to
  assert on command output (`test_management_commands.py:331-336`).
- `pytest.raises(ClickException, match="...")` is the pattern for asserting a djclick
  command's expected failure; the equivalent for a `BaseCommand` failure is
  `pytest.raises(CommandError, match="...")` (not observed directly in FLS's own commands'
  tests yet, but it is the direct Django counterpart to the `ClickException` pattern already
  in use, given `call_command()` does not catch `CommandError` — see §4).
- Any test touching a site-aware model takes the `mock_site_context` fixture rather than
  setting `site` manually (mandatory FLS overlay rule).
- Marker taxonomy: unmarked = portable/downstream-valuable by default; `fls_internal` only for
  tests genuinely coupled to FLS's own repo/brand/demo state. A housekeeping-command test
  suite (sweeping generic `DBTaskResult`/`django_session` rows) has no FLS-brand coupling, so
  it stays unmarked/portable.

No `run_worker` command exists yet anywhere in the FLS tree (`freedom_ls/*/management/commands/`
or `config/`) — `run_worker` is referenced only in the infrastructure contract as a
downstream-repo-provided wrapper around `django_tasks_db`'s `db_worker`, the same relationship
the idea's decisions establish for the housekeeping command's FLS-owned name vs. the
downstream's `run_housekeeping`.

status: ok
