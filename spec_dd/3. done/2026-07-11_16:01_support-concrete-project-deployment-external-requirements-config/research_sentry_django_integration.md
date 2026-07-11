# Research: Sentry (sentry-sdk) integration for Django 6.x

## Summary

Sentry's Python SDK (`sentry-sdk`) auto-detects Django and auto-enables `DjangoIntegration`
when Django is installed — you no longer need to import/pass `DjangoIntegration()` explicitly
unless you want to override its defaults (`transaction_style`, `middleware_spans`,
`signals_spans`, `cache_spans`, `http_methods_to_capture`). The SDK is DSN-driven: passing
`dsn=None` or an empty string makes `init()` a safe no-op (SDK installs a disabled/no-op
client, does not raise). `environment` and `release` are the two fields meant to distinguish
staging/prod and code version respectively, and both can come from env vars natively
(`SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`) or be passed explicitly. Sentry's own docs recommend
initializing in `settings.py`, but Sentry's own GitHub issue tracker (and the Django community)
flags that as an anti-pattern for projects with layered settings — an `AppConfig.ready()` hook
in a dedicated small app (or a dedicated module imported once) is safer, especially for FLS's
`settings_base.py` → `settings_prod.py` inheritance. The `sentry-debug/` + `trigger_error`
(`1/0`) view is genuinely Sentry's official verification snippet, but it is a live crash
endpoint with **no built-in access control** — Sentry's docs don't warn about this, but it
should not ship to production without being gated (staff-only, non-prod only, or removed after
verification). `send_default_pii=True` attaches user id/email/username and full request data
(headers, form data, JSON bodies, IP) to every event — this is a real data-management decision,
not just a toggle.

## 1. Modern `sentry_sdk.init()` for Django

- `DjangoIntegration` is one of Sentry's **auto-enabling integrations**: when the SDK detects
  Django is installed, it enables the integration automatically (controlled by
  `auto_enabling_integrations=True`, the default). You only need
  `integrations=[DjangoIntegration(...)]` if you want non-default behavior.
- Sentry's current official "getting started" snippet for Django:
  ```python
  import sentry_sdk

  sentry_sdk.init(
      dsn="...",
      send_default_pii=True,
      traces_sample_rate=1.0,
      profile_session_sample_rate=1.0,
      profile_lifecycle="trace",
      enable_logs=True,
  )
  ```
  Note this is a "capture everything" onboarding default (`traces_sample_rate=1.0`,
  full profiling, PII on) — fine for a wizard, **not** appropriate to copy verbatim into
  production without dialing rates down.
- Key options and defaults (from Sentry's Python options reference):
  - `dsn` — default `None`; if unset, SDK sends nothing. Can also come from `SENTRY_DSN` env var
    (explicit `dsn=` kwarg takes precedence over the env var).
  - `environment` — default `"production"` (!) if unset; freeform string; also readable from
    `SENTRY_ENVIRONMENT`.
  - `release` — default `None`; SDK will try to auto-detect (git SHA, CI env vars) if not set,
    but Sentry explicitly recommends setting it manually so it stays in sync with your deploy
    tooling; readable from `SENTRY_RELEASE`.
  - `traces_sample_rate` — default `None` (tracing off). Production guidance: a low rate like
    `0.1` (or lower) to control ingest cost/volume; `0` disables new traces.
  - `profiles_sample_rate` — default `None`; sampled *relative to* `traces_sample_rate`, so it
    only fires when tracing is enabled — requires tracing to be turned on first.
  - `send_default_pii` — default `None`/falsy; see §4.
  - `debug` — default `False`; not recommended in production (log volume).

## 2. Making Sentry optional / graceful (no DSN → no-op)

- The SDK is explicitly designed to tolerate a missing/empty DSN: "Python SDK is okay with
  either an empty string or `None`" — `sentry_sdk.init(dsn=None)` (or omitting `dsn` and having
  no `SENTRY_DSN` env var) results in a disabled no-op client. It does not raise, and no data is
  sent.
- The idiomatic pattern seen in the wild:
  ```python
  dsn = os.environ.get("SENTRY_DSN")
  if dsn:
      sentry_sdk.init(dsn=dsn, ...)
  ```
  This is largely belt-and-suspenders since `init(dsn=None)` is already safe, but the explicit
  `if dsn:` guard makes intent obvious and avoids evaluating other Sentry-only settings (release
  detection, etc.) when Sentry isn't configured at all — useful for local dev / CI where you may
  not want the SDK doing any work (e.g., git-based release auto-detection) even as a no-op.

## 3. Staging vs prod separation

