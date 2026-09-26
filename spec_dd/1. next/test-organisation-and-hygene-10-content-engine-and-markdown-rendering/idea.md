# Content engine and markdown rendering test hygiene

Spec 10 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and
hygiene" section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec
depends on and may run beside, the decisions already taken and the assumptions every idea in the
effort makes.

## What

Give `content_engine`'s six grab-bag test files a home that mirrors what they test instead of
nothing, and make `markdown_rendering`'s own test suite stop importing `content_engine` to build
its fixtures.

## Why

`content_engine/tests/` has six files with no matching production module. They guard
`demo_content/` regressions and vendored KaTeX assets, not a `content_engine.py`. They pass today
but look like ordinary unit tests at a glance, which is the rule-1 smell this spec removes.

`markdown_rendering/tests/test_markdown_utils.py` imports `content_engine.models.File` and
`content_engine.templatetags.content_tags` to build its fixtures, even though the runtime
dependency runs the other way. `content_engine` depends on `markdown_rendering`, not the reverse.
A lower-level app's test suite reaching up into its own consumer is the sharpest shape of the
rule-2 violation this effort exists to fix.

## What is settled

- The six rule-1 violations, confirmed still present: `content_engine/tests/test_demo_content_picture_titles.py`,
  `test_demo_content_form_link.py`, `test_demo_content_survey_form.py`,
  `test_demo_content_application_form.py`, `test_demo_content_prices.py`, and
  `test_katex_vendor_assets.py`. Each reads fixture data out of `demo_content/` (via `BASE_DIR`) or
  checks vendored asset files, not a `content_engine` module. They mirror nothing today.
- `content_engine`'s only other test-only cross-app edge is `accounts.factories.SiteFactory`, used
  in `test_course_category_model.py` and `test_content_save_course_categories.py`. Spec 4 moves
  `SiteFactory` to `site_aware_models`, which `content_engine` already depends on at runtime, so
  spec 4 resolves this edge before this spec starts. This spec's own diff carries only the
  import-path fix, not a design decision.
- `markdown_rendering`'s rule-2 violation, confirmed still present: `test_markdown_utils.py`
  imports `freedom_ls.content_engine.models.File` and `freedom_ls.content_engine.templatetags.content_tags`
  (four call sites) to exercise markdown that references files. `content_engine` depends on
  `markdown_rendering` at runtime, never the reverse, so this is a genuine circular edge, not a
  case of an intrinsic shared model (the `accounts`/`FormProgress` exception spec 9 documents does
  not apply here).
- Spec 1 owns the rule-1 mirroring convention, the rule-2 direction rule, and the stub-model
  technique (`panel_framework/tests/conftest.py`) this spec applies to `markdown_rendering`'s
  fixtures.
- Spec 3 owns the baseline files; this spec deletes `content_engine`'s and `markdown_rendering`'s
  lines from the rule-2 baseline once each edge is closed.
- `content_snapshots` (in progress, parent `spec_dd/2. in progress/content_snapshots/`) is a new
  app that reads `content_engine` at runtime; it adds no files under `content_engine/tests/` or
  `markdown_rendering/tests/`, so this spec does not rebase against it.

## Open until the spec

- Where the six grab-bag files move to. A `content_engine/tests/demo_content/` subpackage groups
  the five `test_demo_content_*` files under a name that says what they are; whether
  `test_katex_vendor_assets.py` joins them or gets its own home is for the spec to decide.
- What `markdown_rendering`'s tests build instead of a real `content_engine.File` and
  `content_tags` to exercise file-referencing markdown: a local stub object, following spec 1's
  stub-model technique, or a markdown-rendering-owned fixture that doesn't need a `content_engine`
  model at all.

## Out of scope

- General test quality in either app: weak assertions, redundant tests, missing coverage.
- Any change to `content_engine`'s runtime dependency on `markdown_rendering`. Only
  `markdown_rendering`'s own test suite moves; the production import stands.
- The rest of `content_engine`'s 36 test files carry no further rule-1 or rule-2 violations beyond
  the two named above.

## Resources

- `research_test_layout_audit.md` (stays in the parent `spec_dd/1. next/test-organisation-and-hygene/`):
  §0 for the grab-bag rule-1 violations, §1 for the `markdown_rendering` ↔ `content_engine`
  circular edge, §5 for the per-app rows on `content_engine` and `markdown_rendering`.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`,
  `factory_boy.md`) and `claude_plugins/fls-dev/skills/testing/SKILL.md`: the rule-1/rule-2
  definitions and the stub-model technique this spec applies.
- `freedom_ls/panel_framework/tests/conftest.py`: the reference stub-model implementation.
