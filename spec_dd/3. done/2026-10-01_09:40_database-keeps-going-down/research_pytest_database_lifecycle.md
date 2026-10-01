# Research: what a test run does to the database, and how to bound it

Scope: pytest-django + pytest-xdist + pytest-playwright mechanics against this repo's shared dev
Postgres 17. Primary sources are pytest-django source, pytest-xdist docs/source, Django source, and
the PostgreSQL 17 manual. Where a claim comes from a tool-mediated fetch (WebFetch summarises a
fetched page/file through a small model rather than returning raw text) rather than a directly
quoted line, it is marked **(paraphrased, verify before quoting in the spec)**. Verbatim-quoted
code/doc text is marked as such.

## Suite-size context (read from this repo, not web research)

- `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`,
  no `-n`/`--reuse-db`/`--create-db` in `addopts`. Deps include `pytest-xdist>=3.8.0`,
  `pytest-django>=4.11.1`, `pytest-playwright>=0.7.2`, `pytest-randomly>=4.1.0`.
- `grep -rn "^def test_\|^    def test_"` under `freedom_ls/` returns **4429 matches across 406
  files**; under `tests/` (the repo's own tooling tests, not app tests) **45 matches across 6
  files**. This overcounts slightly (it also matches nested helper functions literally named
  `def test_...` and parametrize-id helpers), but the order of magnitude is real: **on the order of
  4000+ test functions** in the suite pytest-django manages for this worktree.
- Of those, **50 test functions across 23 files carry `@pytest.mark.playwright`**
  (`grep -rn "pytest\.mark\.playwright" freedom_ls/`) — roughly 1% of the suite. A further two files
  (`freedom_ls/conftest.py`, `freedom_ls/tests/playwright_fixtures.py`) define/re-export the
  `logged_in_page`/`live_server_site` fixtures those tests use.
- `freedom_ls/conftest.py`: `logged_in_page` → `live_server` + `@pytest.mark.django_db(transaction=True)`
  (per the fixture's own docstring in `freedom_ls/tests/playwright_fixtures.py`), i.e. the DB is
  fully flushed (not just rolled back) after every Playwright test, and the live server thread holds
  a second, independent DB connection for the duration of the test.
- `config/settings_dev.py`: `DATABASES["default"]["TEST"]["name"] = f"test_{_db_name}"`, no
  `TEST["TEMPLATE"]` set — Postgres's own default (`template1`) applies implicitly (see §2).
  `CONN_MAX_AGE`/`CONN_HEALTH_CHECKS` are not set in dev, so Django's defaults apply
  (`CONN_MAX_AGE=0`), but that setting governs *request*-scoped connection closing in a running
  server, not what pytest-django does with the one connection a test process opens (see §1).
- `conftest.py` (root) / `freedom_ls/conftest.py` add app fixtures (`mock_site_context`,
  `_isolate_media_root`, etc.) with no direct effect on connection count or DB lifecycle.

## 1. Exact sequence: bare run, `--reuse-db`, `--create-db`, under xdist `-n N`

**Bare run (no flags), single process:**

1. First test that needs `db`/`django_db`/`transactional_db` triggers pytest-django's session-scoped
   `django_db_setup` fixture.
2. `django_db_setup` calls `django.test.utils.setup_databases(verbosity=..., interactive=False,
   aliases=aliases, serialized_aliases=serialized_aliases, **setup_databases_args)` — **verbatim
   from `pytest_django/fixtures.py`** (fetched from `pytest-dev/pytest-django` `main` branch,
   `pytest_django/fixtures.py`): `interactive=False` is always passed, so pytest-django never hits
   Django's interactive "type yes to delete" prompt itself — it decides create-vs-reuse purely via
   `setup_databases_args["keepdb"]`.
3. Because neither `--reuse-db` nor `--create-db` was passed, `django_db_keepdb` and
   `django_db_createdb` are both false, so `keepdb` is **not** set in `setup_databases_args`
   (`if django_db_keepdb and not django_db_createdb: setup_databases_args["keepdb"] = True` —
   verbatim from the same fetch), i.e. Django's default `keepdb=False` path runs: `DROP DATABASE`
   the old test DB if it exists, then `CREATE DATABASE ... TEMPLATE template1` (template unset, see
   §2), then run every migration.
4. At session end, `teardown_databases(db_cfg, verbosity=...)` runs — this is what does the
   `DROP DATABASE`. It only runs when `django_db_keepdb` is false (**paraphrased from the same
   fetch** — `setup_databases`/`teardown_databases` call sites are visible verbatim, the surrounding
   keepdb-gating logic was summarised, not quoted).
5. Django's own `_destroy_test_db` does a plain `DROP DATABASE` with no `WITH (FORCE)` and no
   connection-termination step — **verbatim from `django/db/backends/base/creation.py`** (fetched
   from `django/django` `main`): `cursor.execute("DROP DATABASE %s" % ...)`, connecting from the
   *previous* (non-test) database "because it's not allowed to delete a database while being
   connected to it." If anything still holds a connection to the test DB at that point, this DROP
   fails — Django does not self-heal that with `FORCE` (see §2 for whether PG13's `FORCE` option is
   used anywhere here — it is not, in either Django's or pytest-django's code as fetched).

**`--reuse-db` (no `--create-db`):** `django_db_keepdb=True`, `django_db_createdb=False` →
`setup_databases_args["keepdb"] = True`. Django's `_create_test_db` sees the DB already exists and,
because `keepdb` is true, **returns immediately without dropping/recreating or re-running
migrations** — **paraphrased from `django/db/backends/base/creation.py`**: "if we want to keep the
db, then no need to do any of the below, just return and skip it all." Teardown is also skipped
(`teardown_databases` not called when `keepdb` is true). Net effect: no DDL, no connection to the
`postgres` maintenance DB at all for a `--reuse-db` run that finds an existing, structurally-current
test DB.

**`--create-db` alone (no `--reuse-db`):** per pytest-django's own docs (fetched
`pytest-django.readthedocs.io/en/latest/database.html`): *"Without `--reuse-db`, this flag has no
effect since the database is automatically recreated anyway"* — i.e. `--create-db` only does
something in combination with `--reuse-db`; the bare-run behaviour is already "recreate every time."

**`--reuse-db --create-db` together:** `django_db_keepdb=True` and `django_db_createdb=True` →
the `if django_db_keepdb and not django_db_createdb` guard is false, so `keepdb` is **not** set,
forcing the same drop/recreate/migrate path as a bare run once, but a subsequent bare `--reuse-db`
run (without `--create-db`) will then reuse what this run built. This is pytest-django's documented
"I changed migrations, force a rebuild once" idiom (see §4).

**Under xdist `-n N`:**

- Only worker processes run tests; the controller process does not itself execute
  `django_db_setup`.
- Each worker is suffixed via the `django_db_modify_db_settings_xdist_suffix` fixture:
  `xdist_suffix = getattr(request.config, "workerinput", {}).get("workerid")` then
  `_set_suffix_to_test_databases(suffix=xdist_suffix)`, which sets
  `db_settings["TEST"]["NAME"] = f"{test_name}_{suffix}"` — **verbatim/near-verbatim from
  `pytest_django/fixtures.py`** — producing names like `test_db_<branch>_gw0`,
  `test_db_<branch>_gw1`, ...
- **Each worker independently calls `setup_databases()` with no `parallel=` argument** (confirmed:
  the fetched `pytest_django/fixtures.py` call site does not pass `parallel`, and no call to
  `clone_test_db` appears anywhere in pytest-django's fixtures). Django's `setup_databases` default
  is `parallel=0`, and **only `parallel > 1` triggers `connection.creation.clone_test_db(...)`** —
  **verbatim from `django/test/utils.py`** (fetched `django/django` `main`,
  `django/test/utils.py`): `if parallel > 1: for index in range(parallel): ... clone_test_db(...)`.
  **This corrects an ambiguity in `research_current_dev_db_setup.md` §4**, which described
  pytest-django as giving "each xdist worker … its own DB clone." It is not a clone: each worker
  process runs the *entire* `CREATE DATABASE ... TEMPLATE template1` + *entire migration set*
  independently and from scratch. Django's own `clone_test_db`/`--parallel` mechanism (used by
  `manage.py test --parallel`) is a different, unused-here code path.
- Consequence: `-n N` for the first time (or after `--create-db`) means **N concurrent
  `CREATE DATABASE ... TEMPLATE template1`** calls plus **N concurrent full migration runs**, all
  against the one shared Postgres instance, clustered at the start of the run (workers start near-
  simultaneously and most will hit a DB-needing test quickly under pytest-xdist's default
  load-balancing). This is a materially bigger DDL/connection spike than a single bare `pytest`
  run — it is `research_current_dev_db_setup.md`'s "several worktrees doing that at once contend on
  template1" risk, but **reproduced inside a single worktree's own `-n auto` run**, not only across
  worktrees.
- At teardown, the same happens in reverse: up to N concurrent `DROP DATABASE` calls (each
  connecting to its worker's own non-test DB alias first, per §1's Django source finding).
- **What's left behind if a worker/run is killed:** any worker's test DB whose `teardown_databases`
  never ran survives, named `test_db_<branch>_gwN` — indistinguishable from a normal reuse-db
  leftover except for the `_gwN` suffix. A kill mid-`CREATE DATABASE` leaves a half-created or
  absent DB and, per Django ticket #25406 (below), can leave pytest-django's next run **assuming
  the DB already exists** rather than reporting the real error.

Sources: [pytest-django `database.html`](https://pytest-django.readthedocs.io/en/latest/database.html) · [`pytest_django/fixtures.py`](https://github.com/pytest-dev/pytest-django/blob/main/pytest_django/fixtures.py) (fetched via raw.githubusercontent.com) · [`pytest_django/plugin.py`](https://github.com/pytest-dev/pytest-django/blob/main/pytest_django/plugin.py) · [Django `db/backends/base/creation.py`](https://github.com/django/django/blob/main/django/db/backends/base/creation.py) · [Django `test/utils.py`](https://github.com/django/django/blob/main/django/test/utils.py) · [Django `db/backends/postgresql/creation.py`](https://github.com/django/django/blob/main/django/db/backends/postgresql/creation.py) · [Django `db/backends/base/base.py`](https://github.com/django/django/blob/main/django/db/backends/base/base.py) · [Django `db/backends/postgresql/base.py`](https://github.com/django/django/blob/main/django/db/backends/postgresql/base.py)

## 2. Reality check on "template1 contention" — is failure mode #5 real, overstated, or wrong?

**Which maintenance DB does Django use?** Not `template1` directly. `_nodb_cursor()` connects with
`{**self.settings_dict, "NAME": None}` — **verbatim from `django/db/backends/base/base.py`** — and
the PostgreSQL backend's `get_connection_params` substitutes, **verbatim from
`django/db/backends/postgresql/base.py`**: `elif settings_dict["NAME"] is None: # Connect to the
default 'postgres' db. ... conn_params = {"dbname": "postgres", **settings_dict["OPTIONS"]}`. So
every `CREATE DATABASE`/`DROP DATABASE` Django issues is executed from a connection to Postgres's
`postgres` maintenance database, **not** `template1`. Nothing in this stack (Django, pytest-django,
the `dev_db_init.sh`/`dev_db_delete.sh` scripts per `research_current_dev_db_setup.md` §3) opens a
persistent connection to `template1` itself.

**Is `template1` still involved, and does WAL_LOG remove the contention?** Yes to the first,
no to the second. `config/settings_dev.py` never sets `DATABASES["default"]["TEST"]["TEMPLATE"]`,
and Django's Postgres creation code only adds a `WITH TEMPLATE ...` clause when
`test_settings.get("TEMPLATE")` is set — **verbatim from `django/db/backends/postgresql/creation.py`**
(fetched): `suffix = self._get_database_create_suffix(template=source_database_name)` where
`source_database_name` comes from that settings key. With it unset, the bare `CREATE DATABASE
test_db_<branch>` statement Django issues falls through to **Postgres's own default**, which the
PostgreSQL 17 manual states explicitly, **verbatim** (`postgresql.org/docs/17/sql-createdatabase.html`):
*"By default, the new database will be created by cloning the standard system database
`template1`."* On the `STRATEGY` question, the same page states, **verbatim**: *"If the `WAL_LOG`
strategy is used, the database will be copied block by block and each block will be separately
written to the write-ahead log. This is … the default."* Critically, the manual's restriction on
concurrent access is stated **without** carving out an exception for `WAL_LOG`, **verbatim**:
*"no other sessions can be connected to the template database while it is being copied.
`CREATE DATABASE` will fail if any other connection exists when it starts; otherwise, new
connections to the template database are locked out until `CREATE DATABASE` completes."*
**WAL_LOG (the PG15+/PG17 default here) only changes the I/O/checkpoint cost of the copy, not the
exclusivity rule.** `research_postgres_failure_modes.md` §5 is therefore **correct that the failure
mode is real**, and the "not overstated" call should be sharpened: this is not primarily an
*I/O-load* problem, it is a **narrow but genuine race** — the *first* backend to start
`CREATE DATABASE ... TEMPLATE template1` wins; any other backend whose own `CREATE DATABASE` against
`template1` starts while the first is still mid-copy gets the exact
`source database "template1" is being accessed by other users` error the existing research
predicted, and (per §1 above) this can now happen from **N pytest-xdist workers in one worktree**
racing each other, not only from separate worktrees.

**Complete fix, not just mitigation:** the existing research's suggested mitigations ("avoid
connecting anything to `template1` directly," "serializing test-DB creation," "using
`template0`/a lighter creation flow") undersell how completely `template0` fixes this. PostgreSQL
marks `template0` with `datallowconn = false` by default specifically so nothing can ever connect
to it, **paraphrased from PostgreSQL docs on template databases**: *"template0 is normally marked
`datallowconn = false` to prevent it being connected to (and thus modified)."* Because *no* session
can ever be connected to `template0`, `CREATE DATABASE ... TEMPLATE template0` **cannot** race —
the "any other connection exists" check is structurally always false. Setting
`DATABASES["default"]["TEST"]["TEMPLATE"] = "template0"` in `config/settings_dev.py` (the settings
key Django's Postgres creation code already reads, per the source fetch above) removes this failure
mode outright rather than reducing its odds, with no other observed trade-off (both `template0` and
`template1` are near-identical, empty, encoding-only databases for a fresh Postgres 17 cluster).

**DROP DATABASE side (teardown / `--create-db` re-run):** Django's plain `DROP DATABASE` (§1) fails
if any connection remains on the *target* test DB — this is the *other* "being accessed by other
users" message in `research_postgres_failure_modes.md` §5, for the target DB rather than the
template. PostgreSQL 13+'s `DROP DATABASE ... WITH (FORCE)` exists precisely for this
(**paraphrased from EDB/community sources**: it sends the equivalent of `pg_terminate_backend()` to
every session on the target DB, waits briefly, then drops it — it still fails if a backend won't die
within about 5 seconds or if there are prepared transactions/replication slots on that DB), but
**neither Django's core `_destroy_test_db` nor pytest-django's teardown path uses it** (confirmed:
no `FORCE`/`WITH (FORCE)` string appears in the fetched `creation.py` sources). Django's own
documented behaviour when `_create_test_db` hits *any* error (including this one on the previous
run's leftover connection) is to assume the DB already exists and prompt to delete it — Django
ticket [#25406](https://code.djangoproject.com/ticket/25406) is exactly this: *"`_create_test_db`
hides errors like 'source database "template1" is being accessed by other users' with `--keepdb`"* —
**confirming, not merely citing, the existing research's concern that this error class is
mis-reported rather than surfaced cleanly.**

**Conclusion:** failure mode #5 in `research_postgres_failure_modes.md` is **real, correctly
diagnosed, and (with the WAL_LOG detail added here) slightly *understated* as a pure "I/O load"
problem** — it is a genuine exclusivity race on `template1`, now shown to be triggerable by a single
worktree's own `-n auto` run, not only by concurrent worktrees. It has a complete, one-line fix
(`TEST["TEMPLATE"] = "template0"`) that the existing research gestured at but did not confirm as a
full fix rather than a partial mitigation.

Sources: [PostgreSQL 17 `CREATE DATABASE`](https://www.postgresql.org/docs/17/sql-createdatabase.html) · [PostgreSQL `manage-ag-templatedbs`](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html) · [Django ticket #25406](https://code.djangoproject.com/ticket/25406) · [PostgreSQL 13 DROP DATABASE FORCE (EDB)](https://www.enterprisedb.com/postgres-tutorials/postgresql-13-new-feature-drop-database-forcefully) · [depesz — Waiting for PostgreSQL 13: DROP DATABASE force](https://www.depesz.com/2019/11/16/waiting-for-postgresql-13-introduce-the-force-option-for-the-drop-database-command/) · Django/psycopg source links in §1.

## 3. Ways to cap workers, and their trade-offs

- **`-n N` baked into `addopts` forces xdist on *every* invocation**, including a single targeted
  test (`pytest path::test_foo`) — xdist has no concept of "too few tests to bother," so an
  `addopts`-level `-n 8` means a one-test run still spawns 8 worker processes, each of which (per §1)
  independently runs `django_db_setup` the moment that one test needs the DB — i.e. **one test could
  trigger 8× the `CREATE DATABASE`+migrate cost of a plain run** if the test needing the DB is the
  first one any worker picks up, or at minimum pays 8 process-startup costs for a test that gains
  nothing from parallelism. This is the concrete cost the idea's item 4 is warning about, and it is
  why a fixed `-n N` in `addopts` is the wrong lever — it cannot distinguish "a developer ran the
  whole suite" from "a developer/agent ran one test."
- **`-n auto` vs `-n logical`:** per pytest-xdist's own docs (fetched
  `pytest-xdist.readthedocs.io/en/stable/distribution.html`), *"`-n auto`: Uses as many processes as
  your computer has physical CPU cores,"* while *"`-n logical`: Uses the number of logical CPU
  cores instead"* (needs `psutil`; falls back to `auto`'s behaviour if absent) — **paraphrased**.
  Neither is aware of how many *other* worktrees/agents are running on the same machine, so neither
  bounds total load across worktrees by itself.
- **`--maxprocesses`** caps the worker count regardless of `-n`'s value — **paraphrased from
  pytest-xdist docs**: "limit[s] the maximum number of workers to process the tests." This is a
  hard ceiling but, like `-n N`, is typically supplied on the command line/`addopts`, so it shares
  the "forces xdist even for one test" problem unless it is only ever passed alongside an explicit
  `-n`.
- **`PYTEST_XDIST_AUTO_NUM_WORKERS` env var** changes what `-n auto`/`-n logical` *mean*, without
  requiring a command-line flag change — **paraphrased**: "set the environment variable … to the
  desired number of processes." It only takes effect when `-n auto`/`-n logical` is actually passed;
  it has no effect on a plain `pytest` invocation with no `-n` at all, so it does not carry the
  "forces xdist for one test" cost.
- **`pytest_xdist_auto_num_workers(config)` hook** — confirmed to exist, documented since
  pytest-xdist 3.0.2 (per the changelog/issue history found; **not independently verified against
  the changelog text itself, flagged unverified on the exact version**). Implemented as a
  `conftest.py` function; **paraphrased from pytest-xdist docs**: it "can examine
  `config.option.numprocesses` to determine user intent" (i.e. whether `"auto"` or `"logical"` was
  requested) "and can return `None` to fall back to the default." Precedence, **paraphrased**: "the
  hook takes priority" over `PYTEST_XDIST_AUTO_NUM_WORKERS`, which takes priority over `-X
  cpu_count`, which takes priority over `PYTHON_CPU_COUNT`. Like the env var, **this hook is only
  consulted when `-n auto`/`-n logical` is requested** — it does not fire for a bare `pytest` (no
  `-n`) or for an explicit `-n 4`.

**Which approach bounds every invocation without penalising single-test runs or leaking to
downstream projects:**

1. **Never put `-n`/`--maxprocesses` in `addopts`.** Leave xdist fully opt-in, so a single-test run
   pays zero xdist/worker-DB cost, matching current behaviour and the idea's "developer running a
   single worktree should notice nothing" constraint.
2. **Cap what `-n auto` means, in this repo's own `conftest.py`, via
   `pytest_xdist_auto_num_workers(config)`** (or, more simply, an `os.environ.setdefault
   ("PYTEST_XDIST_AUTO_NUM_WORKERS", "<N>")` at the top of the root `conftest.py`, so it applies
   whether a developer/agent types `-n auto` by hand or a documented command does). Either way, the
   cap only engages when someone actually asks for auto-parallelism — it cannot slow down or affect
   a bare `pytest` or `pytest path::test_foo` run, and it costs nothing when `-n` isn't used at all.
3. **This is safe for downstream FLS installs.** `pyproject.toml`'s
   `[tool.setuptools.packages.find]` is `where = ["."]`, `include = ["freedom_ls*"]`, with an
   `exclude` list covering `media*, config*, static*, dev_db*, gitignore*, node_modules*,
   demo_content*` — **the include filter alone already means only packages matching `freedom_ls*`
   are collected into the built wheel/sdist**; the root `conftest.py` and `pyproject.toml` are not
   Python packages under that glob and are not shipped as importable code to a project that installs
   `freedom_ls` as a dependency. A downstream project's own `pytest` run never imports this repo's
   root `conftest.py` or reads its `[tool.pytest.ini_options]`, so a `pytest_xdist_auto_num_workers`
   hook (or an `addopts` change) placed there cannot affect them.
4. Document the cap alongside the existing `-n auto` guidance
   (`claude_plugins/django-stack/skills/testing/SKILL.md:45`, cited in
   `research_current_dev_db_setup.md` §4) so humans and agents see the same number; this satisfies
   the idea's "everywhere the project tells people or agents to run the suite," since the cap is
   enforced in code (the hook/env-var) rather than relying on every doc/skill/agent remembering to
   type `-n 4` instead of `-n auto`.

Sources: [pytest-xdist `distribution.html`](https://pytest-xdist.readthedocs.io/en/stable/distribution.html) · [pytest-xdist issue #792 — env var for auto](https://github.com/pytest-dev/pytest-xdist/issues/792) · [pytest-xdist issue #1102 — hook conditional definition](https://github.com/pytest-dev/pytest-xdist/issues/1102) · [pytest-xdist changelog](https://pytest-xdist.readthedocs.io/en/latest/changelog.html) · `pyproject.toml` (this repo, read directly).

## 4. `--reuse-db` trade-off

- **Speed gain:** confirmed in §1 — a successful `--reuse-db` run with no `--create-db` does zero
  `CREATE DATABASE`/`DROP DATABASE`/migration work; it opens the existing test DB and runs tests
  directly. For a ~4000-test suite (§ suite-size context) with hundreds of migrations, this removes
  the single biggest DDL burst pytest-django performs against the shared Postgres instance.
- **Staleness:** pytest-django's own docs state this plainly, **verbatim** (fetched
  `pytest-django.readthedocs.io/en/latest/database.html`): *"`--reuse-db` will not pick up schema
  changes between test runs."* **Confirmed: there is no migration-detection mechanism** — pytest-django
  does not hash migration state or compare it against the kept DB; it purely branches on the
  `keepdb`/`createdb` command-line flags (§1). The documented recovery is running once with
  `--reuse-db --create-db` (§1) to force a rebuild, then reverting to plain `--reuse-db`.
- **Interaction with rebasing worktrees:** because staleness detection doesn't exist, a worktree
  that rebases in new migrations and then runs `pytest --reuse-db` will run every test against a
  test DB whose schema predates those migrations — tests can fail with "column/table does not
  exist" errors that have nothing to do with the code under test, or (worse, for additive-only
  migrations that don't get exercised) silently pass while not actually validating the new schema.
  `claude_plugins/django-stack/commands/rebase_main.md` Step 9 (per
  `research_current_dev_db_setup.md` §4) runs plain `uv run pytest -x -q` / `uv run pytest -q` with
  **no `--reuse-db` at all**, so the rebase-triggered full-suite runs this repo already has in place
  are unaffected by this staleness risk — but any future doc/skill that suggests `--reuse-db` as a
  default for speed would need to pair it with "run `--reuse-db --create-db` once after a rebase
  that touched migrations," which is a manual step, not automatic. **Is `--reuse-db` +
  auto-`--create-db`-on-migration-change a known pattern?** Not as a built-in pytest-django feature
  (confirmed by the absence of any such flag/behaviour in the fetched docs); it is a documented
  *manual* idiom (run the two-flag combo once), and some third-party wrapper scripts implement an
  automatic version by hashing `migrations/` directories, but pytest-django itself does not ship one.
- **Django's `--keepdb` equivalent:** this *is* Django's `--keepdb` — pytest-django's `--reuse-db`
  maps directly onto Django's `manage.py test --keepdb` flag/`keepdb=True` kwarg (§1's
  `setup_databases_args["keepdb"] = True"` finding). There is no separate "Django equivalent" to
  look for; they are the same underlying mechanism.
- **Does reusing the DB reduce load materially for this suite?** Yes, for the DDL/connection-spike
  cost specifically: it eliminates the `template1`-race window in §2 entirely for any run that
  doesn't need `--create-db`, and eliminates the "N workers each migrate from scratch" cost under
  xdist (§1) for every run after the first. It does **not** reduce the steady-state connection count
  during the test run itself (§6) — that is driven by how many workers/live-servers are open while
  tests execute, not by whether the DB was freshly built.

Sources: [pytest-django `database.html`](https://pytest-django.readthedocs.io/en/latest/database.html) · `claude_plugins/django-stack/commands/rebase_main.md` (read via `research_current_dev_db_setup.md` §4 citation) · §1/§2 above.

## 5. Playwright + xdist

- **live_server per worker:** pytest-django's `live_server` fixture is per-test-process; under
  xdist each worker process gets its own `live_server` instance bound to its own ephemeral port on
  `127.0.0.1`, pointed at that worker's own (suffixed) test database. **Paraphrased from general
  pytest-xdist/pytest-django integration behaviour** (no single canonical doc page fetched
  confirming this exact sentence; consistent with §1's finding that each worker is an independent
  process with its own DB alias) — flagged **unverified against a primary source**, though it
  follows directly from `live_server` being function/session-scoped per test *process* and
  pytest-xdist workers being separate OS processes.
- **Connections per worker:** per `freedom_ls/tests/playwright_fixtures.py`'s own module docstring
  (read directly, not web research): the existing E2E suite uses
  `@pytest.mark.django_db(transaction=True)` specifically because `logged_in_page` needs the
  `live_server` thread (a separate DB connection from the test's own thread) to see data the test
  set up — "the live server thread holds its own DB connection separate from the test thread's
  connection." That is at least **2 connections per running Playwright test**, for its duration, on
  top of whatever the worker's own steady-state connection is (§1, §6).
- **`transaction=True` flush cost:** the same docstring states plainly, **quoted directly from the
  file**: *"`transaction=True` makes pytest-django flush the entire database at the end of every
  test."* This is a full-table `TRUNCATE`/flush per Playwright test, not a rolled-back transaction —
  materially more DB work per test than the ~50 non-Playwright tests' ordinary `django_db` rollback,
  though it is the correct trade-off given the live-server-thread visibility requirement (per the
  same file's own reasoning against a session-scoped `storage_state` alternative).
- **Known issues found:** general web guidance (not project-specific, **paraphrased, low
  confidence — no pytest-playwright/pytest-xdist issue tracker item was directly fetched**) notes
  that pytest-playwright is "parallel-ready" with xdist and each worker gets its own browser
  process/contexts, and that shared mutable state (e.g. a single `storage_state` file written by one
  worker and read by another) is the main documented pitfall — not applicable here since
  `logged_in_page` is function-scoped and UI-logs-in fresh every test (per the fixture's own
  docstring, already read directly above), specifically because a session-scoped `storage_state`
  fixture was tried and rejected for exactly this repo's `transaction=True` flush behaviour.
- Net effect for the connection budget (§6): the ~50 Playwright-marked tests are a small fraction of
  the suite, but each one, wherever it lands under `-n auto`, is worth roughly 2× an ordinary test's
  connection footprint while it runs, plus a full-database-flush's worth of extra write I/O at
  teardown.

Sources: `freedom_ls/tests/playwright_fixtures.py` (read directly, this repo) · [pytest-playwright test-runners doc](https://playwright.dev/python/docs/test-runners) · general web search results on pytest-playwright/xdist (paraphrased, no single authoritative issue found — treat as low-confidence colour, not a citable fact).

## 6. Rough connection budget per worktree

All rows are **for one worktree** against the shared Postgres instance (default `max_connections =
100`, per `research_current_dev_db_setup.md` §1); multiply by the number of concurrently active
worktrees for the shared-server total, per that document's §6 estimate (13+ sibling worktrees
observed). "Sustained" = held open for the run's duration; "peak spike" = brief, at DB
create/migrate/drop boundaries.

| Scenario | Sustained connections | Peak spike | Why |
|---|---|---|---|
| Single targeted test, no `-n`, no DB | 0 | 0 | Test never requests `db`/`django_db` fixture |
| Single targeted test, no `-n`, uses `db` | 1 | 2 (during `CREATE`/migrate or `DROP`) | One process, one `default`-alias connection (§1); brief `_nodb_cursor` connection to `postgres` maintenance DB at setup/teardown |
| Single targeted test, no `-n`, Playwright-marked | 2 | 3 | + `live_server` thread's own connection (§5) |
| Single targeted test, **`-n 8` baked into `addopts`** | up to 8 | up to 16 | Every one of the 8 workers independently runs `django_db_setup` (§1/§3) even though only one test executes — this is the exact cost the idea's item 4 is warning about |
| Full serial suite, bare `pytest` (no `-n`) | 1 (2 briefly during the ~50 Playwright tests) | 2–3 at start (`CREATE`+migrate) and end (`DROP`) | One process for ~4000+ tests (§ suite-size); Playwright tests run one at a time |
| Full serial suite, `--reuse-db` | 1 (2 briefly during Playwright tests) | 0 extra | No `CREATE`/`DROP`/migrate at all (§4) |
| Full suite, `-n 8` (first run / after `--create-db`) | ~8 (up to ~10 while any of the 8 workers is mid-Playwright-test) | **up to ~16** at start (8× `CREATE DATABASE ... TEMPLATE template1` + migrate) and **up to ~16** at end (8× `DROP DATABASE`) | Each worker independently creates+migrates its own DB from scratch (§1); this is also the window where the `template1` race in §2 can actually fire, from this worktree's own workers alone |
| Full suite, `-n 8`, `--reuse-db` (steady state) | ~8 (up to ~10 during Playwright tests) | ~0 extra (no `CREATE`/migrate/`DROP`) | Fastest and lowest-spike combination; still holds 8 sustained connections for the run's duration |
| Full suite, `-n auto` on a 16+-core dev box, no cap | up to 16+ | up to ~32 at start/end | Matches `research_current_dev_db_setup.md` §6's "8-16 simultaneous connections from one worktree alone," now shown to double at the create/drop boundary specifically because of §1's per-worker migrate finding |

**Reading the table against the idea's item 4:** capping `-n auto` (§3) mainly caps the *sustained*
and *peak* rows' worker count directly (e.g. pinning it to 4 turns the last two rows' "16+/32" into
"4/8"); it does **not** by itself remove the `--reuse-db` staleness risk (§4) or the `template1` race
(§2) — those need their own fixes (an explicit `TEST["TEMPLATE"] = "template0"`, and a documented
"force a rebuild after a migration-bearing rebase" step) even after workers are capped.

status: ok
