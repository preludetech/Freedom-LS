# Research: prior art for extract_panels_framework-4-template-contract

Scope note: this worker had no shell, so `git log --oneline -- <paths>` was not run. History below comes from the done specs' own reports, not git.

## Here: earlier extraction specs (decisions that bind spec 4)

### Spec 1 (`3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code`)

- "No copies left behind": a cotton component in two apps is shadowed silently by `INSTALLED_APPS` order (`1. spec.md:70-71`). Spec 1 moved `modal-trigger` and `quick-view-trigger` out of `base` and deleted the old files in the same change. This is the origin of the `panel-` prefix answer: spec 4 must create framework copies of `button`, `chip` and the rest *without* leaving same-named files that fight FLS's. The prefix removes the order dependence.
- Alpine `sidePanel` and `refreshTimer` moved to a new `panel_framework/static/panel_framework/js/shell-components.js` (not `alpine-components.js`). `_base.html` loads it with `defer` before Alpine. The upgrade note's manual step says a host overriding `_base.html` must add that script, or `sidePanel`, `refreshTimer` and `eventRefresh` are undefined. So the idea's contract text ("`alpine-components.js` after the host's bundle") is incomplete: the load-order contract must name **both** files (`shell-components.js` and `alpine-components.js`).
- Spec 1 added an Alpine registration test (`1. spec.md:488-493`): fails, naming template and component, when an `x-data` name in a framework template is not registered in `alpine-components.js` or `shell-components.js`. Names that `base` registers and framework templates use (notably `dropdownMenu`) form an explicit allow-list "for spec 4". Spec 4 owns removing the allow-list entry for `dropdownMenu` once the framework ships its own. A second test fails when a name is registered in two component files, so a framework `dropdownMenu` copy cannot coexist with FLS's under the same name: it needs a distinct name or FLS's must go.
- `nav item count_refresh_events` replaced the hard-coded `conversationChanged` (J2), so `sidebar_nav.html` no longer names comms. Check that remains true.
- Upgrade-note shape: `requires_tailwind_rebuild: true`, `changed_template_paths`. Spec 4 will need the same, and a manual step "run the Tailwind source command before `npm run tailwind_build`".
- Spec 1 research found `sidePanel` was used outside the framework (`_base_interface.html`, learner course base, `content_engine` comment). Same hazard class applies to `dropdownMenu` and `c-pagination` copies: FLS keeps its own for other apps, so two implementations will exist.
- Spec 1 QA (`qa_report.md`): B1 sticky table header paints opaque white inside tinted `panel-notice` (UNRESOLVED after a failed fix, commit 1fe573edc reverted in 166820610). The cause is a CSS token composited against the wrong surface. Lesson for the stylesheet move: the `--panel-table-head` family and `.panel-surface`/`.panel-canvas` interplay is fragile; moving CSS must be byte-identical in behaviour. B2: a hard-coded "Close navigation" button in the educator `_shell.html` (host-side, fixed).
- Spec 1 prior-art lessons (carried from earlier panel specs): nested `x-data="sidePanel"` shared scope (fixed by instance-local fields); no-JS `<noscript>` CSS left `opacity:0`. Both are why JS-off paths need tests when CSS moves. The test shell must support a JS-off render.
- Flake: `test_quick_view_flow.py::test_quick_view_drawer` failed once under load while QA used a dev server, passed alone. Expect this when the Playwright tier runs beside other servers.

### Spec 2 (`3. done/2026-11-18_18:50_extract_panels_framework-2-new-capabilities`)

