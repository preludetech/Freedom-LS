# Research: best practices for static, import-graph test selection (spec 8)

Scope: static path and import-graph selection for a Django + pytest monorepo, a narrow per-batch run, a full run at the end. Coverage-based selection is out of scope and appears only as contrast. Findings marked **[source]** come from the cited pages. Findings marked **[inference]** are my own reasoning, not stated by a source. I did not read every source in full; search summaries were used for some, which are noted.

## 1. Limiting transitive import fan-out

What the established tools do:

- **Pants** exposes the choice as a setting. `--changed-dependents` takes `none`, `direct` or `transitive`, and defaults to `none`. A common CI pattern is `--changed-since=origin/main --changed-dependents=transitive`. **[source]** https://www.pantsbuild.org/dev/reference/subsystems/changed ; https://pantsbuild.org/2.18/reference/subsystems/changed
  Pants's `--changed-*` only narrows first-party targets. A lockfile change did not narrow results (reported in Pants community chat). **[source]** https://chat.pantsbuild.org/t/9729028/is-there-a-way-to-find-out-whether-or-not-the-transitive-dep
- **Bazel, Nx and Pants** all define "affected" as the full reverse-transitive closure over a graph of **targets or projects**. Their safety comes from fine-grained, explicit targets. Cutting the closure off at a depth is not their method. **[source, summarised]** https://nx.dev/concepts/affected
- **Static class-level RTS research (Ekstazi, STARTS)** selects at class granularity, which is the module analogue in Python. It takes the transitive closure over a class-level dependency graph. Class level beat finer method-level selection on cost and safety. A static method-level technique "performs rather poorly". **[source]** https://mir.cs.illinois.edu/~marinov/publications/LegunsenETAL16StaticRTS.pdf
  Class-level selection can be unsafe for changes outside class files (non-code files) and for reflection. **[source]** https://par.nsf.gov/biblio/10603280
  Even at class level, STARTS and Ekstazi re-ran some tests needlessly for some edits (15 and 22 test classes in the cases examined). **[source]** https://par.nsf.gov/servlets/purl/10421200
- **Google TAP** found that tests that fail are generally "closer" to the code they test. Of 5.5M affected tests analysed, only 63K ever failed. TAP's response was to skip tests unlikely to fail, using distance and history signals, and to keep a later, broader run as the safety net. **[source]** https://research.google/pubs/taming-google-scale-continuous-testing/ ; the follow-up on selection algorithms is https://research.google/pubs/assessing-transition-based-test-selection-algorithms-at-google/

Trade-offs (partly **[inference]**):

| Option | Safety | Precision | Notes |
|---|---|---|---|
| Full transitive closure at app level (today) | Highest of the static options | Poor; one line in `panel_framework` selects 36 apps | Graph granularity is the problem, not the closure. |
| Transitive closure at **module** level | Same safety class as Ekstazi/STARTS class-level RTS | Much better: only importers of the changed module, and of their importers, are selected | Matches the research consensus (finest granularity that is still cheap to compute). Re-export hubs (`__init__.py`, `models.py` that import everything) can re-widen it. |
| Direct importers only (depth 1) | Unsafe when the changed module is behind a re-export or a base class (a test imports `B`, `B` imports `A`) | Highest | Pants offers `direct` as an option but defaults to none. Treat as a deliberate speed-for-safety choice. |
| Bounded depth (2 or 3) | A heuristic; misses deep chains | Middle | Consistent with TAP's "closer is likelier" finding, but TAP uses it to rank, with a broader run behind it. |
| Per-app setting (for example a `fan_out` cap per widely imported app) | Depends on the setting | Tunable | Mirrors Nx/Pants per-project overrides. Needs upkeep. |

Best-practice reading: **move the graph to module granularity first** (the same closure, much smaller selection), and use depth limits only as an opt-in for the tail. Because the full run at the end covers the escapes, bounded depth is defensible here. It is not in tools that have no later safety net. **[inference]**

Tooling for a Python graph: grimp builds an import graph and answers `find_downstream_modules` (everything that imports a module, even indirectly), `find_upstream_modules`, and shortest-path queries. The upstream/downstream names changed across versions, so pin the version and check its docs. **[source]** https://grimp.readthedocs.io/en/v3.2/usage.html ; https://github.com/python-grimp/grimp . import-linter is built on grimp, and I did not confirm details of how it uses it.

Django-specific hazards for import graphs **[inference]**: string-based references (`INSTALLED_APPS`, `ROOT_URLCONF`, `include("app.urls")`, `apps.get_model`, `settings.X = "dotted.path"`, signal registration in `AppConfig.ready`) are not seen by an import graph. Static RTS research calls out the same reflection gap. Rules in `[tool.test_tiers]` should cover these explicitly, or the graph should be built from them as extra edges.

