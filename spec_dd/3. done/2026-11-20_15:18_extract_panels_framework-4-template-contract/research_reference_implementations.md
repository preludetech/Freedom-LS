# Research: reference implementations for shipping restylable templates, JS and CSS

Question: how do existing reusable Django UI packages ship templates, components, JS and CSS that a host can restyle, and how do they declare what the host must provide?

Scope note: findings come from the doc pages fetched during this run. Where a page did not say something, that is stated as "not documented" rather than guessed. django-filter, Wagtail admin override mechanics, django-components, daisyUI and Flowbite pages were not retrievable or did not cover the point (see Gaps).

## Per-package findings

### django-tables2
- Source: https://django-tables2.readthedocs.io/en/latest/pages/custom-rendering.html
- Naming: templates live under `django_tables2/` (`table.html`, `bootstrap5.html`, `semantic.html`, responsive variants). Namespaced by package directory, not by prefix on filenames.
- Override: a setting `DJANGO_TABLES2_TEMPLATE` (global), `Meta.template_name` (per class), `template_name=` constructor arg (per instance). Full control: render the table yourself in your own template, using a shipped template as a base.
- CSS: none shipped. Docs: "For none of the templates any CSS file is added to the HTML. You are responsible for including the relevant style sheets." No Tailwind pack.
- Host contract: only the CSS. No context-processor requirement documented.
- Lesson: a setting-named template is the established idiom for "which variant" (matches the idea's base-template setting). Selection by setting is explicit, so there is no silent shadowing.

### django-crispy-forms (and crispy-tailwind)
- Source: https://django-crispy-forms.readthedocs.io/en/latest/install.html
- Since 2.0, template packs are separate PyPI packages (`crispy-bootstrap5`, `crispy-tailwind`, ...) added to `INSTALLED_APPS`. The host picks one with `CRISPY_TEMPLATE_PACK`. Custom packs follow `crispy-forms-<name>`.
- CSS/JS: "does not include static files. You must add the CSS and JS your chosen framework requires."
- Lesson: restyling is solved by a closed, named pack selected by setting, with the CSS stack a host responsibility. Not directly a model for a framework that must carry its own behaviour (Alpine).

### django-allauth (element and layout system)
- Source: https://docs.allauth.org/en/latest/common/templates.html and https://raw.githubusercontent.com/pennersr/django-allauth/main/allauth/templates/allauth/layouts/base.html
- Naming: `allauth/layouts/{base,entrance,manage}.html` for page structure; `allauth/elements/<tag>.html` (`alert`, `button`, `form`, `field`, `fields`, `h1`, `h2`, `panel`, `provider_list`, table elements) for markup. Content templates call `{% element button %}...{% slot ... %}`.
- Override: ordinary template precedence. A project `TEMPLATES["DIRS"]` entry, searched before `APP_DIRS`, with `allauth/elements/h1.html` replaces the default for every page. Elements get `attrs` and `origin` (calling template name) so an override can vary by caller.
- Page shell contract: `layouts/base.html` is a complete, plain, standalone document with no `extends`. It defines blocks `head_title`, `extra_head`, `body`, `content`, `extra_body`. The host overrides this one layout (or copies it) so that it extends the host's own base. The docs page does not list the block contract; it is only visible in the template.
- CSS: none shipped. Default templates are "intentionally plain and without any styling." Framework class names (Bootstrap `btn btn-primary`) live only in the element templates, which is the only place a host edits.
- Lesson for FLS: closest analogue to "primitives are overridable defaults, shell is a host contract". Key differences: allauth ships a plain shell as the default and the host overrides it by same-path replacement; the idea ships a minimal shell for docs and tests only and points the reference page at a setting. Same-path replacement is silent when the host's directory is earlier, but it is the documented mechanism, and allauth has no clash with a host's own un-namespaced components because everything sits under `allauth/`.

### Cotton UI (django-cotton-ui) and django-cotton conventions
- Sources: https://django-cotton.com/ui/installation, https://django-cotton.com/ui/theming, search summary of https://django-cotton.com/docs/components and https://pypi.org/project/django-cotton/
- django-cotton: components are files in `templates/cotton/`, called `<c-name>` in kebab-case; no `.cotton.html` suffix needed since v0.9.12. Cotton resolves by template loader, so a name like `button` from two apps collides by app order.
- Cotton UI naming: a `ui.` subdirectory namespace, called `<c-ui.button variant="primary">` (native `{% cotton ui.button %}`). Namespacing by subfolder instead of a filename prefix. This is the clash-avoidance precedent that matches the idea's `panel-` prefix (here `panel.` folder would be the equivalent; the project chose a filename prefix).
- Install contract: `django_cotton` must precede `django_cotton_ui` in `INSTALLED_APPS` (order matters). Alpine v3 required; the kit's `cotton-ui.min.js` loads before Alpine; Alpine plugins `@alpinejs/collapse` and `@alpinejs/focus` load before Alpine core.
- CSS delivery, two routes:
  1. Precompiled `django_cotton_ui/cotton-ui.css` linked with `{% static %}`, collectstatic in production.
  2. Custom Tailwind build: `python manage.py cotton_ui_sources` writes `cotton-ui.sources.css`, which the host imports into `app.css` after `@import "tailwindcss"`, then adds its own `@source` rules. Run as a pre-build step to keep the class list current.
- Theming: documented token set overridden in `:root` and `.dark`, not `@theme`. Tokens: `--color-accent`, `--color-accent-content`, `--color-accent-foreground`, `--color-ink-50..950`, `--radius-control`, `--radius-box`, `--color-bg`, `--surface-level`, shadow, focus-ring and border tokens. Utilities derive from them (`bg-accent`, `rounded-control`).
- Lesson for FLS: the `cotton_ui_sources` command is a near-exact precedent for the idea's Tailwind source command (generated CSS file imported by the host, run before the build). Also supports offering a precompiled stylesheet as an alternative route. The closed, documented token list with a reference block matches idea part 4. Whether the generated file also holds an `@import` of the package stylesheet is not documented for Cotton UI; that is the project's own choice (answers.md).

### django-tailwind-cli
- Source: https://django-tailwind-cli.readthedocs.io/latest/settings.html
- Generates `.django_tailwind_cli/source.css` under `BASE_DIR` containing `@import "tailwindcss";` (plus `@plugin "daisyui";` when enabled), rewriting it when content changes and saving a `.bak` of manual edits.
- Scanning: Tailwind auto-detection starts at `BASE_DIR` (CLI cwd). Installed apps outside `BASE_DIR` are not found. `TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = True` (off by default) writes an absolute-path `@source` per external app into the generated file; it points at the app's base directory (so Python files too) and is re-checked each write.
- If the host sets `TAILWIND_CLI_SRC_CSS` to its own file, the library creates it once and never overwrites it. Plain `@source` adds to auto detection; `@import "tailwindcss" source(none)` plus explicit `@source` limits it.
- System check `django_tailwind_cli.W001` if the source file sits inside `STATICFILES_DIRS`.
- Lesson: precedent for generating absolute `@source` lines per installed app, for a check on the generated file's location, and for the "host-owned file vs generated file" split. Note it scans the whole app directory, not just `templates/`.

### django-tailwind
- Source: https://django-tailwind.readthedocs.io/en/latest/installation.html (seen only in a search summary; details not verified).
- Generated `styles.css` uses a single `@source` pointing at the project root, covering HTML, Python and JS. Same lesson as above: it relies on location in the project tree, which is the exact assumption the idea removes.

### django-unfold
- Sources: https://unfoldadmin.com/docs/styles-scripts/customizing-tailwind/
- Unfold ships precompiled CSS and treats the host's CSS as an addition. Host compiles its own `styles.css` (`@import 'tailwindcss';`) with the Tailwind CLI and registers it via `UNFOLD["STYLES"] = [lambda request: static("css/styles.css")]`, loaded after Unfold's CSS so it overrides.
- Unfold 0.56+ "strongly recommends" writing plain custom CSS rather than configuring Tailwind. For 0.57+, Tailwind 4 is supported for custom styles. The Tailwind 4 page does not show how to scan Unfold's own templates, so the host only scans its own files.
- Theme values come from `UNFOLD["COLORS"]` settings (older docs).
- Lesson: avoiding the scan problem by shipping compiled CSS. This does not fit the idea because FLS panels use host role tokens and Tailwind utilities that must be generated from the host's theme; but a precompiled framework stylesheet for the Playwright tier is analogous.

### Wagtail (component API)
- Source: https://docs.wagtail.org/en/stable/extending/template_components.html
- `Component` has `template_name`, `render_html(parent_context)`, `get_context_data`, and `media` (CSS/JS). "It is your template's responsibility to output any media declarations": the host page declares where media goes, and views combine the media of all components.
- Admin views extend `wagtailadmin/base.html`, which provides `extra_js`, `extra_css`, `content` blocks. That is Wagtail's shell contract: the host extends a base that exposes named blocks.
- Wagtail admin template override mechanics were not on the fetched page. Not verified.
- Lesson: JS/CSS delivery is the host's job in the shell, with the component declaring what it needs. Comparable to the idea's documented load order for `alpine-components.js`.

### Tailwind v4 `@source` semantics
- Source: https://tailwindcss.com/docs/detecting-classes-in-source-files
- Auto-detection skips `.gitignore`d files, `node_modules`, binaries, CSS files and lockfiles. `@source "../node_modules/@acme/ui-lib"` is the documented way to scan an external library "since dependencies are usually listed in your .gitignore". Paths are relative to the stylesheet. Also `@source not`, `@import "tailwindcss" source(none)`, and `@source inline("...")` for safelisting with brace expansion.
- Complete class names are required; interpolated names such as `bg-${x}-600` are never generated.
- The fetched page does not mention `not-ignored:`; the idea's `@source not-ignored:` comes from `research_uv_sources_and_consumers.md` and was not re-verified here.

## Comparison table

| Package | Namespacing | Override mechanism | CSS delivery | Tailwind scan of package | Shell contract |
|---|---|---|---|---|---|
| django-tables2 | `django_tables2/` dir | setting, Meta, ctor arg | none, host's job | n/a | none |
| crispy-forms | separate pack packages | `CRISPY_TEMPLATE_PACK` | none, host's job | n/a (crispy-tailwind: host scans) | none |
| allauth | `allauth/layouts`, `allauth/elements` | same-path replace via `DIRS` precedence | none (plain) | n/a | `layouts/base.html` blocks |
| Cotton UI | `ui.` folder namespace, `c-ui.*` | override tokens; template precedence | precompiled static CSS or generated sources CSS | `cotton_ui_sources` command writes imported file | base links CSS, JS before Alpine |
| django-tailwind-cli | n/a | setting for src css | generates source.css | optional absolute `@source` per external app | n/a |
| Unfold | n/a | `UNFOLD["STYLES"]` | precompiled | host scans only its own files | admin base |
| Wagtail | n/a | extend `wagtailadmin/base.html` | `media` declared by component, emitted by host | n/a | `extra_js`, `extra_css`, `content` blocks |

## Testing standalone
Not documented on any page fetched. Only inferred: allauth's repo ships a Bootstrap example project (stated on the templates page). No page described a package's own standalone shell or compiled-CSS test tier. Treat as a gap; the project's one-shell-for-docs-and-tests decision (answers.md) is consistent with allauth's plain `layouts/base.html` doubling as default and test shell.

## Takeaways for this spec
1. Prefix or folder namespacing is the norm for primitives that could collide: Cotton UI uses a `ui.` folder, allauth uses an `allauth/` directory. The `panel-` prefix decision matches. Cotton resolves by loader order, so unprefixed names collide silently.
2. A generated CSS file imported by the host plus run-before-build is an established pattern (Cotton UI `cotton_ui_sources`, django-tailwind-cli generated `source.css`). Both write absolute paths resolved at write time. Neither fully matches `@source not-ignored:` (not found in fetched docs).
3. Documented, closed token list overridden in `:root` (not `@theme`) with a reference block is Cotton UI's approach; applicable to the reference theme block.
4. Shell contract is a documented set of block or id names the host provides (allauth blocks, Wagtail blocks). FLS's contract is ids and globals, which no reference package does; document it in the same prose-plus-example style, and add a check (allauth/Wagtail have none; django-tailwind-cli has a system check for its generated file).
5. Document script load order explicitly (Cotton UI: kit JS, then Alpine plugins, then Alpine core).
6. Ship a precompiled stylesheet as an optional second route only if wanted; Cotton UI offers both, but the answers.md decision is the single generated import.

## Gaps
- django-filter, django-components, daisyUI, Flowbite and Wagtail admin override pages could not be fetched or did not cover the point.
- No reference package's own standalone test setup was documented in fetched pages.
- Cotton UI's `cotton_ui_sources` internals (what it writes, how it resolves paths) were not read; only the doc description.

## URLs
- https://django-tables2.readthedocs.io/en/latest/pages/custom-rendering.html
- https://django-crispy-forms.readthedocs.io/en/latest/install.html
- https://docs.allauth.org/en/latest/common/templates.html
- https://raw.githubusercontent.com/pennersr/django-allauth/main/allauth/templates/allauth/layouts/base.html
- https://django-cotton.com/ui/installation
- https://django-cotton.com/ui/theming
- https://pypi.org/project/django-cotton/
- https://django-tailwind-cli.readthedocs.io/latest/settings.html
- https://django-tailwind.readthedocs.io/en/latest/installation.html
- https://unfoldadmin.com/docs/styles-scripts/customizing-tailwind/
- https://docs.wagtail.org/en/stable/extending/template_components.html
- https://tailwindcss.com/docs/detecting-classes-in-source-files

status: ok
