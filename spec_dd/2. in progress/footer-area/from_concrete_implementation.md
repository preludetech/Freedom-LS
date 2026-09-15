What's there now

submodules/Freedom-LS/freedom_ls/base/templates/_base.html:117 ends </main>, then the debug badge, then </body>. There is no footer element and no footer block anywhere in FLS's web chrome (the only footer hits in the submodule are the email template, the PDF report, and slot names on cotton/media-card.html / cotton/modal.html). {% block extra_body %} exists but sits inside <main>, so it's page content, not chrome.

Every page funnels through _base.html — 21 templates, including dashboard.html and course_detail.html directly, and course topic pages via _base_interface.html.

So today the only way to add a site footer is Tier-3 whole-file shadowing: templates/_base.html in this project. That's a ~140-line fork carrying the PostHog snippet, the CDN script tags, the whole head_seo block and the debug badge, which then has to track FLS forever. This project already carries one such fork (apps/landing_pages/templates/landing_pages/_landing_base.html, whose own comment admits the maintenance cost). A second one for a footer is a bad trade.

What would need to change in FLS

1. A footer block in _base.html. After </main> (line 117), before the debug badge:

{% block footer %}{% include "partials/footer.html" %}{% endblock footer %}

Outside <main> so <footer> is a sibling landmark rather than nested in main content. It mirrors the existing {% block header %} at line 99 exactly. Purely additive — no existing page changes until something fills it.

2. Ship partials/footer.html in FLS. Then a downstream project overrides one small file at templates/partials/footer.html instead of the page shell. This is the same seam FLS already uses for partials/header_bar.html, and it's Tier 3 applied to a ten-line file rather than the whole shell. FLS has to decide whether the shipped partial renders nothing at all or a minimal default (legal-doc links, copyright). Either works; rendering nothing is the safer default since it changes no current page.

3. FLS should suppress it where it's wrong, so no downstream rediscovers it. _exam_runner_base.html already blanks {% block header %} because the runner owns its own bar, and course_form_page.html has its own sticky footer inside the runner layout — so the runner base should blank footer the same way. Error pages (400/403/404/429/500/503) are arguable; leaving them is fine.

4. The _base_interface.html question — this is the real decision and it's FLS's to make. That shell's sidebar is a sticky, full-height docked column (height: calc(100vh - var(--sidebar-top)), _base_interface.html:126-131) and the shell owns its own px-4 sm:px-6 lg:px-8. A footer placed after </main> renders full-bleed under the entire grid, so on desktop a learner scrolls a whole viewport of sidebar past before reaching it. FLS should decide whether course-topic and educator pages get the footer, a reduced one, or none, and encode that as a footer override in _base_interface.html — not leave each concrete project to work it out.

What does not need to change

- HTMX. Course-player navigation boosts with hx-target/hx-select="#interface-main" (cotton/player-nav.html:27-32), so a footer outside <main> is never in a swap and survives boosted navigation untouched. No JS or config change.
- Settings / context processors. This project's own partials/footer.html can use {% url %} and its own template tags directly. A setting would only be needed if FLS wanted configuration-driven default footer links, which isn't required for the block to be useful.
- Template loader wiring. BASE_DIR / "templates" is already first in TEMPLATES["DIRS"] (config/settings_base.py:164-166) ahead of the app-directories loader, so the override path works as soon as the block exists.

One local caveat worth knowing: FLS_THEME = "first_class" resolves to the theme directory inside the read-only submodule, so the theme's templates/ directory is not a usable override seam in this project. Creating themes/first_class/ locally would shadow the whole theme including its CSS. The project's footer override belongs in templates/partials/footer.html.

Documentation-wise, if this ships, the footer partial should be named in docs/product/configuration-and-extension.md and the theming how-to's Tier-3 section, so it reads as an advertised extension point rather than something each project has to discover.
