# Research: FLS's `wsgi.py`/`asgi.py` entrypoint contract and the downstream template

## 1. Who actually imports `config.wsgi` / `config.asgi` in this repo — is the broken default ever hit?

**Nobody in this repo imports `config.wsgi` or `config.asgi` today, and `DJANGO_SETTINGS_MODULE` is
always already set by the time either file would run.**

- `config/asgi.py:14` and `config/wsgi.py:14` — the only two lines in the whole repo where the
  literal string `"config.settings"` appears (besides this spec's own `idea.md`), confirmed by a
  repo-wide grep for `config\.settings\b`.
- `manage.py:10` — `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_dev")`. Every
  `manage.py` invocation (`runserver`, `check`, `migrate`, `makemigrations`, `test`, `db_worker`,
  etc.) sets the env var to a module that *does* exist, before Django ever touches `config/wsgi.py`
  (which `runserver`/the autoreloader can import indirectly via the `WSGI_APPLICATION` setting).
- `config/settings_base.py:203` — `WSGI_APPLICATION = "config.wsgi.application"`. There is no
  `ASGI_APPLICATION` setting anywhere in the repo (confirmed by grep for `ASGI_APPLICATION`) — FLS
  runs WSGI-only; nothing references `config/asgi.py` at all except `asgi.py` itself.
- `pyproject.toml:75` — `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE = "config.settings_dev"`.
  Sets the env var for the whole pytest run before any test module (and therefore before any import
  of `config.wsgi`/`config.asgi`, which nothing imports anyway) runs.
- `.github/workflows/tests.yml:39` — the `type-check` job sets `DJANGO_SETTINGS_MODULE:
  config.settings_dev` as a step env var for `mypy`.
- `.github/workflows/security.yml:87` — the `django-check-deploy` job runs `manage.py check --deploy
  --fail-level WARNING --settings=config.settings_prod`, using the `--settings` CLI flag (which
  Django honours ahead of `DJANGO_SETTINGS_MODULE`/any `setdefault`), not the env var at all. `manage.py
  check` never imports `config.wsgi`/`config.asgi`.
- No `Dockerfile`, `docker-compose.yml`, `gunicorn`, `uvicorn`, or `daphne` reference exists anywhere
  in *this* repo (confirmed: `Glob` for `Dockerfile`/`docker-compose.yml` at repo root returns
  nothing; grep for `gunicorn|uvicorn|daphne` across the repo returns no hits outside `uv.lock`
  pinning `gunicorn` transitively — see §4). The standalone deployment path that once ran a WSGI
  server from this repo was deliberately **removed**: see §4.
- The two `wsgi`/`WSGIRequest` hits in `freedom_ls/educator_interface/tests/test_organisation_switcher.py:158`
  and `test_interface_urls.py:12,116` are Django test-client `WSGIRequest` objects (the request
  object returned by the test client), unrelated to the `config/wsgi.py` entrypoint file.

**Conclusion for Q1:** there is no path in this repo, today, where `os.environ.setdefault` in
`asgi.py`/`wsgi.py` is reached with the variable still unset — everything that runs FLS sets
`DJANGO_SETTINGS_MODULE` (or passes `--settings`) before either file could be imported. The
production path that *does* import `config.wsgi:application` lives entirely in the separate
template repo (§4), where the variable is also always pre-set.

## 2. The downstream/template-repo `config/` content contract

Full read of `claude_plugins/fls-dev/resources/template_repo_manifest.md` (299 lines).

**The repo file tree** (lines 42–52) lists the template's `config/` contents:

```
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
```

Every other file in that listing carries an inline annotation describing how it differs from or
extends FLS's own file. **`asgi.py` and `wsgi.py` carry no annotation at all** — unlike
`settings_base.py` ("splat-imports customisation"), `settings_dev.py` ("no qa_helpers;
branch-aware…"), `settings_prod.py` ("Production overrides"), or `urls.py` ("no qa_helpers.urls").
The unannotated listing is consistent with these two files being unmodified `django-admin
startproject` boilerplate carried through verbatim — the same boilerplate origin the idea.md for
this bug already suspects for FLS's own copies — but the manifest never says this explicitly; it
simply never calls the file out.

**The `config/` content contract section** (`## config/ content contract`, starting line 76)
states the authority relationship directly:

> "This is a completeness checklist for keeping a concrete implementation's `config/` aligned with
> the FLS wiring. The **live FLS `config/` at `config/` in this repo is the authority** for the
> canonical app list, middleware, and required setting keys/defaults."

and closes with:

> "The authoritative source for each setting's purpose and default value is always the live FLS
> `config/` in this repo. When in doubt, read the source." (line 298)

**However, the checklist itself has no subsection for `asgi.py` or `wsgi.py`.** It has dedicated
subsections for `settings_base.py`, `config/customisation.py`, `settings_dev.py`, `settings_prod.py`,
and `urls.py` (lines 80–228) — each with a checkbox list of required settings/entries — but no
`### asgi.py` / `### wsgi.py` subsection and no checklist item mentioning either file's contents,
`DJANGO_SETTINGS_MODULE` default, or the `WSGI_APPLICATION`/`ASGI_APPLICATION` settings. So while the
manifest names FLS's `config/` as the authority *in general*, it does not name the entrypoint files'
`setdefault` target as something a downstream should check against FLS's copy — it is simply silent
on `asgi.py`/`wsgi.py` content, and the file-tree listing implies (without stating) that they are
copied through unmodified.

**Nothing in the manifest instructs a downstream to change the `setdefault` target.** If a
downstream project instantiated the template unmodified, its `config/wsgi.py`/`config/asgi.py` would
carry over whatever FLS's own file contains at template-sync time (via `/fls:sdd:update_template_repo`,
mentioned line 38 of the SDD plan record cited in §4) — i.e. today's broken `"config.settings"`
default, unless someone hand-edited it.

## 3. What a downstream project's settings modules look like — would `config.settings_dev`/`config.settings_prod` even be correct there?

**Yes — the module names are identical in both FLS and the template.** Per the manifest:

- `### settings_dev.py` (line 173–192): "- [ ] Extends `settings_base` via `from .settings_base
  import *`" — filed under the heading `settings_dev.py`, i.e. the downstream project's dev settings
  module is also named `config/settings_dev.py` / `config.settings_dev`.
- `### settings_prod.py` (line 194–216): same pattern, "- [ ] Extends `settings_base` via `from
  .settings_base import *`" under the heading `settings_prod.py` — the downstream module is also
  `config/settings_prod.py` / `config.settings_prod`.

So the three-way base/dev/prod split and its module names (`config.settings_base`,
`config.settings_dev`, `config.settings_prod`) are a **shared convention** between FLS and every
downstream concrete project generated from the template — not something FLS invents for itself and
a downstream renames. The downstream files' *contents* differ in specific, catalogued ways (the
"what must be absent" table, lines 251–266: no `qa_helpers`, no `FORCE_SITE_NAME = "DemoDev"`, no
DemoDev role mapping, etc.), but the *module paths* are not part of that divergence list.

This is corroborated by the deployment scaffolding's own SDD plan record (see §4): the template's
Dockerfile and compose file both hardcode `DJANGO_SETTINGS_MODULE=config.settings_prod` and gunicorn
targets `config.wsgi:application` — i.e. the template repo's actual production wiring uses exactly
these two module names.

**Answer to the framing question:** yes — `config.settings_dev` and `config.settings_prod` are
correct, existing module names in a downstream concrete project, not just in FLS. Pointing FLS's own
`asgi.py`/`wsgi.py` `setdefault` at one of them would name a module that also exists downstream,
because the template ships (and is contractually expected to ship) files with those exact names.

No `spec_dd/3. done/` directory name matched `*template-repo*`, `*concrete-project*`, or
`*prod-settings*` as literal substrings via glob; the actual relevant directories use the fuller
names `support-concrete-project-deployment-*` (see §4), which do contain this material.

## 4. How production actually boots

**Nothing in this repo boots production** — FLS is submodule-only from a deployment-artifact
standpoint. Confirmed by:

- `docs/product/deployment.md:8`: "FLS is never deployed standalone — a production deployment is a
  **concrete project** built from the template repo, which owns the Compose and reverse-proxy
  scaffolding."
- `docs/product/deployment.md:111`: "FLS is never deployed standalone. A production deployment is a
  **concrete project** — a downstream repository that installs `freedom_ls` as a git submodule and
  supplies its own settings, content, and deployment scaffolding."
- `spec_dd/3. done/2026-07-17_16:28_remove-standalone-path/1. spec.md` records that this repo
  **used to** ship a standalone `docker-compose.yml` (`db`/`web`/`nginx` services), a standalone
  `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`, and `docs/how tos/DOCKER_DEPLOY.md` — and
  that spec **removed all of them** ("Remove (do not repair) the standalone-only artifacts, since
  there is no standalone deployment for them to serve"). That spec's own record notes the deleted
  compose file "sets `DJANGO_SETTINGS_MODULE=config.settings_prod`" (line 51) — i.e. even the old,
  now-deleted in-repo path set the env var explicitly rather than relying on `wsgi.py`'s default.
  Confirmed no `Dockerfile`/`docker-compose.yml` exist in this repo today (`Glob` both return no
  matches).

**The actual production entrypoint lives in the separate `freedom-ls-concrete-template` repo**
(`git@github.com:preludetech/freedom-ls-concrete-template.git`), which is not checked out anywhere
in this filesystem (`Glob **/freedom-ls-concrete-template/** ` returns nothing). What we know of its
Dockerfile/compose comes from this repo's own SDD plan record for the spec that built it —
`spec_dd/3. done/2026-07-18_17:09_support-concrete-project-deployment-5-template-repo-scaffolding/2. plan.md`
— a design/implementation record, not the live downstream file. It quotes the intended Dockerfile
and compose content directly:

```dockerfile
# python-runtime stage
ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings_prod \
    PYTHONUNBUFFERED=1
USER appuser
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

and the build stage (used for build-time `collectstatic`) also sets it explicitly:

```dockerfile
    HOST_DOMAIN="build.invalid" \
    FLS_THEME="${FLS_THEME}" \
    DJANGO_SETTINGS_MODULE=config.settings_prod \
    AWS_STORAGE_BUCKET_NAME="" \
    uv run python manage.py collectstatic --noinput
```

and the compose `web` service command:

```yaml
  web:
    <<: *app-env
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

That same plan also records (line 26) that at the time of that spec, `gunicorn` was **not** in
`pyproject.toml`/`uv.lock` at all — Task 1 of that plan adds it — reinforcing that no WSGI server
ships or runs from this FLS repo itself; it is a template-repo-only dependency.

**So: `DJANGO_SETTINGS_MODULE` is set explicitly via a Dockerfile `ENV` line in every documented
production path**, both at build time (for `collectstatic`) and at runtime (before gunicorn imports
`config.wsgi:application`). By the time `config/wsgi.py`'s `os.environ.setdefault(...)` line runs,
the variable is already `config.settings_prod` — the `setdefault` call is dead code on this path too,
matching the finding in §1 for the dev/test paths inside this repo. This is a design record for a
spec filed under `spec_dd/3. done/`, not a live inspection of the template repo's actual files, so
treat it as strong but secondhand evidence, not a first-party confirmation of the template repo's
current state.

`docs/product/deployment.md` (`## Target Architecture`, lines 13–23) confirms the same shape at the
narrative level: Caddy → Gunicorn + Django 6 (WSGI application) → PostgreSQL, all shipped by the
template repo's scaffolding, and (`## Provisioning and CI/CD`, lines 31–37) that the build-and-push
CI workflow "lives in the template repo alongside the rest of the deploy scaffolding," not in this
repo.

## 5. Existing tests/checks that would catch this class of bug

**None found.** Specifically:

- No test anywhere in the repo imports `config.wsgi` or `config.asgi` and asserts it succeeds (grep
  for `wsgi|asgi` across the repo turned up only the two entrypoint files themselves, the
  `WSGIRequest` test-client usages noted in §1, and prose mentions in docs/spec files — no test
  module imports the entrypoint).
- `freedom_ls/contrib/conformance/` is FLS's opt-in downstream conformance suite (`__init__.py`
  exports `test_migration_state_consistent`, `test_configured_backend_instantiates`,
  `test_active_icon_set_resolves`, `test_active_theme_resolves`, `test_fls_namespace_reverses`,
  `test_reference_url_reverses`, plus a `drop()` helper). None of the five conformance tests touch
  `config.wsgi`/`config.asgi`, `WSGI_APPLICATION`, or `DJANGO_SETTINGS_MODULE`.
- The Django system-checks framework is used in this repo (`freedom_ls/course_access/checks.py` +
  `apps.py`, documented as the house exemplar in
  `spec_dd/3. done/2026-08-24_06:31_fls-test-portability-part-2/research_django_system_checks.md`),
  but no check inspects `WSGI_APPLICATION`/`ASGI_APPLICATION` resolvability or the entrypoint files;
  the existing checks are about `COURSE_ACCESS_BACKEND` configuration, unrelated to this bug class.
- `manage.py check --deploy` (run in CI via `.github/workflows/security.yml:87`, using
  `--settings=config.settings_prod` directly) does not import `config.wsgi`/`config.asgi` — Django's
  `check` framework does not import the WSGI/ASGI entrypoint modules; it only reads the
  `WSGI_APPLICATION` string setting as a value, without importing what it points to (a manual
  `docs/…research_django_system_checks.md` note, lines 205–212, confirms Django's checks run
  implicitly before `runserver`/`migrate`/`test`/`check`, not as part of the WSGI request stack, and
  says nothing about validating that `WSGI_APPLICATION` resolves).
- No management command (`check_`-prefixed or otherwise) or manifest-diffing tool that compares a
  downstream `config/` against FLS's `config/` exists in this repo — the "authority" relationship
  documented in `template_repo_manifest.md` (§2 above) is a human checklist maintained by hand
  ("Keep the template in sync," lines 294–298: "update both the template repo's `config/` files and
  this document's checklist... The checklist is only as good as the last time someone checked it
  against the live FLS files"), not automated tooling.

**Conclusion for Q5:** no existing test, conformance check, system check, or CI step would catch
`config/wsgi.py`/`config/asgi.py` defaulting to a nonexistent settings module, because nothing in
the repo (or, per the SDD plan record, in the template repo's build/run steps) ever exercises that
`setdefault` fallback — every real invocation pre-sets `DJANGO_SETTINGS_MODULE` or passes
`--settings` before either file could run.

status: ok
