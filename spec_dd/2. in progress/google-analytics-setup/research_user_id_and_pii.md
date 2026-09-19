# Research: GA4 User-ID and PII rules for FLS

Scope: identifiers only. POPIA/cookie-consent legal framing is covered by a separate
research worker; this file assumes GA is otherwise lawful to load and focuses on
*what identifier, if any, should be sent to GA4 for a logged-in learner/educator*.

## 1. How GA4 User-ID works

- User-ID is a GA4 property-level feature you turn on, then supply per-request via
  `gtag('set', 'user_id', '<id>')` (or a `user_id` field in `gtag('config', ...)`),
  set on every page where the user is signed in and cleared/omitted when they are not.
- What it buys: stitching sessions/events from the same person across devices and
  browsers into one "user" for reporting, more accurate active-user counts, a
  signed-in vs signed-out behaviour split, User-ID based exploration, and eligibility
  to build remarketing audiences keyed on it.
- It does **not** work by itself: the property's **Reporting Identity** setting (Admin
  → Data display → Reporting identity) must be set to **Blended** (User-ID → Google
  signals → device ID → modeled, in that priority) or **Observed** (User-ID → device
  ID, no modeling) for User-ID to actually feed the "Identity" reporting; if left on
  "Device-based" the user_id you send is stored but ignored for identity resolution.
