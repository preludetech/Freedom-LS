# Research: audit of the testing-related skills, agents and commands

Scope: the six skills (`ds` = `claude_plugins/django-stack`, `fls-dev` = `claude_plugins/fls-dev`), the two `fls-dev` agents, `do_qa` / `frontend_check` / `design_check` / `implement_plan`, `CLAUDE.md`, and the `writing-for-agents` standard. The skills are thin; most of the testing guidance lives in the plugin `resources/` files they point at, so those are audited too: `ds` `resources/testing.md` (652 lines), `ds` `resources/playwright-testing.md` (203 lines), `fls-dev` `resources/testing.md` (69 lines), `fls-dev` `resources/playwright-testing.md` (19 lines). No skill has its own `resources/` or `references/` dir; all resources are at plugin level (`${CLAUDE_PLUGIN_ROOT}/resources/`).

All paths are relative to the repo root.

## 0. Ground truth verified from the code

| Fact | Source |
|---|---|
| Settings module `config.settings_dev` | `pyproject.toml:79` |
| `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`, so root `tests/` (dev-tooling and plugin-script tests) and the fls-content validator tests are in the default run | `pyproject.toml:82` |
| `addopts`: `--strict-markers -m 'not ci_only and not weasyprint' --disable-socket --allow-hosts=127.0.0.1,::1 --cov --cov-branch --cov-fail-under=73 --tracing=retain-on-failure --screenshot=only-on-failure`; `timeout = 300` | `pyproject.toml:83,90` |
| Markers registered: `playwright`, `ci_only`, `fls_internal`, `weasyprint` | `pyproject.toml:84-89` |
| `pytest-randomly`, `pytest-socket`, `pytest-xdist`, `time-machine`, `pytest-playwright` all installed; xdist is not in `addopts`; root `conftest.py` caps `-n auto` at 4 workers | `pyproject.toml:52-67`; `conftest.py:15-17` |
| Coverage omits `*/qa_helpers/*`, `*/tests/*`, `*/conftest.py`, migrations; the pyproject comment says a few qa_helpers commands carry tests "where the risk is, not to move this number" | `pyproject.toml:100-116` |
| `[tool.test_organisation]` baselines in `test_organisation/` (`declared_edges.toml`, `import_contracts.toml`, `import_baseline.txt`, `mirroring_baseline.txt`, `mirroring_exemptions.txt`); enforced by `tests/test_check_test_mirroring.py` and, in CI lint, by `claude_plugins/django-stack/scripts/check_test_mirroring.py` | `pyproject.toml:92-98`; `.github/workflows/tests.yml:26-28` |
| Conftest layering: `conftest.py` (re-exports `freedom_ls.conftest` plus the xdist hook), `freedom_ls/conftest.py` (autouse `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides`, `_clear_course_access_backend_cache`; opt-in `site`, `mock_site_context`, `logged_in_client`, `staff_client`, `course_with_topic`, `article_with_image`, `course_with_scored_quiz`, `sit_quiz`, `site_aware_request`, `live_server_site`, plus the plain function `reverse_url`), `tests/conftest.py` (a second `_disable_force_site_name`, duplicating the one in `freedom_ls/conftest.py`), per-app `freedom_ls/<app>/tests/conftest.py` | files as named |
| Playwright fixtures: `freedom_ls/tests/playwright_fixtures.py` (`playwright` session override, autouse `reset_local_storage`, `logged_in_user`, `logged_in_page`, all function-scoped); educator-specific `freedom_ls/educator_interface/tests/playwright/conftest.py` | file docstring lines 26-46 |
| Factories live in `freedom_ls/<app>/factories.py` (15 apps) | glob |
| CI: `unit-tests` job runs `uv run pytest -m "not playwright"` (10 min timeout); `playwright-tests` job runs `uv run pytest -m playwright --no-cov` (15 min timeout, uploads `test-results/` on failure). CI's `-m` replaces the `addopts` `-m`, so `ci_only` and `weasyprint` tests run in the unit job | `.github/workflows/tests.yml:44-145` |
| 52 files carry `@pytest.mark.playwright`; layout tests are often `@VIEWPORTS` parametrised with `@pytest.mark.django_db(transaction=True)`, so each viewport pays live_server plus a table flush | `freedom_ls/learner_interface/tests/playwright/test_course_card_layout.py:14-18,73-78`; `transaction=True` appears in 50 playwright files (171 occurrences) |
| `qa_helpers` has 5 test files (`test_qa_create_*.py`); 3 are `fls_internal` | `freedom_ls/qa_helpers/tests/` |
| Root `tests/` holds ~16 test modules for dev scripts and plugin tooling (`test_dev_db_scripts`, `test_land_on_main`, `test_rebase_lost_change_check`, `test_diagnose`, `test_stale_dbs`, `test_reap_playwright_mcp`, `test_design_screenshots`, `test_entrypoints`, ...) | `tests/` |
| `CLAUDE.md` says nothing about testing conventions beyond `uv run pytest` (line 43) and "Don't build functionality that is not explicitly requested". There is no `docs/**/*test*` file. | `CLAUDE.md`; glob |

