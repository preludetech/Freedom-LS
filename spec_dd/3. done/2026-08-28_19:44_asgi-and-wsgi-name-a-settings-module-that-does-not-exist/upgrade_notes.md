---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: asgi-and-wsgi-name-a-settings-module-that-does-not-exist

`config/wsgi.py` and `config/asgi.py` no longer set a default `DJANGO_SETTINGS_MODULE`. Both
carried leftover `django-admin startproject` boilerplate naming `config.settings`, a module FLS
has never had — it ships `settings_base`, `settings_dev` and `settings_prod` only. The caller
now names the settings module, and a process that forgets stops at Django's own error, which
names the variable to set.

No setting changes name, gains a default, or becomes required. Nothing in FLS reads either file.

## Breaking changes

None. A downstream project's own copy of that line is broken in exactly the same way today, so
no path that works now stops working. Every documented invocation — `manage.py`, the pytest
config, the CI workflows, and the template repo's Dockerfile, which exports
`DJANGO_SETTINGS_MODULE=config.settings_prod` before gunicorn imports `config.wsgi:application`
— already sets the variable before either module is imported.

## Manual steps

Delete the same line from the project's own `config/wsgi.py` and `config/asgi.py`:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

`import os` becomes unused in both files once it goes. FLS's copies keep a short comment in its
place recording that the omission is deliberate; mirroring that comment is optional.

Confirm the deployment sets `DJANGO_SETTINGS_MODULE` explicitly. A project on the shipped
scaffolding already does, in the Dockerfile's `ENV` block at both build time (for
`collectstatic`) and run time — this is a check, not a change. A project that hand-rolled its
own container, systemd unit or process manager should verify the variable is exported there
before the WSGI or ASGI callable is imported. Without it, the process now fails at import with
`ImproperlyConfigured: … You must either define the environment variable
DJANGO_SETTINGS_MODULE …` rather than starting on a settings module chosen by boilerplate.

## Template repo

The template repo (`freedom-ls-concrete-template`) ships its own `config/wsgi.py` and
`config/asgi.py` carrying the identical broken default, and needs the identical deletion so that
projects scaffolded after this change do not inherit it. This was **not** applied — no local
checkout of the template repo is configured (`.claude/fls-dev/config.local.md` does not exist in
this worktree), so it is recorded here for whoever next syncs the template.

`claude_plugins/fls-dev/resources/template_repo_manifest.md` is deliberately left alone. Its
`config/` tree lists both files without annotation and its content contract has no subsection
for either; writing a checklist for two files that should never need editing is not the fix.
