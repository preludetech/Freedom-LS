# Answers: extract_panels_framework-4-template-contract

Asked by `/sdd:start` before the spec was written.

- Q: How should the panel framework's own primitives avoid clashing with a host's same-named cotton components? → A: `panel-` prefix: framework templates call `c-panel-button`, `c-panel-chip` and so on, and a host restyles by shipping its own `cotton/panel-*.html` earlier in precedence (asked up front)
- Q: Should the minimal default shell and the Playwright test shell be one template or two? → A: One template, serving the docs, the reference page and the test tiers (asked up front)
- Q: How should a host pull in the framework's stylesheet? → A: The Tailwind source command writes one generated CSS file holding both the `@source not-ignored:` line and an `@import` of the package stylesheet, so the host adds a single `@import` line (asked up front)
- Q: How should the compiled stylesheet for the framework's Playwright tier be built while the framework is in-tree? → A: An in-tree npm script compiling a small framework input CSS (reference theme tokens, framework stylesheet, `@source`), which spec 5 can lift into the package repo (asked up front)
- Q: How should the framework stylesheet handle the `.btn*` and `.chip*` classes that FLS's `c-button`/`c-chip` and the first_class theme also use? → A: Prefix them: the framework defaults use `.panel-btn*` and `.panel-chip*`; FLS overrides `panel-button`/`panel-chip` with thin wrappers around its own `c-button`/`c-chip`, so FLS keeps `.btn`, `.chip` and its theme overrides (asked while the research ran)
- Q: Where should `partials/page_title.html` live, given `navigation_response.html` and seven FLS templates include it? → A: The framework ships `panel_framework/partials/page_title.html`; FLS's `partials/page_title.html` becomes a one-line include of it (asked while the research ran)