## 1. `ds:testing` — `claude_plugins/django-stack/skills/testing/SKILL.md` (258 lines)

### Stale or wrong
- "Playwright tests ... See the `ds:playwright-tests` skill" is fine. But the references to `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` resolve, for the `ds` plugin, to the `ds` resource, never to the `fls-dev` one. `fls-dev:testing` then says "Read `Skill(ds:testing)` first". Two skills, two resource files of the same name, each reached through `${CLAUDE_PLUGIN_ROOT}`. A reader cannot tell which `testing.md` a quoted pointer means.
- "Delete flaky tests. A flaky test is worse than no test." Nothing says how to tell a flaky test from a brittle one, and the repo's layout tests carry `timeout = 300` and retries nowhere, so the rule is unenforced. Wording is fine, but see section 8 on the cleanup needing a definition.
- "Keep tests fast. A unit test taking >100ms is probably hitting real I/O." Not checkable: `--durations` is not in `addopts` and the skill gives no command for it.
- Frontmatter `allowed-tools: Read, Grep, Glob` on a skill whose body instructs running `uv run pytest`, writing tests and running a background Bash. The field only pre-approves tools, so it is harmless, but it misdescribes what the skill does. Same on both playwright-tests skills.

### Missing
- The coverage gate (`--cov-fail-under=73`) and the fact that the gate is the only place coverage is enforced. "Coverage is a signal, not a goal" is stated, but the 73% floor that decides whether deleting tests can fail CI is not.
- That `uv run pytest` runs `tests/` (dev tooling) and `claude_plugins/fls-content` as well as `freedom_ls/` (`testpaths`).
- That coverage omits `*/qa_helpers/*`, and that the suite can still contain tests for it (see 8).
- A definition of "junk test" and "brittle test" beyond the two scattered rules (tautology, absence-of-arbitrary-thing). There is no named list a cleanup can cite, and no instruction that such tests must not be written. The only place the idea is close is the "Anti-pattern cheatsheet", which is a table of symptoms for review, not a "do not write" rule.
- A criterion for when a test should *not* exist: the resource has "What NOT to test" (see below), but the SKILL.md key-rules block, the part read on every invocation, does not.
- When to choose Django test client versus Playwright is a single line ("Playwright is slow; prefer pytest"). No decision table in the skill; the table is only in the playwright resource.
- That tests for tooling under `tests/` and `.claude/` or `claude_plugins/` scripts are a different kind of test with their own location.
- `transaction=True` guidance exists only in the resource ("`transaction=True` is expensive — justify it"). The SKILL.md never mentions it, yet 50 playwright files use it.

### Encourages junk
- Resource "Test Coverage" section: "Cover these for each feature: Happy path / Edge cases ... Relationships (ForeignKey, M2M) / Permissions". "For each feature" with a fixed checklist pushes a test per relationship and per branch. It contradicts the resource's own "Never test trivial model instance creation" and "Trivial CRUD with no logic".
- Resource "Branch coverage": "make sure both sides have a test. Don't write only the happy path." This is a blanket requirement, not conditioned on the branch carrying behaviour.
- SKILL.md "Test validation both ways": "For anything with a validation rule, test that invalid input is rejected". Mandatory, with no limit on framework validators (`max_length`, `required`). The resource's error-test example `test_requires_field` (`pytest.raises(IntegrityError)` on `required_field=None`) tests a Django field constraint, which the resource's own "What NOT to test" forbids.
- Resource "Writing Tests": "Include docstrings" on every test, against SKILL.md "Name tests after behaviour" (the name is the spec). Pushes boilerplate docstrings that restate the name.
- Resource "Key Rules": "Write tests BEFORE implementation (TDD)" as an unconditional rule, alongside "Make one test at a time". Combined with the `qa-bugfixer` flow, this produces one regression test per bug.
- Resource HTMX patterns assert on markup: `assert 'hx-swap-oob="true"' in body`, `assert 'id="like-count"' in body`, `assert "<html" not in response.content.decode()`, `assert b"This field is required" in response.content`. The resource admits "OOB assertions are necessarily string-based". The Django-default message is stable, but the other three couple a test to markup and ids.
- Resource View Tests example asserts `response.context['key'] == expected_data` as the standard shape, i.e. context-key assertions, which are implementation coupled; rendered or observable behaviour would be less so.
- SKILL.md key rules say "No conditionals or loops in test bodies — one behaviour per test" and "No multi-act tests. If you need to call the code twice, that's two tests." Correct for unit tests but it is the opposite of what the cleanup wants for Playwright (flow tests with many acts). The skill does not scope the rule to non-browser tests; `ds:playwright-tests` does not override it explicitly. A reader combining both gets contradictory instructions.

