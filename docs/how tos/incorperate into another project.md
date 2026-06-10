# How to use this in another project

This Learning System is designed to be extended and overwritten.  You can run it as a standalone project and it will work, but the real power is that you can build your own student interfaces on top of it.

## Set up

```
uv init
```


```
git submodule add git@github.com:preludetech/Freedom-LS.git submodules/Freedom-LS
```

```
uv add submodules/Freedom-LS
```

```
django-admin startproject config .
```

Set up a suitable .gitignore


### Useful dependencies

```
uv add --dev django-debug-toolbar
uv add --dev django-browser-reload.
ipython
```

###

python manage.py create_site $SITE_NAME $HOST_DOMAIN --email $SUPER_EMAIL --password $SUPER_PASSWORD



### urls.py

TODO



### settings.py

TODO:

INSTALLED_APPS
make sure to add contrib.sites

MIDDLEWARE
TEMPLATES

STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files (User uploaded files)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)


MARKDOWN_ALLOWED_TAGS = {
    "c-youtube": {"video_id", "video_title"},
    "c-picture": {"src", "alt", "caption"},
    "c-admonition": {"type", "title"},
    "c-flashcard": set(),
    "c-accordion": {"title", "open"},
    "c-slot": {"name"},
    "c-content-link": {"path"},
}

MARKDOWN_TEMPLATE_RENDER_ON = True
COTTON_SNAKE_CASED_NAMES = False

