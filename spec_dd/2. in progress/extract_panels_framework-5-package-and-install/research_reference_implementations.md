# Research: reference implementations (reusable Django apps shipping templates, static, migrations)

Question: how do reference implementations solve packaging, licensing, changelog, CI, Tailwind-dependent templates and an app-label rename?
Method: raw `pyproject.toml` / workflow / docs fetches via web, 2026-11-26. Values are as fetched (summarised by a fetch model); re-check any one before quoting it in the spec. Items marked "not verified" were not confirmed.

## 1. Build backend and package data

| Project (repo) | Backend | Package-data config | Licence declaration |
| --- | --- | --- | --- |
| django-unfold (github.com/unfoldadmin/django-unfold, `pyproject.toml`) | hatchling | `src/unfold` listed under both wheel and sdist targets, mapped to `unfold`. No separate package-data key: hatchling ships every file under the listed dir (templates, static, migrations). | `license = "MIT"` |
| django-debug-toolbar (github.com/django-commons/django-debug-toolbar, `pyproject.toml`) | hatchling | `build.targets.wheel.packages = ["debug_toolbar"]`; version from `debug_toolbar/__init__.py`. No explicit data config. Has a `tox -e packaging` job. | `license = { text = "BSD-3-Clause" }` |
| django-htmx (github.com/adamchainz/django-htmx, `pyproject.toml`) | uv_build (`uv-build>=0.12.1,<0.13`) | None; backend defaults. | `license = "MIT"`, `license-files = ["LICENSE"]` |
| django-allauth (github.com/pennersr/django-allauth, `pyproject.toml`) | setuptools + setuptools-scm | `packages.find include = ["allauth*"]`; `package-data "*" = ["*.mo"]`; other non-py files via setuptools-scm (git-tracked files) | `license = "MIT"`, `license-files = ["LICENSE"]` |
| django-filter (github.com/carltongibson/django-filter, `pyproject.toml`) | flit_core | `[tool.flit.module] name = "django_filters"`; flit ships all files in the module dir. Stale unused `[tool.setuptools]` block present. | `license = {text = "BSD"}` (old form) |
| neapolitan, django-template-partials (carltongibson) | flit_core | `[tool.flit.module]` only | `license = {file = "LICENSE"}` + classifier |
| django-cotton (github.com/wrabit/django-cotton, `pyproject.toml`) | poetry-core | Poetry `exclude = [dev, docs, django_cotton/tests, django_cotton/templates]` (dev-only dirs left out) | `license = "MIT"` under `[tool.poetry]` |
| django-tables2 (jazzband) | not verified (raw URL 404) | - | - |

Take-aways for this spec:
- Hatchling or flit/uv_build with the package dir named explicitly is the norm; none write a package-data table. This supports the idea's "hatchling includes everything under the package dir". Set `[tool.hatch.build.targets.wheel] packages = [...]` and the wheel test is the proof.
- Modern SPDX form (`license = "MIT"` + `license-files = ["LICENSE"]`) is used by django-htmx, django-allauth, django-unfold. This matches the idea. django-filter shows the older form to avoid.
- Only django-debug-toolbar runs a packaging check in CI (`tox -e docs,packaging`); none found build a wheel and assert specific member files. The idea's wheel test is stricter than any reference.
- django-cotton's `exclude` shows the reverse need: dev-only dirs (tests, dev project) kept out of the artefact. Consider excluding `tests/` and (later) `claude_plugins/` from the wheel.

## 2. LICENSE and bundled-asset notices

| Project | What was found |
| --- | --- |
| django-unfold | Single `LICENSE` (MIT); bundled JS/CSS lib notices not confirmed (not verified). |
| django-allauth | `LICENSE` only; `license-files = ["LICENSE"]`. |
| django-debug-toolbar | BSD `LICENSE`. |

