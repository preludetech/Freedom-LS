# Prepare to deploy

FLS has never been deployed. The first deployment is a First Class fleet stack, and that fleet's
infrastructure repo publishes a contract every app repo on the box must satisfy:
`/home/sheena/workspace/first_class/infrastructure/docs/app_repo_contract/`. Six documents, with
numbered clauses `IMAGE-*`, `COMPOSE-*`, `ENV-*`, `EDGE-*` and `CI-*`.

Most of that contract belongs to the downstream project: the Dockerfile, the compose file,
`.env.example`, the CI workflows. FLS ships none of those and is not going to. What FLS owes is the
Python underneath. The management commands those containers run, and the settings that make the
app correct behind a shared reverse proxy. It owes five things and provides none of them.

None of this is specific to First Class. Every FLS deployment resolves its tenant by request host,
starts from a database whose only `Site` is `example.com`, runs its task queue on Postgres and sits
behind something that terminates TLS.

The three notes in the sub-directories are the source review that started this. Where one of them
recommends something this file contradicts, this file wins.

## A first-run bootstrap command

FLS sets no `SITE_ID`, so `get_current_site(request)` resolves the tenant by matching the request
host against `django_site`. A fresh database has one row, `example.com`. Until a row matches the
deployment's hostname, every allauth entrance page, the sitemap and the account mailer raise
`Site.DoesNotExist`, so a freshly deployed stack returns 500 on every login, signup and password
reset. `check --deploy` stays silent throughout: no FLS check registered `deploy=True` queries
`django_site`. Both halves of that are verified in `research_contract_conformance.md`.

FLS ships `setup_initial_prod_data`, the name `CI-18` uses. It writes the `Site` row for
`HOST_DOMAIN` and one administrative `User`. `HOST_DOMAIN` is not a borrowed convention. FLS
already requires that key in `config/settings_prod.py` for `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS`, and documents it in `docs/deployment-security-checklist.md`.

Three properties bind on it, and they come from `CI-18` rather than from taste. It is safe to run
twice, because somebody will. It never resets a password that already exists, because a command
that silently rotates a live administrator's credential is worse than the gap it closes. It
generates the password rather than accepting one and prints it once, which is the whole reason the
step belongs to an operator instead of to CI.

Both commands in `freedom_ls/site_aware_models/management/commands/` go. `create_site_superuser.py`
is zero bytes, so the command has never existed while the filename advertised it. Django registers
nothing for a module with no `Command`, and anyone reading that directory to work out how to
bootstrap a deployment plans around a feature that is not there. `create_site` is real and wrong
for this job: it sets the superuser's password equal to their email address, and it reassigns
`site.domain` without saving, so re-running it to correct a domain prints nothing and changes
nothing. Nothing executable imports either one; every reference is prose, and
`research_bootstrap_command.md` lists them.

Two behaviours carry forward from `create_site`. The allauth `EmailAddress` row marked verified and
primary, without which the account cannot sign in under `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`.
And the `site` foreign key, which FLS's `User` manager will not accept through `create_superuser`.
The default `Organisation` needs no carrying: a `post_save` receiver on `Site` already creates one
whatever wrote the row.

## A worker command

FLS's production task backend is `django_tasks_db.DatabaseBackend`, so a deployment that does not
run a worker accepts background work and never performs it. That failure is invisible at the point
of call, because enqueuing succeeds. `COMPOSE-8` requires a healthcheck on the worker container,
and there is nothing in FLS to probe.

FLS ships a worker command with four properties. It processes every queue, because `db_worker`
defaults to `default` alone and a task on any other queue would be accepted and never run. It
touches a heartbeat file every time it polls. On finding its own heartbeat stale it reports to
Sentry and exits non-zero, so the container restarts. Otherwise it runs `db_worker`'s loop
unchanged.

The third property is the hard one. A wedged worker is stuck inside a task, so the next iteration
of its own loop never arrives to notice. `research_worker_heartbeat.md` works through the options
and lands on a watchdog thread that exits the process directly. It also rules out `SIGALRM`, which
`db_worker` would swallow as an ordinary task failure.

Two things are settled about the shape. The heartbeat touch sits inside the poll loop itself and
nowhere else. A heartbeat on an independent timer stays green on a dead worker, which is a
documented failure of exactly this pattern elsewhere and is cited in the research. And FLS carries
its own copy of the upstream loop body to get the touch inside it, because `db_worker` puts its
loop in a plain `Worker.run()` with no per-iteration seam. That copy is a real cost. It has to be
re-checked whenever the pinned `django-tasks-db` version moves. FLS pins that version exactly, so
the bump is always a deliberate act, which is what makes the cost affordable.

## A housekeeping command

Two tables grow for the life of a stack and nothing empties them: finished task results, and
expired rows in `django_session`. Django expires the session cookie rather than the row. FLS uses
the database session backend, so this is not theoretical.