## 2. Shared fixtures, URL confs, factories, migrations, settings, lockfiles

Established treatment:

- **Global/shared config defaults to "everything affected".** Nx: changing `nx.json` or a global config path affects all projects. A lockfile change affects every task by default, and `projectsAffectedByDependencyUpdates: "auto"` narrows it to projects whose resolved dependencies changed. A path declared a shared global input is pulled into every project's inputs. **[source]** https://nx.dev/docs/reference/inputs (and the named-input pages: https://19.nx.dev/reference/inputs) ; https://nx.dev/deprecated/global-implicit-dependencies
- **Narrowing needs an explicit mapping, and a mistake there causes over- or under-selection.** One Nx issue shows a single shared file declared globally rebuilding unrelated projects, and the fix was a project-level dependency. **[source]** https://github.com/nrwl/nx/issues/9426
- **Pants** treats a lockfile as third-party and does not narrow by it. **[source]** link in section 1.
- For **pytest-testmon** (contrast only): it relies on coverage, and its docs describe data files as a gap where the developer should declare the dependency. I found no official statement on `conftest.py`. **[source]** https://pypi.org/project/pytest-testmon/0.9.7 ; https://pypi.org/project/pytest-testmon

Practical mapping, **[inference]** built from the above and pytest semantics:

| Path | Common treatment | Suggested mapping here |
|---|---|---|
| `conftest.py` | pytest scopes it by directory | Select the tests under that `conftest.py`'s directory (its subtree). Only the root `conftest.py` and plugin files mean full. This is the exact rule pytest uses, so it is safe. |
| `factories.py` | Ordinary code imported by tests | Treat as a module in the import graph (importers of it). Escalate only if a shared factories base is imported broadly. |
| `urls.py` | Resolved by string; a root urlconf feeds `reverse()` everywhere | App `urls.py`: the app's tests plus tests that `reverse` its names (grep for `app_name:`); the root urlconf: full. |
| `migrations/**` | Run by test DB creation for every test | A changed migration affects every test DB build. Keep it full, or select tests of the owning app plus a migration check, with the final full run as backstop. Name the run that covers it. |
| `settings`/`config/**` | Global input | Full for shared settings; test-only or per-environment settings can be mapped. |
| Dependency lockfile / `pyproject.toml` | Nx and Pants default to everything or do not narrow | Full is the norm. Narrowing means diffing resolved packages and selecting importers of the changed package (the Nx "auto" idea). Only worth it if lockfile-only batches are frequent. |
| `apps.py` | Loaded at startup for all tests | Full, or the owning app plus its importers. |

The spec's "no rule is dropped without naming the run that still covers it" matches the Google/Meta model: a narrow tier is only trusted because a wider tier follows. **[inference]**

## 3. Mapping non-code assets (content and data files)

- Tools that follow imports cannot see data files. This is a known safety gap in class-level static RTS, which can fail to select tests affected by non-class files. **[source]** https://par.nsf.gov/biblio/10603280 ; testmon's advice is to declare the file dependency by hand. **[source]** https://pypi.org/project/pytest-testmon/0.9.7
- Bazel/Pants model this as an explicit dependency (a resource or file target on the test). Nx models it through `inputs` globs. **[source]** https://nx.dev/docs/reference/inputs
- Recommended practice **[inference]**: a **glob-to-test-paths rule** in configuration (for example `demo_content/**` maps to the test directories of the apps that load or render demo content), kept next to the code in `[tool.test_tiers]`. Two ways to find the mapping: declare it by hand per glob, or derive it once by grepping tests for the directory name or path, and keep the declaration for CI to review. Prefer a small, honest map over `full`, and add a unit test that fails when a new top-level content path has no rule (the "unmapped path" guard).

## 4. Staged verification and measuring escapes

- **Meta**: predictive selection ran a subset and still reported over 95% of individual failures and over 99.9% of faulty changes, at about half the infrastructure cost. Flaky tests were handled by retrying failures in the training data. **[source]** https://arxiv.org/pdf/1810.05286.pdf ; https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/
- **Google TAP**: selection is paired with later, broader runs, and the number of tests failing is tiny relative to the number run. **[source]** https://research.google/pubs/taming-google-scale-continuous-testing/
- **Launchable**: defines confidence as the probability that a subset catches a failing session, evaluated on held-out sessions where the full result is known. The curve runs from 0% (no tests) to 100% (full suite). The docs describe no separate post-hoc escape metric. **[source]** https://help.launchableinc.com/features/predictive-test-selection/requesting-and-running-a-subset-of-tests/choosing-a-subset-optimization-target/ ; https://help.launchableinc.com/features/predictive-test-selection/requesting-and-running-a-subset-of-tests/choosing-a-subset-optimization-target/how-a-confidence-curve-is-generated/

