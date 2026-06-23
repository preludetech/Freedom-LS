# Template Repo Manifest

The concrete-implementation template lives at:

```
git@github.com:preludetech/freedom-ls-concrete-template.git
```

It is a [GitHub Template Repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template). Use the "Use this template" button on GitHub to create a new repo from it. The template mechanism copies the full working tree including the `submodules/Freedom-LS` entry from `.gitmodules`, so the FLS submodule pointer is preserved. After creating a new repo from the template, clone with `--recurse-submodules` to initialise the submodule.

**Why "Use this template" rather than clone-and-script or cookiecutter?** The submodule pointer needs to survive the copy. GitHub's template mechanism handles this correctly; cookiecutter and bare clone-then-rename do not — they either drop the submodule metadata or require a post-creation init script that is easy to forget.

For a conceptual wiring overview — how the submodule integrates with your project's settings, URL conf, and dependencies — see `docs/how tos/incorporate into another project.md` (currently on disk as `incorperate into another project.md`; the filename will be corrected in a later update).

---

## Thin-template / never-fork-migrations principle

The template is intentionally thin. It provides the wiring — settings, URL conf, theme scaffold, tooling config — and nothing else. All business logic, models, views, and migrations live either in the FLS submodule (read-only) or in apps you add to your own project.

**Never copy FLS migrations into your project.** Migrations belong to the package that owns the model. If you need to extend an FLS model, create your own app with its own migration. Forking FLS migrations breaks future submodule updates.

---

## Repo file tree

The tree below reflects the template as shipped. Read it as a reference for what a healthy concrete implementation should contain — not as a substitute for inspecting the actual files.

```
.claude/
    settings.json          # Denies Write/Edit on submodules/**
.github/
    dependabot.yml         # Weekly updates: gitsubmodule, pip, npm
CLAUDE.md                  # Project-level Claude Code instructions
README.md                  # Getting-started guide for new implementors
claude.sh                  # Wrapper: launches Claude with the FLS plugin loaded
config/
    __init__.py
    asgi.py
    settings_base.py       # Full FLS-wired base settings (see contract below)
    settings_dev.py        # Dev overrides (no qa_helpers, no branch-to-db logic)
    settings_prod.py       # Production overrides
    urls.py                # FLS URL includes (no qa_helpers.urls)
    wsgi.py
manage.py
package.json               # Tailwind CLI + icon-set dependencies; tailwind_build script
pyproject.toml             # Python deps (freedom_ls from submodule); uv.sources wiring
submodules/
    Freedom-LS/            # Git submodule pinned to FLS main
tailwind.input.css         # @source globs + theme imports (hardcoded Node paths)
themes/
    custom/
        static/
            themes/
                custom/
                    theme.css   # Tier-1 token placeholders for the "custom" theme
uv.lock
```

Additionally, after first setup: `templates/` (empty, for Tier-3 template overrides), `static/` (for project static assets), and `logs/` are created locally but are not tracked in git.

---

## `config/` content contract

This is a completeness checklist for keeping a concrete implementation's `config/` aligned with the FLS wiring. The **live FLS `config/` at `config/` in this repo is the authority**. The lists below are a quick reference — they will drift if FLS evolves and this document is not updated. Always check the real files.

### `settings_base.py`

**`INSTALLED_APPS` must contain all FLS apps, in this order:**

- [ ] `whitenoise.runserver_nostatic`
- [ ] `django_cotton.apps.SimpleAppConfig`
- [ ] `django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`, `django.contrib.messages`, `django.contrib.staticfiles`, `django.contrib.sites`, `django.contrib.postgres`, `django.tasks`
- [ ] `unfold` (before `django.contrib.admin`) and all `unfold.contrib.*` entries
- [ ] `django.contrib.admin` (after unfold)
- [ ] `guardian`
- [ ] All FLS apps: `freedom_ls.base`, `freedom_ls.icons`, `freedom_ls.markdown_rendering`, `freedom_ls.content_engine`, `freedom_ls.accounts`, `freedom_ls.student_management`, `freedom_ls.student_progress`, `freedom_ls.site_aware_models`, `freedom_ls.panel_framework`, `freedom_ls.educator_interface`, `freedom_ls.role_based_permissions`, `freedom_ls.student_interface`
- [ ] `encrypted_fields`, `django_ace`, `freedom_ls.webhooks`, `allauth`, `allauth.account`, `axes`

**`MIDDLEWARE` must contain, in order:**

- [ ] `SecurityMiddleware`, `ContentSecurityPolicyMiddleware`
- [ ] `WhiteNoiseMiddleware`
- [ ] `SessionMiddleware`, `CommonMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`
- [ ] `freedom_ls.base.middleware.HtmxMessagesMiddleware`
- [ ] `XFrameOptionsMiddleware`
- [ ] `freedom_ls.site_aware_models.middleware.CurrentSiteMiddleware`
- [ ] `allauth.account.middleware.AccountMiddleware`
- [ ] `freedom_ls.accounts.middleware.RegistrationCompletionMiddleware`
- [ ] `axes.middleware.AxesMiddleware`