- Requirements Google places on the value itself: unique, persistent across sessions
  for that person, ≤ 256 characters, consistently (re-)assigned by you — and, per the
  PII rule below, **not itself derivable back to a real-world identity by anyone
  outside your own systems**.
  Source: [Measure activity across platforms with User-ID](https://support.google.com/analytics/answer/9213390?hl=en)

## 2. Google's PII rule — what's allowed as the identifier

- Google's Ads/Analytics terms and the Analytics Help Center flatly prohibit sending
  Google anything Google could use or recognise as personally identifiable
  information: explicitly listed are email addresses, phone numbers, government IDs
  (e.g. SA ID numbers), full names, physical addresses, financial account data, and
  fine-grained location (< 1 sq mile / raw lat-long). This is a contractual
  obligation, not just a guideline — breach is grounds for suspending the GA
  property.
  Source: [Best practices to avoid sending PII](https://support.google.com/analytics/answer/6366371?hl=en),
  [Understanding PII in Google's contracts and policies](https://support.google.com/analytics/answer/7686480),
  [Safeguarding your data](https://support.google.com/analytics/answer/6004245)
- **A raw database primary key is explicitly sanctioned** by Google's own guidance
  for User-ID (e.g. `user_12345`) *provided* that number, on its own, doesn't let a
  third party who has only Google's UI/exports identify the person. A sequential
  integer with no other context attached is fine as a User-ID value in this sense —
  Google's servers never see anything that resolves to a name/email unless you send
  one alongside it (e.g. in a custom dimension, page URL, or event parameter).
- **A UUID is equally acceptable** and is what most guides recommend as the default
  "safe-looking" choice, but it confers no extra privacy benefit over a plain integer
  pk *if* the pk is otherwise not exposed as a lookup key to outsiders — the property
  Google actually cares about is unlinkability by a third party from Google's data
  alone, not the shape of the string.
- **Hashing is not required by Google for a non-PII value** (a pk or UUID is already
  non-PII). Hashing only matters if the value you'd otherwise send *is* PII (e.g. you
  only have the email available) — hashing an email does not make it acceptable
  either, because Google (or anyone with the same hash function and a guessable input
  space) can recompute the hash from a known email and re-identify the user; salted
  hashing reduces but does not eliminate this. **Conclusion: don't hash email as a
  workaround — use a genuinely non-PII identifier instead (see §3).**
- GA4 ships a **data redaction** setting (Admin → Data streams → your web stream →
  "Redact data") independent of User-ID: it can strip emails from event data on a
  best-effort basis and redact named query-string parameters. It is defence in depth,
  not a substitute for not sending PII in the first place, and it doesn't apply to
  the Measurement Protocol or Data Import.
  Source: [\[GA4\] Data redaction](https://support.google.com/analytics/answer/13544947?hl=en)

## 3. FLS's user model — what identifier is available

Read `freedom_ls/accounts/models.py`:

- `User` extends `SiteAwareModelBase` (not the UUID-pk `SiteAwareModel`). Its pk is a
  plain `BigAutoField` — a small sequential integer — **by deliberate design**: the
  code comment states *"User is the one object whose identity appears in a URL as a
  small sequential number. Permission checks are keyed on email, the actual auth
  identifier, not on this pk."* So the pk is already treated as a low-sensitivity,
  routable identifier inside FLS, not as an internal secret.
- `email` is `unique=True` at the DB/migration level with **no site-scoped uniqueness
  qualifier** — i.e. email is unique across the whole `User` table, and each `User`
  row has exactly one `site` FK. **This means a person does not get a separate
  account per site under the same email**: one email = one `User` row = one home
  site, contrary to the "same person may have separate accounts per site" framing in
  the task brief. (A person *could* still hold two unrelated accounts on two sites if
  they used two different email addresses, but FLS doesn't model "the same person on
  multiple sites" as one identity at all.)
- There is **no existing opaque/public identifier** on `User` (no `uuid` field, no
  `public_id`, no slug) beyond the integer pk itself.
- Consequence for GA4 User-ID: `str(user.pk)` is a reasonable, already-integer,
  already-URL-exposed, non-PII value — sending it to GA adds no new exposure beyond
  what FLS already puts in its own URLs and server logs. A synthetic UUID would need
  a new field/migration for no privacy gain, only string-shape "safety theatre";
  it's arguably *worse* because a fresh random value invites someone to defend it as
  "unguessable" when in fact GA doesn't need or reward unguessability — it needs
  uniqueness, persistence, and unlinkability from Google's side, which the existing
  pk already provides.

## 4. Existing precedent: PostHog

`freedom_ls/base/templates/_base.html` initialises PostHog (`posthog.init(...)`) only
when `POSTHOG_API_KEY` is configured — the same "no key, no-op" pattern this GA work
is meant to copy (per `idea.md`). **There is no `posthog.identify()` call anywhere in
the codebase** (checked all `*.html` and `*.py` under `freedom_ls/`) — FLS does not
currently identify logged-in users to PostHog at all; every PostHog visitor is
tracked purely on PostHog's anonymous `distinct_id`. So there is **no existing
in-repo precedent either for or against** sending a stable user identifier to an
analytics vendor — this GA decision is the first of its kind in FLS, not a "match
what PostHog already does" situation.

## 5. PII leaking into GA via `page_location` / URLs

GA4's automatic `page_view` event captures the full `page_location` (and referrer),
so anything in the URL path or query string reaches Google's servers as a matter of
course — this is the most likely accidental PII channel, independent of the User-ID
question.

Checked `config/urls.py` and the app `urls.py` files:

- **allauth is mounted at `/accounts/`** (`path("accounts/", include("allauth.urls"))`)
  and its own `urls.py` (from the installed `django-allauth` package) defines two
  token-bearing routes that are live in FLS:
  - `accounts/confirm-email/<key>/` — the email-verification key
  - `accounts/password/reset/key/<uidb36>-<key>/` — the password-reset token
  These keys are one-time, time-limited secrets but are **not classic PII** (they
  don't identify a person to a third party by themselves) — the real risk is that
  they are **live credentials**: anyone who can read them (including Google, via
  `page_location`) could complete the linked flow before the user does, and page
  URLs of this shape sitting in GA's raw event export for 2–14 months is an
  unnecessary residual risk.
  Source: local read of `.venv/lib/python3.13/site-packages/allauth/account/urls.py`,
  cross-checked with Django Allauth's own docs at
  [django-allauth.readthedocs.io](https://django-allauth.readthedocs.io/).
- No FLS-authored URL pattern was found that puts an **email address** directly in a
  path (`freedom_ls/accounts/urls.py`, `learner_interface/urls.py` use only
  `course_slug`, `index`, `page_number`, `doc_type`); `educator_interface/urls.py`
  routes everything after `organisations/<slug>/` through a single catch-all
  `path_string` dispatched internally in `views.py` — this is opaque to a URL-pattern
  grep and **should be spot-checked at implementation time** for any learner-detail
  route that might embed an email or full name as a slug rather than a pk.
- No `GET`-parameter based query strings carrying PII were found in the routes
  reviewed, but this repo-wide grep is not exhaustive (query params are runtime, not
  visible in `urls.py`).

**Mitigation, in order of effectiveness:**
1. Turn on GA4's **query-parameter redaction** for the web stream and add any
   parameter names FLS ever puts PII into (currently none identified, but cheap
   insurance).
2. Turn on GA4's **email redaction** (default-on for new streams anyway) as a
   best-effort backstop.
3. For the two allauth token URLs specifically: either (a) don't fire/allow the GA
   tag to send `page_view` on `accounts/confirm-email/*` and
   `accounts/password/reset/key/*` (a small denylist by path prefix, evaluated
   server-side or in the gtag config before `page_view` fires), or (b) strip the
   `key`/`uidb36` path segments from `page_location` before sending, e.g. by setting
   a custom `page_location` in the same `gtag('config', ...)` call that omits the
   trailing token segment. Option (a) is simpler and matches how Sentry/PostHog
   commonly special-case auth pages.
4. None of this is a substitute for HTTPS (already assumed) — these are one-time,
   short-lived tokens, so the residual risk is small but non-zero and free to close.

## 6. Multi-site: does GA need a site/domain parameter?

- GA4 already records `page_location`, which includes hostname, and the default
  Reporting → **Hostname** dimension lets you filter/segment by domain out of the
  box when several sites share one GA4 property (one measurement ID per deployment,
  per the brief). For most reporting (traffic, funnels, page performance) hostname
  alone is enough to separate sites.
- Where hostname is **not** enough: any report that groups or joins on `user_id`
  directly. Because `User.email` is globally unique and each `User` row belongs to
  exactly one `site` (see §3), a given `user_id` (the pk) is already effectively
  site-scoped one-to-one — there is no cross-site collision to disambiguate, so a
  separate site parameter is not needed *to make the user_id unique*.
- It is still worth sending the site's domain (or a short site code) as a **user
  property** (e.g. `site` = `demo.example.com`) rather than relying solely on the
  `Hostname` built-in dimension, because user properties survive into User-ID-scoped
  explorations and audiences in a way that's more convenient than re-deriving from
  hostname each time — this is a minor reporting-convenience recommendation, not a
  PII or correctness requirement.

## 7. Other safe/useful user properties

- **Role** (`learner` / `educator` / possibly `superuser`) as a GA4 **user property**
  is low-risk (not PII, coarse-grained, useful for segmenting funnels by audience)
  and is the one property worth adding alongside `user_id` if this work goes ahead.
  Anything finer (cohort name, course title as a user property rather than an event
  parameter) risks re-identifying small cohorts and should be left as event-level
  parameters, not persistent user properties, if added at all — out of scope here.

## 8. Recommendation

**Send a `user_id` to GA4 for logged-in users, using `str(request.user.pk)`
(the existing integer primary key) — nothing else, nothing hashed, nothing new.**

- It satisfies Google's non-PII requirement as-is: a bare sequential integer with no
  attached email/name reaching Google's servers, already treated by FLS itself as a
  routable, non-secret identifier (see the code comment in `accounts/models.py`).
- Do **not** invent a new UUID field for this — it's a migration for no privacy gain,
  since the pk is already opaque from Google's point of view (Google never receives
  the row it points to, only the number).
- Do **not** hash the email — non-PII values don't need hashing, and hashing PII
  doesn't make it non-PII per Google's own guidance.
- **Condition on consent** (owned by the sibling POPIA/consent worker): only call
  `gtag('set', 'user_id', ...)` once analytics consent is granted, and unset it
  (`gtag('set', 'user_id', null)` or omit on next page load) immediately on logout.
- **Condition on GA being configured at all**, per the existing PostHog pattern: no
  measurement ID → no gtag script → nothing to set `user_id` on.
- **Set Reporting Identity to "Blended" or "Observed"** in the GA4 property Admin —
  without this, the `user_id` you send is inert for identity-based reporting.
- **Close the allauth token-URL leak** (§5) as a cheap, unrelated-but-adjacent fix
  while wiring up `page_view`/`page_location`, independent of the user_id decision.
- Optionally also send `role` (learner/educator) as a user property; optionally send
  the site domain as a user property for reporting convenience, though hostname
  segmentation already covers most needs.

status: ok
