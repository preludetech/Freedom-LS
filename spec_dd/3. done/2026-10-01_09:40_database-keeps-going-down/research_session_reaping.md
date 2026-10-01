# Research: reaping leaked sessions safely

Scope: direction item 3 ("the server reaps leaked sessions") from `idea.md`. This corrects and
extends §6 of `research_postgres_failure_modes.md`. Repo facts used throughout are taken from
`config/settings_dev.py`, `freedom_ls/tests/playwright_fixtures.py`, `pyproject.toml`,
`conftest.py`/`freedom_ls/conftest.py`, and `dev_db/docker-compose.yaml`.

## Correction to the existing research

§6 of `research_postgres_failure_modes.md` says a killed pytest run's backend "stays registered
until TCP eventually notices the peer is gone (which can be a long time, or never, on a local
Docker network)." **That is only true for a narrow subset of cases.** For the common case — a
local pytest/Playwright process that is SIGKILLed while its Postgres backend is idle or idle-in-
transaction — the backend notices within milliseconds, not "eventually." The mechanism, and the
cases where the claim is actually right, are in §1 below.

## 1. Does a SIGKILLed local client's backend exit promptly?

**Yes, for the ordinary case in this repo.** Chain of events, cited to primary/near-primary
sources:

- **Kernel side.** `SIGKILL` cannot be caught, but it does not bypass file-descriptor cleanup:
  the kernel's process-exit path closes every open fd, and for a TCP socket that means the normal
  socket-close path, which sends a FIN. A Baeldung-on-Linux writeup that traced this through
  kernel source confirms the exact call chain: `do_signal -> do_exit -> __exit_files ->
  close_files -> fput -> __fput -> sock_close -> inet_release -> tcp_close -> tcp_send_fin`. There
  is a caveat: if the socket's receive buffer still has unread bytes when it closes, TCP sends RST
  instead of FIN — but for an idle/idle-in-transaction connection (nothing buffered, backend
  blocked in `read()`) that doesn't apply, and either way the peer's next `read()` unblocks
  immediately (`0` for FIN, `ECONNRESET` for RST). Source:
  [Baeldung — How Does Linux Decide to Close a Socket When the Application on One End Is
  Killed?](https://www.baeldung.com/linux/socket-closure-handling)
- **Docker's published port (6543 → 5432).** `settings_dev.py` connects to `HOST: "127.0.0.1",
  PORT: "6543"` — i.e. via loopback. Docker's `--userland-proxy` flag (default `true`) is
  documented, in current `dockerd` reference docs, as controlling **"userland proxy for loopback
  traffic"** specifically — meaning exactly this connection path goes through the `docker-proxy`
  userland process (one spawned per published port), not straight through kernel iptables DNAT.
  Source: [`dockerd` CLI reference](https://docs.docker.com/reference/cli/dockerd/). `docker-proxy`
  is a plain bidirectional TCP relay (`moby/moby` `cmd/docker-proxy`); a relay that copies until one
  side returns EOF and then closes the other side is standard `io.Copy`-based proxy behaviour — so
  the FIN from the dead pytest process propagates through `docker-proxy` to the Postgres backend's
  socket, not just to the host kernel. (I could not pull the exact `proxy.go` source text in this
  session — noting this line as **inferred from documented proxy behaviour, not directly verified
  against source**.)
- **Postgres side, idle backend.** A backend that is `idle` or `idle in transaction` is blocked in
  a blocking read on the client socket waiting for the next protocol message. When that read
  returns EOF (or an error), Postgres logs `unexpected EOF on client connection` (or, if in an open
  transaction, `unexpected EOF on client connection with an open transaction`) and exits — this is
  long-documented, ordinary backend behaviour, not a special detection feature; no keepalive or
  polling setting is needed for this path. Sources: [pgsql-admin thread — "idle in
  transaction...unexpected EOF on client connection"](https://www.postgresql.org/message-id/dcc563d10711091441v24fba20fq275ac75f22f5636e@mail.gmail.com),
  [CodeLessGenie — Unexpected EOF on Client Connection with Open
  Transaction](https://www.codelessgenie.com/blog/unexpected-eof-on-client-connection-with-an-open-transaction/).

**Net: for the common "developer/agent Ctrl-C's or SIGKILLs a live pytest process" case, with the
backend idle or idle-in-transaction, the backend exits in about one round trip — not "eventually."**
This significantly narrows the problem direction item 3 needs to solve; it is not the main leak
source.

**Genuine leaks — when the claim in §6 is right — happen when no FIN is ever sent:**

1. **The client process is still alive but stuck**, not gone: an orphaned pytest/xdist worker
   whose parent (an agent process, a shell, a CI runner) was killed but which itself got
   reparented to init and kept running (e.g. blocked in a `pdb`/`breakpoint()` that nobody
   attached to, a hung browser automation call, a deadlocked thread). Nobody closed the socket, so
   no FIN was sent, and the backend has no way to know the other end has gone quiet on purpose vs.
   is just slow.
2. **Host sleep/suspend, or a real network partition** between client and Docker's proxy/NAT layer
   (more of a concern on Docker Desktop's VM boundary than on Linux-native Docker, but the repo
   doesn't state the host OS). No FIN is sent either way; only TCP keepalives or
   `client_connection_check_interval` can catch this, both of which are slow by default (see below).
3. **Backend mid-query (`state = active`) when the client dies.** The backend is not blocked in a
   socket read at that moment — it is executing. It will not notice the client is gone until it
   next tries to read the socket (after the current statement finishes) or, if
   `client_connection_check_interval` is set (PG14+, default `0`/off), the next time it polls the
   socket during execution. Left at its default, a runaway query from a dead client keeps consuming
   CPU/locks for as long as the query itself would have taken; it is not held open indefinitely,
   but it isn't reaped "promptly" either. Source: [pgpedia —
   client_connection_check_interval](https://pgpedia.info/c/client_connection_check_interval.html),
   [ardentperf — Postgres
   client_connection_check_interval](https://ardentperf.com/2026/02/04/postgres-client_connection_check_interval/).
4. **TCP keepalives as the last-resort backstop** for (1) and (2): Postgres's
   `tcp_keepalives_idle`/`_interval`/`_count` default to `0`, meaning "use the OS default" — and the
   Linux default idle time before the first keepalive probe is commonly 2 hours
   (`net.ipv4.tcp_keepalive_time`), with several retries after that. So the fallback path this repo
   would fall onto for a genuinely orphaned client is measured in hours, not minutes. Source:
   [PostgreSQL docs — Connections and
   Authentication](https://www.postgresql.org/docs/17/runtime-config-connection.html).

**Conclusion for item 3:** server-side reaping settings should be sized for cases 1–4 above (truly
orphaned/stuck clients, hung queries, host sleep), not for "every killed pytest run," because most
killed pytest runs already self-clean within a round trip. That reframes what "leaked" means here:
a leaked session in this repo is a backend that a *human or agent forgot about while it was still
technically alive* (a paused debugger, an orphaned subprocess, a stuck browser step), not the
common "I hit Ctrl-C" case.

## 2. The five timeout settings and how each interacts with this stack

All five are documented at [PostgreSQL 17 — 19.11 Client Connection
Defaults](https://www.postgresql.org/docs/17/runtime-config-client.html) (page numbering/section
varies by doc version; fetched via the "current"/17 tree). Units are milliseconds unless suffixed;
all default to `0` = disabled.

| Setting | What it terminates | SQLSTATE seen by client |
|---|---|---|
| `idle_in_transaction_session_timeout` | A session idle **inside an open transaction** (waiting for the next client query, `BEGIN` already issued) | `25P03` |
| `idle_session_timeout` (PG14+) | A session idle **outside any transaction** | `57P05` |
| `statement_timeout` | A single actively-executing statement (does not affect lock-wait time) | `57014` (`query_canceled`) |
| `lock_timeout` | Time spent waiting to **acquire** a lock (not statement execution time) | `55P03` (`lock_not_available`) |
| `transaction_timeout` (**new in PG17** — confirmed) | Total wall-clock span of a transaction, explicit or single-statement-implicit; does not cover prepared transactions | `25P04` |

Confirmed interaction rule, straight from the docs: **if more than one of these would fire, the
shortest applicable one wins** — e.g. if `transaction_timeout` ≤ `statement_timeout` or ≤
`idle_in_transaction_session_timeout`, the longer settings are effectively moot for that session.
The docs explicitly discourage setting `statement_timeout`, `lock_timeout`, or `transaction_timeout`
**server-wide** in `postgresql.conf`, because they affect every session including ones that
legitimately need to run long (e.g. `pg_dump`, a big migration) — the same caveat by extension
applies to `idle_in_transaction_session_timeout` for anything that legitimately holds a long
transaction. `idle_session_timeout`'s own doc text adds a pooler-specific warning: **"be wary of
enforcing this timeout on connections made through connection-pooling software or other
middleware, as such a layer may not react well to unexpected connection closure."** This repo isn't
using a pooler (PgBouncer is explicitly declined in `idea.md`'s "Not doing" section), so that
caveat doesn't bite here, but it's the reason the docs suggest scoping these to specific
roles/users rather than the whole server.

### How each interacts with this repo's actual usage patterns

- **Django `runserver` with `CONN_MAX_AGE=0`.** Confirmed by reading `settings_dev.py`: it sets no
  `CONN_MAX_AGE`, so Django's default `0` applies (the `CONN_MAX_AGE=60` in
  `freedom_ls/deployment/settings_defaults.py` is only pulled into `settings_prod.py`, never into
  `settings_dev.py` — resolving the uncertainty §6 flagged). Django's connection-closing for
  `CONN_MAX_AGE` is wired to the `request_started`/`request_finished` signals (`close_old_connections`),
  which only fire around HTTP request handling. With `CONN_MAX_AGE=0` the dev server's connection is
  opened per request and closed right after — it is essentially never idle long enough for any of
  these five timeouts to matter. Source (Django docs, persistent connections):
  [docs.djangoproject.com/en/6.1/ref/databases/](https://docs.djangoproject.com/en/6.1/ref/databases/)
  and its explicit line: *"The development server creates a new thread for each request it
  handles, negating the effect of persistent connections. Don't enable them during development."*
- **A pytest-django session's own runner/setup connection.** `close_old_connections` never fires
  for it, because it's signal-tied to Django's *HTTP* request cycle, and this connection is used
  for plain ORM calls outside any request-response cycle — so `CONN_MAX_AGE` (whatever its value)
  has **no effect on it at all**. It stays open for as long as the process holding it does. This
  is the connection class that server-side `idle_session_timeout`/`idle_in_transaction_session_timeout`
  actually protects against, not Django settings.
- **Ordinary `django_db` tests (transaction=False, the default).** pytest-django wraps each such
  test in `atomic()` — a real `BEGIN` on first query, rolled back at teardown (mirrors Django's
  `TestCase`; pytest-django docs: [Database access — helpers](https://pytest-django.readthedocs.io/en/latest/helpers.html)).
  While the test's own Python code runs between ORM calls (assertions, factory setup unrelated to
  the DB, non-DB work), the connection is legitimately `idle in transaction` from Postgres's point
  of view for the lifetime of that one test — normal and short (typically well under a second),
  and it resolves itself when the test's `atomic()` block rolls back at teardown. This is **not**
  the same phenomenon the existing research's Django ticket #17887 citation describes: #17887 was
  about psycopg2's old non-autocommit default leaving *long-running Gunicorn processes* stuck
  `idle in transaction` indefinitely between requests — a bug fixed years ago by Django enabling
  autocommit outside `atomic()`. It is not evidence of pytest-django-specific leaking; citing it for
  that is a stretch the existing research made. The real pytest-specific risk is only if the
  *process* is killed mid-test, before that `atomic()` block gets to roll back — at which point it
  falls into the §1 taxonomy above (usually reaped fast; a leak only if the process is stuck rather
  than gone).
- **Playwright tests (`transaction=True` + `live_server`).** `transaction=True` means no `atomic()`
  wrapping — this is `TransactionTestCase`-style, and `playwright_fixtures.py`'s own module
  docstring confirms every existing E2E test uses `@pytest.mark.django_db(transaction=True)`
  precisely because plain `atomic()`-wrapped tests are invisible to a second DB connection (the
  browser talks to `live_server` on its own thread/connection). Two different connections are in
  play, with two different exposures:
  - The **`live_server` thread's connection** *does* go through Django's request cycle for every
    HTTP request the browser triggers, so `close_old_connections` does fire for it, and with
    `CONN_MAX_AGE=0` it is opened-and-closed per request — the fix from Django ticket #22414
    (**confirmed via the ticket**: `LiveServerThread` connections left open past thread teardown,
    fixed by explicitly closing all connections at teardown) means this class of leak is already
    closed upstream in current Django. It should not sit idle "for many seconds while the browser
    works" under this repo's settings — it isn't holding a connection between requests at all.
  - The **pytest main thread's own connection** (used by fixtures like `logged_in_user` for
    `UserFactory(...)`, `EmailAddress.objects.get_or_create(...)` in `playwright_fixtures.py`) is a
    different story: because `transaction=True` means no `atomic()` wrapper, this connection sits
    plain **idle** (not idle-in-transaction — autocommit, no open transaction) for however long the
    test spends waiting on Playwright/the browser between ORM calls. For a single test this is
    seconds, not minutes, so it's well inside any sane `idle_session_timeout`, but it's the
    concrete mechanism behind the idea doc's "may sit idle for many seconds" line.
  - A **developer paused in `pdb`/`breakpoint()`** mid-test holds whichever of these connections
    was last touched open indefinitely — this is case 1 from §1's leak taxonomy (client alive, no
    FIN sent) and is exactly what `idle_in_transaction_session_timeout` /
    `idle_session_timeout` are for.
- **`--reuse-db` sessions / long migrations on test-DB creation.** These don't change the timeout
  math directly, but they mean the "test DB creation" connection can legitimately be open for
  longer than a normal query (a slow migration) — a `statement_timeout` set too low would abort a
  legitimately slow migration rather than a leak. This is the concrete reason the docs' "don't set
  `statement_timeout` server-wide" caveat matters here.

### What error the client sees, and does the run recover?

Each of the five timeouts, when it fires, closes the connection server-side and the client's
*next* interaction with it raises a `FATAL`. In Django/psycopg terms this surfaces as
`django.db.utils.OperationalError` (psycopg wraps the Postgres FATAL into a `psycopg.errors.*`
subclass of `OperationalError`, which Django's backend re-raises unchanged — I did not find Django
source confirming automatic retry, and the docs' `CONN_HEALTH_CHECKS` feature (see §4) exists
specifically because Django does **not** transparently retry a dead connection: it eagerly checks
before use only if that flag is enabled). Practically:

- If the killed connection belongs to **one test's fixtures or one Playwright test's main-thread
  connection**, the next ORM call after the timeout fires raises `OperationalError` inside that one
  test — it fails (or errors) individually; pytest reports it as one failing test, not a whole-run
  crash, unless it happens while pytest-django's global test-DB setup/teardown connection is the
  one killed (rarer, and more disruptive — that would abort the whole session's setup).
- If the killed connection belongs to a **live migration or the test-DB creation/`template1`
  connection**, the whole run fails at setup with an `OperationalError`/`FATAL` — this is the
  scenario the "don't set `statement_timeout` too low" caveat is protecting against.
- None of these fail *confusingly* in the sense of hanging silently — Postgres logs the exact
  `FATAL: terminating connection due to ...` line, and psycopg surfaces a distinguishable
  SQLSTATE (table above), so a developer grepping the Postgres log or reading the traceback's
  SQLSTATE can identify which timeout fired. That directly serves direction item 6 ("the next
  failure explains itself") if these settings are adopted.

### Recommended values and where to set them

Given the above, my recommendation is to **size these for the "stuck human/agent" case, not the
"routine test run" case**, and to prefer per-role scoping over `postgresql.conf`-wide (`-c` flags),
per the docs' own advice:

| Setting | Recommendation | Reasoning |
|---|---|---|
| `idle_in_transaction_session_timeout` | **10–30 min**, set per role (`ALTER ROLE pguser SET idle_in_transaction_session_timeout = '15min'`), not server-wide | Long enough to survive a real pdb pause or a slow browser step; short enough that a genuinely abandoned `atomic()` block (dead worktree, forgotten debugger) stops holding locks/blocking vacuum within a work session, not overnight |
| `idle_session_timeout` | **60 min or "don't set"** | This repo has no pooler, so the docs' pooler caveat doesn't apply, but plain idle sessions cost little (no locks) — the main win is capping a truly orphaned pytest-runner connection (§1 case 1) eventually. Setting it aggressively risks killing a developer's `manage.py shell` or a long `ipython` session mid-thought for no real benefit; a generous value (or leaving it unset and relying on `idle_in_transaction_session_timeout` plus manual cleanup) is safer for a dev-only server |
| `statement_timeout` | **Don't set server/role-wide.** If set at all, scope it to a "CI/agent" role, well above the slowest known migration/test-DB-creation query | Docs explicitly discourage this globally; this repo has migrations and `--create-db` cycles whose duration isn't bounded by a known worst case |
| `lock_timeout` | **Don't set**, or a generous few minutes on the app role only | The scenario this project actually has (template1/CREATE DATABASE races, §5 of the failure-modes doc) is exactly a lock-wait case — a short `lock_timeout` would convert "occasionally slow" into "occasionally fails," trading one confusing failure for another. Better addressed by the failure-modes doc's own fix (serialize DB creation) than by timing out the wait |
| `transaction_timeout` (PG17) | **Don't set**, or only on a dedicated CI-agent role at a value well above `idle_in_transaction_session_timeout` | New and blunt — it also bounds *active* transaction time, not just idle time, so it can abort a legitimately long-running migration inside a transaction. Since the shorter of `transaction_timeout` and `idle_in_transaction_session_timeout` wins, setting both to similar values makes one of them pointless; better to lean on `idle_in_transaction_session_timeout` alone for this repo's actual problem (idle time, not active time) |

**Scoping mechanism:** the docs are explicit that `ALTER ROLE ... SET` / `ALTER DATABASE ... SET`
override `postgresql.conf`/command-line settings per session, and any superuser or database owner
can set them (`ALTER DATABASE test SET enable_indexscan TO off;` is the docs' own example pattern —
[ALTER DATABASE](https://www.postgresql.org/docs/17/sql-alterdatabase.html)). **However**, see §3:
in this repo everyone connects as `pguser`, which is the superuser created by the official Postgres
Docker image — role-level `ALTER ROLE ... SET` still works for *timeouts* (timeouts are not exempt
for superusers the way `CONNECTION LIMIT` is, see below), so `ALTER ROLE pguser SET
idle_in_transaction_session_timeout = ...` is viable today without creating a new role. Client-side
(`OPTIONS: {"options": "-c idle_in_transaction_session_timeout=900000"}` in Django's `DATABASES`)
is the least good option here: it would need to be duplicated across `settings_dev.py`, any CI
settings module, and every raw `psql`/one-off script, and does nothing for connections opened by
tools outside Django's control (a bare `psql`, `pgAdmin`, an agent's ad hoc script) — server-side
`ALTER ROLE`/`ALTER DATABASE` covers all of those uniformly with one change.

## 3. Per-role/per-database connection caps and reserved slots — and why they don't help as configured today

- **`ALTER DATABASE ... CONNECTION LIMIT n`** and **`ALTER ROLE ... CONNECTION LIMIT n`** are both
  real, documented (`CREATE ROLE`/`ALTER ROLE`:
  [postgresql.org/docs/17/sql-createrole.html](https://www.postgresql.org/docs/17/sql-createrole.html);
  `ALTER DATABASE`: [postgresql.org/docs/17/sql-alterdatabase.html](https://www.postgresql.org/docs/17/sql-alterdatabase.html)).
  **Both are explicitly documented as not enforced against superusers.** The `CREATE ROLE` docs say
  it in so many words: *"the limit is never enforced for superusers."* The per-database limit
  (`datconnlimit`) carries the same exemption — confirmed via a `postgresql.org` pgsql-hackers
  message-id thread on "Connection limit and Superuser," whose stated rationale is *"having
  superusers be immune to `datconnlimit` is considered the right approach... `datconnlimit` can be
  set by database owners, who should not be able to prevent superuser access to their [own]
  database."* Since `dev_db/docker-compose.yaml` sets `POSTGRES_USER=pguser` (the image's own
  bootstrap superuser, per the official `postgres` image's documented behaviour) and
  `settings_dev.py`'s `DATABASES["default"]["USER"]` is `"pguser"` for every worktree — **every
  connection this repo makes today is a superuser connection, so neither `CONNECTION LIMIT` variant
  does anything here.** This confirms the suspicion flagged in the task.
- **Would a per-database cap even bound one worktree, if `pguser` weren't a superuser?** No, not on
  its own. `branch_to_db_name` gives each worktree its own app DB and its own `test_<db>` base
  name, but `pytest-django` under `-n`/xdist appends `_gwN` per worker, so one worktree's test run
  can span `test_<db>_gw0`, `test_<db>_gw1`, ... — each a *separate database object* with its own
  independent `datconnlimit` (default `-1`, unlimited, unless someone sets it on every dynamically
  created `_gwN` database, which is impractical since the set of names depends on the worker count
  chosen at invocation time). A per-database limit set only on the app DB would leave the `_gwN`
  test databases uncapped. **A per-role limit does span all databases that role connects to**, so
  it is the right primitive for "cap one worktree's total footprint" — but only if that worktree
  has its own role (or at minimum, a role not shared by every other worktree). With today's single
  shared `pguser` for everyone, a role-level cap would bound the *sum of all worktrees* together,
  not any one worktree individually — useful as a global ceiling (like `max_connections` itself,
  which already exists) but not a per-worktree fence.
- **`reserved_connections` (PG16+) and `superuser_reserved_connections`** — both documented at
  [PostgreSQL 17 — Connections and Authentication](https://www.postgresql.org/docs/17/runtime-config-connection.html)
  and explained further by [pganalyze — Postgres 16: Surviving without a superuser &
  reserved_connections](https://pganalyze.com/blog/5mins-postgres-16-superuser-reserved-connections):
  `superuser_reserved_connections` (default 3) reserves slots that only superuser connections may
  use once ordinary slots are exhausted; `reserved_connections` (default 0) does the same for
  members of `pg_use_reserved_connections`. **Confirmed: this repo's setup defeats
  `superuser_reserved_connections` entirely**, exactly as the task suspected — the reserved slots
  exist to guarantee an emergency *admin* connection when the pool is full, but if ordinary
  application/test load also connects as the superuser, that same load can consume the reserved
  slots too, leaving zero guaranteed headroom for a human to get in and run
  `pg_terminate_backend()`.
- **What actually helps, given this constraint:** stop using the bootstrap superuser for ordinary
  traffic. Concretely: create a plain, non-superuser role (e.g. `fls_app`) with `CREATEDB` (needed
  for pytest-django's test-database create/drop cycle — `CREATEDB` does not require superuser) and
  ownership of the per-branch databases, point `settings_dev.py`/`.env` at that role for all
  app/test/Playwright connections, and reserve the actual `pguser` superuser purely for a human's
  emergency `psql`. Once that split exists:
  - `superuser_reserved_connections` (its default of 3 is already fine) starts doing its documented
    job, because superuser connections become rare/manual again.
  - `reserved_connections` + granting `pg_use_reserved_connections` to a distinct "diagnostics" role
    becomes viable as a second, non-superuser escape hatch, if wanting to avoid handing out the
    actual superuser password broadly.
  - `ALTER ROLE fls_app CONNECTION LIMIT n` becomes enforceable and gives a single global ceiling
    on ordinary traffic distinct from `max_connections` (belt-and-suspenders, not a substitute for
    the `max_connections`/memory sizing work in item 2 of the idea doc).
  - **Per-worktree bounding still requires a role per worktree** (or at least a role per class of
    load) if the goal is "one worktree can't eat the whole pool" specifically, rather than "total
    dev load can't eat the whole pool." That is a bigger change (dynamic role creation keyed off
    `branch_to_db_name`, analogous to the existing per-branch database naming) and is noted here as
    a possible future step, not a recommendation to do now — this research doesn't take a position
    on whether that complexity is worth it for a 4–6-worktree scale.

## 4. Django-side settings that reduce or surface leaks

- **`CONN_HEALTH_CHECKS`** (Django docs: [persistent
  connections](https://docs.djangoproject.com/en/6.1/ref/databases/#persistent-connections)) makes
  Django ping a reused connection once per request before trusting it, specifically to catch "the
  database server closed an idle connection Django still thinks is open" — i.e. exactly the
  scenario where a server-side `idle_session_timeout`/`idle_in_transaction_session_timeout` fires
  on a connection Django was about to reuse. **It is irrelevant to `CONN_MAX_AGE=0`** (today's dev
  default per §2 — nothing is reused across requests to health-check), and it is **irrelevant to
  the pytest-runner/main-thread connections described in §2**, since those aren't part of Django's
  request-response health-check path either. It would only start mattering if `CONN_MAX_AGE` were
  raised above `0` in dev/test settings, which nothing in this research recommends.
- **`CONN_MAX_AGE` in tests** — per §2, this setting has no effect on the pytest-runner connection
  or on `transaction=True` tests' main-thread connection, because Django's connection-aging check is
  wired to HTTP request signals that don't fire for direct ORM calls. It's real for the
  `live_server` thread's own connection (already closed per-request by the `CONN_MAX_AGE=0`
  default, and Django ticket #22414's fix already closes it at thread teardown too), but tuning it
  further is not a lever for the leaks this research identified.
- **psycopg `connect_timeout`** (a libpq/psycopg connection *option*, distinct from all five server-
  side timeouts above) bounds how long the *client* waits to establish a new connection — it
  protects a developer/test run from hanging forever trying to connect to a database that's
  wedged/unresponsive (e.g. mid-crash-recovery), not from leaking one once connected. Cheap to set
  (`OPTIONS: {"connect_timeout": 5}`) and has no downside for a dev/test stack; it's a
  fail-fast-on-the-client-side complement to the server-side settings, not a substitute.
- **`application_name`** is the single highest-leverage, lowest-risk change for *diagnosability*
  (direction item 6), independent of any timeout: Django's `OPTIONS` accepts an `application_name`
  key passed straight through to psycopg/libpq, and setting it per worktree (e.g.
  `f"fls-{_db_name}"`, reusing the same `branch_to_db_name` value `settings_dev.py` already
  computes) would make every row in `pg_stat_activity` self-identify which worktree/branch owns it
  — turning the failure-modes doc's own diagnostic query
  (`SELECT usename, application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3...`)
  from "which worktree is this, probably, judging by `client_port`" into an exact answer. This is
  worth doing regardless of which timeout values are chosen, since it makes every other mitigation
  in this document (and in `research_postgres_failure_modes.md`) easier to verify was working.

## Summary of corrections made to prior research

1. **§6's "stays registered until TCP eventually notices... a long time, or never"** is corrected:
   for the ordinary killed-local-pytest-process case, the backend exits within about one round
   trip via FIN propagation (kernel exit path → `docker-proxy` loopback relay → backend's blocking
   read returning EOF), not via TCP keepalive detection. The "long time, or never" framing is
   accurate only for orphaned-but-still-alive clients, host sleep/network partition, or backends
   mid-query — a much narrower set of cases than "every killed test run."
2. **§6's citation of Django ticket #17887** as evidence of pytest-specific idle-in-transaction
   leaking is a stretch: that ticket describes a long-fixed psycopg2 autocommit default causing
   *long-running production processes* to leak, not anything specific to pytest-django's `atomic()`
   test wrapping (which is short-lived and self-resolving by design).
3. Clarified that Django's `CONN_MAX_AGE`/`close_old_connections` machinery is **irrelevant** to
   the pytest-runner and `transaction=True` main-thread connections that are actually at risk here,
   because it only fires on HTTP request signals — narrowing where server-side timeouts are the
   only real lever.

status: ok
