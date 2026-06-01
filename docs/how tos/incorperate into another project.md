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
    "c-callout": {"level", "title"},
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

copy `package-lock.json` and `package.json` and `tailwind.input.css` into your own project root.

run `npm i`

Add this to your gitignore:

```
node_modules/
static/vendor/
```

Run `npm run tailwind_watch`

You can now edit `tailwind.input.css` to make it do what you want.

#### Deploy / CI note

`npm run tailwind_build` must run as part of your deploy pipeline (CI step, image build, or predeploy hook) — not just locally. It generates `tailwind.active_theme.css` at the project root and compiles `static/vendor/tailwind.output.css`; both are gitignored, so nothing useful ships from git alone.

The `FLS_THEME` env var (default `default`) selects which theme's tokens are baked into the bundle and is read at **build time** by `scripts/write-active-theme.mjs`. Set it before you run `tailwind_build` — setting it only at runtime will not affect the compiled CSS. Node and npm must be available in the build environment.


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
