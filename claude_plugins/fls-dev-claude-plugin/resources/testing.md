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
- HTMX tests: `student_interface:topic_list`, `student_interface:enrol`, `educator_interface:cohort_create`, `student_interface:complete_topic`, with `TopicFactory`, `StudentFactory`, `CourseFactory`, `id="progress-bar"`, and `enrolled` / `course_id` trigger payloads.
- Auth-bypass example: `from freedom_ls.educator_interface.views import cohort_detail`, using `educator_interface:cohort_detail` and `cohort_pk`.
- time-machine example: `CohortFactory(deadline_at=...)` / `cohort.is_overdue()`.

## Marker taxonomy — full FLS version

- **Unmarked (default) = portable** — the downstream-valuable contract/unit set.
- **`playwright`** — browser-dependent; the browser set a downstream excludes. Lives under per-app `tests/e2e/` dirs. See `Skill(fls-dev:playwright-tests)`.
- **`fls_internal`** — only valid under FLS's own settings, theme, branding, or demo content. Reach for it when a test's assertion is inherently tied to FLS's own repo state (e.g. a shipped `demo_content/` file excluded from the packaged distribution) — not merely because the test asserts an FLS-default value it could instead assert as a contract.
- **`ci_only`** — existing slow / real-time tests, excluded from FLS's own default run too.

FLS's own `uv run pytest` runs everything except `ci_only` — it must exercise `fls_internal` and `playwright` tests against FLS's own settings, since that *is* FLS regression testing. A concrete downstream project instead runs:

```bash
uv run pytest -m "not playwright and not fls_internal and not ci_only"
```

to get only the portable contract set.

**Reach-for-`fls_internal`-last rule:** every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, ask whether it genuinely depends on FLS's own repo/brand/demo state, or whether it's a contract test wearing a brand-literal disguise.

**Scoping the marker:** prefer a file-level `pytestmark = pytest.mark.fls_internal` only when *every* test in the file is brand/demo-coupled (e.g. a file that only ever reads `demo_content/`). In a mixed file, mark the individual `fls_internal` tests instead.

## Collection safety — FLS example

Where the generic resource uses `myproject.optional_feature` / `WidgetFactory`, FLS's concrete target is `freedom_ls.course_applications` / `CourseApplicationFactory`, with the conftest at `freedom_ls/course_applications/tests/conftest.py`.

## FLS de-branding worked examples

- **Ambient-default icon viewBox** — `icons/tests/test_renderer.py::test_returns_svg_with_viewbox` hardcoded `viewBox="0 0 24 24"` on the *ambient* default icon set. Rewrite to `assert re.search(r'viewBox="0 0 \d+ \d+"', result)`, proven to flex by a second case that stubs a non-`24 24` glyph set.
- **Pinned icon set — leave as-is.** `icons/tests/test_renderer.py::test_lucide_icon_set` asserts the literal `viewBox="0 0 24 24"` under `@override_settings(FREEDOM_LS_ICON_SET="lucide")`. Where a test stubs one specific icon set (e.g. `icons/tests/test_render.py::test_literal_glyph_in_active_set`) without pinning `FREEDOM_LS_ICON_SET`, pin it with `@override_settings(FREEDOM_LS_ICON_SET="heroicons")`.
- **Logo scaling with an independent oracle** — `accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height` used to hardcode the shipped `512x248` logo; monkeypatch `email_utils.image_dimensions` to `(300,100)` and assert hand-computed `(144, EMAIL_LOGO_DISPLAY_HEIGHT)` from `email_logo_dimensions("images/any.png")`.
- **Demo content → `fls_internal`** — `content_engine/tests/test_demo_content_picture_titles.py` reads a `demo_content/` file excluded from the packaged distribution; the whole file gets `pytestmark = pytest.mark.fls_internal`.
