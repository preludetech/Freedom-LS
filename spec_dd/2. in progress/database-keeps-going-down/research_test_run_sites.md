# Research: where the project tells people and agents to run tests

Scope: read-only inventory, this repo only, excluding `.venv/`, `node_modules/`, `.git/`, and
`spec_dd/3. done/`. No web research needed or done. Everything below is cited to a file path (line
numbers where useful); anything not directly evidenced is flagged as inference.

## 1. Every place that invokes pytest (full or targeted), who runs it, how often, concurrency

| File : line | Exact command | Who runs it | How often | Concurrent with other runs in same worktree? | Full suite or targeted? |
|---|---|---|---|---|---|
| `CLAUDE.md:41` | `uv run pytest` | Human developer or agent, ad hoc ("Commands" section) | Whenever anyone chooses to | N/A — whatever the invoker adds (no `-n` baked in) | Full |
| `pyproject.toml:81` (`[tool.pytest.ini_options]` `addopts`) | `--strict-markers -m 'not ci_only and not weasyprint' --disable-socket … --cov …` — **no `-n`, no `--reuse-db`/`--create-db`** | N/A — this is the baseline every invocation above inherits | Every invocation | — | Baseline config only |
| `claude_plugins/django-stack/skills/testing/SKILL.md:45` | `uv run pytest -n auto` | Any human/agent following the **generic `ds:testing` skill**'s "Run the full suite in parallel locally" guidance | Whenever a developer wants a faster local run — no cadence, opt-in | **Yes, by design** — this is the one line in the repo that explicitly recommends one xdist worker per CPU core; nothing caps `auto` | Full |
| `claude_plugins/django-stack/commands/commit.md:4` | `uv run pytest` | `/ds:commit` — human or agent, before every checkpoint commit | Once per "checkpoint" commit (referenced by `sdd/commands/commit_quickly.md:9` as the "full pytest suite first" alternative to `/commit_quickly`) | No — sequential, one gate before commit | Full |
| `claude_plugins/django-stack/commands/rebase_main.md:189,195` | `uv run pytest -x -q` then (after it passes) `uv run pytest -q` | The **rebase hook** — configured in `.claude/sdd/config.md:19` (`Rebase command: claude_plugins/django-stack/commands/rebase_main.md`), followed **before every feature-branch SDD step** (`.claude/sdd/config.md:13-15`), and also Step 0 of `/sdd:finish_worktree` | **Very high** — potentially once per `/sdd:next` step per worktree, i.e. many times per spec | Sequential with itself (runs twice, `-x -q` then `-q`); not run against other worktrees' DBs since each worktree has its own `test_db_<branch>` — but stacks against whatever else that worktree is doing | Full (twice) |
| `claude_plugins/sdd/commands/address_pr_review.md:54` | `uv run pytest -x -q` | `/sdd:address_pr_review` — human/agent, after addressing PR review comments | Once per PR-review round | Sequential | Full |
| `claude_plugins/sdd/commands/implement_plan.md:37,56` | `uv run pytest` (in-batch, run by the batch sub-agent itself); then again via `sdd:sdd-mechanic` in Step 3 "Final Verification" | `/sdd:implement_plan` — depth-0 orchestrator spawns **one sub-agent per batch, sequentially** ("After a batch returns, act on its status… move to the next batch") | Once per plan batch (a plan of N vertical slices = N runs) + 1 final run | **No** — batches run one at a time, not fanned out in parallel (confirmed by the "spawn → act on status → next batch" loop; no "spawn in parallel" instruction here, unlike the generic fan-out recipe) | Full, each time |
| `claude_plugins/fls-dev/agents/qa-bugfixer.md:77,92,101` | `uv run pytest <path>::<test> -x` (Step 2, RED), same (Step 4, GREEN), then `uv run pytest` (Step 5, full suite, no `-x`) | `qa-bugfixer` agent, spawned by `/fls-dev:do_qa`'s triage loop (Step 13) | Once per bug fixed; **capped at 3 fixer spawns per `do_qa` run** (`do_qa.md:471-473`) | **Sequential, not concurrent** — `do_qa.md` Step 13 spawns one fixer, waits for its result, re-verifies, reverts-or-marks-fixed, *then* moves to the next bug (each `Agent` spawn is also required to be "solo," `do_qa.md` Rule 3e). No evidence in this repo of several `qa-bugfixer`s running at once in one worktree — this narrows the `research_current_dev_db_setup.md` §4 inference that "QA can fan several bugfixers out inside one worktree" to **not concurrent, based on how the command is actually written** (three sequential full-suite runs per `do_qa` invocation is still real load, just not simultaneous) | Targeted (x2) + Full (x1) per bug |
| `claude_plugins/fls-dev/commands/do_qa.md:457-504` | (no `pytest` invocation of its own) — references and trusts the fixer's Step 5 run | `/fls-dev:do_qa` orchestrator | — | — | — |
| `claude_plugins/fls-dev/resources/testing.md:39-42`, `skills/testing/SKILL.md:133-136`, `resources/playwright-testing.md:10-13`, `skills/playwright-tests/SKILL.md:20` | `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` | Documentation describing **this repo's own** full run vs. the filtered command **a concrete downstream project** runs | Whenever a developer reads the doc and runs the command | N/A (doc, not an automated trigger) | Full (this repo) / filtered subset (downstream) |
| `claude_plugins/fls-dev/commands/concrete/update_fls.md:148,165,212,235` | `uv run pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` | A **downstream, concrete-implementation project's** own Claude session, following the `update_fls` playbook after pulling in an FLS update (per `commands/concrete/README.md:1`: "for concrete implementations of FLS… typically include FLS as a submodule") | Whenever a downstream project runs `/fls-dev:update_fls` | Runs in the downstream project's own dev DB/worktree — outside this repo's shared Postgres entirely | Filtered subset (excludes `playwright`, `fls_internal`, `ci_only`, `weasyprint`) |
| `.github/workflows/tests.yml:85,134` | `uv run pytest -m "not playwright"` and `uv run pytest -m playwright --no-cov` | GitHub Actions CI, two separate jobs | Once per CI run (push/PR) | Each job gets its **own ephemeral `postgres:17` service container** (per `research_current_dev_db_setup.md` §4) — **not the shared dev Postgres**, so out of scope for a worker cap on the shared server | Full, split into two jobs |
| `claude_plugins/django-stack/commands/tdd_implement.md` | (not read in full; matched `pytest` in earlier grep pass under generic `ds` commands) | `/ds:tdd_implement` | Per TDD cycle | Sequential | Targeted, likely |