How a team measures escapes **[inference]**, consistent with the above:

1. **Escape** = a failure in the later full run (or a later batch's full run) for a test the earlier narrow run did not select, where that failure is attributable to the earlier batch's change. Rate = escaped failing batches / batches.
2. Offline: replay the selector over history, as the research file did with the 119 batches. For each past failing full run, check whether the narrow tier would have selected the failing test (recall). The replay covers recall; the saving is the selected-test count against the suite.
3. Log, per batch, the selection reason (rule or path) and the tier, so an escape can be traced to the rule that missed it. Tighten or revert that rule.
4. Target an escape rate agreed up front, then widen the rule that caused the most escapes first. Keep a periodic shadow full run on a sample of batches to measure recall even when the end-of-work full run passes.
5. Separate flaky failures from escapes (Meta's retry approach).

## 5. A small follow-up fix commit: fix diff or cumulative diff

I found no source that addresses review-fix commits directly. What is available **[inference]**:

- The tools cited all select from a diff against a base ref (`--changed-since`, `nx affected --base`). They do not pick a per-commit diff by default. CI-style tools compare the branch to the merge base, which is the cumulative diff.
- A fix diff alone is **unsafe in one specific case**: a fix touches module B, which the batch's own earlier changes (module A) also affect through shared state. Tests selected from B alone may not exercise A's combined effect. The cumulative diff is the safe choice and the fix-only diff is the fast one.
- Compromise: select from the fix diff **union** the tests that failed in the batch's previous run (this is the rerun-failures idea in `faster-test-runs-10`), and let the final full run catch the rest. A fix-only selection is reasonable when the fix is confined to files the batch already ran green on, and the final full run exists. This follows Google's use of closeness: the tests nearest the fix are the likeliest to fail. **[source for closeness]** https://research.google/pubs/taming-google-scale-continuous-testing/
- Choose by which diff the fix run is expected to protect: "does my fix pass" (fix diff plus previous failures) against "is the batch still green" (cumulative diff).

## Recommendations for the spec

1. Build the importer graph at module level (grimp, version pinned) and take the closure over that graph. Make it opt-in in `[tool.test_tiers]`, per the answers file. The depth limit is a second knob and stays off by default.
2. Add explicit edges or rules for Django's string references (urlconfs, `INSTALLED_APPS`, `AppConfig.ready` imports).
3. Scope `conftest.py` to its directory subtree. Keep root `conftest.py`, root settings, lockfiles and root urlconf as `full`, or name the run that covers each when narrowed.
4. Map `demo_content/**` through a glob rule, and add a guard test for unmapped top-level paths.
5. Record the rule and tier per batch so escapes can be traced, and replay the 119 batches to measure recall and saving before turning narrowing on.
6. For fix runs, select from the fix diff plus previous failures, with the final full run as the backstop. The cumulative diff stays available as an option.

## References

- Meta, Predictive Test Selection: https://arxiv.org/pdf/1810.05286.pdf ; https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/
- Google, Taming Google-Scale Continuous Testing: https://research.google/pubs/taming-google-scale-continuous-testing/ ; https://research.google/pubs/assessing-transition-based-test-selection-algorithms-at-google/
- Pants changed options: https://www.pantsbuild.org/dev/reference/subsystems/changed ; https://pantsbuild.org/2.18/reference/subsystems/changed ; https://chat.pantsbuild.org/t/9729028/is-there-a-way-to-find-out-whether-or-not-the-transitive-dep
- Nx: https://nx.dev/concepts/affected ; https://nx.dev/docs/reference/inputs ; https://nx.dev/deprecated/global-implicit-dependencies ; https://github.com/nrwl/nx/issues/9426
- Launchable: https://help.launchableinc.com/features/predictive-test-selection/requesting-and-running-a-subset-of-tests/choosing-a-subset-optimization-target/ ; https://help.launchableinc.com/features/predictive-test-selection/requesting-and-running-a-subset-of-tests/choosing-a-subset-optimization-target/how-a-confidence-curve-is-generated/
- Static RTS research: https://mir.cs.illinois.edu/~marinov/publications/LegunsenETAL16StaticRTS.pdf ; https://par.nsf.gov/servlets/purl/10421200 ; https://par.nsf.gov/biblio/10603280
- grimp: https://grimp.readthedocs.io/en/v3.2/usage.html ; https://github.com/python-grimp/grimp
- pytest-testmon (contrast): https://pypi.org/project/pytest-testmon ; https://pypi.org/project/pytest-testmon/0.9.7
- Not checked: pytest-picked, Bazel docs directly, import-linter docs.

status: ok
