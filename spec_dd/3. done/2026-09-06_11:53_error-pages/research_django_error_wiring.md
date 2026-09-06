# Research: how Django actually serves error pages, and what constrains them in FLS

Scope: Django 6.0 default error-handling machinery as installed in this repo
(`.venv/lib/python3.13/site-packages/django`), cross-referenced against this
project's `config/settings_base.py`, `config/urls.py`, and
`freedom_ls/base/templates/`. No `404.html`/`500.html`/`403.html`/`400.html`/
`403_csrf.html` currently exist anywhere in this project's own template
directories (only vendored third-party test fixtures under `.venv/` match
those filenames — confirmed via glob).

## 1. The template contract

Django's default handlers and template names (`django/conf/urls/__init__.py:6-9`,
`django/views/defaults.py`):

| Status | `handler` | View | Template name | Context passed to `.render()` |
|---|---|---|---|---|
| 404 | `handler404` | `django.views.defaults.page_not_found` | `404.html` | `template.render(context, request)` — **context={"request_path": ..., "exception": ...}, request=request** |
| 403 | `handler403` | `django.views.defaults.permission_denied` | `403.html` | `template.render(request=request, context={"exception": str(exception)})` — **request passed** |
| 400 | `handler400` | `django.views.defaults.bad_request` | `400.html` | `template.render(request=request)` — **context=None, but request passed** |
| 500 | `handler500` | `django.views.defaults.server_error` | `500.html` | `template.render()` — **no arguments at all: context=None AND request=None** |

Source: `django/views/defaults.py:35-150`.

**The 500 case is uniquely starved.** For 404/403/400, Django's backend
`Template.render(context=None, request=None)`
(`django/template/backends/django.py:102-109`) is called *with* `request`, so
`make_context()` builds a `RequestContext` and every configured context
processor runs (`django/template/context.py:290-307`, dispatching to
`RequestContext` when `request is not None`). Only `server_error()` calls
`template.render()` with **zero arguments**, so `request is None`,
`make_context()` builds a bare `Context(None)`, and **no context processor
runs at all** — not even the builtin `django.template.context_processors.csrf`
one, and `request` itself is not in the template's namespace (confirms and
sharpens the task brief's premise: it is only `handler500` that is starved
this way; 404/403/400 render with the project's normal `RequestContext`,
including all five app context processors, `auth`, `messages`, and `csp`).

If no `500.html` exists, Django serves a bare hardcoded `ERROR_PAGE_TEMPLATE`
string (title "Server Error (500)", no details) via
`HttpResponseServerError(...)` — no branding at all
(`django/views/defaults.py:16-26,93-98`). Same pattern for 404/403/400 if
their templates are absent, each with `TemplateDoesNotExist` re-raised only
when a *custom, non-default* `template_name` was supplied and is missing
(`django/views/defaults.py:65-68` etc.) — i.e. leaving the defaults means a
missing template silently degrades to Django's stock plain-text-ish page
rather than crashing.

All four decorate with `@requires_csrf_token`
(`django/views/decorators/csrf.py`), which only guarantees the CSRF
*cookie/token machinery* runs on the request (`_EnsureCsrfToken`, a
`CsrfViewMiddleware` subclass whose `_reject` is a no-op) — it does **not**
put `csrf_token` into the render context by itself; that still requires the
`csrf` context processor to run via `RequestContext`, which for 500 never
happens (see §3).

## 2. The template-loader trap — resolved

`config/settings_base.py:169-200` defines exactly **one** `TEMPLATES` backend
(`django.template.backends.django.DjangoTemplates`) with `DIRS: []`,
`APP_DIRS` commented out, and an explicit `OPTIONS["loaders"]`: a single
`django.template.loaders.cached.Loader` wrapping, in order,
`django_cotton.cotton_loader.Loader`,
`django.template.loaders.filesystem.Loader`, and
`django.template.loaders.app_directories.Loader`, plus
`OPTIONS["builtins"] = ["django_cotton.templatetags.cotton"]`.

`DjangoTemplates.__init__` builds `self.engine = Engine(self.dirs,
self.app_dirs, **options)` from that exact `OPTIONS` dict
(`django/template/backends/django.py:16-28`) — so this one configured
`Engine` instance *is* the cotton-aware, filesystem/app-dirs-aware,
`{% extends %}`-capable engine.

Both code paths that matter resolve back to this same engine:

