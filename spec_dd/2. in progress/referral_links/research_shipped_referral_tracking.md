# Research: what `referral_tracking` actually shipped

The other research files in this directory were written before `referral_tracking` landed on
`main` and describe its spec. This file describes the code, read from the worktree after the rebase,
and names the seams this work touches. Where a sibling file and this one disagree, this one wins.

Spec and history: `spec_dd/3. done/2026-09-10_18:18_referal_tracking/`. Product page:
`docs/product/signup-attribution.md`. Upgrade notes in the same done directory.

## 1. The app as it exists

`freedom_ls/referral_tracking/`, label `freedom_ls_referral_tracking`, verbose name "Referral
tracking". Modules: `models.py`, `capture.py`, `counters.py`, `middleware.py`, `signals.py`,
`admin.py`, `resources.py`, `config.py`, `factories.py`. No `urls.py`, no `views.py`, no templates,
no management commands. Nothing in `config/urls.py` includes it. This work adds the app's first
routes and its first view.

Runtime imports: `accounts`, `base`, `site_aware_models`. Nothing imports it at runtime;
`accounts` reaches it only through a dotted string on the admin's erasure set. `docs/app_structure.md`
shows those three edges and no other. Adding no `Organisation` link keeps that true.

Settings, all optional, in `config.py` via the `AppSettings` pattern:

| Setting | Default |
| --- | --- |
| `REFERRAL_TRACKING_COOKIE_NAME` | `fls_attribution` |
| `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS` | `90` |
| `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` | `1000` |

## 2. The seams a referral code has to pass through

Everything below is a module-level constant or a plain column, so adding `ref` is additive.

- **`capture.TRACKED_PARAMS`**: `advert_code`, the five `utm_*`, `gclid`, `gbraid`, `wbraid`,
  `fbclid`. Any one present on a GET triggers a mint. `ref` is not in it; the spec (§5.4) reserves
  the name for this work.
- **`capture.LOWERCASED_PARAMS`**: `utm_source`, `utm_medium`. Lower-casing is a per-parameter
  choice, so `ref` can be folded or not independently.
- **`models.CAPS`**: one cap per captured field, shared by the cookie payload and the column.
  `advert_code` is 64.
- **`models.ATTRIBUTION_KEY_FIELDS`**: `advert_code` plus the five `utm_*`. This tuple is what
  `FirstTouchCount` groups by, what `attribution_key_hash` digests, and what the middleware copies
  onto the tally row. `FirstTouchCount` carries each key field as a plain column so the admin can
  filter and display it. A seventh key field means a seventh column on `FirstTouchCount`, a column
  on `SignupAttribution`, and every existing `key_hash` staying valid because the digest joins
  values positionally and a blank seventh value changes the digest. That last point is a migration
  concern: rows tallied before the change hash six values, rows after hash seven, so the same key
  lands on two rows across the boundary day. Once, on upgrade day, and the tally is comparative.
- **`capture.COOKIE_KEYS`**: short cookie key per frozen field. `ref` needs one.
  **`COOKIE_DROP_ORDER`** lists the fields dropped when the payload is oversize; attribution-key
  fields are never in it, so `ref` must not be either.
- **`resources.py`** exports every model field except `site`; a new column is exported without
  work, and the admin `list_display` / `list_filter` / `search_fields` lists are where a new column
  is made visible.

## 3. How the middleware behaves, precisely

`AttributionCaptureMiddleware` sits directly after `CurrentSiteMiddleware`.

1. Not a GET, or no tracked parameter in `request.GET` → passes through, no work.
2. Valid signed cookie already present → passes through; `Vary: Cookie` is still added.
3. `get_cached_site(request)` is not a `Site` (rejected Host → `UnknownSite`) → passes through.
4. Otherwise the first touch is read off the request **before** the view runs, and the cookie is
   set and the tally incremented on the response **after** the view returns, whatever the status
   code. A 302 from the view still mints.

Consequences for this work:

- A request to `/go/{code}?utm_source=x` carries a tracked parameter, so without suppression it
  mints a cookie with `landing_path=/go/{code}` and no `ref`, and the tally counts the redirect
  rather than the destination. Suppression has to be specific to the two routes. Skipping every 3xx
  response would also skip a real tracked landing on a page that redirects to login, which is a
  landing the shipped design counts today.
- A visitor who already holds the cookie and arrives via `/go/{code}` is passed through at step 2.
  The hit is logged by the view; the code never reaches the cookie, the tally or the eventual
  `SignupAttribution` row. First touch stays frozen, which is the shipped contract.
- `ref` typed by hand on any URL (`/?ref=whatever`) is captured like any other tracked parameter.
  Nothing validates it against a table, and the shipped design's "no query on an ordinary request"
  property holds because validation would only ever run on the mint path, where a query already
  happens.

## 4. The signup write

`signals.record_attribution_on_signup` on allauth's `user_signed_up`, best-effort inside a
savepoint, `DatabaseError` reported to Sentry and swallowed so the signup completes. The row copies
the cookie payload verbatim into columns; it holds strings, not foreign keys, and `save()` refuses
updates. A `referral_code` column on it is a snapshot of the code text. Nothing can later repoint
it, which is the property the idea wants ("share a value rather than a row").

## 5. Admin conventions now in force

- Both shipped admins extend `SiteAwareExportModelAdmin` (`site_aware_models/admin.py`), which
  wraps `django-import-export` with FLS's `FormulaSafeCSV` format, BOM, ISO timestamps and a
  view-permission export gate. Any new changelist in this app gets a CSV export by declaring a
  `resource_classes` entry; this is the house pattern now, not a per-feature choice.
- Both are fully read-only: `readonly_fields` covering everything, add/change/delete refused.
  `ReferralCode` would be the app's first writable admin.
- `SiteAwareModelAdmin` now ships a stylesheet that wraps long read-only values on phones.
- `USER_ERASURE_CASCADE_MODELS` in `accounts.admin` is the set of read-only audit models the User
  admin vouches for on delete. A hit log holds no `User` FK, so it does not join that set.
- `FirstTouchCount.count.help_text` is where the shipped admin states the "counts mints, bots
  inflate it" caveat. A hit counter saying the same thing in the same place is consistent.

## 6. Positions the shipped work took that this idea inherits or closes

- **No bot filtering on the tally.** `docs/product/signup-attribution.md` lists it under "Not
  built". A machine-fetch verdict on hits does not change that; the tally stays unfiltered.
- **No per-visitor landing record.** Nothing is written at landing except the tally. The idea's
  "hold nothing that describes the visitor" reading of the hit row is the same position.
- **Partner referral codes deferred**, in spec §3 "Out", spec §8 and the product page's "Not built",
  with the deferred plan being a code held on `Organisation`. This idea closes that item with a
  different home. The done directory's `research_referral_codes.md` still argues for the
  `Organisation` FK and the reasons it gives (stable code text, no reuse of `slug`, forbid
  reassignment) survive; only the FK does not.
- **`referral-link-tracker` in `docs/app_conventions.md`** is a planned extractable app that may
  not depend on `site_aware_models`. Spec §4 decided `referral_tracking` is not that app. Codes
  unique per `Site` cannot be that app either, so this work is not it. The convention doc's entry
  remains unreconciled with both features.
- **Retention.** No retention period ships for `SignupAttribution`; kept until the `User` cascade.
  A pruning command for hits would be the first retention tooling in the app.

status: ok
