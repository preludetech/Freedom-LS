# Panel framework: templates, JS and CSS stop assuming FLS

Spec 4 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The framework's templates, JS and CSS in `freedom_ls/panel_framework/` stop relying on anything
FLS-specific being present, so a bare Django project with htmx, Alpine and the documented tokens can
render them. FLS looks and behaves the same afterwards. Six parts:

1. **A documented host contract for the page shell.** The host's base template must provide the fixed
   ids the framework addresses (`#interface-main`, `#main-content`, `#app-modal`, `#app-modal-body`,
   `#quick-view*`, `#instance-header`, `#sidebar-nav`), the `site_name` template variable (read by
   `partials/document_title.html` and `navigation_response.html`), htmx 2.x and the Alpine CSP build
   as globals, the global `X-CSRFToken` `hx-headers`, and script loading order (the framework's
   `static/panel_framework/js/alpine-components.js` after the host's own Alpine bundle and before
   Alpine starts). The framework includes its fragments (`modal_host`, `quick_view_host`,
   `announcer_host`, `sidebar_nav`, `breadcrumbs`, `document_title`) from the host's shell and ships no
   production shell. `reference/component_reference.html` stops extending `_base.html` and extends a
   base template named by a setting (read through the framework's `AppSettings`), defaulting to a
   minimal shell the framework ships for docs and tests. `{{ site_name|default:"" }}` is the fallback
   when the host supplies no `site_name`.
2. **Framework-owned primitives.** Templates under `templates/cotton/` that call the host's `c-button`,
   `c-button-group`, `c-chip`, `c-callout`, `c-back-link`, `c-pagination`, `c-dropdown-menu`
   (plus Alpine `dropdownMenu`), and the page component used by the reference page, call framework
   copies instead. `c-modal-trigger` and `c-quick-view-trigger` are already the framework's (spec 1
   moved them in from `freedom_ls/base/templates/cotton/`). The Alpine pieces they
   need that live in other apps' bundles (`sidePanel` for the mobile filter sheet in
   `table_toolbar.html`, `refreshTimer` and the `conversationChanged` event in `sidebar_nav.html`)
   are resolved per spec 1's decision and this spec makes the templates stop naming FLS apps.
3. **A framework-owned stylesheet.** `.panel-surface`, `.panel-canvas`, `.modal-backdrop-host` and the
   `.btn*` classes the framework uses leave `tailwind.components.css` for a stylesheet shipped in the
   package. FLS's `tailwind.components.css` imports it, and FLS themes keep overriding
   `.panel-surface`/`.panel-canvas` as they do today.
4. **Icon names and theme tokens as a checked host contract.** The 21 static `c-icon` names the
   templates use, plus those reached through `c-button icon_left` (`add`, `filter`, `retry`), are
   documented as a closed list. The closed set of role tokens and raw CSS vars the templates use is
   documented, with a reference theme block for tests and new hosts. A system check in
   `freedom_ls/panel_framework/checks.py` renders each icon name and reports missing ones; another
   checks that the configured base template exists. Tokens are verified by the existing invariant test
   (no raw hex, no palette classes), not by a runtime check.
5. **A Tailwind source command.** A management command in the framework writes a generated CSS file
   holding an `@source` line resolved to the installed package's templates (and JS if class strings live
   there). The host's input CSS imports that file. It is modelled on
   `freedom_ls/base/management/commands/write_active_theme_css.py`. The path is written with
   `@source not-ignored:` so a package under a gitignored `.venv` is still scanned. FLS's
   `tailwind.input.css` swaps its `@source "./freedom_ls/**/templates/**/*.html"` coverage of the
   framework for the generated import.
6. **A framework-owned test shell.** The framework's component, invariant and Playwright tiers run with
   a shell the framework ships under `freedom_ls/panel_framework/tests/templates/panel_framework/`
   (replacing `test_interface.html`, which extends FLS `_base_interface.html`, and
   `test_component_reference.html`, which extends `_base.html`). It loads htmx, Alpine, the framework
   JS and a compiled stylesheet. It covers what spec 2 adds: expandable rows with compact density, the
   required-reason dialog and the `as_of` stamp. The invariant test stops reading
   `FREEDOM_LS_PACKAGE_DIR.parent / "tailwind.components.css"` (`tests/invariants/test_templates.py`)
   and reads the framework's own stylesheet. Playwright helpers the tier uses
   (`freedom_ls.tests.playwright_helpers`: `assert_no_horizontal_overflow` and the others used) are
   copied into the framework's tests.

## Why

Spec 5 moves the framework into its own repo. A move now would leave templates calling `c-button`,
`c-icon`, `sidePanel` and `refreshTimer` that exist only in FLS, CSS classes defined only in FLS's
stylesheet, and a Tailwind scan that finds the framework only because it sits in the FLS tree. The
other Django project would get a library that renders unstyled and silently. The coupling audit
(`research_coupling_audit.md` sections 1b, 1c, 1d) found the Python clean and the templates the real
dependency. Doing this in-tree, before the move, means FLS's own suite proves nothing changed.

## What is settled

