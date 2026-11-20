# Research: UX patterns for a host contract (developer experience, and no visible change)

Topic: ux_patterns. Users here are developers integrating the panel framework into a host Django
project, plus end users who must see no change. Sources are cited inline; claims I did not verify
against a primary page are marked "unverified".

## 1. How libraries communicate missing requirements

### System check messages (Django convention)

- Django's `CheckMessage` takes message text, an optional `hint` (a single-line suggested fix, omit
  it when self-evident), an optional `obj` (what the problem is about) and an `id`. Ids follow
  `<app_label>.<Letter><NNN>`, letter = severity (`E`, `W`), as in `myapp.E001`, `sites.E101`.
  Django states this by example, not as a formal rule. Checks register in a file loaded with the
  app, usually via `AppConfig.ready()`; `deploy=True` marks production-only checks.
  https://docs.djangoproject.com/en/6.0/topics/checks/ ,
  https://docs.djangoproject.com/en/6.0/ref/checks/
- **Project fact**: `freedom_ls/panel_framework/checks.py` already uses the id prefix
  `freedom_ls_panel_framework.E001` to `E007` (read from the file). The idea's example id
  `panel_framework.E001` would collide in meaning with those and drop the prefix spec 5 may rename.
  New ids for icon and base-template checks should continue the existing sequence (next free
  number, `E008` onward, checked against the file) under the same prefix, so ids stay stable
  through the move; the label rename is spec 5's, and it renames every id at once.
- The existing messages carry a `hint=` that tells the developer the fix in one sentence (for
  example `Use a field name or a '__' path through relations.`). Follow that: message states what
  is wrong and where; hint states the one action.

### Wording pattern worth copying

A good contract message has four parts, in this order:

1. What is missing, with its exact name: `Icon 'filter' used by panel_framework templates does not render.`
2. Which setting or template it was looked up through: `Looked up as <c-icon name="filter">.`
3. The one-line fix as `hint`: `Add 'filter' to your icon registry, or override cotton/panel-icon.html.`
4. A docs pointer in the hint, as a repo-relative path (the framework's docs ship in the package,
   and spec 6 owns the skill/plugin): `See docs/host_contract.md#icons.`

Rules that follow from Django's design:

- One `Error` per missing item (one per icon name), not one message listing 21 names, so a
  developer sees exactly which are missing and `--fail-level` / `SILENCED_SYSTEM_CHECKS` can filter
  by id. Group only when there are dozens (cap the list and say "and N more").
- Use `Error` for things that make pages break (missing base template, missing icon that raises).
  Use `Warning` for degraded-but-working (an icon that renders blank). A host that cannot yet fix
  it can silence one id in `SILENCED_SYSTEM_CHECKS`; this is the escape hatch to document.
- Keep the check cheap and import-safe: render a name with the template engine, catch the specific
  `TemplateDoesNotExist` / `TemplateSyntaxError` and report it; no silent `except`
  (project rule: be specific, no silent failures).
- Run the checks always (not `deploy=True`): a missing contract item is a development-time
  problem, and `manage.py check` / `runserver` / `migrate` all run them.

### Precedent for "fail loudly, name the setting"

