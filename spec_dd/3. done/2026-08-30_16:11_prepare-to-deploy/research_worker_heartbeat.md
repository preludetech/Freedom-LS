# Research: worker heartbeat (`COMPOSE-8` `worker` clause)

Scope: how FLS's own worker command (an FLS-owned name, wrapping `django_tasks_db`'s
`db_worker`, per the decision already made) can satisfy `COMPOSE-8`'s four bound properties
for `worker` and the "heartbeat, and what reads it" section, both read in full from
`/home/sheena/workspace/first_class/infrastructure/docs/app_repo_contract/compose.md:143-254`.

The four properties FLS's command must deliver (contract's own words,
`compose.md:175-185`):
1. process every queue (not just `default`);
2. touch the heartbeat every time it polls the queue;
3. on finding its own heartbeat stale, report to Sentry and exit non-zero;
4. otherwise run `db_worker`'s loop unchanged.

The healthcheck itself (`compose.md:161`) is `find /tmp/heartbeat -mmin -5 | grep -q .`,
`interval: 60s`, `start_period: 60s` — that is infra's file, not FLS's concern; FLS only
has to keep `/tmp/heartbeat`'s mtime honest.

---

## 1. `db_worker` internals

Source read in full:
`.venv/lib/python3.13/site-packages/django_tasks_db/management/commands/db_worker.py`.

- The command class is `Command(BaseCommand)` (`db_worker.py:228`). `add_arguments`
  (`db_worker.py:231-284`) defines `--queue-name`, `--interval`, `--batch`, `--reload`,
  `--backend`, `--no-startup-delay`, `--max-tasks`, `--worker-id`.
- `Command.handle()` (`db_worker.py:307-347`) does almost nothing itself: it configures
  logging, builds one `Worker(...)` instance from the parsed options, and either calls
  `worker.configure_signals(); worker.run()` directly, or (if `--reload`, default
  `settings.DEBUG`) wraps `worker.run` in Django's `run_with_reloader`.
- All the actual polling logic lives in a **separate plain class**, `Worker`
  (`db_worker.py:30-191`), not in the `Command`. `Command` only constructs it and calls
  `.run()`. This matters: subclassing `Command` alone (overriding `handle()`) does not
  give access to per-iteration behaviour unless the subclass also replaces `Worker.run()`
  itself, because that's where the loop lives.
- `Worker.run()` (`db_worker.py:87-147`) is a single `while self.running:` loop. Each
  iteration:
  1. builds a `DBTaskResult.objects.ready()` queryset filtered by backend (and by
     `queue_names` unless `process_all_queues`);
  2. inside `exclusive_transaction(tasks.db)`, calls `tasks.get_locked()` to claim one
     task row (or `None`);
  3. if a task was claimed, calls `self.run_task(task_result)`;
  4. if `self.batch and task_result is None`: returns (exits the loop/process);
  5. if `max_tasks` reached: returns;
  6. calls `close_old_connections()`;
  7. if still running and no task was just claimed, `time.sleep(self.interval)`.
- `Worker.run_task()` (`db_worker.py:149-191`) is the seam that runs **only when a task
  was actually claimed** — it sends `task_started`/`task_finished` signals
  (`django_tasks.signals`, `db_worker.py:160,173-175,185-188`) around `task.call(...)`,
  and always resets `self.running_task = False` in a `finally` (line 190) whether the
  task succeeded or raised.
- Signal handling: `Worker.configure_signals()` installs handlers for `SIGINT`, `SIGTERM`,
  `SIGQUIT` (`db_worker.py:75-79`) that flip `self.running = False` for graceful shutdown,
  or `sys.exit(1)` if a second signal arrives mid-task (`db_worker.py:56-73`). There is no
  existing hook for `SIGALRM` or any other periodic signal.

**Seams available to an FLS subclass/wrapper, named concretely:**

- There is **no per-iteration method** distinct from the full loop — `run()` is the only
  place that executes once per poll regardless of whether a task was claimed. `run_task()`
  only executes when a task was claimed, so it cannot alone be the heartbeat-touch point
  (see §3: the contract requires the heartbeat touched *every* poll, including empty
  polls, since `db_worker` polls once a second and the healthcheck window assumes ~300
  ordinary cycles in 5 minutes — `compose.md:245-248`).
- `task_started`/`task_finished` (django_tasks signals) fire only when a task actually
  runs — same limitation as `run_task()`. Not sufficient alone.
