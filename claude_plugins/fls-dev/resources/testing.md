# Testing — FreedomLS addendum

This addendum extends the generic `ds` testing resource (pulled in by `Skill(ds:testing)`). It adds the FreedomLS site-aware, marker-taxonomy, and de-branding material. Read the `ds` resource first for the generic patterns; this file adds only the FLS delta. See also `Skill(fls-dev:testing)`.

## Setup

FLS default settings module is `config.settings_dev` (where the generic resource says "point pytest at your test settings module").

## `mock_site_context` fixture — pervasive

Any DB test touching a site-aware model must take the `mock_site_context` fixture; never manually set `site`.

```python
@pytest.mark.django_db
def test_creation(mock_site_context):
    instance = MyModelFactory()
    assert instance.site is not None
```

`mock_site_context` handles the site automatically — don't set it by hand.

## FLS module/model examples

Where the generic resource uses `myapp` / `articles` / `subscriptions`, FLS's concrete equivalents include:

- Factory import: `from freedom_ls.accounts.factories import UserFactory`.
- HTMX tests: `learner_interface:initiate_course_access`, `learner_interface:view_course_item` (GET to view, POST with `mark_complete` to complete), `educator_interface:cohort_create`, with `TopicFactory`, `UserCourseRegistrationFactory`, `CourseFactory`, `id="progress-bar"`, and `enrolled` / `course_id` trigger payloads.
- Auth-bypass example: `from freedom_ls.educator_interface.views import cohort_detail`, using `educator_interface:cohort_detail` and `cohort_pk`.
- time-machine example: `CohortFactory(deadline_at=...)` / `cohort.is_overdue()`.

## Marker taxonomy — full FLS version

- **Unmarked (default) = portable** — the downstream-valuable contract/unit set.
- **`playwright`** — browser-dependent; the browser set a downstream excludes. Lives under per-app `tests/playwright/` dirs. See `Skill(fls-dev:playwright-tests)`.
- **`fls_internal`** — only valid under FLS's own settings, theme, branding, or demo content. Reach for it when a test's assertion is inherently tied to FLS's own repo state (e.g. a shipped `demo_content/` file excluded from the packaged distribution) — not merely because the test asserts an FLS-default value it could instead assert as a contract.
- **`ci_only`** — existing slow / real-time tests, excluded from FLS's own default run too.
- **`dev_tooling`** — tests of developer tooling (QA seeders, `danger_` commands, dev scripts, the content validator). Excluded from FLS's own default run too; run with `-m dev_tooling`.
- **`weasyprint`** — tests that invoke WeasyPrint and need Pango/cairo/gdk-pixbuf/HarfBuzz present. Excluded from FLS's own default run too, since those system libraries are not assumed locally.

FLS's own `uv run pytest` runs everything except `ci_only`, `weasyprint` and `dev_tooling` — the three the `addopts` `-m` in `pyproject.toml` deselects. It must exercise `fls_internal` and `playwright` tests against FLS's own settings, since that *is* FLS regression testing. To exercise the WeasyPrint tests, opt back in explicitly with `-m weasyprint` on a machine that has the system libraries. A concrete downstream project runs the portable contract set; the command is in the marker section of `Skill(fls-dev:testing)`.

**Reach-for-`fls_internal`-last rule:** every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, ask whether it genuinely depends on FLS's own repo/brand/demo state, or whether it's a contract test wearing a brand-literal disguise.

**Scoping the marker:** prefer a file-level `pytestmark = pytest.mark.fls_internal` only when *every* test in the file is brand/demo-coupled (e.g. a file that only ever reads `demo_content/`). In a mixed file, mark the individual `fls_internal` tests instead.

## Test organisation — FLS specifics

