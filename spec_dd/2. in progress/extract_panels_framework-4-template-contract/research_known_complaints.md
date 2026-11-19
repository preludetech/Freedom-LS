# Known complaints: reusable Django UI apps with host-template and Tailwind coupling

Method: three-plus web searches (standard mode). Several search results were thin or off-target. Anything marked "unconfirmed" is not backed by a source found. Nothing here was verified against Tailwind or cotton source.

## 1. Tailwind v4 does not scan classes from installed packages

- Tailwind v4 reads `.gitignore` and skips ignored paths. Since v4.1 `node_modules` is ignored by default, but explicit `@source` rules that point inside `node_modules/` or carry file extensions no longer consult `.gitignore`. Maintainers' advice for libraries is an explicit `@source "../node_modules/my-ui-lib"`.
  - https://github.com/tailwindlabs/tailwindcss/discussions/19118
  - https://github.com/tailwindlabs/tailwindcss/issues/15452
- One issue reports a uv-created `.venv` with its own nested `.gitignore` containing `*`, and `@source` into it silently scanning nothing. Deleting that nested file made it work. Single user report, not an official answer. Also reported: an allow-list `.gitignore` (`*` then `!exceptions`) makes `@source` silently skip. Fix people adopt: deny-list `.gitignore`. (Found via the same search; see the tailwindlabs links above.)
- Django wrappers: django-tailwind's default `@source "../../../**/*.{html,py,js}"` starts at the project root and does not reach `site-packages`. django-tailwind-cli added an option emitting one `@source` per installed Django app whose path is outside `BASE_DIR` and outside known site-packages (aimed at editable sibling-repo installs). The same docs note Tailwind 4 only walks the working directory tree, so those apps are invisible unless declared. Its `list_templates` command was removed in favour of Django's `get_app_template_dirs()`.
  - https://django-tailwind-cli.readthedocs.io/latest/settings.html
  - https://django-tailwind.readthedocs.io/en/latest/existing-project.html
  - https://cur.at/ZPiLREH?m=web (blog: use Django's template loaders to configure Tailwind)
- Fixes adopted: (a) generate the `@source` line from Python by resolving the installed package path at build time (matches this spec's management command); (b) enumerate template dirs via Django rather than hard-coding `site-packages`; (c) explicit `@source` (with `not-ignored:` where the path sits under an ignored dir); (d) verify by building and grepping the output for a known class.
- Relevance: hard-coded relative `@source` paths break across environments (uv venv location, Docker where the venv is outside the project tree). Resolving at build time avoids that. The failure is silent: unstyled output, no error. A check or a "known class present in built CSS" test would catch it (suggestion, not a sourced practice).

## 2. Template override confusion and silent shadowing

- Django resolves same-named templates by loader order, then `INSTALLED_APPS` order; the first match wins with no warning. Long-standing doc tickets ask for clearer documentation that app order matters for templates.
  - https://code.djangoproject.com/ticket/20914
  - https://docs.djangoproject.com/en/6.0/howto/overriding-templates/
- Overriding only one block of a library's base template without copying the whole file is a recurring request (django-developers thread; django-apptemplates exists to extend a specific app's template via `{% extends "admin:admin/base.html" %}`). Changes outside blocks in a child template are ignored, which frustrates people who expect a free-form override.
  - https://groups.google.com/g/django-developers/c/AlMn1WweDN8/m/-kS2wOThAwAJ
  - https://github.com/jwalgran/django-apptemplates
- django-cotton: its app config auto-prepends its own loader (`django_cotton.cotton_loader.Loader`) ahead of the filesystem and app_directories loaders. I found no source documenting how two same-named components in different apps resolve; I could not confirm it. Treat as unconfirmed and test in-tree (render with the host component present and absent). Source: https://git.joshthomas.dev/mirrors/django-cotton/src/branch/main/django_cotton/apps.py
- Fixes adopted: a namespace prefix on shipped template names (e.g. `panel-button`) so a host's same-named component is never shadowed; documenting overrides as "place your file earlier in precedence"; a contract test rendering default and overridden. This supports the idea's recommended `c-panel-*` default.
- Alternative idea seen: Django-extensions style collision resolvers exist for templatetags (https://sources.debian.org/src/python-django-extensions/4.1-2/django_extensions/collision_resolvers.py), which shows collisions are a real known class of problem.

## 3. Libraries that assume the host base template and blocks

- The general complaint (from the override docs and threads above): a library's templates `{% extends "base.html" %}` and rely on specific block names; hosts must have a matching base or copy the templates. I found no specific GitHub issue to cite for allauth; unconfirmed beyond the Django docs.
- Fix pattern: make the base template name a setting with a shipped minimal default, document required blocks/ids as a contract, and add a system check that the configured template exists. This matches the idea's part 1 and part 4.

## 4. CSS fighting host themes

- No specific source found in this search. Unconfirmed. Known general practice (not sourced here): ship role-token-based classes, no raw hex or palette classes, and let the host override. The idea's invariant test already enforces this.

## 5. Alpine CSP build: registration order and duplicates

- With the CSP build, `x-data` must name a function registered via `Alpine.data()`, and registration belongs in an `alpine:init` listener. If a registering script runs after `Alpine.start()`, or outside `alpine:init`, the name does not resolve. A real report: `app.js` called `Alpine.start()` before a module that registers components had loaded.
  - https://alpinejs.dev/advanced/csp
  - https://dev.to/geanruca/fixing-alpinejs-load-order-in-devlog-istlanding-516p
  - https://docs.hyva.io/hyva-themes/writing-code/csp/alpine-csp.html
  - https://docs.hyva.io/hyva-checkout/devdocs/csp/csp-move-scripts-page-load.html
- Duplicates: Hyvä's guidance is `{once: true}` on the `alpine:init` listener to prevent duplicate registration. Last-registered silently replaces an earlier `Alpine.data` of the same name (my understanding; not confirmed by a cited source), which is the shadowing risk when a framework and a host both define `dropdownMenu`.
- Fixes adopted: documented load order (host bundle, then library JS, then `Alpine.start()`); register inside `alpine:init`; namespace component names (e.g. `panelDropdownMenu`) if the host may define the same name. The idea's part 1 already documents order; the open question is whether `dropdownMenu` clashes with the host's.

## 6. Icon sets assumed by libraries

- Nothing specific found in this search. Unconfirmed. Practice implied by the idea: a closed documented list of icon names plus a system check that renders each, so a missing icon fails loudly instead of rendering blank.

## 7. System checks: noisy or slow

- Nothing specific found. Unconfirmed. General Django guidance (my knowledge, not sourced): checks run on every `manage.py` command including `runserver` and `migrate`, so rendering 21 icons per check adds startup cost and any false positive is noise. Options: register the check with a tag (`Tags.templates` or a custom tag) so it runs only under `check --tag`/deploy, use `Warning` not `Error` for non-fatal items, and give each message an id and a hint pointing at the contract doc. Decide in the spec whether the icon check runs on every command.

## Takeaways for the spec

1. Build-time path resolution plus `not-ignored:` is the adopted pattern for Tailwind scanning; add a verification (known class in built CSS).
2. Prefixed primitive names are the established protection against silent shadowing; test the override both ways. Confirm cotton's cross-app resolution empirically.
3. Make the base template a setting with a check; document blocks and ids.
4. Namespace Alpine component names or prove no clash; register inside `alpine:init`; document order.
5. Tag or scope the system checks to keep startup cheap and messages actionable.

status: ok