- The only two honest options, both requiring an FLS-owned subclass of `Worker` (not just
  of `Command`, since `Command.handle()` treats `Worker` as an opaque, fully-constructed
  object it calls `.run()` on):
  1. **Override `run()` wholesale** in an FLS `Worker` subclass, copying the loop body
     from `db_worker.py:87-147` and inserting a heartbeat-touch call at the point that
     runs on every iteration regardless of outcome (e.g. right after `close_old_connections()`,
     `db_worker.py:141`, before the sleep). This is a full copy-paste of upstream's loop —
     fragile to an upstream version bump (FLS pins `django-tasks-db==0.12.0` exactly, per
     `freedom_ls/deployment/settings_defaults.py:47-48`), and every future patch to
     `Worker.run()` has to be re-applied by hand.
  2. **Override `run_task()` only, and accept a coarser heartbeat contract**: touch the
     heartbeat both (a) at the top of every `run_task()` call and (b) wrap the idle branch
     by *also* overriding `run()` minimally to touch the heartbeat once when no task was
     claimed. This still requires overriding `run()` — there's no way to avoid it if idle
     polls must count towards the "polled" heartbeat. If FLS is willing to accept that the
     heartbeat is only guaranteed fresh *while tasks are actively completing* rather than
     provably fresh on every single 1-second idle tick, `run_task()` alone could be the only
     override, since the healthcheck window (5 minutes / ~300 cycles, `compose.md:245-248`)
     has generous slack for idle polling to still look fresh from an earlier touch — but
     this is a materially weaker reading of "touches the heartbeat every time it polls the
     queue" (`compose.md:177`) than what the contract states, so it should not be presented
     as satisfying the clause without flagging the gap.
  - There is no signal, no Django system-check hook, and no documented extension point in
    `django-tasks-db` for this (confirmed by reading the full source file; nothing else in
    the package registers a signal around the poll loop itself, only around task
    execution).
  - Conclusion: satisfying `compose.md:177` literally requires overriding `Worker.run()`,
    which means vendoring/duplicating upstream's loop body inside FLS. This is the
    concrete cost the contract's own "worker exists" framing accepts implicitly, but it
    is worth naming plainly here since it was not decided already.

## 2. How to run all queues

