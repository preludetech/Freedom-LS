# Research: prior art (faster-test-runs-8-narrower-targeted-tier)

Question: what has already been tried for narrowing the targeted tier's selection, here or elsewhere,
and what happened?

Limits: no shell, so no `git log`. "Here" comes from done specs under `spec_dd/3. done/`, the current
`claude_plugins/django-stack/scripts/select_tests.py`, and `spec_dd/1. next/faster-test-runs/research_batch_test_load.md`.

## 1. Here

### 1.1 Origin: `2026-10-09_09:03_make-sdd-more-efficient` (the tiers)

- Introduced `none` / `targeted` / `full`, `select_tests.py` and `[tool.test_tiers]`.
- **Importers were planned as direct only.** Its plan (Slice 3, `2. plan.md` ~l.506-510) says "Direct
  importers only; the spec names the apps that import the changed app, not the transitive closure",
  and `idea.md` l.118-119 defines importers as "direct deps, not the transitive closure". The
  `importers()` code now chains runtime deps (`select_tests.py:197-218`: "an app that imports an
  importer of `app` runs `app`'s code too"; a test-only dep is one hop). I found no done spec that
  records the change from direct to transitive. It is undocumented drift: the plan's decision was
  direct, the code does transitive. So narrowing back to direct is a return to the original decision,
  not a reversal of a reasoned one. The reason the code chains is stated only in the docstring:
  correctness, since an app that imports an importer runs the changed code.
- **Escalation is an explicit glob list, on purpose.** `research_tiered_gating.md` l.77: "an LLM will
  follow a list more reliably than 'use judgment'". The globs (migrations, `conftest.py`, factories,
  fixtures, `urls.py`, middleware, signals, `apps.py`, `pyproject.toml`, `uv.lock`) are "paths with fan-out
  the mirror and the app map cannot see" (plan l.306): the import graph cannot see that a root
  `conftest.py` or a `urls.py` affects tests that never import it. That is the reason they escalate.
- **Unknown means full**: an unmapped tracked path, a missing app map, or a selector failure all give
  `full`. Skipping on doubt was rejected. This is why `demo_content/**` escalated: no rule knew it.
- FLS escalation globs in `[tool.test_tiers]`: `config/**`, `site_aware_models/**`, `content_base/**`.
- Generic plugins stay generic; FLS values live in `[tool.test_tiers]`.
- CI on the PR is the backstop; `implement_plan` keeps a guaranteed full run.
- pytest-testmon rejected (coverage conflict, no template/static tracking, cold start per worktree);
  left open as a possible later refinement. The idea marks it out of scope.

### 1.2 `2026-11-21_16:08_full-test-run-still-too-often`

Already narrowed escalation, but only for upstream paths (paths main brought in via `--upstream-range`):

- Added provenance (upstream path vs branch path), `app_dependencies()` (related apps) and the rule that
  an upstream escalation glob selects tests only when its owning app is a related or dependent app
  (spec req 4.4); otherwise `none` with a `why: ... (from main; ...)` line. Dependency files
  (`pyproject.toml`, `uv.lock`, `.python-version`, `package*.json`, plus project `dependency_files`) still
  force `full` from either side. Spec req 5: branch paths keep today's rules, so an unmapped branch path
  or a branch `conftest.py` still means `full`. Req 9: FLS escalation globs stay, "scoped by rule 4.4".
- Its research (`research_best_practices.md` l.33): "Scope escalation globs by dependency. A conftest in
  `app_x/` escalates `app_x` and its dependents only. Pants and Bazel scope by package for this reason.
  Only the root conftest and lockfiles are truly global." This was applied to upstream paths only. The
  branch-side escalation globs were not scoped. That is the remaining gap this spec addresses (9 of the 34
  `full` batches were `**/conftest.py`, 2 `urls.py`, 2 `factories.py`).