- `defaults.server_error` calls `django.template.loader.get_template(...)`,
  which iterates `django.template.engines.all()` — the engines built from the
  project's `TEMPLATES` setting — and returns the first that has the template
  (`django/template/loader.py:5-19,65-66`). With only one configured backend,
  that backend **is** this project's cotton-loader engine.
- `Engine.get_default()` (used internally by bare `Template(...).render()`
  calls elsewhere in Django, e.g. its own docstring example) is defined as
  "the first `DjangoTemplates` backend that's configured" — it iterates
  `engines.all()` and returns `engine.engine`
  (`django/template/engine.py:87-112`). With one configured backend, this is
  the *same* engine object as above, not a bare/default-constructed one.

**Plain answer: cotton components (`<c-button>`, `<c-icon>`) and
`{% extends "_base.html" %}` (or any other app template) work inside
`500.html`, `404.html`, `403.html`, and `400.html`.** The loader/engine
configuration is identical for error templates and ordinary views — this
project has only one `TEMPLATES` backend, so there is no bare/"vanilla Django"
engine for `Engine.get_default()` to fall back to. What differs for 500 is
purely the **context** available at render time (§3), not template
resolution or the tag/component vocabulary available.

Verified in practice by tracing `login_prompt.html` (which itself uses
`<c-button>`) — nothing in the cotton loader or `{% extends %}` machinery
depends on `request` or context processors; both are pure template-resolution
concerns, resolved before any context is built.

Citations: `.venv/lib/python3.13/site-packages/django/template/loader.py`,
`.venv/lib/python3.13/site-packages/django/template/engine.py:87-112`,
`.venv/lib/python3.13/site-packages/django/template/backends/django.py:16-28`;
https://docs.djangoproject.com/en/6.0/topics/templates/#django.template.loader.get_template

## 3. What is unavailable during a 500

`config/settings_base.py:185-194` configures these context processors (in
order): `django.template.context_processors.request`,
`django.contrib.auth.context_processors.auth`,
`django.contrib.messages.context_processors.messages`,
`freedom_ls.site_aware_models.context_processors.site_config`,
`freedom_ls.accounts.context_processors.signup_policy`,
`freedom_ls.learner_management.context_processors.can_access_educator_interface`,
`freedom_ls.deployment.context_processors.posthog_config`,
`django.template.context_processors.csp`. None of these — nor the always-on
builtin `csrf` processor — run for a 500 (§1). For 404/403/400 they **all**
run normally, since those handlers pass `request`.

What this project's shared chrome (`freedom_ls/base/templates/_base.html`,
extended by `freedom_ls/base/templates/allauth/layouts/base.html:1` via a bare
`{% extends "_base.html" %}`) relies on, and what happens to each when the
context is empty (the 500 case only):

- `request` (`django.template.context_processors.request`) — absent
  entirely. Any `{{ request... }}` reference resolves to Django's
  `string_if_invalid` (empty string by default), silently.
- `user` (`django.contrib.auth.context_processors.auth`) — absent.
  `partials/header_bar.html:19` does `{% if user.is_authenticated %}`; Django
  template `{% if %}` resolves missing variables via
  `ignore_failures=True` and treats them as falsy, so this **does not raise**
  — it silently falls into the `else` branch and renders
  `partials/login_prompt.html` (an unauthenticated header) even if the
  request that 500'd was authenticated.
- `messages` (`django.contrib.messages.context_processors.messages`) —
  absent. `_base.html:75` includes `partials/messages.html`, whose
  `{% for message in messages %}` loops over a missing variable; Django's
  `{% for %}` tag also degrades a missing/`None` iterable to an empty loop
  rather than raising. Net effect: the toast containers render, empty.
- `site_config` → `site_name`, `site_title`, `site_header`,
  `header_logo_static_path`, `favicon_static_path`, `header_title`,
  `header_title_style` (`freedom_ls/site_aware_models/context_processors.py:23-31`)
  — all absent. `_base.html:21` `{% if favicon_static_path %}` — falls to
  `else`, no favicon `<link>` rendered. `partials/header_bar.html:7,12,14`
  — `{% if header_logo_static_path %}` falls to else (no logo image), and
  bare `{{ header_title }}`/`{% if header_title_style %}style="{{
  header_title_style }}"{% endif %}` render as empty text/no style attribute
  — the header shows a **blank title**, not "Freedom Learning System" or the
  configured site name, and no branding image. This is a real, visible
  degradation: whatever product/theme name is configured
  (`HEADER_TITLE`/site name) does not appear on a 500 page unless the design
  hardcodes a fallback.
