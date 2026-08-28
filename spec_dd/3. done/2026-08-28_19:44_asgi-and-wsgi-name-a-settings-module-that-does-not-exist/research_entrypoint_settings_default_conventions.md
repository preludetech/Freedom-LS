# Research: what should `config/asgi.py` / `config/wsgi.py` default `DJANGO_SETTINGS_MODULE` to?

Scope: external/community evidence only, for the open question of what
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", ...)` should say in FLS's
`config/asgi.py` and `config/wsgi.py`, given the repo has no `config/settings.py`
(only `settings_base.py`, `settings_dev.py`, `settings_prod.py`) and `manage.py`
already defaults to `config.settings_dev`.

---

## 1. What Django itself does and says

### The exact behaviour, from Django's own source (`django/conf/__init__.py`, `main` branch, mirrors 5.2/6.x)

Two distinct failure paths exist, and **both raise `django.core.exceptions.ImproperlyConfigured`** — the premise in the question that one path might raise a bare `ModuleNotFoundError` is not correct as of current Django. Quoting the source directly:

**Case A — `DJANGO_SETTINGS_MODULE` is unset entirely** (`LazySettings._setup`):

```python
def _setup(self, name=None):
    settings_module = os.environ.get(ENVIRONMENT_VARIABLE)
    if not settings_module:
        desc = ("setting %s" % name) if name else "settings"
        raise ImproperlyConfigured(
            "Requested %s, but settings are not configured. "
            "You must either define the environment variable %s "
            "or call settings.configure() before accessing settings."
            % (desc, ENVIRONMENT_VARIABLE)
        )
    self._wrapped = Settings(settings_module)
```

Exact message text: `"Requested settings, but settings are not configured. You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings."`

**Case B — `DJANGO_SETTINGS_MODULE` is set but the module doesn't exist / isn't importable** (`Settings.__init__`):

```python
self.SETTINGS_MODULE = settings_module
try:
    mod = importlib.import_module(self.SETTINGS_MODULE)
except ImportError as exc:
    if exc.name == self.SETTINGS_MODULE:
        msg = f"No module named {self.SETTINGS_MODULE!r}."
        raise ImproperlyConfigured(msg) from exc
    raise
```

Exact message text for FLS's literal current bug: `"No module named 'config.settings'."` — raised as `ImproperlyConfigured`, not `ModuleNotFoundError`. Django catches the `ImportError`/`ModuleNotFoundError` internally and re-raises it as `ImproperlyConfigured` **only when the failing import's name matches the settings module itself** (so an import error *inside* a valid settings file, e.g. a bad `from .base import *`, is *not* swallowed — it propagates as the original error, which is more diagnosable for a typo deep inside a settings file, but less diagnosable at a glance for "which module failed").

**Diagnosability comparison:** Both are `ImproperlyConfigured`, so `except ImproperlyConfigured` handling is identical either way. The *message* differs: Case A explicitly names the environment variable to set and mentions `settings.configure()`; Case B just says "No module named '...'" with the dotted path that was tried, which is arguably *more* directly actionable for someone deploying (it tells you exactly what string it went looking for) but doesn't remind you which env var controls it. Neither is a mysterious traceback — both name-drop something concrete.

