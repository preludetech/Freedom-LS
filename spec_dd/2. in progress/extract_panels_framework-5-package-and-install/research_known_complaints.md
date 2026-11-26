# Research: known complaints about this kind of work

Question: what do users commonly complain about when a Django app moves into its own repo, is installed from a git tag with uv, ships a hatchling wheel, and has its templates scanned by Tailwind v4?

Method: web searches plus two page fetches (Nov 2026). Search snippets were the main source. Items marked *unverified* were not confirmed on the source page and need a spike or test in this spec. Each item gives what went wrong, the fix, and whether it applies to this spec.

## 1. uv

### 1.1 `uv sync` / `uv run` undo a hand-installed editable (applies, high)
- Complaint: a package put in by `uv pip install` is not tracked by the lockfile, so the next `uv sync` or `uv run` puts the locked version back. Reports describe packages "disappearing" after `uv sync`. Related: uv #8124 (users must pass `--no-editable` on every command or uv re-syncs and re-creates the editable install) and uv #15190 / PR #15450 (sync not switching or retaining editables correctly).
- Docs: "it is not recommended to modify the project environment manually, e.g., with `uv pip install`". `uv run` checks the env against the lock by default; `--no-sync` skips that.
- Workaround seen in the wild: install `-e` over the lock, then run every command with `--no-sync` (the Soundverse overlay guide). It leaves `pyproject.toml` and `uv.lock` untouched.
- Here: this is exactly the idea's Spike 1 and `UV_NO_SYNC=1` plan. The sources support treating `UV_NO_SYNC=1` as mandatory. Nothing found shows `uv run` leaving it alone. Run the spike anyway. Cost to accept: a teammate's new dependency is not picked up until an explicit `uv sync`, and then the link must be redone. `rebuild_after_rebase.sh` already does that.
- URLs:
  - https://docs.astral.sh/uv/concepts/projects/sync/
  - https://github.com/astral-sh/uv/issues/8124
  - https://github.com/astral-sh/uv/pull/15450
  - https://www.technetexperts.com/uv-pip-install-vs-uv-add-editable-packages/
  - https://internal-docs.soundverse.ai/how-to/test-soundverse-py-overlay/

### 1.2 Lock keeps the old rev: "I updated the tag but nothing changed" (applies, medium)
- Complaint: uv prefers the locked commit SHA over whatever the ref now points to. Users are surprised that a moved or re-cut tag, or a new tag in `pyproject.toml`, does not update anything until `uv lock --upgrade-package <name>`. uv #13551 is the general form (a user said `uv sync` "reverted" the version to the lock; maintainer: the lock changes only when necessary, use `uv add --upgrade`).
- Fix: after bumping the pin, run `uv lock` (a changed specifier re-resolves it). For a moved tag use `uv lock --upgrade-package django-panel-framework`. Never move a published tag; cut a new one.
- Here: supports the idea's rule "bump the pin and `uv lock` in the same FLS change". Add to the spec: tags are immutable, and a `v0.1.0` re-cut is forbidden.
- URLs:
  - https://github.com/astral-sh/uv/issues/13551
  - https://docs.astral.sh/uv/concepts/resolution/
  - https://timetobuildbob.github.io/blog/the-lockfile-that-pinned-a-missing-sha/

### 1.3 Lock pins a SHA that no longer exists (applies, low)
- Complaint: after a force-push, rebase or tag deletion on the dependency repo, every fresh checkout fails to fetch the locked SHA. It fails before any local code runs.
- Fix: never rewrite history or delete tags on the package repo. Fix forward with a new tag and `uv lock --upgrade-package`.
- Here: the idea already says a fresh import commit and no history extraction. Spec the "tags and `main` history are never rewritten" rule in the package README or CHANGELOG header.
- URL: https://timetobuildbob.github.io/blog/the-lockfile-that-pinned-a-missing-sha/