- Django's own admin checks (`admin.E403`, `admin.E404`) tell the developer which
  `TEMPLATES`/context-processor entry is missing. These are the closest analogue to
  "your base template must provide X". (From memory of Django's admin checks; unverified here.)
- The existing `write_active_theme_css.py` raises `CommandError` that names the setting, the
  resolved directory and the missing file, ending in the fix ("Add the file or fix the slug").
  The new Tailwind source command should match that tone.

## 2. Install-in-N-lines guides

Pattern used by reusable Django UI libraries (django-cotton, django-allauth, crispy-forms style
guides; general pattern, I did not re-fetch each): a numbered list of changes the host makes, each
a literal snippet, ending in a "verify" step.

For this contract the guide is short enough to fit on one page:

1. `INSTALLED_APPS` entry (spec 5's label) and the template precedence order note.
2. Base template: include the framework fragments and the fixed ids (copyable block).
3. Script order: host Alpine bundle, framework `alpine-components.js`, then Alpine start.
4. Tailwind: run the source command; add the one `@import` of the generated file to the input CSS
   (the answers fix this as one line).
5. Theme: paste the reference theme block (section 4), then map tokens to the host's brand.
6. Verify: `manage.py check`, then open the reference page.

Good-practice details:

- Number the steps and keep each to one snippet; put "why" in a sentence after, not before.
- Show the failure mode for each skipped step ("unstyled page" for step 4, "panels do not open"
  for step 3), because the product's stated risk is a library that "renders unstyled and silently"
  (idea.md "Why"). A step that has a check says which id it triggers.
- The contract text is this spec's deliverable; the skill/plugin that packages it is spec 6.

## 3. Reference / kitchen-sink page for checking a theme

- Precedent: Storybook's "docs" and "stories" pages, Bootstrap's component examples, and the
  Django admin's own look as a visual check. Pattern: one page that renders every component in every
  state, so a developer applying a theme checks it in one visit. (General pattern; no single source.)
- Project already has this: `reference/component_reference.html`. The spec changes it from
  extending `_base.html` to extending a base named by an `AppSettings` setting, defaulting to the
  framework's minimal shell. Good practices to keep when doing so:
  - The page must render with the default shell alone, so it doubles as the smoke test that the
    contract is complete (the answers decide one shell serves docs, reference page and test tiers).
  - Group by component with a heading and the variants side by side (button variants and sizes,
    chips, notices by tone, empty/loading/error states, a table with rows, compact density,
    expandable row, the required-reason dialog trigger, the `as_of` stamp).
  - Include the closed icon list rendered as a grid labelled by name; that is a visual twin of the
    icon system check, and missing icons are visible at a glance.
  - Include a token swatch strip (each role token as a labelled box), the visual twin of the
    documented token set.
  - Make it reachable only in DEBUG or by a documented URL include; do not ship it enabled in
    production by default. (Recommendation; check how the page is currently routed.)

## 4. A reference theme block new hosts copy

- Pattern: Tailwind v4 themes are a CSS `@theme { ... }` block of variables; a library documents the
  closed token set and ships a copyable block. Tailwind docs describe `@theme` and `@source`:
  https://tailwindcss.com/docs/detecting-classes-in-source-files
- Format the block as: the token set grouped (surface, text, border, status roles, raw CSS vars),
  every value a neutral working default, each line commented with where it is used (one short
  comment per group, not per token). A host replaces values and never needs to add names.
- Keep exactly one source of truth: the test shell's input CSS imports the same block that the docs
  show, so "reference theme for tests" and "reference theme for new hosts" cannot drift. The existing
  invariant test (no raw hex, no palette classes) guards that templates use only the closed set; add
  a test that every token the templates reference is defined in the reference block (project rule
  in idea.md says tokens are verified by the invariant test, not a runtime check).
- Name the block's file in the generated-file docs so a host finds it (docs point at its path).

## 5. Override-by-template documentation

- Django's documented mechanism: loaders run in `TEMPLATES` order, `DIRS` is searched before app
  directories, and among apps the earlier `INSTALLED_APPS` entry wins; override by creating a file
  at the same relative path, optionally extending the original and replacing a block.
  https://docs.djangoproject.com/en/6.0/howto/overriding-templates/
- django-cotton: components resolve as templates under `cotton/`, so the same precedence applies.
  My search returned no cotton page stating this; treat as an inference and verify in the repo's
  cotton version before documenting it as fact (the spec's "contract test renders every primitive as
  default and as overridden" is the right proof).
- Good documentation of an override surface (pattern from Django admin and allauth docs):
  - A table: primitive name, file path to provide, props it receives, slots it receives, an example
    override. One row per `panel-*` primitive.
  - State plainly which names are overridable and which are not (the `partials/`
    and `modal/` templates are the framework's own structure; the primitives are the seam).
  - Warn about the sharp edge: the earlier app wins silently. The prefix decision (answers: `panel-`
    prefix) removes the silent clash with a host's `c-button`; the doc should say "to restyle, ship
    `cotton/panel-button.html`; your own `c-button` is never touched".
  - Warn that an override must keep the props and the closed class/Alpine hooks the framework's JS
    and invariant tests depend on, and list them.
  - Offer a one-line "thin wrapper" example (a `panel-button.html` that delegates to the host's own
    `c-button`), since that is exactly what FLS does and what most hosts will do.

## 6. The generated-file pattern for build integration

What the file says at the top: existing project practice is a one-line comment,
`/* Generated by manage.py write_active_theme_css — do not edit by hand. */`, followed by the
`@import`. The same pattern fits the new command. Recommended header for the new file:

```
/* Generated by manage.py <command> — do not edit by hand.
   Re-run it after installing or upgrading <package>; the path below is machine-specific. */
@source not-ignored "<abs or relative path to package templates>";
@import "<path to the package stylesheet>";
```

Details to settle:

- **Syntax**: idea.md and the research file name the form `@source not-ignored:`; I fetched
  Tailwind's docs page and it documents `@source "<path>"`, `@source not "<path>"` and
  `@source inline(...)` but not `not-ignored` (the fetch summary did not mention it). Treat the
  `not-ignored` spelling as unverified against Tailwind's public docs: the spec must confirm it
  with a build that scans a gitignored path and finds a class, and the in-tree test should do the
  same. Background on ignored sources:
  https://tailwindcss.com/docs/detecting-classes-in-source-files ; open reports that `@source`
  under gitignored allow-list `.gitignore` files can be silently skipped:
  https://github.com/tailwindlabs/tailwindcss/issues/19844 and
  https://github.com/tailwindlabs/tailwindcss/discussions/19118 (from search summaries; not opened).
- **Committed or not**: existing practice is gitignored because it holds a machine-specific path
  (`tailwind.active_theme.css`, "intentionally gitignored"). The new file holds a path into the
  installed package (a venv path), so it is machine-specific too: gitignore it, generate it in the
  build step (`npm run tailwind_build` chain, as with `write_active_theme_css`) and in CI/Docker
  build. The cost: a fresh checkout cannot run the Tailwind build until the command has run, so the
  docs and the npm script must always chain the command first. Add a clear error if the input CSS
  imports the file and it is missing; Tailwind's own "file not found" is the only signal otherwise
  (consider a short note in the docs: "if Tailwind says it cannot resolve `<generated file>`, run X").
- **Use relative paths where possible** (the existing command prefers a BASE_DIR-relative path and
  falls back to absolute). Keep that; it keeps a committed or cached file stable across machines
  when the package is vendored.
- **Idempotent and quiet**: rewrite only when content changes (avoids watcher loops in
  `tailwind_watch`), print the written path on success.
- **One file, two lines**: the answers fix that this file holds both `@source` and `@import`, so the
  host's input CSS has exactly one new line. The header comment should name both and say why.

## 7. Guaranteeing "no visual change" during a refactor

Three layers, cheapest first. FLS already has the first two; the third needs a choice.

### a. Rendered-HTML equivalence tests for wrapped primitives (recommended primary guard)

- Where the framework moves from calling `c-button` to `c-panel-button` and FLS wraps its own
  `c-button`, assert that the rendered HTML of the new call equals the old for a table of
  (variant, size, icon, disabled, href/button, extra attrs). Normalise whitespace and attribute
  order (parse with `html.parser`/BeautifulSoup, compare trees) so the test fails on class, tag or
  attribute differences, not on formatting.
- Do it before deleting the old call path: render both, assert equal, then switch. The idea's
  "the spec picks per primitive after rendering both" is exactly this test; keep the test as the
  permanent contract test.
- Add the same for each framework page fragment that the host shell now includes (modal host,
  quick-view host, sidebar nav) comparing with a stored golden file. Golden HTML is
  review-friendly (a diff in a PR shows what changed) and deterministic, unlike pixels.
- Stylesheet move check: because `.btn*`, `.panel-surface` and similar classes leave
  `tailwind.components.css`, add a check that the compiled FLS CSS still defines each such selector
  with the same declarations. Practical form: compile before and after, extract rules for the moved
  selectors and diff them (or assert the compiled CSS contains each selector). This catches
  unintended order/cascade loss, which the HTML test cannot see.

### b. Existing invariant tests and Playwright flows (project's stated check)

- The idea names the existing Playwright flows in `educator_interface` and the framework's own as
  the check, with FLS's whole suite proving nothing changed. Relevant existing guards from the
  `panel-framework` skill: `tests/invariants/test_templates.py` (anchors, trigger size, dialog
  structure, raw colours), `test_alpine_registration.py`, `test_public_names.py`, and
  `educator_interface/tests/playwright/test_touch_targets.py` ("Run that file after any change to a
  panel template"). Spec 4 must re-run these after each template move, and the invariant test must
  now read the framework's stylesheet (idea part 6).
- Computed-style assertions in Playwright (heights, widths, overflow) are more stable than pixels;
  the skill already encodes several (44px hit area, small button height). Extend with a handful for
  the new stylesheet (panel surface background, button colour) read through `getComputedStyle`.

### c. Screenshot baselines (visual regression)

- Playwright offers `expect(page).toHaveScreenshot()` / `expect(locator).toHaveScreenshot()`:
  first run writes the baseline, `--update-snapshots` accepts intended change. Rendering varies by
  OS/browser/hardware, so baselines should be generated in the same environment (commonly the
  official Playwright Docker image) as the comparison, with a small tolerance
  (`maxDiffPixelRatio`). Sources (third-party guides found by search; the official page was not
  returned): https://www.mintlify.com/microsoft/playwright/advanced/visual-comparisons ,
  https://qaskills.sh/blog/playwright-visual-comparison-snapshots-guide ,
  https://bugbug.io/blog/software-testing/playwright-visual-regression-testing/
- The Python Playwright binding this project uses has `expect(page).to_have_screenshot()`;
  confirm the project's version supports it before choosing (unverified).
- Cost for this project: baselines are binary files in git, CI-environment specific, flaky around
  fonts and animation, and the project today has none (no visual-regression tier found in the
  skill's enforcement list). For a one-off refactor a lighter pattern is usually enough:
  **a throwaway before/after screenshot comparison** done once by the spec's QA pass (capture the
  key pages at 375/768/1280 before touching templates, again after, diff manually or with a script),
  not a permanent tier. That matches "FLS looks and behaves the same afterwards" without adding a
  maintenance burden. Recommend: HTML equivalence + computed-style tests as the permanent guard;
  screenshots as a one-off QA artefact, kept out of git or committed under the spec dir only.

## 8. Cross-checks against `fls-dev:panel-framework`

- The skill says a host "loads both" JS files (`alpine-components.js` and `shell-components.js`).
  Idea part 1 names only `alpine-components.js` in the load-order contract; the docs must list
  both (`sidePanel`, `refreshTimer`, `visibilityPoller` come from `shell-components.js`) or state
  how spec 1 changed that. Flag for the planner.
- The skill and the invariant `test_alpine_registration.py` say every `x-data` name must be
  registered "unless the host supplies it": that "unless" is itself a host-contract item; the
  closed list of host-supplied Alpine names (if any remain after spec 1) belongs in the contract.
- The skill names components the templates call, including `c-button`, `c-back-link`,
  `c-callout`, `c-icon`, `c-button-group`, `c-pagination`, `c-dropdown-menu`. After the `panel-`
  rename the skill text (its Controls are components and Triggers sections) names old tags
  (`<c-back-link>`, `<c-button variant="link">`); spec 6 owns the skill, but this spec should list
  the places that go stale so spec 6 can update them. Also "No template writes a Cancel button" and
  the invariant tests reference component names and will need updating together.
- The skill relies on shared rules in `tailwind.components.css` (button hit area below `md`,
  `.panel-data-table`, focus-ring rule, select chevron). When the framework stylesheet takes the
  `.btn*` rules, the 44px hit-area rule moves with it or the button looks different on phones.
- The skill's rule "FLS themes override `.panel-surface`/`.panel-canvas`" must keep working: the
  framework stylesheet must be imported before the theme in the cascade (as `tailwind.components.css`
  precedes the active theme today). The generated file's `@import` position in `tailwind.input.css`
  matters; document it, and test it (computed style of a panel with a theme override).

## 9. Recommendations (ordered)

1. Continue the existing check id prefix and sequence; one Error per missing item; a
   one-line fix in `hint` with a docs path; silence-by-id documented.
2. One page "install in six steps" plus a table for primitive overrides; the same page holds the
   reference theme block, imported by the test shell's CSS so it cannot drift.
3. Make the reference page also the smoke test: renders under the minimal shell, shows icon grid
   and token swatches.
4. Generated file: header comment as in `write_active_theme_css`, gitignored, regenerated in the
   build chain, idempotent write, relative path preferred; verify the `not-ignored` spelling in a
   real build.
5. No-change guarantee: rendered-HTML equivalence tests (per wrapped primitive, normalised), a
   compiled-CSS selector check for the moved classes, existing invariant and Playwright tiers, and
   a one-off before/after screenshot pass rather than a permanent baseline tier.

## Sources

- https://docs.djangoproject.com/en/6.0/topics/checks/
- https://docs.djangoproject.com/en/6.0/howto/overriding-templates/
- https://tailwindcss.com/docs/detecting-classes-in-source-files
- https://github.com/tailwindlabs/tailwindcss/issues/19844
- https://github.com/tailwindlabs/tailwindcss/discussions/19118
- https://www.mintlify.com/microsoft/playwright/advanced/visual-comparisons
- https://qaskills.sh/blog/playwright-visual-comparison-snapshots-guide
- https://bugbug.io/blog/software-testing/playwright-visual-regression-testing/
- Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`,
  `freedom_ls/panel_framework/checks.py`,
  `freedom_ls/base/management/commands/write_active_theme_css.py`.

status: ok
