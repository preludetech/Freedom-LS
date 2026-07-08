# Research: Referral/UTM capture mechanics & anonymous→user session linkage

Scope: Django-specific mechanics for capturing `?ref=` + UTM params on inbound requests, storing an
anonymous-visitor identifier, and reconciling that identifier to a `User` at signup in this
codebase (FLS). Product decisions already fixed (not re-litigated here): track anonymous browsing,
link at signup, support both `ref` and UTM, first-party storage, store-only for now (no attribution
reporting yet).

---

## 1. What to capture, and where

### 1.1 Parameter set

Capture on any inbound request, not just the landing page, since a visitor may land on a
deep link (a specific course) before ever hitting a "home" view:

- `ref` — custom code, opaque string, format owned by the external referral-management system.
  Treat as an untrusted string: cap length (e.g. 64 chars) and store even if it doesn't match a
  known code — this app **only observes**, it doesn't validate against the external system.
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` — the standard five
  ([Google Analytics UTM spec](https://support.google.com/analytics/answer/10917952),
  [GA4 “Manual campaign” article](https://support.google.com/analytics/answer/10917952)).

Only capture when at least one of these keys is present in `request.GET`; don't overwrite an
already-stored attribution with a later request that has no params (see §5 "first-touch vs
last-touch" note) unless a deliberate re-attribution policy is wanted later.

### 1.2 Middleware vs. decorator

**Recommend middleware**, not a decorator or per-view code, for three reasons that matter in this
codebase specifically:

1. Referral links can point at *any* URL — course pages, the home page, a specific
   `student_interface` deep link — so capture can't be tied to one or two views. A decorator
   would need to be applied to every candidate entry view and would be missed on new ones.
2. This codebase already has a precedent for "run on every request, stash something and clean up"
   in `freedom_ls/site_aware_models/middleware.py` (`CurrentSiteMiddleware`, thread-local
   request) and a session-writing middleware in `freedom_ls/accounts/middleware.py`
   (`RegistrationCompletionMiddleware`). A new `ReferralCaptureMiddleware` sitting alongside these
   in `MIDDLEWARE` is the idiomatic shape for this project.
3. Middleware runs before the view and can issue the redirect-to-strip-params response (§6)
   without every view needing to know about it.

Rough shape, consistent with the existing middleware style (`__call__`, no `MiddlewareMixin`):

```python
class ReferralCaptureMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._has_referral_params(request):
            self._capture(request)
        return self.get_response(request)
