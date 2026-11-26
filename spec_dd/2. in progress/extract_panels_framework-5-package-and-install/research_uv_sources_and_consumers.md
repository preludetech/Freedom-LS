# Research: uv sources, the live-edit loop, and what each consumer needs

Question: what lets FLS developers edit the panel framework live while the committed
`pyproject.toml` / `uv.lock` resolve in CI, Docker and downstream projects?

Verdict up front: **the earlier claim ("a gitignored `uv.toml` override is the simplest") is wrong.**
`tool.uv.sources` cannot be set from `uv.toml`, and a `uv.toml` would also shadow the whole
`[tool.uv]` table in `pyproject.toml`. There is no uv-native, uncommitted way to swap one dependency's
source. The live-edit loop has to be an editable install layered on top of the synced venv.

## 1. What uv can and cannot override (web findings)

| Mechanism | Can it swap a dependency to a local path without a committed edit? |
| --- | --- |
| `uv.toml` (project, user `~/.config/uv/uv.toml`, system) | **No.** The settings reference shows `sources` and `override-dependencies` as `pyproject.toml`-only (`override-dependencies` is read "only from the pyproject.toml at the workspace root"). Only `no-sources` and `config-settings` are valid in both files. Worse: "`uv.toml` files take precedence over `pyproject.toml` files", so a project-level `uv.toml` makes uv ignore the `[tool.uv]` table entirely. |
| `UV_*` env vars | **No** env var sets a source. `UV_NO_SOURCES` only turns the table off (the opposite of what we want); `UV_NO_SYNC`, `UV_FROZEN`, `UV_LOCKED`, `UV_ENV_FILE` exist. |
| `--no-sources` | Ignores the whole `[tool.uv.sources]` table for a command. Not a per-package swap. |
| Edit `[tool.uv.sources]` to a path in `pyproject.toml` | Works, but is a committed edit; `uv lock` then records a path source, and `uv lock --locked` / `uv sync --locked` fails on any machine where the file and lock disagree. Not an "override". |
| Workspace member | Needs `[tool.uv.workspace]` and `workspace = true` source in the committed `pyproject.toml`, and the lock records it as a member. A committed change again, and the docs' examples only show members under the root. |
| `override-dependencies` | Overrides version *specifiers*, not sources, and is pyproject-only. Not useful. |
| `uv run --with-editable PATH <cmd>` | **Yes, per command.** Overlays an editable install in an ephemeral layer; does not touch the project venv or `uv.lock`. Must be typed on every invocation. (Flag is in the `uv run` CLI reference; not fetched this run.) |
| `uv pip install -e PATH` after `uv sync` | **Yes, persistent in the venv.** Touches neither `pyproject.toml` nor `uv.lock`, so `uv lock --locked` still passes. Undone by the next exact `uv sync` (see below). |
| `PYTHONPATH=/path/to/panel_framework_repo` | Yes, and independent of uv entirely (source dir precedes site-packages). Silent shadowing is the risk. Not a uv doc feature; included as the last-resort fallback. |

Behaviour of sync with a divergent venv (docs: "Syncing the environment"):
- `uv sync` is **exact** by default: it removes packages not selected, and it re-installs a package
  whose locked source differs from what is installed, so an editable install of
  `django-panel-framework` is replaced by the locked git copy. `uv sync --inexact` keeps *extra*
  packages but still installs the *locked* version of ones it manages, so it does not preserve our
  editable either.
- `uv run` syncs **inexact** by default before running, with the same expectation. **Unverified,
  needs a 5-minute spike:** whether `uv run` reverts a hand-installed editable copy of a locked git
  package. Assume it does. `UV_NO_SYNC=1` / `uv run --no-sync` ("skip updating the environment")
  stops it.
- `--locked` only checks lock-versus-`pyproject.toml`. An out-of-band `uv pip install -e` is
  invisible to it, so the lock stays clean. `--frozen` skips even that check.
- Consequence: the editable link is **per-venv state**, not repo state. It must be re-applied after
  every `uv sync` (the FLS `rebuild_after_rebase.sh` runs `uv sync` on every rebase).

