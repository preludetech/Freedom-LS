# Django Template Overrides for Pluggable Theming (Freedom LS)

Research covering how downstream projects (Bloom, FirstClass) can override _some_ FLS templates and cotton components from a single self-contained theme directory, without forking the whole tree.

---

## 1. App ordering + template loader resolution

`app_directories.Loader` walks `INSTALLED_APPS` **in order** and returns the **first** match — there is no "later wins". To make a downstream override win, the override must be discovered _before_ the FLS app's `templates/` dir.

Three workable approaches:

**(a) Theme as a Django app, listed before FLS apps.**
```python
INSTALLED_APPS = [
    "themes.bloom",          # <-- before FLS apps
    "freedom_ls.base",
    "freedom_ls.icons",
    ...
]
```
`themes/bloom/templates/cotton/button.html` then wins over `freedom_ls/base/templates/cotton/button.html`. Cheap, no code, but requires the theme to be a real `AppConfig`.

**(b) Theme dir via `TEMPLATES['DIRS']` (filesystem loader).**
The FLS settings already chain `filesystem.Loader` _before_ `app_directories.Loader`, so anything in `DIRS` wins automatically:
```python
TEMPLATES[0]["DIRS"] = [BASE_DIR / "themes" / env("FLS_THEME") / "templates"]
```
This is the cleanest "drop a folder in, point a setting at it" path and does **not** require the theme to be an installed app. It's already what FLS is half-set-up for (note the `/tmp/lms_templates` placeholder in `settings_base.py`).

**(c) Custom filesystem loader subclass.**
Useful when the theme path is dynamic (per-request, per-site). Subclass `django.template.loaders.filesystem.Loader` and override `get_dirs()` so it returns theme dirs based on whatever signal you choose. See section 2.

Sharp edge: the `cached.Loader` wrapping the chain memoises by template name, so a per-request loader must include the theme key in the cache key (or run uncached in dev).

## 2. Per-request / per-site theme switching

FLS is multi-tenant via `django.contrib.sites` + `CurrentSiteMiddleware`. Switching theme by site is feasible but Django's loader API is **not** request-aware out of the box — loaders are instantiated once per engine. The standard workaround is thread-local site state:

```python
# themes/loader.py
from django.template.loaders.filesystem import Loader
from freedom_ls.site_aware_models.middleware import get_current_site

class SiteThemeLoader(Loader):
    def get_dirs(self):
        site = get_current_site()
        theme = getattr(site, "theme_slug", None) if site else None
        if theme:
            yield settings.THEMES_DIR / theme / "templates"
```
Plug it into `OPTIONS.loaders` _before_ the cotton + app loaders. Disable `cached.Loader` for it, or key the cache by `(template_name, site_id)`.

Prior art: `django-tenants` documents a per-tenant template dir pattern via a custom loader; `django-overextends` (now `template-partials` ecosystem) and `django-apptemplates` solve adjacent ordering problems but not site-keyed selection.

For management commands, signals, and email rendering there is no `request` — `get_template()` then has no site context. Either pass the theme explicitly (`engine.from_string` after manual file lookup) or thread the site through a `RequestContext`-equivalent.

## 3. django-cotton component overrides

Cotton resolves `<c-button variant="primary">` by asking Django to load `cotton/button.html` (kebab-cased) via its own `cotton_loader.Loader`, which in turn delegates to the standard loader chain. **Override resolution is just normal Django template resolution.** Drop `themes/bloom/templates/cotton/button.html` in a higher-priority dir and it replaces the FLS version everywhere — every consumer template (`<c-button>`) picks up the override automatically.

Sharp edges to preserve when overriding `cotton/button.html`:
- Keep the same `<c-vars …>` surface so callers' attributes still bind. FLS's button declares `variant`, `type`, `href`, `form`, `id`, `name`, `value`, `disabled`, `dropdown`, `class`, `icon_left`, `icon_right`, `loading`, `loading_text`. Drop one and consumer templates silently lose behaviour.
- Forward `{{ attrs }}` (or `{{ c.attrs }}`) onto the rendered element — that's how HTMX attributes (`hx-post`, etc.) flow through.
- Preserve the default slot (`{{ slot }}`) and any named slots (e.g. `trigger`, `footer` in `cotton/modal.html`).
- `COTTON_SNAKE_CASED_NAMES = False` is set in FLS — file names must match the kebab tag (`button-group.html`, not `button_group.html`).

## 4. Block-based extension vs full override

