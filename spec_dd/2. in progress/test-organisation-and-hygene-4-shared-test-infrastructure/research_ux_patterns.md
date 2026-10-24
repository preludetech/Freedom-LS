# UX patterns (developer experience) for shared test infrastructure

Scope: UX = developer/AI-agent experience. Sources: the project's own `claude_plugins/fls-dev/skills/testing/SKILL.md` and `idea.md`, plus well-established pytest behaviour (from pytest docs knowledge; no web fetch made, so no URLs were verified this session. Reference: https://docs.pytest.org/en/stable/how-to/fixtures.html, https://docs.pytest.org/en/stable/reference/reference.html#globalvar-collect_ignore_glob).

## 1. Fixture discoverability

- `pytest --fixtures` lists every fixture visible from the cwd/args, grouped by defining file, with the first docstring line. Fixtures with no docstring show only the name. Pattern: give each shared root fixture a one-line docstring saying what it returns and which apps use it. This costs nothing and is what a developer sees first.
- Wildcard re-export (`from freedom_ls.tests.playwright_fixtures import *` in the root conftest):
  - Works for pytest (fixtures register by name), and `--fixtures` shows them under the defining module path.
  - Costs: IDE go-to-definition and "find usages" from a test parameter name do not resolve through `*`; linters flag F403/F401; pytest exposes every public name, including helpers; and the fixtures are registered for every test in the tree, so they appear in `--fixtures` for non-browser apps.
  - Better patterns: (a) `pytest_plugins = ["freedom_ls.tests.playwright_fixtures"]` in the root conftest (the documented, explicit mechanism; the module path is grep-able and `--fixtures` attributes correctly; root-conftest only, since pytest forbids `pytest_plugins` in non-root conftests); or (b) a conftest in the Playwright-only test directories with explicit named imports (`from ... import page_fixture  # noqa: F401`), which scopes visibility and keeps go-to-definition working.
  - Decision lever: if Playwright tests are all marked `playwright` and live in few directories, (b) narrows the surface; if they are spread across many apps, (a) is lower maintenance.
- Fixture placement by breadth of use: a fixture used by one app lives in that app's `tests/conftest.py`; used by a few apps goes in a plain module in `freedom_ls/tests/` imported explicitly or via `pytest_plugins`; the root conftest holds only universally used or autouse ones. This matches the SKILL.md "Fixture placement" and "conftest.py vs. plain module" sections. For `course_with_scored_quiz`/`sit_quiz` (narrow slice), a shared plain module (e.g. `freedom_ls/tests/quiz_fixtures.py`) or the owning app's conftest is more discoverable than the root conftest, which the SKILL.md currently describes as autouse fixtures plus `mock_site_context` (and `course_with_topic`, `staff_client`, `logged_in_client` as justified non-thin wrappers).

## 2. Optional app not installed: what the developer sees

Three behaviours, in order of developer-friendliness:
1. Module-level `pytest.skip(..., allow_module_level=True)`: visible as `SKIPPED [1] ... course_x not installed` in the `-rs` summary. Self-documenting, but the guard must run before any import of the missing app, and it is per-file boilerplate.
2. `collect_ignore_glob` in `tests/conftest.py` (the project's chosen pattern, `app_guards.app_not_installed`): files are silently not collected. No noise, no per-file boilerplate, one guard per app; the trade-off is that nothing tells the developer the tests were skipped. Mitigation: a comment/docstring in the conftest naming the reason, and keep the helper in one place (`freedom_ls/tests/app_guards.py`).
3. Nothing (current state for `course_interest` and `course_recommendations`): collection error (`ModuleNotFoundError`/`ImportError`) aborts or fails the run. Worst experience, especially for downstream projects.
- Pattern that changes decisions: the guard must also cover `factories.py`/conftest imports in the same directory, since a conftest that imports the missing app fails before `collect_ignore_glob` takes effect. Put the `collect_ignore_glob` assignment ahead of any app imports in the new conftest files, and keep those conftests import-free of the optional app (or imports behind the guard). A new conftest that only holds the guard is the minimal DX.
- Use the identical shape to `course_applications/tests/conftest.py` so there is one pattern to grep.

## 3. Factory import-path clarity

- Convention `freedom_ls.<app>.factories` gives one predictable path per app; the developer guesses it without searching. Moving `SiteFactory` to `site_aware_models/factories.py` matches the model's home concept (site-aware base), but `Site` itself is `django.contrib.sites`, so the discoverability risk is that developers look for `SiteFactory` in `accounts` (where it was) or `sites`. Mitigations: docstring on `SiteFactory` naming its home; a line in the SKILL.md/factory_boy resource noting where it lives; the baseline/import-lint (spec 3) will fail loudly on stale `accounts.factories.SiteFactory` imports rather than leave a silent shim.
- Avoid a backward-compat re-export from `accounts.factories`: it keeps old imports working but preserves the rule-2 edge and hides the real location. A clean move with all imports updated in one PR is the clearer end state.
- Avoid dotted-string factory references across apps (SKILL.md says none are used yet); explicit imports stay greppable.

## 4. Making shared locations obvious

- One documented place per kind: `freedom_ls/tests/` for suite-wide shared modules (`site_context.py`, `demo_content_fixtures.py`, `app_guards.py`, `playwright_fixtures.py`); SKILL.md already lists these. Whatever this spec settles for Playwright and quiz fixtures should be added to that list, since the skill is the source of truth for developers and agents.
- Naming: module names say content (`*_fixtures.py`), private helpers underscore-prefixed, public ones documented (see `mail/tests/conftest.py` exception).
- A module docstring at the top of `freedom_ls/conftest.py` and each shared module listing fixtures and their intended consumers makes `pytest --fixtures -v` and file-open both informative. Autouse fixtures deserve the strongest comments, since they act invisibly.
- Deleting the three dead `student_*` `__pycache__` directories is a pure DX win (Glob/grep noise); no tracked content, nothing to document beyond the spec.

## Recommendations that would change decisions

1. Prefer `pytest_plugins` or scoped conftest with named imports over a root `import *`; choose by how many apps use Playwright.
2. Place `course_with_scored_quiz`/`sit_quiz` in a shared plain module (or the narrow users' conftest), not the root conftest.
3. New optional-app conftests: guard first, mirror `course_applications/tests/conftest.py`, no optional-app imports above the guard.
4. Clean move of `SiteFactory`, no re-export shim; update the testing SKILL.md to state its new location.
5. Add one-line docstrings to root and shared fixtures so `pytest --fixtures` is useful.

status: ok