- `signup_policy` → `allow_signups` — absent.
  `partials/login_prompt.html:6` `{% if allow_signups %}` falls to else — no
  Sign-up button rendered (only the Login button, since
  `{% url 'account_login' as login_url %}` does not need context/request at
  all — URL reversal is independent of context processors).
- `can_access_educator_interface` — absent, but only consumed behind
  `{% if user.is_authenticated %}`, which is already false, so moot.
- `posthog_config` → `posthog_api_key`, `posthog_api_host`, `posthog_ui_host`
  — absent. `_base.html:55` `{% if posthog_api_key %}` falls to else — the
  entire PostHog snippet is skipped. No error, just no analytics capture of
  the 500 event client-side.
- `csp` (`django.template.context_processors.csp`) — absent, but nothing in
  `_base.html`/`header_bar.html`/allauth layout uses `{% csp_nonce %}` or an
  inline `nonce=` attribute (confirmed via grep — no matches), and
  `SECURE_CSP_REPORT_ONLY` already allows `CSP.UNSAFE_INLINE` for
  `script-src`/`style-src` (`config/settings_base.py:475-486`), so the
  missing nonce processor has no observable effect today.
- **`csrf_token`** (builtin `csrf` processor, always injected by
  `RequestContext` regardless of the `TEMPLATES["context_processors"]` list —
  `django/template/context.py:5`, `django/template/engine.py:114-118`) — for
  500 specifically this is also absent, because `RequestContext` itself is
  never constructed (§1). `_base.html:68`
  `<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>` therefore renders
  `hx-headers='{"X-CSRFToken": ""}'` on a 500 page. Any subsequent
  htmx-driven POST issued from that page (e.g. a "retry" button wired as
  `hx-post`) will carry an empty CSRF header and get rejected by
  `CsrfViewMiddleware` — a full page reload is needed to pick up a real
  token. `{% csrf_token %}` used directly in a form on `500.html` renders as
  an empty string too (`CsrfTokenNode.render`,
  `django/template/defaulttags.py:76-93` — falls to the `else` branch since
  `context.get("csrf_token")` is `None`; in `DEBUG=True` this additionally
  triggers a Python `warnings.warn(...)` at render time).

Net: `_base.html`/`header_bar.html`/`messages.html`/`login_prompt.html` are
all written defensively enough (bare `{% if %}`/`{% for %}` around every
context-processor-sourced variable) that a bare `Context` does **not** throw
a `TemplateSyntaxError`/`VariableDoesNotExist` at render time — it degrades
silently to an unbranded, unauthenticated-looking header with no logo/title
and a non-functional CSRF token, on 500 only. 404/403/400 do not have this
problem at all.

## 4. `{% static %}` and CSS during errors

`{% static %}` (`django/templatetags/static.py:95-131`) resolves purely via
`StaticNode.handle_simple()` → `staticfiles_storage.url(path)` (or
`STATIC_URL` join as a fallback) — it reads `django.conf.settings` and the
configured storage backend directly; it never touches `context['request']` or
any context processor. **It works identically whether or not `request`/context
processors are present**, so it works in `500.html` exactly as it does
everywhere else, including the plain `Context` case.

`_base.html:46-50` loads Tailwind via
`<link ... href="{% static 'vendor/tailwind.output.css' %}" />` inside the
overridable `{% block tailwind_css %}` — a single compiled bundle at
`static/vendor/tailwind.output.css`, built by
`npm run tailwind_build`/`tailwind_watch`
(`package.json:13-15`: `_write_active_theme` → `manage.py
write_active_theme_css` → `npx @tailwindcss/cli -i ./tailwind.input.css -o
./static/vendor/tailwind.output.css`).
`freedom_ls/base/management/commands/write_active_theme_css.py` generates
`tailwind.active_theme.css` at `BASE_DIR`, a single `@import` pointing at the
resolved active theme's `static/themes/<slug>/theme.css`
(`settings_base.py` comment block at lines 38-52 confirms `tailwind.input.css`
imports both the default-theme baseline *and* this generated
active-theme import into one cascade, compiled into one output file).
**Confirmed: the active theme's role tokens (colors, etc.) are in the same
`vendor/tailwind.output.css` bundle as every other class used site-wide** —
there is no separate/late-loaded theme stylesheet, so a 404/500 page authored
with the project's existing utility classes (`text-on-header`, `bg-*`,
component classes, etc.) renders with full theming from a single `<link>`,
same as any other page, and this needs no context/request either.

