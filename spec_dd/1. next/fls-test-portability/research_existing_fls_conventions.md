# Research: current state of FLS test conventions, config, and plugin docs

Scope: map exactly what exists today so synthesis for "Make the FLS test suite
portable to concrete implementations" knows what to add/change, and — per the
user's explicit instruction — **which plugin markdown files (skills/commands/
agents) must be updated** to hold future development to the new conventions.

An `idea.md` already exists in this spec directory
(`spec_dd/1. next/fls-test-portability/idea.md`) laying out the 5-layer
strategy (markers/collection-safety, de-branding, conformance suite, system
checks, upgrade_notes tie-in). This document is the "what currently exists"
counterpart to that idea, not a restatement of it.

---

## 1. Current pytest config

`pyproject.toml` (repo root), `[tool.pytest.ini_options]`:

```
DJANGO_SETTINGS_MODULE = "config.settings_dev"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]
testpaths = ["freedom_ls", "tests", "fls-content-plugin"]
addopts = "--strict-markers -m 'not ci_only' --disable-socket --allow-hosts=127.0.0.1,::1 --cov --cov-branch --cov-report=term-missing --cov-fail-under=73 --tracing=retain-on-failure --screenshot=only-on-failure"
markers = [
    "playwright: marks tests that use playwright for browser automation",
    "ci_only: marks slow tests that should only run in CI (e.g. real-time rate-limit windows)",
]
```

Key observations:

- **`testpaths = ["freedom_ls", "tests", "fls-content-plugin"]`** — FLS's own
  tests live **inside the `freedom_ls` package itself** (`freedom_ls/<app>/tests/`),
  not in a top-level `tests/` dir that could be excluded independently. This is
  the root packaging cause of the portability problem: a downstream that embeds
  `freedom_ls` as an installed package/submodule and points `testpaths` at its
  own `tests/` still has pytest's rootdir-based collection reach into
  `freedom_ls/**/tests/` because those directories match `python_files` and are
  physically present on disk under the (installed/submoduled) package.
- Only **two markers are currently registered**: `playwright` and `ci_only`.
  There is **no `e2e` marker** (idea.md's Layer 1 wants `e2e`/`playwright` as
  aliases) and **no `fls_internal` marker** at all — this is entirely new.
- `--strict-markers` is already on, so any new marker MUST be added to the
  `markers = [...]` list or every test using it errors at collection.
- `-m 'not ci_only'` is the only default exclusion already in `addopts`. Layer
  1's proposed `-m "not fls_internal and not e2e"` recommendation for
  downstream projects would need to compose with (not replace) this — i.e.
  downstream default should likely be `-m "not fls_internal and not e2e and not ci_only"`.
- `--disable-socket --allow-hosts=127.0.0.1,::1` is real and active (not
  aspirational) — relevant to Layer 3's conformance suite, which must not need
  network access.
- `--cov --cov-fail-under=73` — coverage is measured against `source =
  ["freedom_ls"]` (see `[tool.coverage.run]`), scoped to the package. A
  downstream importing `freedom_ls` as a dependency would not want this
  `--cov-fail-under` gate applied to its own run at all (out of scope per
  idea.md, but worth flagging for Layer 1's "recommended downstream selection"
  since `addopts` also carries the coverage flags, not just the marker filter).
- `--tracing=retain-on-failure --screenshot=only-on-failure` (Playwright) are
  **already implemented** in `addopts`, even though
  `fls-claude-plugin/resources/playwright-testing.md` still labels the
  trace-on-failure section "planned for upcoming phase 2" (see §4 — stale doc,
  worth a small drive-by fix but not core to this spec).
- `[tool.ruff.lint.per-file-ignores]` has a rule for `"**/tests/**/*.py"`
  (allows `S101`/assert etc.) — this pattern only matches trees literally named
  `tests`, which is consistent with the current in-package layout; nothing to
  change here unless the packaging model changes.

`[tool.setuptools.packages.find]`:
```
where = ["."]
include = ["freedom_ls*"]
exclude = ["media*", "config*", "static*", "dev_db*", "gitignore*", "node_modules*", "demo_content*"]
```
Confirms: `freedom_ls*` (including every `freedom_ls/**/tests/*`) **is
packaged and shipped**; `demo_content*` is explicitly **excluded** from the
package. This matters directly for de-branding (§5): any FLS test that reads
`demo_content/` files at import- or run-time (e.g.
`test_demo_content_picture_titles.py`, see §5) will find that directory
**absent entirely** in an installed/submoduled downstream, not just
differently branded — a `FileNotFoundError`, not just an assertion mismatch.