### Overlap and contradiction
- Large duplication inside `ds`: the SKILL.md body (tautology, boundaries, parametrize, hygiene, config-decoupling, HTMX, collection safety, auth) restates the resource, e.g. "Don't assert hardcoded config values" appears at length in SKILL.md (lines 198-204) and in the resource ("Decoupling tests from ambient config"), the four-technique list in both; "Collection safety for optional apps" in both, near word for word; the Red-Flags list and Anti-pattern cheatsheet overlap; "Test order independence" / pytest-randomly in both.
- `ds` resource says markers default portable and names only `playwright`; the `fls-dev` taxonomy adds three more. Consistent, but the base resource documents a "project-specific marker" with no name, which `fls-dev` supplies.
- `ds` resource "Settings: `pyproject.toml`; point pytest at your test settings module" vs the `fls-dev` resource "default settings module is `config.settings_dev`". Consistent, correct against `pyproject.toml:79`.
- `fls-dev:testing` repeats base content in places the overlay claims it does not ("adds only the FreedomLS specifics; it does not repeat the generic body"): the `mock_site_context` example repeats the AAA test shape; the marker taxonomy and the `pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint"` command are repeated in four places (`fls-dev` testing SKILL, `fls-dev` testing resource, `fls-dev` playwright SKILL, `fls-dev` playwright resource).
- Skill vs `CLAUDE.md`: `CLAUDE.md` "Don't build functionality that is not explicitly requested" and "Use skills" are consistent. `CLAUDE.md` has no conflicting testing rule; it also has no testing rule at all, so the skills are the sole source. Note `CLAUDE.md` "Don't add logging unless asked" has no analogue; irrelevant.
- `ds:testing` "Use `@pytest.mark.django_db` for database tests" vs the project's pytest-django config: fine. But `freedom_ls/conftest.py` autouse fixtures (`_isolate_media_root` takes `tmp_path`, `_disable_force_site_name` takes `settings`) are paid by every test, including the many pure-function tests; the skills do not mention the cost.

### Form (`writing-for-agents`)
- Length: 258 lines in SKILL.md plus a 652-line resource. The standard calls this **sprawl** and requires disclosure behind pointers; here the skill is mostly in-file reference (best-practice sections with BAD/GOOD code), not steps. The resource duplicates it (single source of truth violated).
- Description: "Write pytest tests for Django projects. Use when implementing features, fixing bugs, or when the user mentions testing, TDD, or pytest." Three triggers; "implementing features", "fixing bugs" and "testing, TDD, pytest" are partly synonyms (the standard: "one trigger per branch"). Acceptable, but does not front-load a leading word like "junk" or "brittle".
- Negation: the skill is built on prohibitions ("do not add `@pytest.mark.order`", "Don't assert the absence...", "Don't write tautological tests", "Delete flaky tests"). The standard says to prompt the positive and pair prohibitions with a target; most sections do pair (BAD/GOOD), but "Don't" headings dominate.
- No-ops: "Name tests after behaviour", "Arrange / Act / Assert" are defaults the model already follows.
- Environment cache: lines such as "Use `time-machine`", "xdist is opt-in, not baked into `addopts`" duplicate `pyproject.toml`; the standard says to leave config lookups to the environment.
- Run-the-suite paragraph (line 46) appears verbatim in `qa-bugfixer.md` Step 5 and `implement_plan.md` lines 49 and 91: three-plus copies of one rule.

## 2. `ds:playwright-tests` — `claude_plugins/django-stack/skills/playwright-tests/SKILL.md` (44 lines)

### Stale or wrong
- "Reuse a session-scoped login fixture (`storage_state`) so most tests skip the login flow." The FLS code explicitly rejects this: `freedom_ls/tests/playwright_fixtures.py` lines 29-46 say a session-scoped storage_state "does not survive contact with the existing E2E test suite" because `transaction=True` flushes `django_session`. `logged_in_page` logs in through the UI in every test. The base advice is wrong for this repo and nothing in the `fls-dev` overlay overrides it.
- "Test location: `tests/playwright/`". FLS location is `<app>/tests/playwright/` (52 files across apps); root `tests/playwright/` holds only `test_design_screenshots.py`. The `fls-dev` overlay says "per-app `tests/playwright/` dirs" but the base states the opposite and is not marked as superseded.
- "Use `page` and `live_server` fixtures". FLS tests also need `live_server_site` (site domain), `mock_site_context`, `logged_in_page` / `logged_in_user`, and `@pytest.mark.django_db(transaction=True)`. None is mentioned, so a reader writes a test that fails on site lookup or sees no data.
- "Trace and screenshot-on-failure are now captured automatically (`--tracing=retain-on-failure --screenshot=only-on-failure` in `pyproject.toml` `addopts`)". Correct (`pyproject.toml:83`). But the resource `ds` `playwright-testing.md` still says "Trace on failure — **(planned for upcoming phase 2)** ... `playwright_browser_args = ["--trace=retain-on-failure"]`". Skill and resource contradict; the resource is stale.
- "The `expect()` API is **(currently available)**" appears three times (SKILL.md line 34; resource twice). "(currently available)" and "(planned for upcoming phase 2)" are release-staging artefacts with no meaning now; sediment.
- Resource login example uses `reverse('accounts:login')` and `reverse('home')`; real names are `account_login` and `/` (`playwright_fixtures.py:149`). The `fls-dev` resource flags this, but the base example still would not run.
- Resource "Test Organization" tree `tests/playwright/conftest.py` is not the FLS layout.
- Resource "Setup": `uv add --dev playwright`, `playwright install`, `pytest tests/playwright/...` — wrong for FLS (already a dependency; `uv run playwright install --with-deps chromium`; run `uv run pytest -m playwright`).

