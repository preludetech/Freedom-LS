# Research: how reference implementations compute "affected tests"

Topic `reference_implementations`, for `faster-test-runs-8-narrower-targeted-tier`. Question: how do reference
implementations narrow a static selector so a change in a widely imported package does not select every
transitive importer, and so shared files and unmapped paths do not escalate to the full suite?

Current approach (`claude_plugins/django-stack/scripts/select_tests.py`): selection unit is the **app**. A path owned by
an app selects the app's whole `tests/` directory plus the whole `tests/` directory of every app in the
transitive closure of runtime importers (`importers()` chains through runtime deps, one hop for test-only deps).
Any `ESCALATION_GLOBS` hit (`conftest.py`, `urls.py`, `factories.py`, `fixtures/**`, `migrations/**`,
`middleware.py`, `signals.py`, `apps.py`), any dependency file, and any path with no owner and no tooling rule is `full`.
Depth is unbounded and there is no per-app opt-out. (Upstream paths already get a softer rule, `related_tests_decision`:
escalation globs select the related apps' tests instead of `full`. That is a precedent inside this script.)

## Summary table

| System | Selection unit | Depth bound | Shared/config files | Unowned files | Opt-in config |
|---|---|---|---|---|---|
| Pants | file -> target (one `python_test` per file) | `--changed-dependents=direct` or `transitive` | `conftest.py` is an inferred dependency of tests (`[python-infer] conftests`); lockfile change marks all users of any dep | no owning target means no selection (not documented on the page fetched; see note) | `--changed-since`, `--changed-dependents` flags; `[python-infer]` options in `pants.toml` |
| Bazel / bazel-diff / target-determinator | target hash (content-hashed sources, attributes, rule inputs) | none; reports `target_distance` and `package_distance` so a caller can cut by distance | changes to `rule_inputs`/attributes re-hash everything downstream; `--ignore-file` excludes files | files not in the graph do not affect any hash | flags; filter by target type; distance via `--depEdgesFile` |
| Nx affected | task, selected when a changed file is in the task's `inputs` | none; follows named-input rules (`^production`) | lock file affects every task by default; `projectsAffectedByDependencyUpdates: "auto"` narrows it | n/a | `nx.json` `namedInputs`, `affected.legacy`, `NX_LEGACY_AFFECTED` |
| Turborepo | package | none documented for `...` | `globalDependencies` in `turbo.json` hash into every task | n/a | `--filter`, `--affected` (= `--filter=...[main...HEAD]`) |
| pytest-impacted | Python module, via AST import graph | transitive, no limit, no depth option | conftest rules below; dep/config files escalate; per-glob `--impacted-map` | non-Python files map via `--impacted-map` or `--impacted-invalidate-all` | `[tool.pytest.ini_options]` `impacted_*` keys |
| grimp | module (or package with `as_package=True`) | graph API is unbounded; shortest-chain API gives distance | n/a | n/a | library API |
| pytest-picked | test file, from git status only | none, no import graph | none | none | `--picked`, `--mode`, `--parent-branch` |
| pytest-testmon | test, via per-test coverage of files and methods | not a graph; recorded executions | contrast only | n/a | `--testmon` |

## Per-system findings

### Pants (`--changed-since`, `--changed-dependents`)

- Source: https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- `--changed-since=<ref>` selects targets owning files changed since the ref. Alone it covers only the directly changed
  files. `--changed-dependents=direct` adds immediate dependents; `=transitive` adds the whole chain. Example from the
  page: `pants --changed-since=origin/main --changed-dependents=transitive test`. The page recommends diffing against
  `git merge-base HEAD origin/main`.
- Depth: only the two named levels. There is no integer depth. `direct` is the narrowing lever.
- Third-party: a change to one requirement in a lockfile or `python_requirements` generator marks all users of any
  dependency as changed, transitively (the lockfile case is the same shape as our `dependency` globs).
- Selection unit is the file-level target: `python_tests` generates one `python_test` target per test file, and
  Python imports are inferred per file (https://www.pantsbuild.org/stable/docs/using-pants/key-concepts/targets-and-build-files).
  So a change to `panel_framework/foo.py` selects only the files that import `foo` (directly or transitively), not the app.
- Conftests and fixtures: `[python-infer] conftests` (default on) makes a test target depend on every `conftest.py` in its
  directory and ancestors, so a changed `conftest.py` selects exactly the tests under its directory, not the suite.
  `init_files` (default `content_only`) does the same for non-empty `__init__.py`. `string_imports` (default off) infers
  dependencies from dotted strings such as Django settings paths or `pytest_plugins` entries; `string_imports_min_dots`
  default 2. `unowned_dependency_behavior` (`error`/`warning`/`ignore`) sets what an import Pants cannot map does.
  Source: https://www.pantsbuild.org/stable/reference/subsystems/python-infer
- The fetched pages do not say how `--changed-since` treats a changed file that no target owns or a config file such as
  `pants.toml` (not verified; background knowledge is that Pants itself invalidates on its own config, and unowned files
  select nothing, but treat that as unconfirmed).
- Opt-in: command-line flags per invocation, plus `[python-infer]` keys in `pants.toml`.

### Bazel, bazel-diff, target-determinator

- bazel-diff: https://github.com/Tinder/bazel-diff . `generate-hashes` writes a SHA256 per target from rule implementation,
  attribute hashes and the hashes of its `rule_inputs`, recursively; source files are hashed by content. Running it at two
  revisions and diffing gives the impacted set via `get-impacted-targets`.
- Depth: the set is the full transitive closure, but with `-d/--depEdgesFile` each impacted target gets `target_distance`
  (hops to the nearest directly impacted target) and `package_distance` (hops crossing a package boundary). A CI can cut by
  distance. This is the closest published analogue to "limit on import depth".
- Directly impacted = own attributes or source files changed; indirectly = only a dependency changed. `--targetType` filters
  results to, for example, test targets.
- target-determinator: https://github.com/bazel-contrib/target-determinator . Determines which targets were affected between
  two commits using cquery and hashing. Config surface found: `--ignore-file` ("shan't affect the Bazel graph"),
  `--filter-incompatible-targets`, `--verbose` (explains why each target runs). The page gives no depth control.
- Shared files: Bazel is exact because every shared file is a declared input of the targets that use it. A changed shared
  file with no declared consumer affects nothing, and one with declared consumers affects only them. The lesson: escalation to
  everything is a fallback for files whose consumers are unknown; give them a consumer list and they stop escalating.
- Opt-in: all flags, no project-level table on the pages read.

### Nx affected

- Source: https://nx.dev/ci/features/affected
- Selection unit is the task, selected when a changed file is one of its `inputs`. It is not selected by task-hierarchy
  position. Tasks that read the outputs of selected tasks are selected too.
- `namedInputs` define what counts as a change: a `production` input that excludes spec files means a spec-only change does
  not select `build`. This is the equivalent of per-kind rules in `[tool.test_tiers]`.
- Lock file: by default affects every task. `projectsAffectedByDependencyUpdates: "auto"` in `nx.json` limits it to projects
  whose resolved dependencies changed.
- Depth: no depth setting documented.
- Opt-in: Nx 23 and earlier select by project (a change runs every task of the project and its dependents); Nx 24
  `affected.legacy` (or `NX_LEGACY_AFFECTED`) switches back. The newer, narrower behaviour was shipped as the new default with
  an explicit legacy switch, the reverse of this spec's chosen default (answers.md says narrowing is opt-in).

### Turborepo

- Source: https://turborepo.dev/docs/reference/run
- `--filter=...[ref]` selects packages changed since the ref plus all their dependents. `...` before a name = dependents,
  after = dependencies, `^` omits the package itself. `--affected` is `--filter=...[main...HEAD]`.
- Depth: not documented for `...`; it is unbounded. Narrowing is done by filter shape, e.g. `--filter=[main]` (changed
  packages only) versus `...[main]`.
- Shared files: `globalDependencies` globs in `turbo.json` (or `--global-deps`) are hashed into every task, so a change to
  one invalidates everything. The page does not say how `globalDependencies` interacts with `--filter`.
- Selection unit: package (as is our app).

### pytest-impacted (closest Python match)

- Source: https://pypi.org/project/pytest-impacted/
- Unit: Python module. Changed files map to modules without importing them; an AST-built import graph carries impact to test
  modules. A changed package `__init__.py` counts as a change to every module in the package.
- Depth: transitive, no limit, no depth option.
- conftest: a changed `conftest.py` impacts all tests in its directory and below. A conftest imported by a conftest, or fixture
  code it imports, does the same. With `--impacted-conftest-imports`, a conftest that imports changed application code also
  impacts everything under it; without it a notice names the affected conftests. A change reaching a `pytest_plugins`,
  `-p` or `PYTEST_PLUGINS` plugin impacts all tests. So `conftest.py` is scoped to its subtree, not the suite.
- Config files: `uv.lock`, `requirements*.txt`, `pyproject.toml`, `pytest.ini` impact all tests (`--no-impacted-dep-files`
  disables). `--impacted-invalidate-all GLOB` adds more full-suite triggers. `--impacted-map GLOB=PATH` ties a non-Python file
  (template, fixture, JSON) to a test file, module, conftest or directory. This is the rule table that replaces `full` for a
  path the graph cannot see.
- Opt-in: `[tool.pytest.ini_options]` keys `impacted`, `impacted_module`, `impacted_git_mode`, `impacted_base_branch`,
  `impacted_tests_dir`, `impacted_invalidate_all`, `impacted_map`, `impacted_conftest_imports`, `impacted_unimpacted`,
  `no_impacted_dep_files`. Unimpacted tests are deselected by default (`skip` optional).
- A reverse BFS from changed modules to tests is what we would need, at module granularity instead of app granularity.

### Python graph libraries

- grimp: https://grimp.readthedocs.io/en/stable/usage.html . `build_graph(pkg, include_external_packages=...)`;
  `find_downstream_modules(module, as_package=False)` returns every module that imports it, directly or indirectly (no depth
  argument); `as_package=True` treats the module plus its descendants as one unit and excludes modules inside the package.
  `find_shortest_chain(importer, imported)` / `find_shortest_chains(..., as_packages=True)` / `chain_exists` give chain length,
  so a depth cap can be applied by computing shortest-chain length per candidate. `modules_directly_imported_by` /
  `find_modules_that_directly_import` exist for one-hop use (not fetched here; confirm). grimp is a third-party dependency, so
  using it in the stdlib-only `ds` script would break "Stdlib only, like its siblings"; `ast` parsing gives the same graph.
- import-linter (same author, https://import-linter.readthedocs.io): the fetched contract page returned 404, so nothing
  verified. Its documented purpose is forbidding or layering imports, not test selection.
- pydeps: not researched. It draws import graphs and offers a `--max-bacon` depth cut, but I did not fetch it (unverified).

### pytest-picked and pytest-testmon (contrast)

- pytest-picked: https://github.com/anapaulagomes/pytest-picked . Runs tests from modified or untracked **test files** found
  with git status (`--mode=unstaged`) or against a parent branch (`--mode=branch`, `--parent-branch`). No import graph: a changed
  source file selects nothing. That is equivalent to our `test_file_decision` only.
- pytest-testmon: https://pypi.org/project/pytest-testmon . Records per-test coverage of files and methods in `.testmondata`
  and reruns tests whose recorded code changed. Out of scope for this spec (idea.md), noted only because it makes
  fan-out accurate at method level without any rule table.
- Django's own runner: no changed-file selection. `manage.py test` takes labels; I found no mechanism comparable to the above.
  (Not researched in depth.)

## Blog / guidance on rule tables

- Nx monorepo CI practices: https://nx.dev/docs/kb/monorepo-ci-best-practices
- One search result summarised a Python change-detection tool, difftrace (https://pypi.org/project/difftrace/), as mapping a
  changed file to a package by longest source-path prefix and doing a reverse BFS over the package graph; I could not load the
  page, so this is second-hand.
- Search-result guidance (helpmetest, https://helpmetest.com/blog/monorepo-ci-cd-testing-strategy/ ; oneuptime,
  https://oneuptime.com/blog/post/2026-07-28-monorepo-only-affected-builds/markdown): an affected algorithm cannot infer a
  relationship the build model does not contain, so declare explicit edges for undeclared dependencies, and run all when
  root-level config changes. Content not opened by me, only the search summaries.
- I found no Django-specific write-up of a path-to-test rule table or a documented rule for `conftest.py`; the nearest
  documented handling of conftest is Pants and pytest-impacted above.

## What this means for the open questions

Observations, not decisions:

1. **Fan-out narrowing.** Three levers appear in practice.
   - A depth cap: Pants `direct` vs `transitive`; bazel-diff `target_distance`. For a depth-1 cap the `importers()` chaining loop
     (`queue.append(src)`) would stop after the first hop; a per-app cap fits an opt-in table like `[tool.test_tiers]`.
   - A finer unit than the app: Pants (file target), pytest-impacted (module), grimp (`as_package`). Select only the importer
     tests whose modules reach the changed module, not the importer app's whole tests dir. This is the most accurate, and the
     only one of the three that does not trade correctness for width. It needs a module/test-file import graph, which the app
     map (`docs/app_structure.md`) does not hold.
   - A per-app setting: closest equivalents are Nx `projectsAffectedByDependencyUpdates` and Pants `[python-infer]` toggles, both
     project-level config.
2. **Escalation globs.** Every reference scopes shared files rather than escalating: Pants `conftests` inference and
   pytest-impacted scope `conftest.py` to its own directory subtree; pytest-impacted `--impacted-map` ties a non-Python file to
   named tests; Bazel needs declared consumers. Only dependency manifests and global config (`pyproject.toml`, lock files) are
   `full` everywhere (pytest-impacted, Nx, Pants lockfile, Turborepo `globalDependencies`). `upstream` handling already in
   `select_tests.py` (`related_tests_decision`) is the same shape: scoped to related apps. Candidates: `conftest.py` selects its
   directory subtree; `factories.py`/`urls.py` select the owning app plus its direct importers (mirror of Pants `direct`);
   `migrations/**` and settings keep `full` (as every reference does for global config) unless there is a documented reason.
3. **Unmapped paths.** References do not escalate on an unowned file: Pants and Bazel select nothing; pytest-impacted offers
   `--impacted-map`. A project-level glob-to-tests table (like `tooling`) is the established pattern; `demo_content/` would be one
   entry.
4. **Opt-in shape.** `[tool.pytest.ini_options]` for pytest-impacted and `pants.toml` for Pants both hold the whole rule set in
   the project config file; Nx makes the narrower mode a switch (`affected.legacy`). Each narrowing knob can default to today's
   behaviour (answers.md: opt-in per project).

## Sources

- https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- https://www.pantsbuild.org/stable/reference/subsystems/python-infer
- https://www.pantsbuild.org/stable/docs/using-pants/key-concepts/targets-and-build-files
- https://github.com/Tinder/bazel-diff
- https://github.com/bazel-contrib/target-determinator
- https://nx.dev/ci/features/affected
- https://nx.dev/docs/kb/monorepo-ci-best-practices
- https://turborepo.dev/docs/reference/run
- https://pypi.org/project/pytest-impacted/
- https://grimp.readthedocs.io/en/stable/usage.html
- https://github.com/anapaulagomes/pytest-picked
- https://pypi.org/project/pytest-testmon
- https://pypi.org/project/difftrace/ (second-hand)
- https://helpmetest.com/blog/monorepo-ci-cd-testing-strategy/ (search summary only)
- https://oneuptime.com/blog/post/2026-07-28-monorepo-only-affected-builds/markdown (search summary only)

status: ok
