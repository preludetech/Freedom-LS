# Research: what counts as a junk or brittle test here, and how much of the suite is one

Scope: non-playwright tests under `freedom_ls/*/tests/` (the `tests/playwright/` dirs are covered by another unit). All counts are `Grep` (ripgrep) line or file counts over `freedom_ls/**/tests/**/*.py` unless stated. They are indicative, not exact test counts. A "hit" is a matching line, and one test can produce several hits.

## 0. Headline finding

The suite is **large and verbose but mostly disciplined**. The project's own `testing` skills already forbid most smells, and the code mostly follows them:

- There are **0** `xfail`, **0** `@pytest.mark.skip` (unconditional), and **0** "flaky" or "brittle" comments in test code.
- There are **0** `assertContains` calls. Markup is asserted with plain `assert "..." in html`.
- The `__str__` tests are few and behavioural.

The cleanup opportunity is therefore **not a pile of obviously dead tests**. It is concentrated in a few identifiable families:

1. Markup, Tailwind-class and copy assertions on rendered output.
2. Per-app admin test files.
3. Near-duplicate parallel test files (the three tracking-pixel apps, the per-name icon tests).
4. Tests that read source files (CSS) and assert on their text.
5. Config-echo assertions.

Of the ~6742 collected tests, 226 are `playwright`. Roughly 6500 are server-side tests, and these are the ones this unit covers.

## 1. What the project already says it wants (rubric baseline)

Sources read: `claude_plugins/fls-dev/skills/testing/SKILL.md` (FLS overlay) and `claude_plugins/django-stack/skills/testing/SKILL.md` (generic).

- **Behaviour, not implementation.** No call counts on internal helpers, no private attributes, no exact SQL.
- **No negative-existence asserts for names the code never produced** (`assert not hasattr(x, "squirrels")`).
- **No tautologies.** The expected value must not be re-derived with the same logic as the code under test.
- **Mock only at system boundaries.** More than 2 mocks in a test is a smell. Do not mock owned code or the ORM.
- **"Don't assert on styling (CSS classes, colours, font sizes) — only on functionality."**
- **"Don't assert hardcoded config values."** This includes feeding live config through the code and asserting a hardcoded derived result. Pin the config with `override_settings` or supply explicit input instead.
- **"Delete flaky tests."**
- **Linear tests.** No `if`, `for` or `try` in test bodies. One behaviour per test.
- **Tests must pass in any order** (`pytest-randomly`). No outbound sockets (`pytest-socket`). Use `time-machine` for time.
- **"Test has no assertion (or only `status_code == 200`)"** is a named anti-pattern.
- **`fls_internal`: "Reach for it last."** De-brand the test first. Mark it only when it genuinely reads repo, brand or demo state.
- **Coverage "is a signal, not a goal".** The gate is `--cov-fail-under=73` in `pyproject.toml` `addopts`. `[tool.coverage.run] omit` already excludes migrations, tests, conftests and `*/qa_helpers/*`.
- `pyproject.toml` also sets `timeout = 300`, `-m 'not ci_only and not weasyprint'`, and `--strict-markers`.

Note the existing tension: the skill bans CSS-class asserts and loops in test bodies, but the codebase has many of both (see section 3).

## 2. Rubric (mechanical criteria)

Each criterion is something a reviewer can apply by reading one test plus grep. The tag is the verdict if the test fails the criterion.

