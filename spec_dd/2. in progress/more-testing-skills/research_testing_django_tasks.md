# Research: Testing Django Tasks (`django.tasks` + `django-tasks-db`)

Scope: Django 6.0 native Tasks framework, tested under `settings_dev`/pytest, with
`django_tasks_db.DatabaseBackend` (v0.12.0) as the production durable backend.

## PART A — External best practices

### A1. The `django.tasks` API (Django 6.0 core)

- `@task` decorator marks a **module-level function** as a task. By convention it lives in
  a `tasks.py`, though not enforced.
  ```python
  from django.tasks import task

  @task
  def email_users(emails, subject, message): ...
  ```
  Options: `@task(priority=0, queue_name="default", backend="default", takes_context=False)`.
  [Django Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/) ·
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)

- **`Task.enqueue(*args, **kwargs)`** returns a `TaskResult` (id, status, timestamps,
  errors, `return_value`). Async variant `aenqueue()`. `Task.using(...)` returns a copy
  with overridden priority/queue_name/backend/run_after (original unchanged).
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)

- **`default_task_backend`** / **`task_backends["alias"]`**: the configured backend
  instance(s), resolved from the `TASKS` setting. FLS's `webhooks/events.py` imports
  `default_task_backend` directly and calls `.enqueue(task, args=[...], kwargs={})` on it
  (equivalent to `task.enqueue(*args, **kwargs)` but backend-explicit).
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)