**Not a pytest-suite risk (checked and ruled out):**
- `.pre-commit-config.yaml` — hooks are `trailing-whitespace`, `check-yaml`, `check-toml`, `detect-secrets`, `ruff-check`/`ruff-format`, `bandit`, `shellcheck`, and a local `mypy` hook. **No pytest hook.** Confirmed independently by `qa-bugfixer.md:129-130`'s own note ("pre-commit hooks run ruff, mypy, bandit and shellcheck — not pytest").
- `.claude/settings.json:15` — `"Bash(uv run pytest:*)"` is a **permission allow-list entry**, not an invocation site; it just means any of the above commands won't hit a permission prompt.
- `sdd:sdd-worker` (the agent this research file was written by) has **no `Bash` tool at all** (`claude_plugins/sdd/agents/sdd-worker.md:7`: `tools: Read, Glob, Grep, WebFetch, WebSearch, Write`) — the generic SDD fan-out workers used for research/review/spec work **cannot** run pytest, so the parallel-research/parallel-review fan-out pattern (`claude-code-authoring` skill's "spawn in parallel" recipe) is not itself a pytest-concurrency source.
- `sdd:sdd-mechanic` **does** have `Bash` (`claude_plugins/sdd/agents/sdd-mechanic.md:9`) and is the one that runs `uv run pytest` on behalf of `implement_plan.md` Step 3 — but every call site spawns exactly one mechanic solo, never several at once.

## 2. Database create/drop/reset and container-start sites

| File | What it does | Who runs it / when |
|---|---|---|
| `dev_db/docker-compose.yaml` | Defines the single shared `postgres:17` + `mailpit` service; stock defaults (100 connections, no restart policy, no healthcheck) — see `research_current_dev_db_setup.md` §1 for full detail | `docker compose up`, run manually by a developer per `dev_db/README.md:21` |
| `dev_db/README.md:24-29` | Documents the reset path: `./cleanup_devdb.sh` then `docker-compose up` | Manual, developer-run |
| `dev_db/cleanup_devdb.sh` | `docker kill dev_db_dbs_1`, `docker rm dev_db_dbs_1`, `sudo rm -r ./gitignore` — targets a container name modern Compose doesn't produce; likely broken (per `research_current_dev_db_setup.md` §1) | Manual, developer-run |
| `dev_db/docker-entrypoint-initdb.d/create-test-db.sql` | Creates a vestigial single `test_db` at first container bring-up | Automatic, once, at first `docker compose up` |
| `claude_plugins/fls-dev/scripts/dev_db_init.sh` (mirrored at `.claude/fls-dev/scripts/dev_db_init.sh`) | Idempotent `CREATE DATABASE IF NOT EXISTS` for `db_<branch>` and `test_db_<branch>` against the shared container; independently re-derives `branch_to_db_name` in shell | Runs as part of `install_dev.sh`, i.e. **every new worktree setup** |
| `claude_plugins/fls-dev/scripts/dev_db_delete.sh` (mirrored at `.claude/fls-dev/scripts/dev_db_delete.sh`) | `pg_terminate_backend` + `DROP DATABASE IF EXISTS` for both `db_<branch>` and `test_db_<branch>` | **Opt-in only** — runs when `/sdd:finish_worktree` Step 2 executes and `.claude/sdd/config.md`'s **Teardown script** value is non-blank (`claude_plugins/sdd/commands/finish_worktree.md:75-82`) |
| `claude_plugins/fls-dev/scripts/install_dev.sh` (mirrored at `.claude/fls-dev/scripts/install_dev.sh`) | `git submodule update`, `rebuild_after_rebase.sh`, `dev_db_init.sh`, `uv run manage.py migrate` | Configured as `.claude/sdd/config.md`'s **Setup script**, run by the worktree-setup flow (`sdd:git-worktree-setup` overlaid by `fls-dev:git-worktree-setup`) for every new worktree |
| `claude_plugins/django-stack/scripts/db_clear.sh` (mirrored at `.claude/ds/scripts/db_clear.sh` via `ds:init` templates) | `rm -rf "${DB_DATA_PATH}"` — a raw filesystem wipe of the whole Postgres data directory (all worktrees' databases at once), plus `rm -rf media` if present. **Generic `ds` script, not FLS-specific.** No-ops if `DB_DATA_PATH` unset | Manual, developer-run; **destroys every worktree's data**, not just one branch's |
| `claude_plugins/django-stack/templates/wrapper_scripts/db_clear.sh` | Template copy `ds:init` installs as `.claude/ds/scripts/db_clear.sh` | Installed into every project that runs `/ds:init` |
| `.github/workflows/tests.yml` | Ephemeral `postgres:17` service container **per CI job**, ready via `pg_isready` healthcheck (CI-only; not the shared dev container) | Automatic, CI |

No other `install`/`teardown` scripts, and no other `docker compose` mentions were found in `docs/`, `claude_plugins/**` skills, or `.claude/**` beyond the two listed (`claude_plugins/fls-dev/resources/email_templates.md` mentions `docker compose` only in passing re: Mailpit; `claude_plugins/django-stack/scripts/db_clear.sh`'s comment references `dev_db/docker-compose.yaml` for context, not an invocation).

## 3. Plugin distribution: who installs each `claude_plugins/*` directory

| Plugin dir | Manifest name | Portable / product-specific | Who installs it | Effect of editing its pytest guidance/scripts |
|---|---|---|---|---|
| `claude_plugins/django-stack/` | `ds` | **Portable — zero product-specific knowledge, depends on no other plugin** (`django-stack/README.md:3-7`) | **Any** Python/Django/HTMX/Tailwind project via `/ds:init` and `--plugin-dir` | **Directly affects other, unrelated projects.** This is where `-n auto` guidance (`skills/testing/SKILL.md:45`), `commit.md`'s pytest gate, and `rebase_main.md`'s double full-suite run live. A hardcoded worker cap here ships to every project using `ds`, whether or not it shares FLS's dev-Postgres problem. |
| `claude_plugins/sdd/` | `sdd` | **Portable — generic SDD workflow scaffolding** (`sdd/README.md:3-4`), though not yet fully standalone (couples to `fls-dev` naming in `next.md`/`setup_todo_list`) | Any project doing spec-driven development via `/sdd:init` | `implement_plan.md`, `address_pr_review.md`, `commit_quickly.md` here call bare `uv run pytest` (no `-n`) — editing these to add a worker flag or read a config value also ships to every `sdd`-using project. |
| `claude_plugins/fls-dev/` | `fls-dev` | **FLS-specific** — "tied to how *this* product works" (`fls-dev/README.md:3-9`), depends on `sdd` at runtime | Installed **only** where FLS itself is the product being developed: this repo, and (via git submodule, not pip) a "concrete downstream" project that embeds the whole FLS repo tree — see Part 4 | Safe to change freely for this repo's own dev-DB problem. The one exception: `commands/concrete/update_fls.md` and `resources/testing.md`/`playwright-testing.md`'s **filtered command line** (`-m "not playwright and not fls_internal and not ci_only and not weasyprint"`) is prescriptive *for downstream submodule projects*, so changing what that filtered command implies (e.g. adding `-n`) would change downstream's own test run, not this repo's dev DB. |
| `claude_plugins/fls-content/` | `fls-content` | FLS-specific, for course authors (content-authoring conventions, widget reference, markdown conversion) — no pytest-suite guidance for the app itself; its own `validate/tests/test_validator.py` is a self-contained pytest suite for the **content validator tool**, collected in `pyproject.toml:80` (`testpaths = […, "claude_plugins/fls-content"]`) | Course authors working with FLS content trees | Its own tests run as part of this repo's `uv run pytest` (contributing to load), but the plugin's guidance is not test-run guidance for the LMS itself |

**Config-as-alternative-to-hardcoding:** `ds` already has a working per-project config pattern:
`.claude/ds/config.md` (this repo's copy, at repo root) has a `## Rebase Scripts` → `Rebuild script`
key, read by `ds:rebase_main` (`.claude/ds/config.md:25-30`, matching `rebase_main.md:174-178`'s
read of `.claude/ds/config.md`'s `## Rebase Scripts` section) — value blank/absent = skip, so other
`ds`-using projects that never set it see no behaviour change. The **same mechanism could carry a
worker-cap value** (e.g. a new `## Test Execution` → `Pytest worker cap` key, default blank =
today's unbounded `-n auto`/bare-`pytest` behaviour), read by `ds:testing`'s skill guidance and by
`rebase_main.md`'s pytest invocations, and by `sdd`'s `implement_plan.md`/`address_pr_review.md` if
they also read `.claude/ds/config.md` (or a project points them at it via `.claude/sdd/config.md`,
which already has exactly this "read a path from config, blank = skip" shape for its own Setup/
Teardown/Rebase-command keys). This satisfies "must not burden downstream projects" structurally —
the generic plugin files change to *read* a cap, not to *hardcode* one, and FLS's own copies of
`.claude/ds/config.md` / `.claude/sdd/config.md` are the only files that would actually set a
non-default value.

## 4. What ships to downstream via the pip package vs. via git submodule

`pyproject.toml:71-74`:
```
[tool.setuptools.packages.find]
where = ["."]
include = ["freedom_ls*"]
exclude = ["media*", "config*", "static*", "dev_db*", "gitignore*", "node_modules*", "demo_content*"]
```

**The pip/`uv add` package ships only the `freedom_ls` Python package.** `dev_db/` is explicitly
excluded. `conftest.py` (root), `claude_plugins/`, `pyproject.toml` itself, `tests/`, and `docs/` are
not part of `[tool.setuptools.packages.find]`'s include list at all, so none of them install into a
downstream project's `site-packages` via this mechanism. **A downstream project that installs FLS as
a pip dependency gets none of this repo's dev-DB config, pytest config, or Claude plugins — it
brings its own.**

The **only** distribution path that would carry `dev_db/`, root `conftest.py`, `pyproject.toml`'s
`[tool.pytest.ini_options]`, or `claude_plugins/**` is a **git submodule** checkout of the whole FLS
repo — which `claude_plugins/fls-dev/commands/concrete/README.md:1` confirms is how "concrete
implementations of FLS" typically consume it. Even then, a submodule-based downstream project runs
its **own** `docker compose`/dev-Postgres setup and its **own** `pyproject.toml` (evidenced by
`resources/testing.md:39-42`'s explicit downstream-vs-FLS command split: FLS runs the unfiltered
suite, "a concrete downstream project instead runs" the `-m "not playwright and not fls_internal…"`
filtered one against its own settings) — nothing in this repo's `dev_db/` scripts or docker-compose
file is invoked by, or shipped for, that downstream project's own database. **Net: changes to
`dev_db/*`, root `conftest.py`, or `pyproject.toml`'s pytest/xdist settings cannot burden a pip-based
downstream consumer at all (not shipped), and a submodule-based concrete project already runs its own
independent dev-DB stack, so it is not burdened either — provided the change stays inside those
files** and doesn't touch the *generic, portable* `ds`/`sdd` plugin files identified in Part 3, which
**are** shared verbatim with unrelated projects.

## 5. Fan-out width, where discoverable

| Fan-out site | Concurrency | Evidence |
|---|---|---|
| `/fls-dev:do_qa` Step 13 (bugfixer triage loop) | **Sequential, one at a time**, capped at 3 `qa-bugfixer` spawns per run | `do_qa.md:471-473` ("at most three fixer spawns per run"); the per-bug loop text (spawn → wait for `status=` return → re-verify → revert-or-mark-fixed → next bug) has no "spawn in parallel" instruction, unlike the generic recipe; `do_qa.md` Rule 3e requires every `Agent` spawn to be issued "solo" (not batched with other tool calls in the same turn) |
| `/sdd:implement_plan` Step 2 (batch sub-agents) | **Sequential**, one sub-agent per batch, "After a batch returns… move to the next batch" | `implement_plan.md:27-44` |
| Generic SDD fan-out recipe (`spec_from_idea`, review commands, research fan-out) | **Parallel by design** ("spawned in parallel" is recipe step 4), but these spawn `sdd:sdd-worker` (research/review), which **has no `Bash` tool** and therefore cannot run pytest | `claude-code-authoring/SKILL.md:58-71`; `sdd-worker.md:7` |
| A depth-0 command running `sdd:sdd-mechanic` (which does have `Bash` and does run pytest, e.g. `implement_plan.md` Step 3) | Every call site spawns exactly **one** mechanic, never several concurrently | `implement_plan.md:56`, `finish_worktree.md`, `do_qa.md` Step 11/15/17 (all "spawn a solo `sdd:sdd-mechanic`") |

**Correction to the idea's stated assumption:** the idea and `research_current_dev_db_setup.md` §4
flag "QA can fan several bugfixers out inside one worktree" as a contributor to connection pressure.
Reading `do_qa.md`'s actual Step 13 logic, the fan-out is **sequential, not concurrent** — at most one
`qa-bugfixer` (and therefore at most one extra full-suite pytest run) in flight at a time per
`do_qa` invocation, capped at 3 total per run. The real multi-worktree pressure comes from **several
different worktrees each independently running their own rebase-hook / commit-gate / `do_qa` full
suite at the same wall-clock time** (§1's per-worktree cadence), not from concurrency *within* one
worktree's QA loop. This narrows where a worker cap needs to bite: it's the number of xdist workers
*per pytest invocation* and the number of worktrees running pytest *at the same time*, not a
same-worktree agent fan-out width.

---

## Implications

**The minimal set of places a worker cap must reach** (i.e. everywhere a pytest suite can actually
be invoked against the shared dev Postgres, per Part 1):

1. `pyproject.toml`'s `[tool.pytest.ini_options]` `addopts` — the one place that applies to **every**
   invocation below with no further action, if the cap is expressed as a baked-in `-n <N>` (or a
   `-p xdist.plugin` default) rather than left for each caller to add.
2. `claude_plugins/django-stack/skills/testing/SKILL.md:45` — the only line that actively *tells*
   people/agents to run `-n auto` (unbounded). This is the highest-leverage single edit if the cap
   is enforced via `addopts` instead (see 1) — then this line's advice becomes safe by construction
   and only needs its prose updated, not a script change.
3. `claude_plugins/django-stack/commands/rebase_main.md:189,195` — fires before every SDD step, so
   it's the single highest-frequency full-suite trigger in the repo.
4. `claude_plugins/fls-dev/agents/qa-bugfixer.md:101` — full suite, once per bug, up to 3× per QA run.
5. `claude_plugins/sdd/commands/implement_plan.md:37,56` and `address_pr_review.md:54` — full suite,
   once per batch / once per PR-review round.
6. `claude_plugins/django-stack/commands/commit.md:4` — full suite, once per checkpoint commit.

**If the cap is enforced centrally in `pyproject.toml`'s `addopts`** (e.g. a fixed `-n <N>` or a
`--dist`/env-var-driven default), items 3–6 above need **no individual edit** — they all resolve
`uv run pytest` through the same `addopts`, so the fix is one line in one file plus one prose update
to item 2. **If instead the cap must be settable per-project** (so FLS can pick a number appropriate
to "4-6 worktrees at once" without hardcoding that number into a plugin other projects share), the
existing `.claude/ds/config.md` blank-value-means-skip pattern (Part 3) is the fit: a new config key
read by whichever of `ds:testing` / `rebase_main.md` actually issues the pytest command.

**Which of the reachable places are in generic plugins other projects share:**

- `claude_plugins/django-stack/` (`ds`) — **shared.** `skills/testing/SKILL.md`, `commands/rebase_main.md`, `commands/commit.md` all ship verbatim to every project that installs `ds`. Any fix here must be config-driven (default = today's unbounded behaviour) or otherwise inert for a project that hasn't opted in — never a hardcoded FLS-sized number.
- `claude_plugins/sdd/` (`sdd`) — **shared**, but its pytest call sites (`implement_plan.md`, `address_pr_review.md`, `commit_quickly.md`'s reference) call bare `uv run pytest` with no xdist flag already; if the cap lives in `pyproject.toml`'s `addopts` (item 1 above) these sites need no change at all, generic or not.
- `claude_plugins/fls-dev/` (`fls-dev`) — **not shared with unrelated projects** (FLS-specific; the only "downstream" consumer is a submodule-based concrete FLS implementation, which runs its own dev DB anyway per Part 4). `qa-bugfixer.md` is safe to edit freely for this repo's problem.
- `dev_db/*`, root `conftest.py`, `pyproject.toml`'s `[tool.pytest.ini_options]` — **not shipped to any downstream at all** (excluded from the pip package per Part 4, and irrelevant to a submodule-based concrete project's own independent dev-DB stack). These are the safest files to change without triggering the idea's "must not burden downstream projects" constraint — **except** that `pyproject.toml`'s `addopts` is the one file in this list that is also read by the generic-plugin-driven commands in items 3-6 above, so a change there is repo-wide by design, which is exactly the point: it's this repo's own file, not a shared plugin file.

status: ok
