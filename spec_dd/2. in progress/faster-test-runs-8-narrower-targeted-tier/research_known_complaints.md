# Research: known complaints about narrowed test selection

Topic: `known_complaints`. Scope: what developers complain about with static and affected test selection and with narrowed CI test tiers, and what this repo's own history shows. Web findings come from search results and, where noted, one opened issue. Most issue links are leads, not read in full.

An earlier pass on the same subject is `spec_dd/3. done/2026-11-21_16:08_full-test-run-still-too-often/research_known_complaints.md`. It covers over-selection through lockfiles, merge-base errors, last-green staleness and flakes. This file does not repeat that and adds what is specific to narrowing fan-out and escalation globs.

## 1. Over-selection when a core module changes (the idea's main problem)

- **Shared libraries make every dependant affected.** Nx's docs name the cause: shared libraries often hold utilities only one project needs, but touching the library affects every project that imports it. Their advice is to split apps and libs more finely and to use strict named inputs. https://nx.dev/docs/features/ci-features/affected · https://nx.dev/docs/kb/reduce-waste
  - FLS match: `panel_framework` changing selects 36 of 42 app test directories. The unit of selection is the app, as it is a project in Nx. The Nx remedy is a finer unit (the importing module, not the importing app).
- **An implicit-dependency or global input widens too far.** Nx issue #9426: one `implicitDependencies` entry (a GraphQL schema) made an unrelated project miss its cache. A second user saw the same for a `.env` file. Maintainers agreed the effect should reach only the owning project and its consumers. The workaround was to move the file into its own small project that only its users depend on. The issue was closed stale, with no recorded fix. https://github.com/nrwl/nx/issues/9426 (opened and read)
  - FLS match: a `conftest.py`, `urls.py` or `factories.py` glob escalating to `full` is the same shape. The Nx workaround is the same idea as scoping a glob to its own directory.
- **Fix in Nx: inputs per target.** PR #22573 made "affected" depend only on the inputs a target uses. https://github.com/nrwl/nx/pull/22573
- **Opt-in smarter behaviour.** Nx offers a setting to mark projects affected by a dependency update only if they use that dependency. Conservative stays the default. https://nx.dev/docs/features/ci-features/affected
  - Matches the answered decision: narrowing is opt-in per project.
- **Pants over-selects through target generators.** A user found transitive dependents pulled in unrelated tests from the same generator. The suggested workaround was `--changed-generators=direct` together with disabling import inference. Flag semantics were reported as confusing. https://chat.pantsbuild.org/t/16090968/hello-wave-recently-i-ve-noticed-that-a-target-generator-is- · https://chat.pantsbuild.org/t/10504237/i-m-seeing-some-interesting-behavior-if-i-change-a-yaml-file
- **Complaint to expect:** "Direct only" narrowing (one hop) is the usual fix and the usual source of the next complaint, under-selection (section 2).
- **Broad reruns can be by design.** The pytest-testmon docs say it "selects too many tests" depending on the change, and that this is most likely by design. https://pypi.org/project/pytest-testmon/0.9.7

## 2. Under-selection: escapes found late

- **Static graphs miss non-import links.** pytest-impacted builds an AST import graph and falls back to all tests when dependency files change. It cannot see references that are only strings. https://pypi.org/project/pytest-impacted/0.22.0/
- **Django wires things by string at run time.** `INSTALLED_APPS` entries, URL `include("app.urls")`, template names, `apps.get_model("app.Model")`, signal receivers in `apps.py` `ready()`, settings dotted paths and `import_string` calls. Django's own tracker has a case of `import_string` on a test path held in a string, which no import graph sees (https://groups.google.com/g/django-updates/c/d5CIxXaa0EU, a search result I did not open). A Django forum thread notes that adding a signal made existing tests fail in other apps that had never imported the receiver (https://forum.djangoproject.com/t/tests-signals-fixtures-mixing-of-levels-between-apps-and-project/4239, search result only).
  - I found no complaint specific to Django selection tools. The point is inferred from how these links work, not quoted from users.
