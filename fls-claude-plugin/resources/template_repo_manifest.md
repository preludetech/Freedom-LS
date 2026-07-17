# Template Repo Manifest

The concrete-implementation template lives at:

```
git@github.com:preludetech/freedom-ls-concrete-template.git
```

It is a [GitHub Template Repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template). Use the "Use this template" button on GitHub to create a new repo from it. The template mechanism copies the full working tree including the `submodules/Freedom-LS` entry from `.gitmodules`, so the FLS submodule pointer is preserved. After creating a new repo from the template, clone with `--recurse-submodules` to initialise the submodule.

**Why "Use this template" rather than clone-and-script or cookiecutter?** The submodule pointer needs to survive the copy. GitHub's template mechanism handles this correctly; cookiecutter and bare clone-then-rename do not — they either drop the submodule metadata or require a post-creation init script that is easy to forget.

For a conceptual wiring overview — how the submodule integrates with your project's settings, URL conf, and dependencies — see [`docs/how tos/incorporate into another project.md`](../../docs/how%20tos/incorporate%20into%20another%20project.md).

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
.gitmodules                # Declares the submodules/Freedom-LS submodule
CLAUDE.md                  # Project-level Claude Code instructions
README.md                  # Getting-started guide for new implementors
claude.sh                  # Wrapper: launches Claude with the FLS plugin loaded
apps/
    project_setup/         # Scaffold's own first-run bootstrap app (not an FLS app)
        management/commands/
            setup_initial_data.py   # Creates the initial Site + admin user
config/
    __init__.py
    asgi.py
    customisation.py       # Edit-first knobs: theme, icons, branding, admonitions, signup, roles
    role_based_permissions/
        example.py         # Ready-to-edit example role module (unwired by default)
    settings_base.py       # Full FLS-wired base settings; splat-imports customisation (see contract)
    settings_dev.py        # Dev overrides: no qa_helpers; branch-aware multi-worktree dev setup
    settings_prod.py       # Production overrides
    urls.py                # FLS URL includes (no qa_helpers.urls)
    wsgi.py
dev_db/                    # Local dev stack: PostgreSQL + Mailpit (docker compose) + helper scripts
    docker-compose.yaml
    docker-entrypoint-initdb.d/create-test-db.sql
manage.py
package.json               # Tailwind CLI + icon-set dependencies; tailwind_build script
package-lock.json          # npm lockfile (refresh with `npm i`, don't hand-edit)
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

Additionally, after first setup: `templates/` (for Tier-3 template overrides, ships a `.gitkeep`), `static/` (for project static assets; `static/vendor/` holds the built `tailwind.output.css`, which is gitignored), and `logs/` exist locally. The machine-specific `.claude/fls/config.local.md` is also created locally and gitignored.

---

## `config/` content contract

This is a completeness checklist for keeping a concrete implementation's `config/` aligned with the FLS wiring. The **live FLS `config/` at `config/` in this repo is the authority** for the canonical app list, middleware, and required setting keys/defaults. The template, however, *organises* the most commonly edited learner-facing knobs into a dedicated `config/customisation.py` (which `settings_base.py` splat-imports) — so check both that file and `settings_base.py`. The lists below are a quick reference — they will drift if FLS evolves and this document is not updated. Always check the real files.

### `settings_base.py`

The template's `settings_base.py` begins with `from .customisation import *` (see the [`customisation.py`](#configcustomisationpy) subsection below), so the theme, icon, branding, admonition, signup, and role settings documented there land in Django settings without being repeated here.

**`INSTALLED_APPS` must contain all FLS apps, in this order:**