| # | Criterion | Verdict if it fails | Grounding |
|---|---|---|---|
| R1 | Asserts a Tailwind or CSS utility class, exact `class=` string, inline style or DOM structure that is not itself the contract (an `aria-*`, `role`, `href`, `hx-*` or data attribute is a contract; `bg-primary/5` is not) | brittle (change-detector) | Google Testing Blog, change-detector tests; skill "Don't assert on styling" |
| R2 | Asserts a long literal of user-facing copy (sentence of 15+ chars) with `in body`, where the text is not the feature (e.g. an email subject or legal text). Assert on a stable hook (URL, `data-*`, `id`, named context var) instead. | brittle | xUnit Patterns "Fragile Test" (data and interface sensitivity) |
| R3 | Tests Django, a third-party library or Python rather than project code (e.g. a `ModelAdmin` option is registered, `Meta.ordering` equals X, an icon-set dict has a key). Framework behaviour is not ours to guard. | junk | Skill ("tests the config file, not behaviour"); testing-library / Kent C. Dodds "implementation details" |
| R4 | Trivial `__str__`, getter, constant or `verbose_name` test that restates the one-line implementation | junk (tautology) | Skill "tautological tests"; Test Smells catalogue "Redundant Assertion" |
| R5 | Asserts a hardcoded value taken from live config (`settings.X == ...`, CSS token or class exists in a shipped `.css` file) with no controlled input | brittle | Skill: the live-config-through-code variant |
| R6 | Everything the unit does is mocked, so only the mock is exercised. This includes more than 2 `patch`es, or `assert_called*` on an owned collaborator. | junk or brittle | Fowler "Mocks Aren't Stubs"; skill "Mock only at system boundaries" |
| R7 | Duplicates another test's observable behaviour at another layer (a view test and a template test of the same page, or the same parametrised matrix copied per app) | duplicate (keep the lowest layer that proves it) | Google "Software Engineering at Google" test-size and pyramid guidance |
| R8 | Per-instance copy-paste of a generic check (one file per icon name, per tracking provider, per `ModelAdmin`) where one parametrised or shared test covers all | duplicate | Test Smells catalogue "Duplicate Test" / "Eager test" |
| R9 | Order, wall-clock or sleep dependent (`time.sleep`, un-frozen `now()`, reliance on DB row order without `order_by`) | brittle | Beck "Test Desiderata": isolated, deterministic |
| R10 | Only asserts `status_code == 200` or "renders without error" | junk (weak) | Skill anti-pattern table |
| R11 | Loop or conditional in the test body that hides which case failed (`for x in ...: assert`) | brittle (diagnosis) | Skill "Test hygiene"; Test Smells "Conditional Test Logic" |
| R12 | Passes only under FLS's own theme, demo content or branding but lacks the `fls_internal` marker (the inverse: carries the marker but could be de-branded) | mis-marked | FLS overlay marker taxonomy |
| R13 | Tests dev tooling (`qa_helpers`) that is a convenience. This is **keep** only if the command is destructive or its mis-scoping silently harms data. | junk unless R13-exception | User brief ("we shouldn't need to run tests for qa helpers only real code"); `pyproject.toml` coverage `omit` comment |

Keep criteria (floor), also mechanical:

- **K1.** It asserts a security or isolation property: site isolation, organisation isolation, role or permission denial, or an object-level guardian check.
- **K2.** It asserts a state transition or computation: scoring, progress, completion, deadlines, signals, webhook payloads, destructive commands.
- **K3.** It is the only test of an error branch (validation refusal, `PermissionDenied`, 404 on cross-site).
- **K4.** It encodes a regression with a stated reason in a docstring.

Reference URLs:

- Google Testing Blog, "Test Behavior, Not Implementation": https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html
- Google Testing Blog, "Change-Detector Tests Considered Harmful": https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html
- Google Testing Blog, "Test Behaviors, Not Methods": https://testing.googleblog.com/2014/04/testing-on-toilet-test-behaviors-not.html
- Meszaros, *xUnit Test Patterns*, Fragile Test and Conditional Test Logic: http://xunitpatterns.com/Fragile%20Test.html
- Open Catalog of Test Smells: https://test-smell-catalog.readthedocs.io/
- Fowler, "Mocks Aren't Stubs": https://martinfowler.com/articles/mocksArentStubs.html
- Fowler, "Unit Test" (sociable vs solitary): https://martinfowler.com/bliki/UnitTest.html
- Beck, Test Desiderata: https://testdesiderata.com/
- Django test tools (`assertInHTML` and `assertContains` exist for HTML-equivalence assertions): https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertInHTML

I did not retrieve the full text of the xunitpatterns, Fowler, Beck and Django pages. The search tool returned only titles and snippets for the Google posts and the Test Smell Catalogue. Treat the mapping of each criterion to its source as a pointer to read, not a verified quotation.

## 3. Applying the rubric: grep-level evidence

### Overall volume (context)

- Total `def test_` hits in `freedom_ls/**/tests/**/test_*.py` is about 6.5k including playwright dirs.
- `learner_interface/tests/` (non-playwright) has about 654 `def test_` lines in 65 files. The biggest single files are `test_form_runner_views.py` (59), `test_seo_discoverability.py` (34), `test_course_access_integration.py` (33), `test_resume_and_redirect.py` (27) and `test_dashboard_view.py` (22).
- `markdown_rendering/tests/test_markdown_utils.py` has 84 tests. `course_applications/tests/test_views.py` has 77. `course_applications/tests/test_backends.py` has 37.
- Parametrisation is light: 241 `@pytest.mark.parametrize` hits in 117 files, mostly 1 to 3 per file. No matrix explosion was found. `icons/tests` is the exception (see R8).