- **Jest `--findRelatedTests` misses.** Issue "findRelatedTests misses tests, especially in multi-project setups" was closed stale. https://lightrun.com/answers/facebook-jest-bug-findrelatedtests-misses-tests-especially-in-multi-project-setups · Aliased imports break Stryker's use of it: https://stncp.dns-dynamic.net/stryker-mutator/stryker-js/issues/4773 · Dynamic imports need smart handling: https://gitlab.com/gitlab-org/gitlab/-/issues/118499 · Side-effect-only imports were once missed: https://socket.dev/npm/package/jest-changed-files/overview/24.9.0
- **pytest-testmon blind spots.** Data files and external services are documented as outside its scope. Gaps in coverage mean silent skips. Issue #89 asks for a validation mode that runs everything and warns when selection would have missed a change; it has been open since 2018. https://pypi.org/project/pytest-testmon · https://redirect.github.com/tarpas/pytest-testmon/issues · https://dev.co/testing/open-source/pytest-testmon
- **conftest and fixtures.** I found no issue about testmon or pytest-picked and `conftest.py`. testmon tracks executed code, so a changed fixture in a conftest that ran should select the tests that used it, but this is not documented. For import-graph tools a `conftest.py` is never imported by a test, so it is invisible to the graph. That is why FLS escalates it to `full`. Treat it as a design reason, not a user complaint.
- **Typical defence.** Run affected tests at commit time and always run the full suite in CI. The repo's earlier research says the same: `pytest --picked` is not the only gate. `spec_dd/3. done/2026-04-28_07:25_testing-best-practice/research_tooling.md:562`.
- **Safety bias.** A missed regression is silent. An over-run is only slow. Tools therefore default to over-selection, and narrowing is where trust is lost. https://oneuptime.com/blog/post/2026-07-28-monorepo-only-affected-builds/view

## 3. Late failure versus slower early run

- Developers who narrow runs accept a failure surfacing at the backstop run. The cost is the context switch: the failure arrives after the author has moved on, from a run that is usually 20 minutes or more here.
- Repo data supports the weighting. `spec_dd/1. next/faster-test-runs/research_batch_test_load.md` shows a large run takes a median of 22 minutes and up to 88 under load, and `implement_plan` already ends with a full run. So a narrowed batch run pushes an escape to that final run, once per spec, not to a user.
- `spec_dd/3. done/2026-10-09_09:03_make-sdd-more-efficient/idea.md:81` already states the principle: "CI on the PR is the backstop for anything a targeted run missed."
- A late full-run failure also has to be traced back to the batch that caused it. A narrowed tier needs to leave a record of what each batch ran, or the culprit is found by bisecting batches.

## 4. Hard-to-understand selection

- Nx offers `nx graph --affected` and `nx show projects --affected`. Pants offers `--changed-since ... list` then `dependees --transitive`. testmon offers `--testmon-noselect`. Maintainers point users at these because "why was this selected" is the most common question. https://nx.dev/docs/features/ci-features/affected · https://chat.pantsbuild.org/t/9728293/hi-team-a-hopefully-quick-question-on-changed-dependees-supp
- Import-fan-out limits (depth cap) are hard to explain: a test fails at depth 3 and passes selection at depth 2, and nobody can say why from the output alone.
- FLS match: `select_tests.py` already prints a `Decision(path, tier, tests, reason)` per path. A narrowing rule should add the hop that selected each app (for example "imports `panel_framework` directly").

## 5. Config drift