- Depends on spec 2 (and through it spec 1): both rework these templates and the Alpine file, and the
  test shell must cover spec 2's additions.
- The template directory name `panel_framework/` is kept, so the 18 template path references in
  `educator_interface` do not change.
- Primitives ship as overridable defaults and the page shell is a documented contract, not shipped
  (cut assumption). Overriding is by template precedence: a project `DIRS` entry or an earlier app wins.
- The host stack is the same as FLS's: django-cotton, htmx 2, Alpine CSP build, Tailwind v4 with role
  tokens. No other frontend stack is supported.
- `c-pagination` and `c-dropdown-menu` are too big to treat as small host primitives (audit D3): the
  framework owns its copies, with their Alpine, like the other primitives. FLS keeps its own
  `c-pagination` for its other apps.
- The user-facing surface of FLS does not change. The existing Playwright flows in
  `freedom_ls/educator_interface` and the framework's own are the check.
- This spec adds one generated file and one management command to the Tailwind flow; the host runs the
  command before `npm run tailwind_build`. FLS wires it into its existing build step beside
  `write_active_theme_css`.
- Tailwind v4 `@source` honours `.gitignore`, so a `.venv` path needs `@source not-ignored:`
  (`research_uv_sources_and_consumers.md`).
- Python decoupling (settings helper, CSV helpers, site hook, test settings for the unit tier) is
  spec 3's. This spec's test shell must work with the standalone settings spec 3 produces and must not
  duplicate its settings work. The package move, the label and install mechanics are spec 5's.

## Open until the spec

- **How framework primitives avoid clashing with a host's same-named cotton components** (this
  child's owned unknown). Recommended default: framework templates call `panel-`-prefixed primitives
  (`c-panel-button`, `c-panel-chip` and so on, shipped as `templates/cotton/panel-*.html`, matching the
  framework's existing `panel-*` naming), so a host's `c-button` is never shadowed by app order. A host
  restyles by providing its own `cotton/panel-button.html` earlier in precedence. FLS provides thin
  `panel-*` wrappers delegating to its own `c-button`, `c-chip` and the rest so its look is unchanged, or
  accepts the framework defaults where the output is identical; the spec picks per primitive after
  rendering both. A contract test renders every primitive both as default and as overridden. The
  alternative (ship unprefixed `button.html` and rely on app order) is rejected because the collision is
  silent. `c-pagination`, `c-dropdown-menu` and the two triggers get the same prefix if they would
  clash with FLS's.
- Whether `.btn*` classes move with the framework stylesheet or the framework's button stops using
  them. Follow whichever the prefixed `panel-button` needs.
- Whether the minimal default shell and the test shell are one template or two.
- How the framework stylesheet is delivered to a host (an `@import` of a path the Tailwind source
  command also writes, or a separate documented import). The spec chooses; the requirement is one
  documented line in the host's input CSS per file.
- Whether the compiled stylesheet for the Playwright tier is built by an npm script in the package or a
  fixture; spec 5 owns the package repo's tooling, so keep it runnable in-tree here.

## Out of scope

- The Python imports of FLS (`AppSettings`, CSV helpers, `SiteAwareModel`, request-site hook): spec 3.
- The new capabilities themselves (spec 2) and where `sidePanel`, `refreshTimer` and
  `conversationChanged` live (spec 1). This spec consumes both.
- Moving the framework to its own repo, the label, `v0.1.0` and install mechanics: spec 5.
- The host-contract skill and plugin: spec 6. This spec writes only the contract text the system
  check messages and the framework's own docs point at.
- Supporting a host on another frontend stack, shipping a production page shell, a visual redesign of
  the framework's components.
- Making the icon registry or token set open-ended.

## Resources

- Source idea: `spec_dd/1. next/extract_panels_framework/idea.md`.
- `spec_dd/1. next/extract_panels_framework/research_coupling_audit.md`: T1-T11, J1-J5, S1-S5, X3,
  X8, and decision D3 (primitives).
- `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md`: the `@source`
  command row.
- `spec_dd/1. next/extract_panels_framework/research_uv_sources_and_consumers.md`: `@source
  not-ignored:`, the concrete template's Node-only Tailwind stage.
- Code: `freedom_ls/panel_framework/templates/`, `.../static/panel_framework/js/alpine-components.js`,
  `.../checks.py`, `.../tests/templates/panel_framework/test_interface.html`,
  `.../tests/templates/panel_framework/test_component_reference.html`,
  `.../tests/invariants/test_templates.py`, `freedom_ls/base/templates/cotton/` (button, button-group,
  chip, callout, back-link, pagination, dropdown-menu, modal-trigger, quick-view-trigger),
  `freedom_ls/base/static/base/js/alpine-components.js`,
  `freedom_ls/base/management/commands/write_active_theme_css.py`, `freedom_ls/icons/`,
  `tailwind.input.css`, `tailwind.components.css`.
- Skills: `ds:template`, `fls-dev:template`, `ds:alpine-js`, `fls-dev:alpine-js`,
  `fls-dev:icon-usage`, `fls-dev:frontend-styling`, `ds:testing`, `fls-dev:playwright-tests`.
