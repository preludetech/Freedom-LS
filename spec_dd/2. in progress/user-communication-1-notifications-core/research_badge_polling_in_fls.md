# Research: badge polling interval, settled with FLS specifics

Scope note: `research_prior_notification_ux.md` (this directory) already covers general 30-60s
interval guidance and visibility-gated polling mechanics — not repeated here. This file settles the
open question with facts from the FLS codebase itself.

## 1. Where the badge lives, and what surfaces poll

- The bell/badge's home, `freedom_ls/base/templates/partials/header_bar.html`, is included once,
  from `freedom_ls/base/templates/_base.html:104` (`{% include "partials/header_bar.html" %}`
  inside `{% block header %}`).
- `_base.html` is the root template. `freedom_ls/base/templates/_base_interface.html:1` extends it
  (`{% extends "_base.html" %}`) and is the shared shell with the docked/overlay side panel used by
  the learner dashboard, course player and educator interface. So the badge is not one dashboard
  widget — it is present on **every** authenticated page render across all three interfaces, and a
  polling `hx-trigger` on it runs once per open tab, on every page, all the time a user is signed in.
- Grep for `hx-trigger` across `freedom_ls/` (`Grep pattern="hx-trigger"`) found no interval-based
  trigger anywhere in the codebase today — only `hx-trigger="load-tab once"`
  (`panel_framework/templates/panel_framework/partials/tab_container.html:29`), a `change` trigger
  on file upload, and a debounced search input (`base/templates/cotton/data-table.html:18`). **The
  badge is the first poller FLS will ship.** There is no existing interval to match or existing
  polling load to avoid colliding with, and no precedent template to copy verbatim — this is a new
  idiom for the codebase, so get the outerHTML-swap-with-self-contained-trigger detail right (see
  Pitfalls).
- The course player (`_exam_runner_base.html` and friends) does no long-running HTMX work and does
  not poll; it uses HTMX only for form submission. No interaction/collision to design around there.

## 2. HTMX + auth redirect: the FLS convention the badge endpoint must follow

FLS already has a documented, load-bearing convention for exactly the failure mode flagged in the
prompt — a plain 302 (what `login_required`/`LoginRequiredMixin` give by default) gets followed by
htmx's own XHR and the target page's HTML (a login form) gets swapped into the calling element.

- `freedom_ls/accounts/utils.py:110-139`, `redirect_to_auth()`:
  > "htmx follows a 302 inside its own XHR and swaps the target page's HTML into the element that
  > made the request, landing a login form inside a button. An htmx request instead gets 204 with
  > an HX-Redirect header, so the browser performs a real navigation."
  ```python
  if request.headers.get("HX-Request"):
      response = HttpResponse(status=204)
      response["HX-Redirect"] = target
      return response
  return redirect(target)
  ```
- This helper is already load-bearing elsewhere for htmx-originated requests that need auth:
  `freedom_ls/accounts/middleware.py:123-127` (`RegistrationCompletionMiddleware`),
  `freedom_ls/course_interest/views.py` (per its own docstring at line 5-6 and tests at
  `course_interest/tests/test_views.py:290-349`), and mirrored for other htmx flows by
  `panel_framework/actions.py:172,339` (`response["HX-Redirect"] = ...` after 204 on success).
- **Implication for the badge poll endpoint**: it must not sit behind a bare `@login_required`. If
  a session expires mid-poll, an unguarded view returns a normal login redirect, htmx follows it,
  and the login page's markup gets swapped into the badge element — and because the badge is global
  (finding 1), this corrupts the header on whatever page the tab happens to be on, not just one
  feature's own surface. The poll view needs the same 204 + `HX-Redirect` (or equivalent early
  return) as every other htmx endpoint in FLS, most simply by reusing `redirect_to_auth()` or the
  same guard pattern.
- Whether a background tab should be yanked to a full top-level navigation on an expired session, or
  should instead silently stop polling / show a "signed out" affordance in the badge, is a genuine
  UX question the existing helper doesn't answer for a *background* poll (it was designed for
  user-initiated actions). Worth a design decision in the spec, but the *mechanism* to avoid — a
  bare redirect getting swapped in — is already settled FLS practice either way.