HEADLESS_CLIENTS = ("app",)
ACCOUNT_SIGNUP_FIELDS = ["email*", "email2*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_ADAPTER = "accounts.allauth_account_adapter.AccountAdapter"

### Tailwind set up

Copy `package-lock.json` and `package.json` into your own project root, then create a `tailwind.input.css` file at the project root using the template below. Replace `<path-to-freedom_ls>` with the actual path to the FLS package relative to your project root (e.g. `./submodules/Freedom-LS/freedom_ls` if you added FLS as a submodule under `submodules/`), and replace `<theme_slug>` with the slug of your active theme (use `default` to start):

```css
@import "tailwindcss";

@source "<path-to-freedom_ls>/**/templates/**/*.html";
@source "./themes/<theme_slug>/templates/**/*.html";

@import "<path-to-freedom_ls>/themes/default/static/themes/default/theme.css";
@import "<path-to-freedom_ls>/tailwind.components.css";
@import "./themes/<theme_slug>/static/themes/<theme_slug>/theme.css";

@theme { /* downstream project-level overrides, optional */ }
```

The cascade order is intentional: the default theme's tokens come first as the always-on baseline, then FLS component classes (which depend on those tokens), then your active theme's overrides — so your theme wins on every token and component class it touches.

Run `npm i` to install dependencies, then `npm run tailwind_build` to compile.

Add this to your `.gitignore`:

```
node_modules/
static/vendor/
```

> **`@source` and `.gitignore`:** Tailwind's `@source` glob honours `.gitignore`. If FLS lives under a path excluded by an ancestor `.gitignore` (such as `.venv/` or `node_modules/`), the glob silently skips its templates and you will get missing utility classes at runtime. See `docs/how tos/theme-fls.md` for the symlink or copy workaround.

#### FLS_THEME setting

FreedomLS reads the active theme from an environment variable. In your `settings.py`, add:

```python
import os
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR, configure_theme

FLS_THEME = os.environ.get("FLS_THEME", "default")
FLS_THEMES_DIRS = [BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]

RESOLVED_THEME_DIR = configure_theme(
    theme_slug=FLS_THEME,
    themes_dirs=FLS_THEMES_DIRS,
    templates=TEMPLATES,
    staticfiles_dirs=STATICFILES_DIRS,
)
```

`configure_theme` prepends the active theme's `templates/` directory (if it has one) to Django's template search path and its `static/` directory to `STATICFILES_DIRS`. An unknown theme slug raises `ImproperlyConfigured` at startup naming the slug and the directories searched — it fails loud so misconfiguration is caught early.

For the default theme, set `FLS_THEME=default` (or omit the env var — `"default"` is the fallback). Your project's `themes/` directory at `BASE_DIR` is searched before the FLS package directory, so placing a `themes/default/` folder there shadows the built-in default.

For theming beyond the default, see `docs/how tos/theme-fls.md`.

#### Deploy / CI note

`npm run tailwind_build` must run as part of your deploy pipeline (CI step, image build, or predeploy hook) — not just locally. The build step first runs `manage.py write_active_theme_css` (which regenerates `tailwind.active_theme.css` as a one-line `@import` pointing at the resolved active theme), then compiles `tailwind.input.css` to `static/vendor/tailwind.output.css`. Both generated files are gitignored, so nothing useful ships from git alone.

Set `FLS_THEME` before running `tailwind_build` — setting it only at runtime will not affect the compiled CSS. Node and npm must be available in the build environment.


### Conftest:
copy it across

### playwright

run playwright install

## Dev dependencies
install manually

## Theming course cards

FreedomLS renders courses in two shapes: a tall **card** (used on the dashboard) and a
compact **row** (used on the all-courses list). Both shapes are driven by the same
three-tier override ladder. Work at the cheapest tier that meets your needs and only
drop to the next tier when you must.

### Tier 1 — Theme tokens (cheapest)

Override CSS custom properties in your theme's `theme.css`. No template changes are
needed; every card and row re-renders automatically.

**Colour** — the course-card accent palette is a five-slot gradient series defined in
`freedom_ls/themes/default/static/themes/default/theme.css`. Rebrand card hero tiles
and progress bars by overriding the `-from`, `-to`, and `-icon` stops for any slot:

```css
/* In your theme's theme.css */
@theme {
    --fls-course-accent-1-from: #your-colour;
    --fls-course-accent-1-to:   #your-colour;
    --fls-course-accent-1-icon: #ffffff;   /* hero glyph foreground */
}
```

**Shape** — card radius, hero-band height, and body padding are controlled by three
tokens (also in `freedom_ls/themes/default/static/themes/default/theme.css`):

```css
@theme {
    --fls-card-radius:      1rem;   /* card/row corner radius */
    --fls-card-hero-height: 7rem;   /* tall-card hero band height */
    --fls-card-padding:     1rem;   /* card/row body padding */
}
```

The component classes that consume these tokens (`.course-card`, `.course-card-hero`,
`.course-card-body`) are defined in `tailwind.components.css`. Overriding the tokens
in your `theme.css` is enough — do not edit those classes directly.

### Tier 2 — Cotton slots, vars, and mergeable `class`

Both shells expose named slots (`eyebrow`, `footer`, default slot) and a mergeable
`class` attribute. Use these to recompose card or row content and layout without forking
any behaviour logic.

The shells are:

- `freedom_ls/student_interface/templates/cotton/course-card-shell.html` — the tall
  dashboard card.
- `freedom_ls/student_interface/templates/cotton/course-row-shell.html` — the compact
  all-courses row.

Typical use: supply a custom `eyebrow` slot to show a course category badge, or pass
extra Tailwind classes via `class` to adjust spacing for a specific layout:

```html
<c-course-card-shell accent_slot_key="1" icon="…" title="…" class="border-2 border-primary">
    <c-slot name="eyebrow">
        <span class="text-xs text-muted uppercase tracking-wide">Design</span>
    </c-slot>
    {{ slot }}  {# the default leaf content renders here #}
</c-course-card-shell>
```

### Tier 3 — Whole-file template shadowing (last resort)

If neither tokens nor slots are enough, replace an individual leaf template by placing
a file at the same relative path inside your project's theme template directory. Django's
template loader order resolves your file before the FLS default.

The leaf partials — one file per status, per shape — are:

**Card leaves** (dashboard):
- `freedom_ls/student_interface/templates/student_interface/partials/course_card_registered.html`
- `freedom_ls/student_interface/templates/student_interface/partials/course_card_not_registered.html`
- `freedom_ls/student_interface/templates/student_interface/partials/course_card_complete.html`

**Row leaves** (all-courses list):
- `freedom_ls/student_interface/templates/student_interface/partials/course_row_registered.html`
- `freedom_ls/student_interface/templates/student_interface/partials/course_row_not_registered.html`
- `freedom_ls/student_interface/templates/student_interface/partials/course_row_complete.html`

The `@source` glob in `tailwind.input.css` already covers
`freedom_ls/themes/*/templates/**/*.html`, so any Tailwind classes you use in a
theme-level shadow template will be included in the compiled bundle — as long as you
run `npm run tailwind_build` after adding the file.