- Decisions to keep: "unknown means full" for branch paths; dependency files escalate; a skip is never
  reported as a pass; every dropped path gets a visible `why:` line (UX research: "A silent drop looks like
  a bug"); an escalation glob stays a list.
- Test expectations to reuse: neutral app names (`app_a`, `app_b`) in a temp repo, one test per rule in
  `tests/test_select_tests.py`.

### 1.3 The measurement behind this spec

`research_batch_test_load.md` ("What a batch's targeted run selects"), 119 batches since 2026-11-19:
34 `full`, 35 targeted at 28-38 of 42 app test directories, 47 targeted at 1-5, 3 `none`. Reasons for
`full`: unmapped path 14 (3 are `demo_content/**/*.md`), `conftest.py` 9, `config/**` 3, `urls.py` 2,
`factories.py` 2, dependency file 2, migrations 1, `apps.py` 1. One file in `base` selects 38 test
directories, `panel_framework` 36, `accounts` 36, `icons` 30, `content_engine` 28.

### 1.4 Not tried before

Nothing in the repo has limited import depth, added a per-app fan-out setting, or selected by importing
module rather than by app. The idea's three open options are all untried here.

## 2. Elsewhere

- **Pants** (`--changed-dependents=direct|transitive`). The docs recommend `transitive` for PR presubmit and
  do not say when `direct` is right; they warn lockfile changes can select more than expected. Pants has
  the same two depths this spec weighs, and its guidance leans to transitive.
  https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection
- **Nx affected.** Project graph selects affected projects (transitively); a lockfile change marks all
  affected; touching a widely used project affects most of the workspace, the same shape as `base` here.
  Nx lets projects opt out of dependency-update escalation ("projectsAffectedByDependencyUpdates"), a
  per-project setting analogous to a per-app option.
  https://nx.dev/ci/features/affected
- **Google TAP.** Presubmit runs tests directly relevant to a change; wider and periodic runs near HEAD
  catch what selection missed. A related Google paper argues for conservative, complete (transitive)
  selection because missing transitive dependencies is how failures are missed and also makes blame
  harder (found via search summary, not read in full):
  https://research.google/pubs/what-breaks-google/
  https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/
- **Facebook predictive test selection (ICSE 2019).** Compared with selecting all transitively dependent
  tests, a learned model ran about a third of them, caught over 95% of individual failures and over 99.9% of
  faulty changes, and halved infrastructure cost. It is a cost trade, not a guarantee, and relies on
  a later full run.
  https://ar5iv.arxiv.org/html/1810.05286
  https://engineering.fb.com/developer-tools/predictive-test-selection/
- **Academic RTS studies.** One CI study found that selection skipped some tests that later failed
  under a full rerun, almost all flaky. A study of a large Java ecosystem reports that rerunning all tests
  of all transitive clients is costly, which pushes teams to depth limits or sampling.
  https://par.nsf.gov/servlets/purl/10175678
  https://mir.cs.illinois.edu/gyori/pubs/issre18.pdf
- **Practitioner report**: direct-change-only selection often missed transitive and system-wide impact; the
  author kept a full integration run in CI as the backstop.
  https://dev.to/gabrielholmesqa/how-to-know-which-tests-a-pr-will-break-before-ci-runs-44b8
- **Datadog Test Impact Analysis.** Documents what selection cannot see (library changes, config, data
  files), a `ITR:NoSkip` force-full override, and excluding the default branch so everything runs before production.
  https://docs.datadoghq.com/tests/test_impact_analysis/troubleshooting/
- **pytest-testmon** (out of scope, already rejected): https://testmon.org/blog/determining-affected-tests/

I did not find a published account of a team moving from transitive to direct dependents and then
measuring missed failures. The evidence is indirect.

## 3. What this means for the spec

- Narrowing importer depth restores the original 2026-10 decision (direct importers). The cost is named by
  the literature: transitive dependents are where missed failures live, so something must still cover them.
  Here that is `implement_plan` Step 3's full run and CI on the PR (both stay per the idea).
- Narrowing branch-side escalation globs follows the pattern already applied to upstream paths (rule 4.4)
  and the Pants/Bazel "scope by package" advice. Root `conftest.py`, `config/**`, dependency files and
  anything with no owning app remain truly global. A glob list, not judgment, should still decide.
- Opt-in per project (answers.md): consistent with "generic plugins stay generic"; the default stays
  today's wide behaviour. A per-app setting parallels Nx's per-project opt-out.
- Each rule dropped needs a named run that still covers it (settled in the idea); name `implement_plan`
  Step 3, and keep `why:` lines for every narrowed path so a drop is visible.
- `demo_content/` is an unmapped path, not a deliberate escalation. Adding a rule respects "unknown means
  full" because the path becomes known.
- Pitfall: when `importers()` limits depth, the `why:` text ("through X") and the related-apps code
  (`app_dependencies`, also transitive) need a consistent decision, or upstream and branch selection diverge.

status: ok