### R1: Tailwind or CSS utility classes asserted

Method: `assert "<util-class>" in ...` plus `class="..."` patterns. **~36 hits in 21 files.**

- `freedom_ls/educator_interface/tests/test_sidebar.py:127-128`: `"aria-[current]:bg-surface-2" in classes`, `"aria-[current]:text-primary"`.
- `freedom_ls/learner_interface/tests/test_form_runner_views.py:1466-1469`: asserts `"[&_:is(h1,h2,h3,h4,h5,h6)]:text-center"` and the absence of `"[&>p]:text-center"` in content.
- `freedom_ls/panel_framework/tests/test_data_table_panel.py:568`, `:582`: `"md:px-6"` and `"bg-transparent"` in a class attribute.
- `freedom_ls/comms/tests/test_rendering.py:118`: `"bg-primary/5" in row.get("class").split()`.
- `freedom_ls/panel_framework/tests/test_link_cell.py:176`: `"text-on-surface" in classes`.
- `freedom_ls/markdown_rendering/tests/test_markdown_utils.py:339-340`: `"text-left"` and `"text-center" not in result`. This is arguably the contract for table-alignment markdown, so it is a borderline keep.

The skill rule is "don't assert on styling", so these are rubric violations on the project's own terms.

### R1/R5: Tests that read source files and assert on their text

Method: `.read_text()` in `tests/test_*.py`. **32 hits in 15 files.**

`freedom_ls/base/tests/test_theme_tokens.py` is the clearest case (10 hits):

- `test_components_css_declares_new_button_classes`: `for cls in (".btn-secondary", ".btn-ghost", ".btn-accent"): assert cls in css`.
- `test_components_css_declares_new_chip_classes`.
- `test_components_css_declares_alert_family`.
- `test_default_theme_declares_mono_font_token`.

These assert that a shipped CSS file contains a string. They add a R1, R5 and R11 hit in one test. The WCAG-contrast test (`test_muted_text_reaches_4_5_to_1_on_every_page_surface`) is a computed behaviour check and is a keep.

Others:

- `freedom_ls/icons/tests/test_no_font_awesome.py`: 3 reads (a guard against reintroducing a dependency).
- `freedom_ls/panel_framework/tests/test_templates.py:90` `test_no_panel_framework_template_uses_safe`, `:213` `test_forced_colours_rules_live_with_their_components` and `:226` `test_no_panel_component_uses_raw_colours` are repo-lint tests, not behaviour. They are arguably better as pre-commit or lint rules than as pytest tests.
- `freedom_ls/content_engine/tests/test_katex_vendor_assets.py`.

### R2: Exact user-facing copy

Method: `assert "Capital..." (not) in` with a literal of 15+ chars, in `tests/test_*.py`. **At least 30 hits.** The broader pattern, any string of 12+ chars `in` body or content, gives **407 hits in 86 files**. That upper bound includes URLs, ids and `data-*` hooks, so it overstates copy.

Heaviest files:

- `reports/tests/test_partials.py`: 33.
- `base/tests/test_error_pages.py`: 19.
- `listing_visibility`: `learner_interface/tests/test_listing_visibility.py`: 16.
- `reports/tests/test_admin.py`: 15.
- `reports/tests/test_render.py`: 13.
- `educator_interface/tests/test_quick_views.py`: 12.

Concrete copy asserts:

- `freedom_ls/course_applications/tests/test_views.py:612-613`: `"Save and return to your answers"`, `"Back to your answers"`.
- `course_applications/tests/test_views.py:922`: `"Submit application"`. Also `:724` `"Supporting documents"`.
- `freedom_ls/course_applications/tests/test_backends.py:458-459`: `"Finish your application to have it reviewed."`, `"Continue application"`.
- `freedom_ls/course_applications/tests/test_admin.py:233`: `"The course asked for no application form."`.

Some copy is the contract (error pages, legal text, email subjects, an empty-state explaining why). That is a judgement call per test, not a mechanical delete.

### R3 and R4: tests of Django features, `__str__`, `Meta`, `verbose_name`, `get_absolute_url`