Source: [django/conf/__init__.py, main branch](https://github.com/django/django/blob/main/django/conf/__init__.py)

### Django's own docs on choosing the default value

The WSGI deployment doc and ASGI deployment doc both say, near-identically:

> "Django uses the `DJANGO_SETTINGS_MODULE` environment variable to locate the appropriate settings module. It must contain the dotted path to the settings module. You can use a different value for development and production; it all depends on how you organize your settings. If this variable isn't set, the default `wsgi.py`/`asgi.py` sets it to `mysite.settings`, where `mysite` is the name of your project."

Django takes no position on whether the fallback should be the dev or prod module — it explicitly says "it all depends." Sources:
- [How to deploy with WSGI — Django docs](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/)
- [How to deploy with ASGI — Django docs](https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/)

### What `django-admin startproject` generates today

Current template (`django/conf/project_template/project_name/{wsgi,asgi}.py-tpl` on Django's `main` branch) is unchanged boilerplate — this is exactly the pattern FLS copied and never customized:

```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{{ project_name }}.settings')
```

Source: [wsgi.py-tpl](https://github.com/django/django/blob/main/django/conf/project_template/project_name/wsgi.py-tpl), [asgi.py-tpl](https://github.com/django/django/blob/main/django/conf/project_template/project_name/asgi.py-tpl)

### `setdefault()` vs direct assignment — the documented mod_wsgi footgun

Django's own mod_wsgi deployment docs carry an explicit, official warning:

> "If multiple Django sites are run in a single mod_wsgi process, all of them will use the settings of whichever one happens to run first."

The documented fix is to change `os.environ.setdefault(...)` to direct assignment `os.environ["DJANGO_SETTINGS_MODULE"] = "..."` in `wsgi.py`, *or* to use mod_wsgi daemon mode with one process per site (the recommended approach). Source: [mod_wsgi deployment docs](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/mod_wsgi/) (this exact warning; note the doc path is `wsgi/mod_wsgi/` — `wsgi/modwsgi/` 404s).

This traces back to two historical Django tracker tickets:
- [#18518](https://code.djangoproject.com/ticket/18518) — original report that `wsgi.py`'s `setdefault()` doesn't overwrite `DJANGO_SETTINGS_MODULE` under Apache prefork when multiple Django apps share a process, so the second app silently inherits the first app's settings. Django's maintainers **did not** change the generated template; they resolved it by adding documentation (the mod_wsgi doc warning above) instead, explicitly to preserve `setdefault()`'s behaviour of respecting an externally-set env var (useful for gunicorn-style workflows where the launcher sets the var).
- [#18559](https://code.djangoproject.com/ticket/18559) — duplicate/related report, with mod_wsgi's author Graham Dumpleton explaining the underlying mechanism: `os.environ` is process-wide, so under mod_wsgi sub-interpreters, "the first wsgi.py in any sub interpreter will win for the whole process" because setting `os.environ` leaks across sub-interpreters sharing the process. Marked duplicate of #18518.

This is a real, named footgun, but it is about **multiple sites sharing one process** (an Apache/mod_wsgi-specific problem), not directly about "dev settings leaking into prod" — it's adjacent, not identical, to the safety question below.

---

## 2. What real split-settings projects do in `wsgi.py`/`asgi.py`

### cookiecutter-django (most widely used Django project template with split settings)

Verified by fetching the raw files directly from the `master` branch:

`config/wsgi.py`:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
```

`config/asgi.py`:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
```

**This is an inconsistency inside cookiecutter-django itself**: the WSGI entrypoint defaults to the *production* settings module, while the ASGI entrypoint defaults to the *local* (dev) settings module, in the same generated project, side by side. I could not find a GitHub issue in the cookiecutter-django tracker that names this discrepancy explicitly (searched issues; found only tangential ones about running uvicorn locally, #3039, and websocket support, #2506) — it may be an unintentional drift between the two files rather than a documented design decision. Treat this as a *counter-example showing the two choices coexisting even within one well-regarded template*, not as evidence either choice is "correct."

Sources: [config/wsgi.py](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/wsgi.py), [config/asgi.py](https://github.com/cookiecutter/cookiecutter-django/blob/master/%7B%7Bcookiecutter.project_slug%7D%7D/config/asgi.py)

### django-split-settings (wemake-services)

This library's own docs/examples focus on composing one settings package via `include()`, and typically leave `DJANGO_SETTINGS_MODULE` pointed at that package's `__init__.py` (i.e., there's usually still just one resolvable module, unlike FLS's three top-level files with no single default). I did not find an authoritative django-split-settings example that specifically discusses what `wsgi.py`/`asgi.py` should default to when there is no single "settings" module — their examples generally assume `DJANGO_SETTINGS_MODULE` is set explicitly per environment. This is a gap in what I could find, not a finding of "they say don't default."

Sources: [django-split-settings README](https://github.com/wemake-services/django-split-settings), [Django wiki: SplitSettings](https://code.djangoproject.com/wiki/SplitSettings)

### DjangoTricks — explicit "remove setdefault for multi-environment projects" recommendation

A DjangoTricks tip ("About Default DJANGO_SETTINGS_MODULE") states the opposite recommendation from cookiecutter-django/Django's template — for projects with multiple settings files per environment (dev/test/staging/prod), it advises **removing** the `setdefault(...)` line from `manage.py`, `wsgi.py`, and `asgi.py` entirely:

> "If you use multiple Django project settings files for different environments (dev, test, staging, production), then better remove the ... line from manage.py, wsgi.py, and asgi.py: `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demo.settings')` This will force you to always set the DJANGO_SETTINGS_MODULE environment variable ... and will save you from unwanted behavior (like migrating a wrong database) when you mismatch the environments."

This is directly on point for FLS's situation (three settings modules, no canonical single one) and is option (c) from the question — "drop `setdefault` and require the env var." Source: [DjangoTricks — About Default DJANGO_SETTINGS_MODULE](https://www.djangotricks.com/tricks/7PZYEhpk96WV/) (page blocks direct fetch with HTTP 403; content above is reconstructed from indexed search-result text, so treat the exact wording as approximate, though the substance is corroborated by the search engine's cached snippet).

### Summary table of what I found

| Project / source | Choice | Rationale given |
|---|---|---|
| `django-admin startproject` (Django core template) | (a)/(b) undifferentiated — always project's single `settings.py` | N/A — assumes one settings module exists |
| cookiecutter-django `wsgi.py` | (a) points at prod module | No stated rationale found |
| cookiecutter-django `asgi.py` | (b) points at dev/local module | No stated rationale found; likely inconsistent with wsgi.py rather than deliberate |
| DjangoTricks tip | (c) drop `setdefault`, require env var | Explicitly to prevent "unwanted behavior (like migrating a wrong database) when you mismatch the environments" |
| Django's own mod_wsgi docs | neither (a)/(b)/(c) — keep `setdefault` but consider replacing with direct assignment `os.environ[...] = ...` | To fix multi-site-per-process settings bleed under mod_wsgi, unrelated to dev/prod safety |

No source I found makes the case for (a) or (b) explicitly on safety/correctness grounds — cookiecutter-django's choices look like they were made independently for each file without a documented justification, and possibly drifted apart over time.

---

## 3. The safety argument

### Is defaulting a server entrypoint to dev settings a documented footgun?

I found this discussed generically (dev.to/Medium-tier commentary, not Django-official) but consistently: the risk named is that if a deployment forgets to set `DJANGO_SETTINGS_MODULE` and the entrypoint defaults to a dev-flavoured module, the app can boot with `DEBUG=True`, which Django's own deployment checklist treats as a serious, named risk:

> Running `django-admin check --deploy` (or `manage.py check --deploy`) against your production settings "will warn you about production security misconfigurations, such as DEBUG set to True in deployment." `DEBUG=True` in production exposes stack traces, local variables, installed apps, and settings values to any triggering request.

This is Django's own documented guard mechanism (`check --deploy`), not a guard against the *entrypoint defaulting to dev settings specifically* — it's a general pre-deploy linter that would catch dev-flavoured settings regardless of *how* they got selected. I could not find a Django-official statement saying "never let wsgi.py default to a dev module" — the "it all depends on how you organize your settings" line (Section 1) is the closest Django comes to a position, and it takes none.

Sources: [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)

### Is there a real cost to dropping `setdefault` entirely (option c)?

I found no evidence that gunicorn, uvicorn, daphne, `runserver`, or mod_wsgi *rely on* the WSGI/ASGI entrypoint module providing a default value for `DJANGO_SETTINGS_MODULE`:

- **gunicorn / uvicorn / daphne**: these are invoked pointing at the WSGI/ASGI *module and attribute* (e.g. `gunicorn myproject.wsgi:application`, `uvicorn myproject.asgi:application`). They import that module and use whatever `application` object it produces; they don't inspect or require `DJANGO_SETTINGS_MODULE` themselves. If `wsgi.py`/`asgi.py` has no `setdefault` and the env var isn't set some other way, `get_wsgi_application()`/`get_asgi_application()` fails immediately with the `ImproperlyConfigured` message from Case A above — loudly, at process start, before serving any request.
- **`runserver`**: this goes through `manage.py`, not `wsgi.py`/`asgi.py` — `manage.py`'s own `setdefault` (already correctly pointing at `config.settings_dev` in FLS) is what matters for `runserver`, independent of whatever `wsgi.py`/`asgi.py` say.
- **mod_wsgi**: the only place I found an actual *reliance* on `wsgi.py` providing the value is the mod_wsgi multi-site-per-process scenario (Section 1) — and there the officially recommended fix is to *hardcode a specific value with direct assignment*, not to rely on a generic fallback default, so that scenario doesn't argue for keeping a dev/generic default either.

So: I found no ecosystem tooling that breaks if the `setdefault` line is removed, provided something else in the deployment path (env var, `--settings` flag, or process manager config) sets `DJANGO_SETTINGS_MODULE`. The cost of dropping it entirely is operational — a deploy that forgets to set the env var fails to boot instead of running with unintended settings — which the DjangoTricks source (Section 2) frames as the *point*, not a downside.

---

## 4. Precedent for "no default at all"

The clearest concrete precedent is the **DjangoTricks recommendation** already quoted in Section 2 — remove `setdefault` from `manage.py`, `wsgi.py`, and `asgi.py` alike, for exactly FLS's situation (multiple environment-specific settings files, no canonical single module). Its stated payoff is to fail fast rather than risk "migrating a wrong database" or otherwise mismatching environments.

I did **not** find a widely-cited, large-scale open-source Django project (comparable in profile to cookiecutter-django) that ships `wsgi.py`/`asgi.py` with `setdefault` removed and a `raise` or custom message in its place. My searches (cookiecutter-django, django-split-settings docs, Django's own tickets/docs, general web search for "remove os.environ.setdefault wsgi.py") did not surface one. This is a gap: I can confirm the *practice is recommended* by at least one Django-community source, but I cannot point to a well-known reference implementation that does it, so I'm not asserting this is common practice — only that it has a documented rationale and is achievable with plain Django (no wrapper needed).

What the resulting error looks like to an operator who forgot to set the env var, if `setdefault` is simply removed with nothing put in its place: the exact Case A `ImproperlyConfigured` message from Section 1 — `"Requested settings, but settings are not configured. You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings."` — raised at process/import time, before the app serves anything. This is Django's stock message; none of the sources I found add a custom `raise` with project-specific wording in place of the dropped `setdefault`.

---

## Open gaps (things I could not confirm)

- No large reference project found that both (a) has no single canonical settings module *and* (b) deliberately omits `setdefault` in its entrypoints with a custom message — only the DjangoTricks recommendation to omit it, without a public codebase example alongside it.
- Could not fetch djangotricks.com directly (HTTP 403 on `WebFetch`); its exact wording above is reconstructed from a search-engine-indexed snippet, not a verbatim page fetch. The core recommendation (remove `setdefault` for multi-environment projects) is corroborated across two independent search queries, but exact phrasing should be treated as paraphrase-level accurate, not a verified quote.
- No cookiecutter-django issue/PR found explaining *why* `wsgi.py` and `asgi.py` disagree (prod vs. local) — could not determine if this is deliberate or drift.

status: ok
