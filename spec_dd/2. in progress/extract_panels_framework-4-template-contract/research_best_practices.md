# Research: best practices for a reusable Django app's templates, cotton, Alpine and Tailwind

Topic: best_practices. Spec: extract_panels_framework-4-template-contract. Sources fetched on 2026-11-19. Items marked (unverified) came from general knowledge, not a fetched page.

## 1. Namespacing and overriding templates

- Django resolves a template by its path across `DIRS` first, then each app's `templates/` in `INSTALLED_APPS` order. The first match wins. An override must sit at the same path as the original. Source: https://docs.djangoproject.com/en/5.2/howto/overriding-templates/
- Django's docs say that `DIRS` is searched before `APP_DIRS`. A project-level override therefore always beats an app's copy. App order only decides between apps.
- Django's documented override-and-extend trick: a template that extends its own name skips itself and extends the original. `{% extends "admin/base_site.html" %}` with `{{ block.super }}` is the example. The framework can document this for hosts that want to tweak a primitive rather than replace it.
- The convention is to namespace every shipped template under the app name (`panel_framework/...`). This is what the framework already does, and the idea keeps it.
- Cotton components cannot sit in a namespace folder of their own, because the tag name is the path. Cotton's tag `<c-weather-card>` maps to `cotton/weather_card.html`, and dots in an `is=` value map to subfolders (`icons.star` is `cotton/icons/star.html`). Source: https://django-cotton.com/docs/components. The settled `panel-` prefix is the usual stand-in for a namespace. A subfolder (`<c-panel.button>`) is the alternative, but the page did not state the rule directly, so check it against the installed cotton version.
- Cotton components live in the `cotton/` folder of any template directory. Resolution therefore follows the same loader precedence as ordinary templates (inferred). The docs page fetched did not state the search order, `COTTON_DIR` or `COTTON_BASE_DIR`. Read the installed cotton source and the `/docs/configuration` page before the spec relies on a specific rule. A contract test that renders a primitive both as shipped and as overridden proves the precedence regardless.
- The prefix choice avoids silent shadowing. An unprefixed `button.html` would be won or lost by `INSTALLED_APPS` order. A prefixed name is only ever replaced on purpose, by a host file with the same name.
- Best practice for override points: keep the primitive's props (its `c-vars`) and its slots documented as the override contract, and keep the number of primitives small.

## 2. Documenting a host base-template contract

Established patterns (general practice, unverified against a single canonical source):

- Name the contract in one doc: required blocks, fixed element ids, context variables, and global scripts with their load order. Ship the doc inside the package and have check messages point at it.
- Make the base template selectable by a setting, with a default that the package ships for docs and tests. The framework's `AppSettings` setting for the reference page's base template matches this. Django REST framework's `TEMPLATE` style and django-allauth's `base.html` override both follow the same idea (unverified).
- Use `{% extends var %}` or resolve the name in the view and pass it as context. Both are standard Django.
- Give every optional context variable a safe fallback in the framework's templates, as the idea does with `{{ site_name|default:"" }}`.
- Prefer includes of framework fragments from the host's shell (the idea's design) over making the host extend a framework shell. The host keeps its own page layout, and the contract stays small.
- Test the contract by rendering the shipped default shell, so the documented ids exist in at least one real template.

## 3. Django system checks

Source: https://docs.djangoproject.com/en/5.2/topics/checks/

- Register with `@register(...)` in a module loaded from `AppConfig.ready()`. The function takes `app_configs` and `**kwargs`, and returns a list of messages.
- A check also receives `databases`. When it is `None`, the check must not touch a connection. Template checks need no database.
- Message ids follow `<app_label>.<E|W><nnn>`, for example `panel_framework.E001`. The docs give examples and no formal rule. Ids are used to filter and to silence (`SILENCED_SYSTEM_CHECKS`), and tests can assert on the exact id.
- Severity: `Error` stops `runserver` and `migrate`. `Warning` prints and can be silenced. A missing base template or a missing icon renders nothing or breaks pages, so `Error` fits those. A host that deliberately overrides an icon set or has a lenient theme may want a `Warning`.
- Tags: any string works (`register("panel_framework")`), so a host can run `check -t panel_framework`. Django ships a `Tags.templates` tag for template-engine checks, which the Django docs list in the full tag set. Registering under both `Tags.templates` and the app's own tag is a reasonable pattern (unverified for the combined form).
- `deploy=True` is for production-only settings. The template contract is needed in development as well, so do not use it.
- Cost: a check that renders every icon runs on every management command. Keep it quick, and catch `TemplateDoesNotExist` and cotton's failure type specifically rather than a bare `except`.
- Test a check by calling the function and comparing messages, or by `call_command("check")` with `SystemCheckError`.

## 4. Tailwind v4 in a reusable package

Sources: https://tailwindcss.com/docs/detecting-classes-in-source-files and https://tailwindcss.com/docs/theme