- Changed `tailwind.components.css` and added templates (`_row_detail`, `_reason_dialog`, `_lazy_region` `as_of`, `child_rows_toggle`, `row_indent`). These are the surfaces spec 4's test shell must cover. It also changed `freedom_ls/base/templates/cotton/pagination.html`. That means the framework's `c-panel-pagination` copy must be taken from the **post-spec-2** FLS pagination, not the audit's older line count (223 lines).
- QA B2: `callout.html` renders `class="my-6 ... my-0"`, and `my-6` won. Fixed (84fa626e4) so caller margin classes override. A host-restyled or framework `panel-callout` must keep that "caller class wins" behaviour. Add it to the contract test.
- QA B3: sort-only toolbar renders an empty band (fixed in `table_toolbar.html`). Full tier then passed: 15103 tests.
- QA B1 was a Python depth bug, not template.
- A commit-blocking hook (mypy) was tripped by an earlier committed duplicate helper in `test_quick_view_flow.py`. Spec 4 copies Playwright helpers; avoid duplicate definitions.

### Themable-implementations specs (done, 2026-05)

- Phase 1 spec (`...phase-1-theme-resolver-and-default-tokens/1. spec.md:165-181`): the origin of `@source "./freedom_ls/**/templates/**/*.html"` and `write_active_theme_css`. It records the same pitfall spec 4 solves: "`@source` honours `.gitignore`. If FLS is installed under a path excluded by an ancestor `.gitignore` (`.venv/`, `node_modules/`), the glob silently skips" with only a "symlink / asset-pipeline-copy workaround" documented; and "New cotton class names not present at build time are not generated."
- Phase 4 spec: template overrides rely on cotton's loader chain, "a same-named file in a higher-priority `DIRS` entry shadows the FLS default automatically. No new loader logic." This is the precedence mechanism the idea's host-override model uses. It worked because overriding was by `DIRS` (top priority); an override from an *app* depends on `INSTALLED_APPS` order (the silent case).
- Phase 3: Tier-2 theme overrides of `.btn-primary`, `.chip`, `.btn-outline` via `@apply` in the theme CSS. Themes override framework-used `.btn*` classes today. If `.btn*` leave `tailwind.components.css` for the framework stylesheet, theme overrides must still win (layer / import order). Keep the stylesheet import before theme CSS, or in an earlier `@layer`.
- Course-card upgrades: `tailwind.input.css` has an `@source inline(...)` safelist for dynamically built accent classes. Classes assembled in Python or JS strings are not scanned from templates. Check the framework for class names built in `.py` or `.js` (audit S1 says none seen in `.py`; JS not stated). The spec should say whether the generated file also adds the JS dir.

### Research in `spec_dd/1. next/extract_panels_framework/`

- `research_coupling_audit.md`: T1-T15, J1-J6, S1-S5, X3/X8 as listed in the idea. T3-T10 primitives: button (variants), button-group (89 lines, variant `right`), chip (26 lines, `size="xs"`, `:attrs`), pagination (223 lines, `page_obj`), dropdown-menu (94 lines + Alpine `dropdownMenu` at `base/.../alpine-components.js:81`), callout, back-link. T14: `tests/cotton_helpers.py` imports `django_cotton.compiler_regex.CottonCompiler` (internal module; breaks on cotton refactor). Component tier: 10 files rely on `render_cotton`, needing primitives present. Playwright tier needs a Tailwind build (S5). The coupling audit's own sec 5 says component tests need the primitives, which this spec delivers.
- `research_packaging_and_distribution.md` row (line 98): the `@source` management command modelled on `write_active_theme_css` writing `tailwind.active_theme.css`.
- `research_uv_sources_and_consumers.md` is cited by the idea but does not exist in `spec_dd/1. next/extract_panels_framework/` (only `idea.md`, the audit and the packaging research). The `@source not-ignored:` claim therefore has no local source. See below.

### Not found

No done spec covers an icon registry check, an invariant-test shell or a system check for templates beyond the above. Spec 1's `1. spec.md` mentions the invariant tests (`tests/invariants/test_templates.py`, no raw hex or palette classes) as existing, not as prior failures.

## Elsewhere: pitfalls extracting UI from a monolith into a Django package