### conftest.py locations

- `/conftest.py` (repo root) — just re-exports `freedom_ls.conftest` fixtures:
  `from freedom_ls.conftest import *  # noqa: F403`.
- `/tests/conftest.py` — one autouse fixture, `_disable_force_site_name`.
- `/freedom_ls/conftest.py` — the real fixture file: `_disable_force_site_name`,
  `_clear_course_access_backend_cache` (autouse, clears the
  `get_course_access_backend` `functools.cache` before/after every test — see
  §3), `reverse_url`, `site`, `make_temp_file`, `mock_site_context`,
  `logged_in_client`, `course_with_topic`, `site_aware_request`,
  `live_server_site`. Also re-exports Playwright fixtures from
  `freedom_ls.tests.playwright_fixtures` (`logged_in_page`,
  `reset_local_storage`).
- Additional per-app conftests: `freedom_ls/panel_framework/tests/conftest.py`,
  `freedom_ls/accounts/tests/conftest.py`, `freedom_ls/student_interface/tests/conftest.py`.

None of these conftests currently do anything with markers, `importorskip`, or
optional-app detection — that machinery does not exist yet anywhere in the repo
outside of `idea.md`'s own proposal text.

---

## 2. Existing markers & guards — what exists vs. what's new

Grepped the whole repo (excluding `spec_dd/` prose, which is proposal text, not
code) for `pytest.mark.*`, `importorskip`, `apps.is_installed`, `pytest.skip`,
`collect_ignore`.

**Markers actually used in test code today:**
- `@pytest.mark.playwright` — used across ~20 test files, e.g.
  `freedom_ls/student_interface/tests/e2e/test_form_submit_dialog_focus.py`,
  `test_picture_spotlight.py`, `test_form_submit_navigation_guard.py`,
  `test_form_answered_count.py`, `test_course_toc.py`,
  `test_form_required_validation.py`,
  `freedom_ls/panel_framework/tests/e2e/test_list_view_refresh_htmx.py`,
  `test_data_table_panel_htmx.py`, `freedom_ls/base/tests/e2e/test_toast_dismiss.py`.
  All e2e tests already live under a `tests/e2e/` subdirectory per-app
  (matches the `fls:playwright-tests` skill's stated "Test location:
  `tests/e2e/`" rule) — so a **path-based** `--ignore` is already a viable
  complementary signal to the marker, though the marker is the documented
  source of truth.
- `@pytest.mark.django_db` — pervasive (hundreds of tests); unrelated to this
  spec except that `fls_internal` tests will still often need it too.
- `pytest.mark.allow_hosts(...)` — mentioned in `fls-claude-plugin/skills/testing/SKILL.md`
  as the escape hatch for genuine outbound-network tests; used with
  `pytest-socket`.
- `@pytest.mark.ci_only` — mentioned in `pyproject.toml` markers list; used for
  slow/real-time tests (e.g. rate-limit window tests per
  `freedom_ls/accounts/tests/test_signup_rate_limit.py`).
- **No `@pytest.mark.e2e` anywhere** — only `playwright` exists; idea.md
  proposes `e2e` as an alias/rename target.
- **No `@pytest.mark.fls_internal` anywhere** — entirely new, zero existing
  usages to migrate other than the de-branding candidates listed in §5.

**Collection-safety guards:**
- **Zero occurrences of `pytest.importorskip` or `apps.is_installed` guarding
  test collection anywhere in `freedom_ls/`.** The only real-code hit for
  `apps.is_installed` in the whole repo is unrelated research prose in
  `spec_dd/1. next/student-communication/*.md` (a different, unstarted spec
  proposing the same idiom for a messaging app) — i.e. this idiom has never
  actually been implemented in FLS yet, anywhere.
- The only `pytest.skip` calls in shipped code are in
  `fls-content-plugin/validate/tests/test_validator.py` (skips when `uv` is
  not on `PATH` — an environment-capability skip, unrelated to optional-app
  collection).
- `pytest.skip("blocked on #NNN")` is a **documented convention** (from the
  `testing-best-practice-phase-3-*` series of *done* specs) for bugs
  surfaced-but-not-fixed during a refactor — a completely different use of
  `pytest.skip` than the "optional app absent" guard idea.md proposes. Both
  conventions can coexist; worth being explicit in synthesis that the new
  `importorskip`/`is_installed` guard is a **module-existence** check, not a
  "known bug" skip.
- **Confirmed concrete collection hazard**: `freedom_ls/course_applications/`
  is a real optional app (present in FLS's own `INSTALLED_APPS` at
  `config/settings_base.py:112`, and the default `COURSE_ACCESS_BACKEND` at
  `config/settings_base.py:413-415` points at
  `freedom_ls.course_applications.backends.ApplicationCourseAccessBackend`).
  Test modules that import its factories/models **at module scope with no
  guard**:
  - `freedom_ls/student_interface/tests/test_course_access_integration.py:27`
    — `from freedom_ls.course_applications.factories import CourseApplicationFactory`
    (module-level, no `importorskip`). Docstring at the top of this file even
    says: *"These tests import course_applications factories/models to build
    state but student_interface production code must NOT import
    course_applications — that rule is enforced by the architecture, not
    these tests."* — i.e. the author was already aware of the layering
    asymmetry but did not add a collection guard.
  - `freedom_ls/course_applications/tests/test_backends.py:12`,
    `test_views.py`, `test_queries.py`, `test_models.py`,
    `freedom_ls/course_access/tests/test_visibility_enforcing_backend.py` also
    import `freedom_ls.course_applications.factories` at module scope.
  This is exactly the "5 modules abort collection" failure mode idea.md
  describes for First Class.

**Test hygiene doc convention already in place** (not new, but load-bearing
context): `fls-claude-plugin/skills/testing/SKILL.md` already forbids
`@pytest.mark.order` as a fix for order-dependence, and the
`resources/testing.md` "Test order independence" section documents the "tests
must pass in any order" rule (currently marked "planned for upcoming phase 2"
even though `pytest-randomly` is already an installed dev dependency in
`pyproject.toml` — another small stale-doc note, not core to this spec).