References:
- https://docs.astral.sh/uv/concepts/configuration-files/ (uv.toml precedence, merge order)
- https://docs.astral.sh/uv/reference/settings/ (sources/override-dependencies are pyproject-only; no-sources both)
- https://docs.astral.sh/uv/reference/environment/ (UV_NO_SYNC, UV_NO_SOURCES, UV_LOCKED, UV_FROZEN, UV_ENV_FILE)
- https://docs.astral.sh/uv/concepts/projects/sync/ (exact vs inexact, --locked vs --frozen)
- https://docs.astral.sh/uv/concepts/projects/dependencies/ (git/path/editable source syntax, `--no-sources`)
- https://docs.astral.sh/uv/concepts/projects/workspaces/ (workspace sources, editable members)

## 2. Recipe and fallback for the FLS dev loop

Recipe (committed state is the git tag; the editable link is local state):

1. `uv sync` (installs the locked git copy of the framework).
2. `uv pip install --no-deps -e "$PANEL_FRAMEWORK_DIR"` (default
   `/home/sheena/workspace/lms/django_apps/panel_framework`; skip with a message if the directory is
   missing, so CI-like clones and contributors without the repo still work).
3. Keep `uv run` from reverting it: `UV_NO_SYNC=1` in the developer's shell/direnv, and in agent
   sessions via the Claude Code settings `env` block (a per-machine file, not committed), or
   `uv run --no-sync`. Pytest invoked through `uv run pytest` honours it.

Trade-offs: no committed change, lock stays valid, one edit is live in every worktree that did step 2.
Costs: step 2-3 must be redone after `uv sync`; with `UV_NO_SYNC=1` a teammate's new dependency is
not picked up until an explicit `uv sync` (then redo step 2); local tests can pass against the editable
copy while CI uses the tag, so **the tag must be cut and the FLS pin bumped before merging** (a CI job
or pre-merge check that fails when the installed `panel_framework` is not the locked rev would close it).

Fallbacks, in order: (a) `uv run --with-editable "$PANEL_FRAMEWORK_DIR" pytest ...` for one-off
runs; (b) `PYTHONPATH="$PANEL_FRAMEWORK_DIR"` exported in the worktree environment, which survives
`uv sync`/`uv run` untouched (pure-Python package, templates and static found via the module path);
(c) temporarily edit the pin to a path and never commit it (rejected: breaks `--locked`, easy to commit).

## 3. FLS worktrees

- Worktrees live as siblings under `/home/sheena/workspace/lms/freedom-ls-worktrees/<branch>`
  (`main` here). The sdd Setup script is bound to `.claude/fls-dev/scripts/install_dev.sh`, which
  calls `rebuild_after_rebase.sh`, which runs `uv sync`, `npm i`, `npm run tailwind_build`, then
  `dev_db_init.sh`. (Source: `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md`,
  `scripts/install_dev.sh`, `scripts/rebuild_after_rebase.sh`.) `claude_plugins/fls-dev` is where
  the link step belongs, as an FLS-specific addition (generic `sdd`/`ds` must not name it).
- Relative path from a worktree root to the package repo: `../../django_apps/panel_framework`
  (worktree -> `freedom-ls-worktrees` -> `lms` -> `django_apps/`). It holds only because every
  worktree is exactly two levels below `lms/`. Do not rely on it: resolve an env var
  `PANEL_FRAMEWORK_DIR` (absolute, defaulting to that path) in the one script, and add the
  `uv pip install -e` line right after `uv sync` in `rebuild_after_rebase.sh` so rebases re-link.
- Nothing in `pyproject.toml` needs to name the path, so there is no per-worktree edit.

## 4. CI, Docker, infra

- `.github/workflows/tests.yml`: every job is `actions/checkout@v6` -> `astral-sh/setup-uv@v7` ->
  `uv sync` (no `--locked`). GitHub runners have `git`, so a **public** repo over HTTPS needs no
  change. A **private** repo needs credentials: a read-only deploy key via an ssh-agent step, or a
  token plus `git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf
  "https://github.com/"`. Prefer a committed HTTPS URL (the lock records the URL, never the token);
  an `ssh://` URL forces keys on every consumer. Recommend adding `--locked` to CI `uv sync` so a
  stale lock fails loudly.
- FLS has no Dockerfile. The deploy image is built from
  `/home/sheena/workspace/lms/freedom_ls_infra/fls-base/Dockerfile`: `python:3.13-slim` with
  `apt-get install libpq-dev gcc gosu` (**no `git`**), and `uv pip install --system -r
  pyproject.toml` with only `pyproject.toml` copied. Two consequences: it needs `git` added to the apt
  line, and `-r pyproject.toml` reads `[project.dependencies]` only, so a git pin expressed in
  `[tool.uv.sources]` would be ignored there while a PEP 508 `name @ git+https://...@tag` is honoured.