### 1.4 `uv sync --locked` fails with "lockfile needs to be updated" (applies, medium)
- Complaint: `--locked` errors when `pyproject.toml` and `uv.lock` disagree, often after someone edits `[project].dependencies` and forgets `uv lock`. There are reports where `uv lock` followed by `uv sync --locked` still failed when a specific package was added (uv #17747, *details unverified*). Dependabot-style tools also do not update `uv.lock` well (discuss.python.org thread).
- Fix: run `uv lock` in the same commit as the pin change. CI uses `--locked` so a stale lock fails loudly. Add a pre-merge lock check.
- Here: CI `--locked` is already in the idea. The out-of-band editable install does not affect `--locked`, which only compares the lock to `pyproject.toml`.
- URLs:
  - https://github.com/astral-sh/uv/issues/17747
  - https://discuss.python.org/t/updating-uv-lock-with-dependabot/107320
  - https://docs.astral.sh/uv/concepts/projects/sync/

### 1.5 Transitive `[tool.uv.sources]` is not honoured (applies, high)
- Complaint: uv #9446 reports that uv ignores `tool.uv.sources` of dependencies (label `needs-decision`; current status not confirmed). The docs say that when another project consumes yours, only `project.dependencies` and `project.optional-dependencies` are respected.
- Fix: put the git URL in `[project].dependencies` as a PEP 508 direct reference, or declare the dependency in the root project and add a source there.
- Here: confirms the idea's dependency form and the sources-only variant failing in Spike 2. Residual risk: PyPI will not accept a package with direct-URL `Requires-Dist` (see the earlier research), which matters only if FLS is ever published.
- URLs:
  - https://github.com/astral-sh/uv/issues/9446
  - https://docs.astral.sh/uv/concepts/projects/dependencies/

### 1.6 `git` missing in slim Docker images (applies, high)
- Complaint: `python:*-slim` images lack `git`. Installs of git URLs fail with "Cannot find command 'git'" (pip) or uv's git-not-found error. People install git only in the final stage when `uv sync` runs in the build stage, so the fix does nothing.
- Fix: `apt-get install -y --no-install-recommends git` in the stage that runs `uv sync` or `uv pip install`. A multi-stage build can then copy `.venv`, and the runtime stage needs no git.
- Here: the idea adds git to `fls-base`. For the concrete template, put git in the new Python-deps stage. Do not assume the `uv:0.9-python3.13-bookworm-slim` image has it: it is a slim Debian image, so check with a `docker run ... which git` build test. Astral's Docker guide does not mention git.
- URLs:
  - https://gitlab.com/linkahead/linkahead-control/-/issues/17
  - https://docs-next.astral.sh/uv/guides/integration/docker
  - https://devblogs.microsoft.com/ise/dockerizing-uv/

### 1.7 Cache and `--frozen` Docker layers (applies, low)
- Complaint (general): with `uv sync --frozen --no-install-project`, the git dependency is a project dependency, so it is fetched in the deps layer. A moved ref cannot hide there, because the lock holds the SHA. The cost is a git clone per cold cache.
- Here: no action beyond 1.6. *Unverified* beyond the uv docs.

## 2. hatchling

### 2.1 PEP 639 `license` / `license-files` needs a new enough hatchling (applies, high)
- Complaint: SPDX `license = "MIT"` and `license-files = [...]` need a recent hatchling. The sources conflict on the first version: one says hatchling supported PEP 639 from 1.26.0, and hugovk's post moves `requires` to `hatchling>=1.27`. The 1.26.1 changelog says the license-files metadata field was updated to the latest spec (an array of glob patterns). Older hatchling rejects the string form of `license` or ignores `license-files`. Core metadata moves to 2.4.
- Fix: `requires = ["hatchling>=1.27"]` in `[build-system]`. uv builds git dependencies in an isolated env, so the floor also protects consumers. Check the wheel's `METADATA` for `License-Expression: MIT` and `License-File: LICENSE`, and `dist-info/licenses/LICENSE` in the wheel.
- Here: spec the floor as `>=1.27`. The idea's wheel test already asserts `LICENSE` is in the wheel. Add a metadata assertion. Do not also set a `License ::` classifier, since PEP 639 forbids mixing it with an SPDX expression.
- URLs:
  - https://hugovk.dev/blog/2025/improving-licence-metadata/
  - https://hatch.pypa.io/dev/history/hatchling
  - https://peps.python.org/pep-0639/
  - https://discuss.python.org/t/pep-639-round-3-improving-license-clarity-with-better-package-metadata/53020/172

### 2.2 `.gitignore` silently drops files from the wheel (applies, high)
- Complaint: hatchling honours the first `.gitignore` it finds, including ones in parent directories, even outside a git repo. A rule that matches a template, static file or `.txt` leaves the file out. The result is an empty or incomplete wheel (pypa/hatch #1069, #1964). A build from an extracted sdist can behave differently from a build from the repo, since the `.gitignore` is not in the sdist.
- Fix: check rules in the repo's `.gitignore`. Use `[tool.hatch.build.targets.wheel] packages = ["panel_framework"]` and `artifacts = [...]` for ignored-but-needed files (for example built CSS or static output). Keep a `.gitignore` next to `pyproject.toml`. `ignore-vcs = true` is a test knob.
- Here: the bare-repo-plus-worktree layout puts the package one directory below a parent folder, which is the parent-`.gitignore` case. Build the wheel in the test from a clean temp copy of the repo and also from the sdist. Assert templates, static, migrations and `HEROICONS_LICENSE.txt`. Any built Tailwind or static output in `.gitignore` needs `artifacts`.
- URLs:
  - https://github.com/pypa/hatch/issues/1069
  - https://github.com/pypa/hatch/issues/1964
  - https://hatch.pypa.io/dev/config/build

### 2.3 Editable install hides all of the above (applies, high)
- Complaint (general, and in the existing research): an editable install serves from the source tree, so missing package data only shows up on a real install.
- Here: matches the idea's wheel test. Also install the built wheel into a throwaway venv and run `manage.py check` / `makemigrations --check` there.

## 3. Django reusable apps

### 3.1 Templates / static missing after install (applies, medium)
- Complaint: classic packaging bug. The package works in a source checkout, then `TemplateDoesNotExist` after install because templates are not package data (setuptools without `MANIFEST.in` or `include-package-data`). Hatchling includes files under the package directory by default, so the risk is the `.gitignore` case in 2.2 and wrong `packages` config.
- Here: covered by the wheel test. Also test that `INSTALLED_APPS` with `panel_framework` and `APP_DIRS` finds the template and the cotton components from a non-editable install.
- No single source was fetched for this one. It is well known and the packaging doc above covers it. *unverified citation*.

### 3.2 Renaming an app label (applies, high)
- Complaints:
  - Migration dependencies and `django_migrations` rows are keyed by app label. A relabel on an existing database leaves old rows, and migrations that name the old label as a dependency break (Django #23790: "using AppConfig to relabel third-party apps is pretty much impossible").
  - Stale ContentTypes (Django #24067). Django does not auto-delete stale content types on purpose, since that risks data loss. Rename helpers swallow `IntegrityError` and defer to `remove_stale_contenttypes` (Django #36839: silent pass on duplicates).
  - Permission rename can hit unrelated models by substring (Django #36843). Duplicate permissions after a rename (Django forum thread).
  - Workaround blogs: edit `app_label` in `django_content_type`, then `makemigrations` and `migrate --fake-initial`. This fails when there are unapplied migrations in the renamed app.
- Fix for this spec: do not rename in place. The idea and answers already choose a drop-and-recreate: a new app label `panel_framework`, a new table `panel_framework_bulkactionrun`, one clean `0001`. In FLS, one `RunPython` migration drops the old table, deletes `django_migrations` rows for `freedom_ls_panel_framework`, and deletes the ContentType rows for that label (Permission rows cascade). A fresh database must be a no-op.
- Watch-outs for the spec:
  - Any other FLS migration that lists `("freedom_ls_panel_framework", "...")` in `dependencies` or in an FK `to=` breaks once the app is gone. The `BulkActionRun` FK to `django.contrib.sites` is not an issue, but grep every migration for the old label. The `learner_management` `RunStatus` consumer is a place to check.
  - The cleanup migration must not depend on the deleted app's migration, or the graph is broken on a fresh database.
  - Group, role or fixture data that references the old permissions' codenames (`freedom_ls_panel_framework.*`) needs a check.
  - If `django_migrations` rows are deleted but the table is not dropped, the new `0001` does not collide, because the table name differs (as the idea notes).
  - Test the migration on a database that still has the old table and rows, as well as on a fresh one.
- URLs:
  - https://code.djangoproject.com/ticket/23790
  - https://code.djangoproject.com/ticket/24067
  - https://code.djangoproject.com/ticket/36839
  - https://code.djangoproject.com/ticket/36843
  - https://forum.djangoproject.com/t/duplicate-permissions-created-on-model-rename/22740
  - https://makandracards.com/django/54489-django-rename-app

## 4. Tailwind v4

### 4.1 `@source` into an ignored directory is skipped (applies, high)
- Complaint: Tailwind v4 skips files ignored by `.gitignore`, and `node_modules` by default. A user pointing `@source` at a package in `node_modules` got no classes (tailwindcss discussion #19118). The maintainer's answer: it works "as long as files inside the package are not gitignored", and the library should expose a CSS file with its own `@source` and be `@import`ed. A Python analogue (uv's `.venv` has its own `.gitignore` containing `*`) was reported: a nested `.gitignore` with `*` hides the whole directory, so the reporter had to make sure the directory is not listed (tailwindcss #19844 and similar, *details not fetched*).
- Fix: use `@source not-ignored "<path>"` (the `not-ignored:` form the idea names). Confirm the exact syntax against the installed Tailwind version, because the search snippets showed different spellings. Another report says a `.gitignore` with allow-list rules (`*` then `!` rules) makes Tailwind v4 silently ignore `@source` directives that point at ignored directories.
- Here: both `.venv` (root `.gitignore` and uv's own nested `*` file) and any allow-list pattern are in play. The spec should include a test that builds Tailwind with the package templates in a gitignored `.venv` and asserts a class that appears only in a package template is in the CSS. Do this in the package's Playwright job and once in FLS.
- URLs:
  - https://github.com/tailwindlabs/tailwindcss/discussions/19118
  - https://tailwindcss.com/docs/detecting-classes-in-source-files
  - https://github.com/tailwindlabs/tailwindcss/issues/15452
  - https://github.com/tailwindlabs/tailwindcss/issues/19844

### 4.2 Generated `@source` file with absolute vs relative paths (applies, medium)
- Complaint: `@source` paths in a CSS file resolve relative to that CSS file. A generated file imported from `tailwind.input.css` carries paths that must be right from the generated file's location, not from the input file. Different machines have different `site-packages` paths, so the generated file must not be committed (or must be regenerated on every `uv sync`). Also, `@import` of a generated file that does not exist yet fails the Tailwind build outright.
- Here: spec 4 delivers the command. This spec must order steps: `uv sync`, then the generate command, then `npm run tailwind_build`. CI and `rebuild_after_rebase.sh` need the same order. Gitignore the generated file or commit it deliberately. Decide which. *Partly unverified: reasoning from the Tailwind docs, not a found complaint.*
- URL: https://tailwindcss.com/docs/detecting-classes-in-source-files

### 4.3 Multi-stage Docker with Node before Python (applies, high)
- Complaint: a Node-only stage cannot see Python packages, and no source for this exact setup was found. It is a consequence of 4.1 plus stage order.
- Fix (as the idea has it): make the Python-deps phase its own stage, then `COPY --from=python-deps .../site-packages/panel_framework` into the Tailwind stage, and use the same `not-ignored` path. Because `COPY` drops nothing, `.gitignore` rules still apply inside the stage, so keep `not-ignored`. The copied directory must sit at a path that the generated `@source` resolves (the generator reads the installed location, which differs in the Node stage). Consider generating the source file in the Python stage and copying that file along with the directory, with paths relative to the directory.
- Here: manual step in `upgrade_notes.md` for the concrete template. Test with `docker build` on the template.

### 4.4 Editable install path for Tailwind (applies, low-medium)
- Here: with `uv pip install -e`, the package templates sit in the sibling repo, outside the FLS tree and outside its `.gitignore` scope. Tailwind may treat paths outside the project root differently from ones inside it. *Unverified: test.* The generator must resolve the real location (editable or site-packages) at run time, and FLS dev and CI both need coverage.

## 5. Summary of what to add to the spec

1. Treat `UV_NO_SYNC=1` as required, and run Spike 1 to confirm. (1.1)
2. Tags are immutable and package-repo history is never rewritten. Bump the pin and `uv lock` together. (1.2, 1.3)
3. CI `uv sync --locked`, plus the before-landing locked-rev check. (1.4)
4. Keep the PEP 508 line, no sources entry. Spike 2 confirms. (1.5)
5. `git` in every stage that runs `uv sync` or `uv pip install`. Prove with a build, as the uv slim image is not known to ship git. (1.6)
6. `requires = ["hatchling>=1.27"]` plus metadata assertions. Wheel test builds from a clean copy and from the sdist, and checks `.gitignore` effects. Install the wheel into a clean venv. (2.1, 2.2)
7. Cleanup migration: grep for the old label in every migration's dependencies, test on a dirty and a fresh database, check for permission references in fixtures and groups. (3.2)
8. Tailwind: `not-ignored`, ordering of generate-then-build, and a test that proves a package-only class lands in the CSS. (4.1-4.4)

status: ok