---

## 3. Existing Django system checks & `COURSE_ACCESS_BACKEND`

FLS already has a real, working `django.core.checks` convention — Layer 4 of
idea.md is an **extension of an established pattern**, not a new one:

- `freedom_ls/course_access/checks.py` — `check_course_access_configs`
  (`freedom_ls_course_access.E001`): every `Course.access_config` must validate
  against the *active* backend; wraps DB errors so a fresh/unmigrated checkout
  stays silent.
- `freedom_ls/icons/checks.py` — five checks (`freedom_ls.E001`–`E007`, one
  `W001`) covering unknown icon set, missing Iconify JSON, missing mapping
  values/variants, invalid overrides, and mapping-key completeness. This is
  the most elaborate existing check module and a good model for anything
  Layer 4 adds for icon-set config.
- `freedom_ls/accounts/checks.py` — `check_email_colour_tokens`
  (`freedom_ls_accounts.E002`, tag `Tags.compatibility`) and
  `check_legal_docs_present_when_required` (`freedom_ls_accounts.W001`, tag
  `Tags.security`).
- `freedom_ls/base/checks.py` — `check_htmx_messages_middleware`
  (`freedom_ls_base.E001`/`E002`) — checks middleware ordering, no DB access.

**Registration pattern** (`AppConfig.ready()`): only two apps currently wire
checks in via `ready()` — `freedom_ls/base/apps.py:10` (`from . import checks`)
and `freedom_ls/accounts/apps.py:11` (same). `freedom_ls/course_access/apps.py`
and `freedom_ls/icons/apps.py` both also call `from freedom_ls.<app> import
checks  # noqa: F401` inside `ready()`. All four check modules use the
`@register()` (or `@register(Tags.x)`) decorator directly at module import
time, so importing the module *is* the registration — `ready()`'s only job is
to trigger that import.