No reference found that lists third-party asset licences inside the main `LICENSE`. Common practice found is one `LICENSE` plus per-asset notice files shipped beside the assets. The idea's design (MIT text, a list of bundled assets with licence and notice location, `HEROICONS_LICENSE.txt` in the wheel) goes further than the references. `license-files` accepts several globs (PEP 639), so the notice file could also be listed there; not verified against hatchling docs this run.

## 3. CHANGELOG format

| Project | File | Format |
| --- | --- | --- |
| django-filter | `CHANGES.rst` | `Version 26.2 (2026-10-03)` heading, flat bullets ("Added testing against Python 3.15", "Dropped support for Python 3.10", behaviour change with the fix stated) |
| django-allauth | `ChangeLog.rst` | `65.23.0 (2026-11-25)` heading, then fixed subsections: Note worthy changes, Fixes, Security notice, Backwards incompatible changes |
| django-htmx | `CHANGELOG.rst` | Fetch 404; format not verified. CI releases on tag push after a coverage gate, publishing with `uv build`. |

Take-aways: none use machine-readable per-entry flags. django-allauth's fixed subsections (especially "Backwards incompatible changes") are the closest model for the idea's flags (`requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change`, `requires_tailwind_rebuild`). A per-tag block with the date in the heading, then a fixed flag list (always present, `no` or paths), then prose, keeps the file greppable. Markdown is fine; the references use rst but nothing depends on it.

## 4. CI matrices

| Project | Python | Django | DB | Browser tests | Runner |
| --- | --- | --- | --- | --- | --- |
| django-unfold (`.github/workflows/test.yml`) | 3.13, 3.14, 3.15 | 5.2, 6.0, 6.1, main (12 jobs, `fail-fast: false`) | none stated | none | `uv run -- tox run -e python313-django60`, ubuntu-latest, 10 min timeout, push to main and PRs |
| django-htmx (`.github/workflows/main.yml`) | 3.11 to 3.15 | via tox; also uv dependency groups `django52`, `django60`, `django61` declared mutually conflicting in `[tool.uv]` | none | none | `uvx --with tox-uv tox run -f pyXY`; coverage job fails below 100%; tag push builds and publishes |
| django-debug-toolbar (`.github/workflows/test.yml`) | 3.10 to 3.15 and 3.15t | via tox | MariaDB 11.8, SQLite, Postgres via `postgis/postgis:17-3.5` service container, psycopg3 | Selenium (`DJANGO_SELENIUM_TESTS=true`, some postgres jobs only); a vitest job installs Chromium and Firefox through Playwright and runs `npm ci && npm test` | tox + tox-gh-actions; weekly cron `37 3 * * SAT`; merged coverage comment on PR |
| django-filter | classifiers Py 3.11 to 3.15, Django 5.2/6.0/6.1; changelog says "Added testing for Django 6.1" each release | | | | workflow not fetched |

Take-aways: Django 5.2 LTS, 6.0, 6.1 and Python 3.13 to 3.15 is the current window across references. FLS is Python 3.13+, Django 6.x, Postgres 17, so the package matrix could be Django 6.0 and 6.1 on Py 3.13 and 3.14 (add 5.2 only if the package declares it). debug-toolbar is the only reference with a Postgres service container and a Playwright install in CI (one job each). The uv dependency-group-per-Django approach (django-htmx) fits an all-uv package with no tox.

## 5. How Tailwind-dependent templates reach a host's Tailwind