### Missing
- Flow tests. Nothing says a Playwright test should walk a user flow with shared setup and assert many things along the way. The opposite is encouraged (see below).
- A statement that each Playwright test pays for `live_server`, a browser context and (with `transaction=True`) a full-table flush plus a UI login, and so the number of Playwright tests is a cost to be minimised, not a coverage metric.
- Viewport handling: no guidance on parametrising across viewports. Existing code does `@VIEWPORTS` parametrisation (3 viewports, 3 live-server setups). Whether to loop viewports inside one test or parametrise is undecided.
- That layout and geometry assertions (overflow, widths, bounding boxes) are brittle and what justifies them.
- The two CI jobs: `-m "not playwright"` and `-m playwright --no-cov`, which means Playwright tests contribute nothing to the 73% gate in CI.
- The `ci_only`, `fls_internal`, `weasyprint` markers are mentioned only in `fls-dev`.

### Encourages junk
- "When to Use": "Visual verification needed - Layout, responsive behavior" and "Integration testing across pages". The first invites per-component layout tests (the repo has `test_course_card_layout`, `test_quick_view_layout*`, `test_form_option_layout`, `test_stat_tile_progress_width`, `test_progress_bar_fill`, ...). The skill does not say such a check should usually go inside a flow test.
- Resource Best Practices: "6. **Keep tests independent** - Each test should setup/teardown its own data" and "5. **Test happy paths first**". Together with the key rule "Mark all tests" this yields one small test per behaviour, each with its own setup. The resource never says to combine, which is the cleanup's main Playwright ask.
- Resource HTMX example: `expect(page.locator("#content .new-item")).to_be_visible()` and `expect(page.locator(".item")).to_have_count(5)` use CSS class locators, contradicting its own "Locator priority" (CSS is last resort, "brittle to markup refactors") a few lines earlier. Example code teaches the brittle pattern.
- `get_by_text` is rank 3 in the priority list even though the same list calls it "brittle to copy edits"; no guidance to prefer role/label or `data-testid` where copy may change. Existing tests assert exact copy and use xpath (`test_course_card_layout.py:68-70` uses an xpath ancestor expression with `contains(@class, 'surface')`).
- Resource "Test real user behavior ... Test happy paths first - Core user journeys" is compatible with flows, but "Don't test what pytest can" is the only brake on volume.

### Overlap and contradiction
- Contradicts `fls-dev` playwright_fixtures docstring on login scope (above).
- `ds:testing` says "Playwright is slow; prefer pytest" and `ds:playwright-tests` repeats "if it can be tested with pytest, use pytest instead", the same rule three times (testing SKILL, playwright SKILL, resource "When NOT to Use").
- "Mark every browser test `@pytest.mark.playwright`, without exception" appears twice in the SKILL (Key Rules, line 24 and line 30), once in the resource, and again in `fls-dev:playwright-tests`. Marker is applied per test, per file (52 files); no autouse or `pytestmark` mechanism is mentioned, so the "without exception" rule is manual and each test repeats the decorator.

### Form
- 44 lines, within bounds. The description "Write Playwright tests for user flows and browser interactions. Use when testing HTMX, user journeys, or when the user mentions Playwright, browser testing, or E2E." triggers well and does name "flows".
- "When to Use" bullet list has overlapping branches (flows, journeys, integration across pages are one branch written three times).
- Negations ("avoid testing backend logic") without a positive target.
- Does not mention `Skill(ds:use-playwright)` for the MCP path, so the two Playwright skills can be confused; their descriptions are distinct enough ("Write Playwright tests" vs "Use Playwright MCP to interactively browse") that this is minor.

## 3. `ds:use-playwright` — `claude_plugins/django-stack/skills/use-playwright/SKILL.md` (66 lines)