- Automatic detection skips `.gitignore`d files, `node_modules`, binary files, CSS files and lock files. Tailwind's own advice for an external library is an explicit `@source "../node_modules/@acmecorp/ui-lib";`.
- A Python package under a gitignored `.venv` is a gitignored path, so a plain `@source` may not scan it. The idea cites `@source not-ignored:` for this (from `research_uv_sources_and_consumers.md`). The fetched docs page does not mention `not-ignored`. Confirm the exact syntax against the installed Tailwind v4 version before writing the command, since a wrong keyword fails silently by emitting no classes.
- Related directives that the page does document: `@source not "<path>"` to exclude, `@source inline("...")` to safelist, and `@import "tailwindcss" source(none)` to turn off auto-detection so only declared sources count. `@source inline()` is the tool for class names built at runtime, which a scan cannot see. Tailwind cannot read string concatenation, so every class in a template must appear whole.
- Paths in `@source` are relative to the CSS file that holds them. A generated file must therefore write a path correct for where it is written, or an absolute path. The generated-file approach in the answers (one file with the `@source` line and an `@import` of the package stylesheet) gets this right by construction, because the command knows both locations. Relative or absolute, check the written output with a test.
- Plain CSS layer: shipping a package stylesheet that is imported into the host's Tailwind input lets it use `@layer components { ... }` and `@apply`, so utilities in the host still override it by cascade layer order. If the file uses `@apply` or `theme()`-style lookups against the host's tokens, it must be processed by the host's Tailwind build, not served raw. A fully plain CSS file (no `@apply`) can be served as a static file, but then the `@source` scan is not needed for it. Decide per file.
- Theme tokens: `@theme` variables are CSS variables, so `var(--color-x)` works in plain CSS and a host can swap values in a theme block. `@theme` must be top-level. Use `@theme inline` when a token points at another variable, so the utility uses the value directly and not a variable that may be defined deeper in the tree. `@theme static` forces every variable to be emitted, even unused ones, which suits a documented closed token set. Tailwind's docs show sharing tokens as a separate CSS file that a project `@import`s. That is the model for the reference theme block (one file used by tests and new hosts).
- A closed token set is easiest to keep honest with the existing invariant test (no raw hex, no palette classes), as the idea says.
- Do not rely on default palette classes in shipped templates. Use role tokens only. A host that sets `--color-*: initial` would otherwise lose them.

## 5. Alpine components from a package with the CSP build

Source: https://alpinejs.dev/advanced/csp

- The CSP build cannot evaluate arrow functions, property assignment, destructuring, template literals or spread in inline expressions, and `window`/`document` are not available there. All logic goes into `Alpine.data("name", () => ({...}))` and templates reference `x-data="name"`.
- The fetched page does not cover `alpine:init`. The standard pattern from the main Alpine docs: register in a listener, `document.addEventListener("alpine:init", () => Alpine.data("dropdownMenu", ...))`. The framework script must therefore be loaded so that its listener is attached before `Alpine.start()` runs. With a bundled host (`import Alpine; window.Alpine = Alpine; Alpine.start()`), the script must be a classic or deferred script placed so it executes before start. With the CDN build and `defer`, a script placed before the Alpine tag works. This matches the idea's contract: framework JS after the host's Alpine bundle imports and before start. Verify the actual load order in the host shell and document it, since a late script fails with "name is not defined" at runtime.
- Name collisions: `Alpine.data` is one flat registry. A second registration with the same name replaces the first, so a prefix (`panelDropdownMenu`) or a documented override order is the safe approach (unverified: the docs do not state the replace behaviour). The idea keeps `dropdownMenu`. If FLS also registers `dropdownMenu`, the later registration wins, so the contract test must run both load orders.
- Components that need an external piece (`sidePanel`, `refreshTimer`) are best made optional: the template guards on the registered name, or the framework ships its own copy. This is spec 1's decision.
- Registering through a single package file keeps a host to one `<script>` tag.

## 6. Testing a reusable app standalone

Established practice (general, unverified against a single source):

- Ship a minimal test project (settings, urls, a tiny shell template) inside the package's tests, so tests need no host. This is what spec 3's standalone settings and the single-shell answer cover.
- Keep the test shell in the package's test templates directory, which is on the template path only under the test settings, so it never leaks to hosts.
- Compile a small stylesheet for browser tests from a framework input CSS that imports the reference theme, the framework stylesheet and the `@source` line. Build it with an npm script, or a session-scoped fixture that runs the Tailwind CLI once. The answers chose the npm script. Make the Playwright tier fail loudly when the compiled file is missing, since an unstyled page passes many structural assertions while hiding layout bugs.
- Test every primitive both ways: the shipped default, and with an override template dir earlier in `DIRS`. Django's `override_settings(TEMPLATES=...)` or a test-only app earlier in `INSTALLED_APPS` does this.
- Add an invariant test that asserts the framework templates call only `c-panel-*` primitives, or `c-icon` names from the closed list, so a stray host-only component fails in the framework's own suite and not in a host.
- Add a parity test for the FLS side: render a page before and after the change, or rely on the existing Playwright flows, as the idea does.

## Summary of recommendations for the spec

1. Keep `panel_framework/` as the template path. Use the `panel-` prefix for cotton primitives. Document the override as a same-named file earlier in precedence, and note that `DIRS` beats apps.
2. Make the base template for the reference page a setting with a shipped default. Document the shell contract in one doc, and point check messages at it.
3. Use ids like `panel_framework.E00x` and `W00x`. Use `Error` for a missing base template and a missing icon. Run no database access. Tag with the app name.
4. Confirm `@source not-ignored:` syntax and `@source` path semantics against the installed Tailwind before coding the command, and test the generated file.
5. Register all Alpine components in one package script via `alpine:init`, documented load order, and a load-order test with FLS's bundle.
6. One shipped shell for docs, reference page and tests. A compiled stylesheet from an in-tree npm script. Contract tests for default and overridden primitives.

## References

- https://docs.djangoproject.com/en/5.2/howto/overriding-templates/
- https://docs.djangoproject.com/en/5.2/topics/checks/
- https://django-cotton.com/docs/components
- https://tailwindcss.com/docs/detecting-classes-in-source-files
- https://tailwindcss.com/docs/theme
- https://alpinejs.dev/advanced/csp

status: ok
