# Research: best practices for extracting a Django app into a git-tag package

Scope: complements `research_uv_sources_and_consumers.md` (dev loop, CI/Docker, Tailwind traps, transitive
sources). Items marked **(unverified)** come from general knowledge, not a fetched page, and want a quick check
in the spec's spikes.

## 1. Hatchling for a reusable Django app

### Config skeleton (flat layout, package dir `panel_framework/` at repo root)

```toml
[build-system]
requires = ["hatchling>=1.27"]      # >=1.26.2 is the floor for sane PEP 639 output, see below
build-backend = "hatchling.build"

[project]
name = "django-panel-framework"
version = "0.1.0"                   # or dynamic via [tool.hatch.version] path = "panel_framework/__init__.py"
license = "MIT"                     # SPDX expression string, not a table
license-files = ["LICENSE"]         # list of globs
requires-python = ">=3.13"

[tool.hatch.build.targets.wheel]
packages = ["panel_framework"]

[tool.hatch.build.targets.sdist]
include = ["panel_framework", "tests", "LICENSE", "README.md", "CHANGELOG.md", "pyproject.toml"]
```

Facts (cited):
- `license` takes an SPDX expression and `license-files` a list of paths/globs, both in `[project]`
  (https://hatch.pypa.io/latest/config/metadata/).
- Hatchling history: PEP 639 draft support since 1.5.0; **1.26.0 (2024-11-10) made `license-files` an array of
  globs per the final spec and added core metadata 2.4; 1.26.2 back-populated `License-Expression`**
  (https://hatch.pypa.io/latest/history/hatchling/). So pin `hatchling>=1.26.2` at minimum; the string form
  `license = "MIT"` is wrong with older hatchling. Do not also add a `License :: OSI Approved :: MIT` classifier
  (PEP 639 deprecates mixing; **unverified** that hatchling errors, but setuptools does).
- Wheel auto-detection (when no selection option is set) finds `<NAME>/__init__.py` using the *project name*; the
  name `django-panel-framework` normalises to `django_panel_framework`, which does not match `panel_framework`,
  so **`packages = ["panel_framework"]` is required** or the build errors
  (https://hatch.pypa.io/latest/plugins/builder/wheel/).
- `packages` is like `only-include` with the path collapsed to its last component; `include`/`exclude` are
  gitignore-style with `exclude` winning; `artifacts` adds files that VCS ignores and is not affected by
  `exclude`; `force-include` maps arbitrary paths and errors if a source is missing
  (https://hatch.pypa.io/latest/config/build/).
- **Default is to respect `.gitignore`** (first one found in root or parent; `ignore-vcs = true` disables). Any
  non-`.py` file under the package dir (templates, static, `HEROICONS_LICENSE.txt`, migrations) is shipped
  unless gitignored; hatchling needs no `MANIFEST.in` / `include-package-data` (the build page does not state this
  explicitly: **unverified**, but it is the standard hatchling behaviour and exactly what the wheel test proves).
- Traps that follow: (a) a gitignored generated file under the package (e.g. a compiled `static/.../*.css`,
  generated Tailwind source file) is silently dropped: list it in `[tool.hatch.build.targets.wheel] artifacts`
  or commit it; (b) a repo-root `.gitignore` containing `*.txt`, `static/`, `build/` or `lib/` will exclude
  package data; (c) `.gitignore` is read from a parent directory too, so a bare-repo-plus-worktree layout can
  pick up an unexpected ignore file: the wheel test catches this.
- Wheel placement of the licence: under `*.dist-info/licenses/` for metadata 2.4 (PEP 639), so assert
  `any(n.endswith("dist-info/licenses/LICENSE") ...)` rather than a top-level `LICENSE`. The hatch pages fetched
  do not state the location: **unverified**; confirm in the test's first run (print `zf.namelist()`).
  https://peps.python.org/pep-0639/

### sdist vs wheel
- `uv build` / `python -m build` build the sdist first, then the wheel *from the sdist*. A file included in the
  wheel but missing from the sdist therefore vanishes from the wheel. The sdist `include` must cover everything the
  wheel needs (package dir, LICENSE, pyproject, README). The wheel docs recommend this flow
  (https://hatch.pypa.io/latest/plugins/builder/wheel/).
- **git-URL installs build from a checkout (pip/uv `git+https://...@v0.1.0`)**: uv builds a wheel from the
  cloned tree via PEP 517 (`build_wheel`, not necessarily through the sdist **(unverified)**), so test both:
  `uv build --wheel` and `uv build` (sdist then wheel from it).

### Wheel-contents test (pattern)
```python
import subprocess, sys, zipfile
from pathlib import Path

REQUIRED = [
    "panel_framework/templates/panel_framework/icons/HEROICONS_LICENSE.txt",
    "panel_framework/migrations/0001_initial.py",
    # a template, a static file, a templatetag module, a cotton component (derive from the source tree glob)
]

def test_wheel_contains_package_data(tmp_path: Path) -> None:
    subprocess.run(["uv", "build", "--out-dir", str(tmp_path), str(REPO_ROOT)], check=True)  # sdist + wheel-from-sdist
    wheel = next(tmp_path.glob("*.whl"))
    names = set(zipfile.ZipFile(wheel).namelist())
    for path in REQUIRED:
        assert path in names
    assert any(n.endswith(".dist-info/licenses/LICENSE") for n in names)
```
Better: compute the expected set from the working tree (`Path("panel_framework").rglob("*")` minus `__pycache__`,
`*.pyc`) and assert `expected <= names`, so a new template cannot be forgotten, plus assert no `tests/`,
`.github/` or `node_modules` leak. Mark it `@pytest.mark.slow` or run once per session; `uv build` needs network
only for `hatchling` (use `--no-build-isolation` if offline). Build into `tmp_path` so no `dist/` is polluted.
Also test the sdist (`tarfile`) for LICENSE and the package dir. For a stronger check, CI installs the built wheel
into a fresh venv (`uv venv; uv pip install dist/*.whl`) and runs a `python -c "import django, panel_framework"` plus
`manage.py check` against a tiny settings module: that is what an editable install hides.

## 2. Renaming the app label on extraction

Django does not document label changes (the migrations page covers squashing and cross-app dependencies only:
https://docs.djangoproject.com/en/6.0/topics/migrations/). Established practice (**unverified** as a single
source; it follows from how Django keys migration history by `(app_label, name)`):

1. **Treat it as a new app.** New label `panel_framework` -> new `django_migrations` history, regenerated
   `0001_initial` (`makemigrations panel_framework`), new default table `panel_framework_bulkactionrun`
   (`<app_label>_<model>`). Old and new tables never collide; this is exactly the idea's design.
2. **Dependencies on the old label.** Search *other* apps' migrations for `("freedom_ls_panel_framework", "...")`
   dependencies and `to="freedom_ls_panel_framework.X"` FK targets. The idea says only `BulkActionRun` has an FK
   to `django.contrib.sites` and, apparently, nothing points *at* it; verify with
   `grep -rn "freedom_ls_panel_framework" --include="*.py" */migrations`. Never edit existing migrations (project
   rule), so if another app's old migration references the old label, that migration cannot be left dangling:
   either confirm none does, or keep a stub. Because migration graph loading fails with `NodeNotFoundError` when a
   dependency names a missing app, this check is the key gate.
3. **Order on existing databases.** The new app's `0001` creates a different table, so it can run before or after
   the cleanup. Make the cleanup migration depend on nothing from the new app. Fresh DBs: cleanup must be a no-op.
4. **Stale rows** (not cleaned by Django when an app disappears; `remove_stale_contenttypes` handles only
   ContentTypes, interactively, and never touches `django_migrations`):
   - `django_migrations`: `MigrationRecorder(connection).migration_qs.filter(app="freedom_ls_panel_framework").delete()`
     (ORM; model `django.db.migrations.recorder.MigrationRecorder.Migration`). Do this in `RunPython` using
     `schema_editor.connection`, not the historical-app registry (the model is not in it).
   - ContentType: `apps.get_model("contenttypes", "ContentType").objects.filter(app_label="freedom_ls_panel_framework").delete()`
     (Permission rows cascade via FK; a `RunPython` with `dependencies = [("contenttypes", "0002_remove_content_type_name")]`
     is needed per Django's rule that `RunPython` using another app's models needs that dependency, quoted from the
     migrations page above). Also delete `Group`/`User` permission M2M rows: they cascade with Permission.
     Guard: `if not has contenttypes table` is not needed since contenttypes is always installed with FLS.
   - Other label-keyed rows: django-admin `LogEntry` (via ContentType FK, cascades), any `GenericForeignKey` users.
5. **Dropping the old table without raw SQL** (answers the "RunSQL needs security review" open point):
   ```python
   from django.db import connection, migrations, models

   def drop_old_table(apps, schema_editor) -> None:
       table = "freedom_ls_panel_framework_bulkactionrun"
       if table not in schema_editor.connection.introspection.table_names():
           return
       class Legacy(models.Model):          # temp model, not registered in a real app registry slot that matters
           class Meta:
               app_label = "base"           # host app that is installed; db_table below is what matters
               db_table = table
       schema_editor.delete_model(Legacy)
   ```
   Caveats: `delete_model` on a minimal model drops the table (`DROP TABLE ... CASCADE` on PostgreSQL) and does not
   need the real fields, only `db_table`; defining a model class inside a function registers it in the global app
   registry and warns on re-definition ("Model was already registered"): build it with `type()` inside
   `apps` isolation, i.e. use `from django.apps.registry import Apps; Apps()` as the `Meta.apps` to keep it out of
   the global registry (this is what Django's own migration state does) **(unverified in detail; spike it)**.
   `introspection.table_names()` is the supported existence check (`connection.introspection.table_names(cursor=None, include_views=False)`).
   Alternative: `migrations.DeleteModel` cannot be used, because the model is no longer in any migration state
   (no state for the old label), which is why the temp-model approach is the usual trick. Fallback: documented
   manual step in the upgrade notes (idea already lists it).
6. **Where to put it**: one migration in a surviving app (`base`) depending on the app's latest migration; `RunPython`
   with `reverse_code=migrations.RunPython.noop` (data deliberately lost). Use `elidable=True` so a future squash can
   drop it. Remove it a release or two later once all deployments have applied it (Django's recommended squash
   rollout: release with both, then delete: https://docs.djangoproject.com/en/6.0/topics/migrations/).
7. **Test it**: a migration test with `django_db_setup` that creates the legacy table + rows via
   `connection.schema_editor()`, runs the function, asserts table/rows gone, and a second call is a no-op.

## 3. Changelog, versioning, deprecation

- **Keep a Changelog 1.1.0**: change types `Added / Changed / Deprecated / Removed / Fixed / Security`; newest
  first; an `Unreleased` section at top; ISO dates; every version linkable via reference links at the bottom
  (`[0.1.0]: https://github.com/preludetech/django-panel-framework/releases/tag/v0.1.0`, `[Unreleased]: .../compare/v0.1.0...HEAD`);
  yanked releases marked `## [0.1.1] - 2026-12-01 [YANKED]`; state that the project follows SemVer
  (https://keepachangelog.com/en/1.1.0/).
  Put FLS's flags under each version as a small fixed block (not free text), e.g. a bullet list or YAML-ish
  `**Flags:** requires_migrations: false; requires_template_review: true (changed_template_paths: ...)`. Keep the
  schema identical to FLS's `upgrade_notes.md` so spec 6's tooling can parse both.
- **SemVer for 0.x**: major zero means any API may change at any time (https://semver.org/#spec-item-4). Practical
  small-package convention: while 0.y.z, **breaking change -> bump minor, fix/compatible feature -> bump patch**;
  consumers pin exact tags anyway (git tag), so the pin is the real guard. Declare the public API (host contract,
  template paths, tag names, cotton names, settings keys, model fields) in the README so "breaking" is defined.
  SemVer says deprecating public API requires a minor bump (item 7).
- **One-release deprecation rule**: keep the old name working and emit
  `warnings.warn("X is deprecated, use Y; removed in 0.N+1", DeprecationWarning, stacklevel=2)`; log it under
  `Deprecated` in release N and `Removed` in N+1. `DeprecationWarning` is hidden unless triggered in `__main__`
  (and pytest/unittest enable it), so Django-project developers see it only under `-W d` / pytest; use
  `FutureWarning` when the audience is end-user visible, or define a package-specific subclass
  (`class PanelFrameworkDeprecationWarning(DeprecationWarning)`) so consumers can `filterwarnings = ["error::panel_framework.PanelFrameworkDeprecationWarning"]`
  (Django itself does this with `RemovedInDjangoXXWarning`). Use `stacklevel=2` (or `skip_file_prefixes` on 3.12+)
  so the warning points at the caller (https://docs.python.org/3/library/warnings.html). The package's own
  pytest config should set `filterwarnings = ["error::DeprecationWarning:panel_framework"]` so its own code never
  uses a deprecated path, and each deprecation needs a test using `pytest.warns`.
- Deprecating **non-Python** surface (template paths, cotton component names, settings keys, URL names) needs a
  different mechanism: keep a thin template at the old path that `{% include %}`s the new one; for settings, read
  the old key in the settings helper and warn once. List these paths in the changelog's `changed_template_paths` flag.
- Tag mechanics: annotated tags `vX.Y.Z` (`git tag -a`), version in `pyproject.toml` must equal the tag; add a
  CI check (`test: tag == pyproject version == top CHANGELOG entry`) so a mislabeled tag cannot be consumed.
  Do not move or delete a published tag (a lock pins the commit; re-tagging breaks `uv lock` reproducibility);
  yank by adding a new tag and a `[YANKED]` marker.

## 4. Bundling Heroicons (MIT) and the notices

- Heroicons is MIT, `Copyright (c) Tailwind Labs, Inc.` (https://github.com/tailwindlabs/heroicons/blob/master/LICENSE).
  The MIT condition: the copyright and permission notice must be included "in all copies or substantial portions
  of the Software" (https://spdx.org/licenses/MIT.html). Shipping SVG path data inside templates is a copy of a
  substantial portion, so the notice must travel with it; `HEROICONS_LICENSE.txt` beside the templates in the
  wheel does that.
- `HEROICONS_LICENSE.txt` content: the verbatim, complete upstream licence text (copy from the upstream repo
  at the commit/version the SVGs came from) plus a header line naming the source repo and version
  (e.g. "Heroicons v2.x, https://github.com/tailwindlabs/heroicons, icons: arrow-down, ..."). Record the upstream
  version because upstream may add icons or change text.
- `LICENSE` at repo root: standard MIT text with `Copyright (c) 2026 Prelude Technologies`, then a section such
  as:
  ```
  Third-party material
  --------------------
  This package bundles material from other projects, which keep their own licences:

  * Heroicons (icon SVG bodies) - MIT, Copyright (c) Tailwind Labs, Inc.
    Notice: panel_framework/templates/panel_framework/icons/HEROICONS_LICENSE.txt
  ```
  Common alternatives: a separate `NOTICE`/`THIRD_PARTY_NOTICES.md`. The idea's choice (list in `LICENSE`,
  full text in a shipped file) is fine; PEP 639 also lets you put all in `license-files = ["LICENSE", "panel_framework/templates/panel_framework/icons/HEROICONS_LICENSE.txt"]`
  so the notice also lands in `dist-info/licenses/` (recommended: both locations, the second glob preserves
  the directory path). Keep `license = "MIT"` for the package's own code; an expression such as `MIT AND ...` is
  only needed if third-party code were under a different licence, which is not the case for MIT-on-MIT
  (PEP 639 says the expression describes the distribution as a whole: `MIT` already covers both).
  https://peps.python.org/pep-0639/
- Add a test that every bundled-asset name listed in `LICENSE` has its notice file in the wheel (the wheel test
  above) and conversely that the icons directory contains a licence file.
- If a Tailwind-built CSS file is committed/shipped, Tailwind v4's banner comment (`/*! tailwindcss vX | MIT License | https://tailwindcss.com */`)
  is the notice for it; do not strip it **(unverified; check the output)**.

## 5. GitHub Actions for a standalone Django app (Postgres + Playwright + Tailwind v4)

Skeleton (matches the research on checkout/setup-uv versions already used in FLS):
```yaml
name: tests
on: { push: { branches: [main], tags: ["v*"] }, pull_request: {} }
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: panel_framework }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}   # whatever the standalone settings read; points at the service above
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v7
        with: { enable-cache: true }
      - run: uv sync --locked --group dev           # dev group incl. lxml, pytest-playwright
      - run: uv run playwright install --with-deps chromium
      - uses: actions/setup-node@v6                 # or the standalone binary, below
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - run: uv run <tailwind source command from spec 4>   # generates @source file BEFORE the build
      - run: npm run tailwind_build
      - run: uv run pytest
      - if: failure()
        uses: actions/upload-artifact@v5
        with: { name: playwright-traces, path: test-results/ }
```
Sources: setup-uv, `uv sync --locked`, `enable-cache`, `uv run pytest` and private git dependency recipe
(`gh auth login --with-token` + `gh auth setup-git`) from https://docs.astral.sh/uv/guides/integration/github/;
Playwright `python -m playwright install --with-deps`, `actions/checkout@v6`, `upload-artifact@v5` of `test-results/`
from https://playwright.dev/python/docs/ci-intro (that page does not cover browser caching).
Notes:
- Installing only `chromium` (`playwright install --with-deps chromium`) saves minutes **(unverified: flag
  semantics from general knowledge)**; skip caching `~/.cache/ms-playwright` unless the run is slow (restore keys
  must include the playwright version).
- **Tailwind v4 options.** (a) npm (`tailwindcss` + `@tailwindcss/cli`), cached via `setup-node`'s `cache: npm`;
  needs `package-lock.json`. (b) Standalone binary (no Node): download `tailwindcss-linux-x64` from the
  `tailwindlabs/tailwindcss` GitHub release (asset names could not be fetched: **unverified**, check
  https://github.com/tailwindlabs/tailwindcss/releases), `chmod +x`, cache by version key. (b) is lighter for a
  Python-only repo, but the template Docker stage uses npm already, so (a) keeps one mechanism across FLS,
  template and this repo; recommend (a).
- Order: install Python deps -> generate the Tailwind source file (spec 4 command) -> Tailwind build ->
  Playwright tests; the build must precede pytest because Playwright tests need the compiled CSS.
- Matrix: Python 3.13 x Django 6.0 (and the lowest supported Django if the package claims a range) via
  `uv sync --locked` plus `uv pip install "django==6.0.*"`; or just one cell while 0.x.
- Add jobs/steps: (1) wheel-contents test (it is a normal pytest test; also run `uv build`), (2) tag check on
  `v*` tags (tag == version == changelog), (3) `ruff`/`pre-commit run --all-files`, (4) `manage.py makemigrations --check --dry-run`
  so a model change without a migration fails, (5) `uv lock --check` (same as `--locked`).
- Playwright in CI needs a live server: pytest-playwright with `pytest-django`'s `live_server`; set
  `DJANGO_ALLOW_ASYNC_UNSAFE=true` if sync ORM is used in the test body **(unverified: common pytest-playwright
  + pytest-django gotcha)**. Postgres service on `localhost`, not a docker network host, since the job runs on the
  runner.
- `permissions: contents: read` at workflow top; pin third-party actions to major versions or SHAs.

## 6. Checking the installed package matches the lock entry

Two facts to compare, both obtainable without extra dependencies.

**Installed side**: PEP 610 `direct_url.json` in the installed dist's `.dist-info`
(https://packaging.python.org/en/latest/specifications/direct-url-data-structure/):
- git install: `{"url": ".../django-panel-framework.git", "vcs_info": {"vcs": "git", "requested_revision": "v0.1.0", "commit_id": "<40 sha>"}}`;
- editable local dir: `{"url": "file:///abs/path", "dir_info": {"editable": true}}` (no commit id; read it from
  the checkout with `git -C <path> rev-parse HEAD`, and also check `git status --porcelain` / that HEAD equals the
  tag if you require a clean tagged tree).
`importlib.metadata.distribution("django-panel-framework").read_text("direct_url.json")` returns the JSON string
(or `None` for a PyPI install). Use `urllib.parse.urlparse(url).path` for the editable path.

**Lock side**: `uv.lock` has a `[[package]] name = "django-panel-framework"` with
`source = { git = "https://github.com/preludetech/django-panel-framework.git?tag=v0.1.0#<40 sha>" }`
**(unverified format; print your own lock to confirm: uv's git source string is `url?rev|tag|branch=...#sha`)**.
Parse with `tomllib` (stdlib): find the package entry, split on `#` for the locked commit. Do not regex the
file; do not shell out to `uv` (the `sdd`/`ds` portability rule is irrelevant here, this lives in FLS).

**Check logic** (a pytest test or a script in FLS, run in CI and as pre-merge hook):
1. `locked = commit from uv.lock`.
2. `direct_url = importlib.metadata...read_text("direct_url.json")`.
3. If `vcs_info`: `assert commit_id == locked`.
4. If `dir_info.editable`: `head = git -C path rev-parse HEAD`; **in CI, fail** (an editable install means the
   local-dev shortcut leaked); **locally, fail unless `head == locked`** (i.e. the developer has tagged and bumped).
   Locally, warn rather than fail if you want editing to be possible before tagging; make the strictness an
   env switch (`CI=true` or `--strict`).
5. Also assert the `pyproject.toml` pin tag (`@v0.1.0`) equals the lock's `tag=`.
Where to put it: simplest and robust is a pytest test in FLS (`tests/test_framework_pin.py`) that runs wherever
tests run, so CI needs no extra job and pre-merge is just "run the suite on the PR". A pre-commit hook is the
wrong tier: it would run on every commit while the developer is mid-edit, and in an editable loop it would always
fail. A CI-only strict mode of the same test closes the "passes locally, fails on the old tag" gap, because CI
installs from the lock (`uv sync --locked`), so the comparison trivially passes there; the real danger (merging
with an unbumped pin) is caught by CI's *tests running against the tag*, not by the check. So the check's
distinct value is locally and in the pre-merge (finishing) step of the worktree workflow: recommend wiring it to
the same place spec closure runs the suite, plus the strict CI mode that fails on `dir_info.editable`.
`uv sync --locked` / `uv lock --check` does not compare installed state, only lock versus `pyproject.toml`
(see the existing research, section 1).

## 7. Concrete recommendations for the spec

1. Pin `hatchling>=1.26.2`; set `packages = ["panel_framework"]`; sdist `include` list; wheel `artifacts` for any
   gitignored generated file.
2. `license-files = ["LICENSE", "panel_framework/templates/panel_framework/icons/HEROICONS_LICENSE.txt"]`;
   test asserts both under `dist-info/licenses/` (confirm path on first run).
3. Wheel test: build via `uv build` into `tmp_path`; expected set derived from the source tree; also test the
   sdist; CI additionally installs the wheel in a clean venv and runs `manage.py check`.
4. Extraction migration: grep for dependents on the old label first; cleanup in `base`, `RunPython` only, using
   `introspection.table_names()` + `schema_editor.delete_model` on a temp model, `MigrationRecorder` for
   `django_migrations`, ORM delete for ContentType; `elidable=True`, noop reverse, a test. No `RunSQL`, so the
   security-review gate is moot (spike the temp-model registry behaviour).
5. Changelog: Keep a Changelog 1.1.0 plus a fixed flag block; SemVer with breaking -> minor in 0.x; a
   `PanelFrameworkDeprecationWarning(DeprecationWarning)` subclass with `stacklevel=2`; tag/version/changelog
   consistency check in CI; never move tags.
6. Heroicons: verbatim upstream text plus source version in `HEROICONS_LICENSE.txt`; `LICENSE` lists it; ship the
   notice through both package data and `license-files`.
7. CI: Postgres 17 service, setup-uv with `uv sync --locked`, `playwright install --with-deps chromium`, npm
   Tailwind after the spec 4 source command, upload traces on failure, `makemigrations --check`, wheel test.
8. Lock-match check: a pytest test comparing `direct_url.json` (`commit_id` / editable HEAD) to `uv.lock` via
   `tomllib`, strict (fail on editable) under `CI`.

## References
- https://hatch.pypa.io/latest/config/metadata/
- https://hatch.pypa.io/latest/history/hatchling/
- https://hatch.pypa.io/latest/config/build/
- https://hatch.pypa.io/latest/plugins/builder/wheel/
- https://peps.python.org/pep-0639/
- https://docs.djangoproject.com/en/6.0/topics/migrations/
- https://keepachangelog.com/en/1.1.0/
- https://semver.org/#spec-item-4
- https://docs.python.org/3/library/warnings.html
- https://github.com/tailwindlabs/heroicons/blob/master/LICENSE
- https://spdx.org/licenses/MIT.html
- https://packaging.python.org/en/latest/specifications/direct-url-data-structure/
- https://docs.astral.sh/uv/guides/integration/github/
- https://playwright.dev/python/docs/ci-intro

status: ok
