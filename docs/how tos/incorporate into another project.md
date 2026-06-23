# Incorporating FreedomLS into another project

FreedomLS is designed to be extended. You run it as a submodule inside your own Django project, wire the settings and URL conf once, and build your learner-facing features on top. This document explains *why* each piece of the wiring exists — not every setting value. For the complete, copy-pasteable `config/`, use the template repo.

---

## Start from the template repo

The fastest path is to create a new repo from the GitHub template:

```
git@github.com:preludetech/freedom-ls-concrete-template.git
```

Hit "Use this template" on GitHub to create your repo. The template copies the full working tree including the `.gitmodules` submodule pointer, which cookiecutter and plain clone-then-rename do not handle correctly. After creating the repo, clone with `--recurse-submodules` to initialise the submodule.

For a full file-tree listing and a completeness checklist for `config/`, see [`docs/how tos/template repo manifest.md`](template%20repo%20manifest.md).

---

## The submodule + editable install

FreedomLS lives inside your project as a git submodule, typically at `submodules/Freedom-LS/`. It is then installed as an editable Python package via `uv`:

```
git submodule add git@github.com:preludetech/Freedom-LS.git submodules/Freedom-LS
uv add submodules/Freedom-LS
```

**Why editable?** An editable install means Python resolves `freedom_ls.*` imports straight from the submodule directory. You get the real source on disk — no build step, no stale wheel — and `uv` pins the exact submodule commit in `uv.lock`.

**The read-only-submodule rule:** treat the submodule as read-only. Never edit files inside `submodules/Freedom-LS/`. All FLS logic, models, and migrations live there and belong to the package. If you need to extend an FLS model, create your own app with its own migration in your project. Forking FLS migrations breaks future `git submodule update` upgrades. The template repo's `.claude/settings.json` enforces this by denying Write/Edit permissions on `submodules/**`.

After first setup, initialise your Django project:

```
uv init
django-admin startproject config .
python manage.py create_site $SITE_NAME $HOST_DOMAIN --email $SUPER_EMAIL --password $SUPER_PASSWORD
```

---

## The Django Sites framework

FreedomLS uses Django's Sites framework (`django.contrib.sites`) for multi-tenancy. Each request is resolved to a `Site` object at the middleware layer, and all data is scoped to that site automatically.

**Why this matters for your settings:** do not set a hardcoded `SITE_ID`. FreedomLS uses `CurrentSiteMiddleware` (from `freedom_ls.site_aware_models.middleware`) to resolve the current site from the request host. A hardcoded `SITE_ID` overrides that resolution and breaks per-request site scoping.

---

## The `AUTH_USER_MODEL` label

FreedomLS ships its own user model. In your `settings_base.py`:

```python
AUTH_USER_MODEL = "freedom_ls_accounts.User"
```

The app label is `freedom_ls_accounts`, not `accounts`. Django namespaces installed packages by their full module path as the app label unless the app's `AppConfig` overrides it. FLS does not override, so the label is the full dotted name.

---

## The theming cascade

FreedomLS uses a three-tier theming model:

- **Tier 1 — CSS tokens:** override custom properties in `themes/<slug>/static/themes/<slug>/theme.css`. No template changes needed; every component re-renders automatically.
- **Tier 2 — Component classes:** adjust component structure via mergeable `class` attributes and Cotton slots, without forking behaviour logic.
- **Tier 3 — Template shadowing:** replace individual leaf templates by placing a file at the same relative path inside your theme's `templates/` directory. Escape hatch only.

The template repo ships a `custom` theme scaffold at `themes/custom/static/themes/custom/theme.css` with every token commented out. It renders identically to the FLS default until you uncomment and set values. To rebrand: edit that file, then run `npm run tailwind_build`.

For the full token reference, tier-2 Cotton slots, and tier-3 template shadowing details, see [`docs/how tos/theme-fls.md`](theme-fls.md).

---

## The Tailwind `@source` / `.gitignore` pitfall

Tailwind's `@source` glob honours `.gitignore`. If the FLS submodule lives under a path excluded by an ancestor `.gitignore` (such as `.venv/` or `node_modules/`), the glob silently skips its templates and you get missing utility classes at runtime — with no error, just invisible unstyled output.

The template repo's `tailwind.input.css` uses hardcoded relative paths to the submodule that keep it outside any gitignored directory. If you place your submodule somewhere non-standard, verify the `@source` paths still resolve and are not caught by a `.gitignore` rule.

The `@source` cascade order is intentional: FLS default theme tokens come first as the always-on baseline, then FLS component classes (which depend on those tokens), then your active theme's overrides — so your theme wins on every token and component class it touches.

Add these to your `.gitignore`:

```
node_modules/
static/vendor/
```

---

## The `FLS_THEME` setting

FreedomLS reads the active theme from a settings variable. In `settings_base.py`:

```python
import os
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR, configure_theme

FLS_THEME = os.environ.get("FLS_THEME", "custom")
FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]

RESOLVED_THEME_DIR = configure_theme(
    theme_slug=FLS_THEME,
    themes_dirs=FLS_THEMES_DIRS,
    templates=TEMPLATES,
    staticfiles_dirs=STATICFILES_DIRS,
)
```

`configure_theme` prepends the active theme's `templates/` directory to Django's template search path and its `static/` directory to `STATICFILES_DIRS`. An unknown theme slug raises `ImproperlyConfigured` at startup, naming the slug and the directories searched — it fails loud so misconfiguration is caught early.

Your `themes/` directory at `BASE_DIR` is searched before the FLS package directory. Placing a `themes/default/` folder there shadows the built-in FLS default.

**Deploy / CI:** `npm run tailwind_build` must run as part of your deploy pipeline. The build step regenerates `tailwind.active_theme.css` and compiles `tailwind.input.css` to `static/vendor/tailwind.output.css`. Both generated files are gitignored. Set `FLS_THEME` before running the build — setting it only at runtime will not affect the compiled CSS.

---

## Canonical `config/` reference

The template repo is the single source of truth for a correctly wired `config/`. Do not reconstruct the settings from memory or from this document — values drift. The live files in the template repo are maintained against the current FLS version.

See [`docs/how tos/template repo manifest.md`](template%20repo%20manifest.md) for:

- the full repo file tree
- a completeness checklist for `settings_base.py`, `settings_dev.py`, `settings_prod.py`, and `urls.py`
- the list of FLS-internal items that must be absent from a concrete implementation