```

Register it **after** `SessionMiddleware` (needs `request.session`) and after
`CurrentSiteMiddleware` if the captured record should be site-scoped (this app is multi-site via
`site_aware_models`), but it does not need to run after Django's `AuthenticationMiddleware` since
capture logic itself doesn't need `request.user` (anonymous or authenticated both get an anonymous
id assigned/reused — see §3).

Django middleware ordering docs:
https://docs.djangoproject.com/en/stable/ref/middleware/ and
https://docs.djangoproject.com/en/stable/topics/http/middleware/#middleware-order

### 1.3 What to persist per touch

A minimal capture record, keyed by the anonymous visitor id (§2):

- `anonymous_id` (the visitor identifier, not the Django session key — see §2.2)
- `ref` (nullable)
- `utm_source/medium/campaign/term/content` (all nullable)
- `landing_path` (`request.path`, not full querystring — avoid re-storing the very params being
  extracted; also side-steps GET-param log leakage, §6)
- `referrer_header` (`request.META.get("HTTP_REFERER")`, truncated) — useful for later distinguishing
  organic vs. spoofed `ref` codes, but treat as low-trust, attacker-controlled input
- `user_agent` (truncated) — needed for the bot heuristics in §6
- `first_seen_at` / `last_seen_at`
- `site_id` (this app is multi-site; scope every row like the rest of the codebase does)

Store this in a normal Django model (Postgres), not in the session itself — the session is only
storage for the *pointer* (`anonymous_id`), not the accumulating trail, since sessions can be
serialized to cache/db and blowing them up with growing "hit lists" is an anti-pattern the Django
docs explicitly warn about (avoid storing large/complex objects in the session:
https://docs.djangoproject.com/en/stable/topics/http/sessions/#in-development).

---

## 2. Cookie vs. Django session storage for the anonymous identifier

Two related but distinct things are being stored, and conflating them is the most common mistake:

1. **Django's session cookie** (`sessionid`) — Django's built-in mechanism, expires
   (`SESSION_COOKIE_AGE`), rotated by allauth on login for session-fixation protection (§4.4), and
   in this codebase already customized per-environment
   (`config/settings_dev.py:94` sets a per-DB `SESSION_COOKIE_NAME`;
   `config/settings_prod.py` sets `SESSION_COOKIE_AGE = 1209600` (2 weeks),
   `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE`).
2. **The anonymous visitor identifier** — needs to *survive* session rotation/expiry for the
   marketing-relevant window (commonly 30–90 days), which is longer than a typical session
   lifetime and must **not** be invalidated by allauth's login-time session-key rotation.

### 2.1 Recommendation: dedicated first-party cookie, not the Django session

Use a **separate, long-lived, first-party cookie** (e.g. `flsvid` — "FLS Visitor ID") holding an
opaque random token (`uuid4` or `secrets.token_urlsafe`), set directly via
`response.set_cookie(...)`, independent of `request.session`. Rationale:

- **Survives session rotation.** Allauth calls `request.session.cycle_key()` on login (see §4.4),
  which by default preserves session *data* but is exactly the kind of lifecycle event you don't
  want your attribution pointer coupled to. A separate cookie sidesteps the question entirely.
- **Independent expiry window.** `SESSION_COOKIE_AGE` in this codebase is tuned for auth/UX
  concerns (2 weeks in prod). A referral attribution window is a *marketing* decision (e.g. 30/90
  days) and shouldn't be forced to match. Setting the visitor cookie's own `max_age` decouples the
  two.
- **Works for logged-out browsing across session expiry.** If `SESSION_COOKIE_AGE` lapses (or the
  session cookie is a session-only cookie because `SESSION_EXPIRE_AT_BROWSER_CLOSE` is set
  somewhere down the line), a long-lived visitor cookie still identifies the returning anonymous
  browser; the session-keyed approach would silently lose attribution.
- **Simpler backfill query.** The visitor cookie value can be used directly as the FK/lookup key
  from the capture table to the eventual `User` row; no indirection through Django's session store
  table (`django_session`) with its own opaque, rotatable key.

Cookie attributes, mirroring the security posture already set for `SESSION_COOKIE_*` in
`config/settings_prod.py`:

```python
response.set_cookie(
    "flsvid",
    anonymous_id,
    max_age=60 * 60 * 24 * 90,       # 90 days — a marketing decision, tune per product
    httponly=True,                     # no JS access needed; reduces XSS exfiltration risk
    secure=True,                       # prod only, matches SESSION_COOKIE_SECURE
    samesite="Lax",                    # matches SESSION_COOKIE_SAMESITE; survives top-level
                                        # navigation from an external referral link (a `Strict`
                                        # cookie would NOT be sent on the very click that carries
                                        # ?ref=..., which would break capture entirely)
)
```

`SameSite=Lax` (not `Strict`) is load-bearing here: the whole point of the cookie is to be present
on the *first* cross-site navigation (someone clicking a referral link from an external site), and
`Strict` cookies are not sent on that top-level GET navigation in most browsers, defeating capture.
Django cookie docs: https://docs.djangoproject.com/en/stable/ref/request-response/#django.http.HttpResponse.set_cookie

### 2.2 Why not just use `request.session.session_key`

The session key is tempting (it's already there), but:
- It's designed to be **rotated** (login, `cycle_key()`, periodic re-issuance for security), so
  using it as a stable long-term visitor identifier fights the framework.
- Anonymous sessions in Django are **lazy** — a session row/cookie is only created once something
  writes to `request.session`, so simply reading `session_key` before writing anything gives
  `None`. You'd need to force `request.session.save()` on first touch just to mint a key, which is
  wasted session-store I/O for something that isn't session data.
- Session storage backend (db/cache) may not be tuned for the write volume of "every anonymous
  page view," whereas a stateless signed cookie has zero server-side storage cost for the pointer
  itself (the capture *record* still lives in Postgres, keyed by the cookie value).

If a project explicitly prefers to avoid an extra cookie, storing `anonymous_id` as a session
*value* (`request.session.setdefault("anonymous_id", uuid4)`) is workable but then
`SESSION_COOKIE_AGE`/rotation becomes the attribution window and login-time behavior (§4.4) needs
to explicitly re-mint or preserve it — more moving parts for no benefit here.

### 2.3 First-party only (per product decision)

No third-party cookie, no cross-domain tracking pixel. The visitor cookie is set by this Django
app on its own domain in the same response cycle that captures the params — nothing sets it on
another origin. This also sidesteps SameSite/third-party-cookie deprecation entirely, and needs no
cookie-consent-banner special-casing beyond whatever this project already does for
`sessionid` (functional/strictly-necessary first-party cookies are commonly exempt from consent
banners, but that's a legal/compliance call outside this research's scope).

---

## 3. Anonymous browsing trail: recording and backfilling

### 3.1 Recording anonymous views

Every request the capture middleware sees (or a lighter secondary middleware/signal for
non-referral traffic, if the product wants *all* anonymous browsing tracked, not just
referral-tagged sessions) writes/updates a small "visit" or "touch" table keyed by
`anonymous_id`, not by `request.user` (which is `AnonymousUser` at this point and has no PK to
hang a FK off).

Model shape (illustrative — final naming/fields are a design decision, not this research's call):

```python
class ReferralVisit(SiteAwareModel):
    anonymous_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="referral_visits")
    ref = models.CharField(max_length=64, blank=True)
    utm_source = models.CharField(max_length=128, blank=True)
    utm_medium = models.CharField(max_length=128, blank=True)
    utm_campaign = models.CharField(max_length=128, blank=True)
    utm_term = models.CharField(max_length=128, blank=True)
    utm_content = models.CharField(max_length=128, blank=True)
    landing_path = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