- **Granting permissions:** the higher-level layer the generic "Granting permissions in tests" rule names is `role_based_permissions`. An app that checks permissions through guardian grants them with `assign_perm` in its tests, never by assigning an FLS role, unless the app depends on `role_based_permissions` at runtime.
- **Stub models:** "some object with an assignable role" is the common FLS case for the stub-model technique, in `role_based_permissions`' own tests.
- **Cross-cutting tests:** checks over the shipped `demo_content/` belong in a `content_engine/tests/demo_content/` subpackage and carry `fls_internal` (see the marker taxonomy below). Today they sit flat in `content_engine/tests/` as `test_demo_content_*.py`, listed in the mirroring baseline.

## Test tiers — FLS specifics

`[tool.test_tiers]` in `pyproject.toml` extends the generic lists in `select_tests.py`:

- `none`: `spec_dd/**` holds spec documents no test reads, and `claude_plugins/**/*.jsx` are course-author components that no test executes.
- `escalation`: `config/**` is the settings package every test runs under. `site_aware_models` and `content_base` are the bases every model and content type builds on, so a change there reaches apps the dependency map shows only indirectly.
- `tooling`: this repository hosts the plugins, so `claude_plugins/*/scripts/**` and `claude_plugins/*/templates/**` map to the top-level `tests/` directory where their tests live. `claude_plugins/fls-content/**` maps to its own tests and to `content_engine`'s validator tests, which exercise the content it ships. `claude_plugins/*/**/*.md` maps to `tests/test_test_tiers.py`, the one test that reads the plugin prompts.

## Collection safety — FLS example

Where the generic resource uses `myproject.optional_feature` / `WidgetFactory`, FLS's concrete target is `freedom_ls.course_applications` / `CourseApplicationFactory`, with the conftest at `freedom_ls/course_applications/tests/conftest.py`.

## FLS de-branding worked examples

- **Ambient-default icon viewBox** — `icons/tests/test_renderer.py::test_returns_svg_with_viewbox` hardcoded `viewBox="0 0 24 24"` on the *ambient* default icon set. Rewrite to `assert re.search(r'viewBox="0 0 \d+ \d+"', result)`, proven to flex by a second case that stubs a non-`24 24` glyph set.
- **Pinned icon set — leave as-is.** `icons/tests/test_renderer.py::test_lucide_icon_set` asserts the literal `viewBox="0 0 24 24"` under `@override_settings(FREEDOM_LS_ICON_SET="lucide")`. Where a test stubs one specific icon set (e.g. `icons/tests/test_render.py::test_literal_glyph_in_active_set`) without pinning `FREEDOM_LS_ICON_SET`, pin it with `@override_settings(FREEDOM_LS_ICON_SET="heroicons")`.
- **Theme values read through the code** — tests that loaded a real theme `.css` and asserted `resolve_color(load_theme("first_class")) == "#283593"` or `email_safe_font_stack(theme["font-sans"]) == "sans-serif"` break the day someone re-skins `first_class`. Feed an explicit token dict instead (`resolve_color({"color-primary": "#283593"})`), and cover the shipped themes with a check that resolution succeeds.
- **Logo scaling with an independent oracle** — `accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height` used to hardcode the shipped `512x248` logo; monkeypatch `email_utils.image_dimensions` to `(300,100)` and assert hand-computed `(144, EMAIL_LOGO_DISPLAY_HEIGHT)` from `email_logo_dimensions("images/any.png")`.
- **Shadowed partial → assert the contract, not the copy** — `learner_interface/tests/test_anonymous_home_page.py` pinned the hero's marketing headline, which a downstream replaces wholesale. Assert the partial's template name (`[t.name for t in response.templates]` reports the lookup name, so a shadow still matches) or a documented structural hook. Note that `html.split("Some Heading")` is the same bug wearing a different hat: under a shadow it raises `IndexError` rather than failing.
- **Demo content → `fls_internal`** — `content_engine/tests/test_demo_content_picture_titles.py` reads a `demo_content/` file excluded from the packaged distribution; the whole file gets `pytestmark = pytest.mark.fls_internal`.