## 5. Custom handlers

Per Django docs and `django/conf/urls/__init__.py:6-9`: assign
`handler404`/`handler403`/`handler400`/`handler500` as
import-path-or-callable module attributes in the **root URLconf**
(`config/urls.py`) — they are looked up specifically there, not in any
included URLconf. None of the four are currently set in `config/urls.py`
(confirmed by reading the file in full — only `urlpatterns` is defined), so
this project is on Django's stock defaults for all four today.

Trade-off of a custom `handler500`: it can supply whatever context it wants
(build it manually — there is no request-driven `RequestContext` for free
unless the custom view explicitly does `render(request, "500.html", {...})`,
which *does* let it recover `request`/context processors, unlike the stock
`server_error`). But **any exception raised *inside* a custom `handler500`
itself is not caught by anything further** — Django's exception-handling
middleware calls `handler500` exactly once as the last resort
(`django/core/handlers/exception.py:139-143`,
`get_exception_response`/`handle_uncaught_exception`); if that call raises,
Django's WSGI/ASGI handler has no further template fallback and the
underlying server (or `django.core.handlers.wsgi`) returns Django's bare,
last-resort plain response (or, under `DEBUG=True`, the debug traceback page)
— i.e. exactly the ugly generic error this project is trying to avoid,
except now with the additional risk that the custom handler's own bug caused
it. A custom `handler500` should stay defensively simple (no DB queries that
can themselves fail, no context processors that can raise) precisely because
it is off the safety net.

`CSRF_FAILURE_VIEW` (default `django.views.csrf.csrf_failure`,
`django/views/csrf.py`) is a **separate** setting from
`handler403`/`CsrfViewMiddleware`'s rejection path — it is not wired through
`ROOT_URLCONF` handler lookup at all, and is not currently set anywhere in
this project's `config/settings_*.py` (grepped — zero matches outside an
unrelated screenshot fixture). Its default view looks for `403_csrf.html`
(`CSRF_FAILURE_TEMPLATE_NAME`) and, when absent (true today), falls back to
reading a **hardcoded builtin template file**
(`django/views/templates/csrf_403.html`) via `Engine().from_string(...)` —
this is a bare `Engine()`, genuinely unconfigured, not this project's cotton
engine, rendered with a plain `Context(c)` — completely bypassing
`_base.html`, cotton, and the theme CSS. **This is the one bare-Django,
totally unbranded failure surface in the whole error-page picture today**,
and it is reachable in production any time a CSRF check fails (stale
form/session, third-party POST, etc.) — distinct from, and currently more
exposed than, the generic `403.html` path (`PermissionDenied`), which *is*
already using the project's engine/loaders once a `403.html` template exists.
Unlike `handler500`, `csrf_failure` **does** pass `request=request` to
`.render()` (`django/views/csrf.py:70`), so a project-authored `403_csrf.html`
would get the full `RequestContext` (all context processors run) — this
failure mode is a "template is missing" gap, not a "context is starved" gap.

Citations: https://docs.djangoproject.com/en/6.0/topics/http/views/#customizing-error-views ;
`django/views/csrf.py`.

## 6. How error pages behave under HTMX