`user` starts `NULL` for every anonymous touch. Index `anonymous_id` (and `site_id`, following the
`site_aware_models` convention already used across the codebase) for the backfill query.

### 3.2 Backfilling the user FK at signup

At the moment a `User` is created, look up all `ReferralVisit` rows (and, ideally, the single
"first-touch attribution" summary row) matching the request's `anonymous_id` cookie and set
`user = new_user` on them (`ReferralVisit.objects.filter(anonymous_id=..., user__isnull=True).update(user=new_user)`).
This is the "reconciliation" step described in §4.

Consider *also* writing a small `UserReferralAttribution` (one row per user, first-touch,
immutable) at the same time, separate from the raw trail — cheap to query later ("which users
came from campaign X") without scanning the trail table. This is optional for a store-only-for-now
feature but worth flagging as a natural extension point given "first-touch vs last-touch" isn't
decided yet (§5).

---

## 4. Allauth signup mechanics: where the linkage hook goes

This codebase's signup path already runs through a custom adapter:
`freedom_ls/accounts/allauth_account_adapter.py:AccountAdapter.save_user`, registered via
`ACCOUNT_ADAPTER = "freedom_ls.accounts.allauth_account_adapter.AccountAdapter"`
(`config/settings_base.py:342`). `save_user` is already the place where a domain event is fired
after commit:

```python
def save_user(self, request, user, form, commit=True):
    user = super().save_user(request, user, form, commit=commit)
    if commit:
        from freedom_ls.webhooks.events import fire_webhook_event
        fire_webhook_event("user.registered", {...})
    return user
```

### 4.1 Two viable hook points — and why `save_user` is the better fit here

**Option A — `AccountAdapter.save_user`.** Runs synchronously, inside the view, with `request`
already in scope (needed to read the `flsvid` cookie) and *before* the `user_signed_up` signal
fires (allauth's flow: form validity → `adapter.save_user()` → `complete_signup()` → signal
dispatch). Pro: co-located with the existing `fire_webhook_event("user.registered", ...)` call,
same method, same transaction boundary, same "this is where account-creation side effects live"
convention already established in this file. Con: adapter methods are meant to be about
"decorating" the user-creation step (allauth's own docs frame `save_user` as "instantiate/save the
user instance"), so a large reconciliation query here is a bit of scope creep on the method's
stated purpose — but it's minor and matches existing precedent (the webhook fire is already doing
adjacent "post-creation side effect" work in the same method).

**Option B — `user_signed_up` signal receiver.** Allauth signal, fires after `save_user` and after
allauth's own post-signup housekeeping, with `request` and `user` kwargs
(`allauth/account/signals.py`: *"Provides the arguments `request`, `user`"*). Pro: decoupled —
doesn't touch the adapter file at all, lives in a `signals.py` connected via `AppConfig.ready()`,
which is the idiomatic Django way to add a side effect to "a user just signed up" without editing
someone else's adapter method. This also mirrors how `webhooks/events.py` itself is deliberately
kept as a standalone module the adapter merely calls into, rather than webhook logic being inlined
into the adapter.

**Recommendation: put the reconciliation call in `AccountAdapter.save_user`, alongside the
existing `fire_webhook_event` call**, for one concrete reason: `save_user` is the last point that
definitely has the *unsaved-then-just-saved* `user` object and the original `request` in the same
call, before allauth's own redirect/response construction runs — and this repo has already decided
that adapter method is where "things that must happen when an account is created" go (per the
existing webhook call). Using the `user_signed_up` signal instead is *also correct allauth
practice* and worth using if the reconciliation logic grows complex enough to want its own module
— but starting in `save_user`, calling out to a plain function (e.g.
`freedom_ls.referral_tracking.linkage.reconcile_anonymous_visits(request, user)`), keeps parity
with how `fire_webhook_event` is called (a local import, a plain function call, not inlined logic).

Conceptually:

```python
def save_user(self, request, user, form, commit=True):
    user = super().save_user(request, user, form, commit=commit)
    if commit:
        from freedom_ls.referral_tracking.linkage import reconcile_anonymous_visits
        from freedom_ls.webhooks.events import fire_webhook_event

        reconcile_anonymous_visits(request, user)  # read flsvid cookie, backfill FK
        fire_webhook_event("user.registered", {...})
    return user
```

`reconcile_anonymous_visits` reads `request.COOKIES.get("flsvid")`, and if present, does the
`update(user=user)` backfill described in §3.2. No signal needed for this store-only feature; a
signal only earns its keep once something *else* (not signup itself) also needs to react to "user
signed up with referral attribution."

### 4.2 `user_logged_in` — not needed for this feature, but note the boundary

`user_logged_in` (also `request` + `user` kwargs) fires on every login, not just signup. Since the
product decision is "link anonymous browsing to the user **at signup**," this signal is out of
scope for the core capture/link mechanic. It would matter for a *later* feature ("keep updating
attribution/last-seen for existing users on every login"), which is explicitly not being requested
now — flagged here only so it isn't accidentally conflated with `user_signed_up` during
implementation. Allauth signals reference:
https://docs.allauth.org/en/latest/account/signals.html

### 4.3 Social-login signup path

`save_user` on `DefaultAccountAdapter` is also invoked from the regular signup form; social/SSO
signups (via `allauth.socialaccount`) go through `SocialAccountAdapter.save_user` instead (a
different adapter class) if social login is ever enabled here. Currently this codebase doesn't
appear to enable `django-allauth[socialaccount]` providers, but if it's added later, the same
reconciliation call needs mirroring into that adapter too — worth a one-line note/TODO in the
eventual implementation plan rather than solved now (YAGNI per product decision "store data only
for now").

### 4.4 Session-fixation interaction (relevant because it's easy to get backwards)

Allauth (like Django's own login()) rotates the session key on login/signup
(`request.session.cycle_key()`, called from within `django.contrib.auth.login()`, which allauth's
`perform_login` calls) specifically to defeat session fixation. **This is exactly why the anonymous
visitor identifier must not live in `request.session`** (§2.2) — if it did, the reconciliation
read would need to happen *before* `cycle_key()` fires, adding a real ordering hazard. Because the
recommendation in §2.1 uses an independent `flsvid` cookie, this ordering concern disappears
entirely: the cookie is unaffected by session-key rotation, and `reconcile_anonymous_visits` can
run any time after signup with no race. Django docs on `cycle_key`/session security:
https://docs.djangoproject.com/en/stable/topics/http/sessions/#session-security

---

## 5. First-touch vs. last-touch (flag, not a decision)

Not asked-for in this research brief, but worth flagging since it affects the capture-middleware
logic in §1.1: if a visitor arrives via `ref=partnerA`, then later clicks a `utm_source=email`
newsletter link before signing up, does attribution overwrite (last-touch) or is the earliest touch
preserved (first-touch)? For a store-only-for-now feature, the safest default is to **store every
touch** (the `ReferralVisit` trail) and **not** collapse to a single "the" attribution row yet —
that decision can be made later once reporting requirements exist, without needing to re-capture
historical data. Don't build the first/last-touch resolution logic now; just don't foreclose it by
only keeping one row per visitor.

---

## 6. Pitfalls

- **Bots/crawlers.** Search engine crawlers and link-preview bots (Slack/Discord/Twitter unfurlers,
  security scanners) will hit referral URLs and inflate/corrupt the capture data. Mitigations:
  cheap user-agent substring denylist (`bot`, `crawler`, `spider`, common unfurler UAs) applied
  *before* writing a capture row (still fine to redirect/serve the page — just skip the write);
  don't try to be exhaustive, this is a "reduce noise," not a security control. Do not rely on
  UA-sniffing for anything security-sensitive — it's easily spoofed and here it's only cosmetic to
  data quality.
- **Session fixation.** Covered in §4.4 — solved structurally by keeping the visitor id out of
  `request.session`. If a project instead stores it in the session, an attacker who fixates a
  victim's session before it's authenticated could get referral data attributed to a session they
  control; using a dedicated cookie the attacker doesn't control (a fresh random token minted by
  the server on first sight, `httponly`, never settable by client JS) avoids this class of issue.
- **Users who clear cookies.** Attribution is lost — this is an accepted, unavoidable limitation of
  first-party-cookie-only tracking (per the product decision to avoid third-party
  tracking/fingerprinting). No workaround is in scope; don't build fingerprinting to compensate.
- **Multiple devices.** A visitor who clicks a referral link on their phone and signs up on their
  laptop will not be linked — the cookie is per-browser. Same acceptance as above; flagging so it
  isn't reported as a "bug" later. Cross-device stitching (email-based matching, server-side
  identity graphs) is explicitly out of scope for a first-party, cookie-only design.
- **GET-param leakage into logs/referrers.** `?ref=` and UTM params in the URL bar get logged by
  web servers/CDNs/proxies (access logs) and forwarded verbatim in the `Referer` header of any
  outbound link/asset request from that page (e.g. to a CDN, to an embedded iframe, or to an
  external analytics script) unless stripped. Two independent mitigations, both recommended:
  1. **Redirect-after-capture** (§ below) to remove the params from the URL bar before the page
     renders further outbound links.
  2. A `Referrer-Policy` header (e.g. `strict-origin-when-cross-origin`, Django's default via
     `SecurityMiddleware`/`django.middleware.security` or explicit setting) so even the shortened
     URL's origin-only referrer is sent to third-party requests. Check current
     `SECURE_REFERRER_POLICY` setting / Django default:
     https://docs.djangoproject.com/en/stable/ref/settings/#secure-referrer-policy
  Access-log leakage of the raw incoming request (params still visible in *this* app's own web
  server logs before the redirect) is generally accepted as normal/expected for query params and
  not treated as a leak requiring special handling, but avoid also echoing the raw `ref`/UTM values
  back into any *application* log lines beyond what's already stored in the capture row.
- **Redirect-after-capture to strip the param.** Once the middleware has captured the params and
  set the `flsvid` cookie, issue a same-path redirect with the tracking query params removed
  (`HttpResponseRedirect(request.path)` or reconstruct the querystring minus the known keys if
  other legitimate params need to survive), so the URL a user might bookmark/share doesn't carry
  someone else's referral code forward, and so referrer headers to third parties from that page
  don't include it either. This is the same pattern documented by
  [django-utm](https://github.com/kmmbvnr/django-utm) and
  [django-analytical](https://django-analytical.readthedocs.io/) for UTM capture, and is standard
  practice for GA-style campaign links generally. Caveat: an extra redirect costs a round trip on
  every referral-tagged landing — acceptable given this is a one-time event per visitor per touch,
  not a page rendered directly.

---

## 7. Summary of concrete recommendations

1. Capture in **middleware** (`ReferralCaptureMiddleware`), registered after `SessionMiddleware`
   and `CurrentSiteMiddleware`, matching this codebase's existing middleware style
   (`freedom_ls/site_aware_models/middleware.py`, `freedom_ls/accounts/middleware.py`).
2. Anonymous identity lives in a **dedicated first-party cookie** (`flsvid`), not
   `request.session` — `httponly`, `secure` (prod), `samesite="Lax"`, its own `max_age`
   independent of `SESSION_COOKIE_AGE`.
3. Persist every touch to a Postgres model (`ReferralVisit` or similar), `site_aware_models`-scoped,
   `user` FK nullable and backfilled later — don't collapse to first/last-touch yet (§5).
4. Reconcile at signup inside **`AccountAdapter.save_user`**
   (`freedom_ls/accounts/allauth_account_adapter.py`), alongside the existing
   `fire_webhook_event("user.registered", ...)` call — read the `flsvid` cookie, `update()` the
   matching rows' `user` FK. `user_signed_up` signal is the documented allauth alternative if this
   grows past a simple function call.
5. Redirect-after-capture to strip `ref`/UTM params from the URL before rendering, both for
   referrer-leakage hygiene and to stop bookmarked/shared URLs from re-propagating someone else's
   attribution.
6. Treat `ref`/UTM/referrer values as **untrusted input** throughout — length-cap, no raw-SQL, no
   trust placed in `ref` matching a real code (validation lives in the external system).

## References

- Django sessions: https://docs.djangoproject.com/en/stable/topics/http/sessions/
- Django session security / `cycle_key`: https://docs.djangoproject.com/en/stable/topics/http/sessions/#session-security
- Django cookies (`set_cookie`): https://docs.djangoproject.com/en/stable/ref/request-response/#django.http.HttpResponse.set_cookie
- Django middleware: https://docs.djangoproject.com/en/stable/topics/http/middleware/
- `SECURE_REFERRER_POLICY` setting: https://docs.djangoproject.com/en/stable/ref/settings/#secure-referrer-policy
- django-allauth signals reference: https://docs.allauth.org/en/latest/account/signals.html
- django-allauth signals source (installed version, confirms `request`/`user` kwargs):
  `.venv/lib/python3.13/site-packages/allauth/account/signals.py`
- django-utm (UTM capture + redirect-strip pattern precedent): https://github.com/kmmbvnr/django-utm
- django-analytical: https://django-analytical.readthedocs.io/
- Google UTM parameter reference: https://support.google.com/analytics/answer/10917952
- In-repo precedent read for this research:
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/accounts/allauth_account_adapter.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/webhooks/events.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/accounts/middleware.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/site_aware_models/middleware.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/config/settings_prod.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/config/settings_dev.py`
  - `/home/sheena/workspace/lms/freedom-ls-worktrees/main/config/settings_base.py`

---

status: ok