- `environment` is the mechanism Sentry provides specifically for this ("think staging vs
  production"). It's a freeform string, not constrained by Sentry. Set via `SENTRY_ENVIRONMENT`
  env var or `environment=` kwarg — for FLS this maps naturally to reading an existing
  concrete-project env var (e.g. `DJANGO_ENV` / `DEPLOY_ENVIRONMENT`) and passing it through,
  rather than introducing a second, possibly-inconsistent flag.
- `release` is the versioning axis (which code is deployed), independent of `environment`
  (which deploy target it's in). Recommended values: SemVer, CalVer, or git commit SHA, ideally
  prefixed with a package identifier (e.g. `"freedom-ls@2026.07.10"` or `"freedom-ls@<git-sha>"`).
  Sentry's SDK will auto-detect git SHA from a local `.git` if present, but auto-detection in a
  containerized/deployed environment (no `.git` dir, or a shallow clone) is unreliable — **for
  staging/prod, explicitly set `release` from a build-time env var** (CI-injected git SHA or
  version tag) rather than relying on auto-detection.
- One codebase, multiple environments: this is exactly Sentry's supported model — same DSN
  (same Sentry project) but different `environment` tag per deploy, so events group per-release
  and filter per-environment in the Sentry UI. No need for separate Sentry projects unless you
  want hard data isolation between staging and prod.

## 4. `send_default_pii=True` implications

- With `django.contrib.auth` active (as FLS has, via `accounts.User`), enabling
  `send_default_pii` attaches **current user id, email address, username** to every event.
- It also attaches **full request data** to all events: HTTP method, URL, request headers, form
  data, and JSON payloads.
- This is a real data-management/compliance decision, not a harmless verbosity toggle — it means
  Sentry (a third-party SaaS, unless self-hosted) will receive learner emails/usernames and
  potentially sensitive form payloads (e.g. assessment answers, PII in profile forms) on every
  captured error/transaction. Sentry's own guidance: enable cautiously and use their "Sensitive
  Data" scrubbing features (`before_send` hooks, data scrubbing settings) to redact what you
  don't want sent, rather than leaving `send_default_pii=True` blanket-on with no scrubbing.
  This should be flagged as an explicit decision to make (see Gotchas below), not silently
  copied from the starting snippet.

## 5. The debug/test endpoint (`sentry-debug/` + `trigger_error`)

- Yes — this is Sentry's own current official verification snippet, shown as the "Verify" step
  in their Django integration docs:
  ```python
  from django.urls import path

  def trigger_error(request):
      division_by_zero = 1 / 0

  urlpatterns = [
      path('sentry-debug/', trigger_error),
      # ...
  ]
  ```
- Caveat: Sentry's own docs include **no warning** about access control, and the view has none —
  it's an unauthenticated URL that deliberately throws a 500. That's acceptable transiently for
  a manual smoke test, but leaving it reachable in production is a minor liability (noise/abuse
  vector, and a permanent guaranteed-crash endpoint). Recommended handling (decision for the
  spec, not yet made): either (a) gate it behind `staff_member_required`/superuser check, (b)
  only wire the URL when `DEBUG` or a non-prod flag is true, or (c) treat it as a one-time
  manual verification step removed from the codebase after confirming events reach Sentry. FLS
  convention favors explicitness (`get_object_or_404`-style patterns, no implicit magic), so
  gating behind an env-conditional URLconf include is likely the cleanest fit.

## 6. Where `init()` should live

- Sentry's official docs say: initialize in `settings.py`.
- However, Sentry's own docs-repo issue tracker (getsentry/sentry-docs #5326) flags this as
  problematic for projects with **layered/inherited settings** — which is exactly FLS's shape
  (`settings_base.py` → `settings_prod.py`, and presumably per-concrete-project overrides on top
  of that). Problems cited: init-on-import makes it hard to override Sentry config cleanly
  across a base → environment-specific → project-specific chain, and mixes app-initialization
  side effects into what should be declarative settings.
- The suggested alternative: put the `sentry_sdk.init(...)` call inside an `AppConfig.ready()`
  hook in a small dedicated app (or existing low-level app like `base`), added early in
  `INSTALLED_APPS`, reading its config values (`dsn`, `environment`, `release`, etc.) off
  `django.conf.settings` at that point (settings are fully loaded by the time `ready()` runs,
  avoiding the "apps aren't loaded yet" class of errors some users hit with DRF + Sentry when
  init runs too early).
- Ordering constraint: init must happen before requests are served / before other apps that
  should be traced are used, but does **not** need to happen before Django's own settings module
  finishes executing — `ready()` runs after settings are fully loaded and the app registry is
  populated, which is actually *later* and *safer* than settings.py-time init, not earlier.
- Known pitfall: dev-server autoreload can cause Django to load the app registry (and thus
  `ready()`) more than once in some scenarios; if `ready()` isn't idempotent this can
  double-init. Guard with a module-level "already initialized" flag if this matters (mainly a
  dev-server concern, not typically an issue under gunicorn/uwsgi in prod, but cheap to guard
  regardless).

## 7. Dependency / install

- Package: `sentry-sdk` on PyPI. Base install works for all frameworks — Django support is
  built into the SDK's `integrations.django` module, not a separate package.
- Optional extras exist per-integration, e.g. `sentry-sdk[django]`, which additionally pulls in
  packages needed for tighter integration in some configurations. Per project convention:
  ```
  uv add "sentry-sdk[django]"
  ```
  (Plain `uv add sentry-sdk` also works — DjangoIntegration auto-enables regardless — but the
  extra is the documented, explicit spelling and costs nothing extra to include.)
- Profiling (`profiles_sample_rate` / continuous profiling) requires SDK ≥ 1.18.0 for
  transaction-based profiling; continuous profiling APIs (`profile_session_sample_rate`,
  `profile_lifecycle`) are newer and were still marked experimental prior to SDK 2.24.1 — worth
  pinning a recent `sentry-sdk` version if profiling is wanted, and treating profiling as
  optional/deferred rather than day-one scope.

## Recommended config sketch for FLS staging + prod

Not a final spec — for idea-refinement purposes only.

```python
# freedom_ls/base/apps.py (or a new tiny app, added early in INSTALLED_APPS)

from django.apps import AppConfig
from django.conf import settings


class BaseConfig(AppConfig):
    name = "freedom_ls.base"

    def ready(self) -> None:
        dsn = getattr(settings, "SENTRY_DSN", None)
        if not dsn:
            return  # local/dev/unconfigured deploys: no-op, nothing sent

        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
            release=getattr(settings, "SENTRY_RELEASE", None),  # e.g. git SHA injected at build time
            traces_sample_rate=getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1),
            send_default_pii=getattr(settings, "SENTRY_SEND_DEFAULT_PII", False),
        )
```

- `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` sourced from environment variables per
  project convention ("never hardcode credentials... come from environmental variables").
- `SENTRY_ENVIRONMENT` set to `"staging"` / `"production"` per deploy target.
- `SENTRY_RELEASE` set to the deployed git SHA or version tag by CI, not left to SDK
  auto-detection.
- `traces_sample_rate` defaulted low (e.g. `0.1`) for cost control; can be raised temporarily
  when debugging a specific issue.
- `send_default_pii` defaulted to `False` — an explicit opt-in per environment, not inherited
  blindly from the starting snippet, given FLS handles learner PII.
- `sentry-debug/` URL only wired when a non-prod flag is set, or gated to staff/superuser.

## Gotchas / decisions to make

- **`send_default_pii=True` vs FLS's learner data** — needs an explicit decision, not a default
  carry-over from the starting snippet. Consider `before_send` scrubbing if PII is wanted for
  debugging but full request bodies are not.
- **Where does `SENTRY_ENVIRONMENT` come from?** Should reuse whatever env-distinguishing
  variable the concrete-project deployment already sets (if one exists) rather than inventing a
  second one — needs a look at how `settings_prod.py` currently distinguishes staging vs prod
  (if at all).
- **`release` source** — needs a concrete answer: is there already a CI-injected git-SHA/version
  env var in the deployment pipeline this can hook into, or does one need to be added?
  Auto-detection is not reliable enough for prod.
- **`sentry-debug/` endpoint** — decide gating strategy (staff-only / non-prod-only / manual
  removal after verification) before shipping; Sentry's own docs are silent on this risk.
- **`AppConfig.ready()` vs settings.py** — given FLS's `settings_base.py` → `settings_prod.py`
  inheritance (and presumably per-concrete-project layering on top again), `ready()` in a small
  early app is the safer fit; confirm which existing app (`base`?) is the natural home, or
  whether a new minimal app is warranted.
- **Package extra** — decide between plain `sentry-sdk` and `sentry-sdk[django]`; functionally
  near-equivalent today, but `[django]` is the documented spelling.
- **Profiling** — treat `profiles_sample_rate`/continuous profiling as an optional follow-up, not
  day-one scope, given version-maturity caveats.
- **Default `environment` is `"production"`** if left unset — a silent footgun if staging forgets
  to set `SENTRY_ENVIRONMENT`; should be enforced/validated rather than left to default.

## References

- Sentry Django integration guide: https://docs.sentry.io/platforms/python/integrations/django/
- Sentry Python configuration options reference: https://docs.sentry.io/platforms/python/configuration/options/
- Sentry Python releases guide: https://docs.sentry.io/platforms/python/configuration/releases/
- Sentry Python default/auto-enabling integrations: https://docs.sentry.io/platforms/python/guides/django/configuration/integrations/default-integrations/
- Sentry Python integrations config (Django): https://docs.sentry.io/platforms/python/guides/django/configuration/integrations/
- Sentry Python profiling setup: https://docs.sentry.io/platforms/python/profiling/
- sentry-sdk on PyPI: https://pypi.org/project/sentry-sdk/
- sentry-python source (Django integration module): https://github.com/getsentry/sentry-python/blob/master/sentry_sdk/integrations/django/__init__.py
- GitHub issue: "Don't suggest using settings file for Django integration": https://github.com/getsentry/sentry-docs/issues/5326
- Debugging Sentry locally in a Django project (community writeup, corroborates settings.py vs AppConfig discussion): https://cscheng.info/2024/11/25/debugging-sentry-locally-in-a-django-project.html

status: ok