Full override of a cotton component is a sledgehammer. For "insert, don't replace":

- **Cotton named slots** are the recommended primitive. Define `<c-header>{{ slot }}{{ logo }}{{ nav }}</c-header>` in FLS, downstream renders `<c-header><c-slot name="logo">…</c-slot></c-header>` without re-implementing the header. This already shows up in FLS's `cotton/modal.html` (`trigger`, `footer`).
- **Classic `{% block %}` inheritance** still works for page-level shells (`base.html`). Downstream `templates/base.html` does `{% extends "freedom_ls/base.html" %}` and only fills in the blocks it cares about. Pair with `app_directories` ordering so the override is discoverable.
- **Theme-provided partial includes**: FLS shells include a `{% include "theme/header_logo.html" %}` that resolves to a no-op stub by default. Downstream supplies a real one in its theme dir. Lighter than block inheritance, but harder to discover.

Recommendation: design new shared shells with explicit cotton named slots up front; use `{% block %}` only for the top-level `base.html`-style scaffolds.

## 5. Concrete drop-in theme directory feasibility

Minimum machinery for `THEMES_DIR/<name>/{templates/, static/, theme.css}` selectable by one setting:

```python
# settings.py
FLS_THEME = env("FLS_THEME", default="default")
THEMES_DIR = BASE_DIR / "themes"

TEMPLATES[0]["DIRS"] = [THEMES_DIR / FLS_THEME / "templates"]
STATICFILES_DIRS = [THEMES_DIR / FLS_THEME / "static"] + STATICFILES_DIRS
```
That's it for static-per-deploy theming. Add the custom loader from §2 only if you need _site-keyed_ switching.

Existing packages worth mining:
- **Mezzanine themes** (`mezzanine.themes`) — themes are just apps placed at the front of `INSTALLED_APPS`. Right: zero new abstractions, leans on Django's loader. Wrong: per-site switching is bolted on via middleware that mutates `INSTALLED_APPS` at runtime — fragile and incompatible with `cached.Loader`.
- **django-theme-loader** / **django-themes** (small, semi-maintained) — provide a `ThemeLoader` keyed off a setting. Right: clear separation of theme dir from app dir. Wrong: most don't account for `cached.Loader` keying or static-files parallelism.
- **Wagtail** (for inspiration, not adoption) — uses model-driven page templates and a `TEMPLATE_DIRS` per site setting; heavyweight but correct on cache keying.
- **django-pattern-library** — orthogonal but useful for previewing theme overrides.

For FLS specifically: ship a `default` theme dir alongside FLS, keep all currently-themable pieces (e.g. `cotton/button.html`, the page shell, brand colour CSS) referenced via the theme dir, and let downstream replace just the files they care about. Document the cotton `<c-vars>` surface as the public contract for any overridable component.

---

## References

- Django docs — Template loaders: <https://docs.djangoproject.com/en/6.0/ref/templates/api/#loader-types>
- Django docs — `app_directories.Loader`: <https://docs.djangoproject.com/en/6.0/ref/templates/api/#django.template.loaders.app_directories.Loader>
- Django docs — `filesystem.Loader`: <https://docs.djangoproject.com/en/6.0/ref/templates/api/#django.template.loaders.filesystem.Loader>
- Django docs — `cached.Loader`: <https://docs.djangoproject.com/en/6.0/ref/templates/api/#django.template.loaders.cached.Loader>
- Django docs — Template inheritance / `{% block %}`: <https://docs.djangoproject.com/en/6.0/ref/templates/language/#template-inheritance>
- Django docs — Sites framework: <https://docs.djangoproject.com/en/6.0/ref/contrib/sites/>
- django-cotton docs — Components, slots, `c-vars`, `attrs`: <https://django-cotton.com/docs/components>
- django-cotton docs — Naming + `COTTON_SNAKE_CASED_NAMES`: <https://django-cotton.com/docs/configuration>
- django-cotton source (`cotton_loader.Loader`): <https://github.com/wrabit/django-cotton/blob/main/django_cotton/cotton_loader.py>
- Mezzanine themes: <https://github.com/stephenmcd/mezzanine/wiki/Themes>
- django-tenants — multi-tenant template dirs: <https://django-tenants.readthedocs.io/en/latest/templates.html>
- django-apptemplates (override-by-app prior art): <https://pypi.org/project/django-apptemplates/>
- django-pattern-library: <https://torchbox.github.io/django-pattern-library/>