- The concrete template's Dockerfile (`freedom-ls-concrete-template/Dockerfile`) runs `uv sync
  --frozen --no-install-project --no-install-package freedom_ls` in a `ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim` stage. That phase would now fetch the git
  dependency, so it needs `git` in the image (the slim uv image is not known to ship it: verify) and,
  for a private repo, a BuildKit secret mount for the token.

## 5. Concrete projects (First-Class, template) and FLS packaging

- Both pin FLS identically: `[tool.uv.sources] freedom_ls = { path = "submodules/Freedom-LS",
  editable = true }`, `testpaths` includes the submodule, CI uses `submodules: recursive`.
- **Transitive resolution is the critical point.** The uv docs describe `tool.uv.sources` as part of the
  *project's own* development metadata; for anything consuming a project as a dependency, only
  `project.dependencies` / `optional-dependencies` are used (workspace docs state root-level sources
  cascade only to *members*). The published-metadata behaviour of a path dependency's sources was not
  stated in a doc I could fetch, so treat as **very likely, to be confirmed in the same 5-minute
  spike**: First-Class resolving `freedom_ls` from the submodule path will NOT apply FLS's
  `[tool.uv.sources]`. A bare `django-panel-framework>=0.3` in FLS's dependencies plus a sources
  entry would therefore make First-Class look it up on PyPI and fail. Fix: FLS declares it as a
  PEP 508 direct reference in `[project].dependencies`:
  `"django-panel-framework @ git+https://github.com/<org>/django-panel-framework.git@v0.3.0"`. Those
  are part of the metadata, so they follow transitively. (This is a uv-ism-free way to get the same
  result in pip, in `uv pip install -r pyproject.toml`, and in downstream projects.) A concrete
  project that wants a different pin or a local checkout can still add its own
  `[tool.uv.sources]` entry at its root.
  Each concrete project's `uv.lock` will then contain the git rev; bumping the tag in FLS moves it
  on the next `uv lock --upgrade-package django-panel-framework` in that project, or via the existing
  update flow.
- **FLS is a package, loosely.** `pyproject.toml` has `[project]` and `[tool.setuptools.packages.find]
  (include = ["freedom_ls*"])` but **no `[build-system]`**, so uv falls back to legacy setuptools.
  There is no package-data/MANIFEST (the template's Dockerfile says so and therefore keeps the
  install editable). Leaving the app: nothing to remove from `packages.find` (the include is a glob
  and the directory just disappears); the only pyproject change is the dependency line. FLS is not
  published anywhere I can find (no PyPI mention in README, docs or workflows).
  **Contrast for the new repo:** it will be installed as a *built wheel* from git, so it needs an
  explicit `[build-system]` and must ship templates, static files and migrations as package data
  (hatchling includes everything under the package dir; setuptools needs `include-package-data` +
  `MANIFEST.in`/`package-data`). A test that builds the wheel and asserts the template files are
  present is cheap insurance; the editable dev install would hide this bug.
- **Tailwind is the real breakage.** Concrete `tailwind.input.css` uses
  `@source "./submodules/Freedom-LS/freedom_ls/**/templates/**/*.html"`; FLS's own uses
  `./freedom_ls/**/...`. The framework's templates will sit in `.venv/lib/python3.13/site-packages/panel_framework/`
  (or the editable repo dir). Two traps:
  1. Tailwind v4 `@source` honours `.gitignore` (First-Class's own `tailwind.input.css` comments on
     this); `.venv` is ignored, so the path needs `@source not-ignored:`.
  2. The concrete template's Dockerfile builds Tailwind in a **Node-only first stage** before any
     Python is installed, so neither a generated CSS file from a management command nor a
     site-packages path exists yet. Fix by splitting the Python-deps phase into its own stage and
     `COPY --from=` the installed `panel_framework` directory (or the generated source file) into
     the Tailwind stage; or run Tailwind after `uv sync`. In FLS CI, `uv sync` already precedes
     `npm run tailwind_build`, so it only needs the generated-file command step.
  Each concrete project's `tailwind.input.css` must `@import` the generated file (or add the
  `@source`), so this is an upgrade-notes item (`requires_tailwind_rebuild`) and an edit to the
  concrete template.

## 6. Publishing: git tag versus PyPI

- Git tag only: zero publishing process, private-friendly, lock pins an exact commit. Downsides: every
  consumer needs `git` and (if private) credentials, no `pip install django-panel-framework>=x`
  resolution across a range, and anything that wants to publish *FLS itself* to PyPI could not do so:
  PyPI rejects uploads whose `Requires-Dist` contains direct URL references ("Can't have direct
  dependency", PEP 715-era enforcement; evidence in the setuptools/other-project issues at
  https://github.com/pypa/setuptools/issues/2880 and https://github.com/aradng/FastLoom/pull/18).
  FLS is not published today, so this costs nothing now; it becomes a blocker the day FLS goes to PyPI.
- PyPI (or a private index): allows plain `django-panel-framework>=0.3,<0.4` in FLS, makes the
  `[tool.uv.sources]`-vs-transitive worry vanish, and lets uv's resolver pick versions. Costs: a
  release pipeline and a public (or private-index) namespace.
- Staged path: tag-only now with the PEP 508 URL; when FLS or the package is ever published, switch
  the line to a version specifier. The import name is unchanged either way.

## 7. Recommended architecture

**Committed state**
- Panel repo (`/home/sheena/workspace/lms/django_apps/panel_framework`, GitHub, annotated tags
  `vX.Y.Z`, explicit `[build-system]`, templates/static/migrations as package data, `CHANGELOG.md`).
- FLS `pyproject.toml`: one line in `[project].dependencies`, the PEP 508 git+https tag reference.
  **No** `[tool.uv.sources]` entry for it. `uv.lock` records the resolved rev. CI keeps `uv sync` (add
  `--locked`).

**Dev loop (FLS developer / agent worktree)**
- `claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` gains, after `uv sync`, an
  idempotent "link the framework" step: if `$PANEL_FRAMEWORK_DIR` (default
  `/home/sheena/workspace/lms/django_apps/panel_framework`) exists, `uv pip install --no-deps -e` it.
  `UV_NO_SYNC=1` in the developer environment (agent `env` setting); fallback `uv run --with-editable`
  or `PYTHONPATH`.
- Framework changes that FLS needs follow: edit in the package repo -> tests there -> tag -> bump the FLS
  pin and `uv lock` -> FLS suite. The bump commit, not the live edit, is what CI sees.

**CI**: unchanged apart from `--locked`; public repo needs nothing; private repo needs a deploy key
or token `insteadOf` step in the `uv sync` jobs.
**Docker**: add `git` (and a BuildKit secret if private) to `freedom_ls_infra/fls-base/Dockerfile`
and to the concrete template's python-builder stage; reorder Tailwind to run after the Python deps
are installed (or copy the package's templates in), and use `@source not-ignored:`.
**Downstream**: concrete projects get the package transitively through `freedom_ls` (PEP 508 line),
nothing declared locally; they pick up a new pin through the existing FLS update flow
(`requires_package_upgrade` + `requires_tailwind_rebuild`), and re-lock.

## 8. Risks

1. **Transitive source behaviour unconfirmed**: do the spike (First-Class sandbox: path-install FLS
   whose pyproject has a git PEP 508 dep; and a second variant with a sources-only entry to see it fail).
2. **`uv run` reverting the editable install** unconfirmed; decides whether `UV_NO_SYNC` is mandatory.
3. **Dev/CI divergence**: local editable code passes tests, CI on the old tag fails. Mitigate with a
   pre-merge check that the installed `panel_framework` is the locked rev, and a rule that a pin bump
   ships in the same FLS change.
4. **Wheel missing templates/migrations** in non-editable installs (hidden by editable dev). Wheel-content test.
5. **Tailwind pipeline**: gitignored `.venv` skipped; Node-only Docker stage cannot see the package.
6. **Private repo credentials** in CI and both Dockerfiles; `git` absent from `python:3.13-slim`.
7. **uv.toml temptation**: adding a project `uv.toml` silently disables all `[tool.uv]` in
   `pyproject.toml`. Record this in the spec so nobody tries the earlier suggestion.
8. **Hand-edited relative path** `../../django_apps/...` assumes worktrees two levels deep; use the env var.

status: ok