1. **Tailwind v4 does not scan ignored paths.** Official docs: Tailwind scans everything except files in `.gitignore`, `node_modules`, binary, CSS and lockfiles; external libraries "are usually listed in your `.gitignore`", and `@source` registers them. https://tailwindcss.com/docs/detecting-classes-in-source-files
2. **Verify `@source not-ignored:`.** I found no Tailwind documentation of a `not-ignored` keyword; the docs page does not use the term. A search found no official source either. Treat the idea's syntax as UNVERIFIED and test against the Tailwind version pinned in `package.json` before the spec relies on it. Reported behaviours that bear on it: a `.gitignore` that is an allow-list (`*` then `!x`) makes `@source` into ignored dirs fail silently (https://gh.r-mj.com/tailwindlabs/tailwindcss/issues/19844; Hyva advice to use a deny-list: https://docs.hyva.io/hyva-themes/faqs/tailwindcss.html); a nested `.gitignore` (uv writes one inside `.venv`) blocked a `@source` path (https://fixgraph.netlify.app/issue/gh-tailwindlabs-tailwindcss-15452); `node_modules` is skipped since 4.1.0 regardless of `.gitignore` (https://scriptagc.wasmer.app/https_redirect_github_com/tailwindlabs/tailwindcss/pull/17255); an explicit `@source` can override it (https://v3.tailwindcss.com/docs/v4-beta); `source(none)` did not disable `.gitignore` handling in one report (https://scriptagc.wasmer.app/https_redirect_github_com/tailwindlabs/tailwindcss/issues/16920). The fallback if `not-ignored:` is not real: the command writes the path of a copy or symlink outside ignored dirs, or the test must assert a framework-only class (e.g. one used only in a framework template) appears in compiled output from an installed (not in-tree) path. Put exactly that check in the spec.
3. **`@source` paths are relative to the stylesheet that contains them.** The generated file must write a path that is correct relative to its own location (or absolute), and the `@import` of the generated file must come after `@import "tailwindcss"` so the sources register in the same build. (Docs: "relative to the stylesheet", same page as item 1.)
4. **Template shadowing is silent.** Django's `app_directories` loader returns the first match by `INSTALLED_APPS` order; cotton resolves by filename across all apps' `templates/cotton/`. A framework `button.html` and a host `button.html` clash with no error. This is the reason for the `panel-` prefix (already decided). Residual risk: the framework's `panel-*` names could still collide with a host's own `panel-*` files (FLS's `educator_interface` uses `panel-*` names? check at spec time), so the contract test should assert uniqueness of cotton names across all installed apps' `templates/cotton/` dirs. Spec 1's own note (`research_prior_art.md` there) made the same point without web sources (general practice, not web-verified).
5. **Alpine registration order.** `Alpine.data(...)` must run in `alpine:init`, so component scripts must be deferred and precede Alpine core. A missing component is only a console error under the CSP build. Spec 1 already has a test for names in framework templates; extend it to the new `panel-*` components and to host-provided names (empty allow-list after spec 4 ideally).
6. **Static file naming and caching.** Moving or adding static files changes `collectstatic` manifest hashes; the stylesheet and the compiled test CSS need a rebuild step noted in upgrade notes (as spec 1's notes do).
7. **CSS ordering and layers.** Tailwind v4 emits `@layer` ordering; a framework stylesheet `@import`ed in the host input CSS lands in whichever layer it declares. Theme overrides of `.panel-surface`/`.btn-*` must come later or sit in a higher layer. Check by an invariant that the compiled CSS places theme overrides after the framework rules (spec 1 QA B1 is an example of a token/surface compositing regression from CSS moves).

## Open cautions for the spec

- `shell-components.js` is a second script in the load-order contract (see Spec 1 above); the idea names only `alpine-components.js`.
- Spec 1's duplicate-registration test will fail if the framework registers `dropdownMenu` while `base` still does; decide naming (`panelDropdownMenu`) or removal.
- Pagination copy must track spec 2's `pagination.html` changes.
- `callout` caller-margin override behaviour (spec 2 B2) belongs in the contract test.
- Spec 1 QA B1 (table header over tinted notice) is still unresolved; do not read a visual diff of that component as a regression from this spec.
- `research_uv_sources_and_consumers.md` is missing; `@source not-ignored:` is unverified.

status: ok