**`AUTHENTICATION_BACKENDS` must include:**

- [ ] `axes.backends.AxesStandaloneBackend`
- [ ] `django.contrib.auth.backends.ModelBackend`
- [ ] `guardian.backends.ObjectPermissionBackend`
- [ ] `allauth.account.auth_backends.AuthenticationBackend`

**Required settings:**

- [ ] `AUTH_USER_MODEL = "freedom_ls_accounts.User"` — the app label is `freedom_ls_accounts`, not `accounts`
- [ ] `ROOT_URLCONF = "config.urls"`
- [ ] `FLS_THEME` — read from `os.environ.get("FLS_THEME", "custom")`. The template defaults to `"custom"` (see theme section below); the FLS repo itself defaults to `"default"`. The slug must resolve in `FLS_THEMES_DIRS` at startup.
- [ ] `FLS_THEMES_DIRS` — `[BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]`
- [ ] `RESOLVED_THEME_DIR = configure_theme(theme_slug=FLS_THEME, themes_dirs=FLS_THEMES_DIRS, templates=TEMPLATES, staticfiles_dirs=STATICFILES_DIRS)`
- [ ] `FREEDOM_LS_ICON_SET = "heroicons"`
- [ ] `STATICFILES_DIRS` includes `BASE_DIR / "static"`
- [ ] `MARKDOWN_ALLOWED_TAGS` — full dict of cotton component tags; check the live file for the complete set
- [ ] `MARKDOWN_TEMPLATE_RENDER_ON = True`, `COTTON_SNAKE_CASED_NAMES = False`
- [ ] `WEBHOOK_EVENT_TYPES = FLS_WEBHOOK_EVENT_TYPES`
- [ ] `SECURE_CSP_REPORT_ONLY` dict
- [ ] `TASKS` dict (base uses `ImmediateBackend`)
- [ ] `SALT_KEY` (derived from `WEBHOOK_ENCRYPTION_SALT` env var; dev fallback is deterministic but insecure)
- [ ] AllAuth block: `ACCOUNT_LOGIN_METHODS = {"email"}`, `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`, `ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"`, `ACCOUNT_FORMS = {"signup": "freedom_ls.accounts.forms.SiteAwareSignupForm"}`, `ACCOUNT_PREVENT_ENUMERATION = True`
- [ ] `AXES_FAILURE_LIMIT`, `AXES_COOLOFF_TIME`, `AXES_LOCKOUT_PARAMETERS`, `AXES_RESET_ON_SUCCESS`
- [ ] `TRUSTED_PROXY_IP_HEADER: str | None = None`
- [ ] `LEGAL_DOCS_MANIFEST_PATH: str | None = None`
- [ ] Branding stubs (all `None` by default): `HEADER_LOGO_STATIC_PATH`, `FAVICON_STATIC_PATH`, `HEADER_TITLE`, `HEADER_TITLE_STYLE`, `EMAIL_LOGO_STATIC_PATH`

**Template loader chain (required order):**

```python
"loaders": [
    ("django.template.loaders.cached.Loader", [
        "django_cotton.cotton_loader.Loader",
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ])
]
```

**Context processors (required):**

- [ ] `django.template.context_processors.request`
- [ ] `django.contrib.auth.context_processors.auth`
- [ ] `django.contrib.messages.context_processors.messages`
- [ ] `freedom_ls.site_aware_models.context_processors.site_config`
- [ ] `freedom_ls.accounts.context_processors.signup_policy`
- [ ] `django.template.context_processors.csp`

**Template builtins:**

- [ ] `django_cotton.templatetags.cotton`

### `settings_dev.py`

Items a concrete dev config should contain — see the exclusions table below for FLS-internal dev items that must NOT carry over.

- [ ] Extends `settings_base` via `from .settings_base import *`
- [ ] `DEBUG = True`
- [ ] `ACCOUNT_RATE_LIMITS = False`
- [ ] `AUTH_PASSWORD_VALIDATORS = []`
- [ ] Dev `DATABASES` block (PostgreSQL, env-var driven with sensible dev defaults)
- [ ] `django_browser_reload` in `INSTALLED_APPS` (for live reload)
- [ ] `debug_toolbar` added to `INSTALLED_APPS` when not running tests

### `settings_prod.py`