- Not a pytest skill; included because it shares the name. No test-related staleness except: MCP tool prefix `mcp__plugin_ds_playwright__*` matches `do_qa.md` allowed-tools. Config path `.claude/ds/config.md` exists (verified).
- Missing: no statement that interactive MCP browsing is for exploration only and that anything worth keeping becomes a pytest flow test (or does not become a test). `do_qa.md` Step 7 says "DO NOT write test scripts", but this skill says nothing about it.
- Form: description covers a distinct branch (interactive browsing); "Use when the user asks you to look at a page, check how something looks, click through a flow, fill in forms, or debug UI issues" has four near-synonym triggers. Acceptable.

## 4. `fls-dev:testing` — `claude_plugins/fls-dev/skills/testing/SKILL.md` (159 lines)

### Stale or wrong (verified against code)
- "No FLS app mirrors a subpackage yet: templatetag and management-command tests sit flat in `tests/`" — verified: glob for `tests/{templatetags,management,invariants,demo_content}/**` returns nothing. Correct, but this means `ds` rules ("`<app>/templatetags/content_tags.py` becomes `<app>/tests/templatetags/test_content_tags.py`") are broken in every app and recorded in `mirroring_baseline.txt` (e.g. 8+ `accounts` entries); the cleanup will interact with this baseline (a deleted test file must have its line removed from `test_organisation/mirroring_baseline.txt`, else the check fails as stale).
- "`form_engine/tests/test_import_independence.py`, and `content_engine`'s `test_demo_content_*.py` and `test_katex_vendor_assets.py`, are not yet grouped" — files exist flat; consistent with the resource's "Today they sit flat in `content_engine/tests/` as `test_demo_content_*.py`".
- Marker section: "Unmarked (default) = portable ... `playwright` — browser-dependent". Correct. "FLS's own `uv run pytest` runs everything except `ci_only` and `weasyprint`" — matches `addopts`. "`weasyprint` ... included in CI ... since CI's `-m "not playwright"` overrides" — verified in `tests.yml:88`. However, the same override means `ci_only` runs in CI too; the skill says "ci_only — existing slow / real-time tests (unchanged)" and does not say CI runs them.
- "`freedom_ls/conftest.py` holds the autouse `_disable_force_site_name`, `_isolate_media_root`, `_disable_preview_overrides` and `_clear_course_access_backend_cache`" — verified. Missing from the skill: `tests/conftest.py` also defines an autouse `_disable_force_site_name` (duplicate), and root `conftest.py` star-imports `freedom_ls.conftest`.
- "The thin-wrapper rule: Root-conftest fixtures that are correctly not thin: `course_with_topic` and `staff_client`." The root conftest also holds `article_with_image`, `site_aware_request` (a 1-line wrapper), which the skill does not assess. Minor.
- "Pattern to avoid: `learner_interface/tests/conftest.py`, plain functions for manual import" — verified: the file defines `section_by_slug`, `rendered_section`, `register_user_for_course`, `course_progress_record`, `form_attempt`, `topic_completion`, `learner_with_two_grants`, `collection_item_for` as plain functions. "moving panel_framework's ones there is test-code cleanup for a later spec" — `panel_framework/tests/conftest.py` still defines `StubModel`, `StubChild` etc. The idea touches this directly ("badly organised"); the skill's "later spec" note is a reference the standard and `implement_plan.md` line 52 forbid ("`a later spec`"). That is a violation of the repo's own comment rule inside a skill.
- Skill says "`reports`, `educator_interface`, `learner_management`, `base` and `organisations` check only `has_perm` ... `reports/tests/test_admin.py` already uses `assign_perm`". Not re-verified; treat as unaudited.
- `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` in the overlay points at the `fls-dev` resource; the "FLS de-branding worked examples" section lists specific test names (`icons/tests/test_renderer.py::test_returns_svg_with_viewbox`, `accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height`, `learner_interface/tests/test_anonymous_home_page.py`). These are test-specific past-tense fixes ("used to hardcode"), i.e. a changelog, which goes stale the moment the cleanup deletes or renames those tests. Verify and update after the cleanup.
- Resource line: "Auth-bypass example: `from freedom_ls.educator_interface.views import cohort_detail`" — a pointer to the anti-pattern in FLS terms; unverifiable by this audit, likely stale.

### Missing
- The `fls_internal` count: 15 files, three of them are `qa_helpers` tests. The skill's "Reach for `fls_internal` last" does not mention that tests of dev tooling are ambient-dependent by nature.
- Where qa_helpers tests belong at all (they sit in `freedom_ls/qa_helpers/tests/`, which is mirrored; coverage omits that package).
- The playwright-fixture layer (`freedom_ls/tests/playwright_fixtures.py`: `logged_in_page`, `logged_in_user`, `live_server_site`) is not mentioned in either `fls-dev` testing skill; only the resource points to it in a one-line aside.
- `freedom_ls/tests/` helper package (`app_guards.py`, `images.py`, `storages.py`, `playwright_fixtures.py`) is used by name in the skill (`app_not_installed`) but not described as a package.
- Factories location and which factory to reach for are only in `fls-dev` `resources/factory_boy.md` (not audited here); not linked from the "Granting permissions"/"Fixture placement" sections.
- The root `tests/` directory (dev scripts, plugin tooling) has no convention: not mirrored, not marked, not mentioned.
- That `mock_site_context` is required for site-aware models but is opt-in, so every Playwright test touching data must also request it (the playwright fixtures do, tests that build data before `logged_in_page` must too).

