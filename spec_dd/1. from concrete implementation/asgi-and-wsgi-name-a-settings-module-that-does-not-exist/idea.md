# Idea: FLS's `asgi.py` and `wsgi.py` default to a settings module the repo does not have

## The bug

Source: auditing this project's `config/` against FLS's at `c43a3381` during the
`prod_bucket_setup` upgrade.

Both entry points set the same default:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

There is no `config/settings.py` in FLS. The repo ships `config/settings_base.py`,
`config/settings_dev.py` and `config/settings_prod.py` only. So running FLS's own `wsgi.py` or
`asgi.py` without `DJANGO_SETTINGS_MODULE` already exported fails with `ModuleNotFoundError`.

It is almost certainly leftover `django-admin startproject` boilerplate that survived the split into
base/dev/prod. It stays invisible because everything that actually runs FLS — `manage.py`, pytest,
gunicorn in a downstream image — sets the variable explicitly.

The reason it is worth fixing rather than ignoring: `template_repo_manifest.md` names the live FLS
`config/` as the authority downstreams should check their own wiring against. A concrete project
that copies this line inherits a broken default, and it is the kind of thing that only surfaces the
first time someone runs a server without the env var set.

## Expected fix

Point both defaults at a module that exists — `config.settings_dev` is the closest match to the
other dev-time defaults in the repo — or drop the `setdefault` entirely and let the failure name the
missing variable, which is the more honest outcome for a repo with no single canonical settings
module.

## Sources

- `submodules/Freedom-LS/config/asgi.py` — line 14.
- `submodules/Freedom-LS/config/wsgi.py` — line 14.
- `submodules/Freedom-LS/claude_plugins/fls-dev/resources/template_repo_manifest.md` — the
  "`config/` content contract" section naming FLS's `config/` as the authority.