- `__str__` tests: about **12 hits**, all behavioural, e.g. asserting a name rather than a UUID.
  - `reports/tests/test_models.py:93,99,106,111` (4 tests).
  - `learner_management/tests/test_cohort_deadline.py:54,70`, `test_learner_deadline.py:48,62` and `test_learner_cohort_deadline_override.py:41,60`. These are `with_content_item` / `without_content_item` pairs across 3 files.
  - `course_recommendations/tests/test_models.py:13`.
  - `referral_tracking/tests/test_models.py:97`.
  - The `__str__` pairs in 3 deadline files are the most junk-like (rubric R4, R8).
- `Meta`, `verbose_name`, `ordering`: **0 hits** in test assertions (only a comment in `panel_framework/tests/stub_panels.py:122`).
- `get_absolute_url`: 9 hits in 3 files (`blog/tests/test_seo_discoverability.py` 5, `content_engine/tests/test_article_model.py` 2, `blog/tests/test_views.py` 2), used as URL builders in SEO and view tests, not tested for their own sake.
- Settings echoes (R5): only `accounts/tests/test_utils.py:123,129,135` (`settings.AXES_LOCKOUT_PARAMETERS == [...]`, `settings.AXES_CLIENT_IP_CALLABLE`, `settings.AXES_LOCKOUT_TEMPLATE == "accounts/lockout.html"`). These are three config-echo tests. They have a comment explaining the security reason, which the skill warns against but which makes them a deliberate guard.
- Admin registration (`site.is_registered`, `_registry`, `list_display ==`): **0 hits**. Admin tests are behavioural.

### Admin test files (R3/R7/R8)

Method: `def test_` count in `tests/test_admin*.py`. **214 tests in 17 files.**

| File | Tests |
|---|---|
| `referral_tracking/tests/test_admin.py` | 31 |
| `form_engine/tests/test_admin.py` | 35 |
| `webhooks/tests/test_admin.py` | 24 |
| `reports/tests/test_admin.py` | 23 |
| `course_applications/tests/test_admin.py` | 21 |
| `organisations/tests/test_admin.py` | 20 |
| `content_engine/tests/test_admin.py` | 17 |

Sampling `form_engine/tests/test_admin.py` shows mostly permission, validation and read-only behaviour:

- `test_form_admins_never_permit_deletion`
- `test_a_viewer_cannot_add_answer_data`
- `test_staff_without_permission_cannot_reach_answer_data`

These are K1 keeps. A smaller set are render checks that overlap, e.g. `test_it_renders_with_rows_present`, `test_the_add_page_offers_user_and_form`, `test_the_change_page_is_read_only`. The `test_it_renders_with_rows_present` test is an R10 candidate.

### R6: mocks

Method: `mock.patch|patch(|monkeypatch.setattr|MagicMock|Mock(`. **295 hits in 61 files.** `assert_called|call_count|.call_args`: **95 hits in 20 files.**

Concentrated in boundary-owning code, which the skill allows:

- `deployment/tests/test_housekeeping.py`: 44 patch hits, 11 call asserts.
- `deployment/tests/test_worker.py`: 30 and 15.
- `webhooks/tests/test_delivery.py`: 26 and 14.
- `webhooks/tests/test_send_test_views.py`: 10.
- `webhooks/tests/test_events.py`: 9 and 10.
- `comms/tests/test_delivery.py`: 6 call asserts.

`deployment/tests/test_worker.py` also holds all of the real `time.sleep` uses (lines 161, 248, 250), which are short (0.05 to 0.1 s) with a comment at `:180` about avoiding a 30 s sleep.

`learner_interface/tests/` is not mock-heavy. `test_anonymous_home_page.py` has 1 and `test_resume_and_redirect.py` has 16 `patch`-like hits, mostly settings.

Whether `deployment` and `webhooks` mock owned internals or only the network and clock needs reading per test. Grep cannot tell. These are the R6 candidates, not confirmed junk.

### R7: duplicates across layers

Method: file-name inspection and read of `panel_framework/tests/`.