**Confirmed gap** (exactly what idea.md's Layer 4 targets):
`freedom_ls/student_interface/apps.py` is a **bare** `AppConfig` — no `ready()`
method, no checks module, nothing. There is **no existing system check** that
`student_interface` (or anything else) requires `settings.COURSE_ACCESS_BACKEND`
to be set, importable, or to resolve to an app that's actually in
`INSTALLED_APPS`. `COURSE_ACCESS_BACKEND` itself:
- Defined with a default in `config/settings_base.py:413-415` (defaults to the
  `course_applications` backend — always "set" *within FLS itself*, so FLS's
  own checks would never catch a downstream that deletes/omits the setting).
- Loaded via `freedom_ls/course_access/loader.py::get_course_access_backend()`
  — `@functools.cache`d, `import_string(settings.COURSE_ACCESS_BACKEND)`,
  wraps in `VisibilityEnforcingBackend`. No existing error handling here for
  "setting missing" (an `AttributeError`/`ImproperlyConfigured` would just
  propagate at first call, not at `manage.py check` time) or "resolves to an
  app not installed" (an `ImportError`, same story).
  This is precisely the runtime-500-not-caught-by-`manage.py check` bug
  idea.md's Layer 4 is designed to convert into a boot-time `Error`.
- The existing `freedom_ls_course_access.E001` check (course_access/checks.py)
  only validates **stored `Course.access_config` values** against whatever
  backend is currently configured — it presupposes the backend itself resolves
  successfully; it does not check that the backend's *setting* is present or
  that the backend's *app* is installed. That's a distinct, currently-unfilled
  check idea.md's Layer 4 explicitly calls out:
  *"student_interface installed but COURSE_ACCESS_BACKEND unset → error"* and
  *"configured COURSE_ACCESS_BACKEND backend's app not in INSTALLED_APPS →
  error"* (idea.md lines 144-145) — neither exists in the codebase today.

---

## 4. Plugin markdown files that encode test/dev conventions

Plugin root: `fls-claude-plugin/`. Files below are the ones that currently
state testing/marker/branding conventions and would need to change (or gain
new rules) once the Layer 1-5 conventions land. Quoted lines are exact.

### `fls-claude-plugin/skills/testing/SKILL.md` — the core testing skill

Currently covers TDD, factories, mocking, tautology avoidance, HTMX test
patterns, and one relevant de-branding rule already in place (line 184):

> "Don't assert hardcoded config values... This includes the subtler variant:
> feeding **live** configuration... through the code under test and asserting
> the **derived** result against a hardcoded expected... Instead, test the
> function with an **explicit input**... and let a system check or smoke test
> guard that the *real* config still resolves without error."

**What needs to change/be added:**
- No mention anywhere of `e2e`/`fls_internal` markers, `pytest.importorskip`,
  or `apps.is_installed` collection-safety guards for optional-app tests. This
  skill is the natural home for a new "## Marker taxonomy" section (default =
  portable, `fls_internal` for brand/demo-coupled FLS-only tests, `e2e` for
  browser tests) and a "## Collection safety for optional apps" section
  documenting the `pytest.importorskip("freedom_ls.course_applications")`
  module-level guard.
- Line 20 ("Test files: `freedom_ls/<app_name>/tests/test_<module>.py`") is
  the packaging convention that *causes* the portability problem (§1) — if
  Layer 1-2 changes anything about where/how tests are collected or what
  markers new tests must carry, this rule needs an accompanying "and mark it
  `fls_internal` if it asserts FLS's own branding/demo content" addendum.
- The existing de-branding rule (line 184, quoted above) is **general
  config-assertion guidance** but doesn't yet reference the specific
  `viewBox`/icon-set/logo-dimension cases as worked examples, nor tell the
  author to reach for the `fls_internal` marker as the fallback when a test
  genuinely can't be de-branded. Layer 2 work should feed worked examples back
  into this skill (and/or `resources/testing.md`) once the icon/email/demo
  tests are fixed.
- No mention of the conformance suite (Layer 3) or system checks (Layer 4) as
  testing concepts at all.

### `fls-claude-plugin/resources/testing.md` — long-form patterns resource

Already has (lines 415-417) the general "never test hardcoded config" /
"derived-from-live-config" rule, word-for-word mirrored from the skill file
above (these two files are kept in sync manually — any Layer 2 addition must
be made in **both**). The "## Future phases" footer (line 435-437) already
points at `spec_dd/` for phase tracking — **this spec should be added there**,
and the phase-tracking sentence updated once this spec lands, per that file's
own convention of listing subsequent phases.
No existing section for marker taxonomy, `importorskip`, conformance suite, or
system checks — all net-new additions needed here to mirror whatever lands in
the SKILL.md.
Also note (stale, minor, drive-by candidate): the "Test order independence"
(line 239) and "No unexpected network sockets" (line 425) sections are both
still labelled **"(planned for upcoming phase 2)"** even though
`pytest-randomly` and `pytest-socket` are already installed dev dependencies
and `--disable-socket` is already live in `pyproject.toml` `addopts` — these
should be flipped to "(currently available)" independent of this spec, but
it's adjacent enough that this spec's author may want to fix it in passing.

### `fls-claude-plugin/skills/playwright-tests/SKILL.md`

Line 24: **"Mark all tests with `@pytest.mark.playwright`"** — this is the
line that needs to change/expand if Layer 1 introduces `e2e` as the primary
name (alias or rename). Whichever direction synthesis picks, this exact line
is the enforcement point for every future Playwright test.
Line 29: `Test location: tests/e2e/` — already matches the existing
`tests/e2e/` subdirectory convention (§2); no change needed there, but this
skill should also state that all `tests/e2e/**` tests are implicitly
`fls_internal`-adjacent for a downstream (they require a live browser +
server, per idea.md's non-goal), reinforcing why Layer 1 wants them cleanly
excludable by marker.

### `fls-claude-plugin/resources/playwright-testing.md`

Lines 47/60: `@pytest.mark.playwright` example decorators — same rename
consideration as the SKILL.md above; every code sample needs to change
together with the actual marker name decision.
No mention of `e2e`, `fls_internal`, or downstream exclusion at all.

### `fls-claude-plugin/skills/icon-usage/SKILL.md`

This skill is about **using** `<c-icon>` in templates/production code — it
does not currently mention testing at all, and correctly doesn't reference
`viewBox` literals (those live only in the icon *rendering* internals, not in
template usage). No change needed here for Layer 2; the de-branding fix
belongs in the icon *tests* (§5) and possibly a testing-skill worked example,
not in this skill.
`fls-claude-plugin/skills/icon-usage/resources/configuring-icons.md` and
`resources/custom-icon-backend.md` were also located but are about
configuring/building icon backends, not testing them — reviewed and out of
scope for this research task's testing-convention mapping.

### `fls-claude-plugin/skills/request-code-review/code-reviewer.md` and `agents/code-reviewer.md`

Neither file currently mentions markers, `uv run pytest`, `importorskip`, or
brand-coupled assertions anywhere. `agents/code-reviewer.md`'s "Important
Issues" checklist (lines 74-88) is the natural place to add a bullet once
Layer 1-2 conventions exist, e.g. "new/changed test asserts an FLS-default
literal (icon viewBox, logo dimensions, demo-content string) without the
`fls_internal` marker" and "new test module imports an optional-app
factory/model at module scope without an `importorskip`/`apps.is_installed`
guard" — both would be concrete, checkable review criteria once the
convention exists. Currently there is nothing here to catch either failure
mode in review.

### Commands that run `uv run pytest` — grep across the whole plugin

```
fls-claude-plugin/hooks/hooks.json:29       uv run ruff check . && uv run mypy . && uv run pytest --tb=short -q   (PreToolUse hook on `git commit`)
fls-claude-plugin/commands/address_pr_review.md:49   uv run pytest -x -q
fls-claude-plugin/commands/commit.md:4      Run `uv run pytest` to make sure all tests pass before committing
fls-claude-plugin/commands/rebase_main.md:29 uv run pytest -x -q
fls-claude-plugin/commands/sdd/implement_plan.md:32,55   uv run pytest  (batch + final verification)
fls-claude-plugin/commands/concrete/update_fls.md:105,122,147,168   uv run pytest  (test gate, 4 separate call sites)
fls-claude-plugin/skills/testing/SKILL.md:30  uv run pytest -n auto  (parallel run, xdist opt-in)
fls-claude-plugin/templates/settings.json:14  "Bash(uv run pytest:*)"  (allowlisted bash pattern)
```

**Critical distinction for synthesis:** `hooks.json`, `commit.md`,
`rebase_main.md`, `address_pr_review.md`, `implement_plan.md` and the
`testing/SKILL.md` all run `uv run pytest` **inside the FLS repo itself**
(depth-0 development on FLS's own worktree) — there, running the *entire*
suite including `fls_internal`/`e2e` tests against FLS's own settings is
exactly correct and should not change.

`fls-claude-plugin/commands/concrete/update_fls.md` is different in kind: it
is the command that runs **inside a concrete downstream project** (the
"submodules/Freedom-LS" flow) and is the literal reproduction of the bug
idea.md opens with. It calls bare `uv run pytest` at four points:
- Step 3h ("Verify"), line 105-106: *"Run the full test suite and confirm
  everything passes: `uv run pytest`"*
- Step 4 (final sync), line 122: *"Run the full test suite one last time:
  `uv run pytest`"*
- Rollback recovery, line 147
- The "Per-spec loop (reference)" pseudocode, line 168: `uv run pytest # test gate`

**This is the single highest-value command file to update.** Once Layer 1
markers exist, each of these four call sites needs to either (a) pass
`-m "not fls_internal and not e2e"` explicitly, or (b) rely on a
downstream-side `pyproject.toml`/`pytest.ini` default that already excludes
those markers (documented, not enforced, by this command) — and, once Layer 3
lands, this is exactly where the command should additionally invoke the
shipped conformance suite as the **positive** signal idea.md's Goal #3 asks
for (today there is no such invocation anywhere in this file).

### `fls-claude-plugin/commands/sdd/update_upgrade_notes.md` and `commands/concrete/update_fls.md` — the `upgrade_notes.md` schema

See §6 below for the full mechanism; flagged here because `update_upgrade_notes.md`'s
flag list (`requires_migrations`, `requires_template_review`,
`requires_settings_change`, `requires_package_upgrade`, `requires_npm_install`,
`requires_tailwind_rebuild`) has **no flag for "this spec added/changed a
Django system check"** or "this spec's hard config requirement is now enforced
by `manage.py check`" — Layer 5 of idea.md wants specs with a hard config
requirement to set `requires_settings_change: true`, which the schema already
supports; it's Layer 4's tie-in (system check now *enforces* the requirement)
that has no corresponding flag today. Whether to add one is a synthesis
decision, not asserted here as a requirement.

### Other plugin files scanned and found *not* to need changes for this spec

- `fls-claude-plugin/skills/htmx/SKILL.md`, `frontend-styling/SKILL.md`,
  `admin-interface/SKILL.md`, `markdown-content/SKILL.md`,
  `multi-tenant/SKILL.md`, `registration/SKILL.md`, `alpine-js/SKILL.md`,
  `git-worktree-setup/SKILL.md`, `template/SKILL.md`,
  `update-claude-project-settings/SKILL.md`,
  `claude-code-authoring/SKILL.md` (+ its `resources/*`) — none mention
  pytest markers, `importorskip`, icon viewBox, or `uv run pytest`.
- `fls-claude-plugin/commands/sdd/*` other than `update_upgrade_notes.md` and
  `implement_plan.md` (i.e. `plan_from_spec.md`, `spec_from_idea.md`,
  `spec_review.md`, `plan_security_review.md`, `plan_structure_review.md`,
  `next.md`, `start.md`, `improve_idea.md`, `finish_worktree.md`,
  `protected/*`) — none reference pytest/markers directly; out of scope.
- `fls-claude-plugin/agents/sdd-worker.md`, `agents/sdd-mechanic.md`,
  `agents/qa-data-helper.md` — generic subagent-authoring guidance, no
  test-marker content.
- `fls-claude-plugin/resources/factory_boy.md` — factory patterns only, no
  marker/branding content beyond what's already noted.

---

## 5. Icon-set / branding assertions in tests today (de-branding surface)

Grepped for `viewBox="0 0 24 24"`, `FREEDOM_LS_ICON_SET`, and related literals
in test files:

**`freedom_ls/icons/tests/test_renderer.py`** (the clearest, most literal case
from idea.md's own table):
```python
class TestRenderIcon:
    def test_returns_svg_with_viewbox(self) -> None:
        result = render_icon("success")
        assert "<svg" in result
        assert 'viewBox="0 0 24 24"' in result      # line 25 — hardcodes heroicons' box
        assert "</svg>" in result
    ...
    @override_settings(FREEDOM_LS_ICON_SET="lucide")
    def test_lucide_icon_set(self) -> None:
        result = render_icon("success")
        assert "<svg" in result
        assert 'viewBox="0 0 24 24"' in result      # line 75 — coincidentally also 24x24, still hardcoded
```
`test_tabler_icon_set` and `test_phosphor_icon_set` (lines 77-85) only assert
`"<svg" in result` — no hardcoded viewBox — these two are **already**
portable-shaped; only `test_returns_svg_with_viewbox` and `test_lucide_icon_set`
hardcode the literal. Since the default icon set is Heroicons
(`freedom_ls/icons/checks.py:29` default `"heroicons"`), any downstream that
sets `FREEDOM_LS_ICON_SET` to something with a different box (e.g. phosphor's
`0 0 256 256`, per idea.md's own table) fails `test_returns_svg_with_viewbox`
even though nothing is broken.

**`freedom_ls/icons/tests/test_no_font_awesome.py:35`** — uses a **regex**,
already de-branded: `r"<svg[^>]*viewBox=\"0 0 \d+ \d+\"[^>]*>.*?</svg>"` — a
good existing example of the "assert structurally, not the exact box" pattern
Layer 2 wants; worth citing as the target style when fixing
`test_renderer.py`.

**`freedom_ls/icons/tests/test_checks.py`** and
**`freedom_ls/student_interface/tests/test_course_icon.py:167`** —
`@override_settings(FREEDOM_LS_ICON_SET=...)` used to test the *checks*
themselves (parametrizing over known-set names) — this is legitimate (testing
the check logic against multiple sets), not a brand-literal assertion; not a
de-branding target.

**`freedom_ls/accounts/tests/test_email_utils.py:416-424`** — the logo
dimension case from idea.md's table:
```python
def test_email_logo_dimensions_scales_to_display_height() -> None:
    """The logo is scaled to the fixed display height with width preserving ratio."""
    ...
    # 512x248 scaled to height 48 -> width round(512*48/248) = 99.
    assert result == (99, EMAIL_LOGO_DISPLAY_HEIGHT)
```
Hardcodes the shipped FLS logo's native `512x248` pixel dimensions inline in
the comment/expected-value derivation. A downstream with a differently-sized
logo asset fails this test even though `email_logo_dimensions()` itself is
correct. This is the "read expected dimensions from the *configured* logo
asset" case idea.md's Layer 2 names explicitly.

**`freedom_ls/content_engine/tests/test_demo_content_picture_titles.py`** —
reads a **shipped demo-content file directly off disk**:
```python
CONTENT_WIDGETS_MEDIA = (
    BASE_DIR / "demo_content" / "functionality_demo_content_widgets" / "2. media" / "content.md"
)
...
def test_demo_media_picture_titles_do_not_duplicate_figure_prefix():
    markdown = CONTENT_WIDGETS_MEDIA.read_text(encoding="utf-8")
    ...
```
This is worse than a branding-literal mismatch: since `demo_content*` is
**excluded from the packaged distribution**
(`[tool.setuptools.packages.find] exclude = [..., "demo_content*"]`, §1), a
downstream that installs `freedom_ls` as a package (rather than working
inside the monorepo) will hit `FileNotFoundError` at test **execution**, not
just an assertion failure — a strong candidate for `fls_internal` regardless
of any de-branding, since it inherently depends on the FLS repo's own
`demo_content/` tree existing on disk. (Note: this file's own module search —
"test_demo_content*" — returned only this single file; idea.md's reference to
`content_engine/tests/test_demo_content_picture_titles.py::*` matches
exactly.)

**`freedom_ls/panel_framework/tests/test_htmx_navigation.py:42-57`** —
`test_non_htmx_returns_full_page` asserts theme/markup-shaped strings:
```python
assert 'id="sidebar-nav"' in content
assert 'aria-label="Breadcrumb"' in content
assert 'aria-current="page"' in content
```
These are structural template-id/ARIA assertions, not brand-literal colors or
icon boxes — arguably more robust than the icon/logo cases, but idea.md lists
this test as failing in First Class due to "different active theme". Whichever
specific markup differs there needs identifying at implementation time; this
research did not find an obviously brand-coupled literal in the visible test
body beyond template structure, so worth a closer look during planning rather
than assuming the whole test needs the `fls_internal` marker.

Summary table of concrete offending files/tests found:

| File | Test(s) | Literal |
|---|---|---|
| `freedom_ls/icons/tests/test_renderer.py` | `test_returns_svg_with_viewbox` (L22-26), `test_lucide_icon_set` (L71-75) | `viewBox="0 0 24 24"` |
| `freedom_ls/accounts/tests/test_email_utils.py` | `test_email_logo_dimensions_scales_to_display_height` (L416-424) | `(99, EMAIL_LOGO_DISPLAY_HEIGHT)` derived from hardcoded `512x248` shipped logo |
| `freedom_ls/content_engine/tests/test_demo_content_picture_titles.py` | `test_demo_media_picture_titles_do_not_duplicate_figure_prefix` (whole file) | reads shipped `demo_content/` path directly (excluded from package) |
| `freedom_ls/panel_framework/tests/test_htmx_navigation.py` | `test_non_htmx_returns_full_page` (L42-57) | theme/markup assertions (needs closer look, not a clear single literal) |

---

## 6. `upgrade_notes.md` mechanism (for Layer 5 tie-in)

Originates from the *done* spec
`spec_dd/3. done/2026-06-26_14:55_concrete-implementation-helpers/` (its
`1. spec.md` lines 256-262 list the flag set), implemented by two plugin
commands:

- **`fls-claude-plugin/commands/sdd/update_upgrade_notes.md`** — runs at depth
  0, at the end of a spec (in FLS's own repo), reads `1. spec.md`, `2. plan.md`,
  and the actual `git diff main..HEAD`, and writes
  `<spec-dir>/upgrade_notes.md` with this exact YAML-frontmatter + prose shape:
  ```yaml
  requires_migrations: false
  requires_template_review: false
  changed_template_paths: []
  requires_settings_change: false
  changed_settings: []
  requires_package_upgrade: false
  changed_packages: []
  requires_npm_install: false
  changed_npm_packages: []
  requires_tailwind_rebuild: false
  ```
  followed by a `## Breaking changes` and `## Manual steps` prose body. Flag
  semantics are documented inline (lines 37-44 of that command file). The
  command finishes by delegating a todo-tick to `fls:sdd-mechanic`.
- **`fls-claude-plugin/commands/concrete/update_fls.md`** — runs inside a
  **downstream** concrete project. For each newly-completed FLS spec (moved
  into `spec_dd/3. done/` upstream), it reads that spec's `upgrade_notes.md`
  frontmatter and drives the integration: pre-flight `migrate --check`, moves
  the submodule pointer, `uv sync`, then conditionally runs
  `makemigrations && migrate` / applies `changed_settings` / reconciles
  `changed_packages` / mirrors `changed_npm_packages` into the downstream's own
  `package.json` + `npm install` / `npm run tailwind_build` / flags stale
  template overrides for `changed_template_paths` — **never auto-merges**
  template drift. Finishes with `makemigrations --check`, `uv run pytest`
  (the exact bare test-suite call flagged as the portability bug in §4), and a
  commit `Update FLS: <spec-name>`. Also documents a full rollback procedure if
  a spec's integration fails mid-way (reset submodule pointer to last good
  commit, `uv sync`, re-verify).
- If a spec has **no** `upgrade_notes.md` (pre-dates the mechanism, or the
  command that authors it wasn't run), `update_fls.md` explicitly falls back
  to "prose inference" from `1. spec.md`/`2. plan.md`/the diff — a soft
  degrade, not a hard failure.

**How Layer 5 ties in, concretely:** any future spec that introduces a hard
config requirement analogous to `COURSE_ACCESS_BACKEND` (i.e. "downstream must
set X or things silently 500 at runtime") should (a) set
`requires_settings_change: true` with the specific key(s) in its
`upgrade_notes.md` (mechanism already supports this — no schema change
needed), and (b) — per idea.md's own text — *"ideally the Layer 4 system check
enforces it"*, i.e. the same spec should ship a `django.core.checks` `Error`
so that even a downstream that misses/ignores the `upgrade_notes.md` prose
still gets a hard `manage.py check` failure. The `home_page` spec that
introduced the `COURSE_ACCESS_BACKEND` requirement (and a second spec that
added the missing `applications/` URL include) are cited in idea.md as the
two specs that shipped **without** upgrade notes at all — confirmed by the
absence of any hit for those spec names carrying `upgrade_notes.md` frontmatter
content in this repo's `spec_dd/3. done/` tree at the time of this research
(the mechanism/command itself was only introduced in the same window as the
first of those two specs, per idea.md's own note).

---

## Footer

status: ok
reason: All six requested areas mapped with concrete paths/line numbers; no blockers encountered.