- [ ] `whitenoise.runserver_nostatic`
- [ ] `django_cotton.apps.SimpleAppConfig`
- [ ] `django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`, `django.contrib.messages`, `django.contrib.staticfiles`, `django.contrib.sites`, `django.contrib.postgres`, `django.tasks`
- [ ] `unfold` (before `django.contrib.admin`) and all `unfold.contrib.*` entries
- [ ] `django.contrib.admin` (after unfold)
- [ ] `guardian`
- [ ] All FLS apps: `freedom_ls.base`, `freedom_ls.icons`, `freedom_ls.markdown_rendering`, `freedom_ls.content_engine`, `freedom_ls.accounts`, `freedom_ls.student_management`, `freedom_ls.student_progress`, `freedom_ls.site_aware_models`, `freedom_ls.panel_framework`, `freedom_ls.educator_interface`, `freedom_ls.role_based_permissions`, `freedom_ls.student_interface`
- [ ] `encrypted_fields`, `django_ace`, `freedom_ls.webhooks`, `allauth`, `allauth.account`, `axes`
- [ ] `apps.project_setup` — the scaffold's own bootstrap app (not an FLS app; see [first-run bootstrap](#appsproject_setup--first-run-bootstrap) below)

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
- [ ] `FLS_THEME` — defined in `customisation.py` as `os.environ.get("FLS_THEME", "custom")`. The template defaults to `"custom"` (see theme section below); the FLS repo itself defaults to `"default"`. The slug must resolve in `FLS_THEMES_DIRS` at startup.
- [ ] `FLS_THEMES_DIRS` — `[BASE_DIR / "themes", FREEDOM_LS_PACKAGE_DIR / "themes"]`
- [ ] `RESOLVED_THEME_DIR = configure_theme(theme_slug=FLS_THEME, themes_dirs=FLS_THEMES_DIRS, templates=TEMPLATES, staticfiles_dirs=STATICFILES_DIRS)`
- [ ] `FREEDOM_LS_ICON_SET = "heroicons"` — defined in `customisation.py`
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
- [ ] Branding stubs, admonitions, signup, and the role mapping live in `customisation.py` — see the [`customisation.py`](#configcustomisationpy) subsection below

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

### `config/customisation.py`

The "edit-first" file — the knobs new projects most commonly change, grouped in one place. `settings_base.py` splat-imports it (`from .customisation import *`), so each setting here lands in Django settings. Everything not exposed here keeps its FLS default. Items:

- [ ] **Theme** — `FLS_THEME = os.environ.get("FLS_THEME", "custom")` (see the theme section below)
- [ ] **Icons** — `FREEDOM_LS_ICON_SET = "heroicons"`; `FREEDOM_LS_ICON_OVERRIDES: dict[str, str] = {}` (per-icon semantic-name swaps)
- [ ] **Branding** (all `None` by default) — `HEADER_LOGO_STATIC_PATH`, `FAVICON_STATIC_PATH`, `HEADER_TITLE`, `HEADER_TITLE_STYLE`, `EMAIL_LOGO_STATIC_PATH`
- [ ] **Admonitions** — `ADMONITION_TYPES` dict (`note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`, plus the required `default` fallback), followed by a commented `**ADMONITION_TYPES, ...` example showing how a project adds its own type. Each entry maps to `{label, icon, color}` with an optional `icon_fallback`.
- [ ] **Signup** — `ALLOW_SIGN_UPS = True`, `REQUIRE_NAME = True`, `REQUIRE_TERMS_ACCEPTANCE = False` (a per-site `SiteSignupPolicy` row overrides these)
- [ ] **Roles** — `FREEDOMLS_PERMISSIONS_MODULES: dict[str, str] = {}`, a placeholder mapping `Site.name → dotted module path`. Empty is a safe default (FLS falls back to the base roles in `freedom_ls.role_based_permissions.roles`). A ready-to-edit example ships at `config/role_based_permissions/example.py`, with a commented snippet showing how to wire it (`{"Local": "config.role_based_permissions.example"}`). **Do not** copy FLS's own `config/role_based_permissions/demodev.py` or its DemoDev mapping into the scaffold.

### `settings_dev.py`

Items a concrete dev config should contain — see the exclusions table below for FLS-internal dev items (e.g. `qa_helpers`) that must NOT carry over.

- [ ] Extends `settings_base` via `from .settings_base import *`
- [ ] `DEBUG = True`
- [ ] `ACCOUNT_RATE_LIMITS = False`
- [ ] `AUTH_PASSWORD_VALIDATORS = []`
- [ ] `HEADLESS_SERVE_SPECIFICATION = True` (exposes the allauth OpenAPI spec in dev)
- [ ] `django_browser_reload` in `INSTALLED_APPS` (for live reload)
- [ ] `debug_toolbar` added to `INSTALLED_APPS` when not running tests
- [ ] Mailpit email backend — SMTP to `localhost:1025` (the `dev_db/` Docker stack runs Mailpit; inbox at `localhost:8025`)

**Branch-aware multi-worktree dev setup** (see [Multi-worktree dev setup](#multi-worktree-dev-setup) below). Unlike the FLS-internal exclusions, this is *intentionally present* in the template:

- [ ] `from freedom_ls.base.git_utils import branch_to_db_name, get_current_branch`
- [ ] `_branch = get_current_branch(base_dir=BASE_DIR)`; `_db_name = branch_to_db_name(_branch) if _branch else "db"`
- [ ] Dev `DATABASES` block (PostgreSQL, env-var driven) whose `NAME` defaults to `_db_name` and `TEST.NAME` to `f"test_{_db_name}"`
- [ ] `SESSION_COOKIE_NAME = f"sessionid_{_db_name}"` — per-worktree session isolation
- [ ] Appends `freedom_ls.base.context_processors.debug_branch_info` to the `TEMPLATES` context processors — renders the dev branch banner

### `settings_prod.py`

- [ ] Extends `settings_base` via `from .settings_base import *`
- [ ] `SECRET_KEY = fls_defaults.require_secret_key()` — hard-fails at import if `SECRET_KEY` is missing/empty rather than silently disabling session/CSRF signing
- [ ] `HOST_DOMAIN = os.environ["HOST_DOMAIN"]` (hard failure if missing)
- [ ] `SECURE_SSL_REDIRECT = True`
- [ ] `SECURE_PROXY_SSL_HEADER = fls_defaults.SECURE_PROXY_SSL_HEADER`
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

## `apps/project_setup` — first-run bootstrap

The template ships its own small app at `apps/project_setup` (registered in `INSTALLED_APPS`). Its `setup_initial_data` management command bootstraps a fresh checkout: it creates the initial `Site` (name `"Local"`, domain `127.0.0.1:8000`) and a verified admin superuser, idempotently. It is the scaffold's own app — **not** an FLS app — and replaces the FLS-internal `FORCE_SITE_NAME = "DemoDev"` approach: concrete projects create and name their own site here rather than forcing FLS's demo site.

The `"Local"` site name is the default key referenced by the `FREEDOMLS_PERMISSIONS_MODULES` placeholder in `customisation.py`; keep the two in sync if you rename the site.

---

## Multi-worktree dev setup

The template's dev config supports running several git worktrees/branches side by side on one host. This is a deliberate flip from the old single-database assumption: each branch gets its **own** database and its **own** session cookie so concurrent dev servers don't collide.

- The branch→db-name mapping comes from `freedom_ls.base.git_utils` (`get_current_branch`, `branch_to_db_name`); `settings_dev.py` uses it for `DATABASES["default"]["NAME"]`/`TEST.NAME` and for `SESSION_COOKIE_NAME`.
- The `dev_db/` directory holds the matching local stack — a `docker-compose.yaml` running PostgreSQL (port `6543`) and Mailpit, plus an init script and helper scripts. The shell side mirrors the same branch→db logic so Django connects to the database the scripts create.
- `debug_branch_info` (appended to the dev context processors) renders a coloured banner naming the current branch, so it's obvious which worktree a running server belongs to. The processor self-guards on `DEBUG`.

These items were previously listed as "must be absent" (FLS worktree tooling); they are now part of the template's own dev contract.

---

## What must be absent from a concrete implementation

These items exist in the FLS repo's own dev config for internal development and testing. They must **not** appear in a concrete implementation's settings or URLs.

Note: the branch-aware DB/session logic, `debug_branch_info`, and `HEADLESS_SERVE_SPECIFICATION` are **no longer** on this list — they are now part of the template's dev contract (see [Multi-worktree dev setup](#multi-worktree-dev-setup) and the `settings_dev.py` checklist).

| Item | Where it lives in FLS | Why it must be absent |
|---|---|---|
| `freedom_ls.qa_helpers` | `INSTALLED_APPS` in `settings_dev.py` | FLS-internal QA tooling; not for production projects |
| `freedom_ls.qa_helpers.urls` | `urls.py` DEBUG block | Same; exposes internal test routes |
| `FORCE_SITE_NAME = "DemoDev"` | `settings_dev.py` | Hardcodes the FLS internal demo site; concrete projects create their own site via `apps/project_setup`'s `setup_initial_data` |
| DemoDev role mapping + module (`{"DemoDev": "config.role_based_permissions.demodev"}` and `config/role_based_permissions/demodev.py`) | `settings_dev.py` + `config/` | FLS demo roles; the scaffold ships an unwired generic `config/role_based_permissions/example.py` instead (the `FREEDOMLS_PERMISSIONS_MODULES` placeholder itself stays, defaulting to `{}`) |
| `HEADER_LOGO_STATIC_PATH = "images/first_class_logo.png"` etc. | `settings_dev.py` | FirstClass demo branding; concrete projects supply their own assets (template branding stubs default to `None`) |
| `ADMONITION_TYPES` override adding `"regulation"` | `settings_dev.py` | FLS demo-content-specific admonition type; the template ships only the base set plus a commented example, so omit unless your content uses it |
| `REQUIRE_TERMS_ACCEPTANCE = True` | `settings_dev.py` | DemoDev policy override; the template's `customisation.py` default is `False` — set it per your own policy, don't copy the DemoDev value |

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