- `panel_framework/tests/` has per-component test files (`test_component_card`, `_stat_tile`, `_page_header`, `_avatar_chip`, `_progress_bar`, `_status_badge`, `_toolbar`, `_definition_list`, `_attention_list`, `_empty_state`). Each asserts markup of a Cotton component. Several also appear again in `test_templates.py` and `test_data_table_panel.py` (class asserts on the table toolbar), and in `test_htmx_navigation.py` (31 markup-assert hits).
- `learner_interface/tests/` has many per-feature view test files where several test the same pages: `test_course_detail_public`, `test_course_detail_visibility`, `test_course_detail_category_chip`, `test_course_detail_toc_in_development`, `test_course_price_placement`, `test_course_price_component`. A price component test and a price-placement test both render the course detail page. The separate files each pay their own fixture setup.
- Learner-page SEO is tested twice: `learner_interface/tests/test_seo_discoverability.py` (34 tests, 12 content-assert hits) and `blog/tests/test_seo_discoverability.py`.
- `educator_interface/tests/test_organisation_isolation.py` (27 content-assert hits) and `test_permission_matrix.py`, `test_denied_experience.py` overlap in intent. Keep the isolation tests (K1).

I have not proven pairwise duplication test by test. These are structural indicators.

### R8: near-identical generated test files

- **Tracking pixels.** `tiktok_pixel/tests/test_context_processors.py` (20 tests), `meta_pixel/tests/test_context_processors.py` (21) and `google_tag/tests/test_context_processors.py` have the same shape. Each also has parallel `test_checks.py`, `test_events.py`, `test_config.py` and `test_*_tags.py`: `tiktok_pixel` 5/4/1/2, `meta_pixel` 5/4/1/2. This is a candidate for a shared parametrised contract test.
- **Icons.** `icons/tests/test_{cohort,course,edit,check_all}_semantic_name.py` plus `test_panel_component_semantic_names.py` repeat the same three tests per name: "is a semantic name", "is mapped in every set" (parametrised) and "renders in every set". `test_cohort_semantic_name.py` is 30 lines for 1 + 2N (N = icon sets) test cases. The mapping check could be a single test that loops the registry.
- **Deadlines.** `test_cohort_deadline.py`, `test_learner_deadline.py` and `test_learner_cohort_deadline_override.py` have mirrored `__str__` pairs (see above).
- **`contrib/conformance`** is a deliberate probe design (named exception in the FLS skill). Keep.

### R9: order and time

- `time.sleep`: 3 hits, all in `deployment/tests/test_worker.py`. No `sleep` elsewhere in non-playwright tests.
- `freeze_time`/`freezegun`: **0**. Time-shaped tests use `time_machine` (**63 hits in 11 files**, heaviest `reports/tests/test_gather.py` 11, `reports/tests/test_at_risk_rules.py` 9, `reports/tests/test_gather_indexes.py` 9, `role_based_permissions/tests/test_utils.py` 7). That is consistent with the skill, with no misuse found at grep depth.
- `pytest.mark.timeout`: **0**. A global `timeout = 300` is set in `pyproject.toml`.
- Query-count assertions (`django_assert_num_queries` and kin): **95 hits in 23 files**, e.g. `reports/tests/test_gather_indexes.py` (20), `course_applications/tests/test_backends.py` (14), `learner_interface/tests/test_dashboard_cost.py` (8). These pin an exact query number. They are a deliberate N+1 guard, but an exact count is brittle against unrelated ORM changes. Review `==` against `<=`.

### R10: weak assertions

Not measurable by grep alone. `assert response.status_code == 200` as the sole assertion needs per-test reading. The `learner_interface` and `educator_interface` suites mostly add content asserts after the status check.

### R11: loops in test bodies

Method: `^\s+for .* in .*:$` in `tests/test_*.py`. **172 hits in 84 files.** These include comprehensions' multi-line forms and non-assert loops (setup), so many are fixture-building. Assert-in-loop examples:

- `base/tests/test_theme_tokens.py:112,118,137` (`for cls in (...): assert cls in css`).
- `qa_helpers/tests/test_qa_create_organisations.py:43` loops organisations and calls `reverse` with no `assert` (the assertion is implicit in `NoReverseMatch`).
- Heaviest loop files: `reports/tests/test_gather.py` (11), `reports/tests/test_pdf_integration.py` (9), `icons/tests/test_mappings.py` (5), `icons/tests/test_no_font_awesome.py` (5), `learner_interface/tests/test_course_part_children.py` (5), `panel_framework/tests/test_data_table_panel.py` (7).

The skill prohibits loops in test bodies, but the real prevalence is unclear because setup loops dominate the raw count.