### Encourages junk
- "`mock_site_context` fixture (mandatory for site-aware models)" example: `test_registered_learner_appears_in_cohort_roster` — fine.
- The whole organisation block (mirroring, baselines, dependency direction, stub models, fixture scope, conftest-vs-module) is about *where* tests go and says nothing about *whether* a test should exist. A reader satisfying every rule can still produce a test per method of a model. Nothing here pushes toward junk by itself, but it is 100% structure and 0% value filter.
- "Pattern to follow: `accounts/tests/conftest.py`" etc. encourages new fixtures per app; no counter-rule about deleting unused fixtures.

### Overlap and contradiction
- Triple repetition of marker taxonomy and the `-m` command: this SKILL (lines 126-142), the `fls-dev` resource (lines 31-49), `fls-dev:playwright-tests` (lines 13-21), the `fls-dev` playwright resource (lines 5-13).
- "Collection safety — FLS example" repeats `ds` content with FLS names; the resource repeats it again (`fls-dev` resource "Collection safety — FLS example").
- Resource "mock_site_context fixture — pervasive" repeats the SKILL's "mandatory" section.
- `fls-dev` frontmatter description is a 90-word feature list; the standard says to prune pointer text and to avoid listing identity the body already carries.

### Form
- 159 lines; mostly in-file reference with long quoted code (the `_panel_test_tables` fixture quoted "near-verbatim" is a copy of environment code, i.e. a cache that will go stale). Candidates for disclosure.
- Description: "FreedomLS-specific extension of the ds:testing skill. Adds the FLS instances of ..." Leading words are "FreedomLS-specific extension"; it triggers only "alongside ds:testing". A model reading the description cannot tell the branches (site-aware fixture, markers, organisation) apart. Weak pointer.
- Contains comment-rule violations: "test-code cleanup for a later spec" (line 67).
- Sentence "No FLS factory breaks the direction rule today, and none uses the dotted-string form yet, so this is new guidance rather than a description of existing code" is a status report, not guidance (sediment).

## 5. `fls-dev:playwright-tests` — `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md` (21 lines)

- Stale/wrong: none against the code; the `-m` command and per-app dirs are right. It is the only place that records "all under per-app `tests/playwright/` dirs", which is the correction the `ds` skill needs.
- Missing (the cleanup depends on these): the FLS fixtures (`logged_in_page`, `logged_in_user`, `live_server_site`, `mock_site_context`, `transaction=True` and why), that login is function-scoped on purpose, that Playwright tests are flow tests, that layout checks belong inside flows, that viewport variation should not multiply live-server setups, and the CI split (`-m playwright --no-cov`).
- Encourages junk: "Mark every browser test, without exception" with nothing about minimising the number of browser tests.
- Overlap: the description's only content is "Explains why the playwright marker exists for FLS downstream exclusion", i.e. the skill is a single paragraph that repeats the marker taxonomy from `fls-dev:testing`. Candidate for folding into `fls-dev:testing` or expanding into the real FLS Playwright skill.
- Form: short, fine. Description is narrow (only the marker) so it will not trigger when someone writes a flow test and needs the fixtures. Wrong branch named.

## 6. `fls-dev:use-playwright` — `claude_plugins/fls-dev/skills/use-playwright/SKILL.md` (17 lines)

- Points at `.claude/fls-dev/config.md`; exists. `do_qa.md` also says the config path is `.claude/fls-dev/config.md`. Consistent.
- `ds:use-playwright` says "Read the project's dev-site config file (`.claude/ds/config.md` by default)". Fine.
- Not testing-related beyond name. No findings.

## 7. Agents

