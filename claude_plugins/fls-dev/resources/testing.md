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

## Markers

The taxonomy (`playwright`, `fls_internal`, `ci_only`, `weasyprint`, `dev_tooling`), what the default run and each CI job select, and the downstream filter string are in the marker section of `Skill(fls-dev:testing)`.

**Reach-for-`fls_internal`-last rule:** every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, ask whether it genuinely depends on FLS's own repo/brand/demo state, or whether it's a contract test wearing a brand-literal disguise.

**Scoping the marker:** prefer a file-level `pytestmark = pytest.mark.fls_internal` only when *every* test in the file is brand/demo-coupled (e.g. a file that only ever reads `demo_content/`). In a mixed file, mark the individual `fls_internal` tests instead.

## Test organisation — FLS specifics

- **Granting permissions:** `Skill(fls-dev:testing)` has the rule, including where `assign_object_role` is the only grant that works.
- **Stub models:** "some object with an assignable role" is the common FLS case for the stub-model technique, in `role_based_permissions`' own tests.
- **Cross-cutting tests:** checks over the shipped `demo_content/` live in a `tests/demo_content/` subpackage and carry `fls_internal`. `test_organisation/mirroring_exemptions.txt` lists every cross-cutting subpackage.

## Test tiers — FLS specifics

`[tool.test_tiers]` in `pyproject.toml` extends the generic lists in `select_tests.py`:

- `none`: `spec_dd/**` holds spec documents no test reads, and `claude_plugins/**/*.jsx` are course-author components that no test executes.
- `escalation`: `config/**` is the settings package every test runs under. `site_aware_models` and `content_base` are the bases every model and content type builds on, so a change there reaches apps the dependency map shows only indirectly.
- `tooling`: this repository hosts the plugins, so `claude_plugins/*/scripts/**` and `claude_plugins/*/templates/**` map to the top-level `tests/` directory where their tests live. `claude_plugins/fls-content/**` maps to its own tests and to `content_engine`'s validator tests, which exercise the content it ships. `claude_plugins/*/**/*.md` maps to `tests/test_test_tiers.py`, the one test that reads the plugin prompts.

## Collection safety — FLS example

Where the generic resource uses `myproject.optional_feature` / `WidgetFactory`, FLS's concrete target is `freedom_ls.course_applications` / `CourseApplicationFactory`, with the conftest at `freedom_ls/course_applications/tests/conftest.py`.

## De-branding techniques

- **Ambient-default config.** Assert the structure, not the value the ambient icon set happens to produce: `re.search(r'viewBox="0 0 \d+ \d+"', result)`, not `viewBox="0 0 24 24"`. Prove it flexes with a second case that stubs a glyph set of a different size.
- **Pinned config stays as-is.** A test whose subject is one specific icon set pins it with `@override_settings(FREEDOM_LS_ICON_SET="lucide")` and may assert that set's literals. A test that stubs one set without pinning `FREEDOM_LS_ICON_SET` gets the pin added.
- **Theme values read through the code.** A test that loads a real theme `.css` and asserts a derived colour or font stack breaks the day someone re-skins the theme. Feed an explicit token dict instead (`resolve_color({"color-primary": "#283593"})`) and cover the shipped themes with a check that resolution succeeds.
- **Independent oracle for shipped assets.** Monkeypatch the image-dimension reader to a fixed size and assert a hand-computed result, never one derived from the shipped logo.
- **Shadowed partial.** A downstream replaces marketing copy wholesale, so assert the partial's template name (`[t.name for t in response.templates]` reports the lookup name, so a shadow still matches) or a documented structural hook. `html.split("Some Heading")` is the same bug: under a shadow it raises `IndexError` rather than failing.
- **Demo content.** A file that reads `demo_content/`, which the packaged distribution excludes, gets `pytestmark = pytest.mark.fls_internal`.