### R12: `fls_internal`

Method: `fls_internal` line hits in `tests/**/*.py`: **20 hits in 14 files**:

- `content_engine/tests/test_demo_content_{application_form,picture_titles,form_link,articles,prices,survey_form}.py`.
- `learner_interface/tests/test_demo_content_course_card.py`.
- `blog/tests/test_demo_articles.py`.
- `contrib/conformance/tests/` (3 files).
- `qa_helpers/tests/` (3 files).

Only about 1 in 25 test files carries the marker. The `contrib/conformance/tests` files and the `qa_helpers` tests are marked internal. The `qa_helpers` ones are in scope for R13.

### R13: `qa_helpers`

`freedom_ls/qa_helpers/tests/`: **19 tests in 5 files**.

- `test_qa_create_application_review_accounts.py` (2)
- `test_qa_create_report_cohort.py` (3)
- `test_qa_create_organisations.py` (4)
- `test_qa_create_report_fixtures.py` (6)
- `test_qa_create_report_brand_organisations.py` (4)

`pyproject.toml` `[tool.coverage.run] omit` already excludes `*/qa_helpers/*` and says a few commands "do carry tests -- the destructive ones, where a mis-scoped delete silently empties somebody's dataset". So the project has already decided qa_helpers tests are the exception, not the rule.

`test_qa_create_organisations.py` tests slug derivation and reversibility of the educator URL for a seeded organisation. That is tooling correctness, not shipped behaviour. Whether each file is a destructive command was not checked in detail here.

`dev_tools/tests/test_danger_clear_all_course_progress.py` (2 patch hits) and `dev_tools/tests/test_create_demo_data.py` are the nearby destructive-command guards (K2).

## 4. Brittleness evidence from history and code signals

Searched `freedom_ls/**/tests/**/*.py` for `xfail|pytest.mark.skip|skipif|flaky|time.sleep|pytest.mark.timeout|brittle|@claude|TODO|depends on`.

| Signal | Count | Notes |
|---|---|---|
| `xfail` | 0 | |
| unconditional `skip` | 0 | |
| `skipif` | 4 | `reports/tests/conftest.py:26` (`requires_tailwind_bundle`), `content_engine/tests/test_article_model.py:41`, `content_engine/tests/test_demo_content_articles.py:66` (blog not installed), `learner_interface/tests/test_demo_content_course_card.py:22`. All are environment guards, not suppressed failures. |
| `flaky`, `brittle`, retry decorators | 0 | |
| `@claude` or `TODO` | 0 | |
| `time.sleep` | 3 | `deployment/tests/test_worker.py:161,248,250`, short, justified in a comment at `:180` |
| `pytest.mark.timeout` | 0 | global `timeout = 300` only |
| `freeze_time` | 0 | `time_machine` used instead (63 hits) |

"depends on" comment hits were all explanatory prose. For example, `reports/tests/test_pdf_integration.py:9` says "assertion here depends on exact whitespace or word order beyond what is" in a way that signals awareness of brittleness (the file sets a policy against it).

I could not see git history or CI flake rates, so brittleness here means "likely to break on unrelated change". It does not mean "has been seen to flake". The only direct brittleness signals in code are the real-clock `time.sleep` calls and exact query-count asserts. The skills document that the full suite "can take more than 10 minutes".

Tests that read like regression-from-incident: many docstrings explain a failure mode (for example `qa_helpers/tests/test_qa_create_organisations.py`: "An organisation whose slug the educator interface cannot route to is worse than one that was never seeded"). These tests are valuable (K4) and should not be treated as junk because they are narrow.

## 5. What is clearly worth keeping (the floor)

Observed behaviour-test families that meet K1 to K4:

