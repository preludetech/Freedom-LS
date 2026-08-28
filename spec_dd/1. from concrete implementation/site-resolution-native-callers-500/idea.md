# Idea: make site resolution honour `FORCE_SITE_NAME` for native `contrib.sites` callers

## The bug

Every pre-demo QA suite (`system_qa/00`–`06`) independently hit the same blocker, and it was
traced in full in `system_qa/04_quizzes_and_assessments/login_500_investigation.md`.

On any host/port other than the one literally stored in the `Site.domain` row (in dev that is
`127.0.0.1:8000`), these pages return **HTTP 500** with
`django.contrib.sites.models.Site.DoesNotExist: Site matching query does not exist.`:

- **All allauth entrance pages** — `/accounts/login/`, `/accounts/signup/`,
  `/accounts/password/reset/`, logout, email-verification-sent, etc. The 500 fires on a plain
  **GET** (no form submit), because the context is built on every render.
- **`/sitemap.xml`** — `django.contrib.sitemaps.views.sitemap`.
- **Outbound account email** — `AccountAdapter.send_mail()` (see below), which 500s when an email
  is actually sent (signup / password-reset POST).

### Why `FORCE_SITE_NAME` does not save these paths

FLS resolves the current site through its own `get_cached_site(request)`
(`freedom_ls/site_aware_models/models.py`), which — when `settings.FORCE_SITE_NAME` is set —
looks up `Site.objects.get(name=force_name)` and does **no host matching at all**. That is why
FLS content pages (`/`, `/courses/`) work on any port. The concrete project sets
`FORCE_SITE_NAME = "Local"` in `config/settings_dev.py` precisely so a random dev port resolves
the demo site.

But three callers never go through `get_cached_site()`; they call Django's **native**
`django.contrib.sites.shortcuts.get_current_site(request)` directly:

1. **Vendored django-allauth** (`allauth==65.18.0`) —
   `allauth/account/internal/templatekit.py:get_entrance_context_data()` calls
   `get_current_site(request)` and is invoked from ~16 `get_context_data()` overrides in
   `allauth/account/views.py` (`LoginView`, `SignupView`, `LogoutView`, password-reset views,
   etc.). This is third-party code the project neither owns nor subclasses, and there is **no
   allauth adapter/signal/setting hook** for the `site` value it injects.
2. **`django.contrib.sitemaps`** — the built-in sitemap framework, a second independent native
   caller.
3. **FLS's own `AccountAdapter.send_mail()`** —
   `freedom_ls/accounts/allauth_account_adapter.py` (~line 62) **still** calls native
   `get_current_site(request)` rather than `get_cached_site()`. This one is squarely FLS code and
   was simply missed by the earlier site-resolution sweep
   (`2026-03-13_12:53_bug-FORCE_SITE_NAME-is-ignored-for-existing-sites`), whose table only
   covered `UserManager.get_queryset()`, `AccountAdapter.is_open_for_signup()`, and the xapi
   `hello()` endpoint.

With no `SITE_ID` configured, native `get_current_site()` falls back to
`Site.objects.get(domain__iexact=request.get_host())`. The only `Site` row is `Local` /
`127.0.0.1:8000`, so any other host (e.g. `127.0.0.1:8309`) matches nothing → `DoesNotExist` →
uncaught → 500.

### This is also a latent production risk, not just a dev-port artifact

In production, `config/settings_prod.py` drives `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` from the
`HOST_DOMAIN` env var, but **nothing keeps the `Site.domain` DB row in sync with `HOST_DOMAIN`**.
There is no migration, deploy hook, or startup check asserting `Site.domain == HOST_DOMAIN`. If
`HOST_DOMAIN` is set/changed to a real domain but the `Site` row isn't updated to match exactly
(case, port, `www.` prefix, or a reverse proxy rewriting `Host`), or a second custom/staging
domain is added, production would 500 `/accounts/login/` with the exact same
`Site.DoesNotExist`. So this is a genuinely under-specified site-resolution contract that FLS —
a framework explicitly built for multi-tenancy — should close, not merely a dev workaround.

## Expected fix

Make FLS's site-resolution mechanism cover **native `contrib.sites` callers** too, so the
`FORCE_SITE_NAME` "any host resolves the site" promise holds framework-wide (allauth entrance
pages, sitemaps, and email), in **one** place. The investigation's recommended shape (its
"option b") is a thin, FLS-owned shim installed at app-ready time (in the relevant FLS app's
`AppConfig.ready()`) that wraps `django.contrib.sites.shortcuts.get_current_site` /
`SiteManager.get_current` so that, when `FORCE_SITE_NAME` is set, it returns the forced site
(mirroring `get_cached_site()`'s logic) before any host-based lookup. Because it patches the
native entry point, it fixes allauth, `django.contrib.sitemaps`, and `send_mail()` uniformly —
including the vendored allauth code that has no hook to override.

In addition (belt and braces, and correct regardless of the shim): change FLS's own
`AccountAdapter.send_mail()` (`freedom_ls/accounts/allauth_account_adapter.py`) to use
`get_cached_site()` instead of native `get_current_site(request)`, matching the rest of the
adapter.

### Why not just set `SITE_ID`

`SITE_ID` would short-circuit `get_current_site()` to a PK lookup and technically fix all three
call sites, but it was already rejected for this project:

- `django.contrib.sites`' initial migration seeds `Site(pk=1, domain="example.com")`, so whether
  "Local" lands on pk 1 or 2 depends on migration/seed order and is **not** guaranteed across
  fresh databases — the exact reasoning that produced `FORCE_SITE_NAME` in the first place (see
  the project's own `2026-03-12_09:95_worktree-dx/research_force_site.md`).
- It can't be computed reliably at settings-import time (the DB may not exist yet).
- It is a global, install-wide constant that would silently pin **every** future native
  `contrib.sites` caller to one site, re-introducing single-Site brittleness for a framework that
  is designed for multi-tenancy even though this deployment is single-tenant today.

The shim keeps the `FORCE_SITE_NAME`-driven, name-based resolution FLS already committed to, and
extends it to the callers that currently bypass it.

## Minor adjacent observation (same area, not a separate fix)

At startup FLS logs `Rejected site domain '127.0.0.1:8000' as a legal-docs directory name;
falling back to _default only` (seen in `system_qa/03`). FLS's legal-docs resolver rejects a
`Site.domain` containing a port/colon as a directory name and falls back to `legal_docs/_default/`.
That fallback is harmless **as long as `_default` docs exist**, so it needs no fix here — but it is
worth being aware of when reviewing this area, because it means site-specific legal docs can never
resolve for a port-bearing domain. (The learner-facing legal-docs 404 in `system_qa/01` is a
separate, concrete-project content gap — shipping `legal_docs/_default/{terms,privacy}.md` — and is
**not** FLS work.)

## Sources

- `system_qa/04_quizzes_and_assessments/login_500_investigation.md` (full root-cause trace).
- Reproductions: `system_qa/00_smoke_demo_walkthrough/qa_report.md` (Defect),
  `01_discovery_and_catalogue/qa_report.md` (Bug 2), `02_account_and_authentication/qa_report.md`
  (Bug 1), `03_free_enrolment_and_course_player/qa_report.md` (Issue 1),
  `04_quizzes_and_assessments/qa_report.md` (Finding A), `05_completion_and_dashboard/qa_report.md`,
  `06_application_gated_course/qa_report.md`.
