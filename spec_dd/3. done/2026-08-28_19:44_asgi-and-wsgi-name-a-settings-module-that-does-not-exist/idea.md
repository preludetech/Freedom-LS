# Idea: FLS's `asgi.py` and `wsgi.py` default to a settings module the repo does not have

## The bug

Both entry points set the same default:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

There is no `config/settings.py` in FLS. The repo ships `config/settings_base.py`,
`config/settings_dev.py` and `config/settings_prod.py` only, so a process that reaches this line
with the variable still unset dies at import with
`ImproperlyConfigured: No module named 'config.settings'.` This is leftover `django-admin
startproject` boilerplate that survived the split into base/dev/prod. `manage.py` was updated to
`config.settings_dev` at the time. These two were not.

The line is dead code on every path that exists today. `manage.py`, the pytest config in
`pyproject.toml` and the CI test workflow all set `DJANGO_SETTINGS_MODULE=config.settings_dev`, the
deploy check passes `--settings=config.settings_prod`, and the template repo's Dockerfile exports
`config.settings_prod` before gunicorn imports `config.wsgi:application`. Nothing in FLS imports
`config/asgi.py` at all. `settings_base` sets `WSGI_APPLICATION` and there is no `ASGI_APPLICATION`
anywhere in the repo.

## Why fix a line nobody executes

Because it is published as a reference. `template_repo_manifest.md` names the live FLS `config/` as
the authority a concrete project checks its own wiring against, and the scaffold ships its own
`config/wsgi.py` and `config/asgi.py`. Every other file in that manifest's `config/` tree carries an
annotation saying how the downstream copy differs. These two carry none, and the checklist has no
subsection for them, so the honest reading is "copied verbatim". A concrete project inherits the
broken default and finds out the first time someone starts a server without the variable already
exported.

Being unreachable is also why it survived this long. No test imports either entry point, no
conformance test or system check looks at them, and keeping the template's `config/` aligned with
FLS's is a checklist somebody maintains by hand. There is nothing between this line and a downstream
repo.

## What we are doing

**Delete the `setdefault` call from both files**, rather than repointing it. FLS has no canonical
settings module, so any default is a guess about which environment the reader is in, and every real
invocation already answers that question explicitly. With the line gone, a deployment that forgets
the variable stops at import with Django's own message naming `DJANGO_SETTINGS_MODULE`, instead of
booting a server on a settings module chosen by whoever last edited the boilerplate. Nothing pays
for this. Gunicorn, uvicorn and daphne take the entry point as `module:attribute` and never consult
the variable themselves, and `runserver` goes through `manage.py`, whose own default is correct and
stays put.

**Both files change, and `asgi.py` stays.** It is unreferenced today, but it is what anyone reaching
for async starts from, the template repo ships it, and keeping the pair identical is what stops them
drifting apart again. Cookiecutter-django's `wsgi.py` and `asgi.py` disagree with each other right
now for exactly that reason.

**A test imports both entry points and asserts each yields an application.** It is the only thing
that would have caught this, and it turns two unexercised files into covered ones.

Left alone deliberately: `template_repo_manifest.md` gains no `wsgi.py` or `asgi.py` section. The
manifest's silence is real, but writing a checklist for two files that should never need editing is
not the fix.

## Research

`research_entrypoint_settings_default_conventions.md` has Django's exact failure messages, what
cookiecutter-django and the wider community actually do, and the precedent for dropping the default.

`research_fls_entrypoint_and_downstream_contract.md` has every caller of the entry points in this
repo and in the template's deploy path, what the manifest does and does not say, and the absence of
any existing guard.

Found during the `prod_bucket_setup` audit of this project's `config/` against FLS's, alongside the
sibling idea `settings-base-template-dirs-points-at-a-scratch-path`.