## 3. Per-request cost

- Full middleware stack: `config/settings_base.py:152-169` — `SecurityMiddleware`,
  `ContentSecurityPolicyMiddleware`, `WhiteNoiseMiddleware`, `SessionMiddleware`, `CommonMiddleware`,
  `CsrfViewMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`, `HtmxMessagesMiddleware`,
  `XFrameOptionsMiddleware`, `CurrentSiteMiddleware`, `AttributionCaptureMiddleware`,
  `AccountMiddleware`, `RegistrationCompletionMiddleware`, `AxesMiddleware`. None of these add
  extra DB work specific to a plain poll GET:
  - `CurrentSiteMiddleware` (`freedom_ls/site_aware_models/middleware.py`) does no DB query itself —
    it just publishes the request on a thread-local so `SiteAwareManager` can filter by it.
  - `AttributionCaptureMiddleware` (`freedom_ls/referral_tracking/middleware.py:51-52`) early-returns
    unless the request carries tracked UTM/referral params — a poll URL carries none, so it's a
    no-op, and it will not mint an attribution cookie or increment a referral counter on every poll.
  - `HtmxMessagesMiddleware` (`freedom_ls/base/middleware.py`) is a no-op unless Django messages are
    queued; the poll view raises none, so responses stay a minimal fragment, no OOB toast glued on.
  - `RegistrationCompletionMiddleware`'s incompleteness check is cached per session
    (`_is_complete_cached`, `freedom_ls/accounts/middleware.py`), so repeat polls don't re-run
    `get_incomplete_forms` every hit.
  So the marginal cost of the poll, beyond what every other authenticated GET already pays
  (session load, CSRF, auth, Axes bookkeeping), is essentially just the view's own count query.