FLS ships one command that runs both sweeps, and one command rather than a shell chain because
every requirement on it is an exit-code decision. Chained with `&&` a failing prune stops the
session sweep for the life of the container; chained with `;` the failure is invisible instead. One
sweep failing must never stop the other, every failure must reach Sentry, and the command must
still exit non-zero afterwards. None of that survives in a `while true` wrapper, and a wrapper
written once per downstream is a wrapper that drifts.

It also fails when a task that was due to run has sat unpicked for more than an hour. A worker
polls once a second, so an hour means nothing is consuming. This catches a worker that has
stopped rather than wedged, which the heartbeat cannot see. A scheduled task not yet due is not
late. `research_housekeeping_command.md` has the query shape and the sentinel `run_after` value
that distinguishes the two.

Both sweeps prune across every queue, both are safe to run twice, and the command touches the same
heartbeat file on a clean sweep.

## Visitor identity behind the edge

Behind the fleet's shared proxy, `REMOTE_ADDR` is the proxy's own address on the Docker network. It
is the same value for every visitor on the box. Nothing in FLS sets `AXES_CLIENT_IP_CALLABLE` or
`ALLAUTH_TRUSTED_CLIENT_IP_HEADER`, so django-axes and allauth both read it.

That is a live denial of service on the login page, not a tidiness problem.
`AXES_LOCKOUT_PARAMETERS` is set to the flat `["ip_address", "username"]`, which locks on address
alone as well as on username alone. Five failed attempts from anyone, and every learner on the
stack is locked out of a shared address they have no way to stop sharing.
`AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT` is unset, so the library's default lets a script
that keeps trying hold that lockout open indefinitely.

FLS reads the single-valued header the edge sets, uses the nested lockout form so a lockout needs
address and username together, and stops a retrying client from extending its own cool-off. FLS
already has a narrower mechanism here, `TRUSTED_PROXY_IP_HEADER` feeding `get_client_ip`, used only
for `LegalConsent` evidence and wired to neither library. Its docstring offers `X-Forwarded-For` as
the example, which is the header this must not naively split. Whether the new wiring extends that
mechanism or sits beside it is the spec's call. The docstring is wrong either way.

## A production cache

FLS sets no `CACHES` anywhere, so production silently runs Django's `LocMemCache`: per-process, so
each gunicorn worker holds its own, and lost on every restart. `CI-14` requires the database cache
backend and puts `createcachetable` in the automated deploy sequence, which is inert against a
setting that does not exist.

This is also what makes the axes fix work. Failure counters split across gunicorn workers do not
count, so the lockout thresholds above mean something different in production from what they mean
in a test.

## Deliberately not in scope

`create_demo_data` keeps its hardcoded loopback domains and its password-equals-email accounts. It
is a development command and those are correct for development. What it gets is a docstring and
help text saying so, because it is currently the only command that writes `Site` rows and it reads
from the outside like a seeder something might point at staging. Seeding a staging tier is not an
FLS concern.

The Sentry cron monitor stays downstream. `COMPOSE-8` wants the housekeeping container checking in
to one, but the monitor's slug and environment are fleet conventions, and FLS commands reaching
Sentry with errors is the part that generalises. The downstream wrapper does the check-in.

The Dockerfile, the compose file, `.env.example` and the CI workflows stay downstream, as do all of
`IMAGE-*` and most of `COMPOSE-*`. FLS's job is to make those writable correctly, not to write them.

## Consequences worth knowing before the spec

`setup_initial_prod_data` is the contract's name, and a downstream that defines its own of that name
will shadow FLS's or be shadowed by it, silently, depending on which app sits earlier in
`INSTALLED_APPS`. First-Class-LMS has already written one. Something has to give there, and it is a
one-line conversation with that repo rather than a reason to rename FLS's.

FLS's worker and housekeeping commands need names of their own, distinct from the `run_worker` and
`run_housekeeping` that `COMPOSE-8` names, for the same shadowing reason and with no contract
clause forcing the collision. Downstream wrappers take the contract's names.

`research_contract_conformance.md` also flags that the concrete-project template ships a compose
file with its own `caddy` service publishing ports 80 and 443, which `EDGE-5` and `COMPOSE-4` both
forbid, and a `web` healthcheck that sends no `Accept: application/json` and so lands on the
`Site.DoesNotExist` path. That is the template repo's bug, not FLS's, and it needs fixing before
anyone copies it.

## Research

- `research_bootstrap_command.md` lists every reference to the two deleted commands, what
  `create_site` does that must survive, FLS's `User` and superuser requirements, and how Django
  resolves duplicate command names.
- `research_worker_heartbeat.md` covers `db_worker`'s loop and the seams it does and does not
  offer, the all-queues argument, and why a watchdog thread is the only staleness check that works.
- `research_housekeeping_command.md` covers `prune_db_task_results` and `clearsessions` internals,
  the late-unpicked-task query, and how to fail both sweeps independently while still exiting
  non-zero.
- `research_contract_conformance.md` lists every contract clause that binds on FLS, what FLS already
  satisfies, and what it does not.