### `fls-dev:qa-bugfixer` — `claude_plugins/fls-dev/agents/qa-bugfixer.md`
- Produces tests of the kind to be removed: "Write a **single focused pytest test** that reproduces the bug", plus "When the defect only shows up in a real browser ... write a `@pytest.mark.playwright` test instead. Put it in the app's `tests/playwright/` directory". Every QA bug becomes at least one new test, and every browser-only bug becomes one new Playwright test with its own `live_server` and `transaction=True` flush. `do_qa.md` Step 13 allows up to three fixer spawns per run, so each QA run can add up to three Playwright tests. Nothing tells the agent to extend an existing flow test in that app's `tests/playwright/` instead of adding a new file, nor to check whether an existing test already covers the page.
- The agent also tells the fixer "A design miss's failing test is a Playwright test" (via `do_qa.md` Step 13 condition 2). A design (visual layout) miss becomes a layout assertion, which is the brittle class (geometry, widths).
- "Place it in the correct test file for the affected app." — does not say mirroring rules or the baseline; does not say to avoid creating a new file (a new non-mirrored file would fail the mirroring check, but the check is only a CI lint, not in the agent's step list).
- Step 5 `uv run pytest` runs the entire default suite, Playwright included, plus `--cov-fail-under=73`. With `-x` omitted deliberately. Runtime "can take more than 10 minutes" (also stated in `ds:testing`), while CI's unit job timeout is 10 minutes (`tests.yml:46`) and playwright is 15. The agent cannot tell which part is slow.
- Regression-test naming rule at the end ("Its name and docstring say what used to break ... never a QA bug ID") is good and is the only anti-sediment rule.
- Agent frontmatter `skills:` preloads `ds:testing`, `fls-dev:testing`, `ds:playwright-tests`, `fls-dev:playwright-tests`, so every fixer spawn loads the 258-line skill plus overlays, which includes the contradicting "session-scoped `storage_state`" advice and no flow guidance.
- States "the pre-commit hooks ... do NOT run pytest" — not re-verified here.
- `status: …` footers and return line conform to the worker contract.

### `fls-dev:qa-data-helper` — `claude_plugins/fls-dev/agents/qa-data-helper.md`
- Creates management commands in `qa_helpers/management/commands/` ("preferred for reusable scenarios"); there are ~65 `qa_*` commands. It never says to write tests for them, and pyproject's coverage comment says they are not meant to be tested ("written where the risk is, not to move this number"). Only 5 have tests. The agent frontmatter does not forbid creating tests, and it has no `Write`/`Edit` tool in its `tools:` list (`Glob, Grep, Read, WebFetch, WebSearch, Bash,`), so it creates files through Bash; nothing in it generates tests. Good for the cleanup.
- Description example text refers to "qa-data-factory agent" (4 times) but the agent is `qa-data-helper`. Stale name in the description examples; may cause wrong routing.
- "Discover existing factories first ... look in `tests/`, `factories.py`, `conftest.py` files" — correct directories.
- Note "management commands that accept arguments", "ideally reusable": invites accumulating one-off commands (65 and growing). Related to the idea's "qa helpers" remark; the agent has no instruction to delete spent commands.
- No stale path in the factory pointer: `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` exists in `fls-dev`.

## 8. Commands

### `fls-dev:do_qa` — `claude_plugins/fls-dev/commands/do_qa.md`
- Manual Playwright MCP QA by design ("DO NOT write test scripts — interact with the site directly", Step 7). Does not itself produce pytest tests; the only test-producing path is Step 13 (qa-bugfixer, green-lane bugs). Condition 2 reads "A pytest test can prove the fix. That includes a `@pytest.mark.playwright` browser test (the project's Playwright tests run in the ordinary `uv run pytest` suite)". This is correct for the default run (local `uv run pytest` includes `playwright`), but the parenthetical encodes "Playwright tests are cheap to add"; the cleanup wants the opposite.
- Step 13 "Trust the fixer's pytest run for the regression layer ... do not re-drive what pytest already covers" — this is the only duplication guard: it says the browser re-drive covers only the failing flow.
- Test plan sections (`3. frontend_qa.md` per `frontend_check.md`) are separate from pytest; no step compares planned QA to existing Playwright tests, so the same flows are checked twice (once in pytest Playwright, once by hand).
- Step 2 diff scoping classifies changes by path; unrelated to tests.
- Plugin doc and Step 11 refer to `compress_screenshots.py`; not test related.

### `fls-dev:protected/frontend_check` — `claude_plugins/fls-dev/commands/protected/frontend_check.md`
- Smoke visit of pages at 1920x1080, 375x812, 768x1024 for "HTTP 500 or 404, a visible traceback, no main navigation region or primary content region, an error-level console entry, a navigation that overflows or overlaps". Overlaps pytest Playwright coverage conceptually: `freedom_ls/*/tests/playwright/*layout*` tests (course card, quick view, form option, modal layout, mobile cards, educator mobile tests) already assert layout at mobile/tablet/desktop in the pytest suite. It is not a duplicate of any specific test, but it is a second way of checking overflow/overlap. The helper fires after a rebase only; no step reads the existing Playwright coverage first.
- Step 4 spawns `fls-dev:qa-bugfixer` for each failure (max three), so a rebase smoke failure also becomes a new regression test (same junk risk as above).

### `fls-dev:protected/design_check` — `claude_plugins/fls-dev/commands/protected/design_check.md`
- Takes design screenshots of the running app for comparison. Related pytest code: `tests/test_design_screenshots.py` and `tests/playwright/test_design_screenshots.py` (the tooling that takes those screenshots is itself tested in the default run). The command does not duplicate assertions; it produces images read by a model. It does depend on tooling that has two test files in the default run, which falls under "tests for dev tooling" and is a candidate for the cleanup scope question.

### `sdd:implement_plan` — `claude_plugins/sdd/commands/implement_plan.md`
- Line 49: step 3 "run `uv run pytest` ... all tests must pass". Line 68: "**All tests must pass before moving to the next batch.**" Line 91: final `uv run pytest` via `sdd:sdd-mechanic`. Line 52 forbids test names that mention spec, plan, `§4b`, `batch 3`, etc., and says "If the project has a skill for writing code comments, the batch follows it".
- Nothing here limits how many tests a batch adds, and nothing tells the implementer to prefer extending an existing flow test. The plan format (not audited here) decides the per-batch test list.
- Full-suite run per batch plus final: with Playwright in the default `uv run pytest`, each batch pays all browser tests. The cleanup's speed-up applies directly to this loop, and these lines need the same "run in background, >10 min" caveat they already carry. If the cleanup shortens the suite, three copies of the ">10 minutes" sentence become stale (this SKILL, `qa-bugfixer.md`, `implement_plan.md` x2).

## 9. If the idea goes this way, the following will need updating

1. **qa_helpers / dev-tooling tests leave the default run.** `pyproject.toml` `testpaths` (root `tests/`) and a marker or deletion decision for `freedom_ls/qa_helpers/tests/` (5 files, 3 `fls_internal`). Skills affected: `fls-dev:testing` marker taxonomy (add a statement or a new marker), `ds` resource "Markers", `qa-data-helper.md` (state that its commands carry no tests), the `pyproject.toml` coverage comment, `test_organisation/mirroring_baseline.txt` (any deleted file's line must be removed, or the stale-line check fails), `tests/test_check_test_mirroring.py` (is itself a root `tests/` dev-tooling test).
2. **Flow tests for Playwright.** `ds:playwright-tests` SKILL and resource, `fls-dev:playwright-tests` (add the FLS fixtures, `transaction=True`, shared setup, one flow per page or journey, viewport handling), `qa-bugfixer.md` Step 1 (extend a flow test rather than add a file), `do_qa.md` Step 13 condition 2 parenthetical, `frontend_check.md` Step 4.
3. **Junk/brittle definition.** `ds:testing` SKILL key rules (new short block), `ds` resource "What NOT to test", and removing the contradicting "Cover these for each feature" / "Branch coverage" / "Include docstrings" / `test_requires_field` example. `fls-dev:testing` "FLS de-branding worked examples" must be re-checked against deleted tests.
4. **Conflicts to resolve first**: `ds:playwright-tests` login fixture advice vs `playwright_fixtures.py`; `ds` playwright resource trace "planned for phase 2" vs `addopts`; CSS-class examples vs locator priority; one-behaviour-per-test rule vs flow tests.

## 10. Summary table by file

| File | Lines | Stale/wrong | Encourages junk | Form issues |
|---|---|---|---|---|
| `ds` skills/testing | 258 | allowed-tools, 100ms rule uncheckable, resource pointer ambiguity | validate-both-ways, one-behaviour-per-test unscoped (vs flows) | sprawl, duplicates resource, negation-heavy |
| `ds` resources/testing.md | 652 | `required_field=None` IntegrityError example | "Cover these for each feature", "Branch coverage", docstrings, markup assertions | sprawl, duplicates SKILL |
| `ds` skills/playwright-tests | 44 | storage_state advice, `tests/playwright/` location | per-test independence, layout bullet | overlapping triggers |
| `ds` resources/playwright-testing.md | 203 | phase-2 trace, `accounts:login`/`home`, setup commands, tree | CSS-class examples | "(currently available)" sediment |
| `ds` skills/use-playwright | 66 | none | none | fine |
| `fls-dev` skills/testing | 159 | "later spec" comment; de-branding examples tied to named tests | no value filter | long quoted fixture, weak description |
| `fls-dev` resources/testing.md | 69 | named-test changelog | none | duplicates SKILL |
| `fls-dev` skills/playwright-tests | 21 | none | no brake on volume | description names wrong branch (marker only) |
| `fls-dev` resources/playwright-testing.md | 19 | none | none | fine |
| `fls-dev` skills/use-playwright | 17 | none | none | fine |
| `qa-bugfixer.md` | 217 | none | one new test per bug, Playwright for design misses | preloads 4 skills |
| `qa-data-helper.md` | 95 | "qa-data-factory" name in examples | commands accumulate, 65 and counting | long description examples |
| `do_qa.md` | 660 | none | Step 13 cond. 2 "cheap Playwright" | very long; deliberately a step file |
| `frontend_check.md` | 104 | none | fixer spawn | overlaps layout tests conceptually |
| `design_check.md` | 48 | none | none | fine |
| `implement_plan.md` (test lines) | 49, 52, 68, 91 | none | no cap on tests per batch | three copies of ">10 minutes" rule |

status: ok · reason: audit complete; all named skills, agents, commands, resources and ground-truth config read and cross-checked