| Project | Mechanism found | Source |
| --- | --- | --- |
| django-unfold | Ships its own prebuilt CSS; the host only compiles Tailwind for its own overrides: `@import 'tailwindcss';` and `npx @tailwindcss/cli -i styles.css -o your_project/static/css/styles.css --minify` (Unfold 0.57+, Tailwind 4); v3 `content: ["./your_project/**/*.{html,py,js}"]`. No `@source` for package templates, no management command. | https://unfoldadmin.com/docs/styles-scripts/customizing-tailwind/ |
| django-tailwind (timonweb) | Generated `theme` app in the host; default v4 `@source "../../../**/*.{html,py,js}";` (glob from three levels above the CSS). v3 `content` lists `'../../templates/**/*.html'`, `'../../**/*.py'`, `'!../../**/node_modules'`. Discovery is by path, not `INSTALLED_APPS`. Nothing for site-packages. | https://github.com/timonweb/django-tailwind (docs/installation.md) |
| django-tailwind-cli | Opt-in `TAILWIND_CLI_AUTO_SOURCE_EXTERNAL_APPS = True`: for each installed app outside `BASE_DIR` and outside every site-packages dir (editable installs from a sibling repo) it writes an absolute `@source "/abs/path/to/app";` into an auto-generated `source.css` (starts with `@import "tailwindcss";`). Regenerated whenever the file is written; a hand-written `TAILWIND_CLI_SRC_CSS` is left alone. Regular site-packages apps are explicitly NOT covered. | https://django-tailwind-cli.readthedocs.io/latest/settings.html |
| python-webpack-boilerplate | `@import "tailwindcss" source(none);` then explicit `@source "../../../app/**/*.html";` lines. | https://python-webpack-boilerplate.readthedocs.io/en/latest/setup_with_tailwind/ |
| crispy-tailwind | Not fetched; not verified. | |

Take-aways:
- No reference found that prints the package path from a management command, or that uses `@source not-ignored:` for a `.venv` path. Spec 4's source command is new ground; django-tailwind-cli's "generate a CSS file with absolute `@source` lines" is the nearest prior art and makes the same choice (generated file, host imports it, regenerated on demand).
- django-tailwind-cli says plainly that its auto mode skips site-packages apps, which confirms the need for an explicit generated `@source` for an installed package.
- django-unfold avoids the problem by shipping compiled CSS. That is the alternative if a host cannot run the source command; the idea does not take it.
- Tailwind v4 gitignore behaviour (`.venv` skipped, hence `not-ignored:`) comes from the existing research file; not re-verified here.

## 6. App-label change when moving into a package

| Case | What they did |
| --- | --- |
| django.contrib.comments to django-contrib-comments (label `comments` to `django_comments`) | Install the package, change the `INSTALLED_APPS` entry to `django_comments`, update urls/imports. The new initial migration collides with the old table, so docs say run `manage.py migrate django_comments --fake-initial` (error quoted: `relation "django_comments" already exists`). Docs say nothing on `django_content_type` rows. Table name kept, no drop. https://django-contrib-comments.readthedocs.io/en/latest/porting.html |
| Generic rename guides and django-rename-app | `rename_app` command renames app tables plus `django_content_type` and `django_migrations` rows; then a migration for indexes and FKs. Manual route: update `django_content_type.app_label`, `django_migrations.app`, rename tables via `AlterModelTable` or `RunPython`. "Reset" route for small projects: delete the old app's migration records, regenerate migrations, `migrate --fake-initial` (loses history). https://dev.to/djangotricks/how-to-rename-a-django-app-15m3, https://makandracards.com/django/54489-django-rename-app |
| Django tickets | The label is hardcoded in migration `dependencies`, so relabelling in place is unsupported: https://code.djangoproject.com/ticket/23790, https://code.djangoproject.com/ticket/25765 |

Compared with this spec: the idea takes the "reset" route with a different table name (`panel_framework_bulkactionrun`), which avoids the `--fake-initial` / "relation already exists" trap django-contrib-comments hits, because old and new tables never share a name. Old rows are then removed explicitly (answers file: a `RunPython` that checks through `connection.introspection` and calls `schema_editor.delete_model`, plus ORM deletes of `django_migrations` and ContentType rows). No reference found that did exactly this drop; django-contrib-comments kept the table and faked, which does not fit here because the data is not worth keeping and the label changes.

## 7. Gaps

- django-tables2, django-cotton's CHANGELOG, crispy-tailwind and neapolitan CI were not read (404 or not fetched).
- No reference found with a wheel-contents test, a `LICENSE` that enumerates bundled assets, a git-tag-only release flow, or a management command that prints the package path for Tailwind.
- Values come from a summarising fetch; verify specifics before copying.

status: ok