- **Count query**: no `Notification` model exists yet (the `comms` app is what this spec builds),
  but FLS has a direct precedent for the exact shape of index needed — a per-user "how many active
  rows" query: `role_based_permissions/models.py:40,74,116`,
  `models.Index(fields=["user", "is_active"])`. The equivalent here is an index covering
  `(user, site, read_at)`, or — since Postgres 17 supports partial indexes and FLS already writes
  Postgres-only conditional constraints (`condition=models.Q(...)` at
  `learner_management/models.py:183,229,281`, `organisations/models.py:108`,
  `reports/models.py:80`, the same `condition=` argument Django's `models.Index` also accepts) — a
  partial index such as `models.Index(fields=["user"], condition=models.Q(read_at__isnull=True))`.
  A `COUNT(*) WHERE user_id=%s AND site_id=%s AND read_at IS NULL` against that index is a cheap
  index-only scan, well within what a 30-60s poll from every open tab of every signed-in user
  sustains. **No caching layer is warranted** for this query.
- **Caching would not actually help**: production's `CACHES` (`config/settings_prod.py:89`)
  resolves to `freedom_ls.deployment.settings_defaults.DATABASE_CACHES`
  (`freedom_ls/deployment/settings_defaults.py:86`) — i.e. FLS's cache backend in production is
  itself a Postgres-table-backed `DatabaseCache`, not Redis/Memcached. Caching the unread count
  there trades one indexed `COUNT` for a cache-table `SELECT` (its own DB round trip, with its own
  expiry bookkeeping) plus invalidation work on every notification-raise and every mark-as-read —
  no clear win. Skip caching for this spec.
- **Session expiry**: `SESSION_SAVE_EVERY_REQUEST` is not set anywhere in `config/settings_base.py`,
  `settings_dev.py` or `settings_prod.py` (grepped, no hits), so it is Django's default `False` — a
  session is only rewritten when its data actually changes. A poll GET that doesn't touch
  `request.session` does **not** extend session expiry or write to `django_session` on every tick.
  FLS's own prior research confirms this explicitly:
  `spec_dd/3. done/2026-09-10_18:18_referal_tracking/research_django_implementations.md:199-207`
  ("`SESSION_SAVE_EVERY_REQUEST` defaults to False ... which FLS doesn't [set]"). So an open
  background tab polling for 8 hours does not silently keep an otherwise-idle session alive.
  `SESSION_COOKIE_AGE = 1209600` (2 weeks) is set in `config/settings_prod.py:51`, unaffected by
  polling either way.
- **No analytics/logging pollution**: `partials/google_analytics_events.html`,
  `partials/posthog.html` and `partials/google_analytics.html` are wired into `<head>` and into
  `#interface-main` by the full-page shells (`_base.html:84,90-92`,
  `_base_interface.html:208`) — they are part of the full HTML document, not something a
  fragment-returning view re-includes. As long as the poll view renders only its own small
  badge/count partial (does not extend `_base.html`/`_base_interface.html`), it never re-emits
  GA/PostHog `<script>` tags or fires duplicate pageviews/events on every tick. Combined with
  `AttributionCaptureMiddleware`'s no-op above, polling does not touch Google Analytics, PostHog,
  or `referral_tracking` at all. FLS adds no per-request access-log middleware of its own (and
  CLAUDE.md says not to add logging unless asked), so there is nothing else to pollute.

## 4. HTMX 2 mechanics specific to FLS conventions

- `claude_plugins/django-stack/skills/htmx/SKILL.md` gives the two rules that matter here: always
  pair `hx-target`/`hx-swap` and **prefer `outerHTML`** as the swap strategy. For a self-polling
  element this is not just a preference but a correctness requirement: the response fragment must
  re-include the same `hx-get`/`hx-trigger` attributes, and the swap must replace the whole element
  (`outerHTML`), or the re-rendered badge loses its trigger and polling silently stops after the
  first tick. Because there is no existing poller in FLS to copy this idiom from (finding 1), this
  is the detail most likely to be gotten wrong the first time.
- Visibility gating + no request pile-up: `hx-trigger="every 45s [document.visibilityState ===
  'visible'], visibilitychange from:document [document.visibilityState === 'visible']"` — the
  filtered `every` clause suppresses ticks while hidden (htmx does not queue missed ticks for a
  filtered `every` trigger), and the filtered `visibilitychange` clause fires one fresh request the
  moment the tab regains visibility rather than waiting out the remainder of the interval. Since the
  badge is a single element issuing its own request, there is no separate stacking risk beyond the
  standard htmx behaviour of one in-flight request per triggering element.
- Immediate refresh after mark-as-read, without waiting for the next tick — FLS already has both of
  the idioms this needs, live in the codebase today:
  1. **`HX-Trigger` response header + a listener**, exactly as `panel_framework` already does for
     its own list refresh: `panel_framework/actions.py:169,205` sets
     `response["HX-Trigger"] = ...` on a successful action, and
     `panel_framework/static/panel_framework/js/alpine-components.js:24` documents "Re-fetches the
     list table when a create action's HX-Trigger event fires". The mark-as-read/mark-all-read view
     would set `response["HX-Trigger"] = "notificationsRead"`, and the badge's own `hx-trigger` list
     would add `, notificationsRead from:body` so it refetches immediately on that event.
  2. **Out-of-band swap**, the pattern already used for `partials/page_title.html:8`,
     `partials/breadcrumbs.html:38`, `partials/organisation_switcher.html:12` and
     `partials/messages.html` (an `hx-swap-oob="true"` element gated behind an `oob` context flag).
     The mark-as-read view's response could carry a second, OOB-flagged badge fragment alongside its
     primary content, updating the count in the same round trip with no second request at all. This
     is cheaper than option 1 (no extra HTTP round trip) and should be preferred wherever the
     mark-as-read view and the badge can share one response; `HX-Trigger` is the right tool only
     when they're rendered by views that don't already share a response (e.g. the notification
     centre's full-page mark-all-read).
  - Either mechanism re-announces through the badge's existing `role="status"` (settled in the idea
    doc) for free — no extra accessibility work needed on refresh.

## 5. Should the interval be a setting?

Yes. `claude_plugins/fls-dev/skills/app-settings/SKILL.md` and
`claude_plugins/django-stack/skills/app-settings/SKILL.md` establish the pattern: a reusable app
declares its own tunables in a `config.py` in the app that reads them, as a class-level annotation
resolved through `AppSettings`/`Setting`, e.g. (for the new `comms` app):

```python
# freedom_ls/comms/config.py
class CommsConfig(AppSettings):
    NOTIFICATION_BADGE_POLL_SECONDS: int
    declared_settings = {"NOTIFICATION_BADGE_POLL_SECONDS": Setting(default=45)}
```

Not `required=True` — a safe numeric default within 30-60s always exists. The header template
should read the value through a small context processor (FLS already exposes several this way:
`site_aware_models.context_processors.site_config`, `google_tag.context_processors.google_tag_config`
in `config/settings_base.py:195,200`) rather than hardcoding `45s` in the `hx-trigger` string, so a
downstream project can retune it per CLAUDE.md's "designed to be installed into other Django
projects... designed to be extended and customized" without forking the template.

## Recommendation: 45 seconds

- Middle of the 30-60s range the general research already settles on.
- The badge is global (finding 1): it is present on every authenticated page, for every open tab,
  for as long as a user is signed in — a much larger footprint than a single feature surface. Given
  that reach, favour the upper-middle of the range over the aggressive end (30s) even though each
  individual query is cheap (finding 3): the aggregate request volume across "every signed-in user,
  every open tab, all day" is what should decide this, not the cost of one query in isolation.
- Because mark-as-read already gets an immediate, same-request-or-one-event update (finding 4), the
  interval only has to cover the "something happened to me while I wasn't looking at the panel"
  case — course registration/completion notifications are not second-sensitive, so there is no
  UX pressure toward the tighter end of the range either.
- No existing FLS poller to stay compatible with (finding 1), so no external constraint pulls the
  number away from the general recommendation's midpoint.

## Pitfalls

- Do not put the poll view behind a bare `@login_required`/`LoginRequiredMixin` — use
  `redirect_to_auth()`'s 204 + `HX-Redirect` pattern (`freedom_ls/accounts/utils.py:110-139`) or an
  equivalent guard, or an expired session swaps a login page into the header on whatever page the
  tab happens to be showing (finding 2).
- Return the whole badge element (`hx-swap="outerHTML"`) with its own `hx-get`/`hx-trigger`
  attributes intact on every response — this is the first poller in FLS, so there's no existing
  template to copy the "don't drop your own trigger" detail from (finding 4).
- Render the poll view's own small partial only — don't extend `_base.html`/`_base_interface.html`
  for it, or GA/PostHog script tags get needlessly re-emitted into a fragment every tick
  (finding 3).
- Don't cache the unread count: FLS's cache backend in production is itself DB-backed
  (`DatabaseCache`), so caching buys no real cost saving and only adds invalidation surface on every
  notification-raise and mark-as-read (finding 3).
- `SiteAwareManager` filters by the current site automatically inside a request
  (`CurrentSiteMiddleware`); the poll view's count query should rely on that default filtering
  rather than reimplementing site scoping, and must not accidentally reuse a background-safe helper
  that takes an explicit `site_id` (the idea doc's note that `SiteAwareManager` does *not* filter
  outside a request is a background-task concern, not this synchronous view's — but the two code
  paths will exist side by side in the same app, so keep them distinct).
- `SESSION_SAVE_EVERY_REQUEST` is unset (defaults `False`) today, so polling doesn't extend session
  life (finding 3) — but if anything ever flips that setting to `True` for an unrelated reason,
  every open tab's 45s poll would start writing to `django_session` on every tick; worth a one-line
  guard comment near the setting if it's ever touched.

## Reference URLs

- HTMX `hx-trigger` docs (`every`, filters, `from:`): https://htmx.org/attributes/hx-trigger/
- HTMX `HX-Trigger` response header: https://htmx.org/headers/hx-trigger/
- HTMX out-of-band swaps: https://htmx.org/attributes/hx-swap-oob/
- Django `SESSION_SAVE_EVERY_REQUEST`: https://docs.djangoproject.com/en/6.0/ref/settings/#session-save-every-request
- Django partial indexes (`Index.condition`): https://docs.djangoproject.com/en/6.0/ref/models/indexes/#condition
- Django cache framework / `DatabaseCache`: https://docs.djangoproject.com/en/6.0/topics/cache/#database-caching

status: ok