`Worker.__init__` sets `self.process_all_queues = "*" in queue_names`
(`db_worker.py:43`), and `Worker.run()` only filters `tasks = tasks.filter(queue_name__in=self.queue_names)`
`if not self.process_all_queues` (`db_worker.py:100-101`). `Command.add_arguments`'s
`--queue-name` help text confirms: *"To process all queues, use `'*'`"* (`db_worker.py:237`).
So the exact argument value is `--queue-name '*'` (quoted so the shell doesn't glob it) —
equivalently, when constructing `Worker(...)` directly, pass `queue_names=["*"]`. This is
argument-surface only; it needs no code seam beyond passing the right value through to
`Worker.__init__`.

## 3. Heartbeat mechanics

- **Touching cheaply per poll.** The cheapest correct primitive is `Path(...).touch()`
  (stdlib `pathlib`), which updates mtime (and creates the file if absent) with a single
  syscall (`utimensat`/`futimens` under the hood) — no read, no write of file contents
  needed, since the healthcheck (`find ... -mmin -5`) only inspects mtime. At `db_worker`'s
  default 1-second poll interval this is one cheap syscall per second; that is negligible
  I/O load and does not need debouncing or a separate timer — touching on every iteration
  *is* the whole point (see §5's pitfall about heartbeats that update independently of
  real work).
- **Non-root user and path choice.** `dockerfile.md:17-30` (`IMAGE-2`) runs the container
  as `appuser`, uid `10001`, created via `useradd --system --create-home --uid 10001
  appuser`. `compose.md:242-243` states plainly: `/tmp/heartbeat` sits under `/tmp`
  *because* `IMAGE-2` runs as non-root — `/tmp` is world-writable (sticky bit, mode 1777)
  by default in the `python:*-slim` runtime image regardless of which user owns the
  process, so it needs no explicit `chown`/`chmod` step in the Dockerfile for a non-root
  `appuser` to write there. Any FLS-side implementation must honour the same fixed path;
  the contract fixes it explicitly ("The path is fixed here so all four stacks agree and
  the check above is copy-paste," `compose.md:239-240`) — this is not a place for
  per-deployment configurability.
- **Should the path be an FLS app setting?** The house pattern for this
  (`freedom_ls/base/app_settings.py:11-59`, illustrated by `freedom_ls/health/config.py`
  and `freedom_ls/deployment/config.py`) is `AppSettings` subclasses with a
  `declared_settings: dict[str, Setting]` map, each `Setting(default=..., required=...)`,
  exposed as a module-level `config = SomeConfig()` singleton, read lazily via
  `config.NAME` (never at import time — `app_settings.py:25`). Given the path is fixed by
  the contract for a reason (fleet-wide healthcheck copy-paste, `compose.md:239-240`),
  making it a *required*, uncustomisable setting would contradict the contract's own
  stated rationale; making it an *optional* setting with `Setting(default="/tmp/heartbeat")`
  would fit the house pattern exactly (mirrors `HealthConfig.HEALTH_READINESS_CHECKS`'s
  shape: one list-typed optional setting with a sensible default,
  `freedom_ls/health/config.py:9-11`) while still letting a downstream override it if a
  future stack genuinely needs to (e.g. a differently-shaped filesystem). This is a design
  choice, not settled by the research; the trade-off is fleet-wide predictability
  (contract's stated reason) versus the project's general preference for configurability
  via `AppSettings` rather than hardcoded literals. Whichever app owns the worker command
  would define its own `config.py` in that app following exactly the
  `HealthConfig`/`DeploymentSettings` shape.

## 4. Self-detected staleness — the hardest part

The contract's own words for what has to happen: *"On finding its own heartbeat stale it
reports to Sentry and exits non-zero, so `restart: unless-stopped` restarts it"*
(`compose.md:178-179`), and *"What acts on a wedged worker is `run_worker` exiting, not
Docker"* (`compose.md:254`). The hard constraint: **a wedged worker is, by definition,
stuck inside `task.call()`** (`db_worker.py:162-168`, called from `run_task()`, called
from the single-threaded `run()` loop) — so whatever does the staleness check cannot be
"the next iteration of the same loop," because that iteration never arrives while the
task is hung.

Three candidate mechanisms, evaluated:

- **A separate background thread inside the same process (a watchdog thread).** Started
  once, before `worker.run()` is called, running a `while True: sleep(N); check
  time.time() - last_touch > threshold: act` loop. This is the option that actually works
  for the general case, for a specific reason worth stating precisely: Python's GIL is
  released periodically even during CPU-bound execution (cooperative switching, default
  `sys.getswitchinterval()` = 5ms) and is released around blocking I/O (DB queries via
  psycopg, HTTP calls, `time.sleep`) — which covers the overwhelmingly common way a task
  actually hangs (a network call or DB query that never returns). A watchdog thread
  therefore keeps getting scheduled and can independently read the heartbeat file's mtime
  (or an in-process timestamp updated at the same point) and call **`os._exit(1)`**
  directly — not `sys.exit()`, which only raises `SystemExit` in *whichever* thread calls
  it and would do nothing useful called from the watchdog thread (it would just exit the
  watchdog thread, leaving the wedged main thread and the process running). `os._exit()`
  terminates the whole process immediately, without running Python-level cleanup, which is
  exactly the exit semantics needed here — a clean shutdown isn't achievable anyway
  because the wedged main thread cannot cooperate. Trade-off: the one failure mode this
  cannot catch is a C extension that holds the GIL continuously without ever releasing it
  (e.g. a pathological C-level infinite loop) — a real but narrow risk for a Django task
  whose bodies are ordinary ORM/HTTP-bound Python, not compute kernels.
- **`signal.alarm` / `SIGALRM`.** Rejected as the mechanism for *this* job. `SIGALRM`
  only interrupts the **main thread**, and only when the interpreter is in a place that
  checks for pending signals — this generally does happen even mid-syscall since Python
  3.5 (PEP 475's automatic EINTR retry is skipped when a signal handler raises), so it
  *can* interrupt a hung DB call. But `signal.alarm()` supports exactly one pending alarm
  per process, and `db_worker`'s `Worker.configure_signals()` already claims `SIGINT`,
  `SIGTERM`, `SIGQUIT` (`db_worker.py:75-79`) for graceful-shutdown handling — a
  `SIGALRM`-based watchdog would need to coexist with, not replace, that. More
  fundamentally, an alarm that fires *inside* `task.call()` would raise into
  `run_task()`'s `except BaseException as e:` (`db_worker.py:176`), which is deliberately
  broad and catches everything including a raised `TimeoutError`/custom alarm exception —
  so the alarm would be swallowed as an ordinary task failure (`db_task_result.set_failed(e)`,
  `db_worker.py:177`) and the loop would simply continue to the next task, **not** exit
  the process. That is a per-task timeout mechanism, not the "the whole worker process
  exits non-zero" behaviour the contract asks for, and reusing it for that purpose would
  require also patching `run_task()`'s exception handling to distinguish "the watchdog
  fired" from "the task raised," which is exactly the kind of upstream-internals coupling
  §1 already flags as fragile. Plainly: this option does not fit without also overriding
  `run_task()`'s exception handling, and even then it only detects staleness while a task
  is running, not while idle-polling.
  - Sources: [PEP 475 — Retry system calls failing with EINTR](https://peps.python.org/pep-0475/),
    [Python docs — `signal.alarm`](https://docs.python.org/3/library/signal.html#signal.alarm).
- **A separate subprocess supervisor** (e.g. a tiny supervisor process managing the real
  worker as a child, killing/restarting it on staleness). Works in principle — it sidesteps
  the GIL question entirely since it's a different process — but contradicts the
  already-made decision that FLS ships one worker command under one FLS-owned name that
  `run_worker` wraps; introducing a second always-running FLS process (the supervisor)
  inside the same container changes what `command: python manage.py run_worker`
  (`compose.md:159`) is actually running, and duplicates work Docker's own
  `restart: unless-stopped` (`compose.md:127,139-141`) already does at the container
  level — the container-level restart is exactly what's supposed to happen once the
  in-process check exits non-zero. A subprocess supervisor is a heavier, redundant
  answer to a problem the watchdog thread already solves more simply within one process.

**Conclusion for this point:** a same-process watchdog thread reading a shared timestamp
(or the heartbeat file's own mtime) and calling `os._exit(1)` on staleness is the option
that actually works for the class of hang that matters (I/O-bound tasks); `SIGALRM` does
not fit without extensive additional coupling into `run_task()`'s exception handling, and
a subprocess supervisor is a workable but heavier and redundant alternative given
`restart: unless-stopped` already exists at the container level. Reporting to Sentry
before `os._exit(1)` needs `sentry_sdk.capture_message(...)` (or similar) called
synchronously from the watchdog thread — `freedom_ls/deployment/sentry.py:8-18`'s
`init_sentry()` configures the SDK once at process start via `AppConfig.ready()`
(implied by the module's own comment, `deployment/config.py:22`, "read by `init_sentry()`
in `AppConfig.ready()`"), and the Sentry Python SDK is documented as thread-safe for
capturing from a non-main thread, but this should be verified against the installed SDK
version rather than assumed.

## 5. Prior art

- **Celery + Docker heartbeat-file pattern exists but has a documented, exact instance of
  the pitfall this design must avoid.** [maykinmedia/charts issue #148](https://github.com/maykinmedia/charts/issues/148)
  reports a heartbeat file (`/app/tmp/celery_worker_heartbeat`) that kept being updated
  **even after Celery itself stopped responding** ("Error: No nodes replied within time
  constraint"), so the liveness probe stayed green on a dead worker. The issue's own
  conclusion is to abandon the heartbeat-file approach in favour of `celery inspect ping`
  with a long grace period. The root cause, inferred from the report: whatever process
  wrote that heartbeat file was not gated on the worker's own poll/task-processing loop —
  it kept ticking on its own schedule regardless of whether real work was happening. This
  is precisely the failure mode FLS's design must not reproduce: the heartbeat-touch call
  has to sit *inside* the same call path that a hung task blocks (§1, §4), never on an
  independent timer.
- **The "conditional heartbeat" principle, stated directly by a heartbeat/dead-man-switch
  vendor.** [Drumbeats — Heartbeat Monitoring](https://drumbeats.io/heartbeat-monitoring):
  *"Every healthy iteration of your loop sends one outbound ping"* — the ping is meant to
  be a positive assertion that one iteration of real work actually completed, not proof
  the process is merely alive. The same page names the exact failure this implies: *"If a
  loop sends pings unconditionally while being stuck internally, heartbeats won't help."*
  This corroborates the maykinmedia finding independently and generalises it: any
  heartbeat write that isn't causally downstream of the actual work happening is
  worthless as a liveness signal, no matter how the write itself is implemented (file
  mtime, HTTP ping, or otherwise).
- **`find ... -mmin` as the staleness test itself is standard/uncontested** — it appears
  identically in Nautobot's own Celery heartbeat healthcheck
  (`[ $(find $CELERY_WORKER_HEARTBEAT_FILE -mmin -1 | wc -l) -eq 1 ] || false`, per
  [Nautobot Celery Configuration docs](https://docs.nautobot.com/projects/helm-charts/en/stable/advanced-features/celery-configuration/))
  and matches `compose.md:161`'s `find /tmp/heartbeat -mmin -5 | grep -q .` exactly in
  form — nothing to flag there.
- **`celery-live`** ([GitHub](https://github.com/MrWeeble/celery-live),
  [PyPI](https://pypi.org/project/celery-live/)) is a small third-party liveness/readiness
  probe *service* for Celery specifically for Kubernetes, offered as an alternative to the
  file-heartbeat pattern after the same class of bug was hit. Not directly reusable for
  `django-tasks-db` (it's Celery-broker-specific), but its existence corroborates that the
  naive file-heartbeat pattern has a known failure mode serious enough that people built a
  separate tool to route around it, rather than fixing the heartbeat-touch placement — the
  fix FLS is taking (placing the touch inside the loop itself, per §1/§4) is the cheaper
  and, per Drumbeats' framing, more correct fix, not just a workaround.
- Other consulted, lower-signal sources (general Docker-healthcheck background, not
  worker-specific): [Docker healthchecks: what they actually measure — dev.to](https://dev.to/jtorchia/docker-healthchecks-what-they-actually-measure-and-what-you-shouldnt-promise-46mk).

**Pitfall to carry forward explicitly:** the maykinmedia/Drumbeats finding directly
validates §1's conclusion — an FLS wrapper that touches the heartbeat from a location
*not* gated on the poll loop's own progress (e.g. a bare `threading.Timer` ticking on a
fixed schedule, independent of `Worker.run()`) would defeat the entire design exactly the
way the Celery chart's did. The heartbeat-touch call must be reached only when the loop
itself actually completes an iteration.

## 6. Existing FLS tests for management commands

- House convention, confirmed by reading `freedom_ls/role_based_permissions/tests/test_management_commands.py`
  and corroborated by the prior research files already in this spec's directory
  (`spec_dd/2. in progress/more-testing-skills/research_testing_management_commands.md`,
  `research_testing_django_tasks.md` — read in full, not re-derived here):
  - Invoke via `django.core.management.call_command(name, *args)`, never `subprocess`.
  - FLS has two coexisting command styles: plain `BaseCommand` (raises `CommandError`,
    honours `stdout=StringIO()` passed to `call_command`) and `djclick` (`import djclick
    as click`, raises `click.ClickException`, writes via `click.echo`, so tests must use
    `contextlib.redirect_stdout(StringIO())` around the `call_command` call rather than
    passing `stdout=`). `db_worker`'s own `Command` is a **plain `BaseCommand`**
    (`db_worker.py:228`), so an FLS wrapper naturally following that base class would use
    the `stdout=StringIO()` idiom, not `redirect_stdout`.
  - `pytest.mark.django_db` per test; a `_call_sync()`/`_call_validate()` style thin
    helper function wrapping `call_command` + output capture is the established local
    idiom in `role_based_permissions`.
  - "Thin `handle()`/`command()`, logic in a plain importable function" is the explicitly
    preferred shape (both prior research files independently converge on this,
    citing `sync_role_permissions.py` as FLS's own positive example) — directly relevant
    here since `Worker.run()`/`run_task()` are *not* thin and are not FLS's to restructure
    (they're upstream), so FLS's own added logic (heartbeat touch, staleness check, Sentry
    report) should itself live in small, separately testable functions/methods rather than
    inline in an overridden `run()`.
  - `django_tasks_db.DatabaseBackend` itself (the production task backend) is **not**
    exercised in any existing FLS test — confirmed directly by `research_testing_django_tasks.md`
    §A5/§B4.3: tests run under `ImmediateBackend` (`settings_dev`'s `TASKS`, unchanged for
    tests), and there is no documented pattern anywhere (Django docs, `django-tasks-db`
    docs, or FLS's own prior research) for spinning up a real `db_worker`/`Worker` loop
    inside a test process. A worker-heartbeat test suite would therefore need to test the
    heartbeat-touch/staleness-check logic as **plain, directly-callable functions** (e.g.
    "does touching the path update its mtime," "does a stale mtime trigger the exit path,"
    mocked at the `os._exit`/Sentry boundary) rather than attempting an end-to-end
    `call_command("run_worker")` test that actually drains a queue — no existing FLS
    convention or upstream tooling supports the latter.

---

status: ok