- [ ] Extends `settings_base` via `from .settings_base import *`
- [ ] `SECRET_KEY = os.getenv("SECRET_KEY", "")`
- [ ] `HOST_DOMAIN = os.environ["HOST_DOMAIN"]` (hard failure if missing)
- [ ] `SECURE_SSL_REDIRECT = True`
- [ ] HSTS settings (`SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`)
- [ ] Secure cookies: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, etc.
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`
- [ ] `X_FRAME_OPTIONS = "DENY"` (overrides the `SAMEORIGIN` base)
- [ ] `STATIC_ROOT` set for whitenoise collection
- [ ] S3 media storage block (conditional on `AWS_STORAGE_BUCKET_NAME`)
- [ ] `STORAGES` dict: whitenoise for staticfiles, S3 or filesystem for default
- [ ] Email settings (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, etc.) from env vars
- [ ] `ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"`
- [ ] Logging configuration (console + rotating file handlers for `django`, `django.request`, `django.security`, `freedom_ls`)

### `urls.py`

- [ ] `ADMIN_URL` read from `os.environ.get("DJANGO_ADMIN_URL", "admin/")`
- [ ] `path("health/", health_check, name="health_check")` — comes first, before admin
- [ ] `path(ADMIN_URL, admin.site.urls)`
- [ ] `path("educator/", include("freedom_ls.educator_interface.urls"))`
- [ ] `path("accounts/", include("allauth.urls"))`
- [ ] `path("accounts/", include("freedom_ls.accounts.urls"))`
- [ ] `path("", include("freedom_ls.student_interface.urls"))`
- [ ] Debug block adds `django_browser_reload` and `debug_toolbar_urls()` — but **not** `freedom_ls.qa_helpers.urls`

---

## What must be absent from a concrete implementation

These items exist in the FLS repo's own dev config for internal development and testing. They must **not** appear in a concrete implementation's settings or URLs.

| Item | Where it lives in FLS | Why it must be absent |
|---|---|---|
| `freedom_ls.qa_helpers` | `INSTALLED_APPS` in `settings_dev.py` | FLS-internal QA tooling; not for production projects |
| `freedom_ls.qa_helpers.urls` | `urls.py` DEBUG block | Same; exposes internal test routes |
| `freedom_ls.base.context_processors.debug_branch_info` | `settings_dev.py` context processors | FLS worktree tooling; irrelevant in concrete projects |
| Branch-to-db-name logic (`branch_to_db_name`, `get_current_branch`) | `settings_dev.py` `DATABASES` block | FLS multi-worktree dev setup; concrete projects use a single named database |
| `SESSION_COOKIE_NAME = f"sessionid_{_db_name}"` | `settings_dev.py` | Companion to the branch-to-db logic above |
| `FORCE_SITE_NAME = "DemoDev"` | `settings_dev.py` | Hardcodes the FLS internal demo site; concrete projects set up their own sites |
| `FREEDOMLS_PERMISSIONS_MODULES` | `settings_dev.py` | FLS-internal permission module wiring for DemoDev; concrete projects configure their own |
| `HEADER_LOGO_STATIC_PATH = "images/first_class_logo.png"` etc. | `settings_dev.py` | FirstClass demo branding; concrete projects supply their own assets |
| `ADMONITION_TYPES` override adding `"regulation"` | `settings_dev.py` | FLS demo-content-specific admonition type; omit unless your content uses it |
| `REQUIRE_TERMS_ACCEPTANCE = True` | `settings_dev.py` | DemoDev policy override (base default is `False`); set explicitly in your own config |
| `HEADLESS_SERVE_SPECIFICATION = True` | `settings_dev.py` | FLS dev-only; exposes the allauth OpenAPI spec in dev |

---

## Theme: the `custom` placeholder and rebrand workflow

`FLS_THEME` defaults to `"custom"` in the template (the FLS repo itself defaults to `"default"`). The `custom` theme lives at:

```
themes/custom/static/themes/custom/theme.css
```

The file ships with every token commented out, so it renders identically to the FLS default theme until you override tokens. To rebrand:

1. Uncomment and set the token values you want to change in `themes/custom/static/themes/custom/theme.css`.
2. Rebuild: `npm run tailwind_build`.

No Django restart is needed — theme tokens are compiled into the CSS bundle at build time.

For the full token reference, tier-2 component class overrides, tier-3 template shadowing, and build pitfalls, see `docs/how tos/theme-fls.md`.

To switch to a different built-in FLS theme (e.g. `"default"`, `"first_class"`):

1. Set `FLS_THEME=<slug>` in your environment.
2. Update the active-theme `@import` in `tailwind.input.css` to point at that theme's `theme.css`.
3. Run `npm run tailwind_build`.

---

## Keeping the template in sync

When the FLS `config/` evolves — new middleware, new required settings, new URL includes — update both the template repo's `config/` files and this document's checklist. The checklist is only as good as the last time someone checked it against the live FLS files.

The authoritative source for each setting's purpose and default value is always the live FLS `config/` in this repo. When in doubt, read the source.