- **Site and organisation isolation.** `educator_interface/tests/test_organisation_isolation.py`, `test_organisation_switcher.py`, `test_permission_matrix.py`, `test_denied_experience.py`. `learner_interface/tests/test_read_path_record_scoping.py` (21) and `test_player_progress_scoping.py` (21). `site_aware_models/tests/` (forms, admin filters, `test_get_cached_site`).
- **Role and permission.** `role_based_permissions/tests/` (`test_models`, `test_roles`, `test_registry`, `test_migrations`), `panel_framework/tests/test_check_access.py`, `form_engine/tests/test_admin.py` permission tests, `learner_interface/tests/test_course_access_integration.py` (33) and `course_access/tests/test_backends.py`.
- **Scoring and progress.** `form_engine/tests/test_scoring.py`, `test_form_progress_score_quiz.py`, `learner_progress/tests/` (`test_course_progress_*`, `test_recalculate_progress_percentages`, `test_completion_signal`, `test_registration_signals`), `learner_interface/tests/test_outline_agrees_with_progress.py`, `test_course_finish_requires_passing.py`, `test_sequential_item_unlock.py`.
- **Signals and webhooks.** `webhooks/tests/test_delivery.py`, `test_events.py`, `test_integration.py`, `*_webhook_events.py` in `accounts`, `learner_management` and `learner_interface`.
- **Deadlines and time.** `learner_management/tests/test_deadline_utils.py`, `reports/tests/test_at_risk_rules.py`.
- **Destructive management commands.** `dev_tools/tests/test_danger_clear_all_course_progress.py`, `accounts/tests/test_setup_initial_prod_data.py`, `referral_tracking/tests/test_prune_referral_code_hits.py`, `deployment/tests/test_housekeeping.py`.
- **Security-sensitive.** `accounts/tests/test_login_rate_limit.py`, `base/tests/test_csv_safety.py`, `icons/tests/test_renderer.py` SVG sanitiser tests (`test_script_tag_rejected`, `test_foreign_object_rejected`, `test_event_handler_rejected`, `test_aria_label_is_escaped`), `mail/tests/`.
- **Framework-contract checks** the project builds on: `contrib/conformance/tests/`, `form_engine/tests/test_import_independence.py` and the `test_organisation/` hooks they back.

## 6. Risks of removal

1. **Coverage gate at 73%** (`--cov-fail-under=73`, branch coverage). Removing view and template tests that are the only exerciser of a template branch or a view branch will drop the number. Removing admin tests (214 tests, 17 files) is the biggest exposure because `ModelAdmin` methods are only reached through them. `qa_helpers` is already excluded from the measure, so deleting its 19 tests costs nothing there. The `reports/tests/test_partials.py`, `test_render.py` and `panel_framework` component tests may be the only thing covering their Cotton templates' branches. I did not run coverage, so the per-file contribution is unmeasured.
2. **Docs as tests.** Many docstrings state the product rule (for example `test_qa_create_organisations.py`, `test_pdf_integration.py`, `test_theme_tokens.py`). Some tests are the only written statement of an invariant, e.g. the AXES rationale in `accounts/tests/test_utils.py:115-135`. A `settings.X == ...` assert there is the only guard that a security setting is not silently dropped. Deleting it under R5 loses a security property unless a system check replaces it. The testing skill itself suggests a system check or smoke test as the replacement for such tests.
3. **Single guard on a security property.** Do not remove assertions in K1 families without confirming a second test covers the same property at a lower layer. Examples: cross-site and cross-organisation 404, a viewer being unable to add or delete answer data, and `test_form_admins_never_permit_deletion`.
4. **Template guards that are really lints.** `panel_framework/tests/test_templates.py::test_no_panel_framework_template_uses_safe` and `icons/tests/test_no_font_awesome.py` enforce repo rules. Removing them without a lint equivalent loses the rule.
5. **Downstream portability.** FLS is distributed to downstream projects. Per the overlay skill, unmarked tests are the portable contract set. Deleting contract-level tests (not markup tests) in portable apps reduces the safety net downstream projects run via `-m "not playwright and not fls_internal ..."`.
6. **Test-organisation hooks.** `test_organisation/` baselines (`mirroring_baseline.txt`, `import_baseline.txt`, `mirroring_exemptions.txt`) list test files. Removing or moving files interacts with the `test-mirroring` and `lint-imports` hooks, so those baselines may need regenerating.
7. **Class-asserting tests that are actually contracts.** `educator_interface/tests/test_sidebar.py`'s `aria-[current]:...` asserts and the markdown table alignment check are the way the code expresses an accessibility or rendering contract. Treat R1 as "ask whether the class is the contract", not as an automatic delete.

## 7. Open questions this unit could not answer

- Exact number of junk tests. Grep gives candidate families, not a verdict per test.
- Which tests are the sole coverage of a branch (needs a coverage run).
- Which mock-heavy tests in `deployment` and `webhooks` mock owned code (needs per-test reading).
- The slowest tests and fixtures by cost (needs `--durations`). The brief's "very very big" may be about run time more than count.

status: ok