- **`TASKS` setting**: dict keyed by backend alias (`"default"`, others), each entry needs
  `BACKEND` (dotted path); `OPTIONS` and `QUEUES` are documented keys.
  ```python
  TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}
  ```
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/) ·
  [Django 6.0 release notes — Background Tasks](https://docs.djangoproject.com/en/6.0/releases/6.0/)

- **All args/kwargs and the return value must be JSON-serializable** — this is validated by
  the backend (`validate_task`) regardless of which built-in backend is configured, so it
  *is* caught by ImmediateBackend-backed tests, not just in production. Non-JSON-friendly
  types (tuples, datetimes, model instances) need explicit conversion (e.g. pass an id, not
  an object; tuples silently become lists on the JSON round-trip and lose hashability).
  [Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/)

- Only two backends ship in Django 6.0 itself, and both are **documented as
  development/testing-only** — there is **no built-in production backend**. A real
  production backend (e.g. `django-tasks-db`) is a required third-party dependency; Django
  provides task *definition or scheduling*, not a worker.
  [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/) ·
  [Django's Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/)

### A2. `ImmediateBackend` — the recommended test/dev backend

- `django.tasks.backends.immediate.ImmediateBackend` runs the task **synchronously, in the
  calling thread, at `.enqueue()` time**, and returns a completed `TaskResult`.
- Verified from Django's own source (`django/tasks/backends/immediate.py`): `enqueue()` just
  validates the task and calls `_execute_task()` inline — **no `transaction.on_commit()` or
  `transaction.atomic()` wrapping anywhere in this backend.** Task execution therefore
  happens exactly when `.enqueue()` is called, even mid-transaction.
  [Django source, `django/tasks/backends/immediate.py`](https://github.com/django/django/blob/main/django/tasks/backends/immediate.py)
- `supports_get_result = False` — despite implementing the method, `get_result()` isn't
  meaningfully usable because the result can't be fetched from a different thread/backend
  round-trip; treat the return value of `.enqueue()` (the `TaskResult` you already have) as
  the only thing worth asserting on.
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)
- How to activate for tests: either make it the default for `settings_dev`/test settings
  (as FLS already does — see Part B), or scope it with
  `@override_settings(TASKS={"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}})`
  for a single test/class when the project's default backend is something else.
  [Django's Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/)

### A3. `DummyBackend` — records without executing

- `django.tasks.backends.dummy.DummyBackend` does **not** run the task; it stores a
  `TaskResult` (status stays `READY`) so you can assert enqueueing happened without side
  effects.
  ```python
  @override_settings(TASKS={"default": {"BACKEND": "django.tasks.backends.dummy.DummyBackend"}})
  def test_enqueues():
      my_task.enqueue("arg")
      backend = task_backends["default"]
      assert len(backend.results) == 1
      assert backend.results[0].status == TaskResultStatus.READY
      backend.clear()
  ```
- **Correction to the assumption in this brief**: the inspectable attribute is
  **`backend.results`** (a list of `TaskResult`), not `.enqueued`. There's also
  `backend.clear()` to reset between assertions.
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/) ·
  corroborated by [Django Tasks: Exploring the Built-in Tasks Framework — Real Python](https://realpython.com/django-tasks/)

### A4. Recommended testing patterns (by layer)

1. **Unit-test the task body directly**, as a plain function — call
   `dispatch_event(event_id, site_id)` (not `.enqueue()`), assert on DB state / mocked
   collaborators. Fast, no backend involved, no coupling to `django.tasks` internals.
2. **Assert enqueueing happened with the right task + args**, without running it — either
   mock the backend (`patch("...events.default_task_backend")` and inspect
   `mock_backend.enqueue.call_args`) or switch to `DummyBackend` for that test and inspect
   `backend.results[0].task` / the args on the `TaskResult`. `DummyBackend` is more
   "native" (asserts against the real API surface, would catch e.g. a non-serializable
   arg), while mocking is more surgical when you specifically don't want the real
   `enqueue()` (and its JSON-serialization validation) to run at all.
3. **Full integration via `ImmediateBackend`**: let `.enqueue()` run for real (this is
   already what FLS's `settings_dev`/test `TASKS` config does — see Part B) — this actually
   *runs* the task inline and exercises task-arg serialization plus the task body in one
   go. Good end-to-end smoke coverage, but be careful: if the task body has side effects
   (HTTP calls, emails), you'll want those collaborators mocked regardless of backend.

   Sources for all three patterns: [Django's Tasks framework docs](https://docs.djangoproject.com/en/6.0/topics/tasks/), [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/), [Real Python — Django Tasks](https://realpython.com/django-tasks/), [Lincoln Loop — Django 6 Tasks](https://lincolnloop.com/blog/django-6-tasks-background-processing-without-the-infrastructure/)

### A5. `django-tasks-db` (`DatabaseBackend`) specifics

- Separate package since v0.12.0 (previously bundled in the older `django-tasks` backport);
  add `"django_tasks_db"` to `INSTALLED_APPS` and set
  `TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}`.
  [django-tasks-db GitHub](https://github.com/RealOrangeOne/django-tasks-db)
- Stores tasks as DB rows (ORM-based — Postgres in FLS's case), which means **task
  enqueueing participates in the calling DB transaction** just like any other ORM write,
  and gives admin-visible task history (scheduled/running/succeeded/errored) — a real
  operational advantage over pure in-memory queues.
  [Using Django Tasks in production — Better Simple](https://www.better-simple.com/django/2026/05/06/using-django-tasks-in-production/)
- Execution requires a **separate out-of-process worker**: `python manage.py db_worker`
  (in `DEBUG` it auto-reloads on code changes unless `--reload` is disabled; auto-reload is
  explicitly *not* recommended in production because tasks may not stop cleanly).
  [django-tasks-db GitHub](https://github.com/RealOrangeOne/django-tasks-db)
- **No test guidance is published** by the package itself for exercising `DatabaseBackend`
  directly in a test suite (could not verify a documented pattern). In practice this means:
  a project's automated tests essentially never exercise the real production backend/worker
  path — they exercise `ImmediateBackend` (or `DummyBackend`) and trust that
  `DatabaseBackend`'s `enqueue()`/task-loading round-trip is JSON-serialization-compatible
  with what `ImmediateBackend` already validated. Flag this as a coverage gap: if a project
  wants confidence the `db_worker` path actually works, that has to be a manual/staging
  check, or a narrow contract test that switches `TASKS` to `DatabaseBackend` via
  `override_settings` and asserts a task row gets created (still not a full
  enqueue→worker→execute round trip without literally running `db_worker`).

### A6. `on_commit` / transactions — the most important, most easily-gotten-wrong part

**Critical, verified finding: Django 6.0's built-in `django.tasks` does *not* automatically
defer `enqueue()` until the current transaction commits.** There is no `ENQUEUE_ON_COMMIT`
setting or automatic on-commit deferral in core Django 6.0 — this was checked directly
against Django's own docs and source:

- The official transactions section of the Tasks topic guide is explicit that **you must
  manually** wrap the enqueue call in `transaction.on_commit()`:
  ```python
  from functools import partial
  from django.db import transaction

  with transaction.atomic():
      Thing.objects.create(num=1)
      transaction.on_commit(partial(my_task.enqueue, thing_num=1))
  ```
  and warns that without this, "workers could start to process a Task which uses objects it
  can't access yet."
  [Django's Tasks framework docs — Transactions](https://docs.djangoproject.com/en/6.0/topics/tasks/#transactions)
- `ImmediateBackend`'s source has zero `on_commit`/`atomic` code (verified directly, see
  A2) — it enqueues (=runs) exactly when called, transaction or not.
  [`django/tasks/backends/immediate.py`](https://github.com/django/django/blob/main/django/tasks/backends/immediate.py)
- An **open** Django Forum proposal (opened 2026‑05‑23, *after* the 6.0 release) to add a
  `Task.enqueue_on_commit()` convenience method confirms this gap is known and unresolved
  as of this research: the current recommended pattern is "verbose and easy to forget," and
  the lack of a built-in helper causes real races ("the worker may start on another
  connection and fail to read the database row that the request just created").
  [Django Forum — "Add Task.enqueue_on_commit() to Django's Tasks API"](https://forum.djangoproject.com/t/feedback-requested-add-task-enqueue-on-commit-to-django-s-tasks-api/45174)
- **Do not confuse this with the older, separate `django-tasks` backport package**
  (RealOrangeOne's pre-Django-6.0 project), which reportedly had its own
  `ENQUEUE_ON_COMMIT` setting concept with different default semantics. Search results
  surfaced that name and initially looked authoritative for core `django.tasks`, but it did
  **not** check out against Django's actual 6.0 docs/source. Flagging this explicitly since
  it's an easy trap when researching this topic — always verify against
  `docs.djangoproject.com/en/6.0/...`, not just search snippets or older backport docs.
- Net effect: **any code that creates a DB row and then enqueues a task depending on that
  row must explicitly wrap the enqueue in `transaction.on_commit(functools.partial(...))`**
  — this applies to `ImmediateBackend` too if you ever run under `ATOMIC_REQUESTS`/nested
  atomic blocks and want deterministic ordering, and applies doubly to
  `django_tasks_db.DatabaseBackend` in production, where the task really is picked up by an
  out-of-process worker on a separate connection.

**Testing this correctly with pytest-django:**
- pytest-django's `django_capture_on_commit_callbacks` fixture is the idiomatic way to
  assert an `on_commit()`-wrapped callback (e.g. the enqueue) actually gets registered and
  (optionally, with `execute=True`) fires:
  ```python
  def test_enqueues_on_commit(db, django_capture_on_commit_callbacks):
      with django_capture_on_commit_callbacks(execute=True) as callbacks:
          fire_webhook_event(...)
      assert len(callbacks) == 1
  ```
- **The fixture's own docs explicitly warn: "Avoid this fixture in tests using
  `transaction=True`; you are not likely to get useful results."** — `transaction=True`
  changes how/when on_commit callbacks fire (real commits happen) in a way that conflicts
  with the fixture's capture mechanism.
  [pytest-django — helpers, `django_capture_on_commit_callbacks`](https://pytest-django.readthedocs.io/en/latest/helpers.html)
- This means the two standard techniques for making on_commit code observable in tests —
  `@pytest.mark.django_db(transaction=True)` (real commits, real firing, but you can't
  easily intercept/count the callbacks) vs. `django_capture_on_commit_callbacks` (capture
  and optionally execute, but only under the default non-`transaction=True` marker) —
  **are mutually exclusive per test.** Pick the one that matches what you're asserting:
  end-to-end side effects → `transaction=True`; "was an on_commit callback registered
  with the right args" → `django_capture_on_commit_callbacks` without `transaction=True`.

### A7. Pitfalls (consolidated)

- **Relying on a running worker in tests.** Tests should never depend on `db_worker` being
  up; use `ImmediateBackend`/`DummyBackend`/mocking instead. There is no documented pattern
  for spinning up `db_worker` inside a test process, and doing so would make tests slow and
  non-deterministic. [django-tasks-db GitHub](https://github.com/RealOrangeOne/django-tasks-db)
- **Assuming enqueue-on-commit is automatic.** It is not, in core Django 6.0 (see A6) — a
  task enqueued before its data commits can silently no-op against a row that "doesn't
  exist yet" from the worker's point of view (or, more subtly, is inconsistent) if run under
  `DatabaseBackend` with a real out-of-process worker. This is invisible under
  `ImmediateBackend` because there's no cross-connection race — so **tests that only ever
  use `ImmediateBackend` cannot catch this class of bug.**
  [Django's Tasks framework docs — Transactions](https://docs.djangoproject.com/en/6.0/topics/tasks/#transactions)
- **Non-deterministic execution / ordering** with real backends (priority, queue routing,
  retries) is a production-worker concern, not something to model in unit tests — keep
  those concerns in the task body's own tests (idempotency, retry counts) rather than
  trying to simulate scheduling.
- **Serialization of task args**: JSON-only. Passing model instances, tuples, or
  datetimes as args will fail validation (`TaskResultStatus.FAILED` under
  `ImmediateBackend`, or a `validate_task`/`InvalidTask` error before ever reaching a
  worker under `DatabaseBackend`). Tests that mock out the backend entirely (patching
  `default_task_backend`) will **not** catch this — only a real `.enqueue()` call (via
  `ImmediateBackend` or `DummyBackend`) exercises validation.
  [Tasks API reference](https://docs.djangoproject.com/en/6.0/ref/tasks/)

---

## PART B — Current FLS state & gaps

### B1. Current task usage (`freedom_ls/webhooks/events.py`)

- `fire_webhook_event()` creates a `WebhookEvent` row, then calls
  `default_task_backend.enqueue(_dispatch_event_task, args=[str(event.pk), site_id], kwargs={})`
  **directly — not wrapped in `transaction.on_commit()`.**
- `_dispatch_event_task` is a thin `@task()`-decorated wrapper around the plain function
  `dispatch_event(event_id, site_id)`, which does the real work (endpoint lookup, circuit
  breaker check, `WebhookDelivery` get_or_create, `attempt_delivery()`).
- `dispatch_event()` is a normal function with no `@task` decorator — it's the "logic"
  layer, matching pattern A4.1 (test the plain function directly).

### B2. Task backend configuration

- `config/settings_base.py` (~line 406-414): `TASKS = {"default": {"BACKEND":
  "django.tasks.backends.immediate.ImmediateBackend"}}`, used by both dev **and the test
  suite** (settings_dev inherits from settings_base and doesn't override `TASKS`) — so
  `default_task_backend.enqueue()` in tests genuinely runs `_dispatch_event_task` (and
  therefore `dispatch_event`) synchronously and for real, unless the test explicitly mocks
  `default_task_backend` first.
- `config/settings_prod.py` (line 82): `TASKS = fls_defaults.DATABASE_TASKS`, i.e.
  `{"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}`, defined in
  `freedom_ls/deployment/settings_defaults.py` (lines 45-51).
- `django_tasks_db` and `django.tasks` are both in `INSTALLED_APPS`
  (`config/settings_base.py` lines 84-85), so `django_tasks_db`'s models/migrations exist
  in every environment even though only production actually uses `DatabaseBackend`.
- **The comment in `settings_defaults.py` is not accurate per the research above**: it
  says *"Enqueue stays on-commit (Django default) so the worker sees the committed
  WebhookEvent row."* Per A6, there is **no such Django default** in core `django.tasks`
  6.0 — enqueue-on-commit is something you must implement yourself with
  `transaction.on_commit()`, and `freedom_ls/webhooks/events.py` does not do this anywhere
  in the current code (verified: no `on_commit` calls exist in the `webhooks` app, nor in
  either call site — `freedom_ls/accounts/allauth_account_adapter.py:save_user` or
  `freedom_ls/student_management/models.py:CourseRegistration.save`). This is a real,
  unverified-by-tests correctness gap for the production `DatabaseBackend` path: if
  `fire_webhook_event()` ever runs inside an outer `transaction.atomic()` block, the
  `db_worker` process (a separate connection) could pick up `_dispatch_event_task` and call
  `WebhookEvent.objects.get(pk=event_id)` before that row is committed, hit
  `WebhookEvent.DoesNotExist`, and **silently return** (`dispatch_event`'s explicit
  early-return on `DoesNotExist` — see `events.py` lines 59-62) — the event is lost with no
  error surfaced anywhere. This should be flagged as a functional risk to fix
  (`transaction.on_commit(functools.partial(default_task_backend.enqueue, ...))`) — not
  something this research task is scoped to fix, but worth carrying into the skill as "check
  for this" guidance.
- The `# transaction=True so that on_commit hooks for webhook delivery fire under test`
  comments repeated across `test_events.py` and four other webhook-adjacent test files
  (`accounts/tests/test_account_webhook_events.py`,
  `accounts/tests/test_user_registration_webhook_integration.py`,
  `student_interface/tests/test_course_completion_webhook_events.py`,
  `student_management/tests/test_registration_webhook_events.py`) currently describe
  behavior that **doesn't exist in the code** (no `on_commit` calls anywhere in this
  chain today). Either this is leftover/aspirational commentary, or it's evidence the
  team *intends* to add the missing `on_commit()` wrapping from B2 above and pre-emptively
  set up tests for it. Either way it's worth reconciling: right now `transaction=True` is
  doing something more mundane — letting `ImmediateBackend`'s synchronous task run against
  real committed rows across the multiple queries in `dispatch_event`, and matching the
  pattern used for genuinely commit-dependent assertions elsewhere in the suite.

### B3. Current test patterns (`test_events.py`, `test_integration.py`)

- `TestFireWebhookEvent` (`@pytest.mark.django_db(transaction=True)`):
  - Uses `unittest.mock.patch("freedom_ls.webhooks.events.default_task_backend")` to
    replace the backend entirely, then asserts
    `mock_backend.enqueue.assert_called_once()` and inspects `call_args.kwargs["args"]`.
    This is pattern A4.2 (assert-enqueued, mocked) — functionally reasonable, but per A7 it
    means **no test ever exercises the real `.enqueue()` call with real JSON-serialization
    validation** for `_dispatch_event_task`'s args (`str(event.pk)`, `site_id` — both plain
    JSON-safe types today, so low risk currently, but this pattern wouldn't catch a
    regression if someone later passed something non-serializable, e.g. a `Site` object
    instead of `site_id`).
  - Other tests in this class (`test_creates_event_record_on_commit`, etc.) let the real
    `default_task_backend` (= `ImmediateBackend` under `settings_dev`) run, meaning
    `_dispatch_event_task`/`dispatch_event` executes for real as a side effect of calling
    `fire_webhook_event()` — this is pattern A4.3 (integration via ImmediateBackend),
    though it isn't labeled or intentional-looking as such; it's an implicit consequence of
    the project-wide `TASKS` setting rather than a per-test/`override_settings` choice.
- `TestDispatchEvent` (`@pytest.mark.django_db`, no `transaction=True`): calls
  `dispatch_event(str(event.pk), mock_site_context.pk)` **directly**, bypassing
  `.enqueue()`/`@task` entirely — this is pattern A4.1 (test the plain function). Correct
  approach for logic-heavy assertions (matching endpoints, circuit breaker, idempotency,
  site filtering) — `attempt_delivery` is mocked at the boundary so these tests don't also
  depend on HTTP delivery mechanics.
- `test_integration.py` similarly calls `dispatch_event()` directly (never through
  `.enqueue()`/the task decorator) for its full-flow tests (Brevo preset, standard webhook,
  site isolation), with `httpx.request` mocked at the delivery layer. This never exercises
  `_dispatch_event_task` or the backend at all.

### B4. Evaluation against best practice / gaps for the skill to address

1. **No test uses `ImmediateBackend`/`DummyBackend` explicitly or intentionally** — the
   project relies on the *ambient* `settings_dev` `TASKS` config (ImmediateBackend) rather
   than an explicit `@override_settings(TASKS=...)` per test. This works today because
   there's only one backend config in play, but it means the tests don't self-document
   "this exercises the real enqueue path" vs. "this bypasses it" — worth making explicit in
   the skill (e.g. name the fixture/marker, or comment why `default_task_backend` is
   mocked vs not).
2. **`DummyBackend` is unused but would be a cleaner fit than manual mocking** for
   `test_enqueues_dispatch_event_task`: swapping the `patch(...default_task_backend...)`
   for `@override_settings(TASKS={"default": {"BACKEND":
   "django.tasks.backends.dummy.DummyBackend"}})` + asserting on
   `task_backends["default"].results` would (a) exercise real `Task`/`enqueue()` argument
   validation (catching serialization bugs the current mock can't), and (b) assert against
   the public `django.tasks` API surface instead of an internal implementation detail
   (`default_task_backend.enqueue` being called with specific `kwargs["args"]`).
3. **No test exercises `django_tasks_db.DatabaseBackend`** (production backend) at all —
   entirely reasonable per A5 (no worker in tests), but the skill should be explicit that
   this is a deliberate, accepted gap, not an oversight, and suggest what (if anything)
   compensates for it (e.g. a lightweight settings/staging smoke check, or at minimum a
   `TASKS` setting comment stating the production backend's contract is unverified by
   automated tests).
4. **Missing `transaction.on_commit()` wrapping around the real `enqueue()` call** (B2) is
   the most important finding — it's the one place the current design *actively contradicts*
   its own settings comment and would misbehave in production under
   `django_tasks_db.DatabaseBackend`, but is invisible today because tests only ever run
   under `ImmediateBackend` (which has no cross-connection race to expose it — A6/A7). The
   skill should teach: (a) wrap production-affecting enqueue calls in `transaction.on_commit`
   when they depend on just-created/updated rows, and (b) test that wrapping with
   `django_capture_on_commit_callbacks` (not `transaction=True` — see A6) rather than
   inferring it indirectly through `transaction=True` + a same-process synchronous backend.
5. **`_dispatch_event_task` (the actual `@task`) is never invoked in tests via its
   `.enqueue()`/task API** — every test that runs the dispatch logic does so by calling
   `dispatch_event()` directly. This is correct per pattern A4.1, but leaves a small gap:
   nothing currently proves `_dispatch_event_task`'s thin wrapper (`@task()` decorator +
   arg passthrough) itself is wired correctly end-to-end (e.g. that `.enqueue()` on it,
   not just on `default_task_backend` generically, produces a working call). A single
   `DummyBackend`- or `ImmediateBackend`-based test calling
   `_dispatch_event_task.enqueue(event_id, site_id)` directly would close this.

## Recommendations for the skill (not written here — for the skill author)

- Teach the three-layer pattern from A4 explicitly (plain-function test / assert-enqueued
  test / ImmediateBackend integration test), and name which FLS pattern maps to which.
- Teach `DummyBackend` as the preferred way to assert "a task was enqueued with the right
  args" over mocking `default_task_backend`, specifically because it validates
  JSON-serializability for free.
- Teach the on_commit gap from A6 as a checklist item: "does this task depend on data from
  the current request/transaction? If so, is `.enqueue()` wrapped in
  `transaction.on_commit()`? Is there a test using `django_capture_on_commit_callbacks`
  (not `transaction=True`) proving it?"
- Explicitly document that `django_capture_on_commit_callbacks` and
  `@pytest.mark.django_db(transaction=True)` are not meant to be combined, per
  pytest-django's own docs.
- Flag `django_tasks_db.DatabaseBackend` as untestable-in-process by design; the skill
  should say so rather than implying coverage exists.
- Point at `freedom_ls/webhooks/events.py` + `settings_defaults.py`'s `DATABASE_TASKS`
  comment as a worked (negative) example once the on_commit gap is fixed — before that,
  don't present it as a positive example of correct on_commit handling.

## Unverified / could not confirm

- Whether `django_tasks_db.DatabaseBackend.enqueue()` itself applies any `on_commit`
  deferral internally (as opposed to `django.tasks` core) — I could not fetch the package's
  `backend.py` source directly (404 on the expected raw GitHub path) to check line-by-line.
  Search-result summaries suggest the recommended pattern for this backend is still "wrap
  with `transaction.on_commit()` yourself," consistent with core `django.tasks`, but this
  specific claim is corroborated by search snippets rather than a directly-read source file
  and should be spot-checked against the installed `django_tasks_db==0.12.0` package source
  in the venv before treating it as certain.
- No official published guidance was found for testing `DatabaseBackend` behavior (e.g.
  task-row creation) without running `db_worker`; the "contract test via
  `override_settings`" idea in B4.3 is this researcher's inference, not a documented
  pattern.

status: ok