- Per-app settings and glob lists rot. A new app or a moved directory has no rule, and the selector falls to `full` (today) or, worse after narrowing, to nothing. The earlier research notes an empty run is more dangerous than a full run. See also Nx #9426: a global input added for one project altered others later.
- Mitigation seen in practice: an unknown path fails safe (escalate or warn), and a test that checks every top-level directory has a rule. I did not find a quoted source for the second point; it is my inference.
- Repo evidence of drift risk: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/todo.md:42` records `tests/test_generate_app_map.py::test_check_from_repo_root_exits_0` failing in the full run because a generated app map went stale after a script edit that added an `audit_log` import. A path-to-test rule built on imports only would not have selected that test from a script edit.

## 6. Repo evidence: failures the full run caught that earlier runs did not

The "Fix the tests the full run after the QA fixes left failing" lines in `todo.md` files are the nearest this repo has to a record of escapes. None says "the targeted run missed it" outright. I read them as follows, and have not opened the plans to confirm.

| Spec | Failure the full run found | Escape from selection? |
|---|---|---|
| `2026-11-08_19:37_educator-interface-design-learner-csv-upload-design-fix/todo.md:23` | `learner_interface` Playwright `test_course_browse_flow.py::test_due_date_reads_in_the_browser_time_zone` expects the old text `Mar 15, 2999, 05:59 PM`; `localTime` now renders `15 Mar 2999, 17:59` | Likely yes. A shared rendering change broke a test in another app. A one-hop or app-local rule could miss it. |
| `2026-11-06_08:20_educator-interface-12-docs-and-polish/todo.md:42` | `tests/test_generate_app_map.py` failed from a stale generated app map | Yes by kind. A non-import dependency (a generated artifact) |
| `2026-10-25_17:46_deadlines-1-dates-and-overdue/todo.md:22` | query-budget test `test_resolver.py` fails with 6 queries against a budget of 5 | No. Order-dependent cold cache, so it fails with or without selection. |
| `2026-11-01_23:53_deadlines-2-consequence-policy/todo.md:23` | 24 tests in `tests/test_update_concrete_projects.py` | No. They arrived with a commit from main. |
| `2026-11-11_06:57_design_educator-interface-bulk-action/todo.md:21` | dashboard query-count test, 71 against a limit of 70 | No. Fails on main too. |
| `2026-11-13_08:06_educator-interface-13-staff-roles/todo.md:35`, `2026-11-15_13:44_deadlines-3-extensions-and-pause/todo.md:23`, `2026-11-20_11:24_misure-of-admonitions/todo.md:24` | timeouts under parallel load, a Mock-iteration flake, a Playwright flake | No. Load or order problems. |

Reading: of eight recorded full-run failures, two look like real selection escapes (a shared rendering change and a generated-artifact dependency). Six are order, load, date or main-origin problems that a narrower run would neither cause nor prevent. This is a small sample and the classification is mine. `spec_dd/1. next/audit-log-describe-test-flake/idea.md:1` adds one more flake that shows only in loaded full runs.

I found no review or QA note that says in so many words that a targeted run missed a failure the final run caught.

## Takeaways for the spec

1. Expect the next complaint after narrowing to be escapes through string-wired Django links (URL includes, templates, signals in `ready()`, `get_model`, settings paths). Decide which of these a rule covers and which are left to the final full run, and say so.
2. Narrowing by importing module, not importing app, matches what Nx and Pants users ask for. A depth cap is the least explainable option.
3. Keep `conftest.py`, `urls.py` and `factories.py` escalating only where a narrower scope is provable, for example a conftest in one app selects that app and the apps that import its fixtures. Nx #9426 shows global inputs that leak.
4. Make every selection explainable: print which hop or glob selected each app. This is what users of Nx, Pants and testmon rely on.
5. Fail safe on an unknown path and add a check that catches new directories with no rule, so drift does not become silent under-selection.
6. Record what each batch ran, so a late failure at the final full run can be traced to a batch.
7. Do not read "the full run found a failure" as "selection missed it": most recorded failures here were flakes or main-origin.

## Sources

- https://github.com/nrwl/nx/issues/9426
- https://github.com/nrwl/nx/pull/22573
- https://nx.dev/docs/features/ci-features/affected
- https://nx.dev/docs/kb/reduce-waste
- https://chat.pantsbuild.org/t/16090968/hello-wave-recently-i-ve-noticed-that-a-target-generator-is-
- https://chat.pantsbuild.org/t/10504237/i-m-seeing-some-interesting-behavior-if-i-change-a-yaml-file
- https://chat.pantsbuild.org/t/9728293/hi-team-a-hopefully-quick-question-on-changed-dependees-supp
- https://pypi.org/project/pytest-testmon · https://pypi.org/project/pytest-testmon/0.9.7 · https://redirect.github.com/tarpas/pytest-testmon/issues · https://dev.co/testing/open-source/pytest-testmon
- https://pypi.org/project/pytest-impacted/0.22.0/
- https://lightrun.com/answers/facebook-jest-bug-findrelatedtests-misses-tests-especially-in-multi-project-setups
- https://stncp.dns-dynamic.net/stryker-mutator/stryker-js/issues/4773
- https://gitlab.com/gitlab-org/gitlab/-/issues/118499
- https://socket.dev/npm/package/jest-changed-files/overview/24.9.0
- https://groups.google.com/g/django-updates/c/d5CIxXaa0EU
- https://forum.djangoproject.com/t/tests-signals-fixtures-mixing-of-levels-between-apps-and-project/4239
- https://oneuptime.com/blog/post/2026-07-28-monorepo-only-affected-builds/view

status: ok