This project loads htmx 2.0.8 globally (`_base.html:25`,
`https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js`). In htmx 2.x,
`htmx:beforeSwap` fires for **every** response regardless of status code, but
`evt.detail.shouldSwap` **defaults to `false` for any non-2xx/3xx response**
(422 is special-cased as swappable-but-marked-error in htmx's default
`responseHandling` table; general 4xx/5xx — which is what 404/403/400/500
error pages are — are not swapped by default). A handler must explicitly set
`evt.detail.shouldSwap = true` (and usually `evt.detail.isError = false`) to
make htmx render a 4xx/5xx body into the target; otherwise the DOM is left
unchanged and htmx instead fires `htmx:responseError`/`htmx:sendError`.
(https://htmx.org/events/#htmx:beforeSwap)

**Confirmed: this project has no global listener for `htmx:responseError` or
`htmx:sendError` anywhere** (grepped `freedom_ls/` — zero matches). So for
any hx-boosted navigation or plain `hx-get`/`hx-post` request that is *not*
targeting `#interface-main`, a 404/403/400/500 response today produces **no
visible change at all** — the user stays on the stale page they were already
looking at, with no toast, no redirect, no indication anything failed, beyond
whatever htmx's own console warning does.

The one exception is `freedom_ls/base/static/base/js/interface-swap-fallback.js`,
loaded unconditionally in `_base.html:34` (deliberately outside any
boosted-swap scope, per the comment at `_base.html:26-33`, because htmx does
not execute `<script>` tags found in a swapped-in `<head>`). It listens on
`document` for `htmx:beforeSwap` and, **only when `evt.detail.target.id ===
"interface-main"`**, checks whether `evt.detail.serverResponse` (the raw
response body string) contains the literal substring `id="interface-main"`.
If it does not — which is exactly what a full-document `404.html`/`500.html`/
`403.html`/`400.html` response body would look like (no course-player shell
markup) — it sets `evt.detail.shouldSwap = false` (redundant with the htmx
default for non-2xx, but also covers *2xx* boosted responses that legitimately
lack the shell, e.g. a redirect target outside the player) and forces
`window.location.href = evt.detail.xhr.responseURL ||
evt.detail.requestConfig.path`, i.e. a **real, full-page navigation** to the
error URL. That reload re-requests the URL as a normal top-level GET, gets
the true status code, and — crucially — **is not itself an htmx request**, so
context processors and the full page shell render normally for 404/403/400
(and the bare-context 500 for status 500). So: any error surfaced while
inside the boosted course-player shell (`#interface-main`) already
self-heals into a correctly-rendered full error page today. Any error
surfaced by htmx activity **outside** that specific target id currently has
no fallback and is silently swallowed by the browser tab staying put.

## 7. DEBUG and testing

- With `DEBUG=True` (the default in `config/settings_dev.py:19`), unhandled
  exceptions never reach `handler500`/`500.html` at all — Django's exception
  middleware serves `django.views.debug.technical_500_response` (the yellow
  traceback page) instead, and `Http404`/`PermissionDenied`/`BadRequest` get
  their own "technical" debug variants
  (`django/core/handlers/exception.py:64-126`). **The only way to see the
  project's actual `404.html`/`403.html`/`400.html`/`500.html` render locally
  is with `DEBUG=False`.**
- `raise Http404(...)` / `raise PermissionDenied(...)` / `raise
  SuspiciousOperation(...)` anywhere in a view is the standard way to trigger
  404/403/400 respectively for manual or automated testing, independent of
  DEBUG.
- To actually trigger a genuine 500 for testing, an unguarded exception (e.g.
  `1/0`) must escape the view — `freedom_ls/deployment/views.py:5-8`
  (`trigger_error`, `@staff_member_required`, mounted at `sentry-debug/` via
  `freedom_ls/deployment/urls.py:8`) already exists for exactly this purpose
  ("deliberate ZeroDivisionError to verify Sentry capture").
- `django.test.Client(raise_request_exception=False)` (or setting
  `self.client.raise_request_exception = False` on an existing client
  instance) is required to see the 500 response object in a test instead of
  having the original exception re-raised into the test —
  `django/test/client.py:790-805` (`check_exception`): by default
  (`raise_request_exception=True`, the constructor default at
  `client.py:1053,1411`) the test client re-raises any exception the view
  produced rather than returning the rendered error response.
- Combine with `django.test.override_settings(DEBUG=False)` (as a decorator,
  context manager, or in a `SimpleTestCase.settings()` block) so the test
  actually exercises `handler500`/`500.html` instead of the debug page —
  per Django's own testing docs for custom error handlers, this typically
  also needs `@override_settings(ROOT_URLCONF=<module>)` if the handler is
  defined outside `config.urls` for the test.
  (https://docs.djangoproject.com/en/6.0/topics/http/views/#testing-custom-error-views)
- `ALLOWED_HOSTS` gotcha: `config/settings_base.py:67` sets `ALLOWED_HOSTS: list[str] = []`,
  and `config/settings_dev.py` does not override it. Django implicitly
  allows `localhost`/`127.0.0.1`/`[::1]` **only when `DEBUG=True`**
  (`CommonMiddleware`/`django.http.request.validate_host` special-case). The
  moment a developer flips to `DEBUG=False` locally to see the real error
  templates (per above), any request whose `Host` header isn't in
  `ALLOWED_HOSTS` raises `DisallowedHost`, itself a `SuspiciousOperation` →
  a *different* 400 response before ever reaching the intended error page
  under test — `ALLOWED_HOSTS` must be set locally (e.g.
  `["localhost", "127.0.0.1"]`) for this DEBUG=False dance to work at all.
- Static files under `DEBUG=False`: `whitenoise.runserver_nostatic` is first
  in `INSTALLED_APPS` (`config/settings_base.py:73`), which disables Django's
  built-in `runserver` static-file serving (normally gated on
  `DEBUG=True`/`--insecure`) in favor of `WhiteNoiseMiddleware`
  (`config/settings_base.py:150`, third in `MIDDLEWARE`, right after
  `SecurityMiddleware`/CSP). WhiteNoise serves static files regardless of
  `DEBUG`, so the Tailwind bundle and any images referenced by `500.html`
  keep working when flipping to `DEBUG=False` locally — no `--insecure`
  flag or extra static-serving gymnastics needed for this project
  specifically (a departure from vanilla Django's own DEBUG=False-breaks-
  runserver-static-serving gotcha).
- `SecurityMiddleware` in dev: no `SECURE_SSL_REDIRECT`/HSTS settings are set
  in `settings_dev.py` (those only appear in `config/settings_prod.py:20-33`),
  so flipping `DEBUG=False` locally does not also trigger an HTTPS redirect
  loop against a plain-HTTP dev server.

## 8. Sentry

Sentry **is wired**: `sentry-sdk[django]>=2.64.0` is a pinned dependency
(`pyproject.toml:34`); `freedom_ls/deployment/apps.py:9-13`
(`DeploymentAppConfig.ready()`) calls `init_sentry()`
(`freedom_ls/deployment/sentry.py:8-18`), which calls `sentry_sdk.init(dsn=...,
environment=..., release=..., traces_sample_rate=..., send_default_pii=...)`
whenever `SENTRY_DSN` is set (no-op otherwise — `sentry.py:10-11`). The
Django integration auto-registers via `sentry_sdk.init(...)` and connects a
listener to Django's `signals.got_request_exception`
(`.venv/lib/python3.13/site-packages/sentry_sdk/integrations/django/__init__.py:201,556`).

**Ordering matters and works in this project's favor for real 500s**:
`django/core/handlers/exception.py:139-143` — for a genuine unhandled
exception (the only path that reaches `handler500`), Django fires
`signals.got_request_exception.send(...)` **before** calling
`handle_uncaught_exception()` (which invokes `handler500`). So by the time a
custom `handler500` runs, Sentry's Django integration has already
synchronously captured the event. This does **not** apply to 404/403/400 —
`get_exception_response()` (`exception.py:162-170`) only sends
`got_request_exception` if the *error-handler callback itself* raises, so a
plain `Http404`/`PermissionDenied`/`BadRequest` is not sent to Sentry by this
mechanism, and correspondingly has no Sentry event ID available to display.

**`sentry_sdk.last_event_id()` no longer exists** — removed in sentry-sdk
2.0.0 (deprecated since 1.40.5); confirmed absent by grep across the entire
installed `sentry_sdk` package in this venv. The design's "Reference
FC-5X-9K2QD7" support-reference idea needs the *current* API instead:
`sentry_sdk.Scope.last_event_id()` — a classmethod added in sentry-sdk 2.2.0
(`.venv/lib/python3.13/site-packages/sentry_sdk/scope.py:406-420`,
`return cls.get_isolation_scope()._last_event_id`), returning the event ID
"most recently captured by the isolation scope, or None if no event has been
captured" (its own docstring also warns delivery to Sentry is not
guaranteed — network/quota/`before_send` can still drop it, so a nonzero ID
is not proof the event arrived). `Scope` is exported directly from
`sentry_sdk/__init__.py:12`, so `sentry_sdk.Scope.last_event_id()` is
reachable without extra imports. This is available to a custom `handler500`
(called after the exception is captured, per the ordering above) but would
be `None` inside 404/403/400 handlers unless something else captured an
event for that request.

Sources:
- https://github.com/getsentry/sentry-python/issues/3049 ("No more last_event_id")
- https://newreleases.io/project/pypi/sentry-sdk/release/2.0.0 (removal in 2.0.0)

status: ok
