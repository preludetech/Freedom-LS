# Research: campaign-attribution capture — how Django does this, and where it breaks

## Findings that would change a design decision

1. **The "same view that creates the account" framing in the draft is right, but the hook has to be
   `custom_signup()` / `save_user()` on the *signup POST*, never anything tied to email confirmation.**
   With `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (`config/settings_base.py:404`), allauth's
   `user_signed_up` signal — and the adapter/form hooks that run in the same request — fire
   **before** the confirmation link is clicked, on the request that submitted the signup form. That
   request is the one carrying the attribution cookie. The confirmation click can happen on a
   different device entirely (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True`,
   `config/settings_base.py:405`, logs the user in on *whichever* browser clicks the link), so
   anything hung off `email_confirmed` or off FLS's own post-verification
   `complete_registration_view` (`freedom_ls/accounts/views.py:77`, gated by
   `RegistrationCompletionMiddleware`, `freedom_ls/accounts/middleware.py`) sees the *confirming*
   browser's cookies, not the *signing-up* browser's. For a mobile email-app click that is very
   often a cookie-less browser. This is not a hypothetical edge case, it's the normal path for
   mandatory-verification signup — resolve it by capturing at signup time, not confirmation time.
   [django-allauth signals docs](https://docs.allauth.org/en/dev/account/signals.html),
   [allauth issue #3963 confirming `user_signed_up` fires pre-confirmation](https://github.com/pennersr/django-allauth/issues/3963)

2. **FLS already has the exact hook and the exact append-only-row precedent for this**:
   `SiteAwareSignupForm.custom_signup(request, user)` (`freedom_ls/accounts/forms.py:133-171`) runs
   synchronously inside the signup POST, already has `request` (cookie-bearing) and `user`, already
   calls `get_client_ip(request)`, and already writes a write-once row (`LegalConsent`) inside a
   `transaction.atomic()` block. The attribution row is the same shape of problem — write once, at
   signup, from a request that has both the visitor's cookies and the freshly-created user — and
   should almost certainly be written from the same place. `AccountAdapter.save_user()`
   (`freedom_ls/accounts/allauth_account_adapter.py:136-156`) is the other real candidate: it is
   where the existing `user.registered` webhook fires, is more central (`ACCOUNT_ADAPTER` is one
   config point; `ACCOUNT_FORMS["signup"]` is a second, independent one a downstream project could
   swap without touching the adapter), but doesn't have direct access to the raw request cookies —
   only to whatever `save_user`'s `request` parameter carries, which is the same request object, so
   this is a wash for cookie access. The real trade-off is architectural: hooking the *form* couples
   attribution capture to `SiteAwareSignupForm` specifically (bypassed if a downstream project
   overrides `ACCOUNT_FORMS`); hooking the *adapter* couples it to `AccountAdapter` (bypassed only if
   a downstream project overrides `ACCOUNT_ADAPTER`, a much rarer override). Prefer the adapter for
   robustness, unless the design wants attribution capture to live beside `LegalConsent`'s
   `custom_signup` for readability.

3. **`django-utm-tracker` already does roughly a third of this feature, is actively maintained, and
   explicitly supports Django 5.2–6.0** — but adopting it is still the wrong call here. It ships a
   pair of middlewares that extract `utm_*`, `gclid`, `fbclid` (and more) into `request.session`
   (anonymous) or a `LeadSource` model (authenticated), which is structurally very close to this
   spec's "cookie + session, then copy to a per-user row at signup." It does **not** capture `ref`
   partner codes tied to an `Organisation`, does not capture `_ga`/`_fbp`/`_fbc`, does not capture
   client IP or user agent, is not site-aware (`LeadSource` has no `Site`/`Organisation` FK — it
   would need wrapping in `SiteAwareModel` regardless), and its own signup-time write happens off
   `request.user` being authenticated on a later request, which has exactly the same
   different-device gap described in point 1 unless its middleware runs on the same request as
   signup. FLS is a **library installed into other Django projects**: adding a third-party
   `INSTALLED_APPS`/`MIDDLEWARE` dependency for roughly a third of the requirement, while still
   writing the `Organisation`-linked `ref` resolution, the ad-cookie capture, IP/UA capture and the
   `SiteAwareModel`/`SiteAwareModelAdmin` integration by hand, is worse than writing the ~150–250
   lines FLS actually needs against its own conventions (`SiteAwareModel`, `get_client_ip`,
   `get_cached_site`). Nothing else surveyed (`django-analytical`, `django-referral`,
   `pinax-referrals`, `django-utm-cookies`) does meaningfully more of this feature — see the "packages
   surveyed" section below.

4. **Middleware placement is constrained two ways, not one.** It must sit after
   `SessionMiddleware` (`config/settings_base.py:151`) to have `request.session` at all — trivial.
   Less obviously: if capture is also expected to *validate* the `ref` code against `Organisation`
   at landing time (rather than deferring all validation to signup), it must sit **after**
   `CurrentSiteMiddleware` (`config/settings_base.py:158`), because `Organisation` is a
   `SiteAwareModel` and its default manager (`SiteAwareManager`,
   `freedom_ls/site_aware_models/models.py:65-76`) reads the current site from the thread-local that
   only `CurrentSiteMiddleware` populates (`freedom_ls/site_aware_models/middleware.py:26-36`). A
   position before `CurrentSiteMiddleware` would see `Organisation.objects` unfiltered/thread-local-empty
   and silently return the wrong queryset semantics. If capture stays "store the raw string, resolve
   it to an `Organisation` only at signup" (recommended — keeps the hot landing-page path DB-free),
   site-awareness doesn't matter for the middleware itself and it can sit anywhere after
   `SessionMiddleware`. `AuthenticationMiddleware` (`config/settings_base.py:154`) is irrelevant to
   the capture middleware (it never reads `request.user`); it only matters to the *consumption* side
   (`custom_signup`/`save_user`, which already run after `AuthenticationMiddleware` naturally since
   they're inside the signup view). Note also that `WhiteNoiseMiddleware` runs **before**
   `SessionMiddleware` (`config/settings_base.py:150-151`), so static/media requests never reach any
   session-touching middleware — one less thing to exempt by hand, unlike
   `RegistrationCompletionMiddleware`'s explicit `_exempt_path_prefixes()`
   (`freedom_ls/accounts/middleware.py:49-68`), which exists only because that middleware runs late
   enough (after `AccountMiddleware`) that static/media paths *do* reach it.

5. **Session lifetime and cookie lifetime disagree by design, and that needs to be resolved
   explicitly, not left implicit.** Nothing overrides `SESSION_COOKIE_AGE`, so the session cookie
   is Django's default 2 weeks in dev and explicitly 2 weeks in prod
   (`SESSION_COOKIE_AGE = 1209600`, `config/settings_prod.py:50`). The spec's attribution cookie is
   90 days. If a design leans on `request.session` as anything other than a same-visit convenience
   cache, a visitor who lands via an ad and signs up 20 days later has a live 90-day attribution
   cookie but a long-expired session — the signup-time read must be from the **cookie**, with the
   session (if kept at all) treated as a within-visit optimisation only, never the source of truth.

## 1. Packages surveyed

| Package | Maintained / Django 5–6 | What it actually does | Verdict |
|---|---|---|---|
| [django-utm-tracker](https://github.com/yunojuno/django-utm-tracker) | Yes — states Python 3.12+, Django 5.2–6.0 support | Two middlewares extract `utm_*`, `gclid`, `fbclid` (+ configurable custom tags) from the querystring into `request.session` (anon) or a `LeadSource` FK'd to `request.user` (authenticated); no `ref`/partner code, no ad-cookie capture (`_ga`/`_fbp`/`_fbc`), no IP/UA, not site-aware | Closest match; still leaves most of this spec unbuilt and adds a dependency for a fraction of the work. Not recommended — see finding 3. |
| [django-analytical](https://django-analytical.readthedocs.io/) (Jazzband) | Maintained | Template-tag/context-processor glue for *third-party* analytics services (GA, GTM, Mixpanel, etc.) — injects tracking snippets into templates. No server-side capture, no DB model, not the same problem at all | Not applicable |
| [django-referral](https://djangopackages.org/packages/p/django-referral/) | Stale (last significant activity years old per Django Packages listing) | Referral-link generation + campaign pattern matching for a referrer→campaign mapping | Not maintained enough to trust for a currently-Django-6 project; also solves a different problem (referral-link publishing, not ad-campaign capture) |
| [pinax-referrals](https://github.com/pinax/pinax-referrals) | Actively maintained, Django 3.2–6.0 tested per its own docs | Lets *users* publish referral links to pages/objects and records responses; supports anonymous referral codes for promotions | Different product shape — it's a "refer-a-friend" system with its own `Referral`/`Response` models, not a passive UTM/ad-cookie capture layer. Wrong fit even though it's healthy. |
| django-utm-cookies | Small, low-activity | Middleware that stores UTM params directly in cookies, no DB persistence, no signup integration | Too thin to be worth the dependency over writing the cookie-set logic directly |
| "django-marketing-attribution" | Does not exist as a real package | — | — |

Given FLS's constraints — multi-tenant (`Organisation`/`Site` scoping), a library installed into
other Django projects (every added runtime dependency is a cost every downstream project inherits),
and a payload shape (`ref`→`Organisation`, ad-network cookies, IP/UA) no surveyed package covers —
writing this in-house against FLS's existing `SiteAwareModel`, `get_client_ip`, and admin
conventions is the right call. The one thing worth borrowing conceptually from
`django-utm-tracker` is its two-stage shape (capture middleware → session, then a second write on
the authenticated path) — but FLS should collapse that second write into the *signup-request* hook
(finding 1–2), not a later authenticated-request middleware, precisely because of the
different-device gap that shape has.

## 2. Where in the middleware chain

Current order (`config/settings_base.py:147-163`):

```
SecurityMiddleware → ContentSecurityPolicyMiddleware → WhiteNoiseMiddleware →
SessionMiddleware → CommonMiddleware → CsrfViewMiddleware → AuthenticationMiddleware →
MessageMiddleware → HtmxMessagesMiddleware → XFrameOptionsMiddleware →
CurrentSiteMiddleware → AccountMiddleware → RegistrationCompletionMiddleware → AxesMiddleware
```

- **Must be after `SessionMiddleware`.** `request.session` doesn't exist before it; writing to it
  earlier raises `AttributeError`.
- **Should be after `CurrentSiteMiddleware`** only if the middleware itself needs to resolve
  `Organisation` rows (see finding 4) — otherwise this constraint doesn't bind and the natural slot
  is right after `SessionMiddleware`, before `CommonMiddleware`, so it runs as early as possible on
  every request that reaches Django (not blocked by anything that might short-circuit — e.g.
  `CommonMiddleware`'s `APPEND_SLASH` redirect happens *after* this point either way, so a redirect
  doesn't cost a second capture; capturing before `CommonMiddleware` means the *original* landing
  URL — with its querystring — is what gets read, before any URL-rewriting middleware touches it).
- **`AuthenticationMiddleware` does not matter to the capture middleware.** It never reads
  `request.user`, only `request.GET`/`request.COOKIES`/`request.session`.
- **`CsrfViewMiddleware` does not matter.** Setting a cookie / writing to session in a GET view
  chain doesn't touch CSRF at all; CSRF only gates unsafe methods.

## 3. The signup hook

Established above (finding 1–2). Summary of every candidate and what request it actually sees:

| Hook | Has the signup-browser's request/cookie? | Notes |
|---|---|---|
| `user_signed_up` signal | Yes — fires synchronously in the signup view, pre-confirmation | Standard allauth signal; receives `request` and `user`. [Signal docs](https://docs.allauth.org/en/dev/account/signals.html) |
| `AccountAdapter.save_user()` (`freedom_ls/accounts/allauth_account_adapter.py:136`) | Yes — same request | Already FLS's hook for `user.registered` webhook; most central override point |
| `SiteAwareSignupForm.custom_signup()` (`freedom_ls/accounts/forms.py:133`) | Yes — same request | Already FLS's hook for `LegalConsent`; bypassed if `ACCOUNT_FORMS["signup"]` is swapped by a downstream project |
| `email_confirmed` signal | **No, unreliable** — request is whatever browser clicked the link | Different device/browser is the normal case for mandatory email verification, not an edge case |
| `RegistrationCompletionMiddleware` / `complete_registration_view` (`freedom_ls/accounts/views.py:77`) | **No, unreliable** — same reasoning; this middleware only fires on an *authenticated* request, and `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION=True` logs the user in on whichever browser confirmed | Wrong layer for this: it exists to gate *additional registration forms*, not to capture ambient browser state |

**Conventional resolution** (confirmed by allauth's own community/issue tracker discussion of this
exact gap,
[allauth issue #3963](https://github.com/pennersr/django-allauth/issues/3963)): capture attribution
strictly at signup submission time, reading the *cookie* (not `request.session`, which may already
be stale by the time of signup — see finding 5) that was set on an earlier, unrelated landing-page
visit. Do not attempt to attribute at confirmation time; if the confirming device differs from the
signup device, that is expected and out of scope — the row is written once, at signup, from
whatever cookie exists on that request (possibly none, if the visitor never landed with query
params in this browser at all).

## 4. Cookie handling in Django

- **Setting from middleware**: `response.set_cookie(...)` (or `set_signed_cookie`) on the
  `HttpResponse` returned by `get_response(request)` inside `__call__` — standard for
  new-style middleware.
- **`SameSite`/`Secure` defaults**: Django's own default for `SESSION_COOKIE_SAMESITE` is `"Lax"`
  and FLS's prod settings pin `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_SAMESITE = "Lax"`
  (`config/settings_prod.py:36-38`). `Lax` is correct for this cookie too: the landing hit that sets
  it always arrives via a top-level navigation (clicking an ad/link), which `Lax` permits; nothing
  about this feature needs `SameSite=None` (which would additionally require `Secure` unconditionally
  and is reserved for cross-site iframe/fetch scenarios this feature doesn't have).
  [Django sessions docs](https://docs.djangoproject.com/en/6.0/topics/http/sessions/)
- **Signed vs plain**: `request.set_signed_cookie(key, value, salt=...)` /
  `request.get_signed_cookie(key, salt=...)` are cheap and worth using here — not to keep the
  *content* secret (query params are public by nature) but to stop a visitor from hand-writing the
  cookie directly to claim a referrer/`Organisation` attribution they were never actually referred
  through (bypassing the `?ref=` query param entirely). Signing doesn't prevent someone from simply
  visiting `?ref=<code>` themselves — that's inherent to the feature — it only prevents *cookie*
  forgery once the value is trusted server-side. Use a distinct `salt` from any other signed cookie
  in the project so a compromise of one doesn't cross-apply.
  [Django cookie signing](https://docs.djangoproject.com/en/6.0/topics/http/sessions/#django.contrib.sessions.backends.base.SessionBase)
- **Size**: RFC 6265's practical floor is ~4096 bytes per cookie, and Django doesn't fail loud if
  exceeded — browsers silently drop or truncate ([Django ticket #22242, "setting cookie that is too
  large fails silently"](https://code.djangoproject.com/ticket/22242)). This payload — five-plus
  `utm_*` fields, `gclid`/`fbclid`, `ref`, landing path, `Referer` (which can be arbitrarily long —
  a referring search-results URL easily runs several hundred characters), a timestamp, plus signing
  overhead — needs an explicit cap on stored field lengths (especially `Referer` and landing path)
  well before 4096 bytes, and needs to be considered *alongside* the session cookie and CSRF cookie
  that also ride on every request's `Cookie:` header, since intermediary/proxy request-header size
  limits (e.g. nginx's default 8k) are a shared budget, not per-cookie.
- **Interaction with `SESSION_COOKIE_*`**: none structurally — this is an independent cookie with
  its own name/`Max-Age`/`SameSite`/`Secure` — but its `Secure`/`SameSite` values should track the
  same production posture (`SESSION_COOKIE_SECURE = True` only applies in prod,
  `config/settings_prod.py:36`; dev has no HTTPS, so `Secure=True` there would silently prevent the
  cookie from ever being set over `http://localhost`) — whatever setting drives `Secure` needs a
  dev/prod split mirroring how `SESSION_COOKIE_SECURE` itself is only set in `settings_prod.py`.

## 5. Session write behaviour

Django creates an in-memory session object on every request but only **persists** a row to
`django_session` when the session is actually modified (`SESSION_SAVE_EVERY_REQUEST` defaults to
`False`, and nothing in `config/` overrides it — confirmed by grep). FLS also sets no
`SESSION_ENGINE`, so the default `django.contrib.sessions.backends.db` applies (confirmed by grep
across `config/`; corroborated by a prior research note in this repo,
`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/research_housekeeping_command.md:121-144`, which
also records that a `clearsessions`-equivalent housekeeping sweep already runs against
`django_session`, so any session rows this feature creates are already covered by existing
expiry/cleanup — no new sweep needed). `modified` controls whether the row gets written at all;
`accessed`/`expiry` bookkeeping only matters if `SESSION_SAVE_EVERY_REQUEST=True`, which FLS doesn't
set. Practical cost: writing attribution data into `request.session` on a landing GET means one
`INSERT` into `django_session` per such landing — bounded to visits that carry query params (per the
spec, not every anonymous GET), so this is proportional to ad/campaign traffic, not general site
traffic. Whether the session write is worth doing at all, given the durable cookie already exists
and the session expires in 2 weeks vs. the cookie's 90 days (finding 5), is a real design question:
the session buys same-visit convenience (avoids re-parsing the cookie every request within one
visit) at the cost of a DB write on first touch — reading only the cookie in the signup-time hook
and treating the session as optional/absent-tolerant would remove that write from the design's hot
path without losing correctness.

## 6. Client IP

FLS already has a single sanctioned resolver: `get_client_ip()`
(`freedom_ls/accounts/utils.py:20-57`). It reads `config.TRUSTED_PROXY_IP_HEADER`
(`config/settings_base.py:343-348`, default `None`) — when set, it trusts *only* that header's
value whole (never split, unlike `X-Forwarded-For`, which can carry an attacker-supplied chain of
addresses since it's an append-only header some clients set themselves); when unset, it falls back
to `REMOTE_ADDR` directly. This function is already wired to **two** other places, and any new
attribution code must reuse it rather than add a third IP-resolution path:

- `AXES_CLIENT_IP_CALLABLE = "freedom_ls.accounts.utils.get_client_ip"` (`config/settings_base.py:338`)
- `SiteAwareSignupForm.custom_signup()` uses it for `LegalConsent.ip_address`
  (`freedom_ls/accounts/forms.py:142,148`)

A prior research note in this repo already flagged the real-world footgun here: behind a shared
proxy with `TRUSTED_PROXY_IP_HEADER` left unset, `REMOTE_ADDR` becomes the proxy's own Docker-network
address — identical for every visitor
(`spec_dd/3. done/2026-08-30_16:11_prepare-to-deploy/idea.md:103-119`). The same footgun applies
here: a misconfigured deployment would silently write the same `client_ip` value into every
attribution row, not fail loud. That's a deployment-configuration risk inherited from existing
infrastructure, not something new code needs to solve, but it should be named in the idea doc so a
future "why are all our attribution rows the same IP" investigation finds this note.

## 7. Admin patterns

`LegalConsent`'s admin (`freedom_ls/accounts/admin.py:63-91`) is the direct template for a
read-only, append-only, filterable admin on a `SiteAwareModel`:

- Subclasses `SiteAwareModelAdmin` (`freedom_ls/site_aware_models/admin.py:15-18`), which excludes
  the `site` field from the form (`exclude = ["site"]`) since it's set automatically from the
  request thread-local.
- `has_add_permission`/`has_change_permission`/`has_delete_permission` all return `False`.
- Every field is listed in `readonly_fields` as a second line of defence beyond the view
  permissions.
- Model-level defence too: `LegalConsent.save()` (`freedom_ls/accounts/models.py:198-210`) raises
  `ValueError` if called on an existing row (distinguishing via `_state.adding`, since
  `SiteAwareModel`'s UUID pk is populated at instantiation, before any DB row exists) — with an
  explicit docstring caveat that `QuerySet.update()`/`bulk_update()` bypass this silently, which is
  exactly why the admin's own permission methods are the second, independent layer, not a backstop
  that assumes the model guard is sufficient.
- `list_display`/`list_filter`/`search_fields` — `LegalConsentAdmin` filters on
  `document_type`/`document_version` and searches `user__email`/`git_hash`; the attribution admin's
  natural filters are `utm_source`/`utm_medium`/`utm_campaign`/whichever partner `ref` resolves to,
  and search on `user__email`.

For "exportable": FLS already has `unfold.contrib.import_export` installed
(`config/settings_base.py:92`, django-import-export's Unfold integration) — that's the natural
export mechanism (an `ExportMixin`/`ImportExportModelAdmin` on the new admin class) rather than a
hand-rolled CSV view, and it's consistent with what's already available project-wide. **Hazard**:
several of this row's fields are attacker-controlled free text taken verbatim from query params and
the `Referer` header — `utm_campaign`, `ref`, landing path, `Referer`, user agent — with no
sanitisation contract of their own. If any such value begins with `=`, `+`, `-`, or `@`, a CSV
export opened in Excel/Google Sheets executes it as a formula (CSV/formula injection — a known
OWASP class, and one django-import-export has had its own advisories about historically). FLS has
no existing export precedent to lean on for escaping (grepping the codebase for CSV/export handling
turns up no prior art beyond the `unfold.contrib.import_export` app itself), so this needs an
explicit escaping step (prefixing risky leading characters, e.g. with a leading `'` or tab) wherever
the export resource/serializer for these fields is defined — it is not something the admin gets for
free just by using `ImportExportModelAdmin`.

## 8. Testing

FLS's existing middleware test style is plain `django.test.Client` + `pytest.mark.django_db`, no
mocking of the middleware in isolation — see
`freedom_ls/accounts/tests/test_registration_completion_middleware.py:1-56` (asserts response codes
and redirect targets against a real request/response cycle) and
`freedom_ls/accounts/tests/test_signup_messages.py` (drives the *actual* allauth signup +
`EmailConfirmationHMAC` confirmation flow end-to-end, including pulling the confirmation key
directly via `EmailConfirmationHMAC(email_address).key` rather than parsing an email body — the
pattern to reuse for any test that needs to walk signup → confirm).

Awkward parts specific to this feature:

- **Cookie round-trip across the verification hop.** `django.test.Client` persists cookies across
  requests made on the *same* `Client` instance (it behaves like one browser), which is exactly
  right for testing "land with `?utm_source=...` → sign up → row gets the attribution" as one
  continuous flow using a single `Client()`. Testing the different-device gap (finding 1) requires
  the *opposite*: performing the landing GET and signup POST on one `Client()`, then performing the
  confirmation-link GET on a **second, fresh** `Client()` with no shared cookies — asserting the
  attribution row was already written correctly at signup time and is *not* expected to change (or
  break) when confirmation happens cookie-less on a different client. This is the regression test
  that actually proves the design decision in finding 1, not just documents it.
- **Freezing time.** FLS's test dependency for this is `time-machine` (`pyproject.toml:65,145`), not
  `freezegun` (not a dependency here) — any test asserting the stored "first-seen timestamp" or a
  cookie's `Max-Age`/expiry math should use `time_machine.travel(...)`, matching the rest of the
  suite's convention.
- **allauth's mandatory-verification flow in tests.** Signing up under
  `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` does not log the user in immediately and does not
  create a queryable "signed up but unverified" shortcut — tests need the
  `EmailAddress`/`EmailConfirmationHMAC` dance shown in `test_signup_messages.py:76-78` to reach a
  confirmed, logged-in state, which is one extra step beyond a typical `UserFactory()` +
  `force_login()` test and needs to be present in any test exercising the full landing → signup →
  confirm path (as opposed to unit-testing the signup-time hook function directly, which doesn't
  need the confirmation step at all — arguably the cheaper, preferred unit of testing here, since
  finding 1 established the confirmation step is irrelevant to correctness).

status: ok
