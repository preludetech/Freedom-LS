---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS                          # hard: add "import_export" after "unfold.contrib.import_export" or the changelists fail to render; add "freedom_ls.referral_tracking" or the feature is silently absent
  - MIDDLEWARE                              # hard: add AttributionCaptureMiddleware or no cookie is minted and every signup records as direct
  - REFERRAL_TRACKING_COOKIE_NAME           # optional: defaults to "fls_attribution"
  - REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS   # optional: defaults to 90
  - REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP   # optional: defaults to 1000
  - TRUSTED_PROXY_IP_HEADER                 # optional: existing key; unset behind a proxy, every row stores the proxy's address
requires_package_upgrade: true
changed_packages:
  - django-import-export>=4.4.1            # hard: new base dependency, pulled in by `uv sync`; brings tablib and diff-match-patch
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral tracking

A new app, `freedom_ls.referral_tracking`, records where each signup came from. A middleware
sets a signed, first-party, `HttpOnly` cookie on a visitor's first landing that carries
`advert_code`, a `utm_*` parameter or an ad-network click id, and tallies that first touch per
site per day. A receiver on allauth's `user_signed_up` signal then writes one read-only
`SignupAttribution` row per new user from the cookie plus the signup request's `_ga` / `_fbp` /
`_fbc` cookies, client IP and user agent. Two read-only admin changelists with a CSV export are the
whole interface. The export runs on `django-import-export`, which is new to FLS.

Nothing is wired up until you add the app and the middleware, and no system check enforces either,
so the failure modes below are the only warning you get. `freedom_ls.accounts` does not import the
new app, so a project that leaves it out of `INSTALLED_APPS` still boots and simply records
nothing. The dependency runs the other way: the app's admin and its signal receiver import
`freedom_ls.accounts`, so the app cannot be installed without it.

## Breaking changes

### Deleting a user from the admin now succeeds, and erases their audit rows

On `main`, the read-only `LegalConsent` admin blocked the User admin's delete confirmation with
a "permission needed" notice, because Django asks every cascaded model's admin for delete
permission. `UserAdmin.get_deleted_objects` now vouches for every model in
`freedom_ls.accounts.admin.USER_ERASURE_CASCADE_MODELS`, which holds `LegalConsent` and, once
the referral tracking admin loads, `SignupAttribution`, so deleting an account from the admin
goes through and takes both by cascade. The per-row admins stay read-only; account erasure is
the one path that removes those rows. If you subclass `UserAdmin` and override
`get_deleted_objects`, call `super()` or the block returns. If you add a read-only audit model
of your own that cascades from `User`, add it to that set from your admin module.

### Admin CSV exports run on `django-import-export`

FLS now depends on `django-import-export`, and `"import_export"` has to be in your
`INSTALLED_APPS`. Without it, any changelist whose admin extends the new
`freedom_ls.site_aware_models.admin.SiteAwareExportModelAdmin` raises `TemplateDoesNotExist`.
The referral-tracking admins are the first; further FLS exports will use the same base, so add
it once now. The export gives each such changelist an "Export selected ..." action and an
"Export" button that downloads the whole filtered list, both gated on the model's view
permission. The download is named `<Model>-<date>.csv`, carries no `site` column, and writes
booleans as `1`/`0`. Formula escaping and the UTF-8 BOM are applied by FLS's own
`FormulaSafeCSV` format; leave `IMPORT_EXPORT_FORMATS` and
`IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT` unset, since the package's own escaping is weaker
and would run first.

### `SiteAwareModelAdmin` and `GuardedSiteAwareModelAdmin` ship a stylesheet

Both bases now declare a `Media` class loading
`freedom_ls/site_aware_models/static/site_aware_models/css/admin.css`, which lets long
read-only values wrap on a phone instead of widening the page. Django merges admin `Media`
by inheritance, so an admin of yours that declares its own `Media` keeps it unless that class
sets `extend = False`. The file has to reach your static root; see "Manual steps".

### Signup attribution is written from a `user_signed_up` receiver

The row is written by `freedom_ls.referral_tracking.signals.record_attribution_on_signup`,
connected to allauth's `user_signed_up` signal, and nowhere else. allauth sends that signal
from `complete_signup()`, so any signup form that goes through allauth's signup view gets a
row, including one that does not subclass `freedom_ls.accounts.forms.SiteAwareSignupForm`.
A signup path of your own that skips `complete_signup()` writes no row. Accounts created by
the admin, a management command or an import get no row either; that is by design.

## Manual steps

1. **Add the apps to `INSTALLED_APPS`.** `import_export` goes after
   `unfold.contrib.import_export`, so Unfold's templates win lookup; the new app goes after
   `freedom_ls.accounts`:

   ```diff
     "unfold.contrib.import_export",
   + "import_export",
     ...
     "freedom_ls.accounts",
   + "freedom_ls.referral_tracking",
     "freedom_ls.organisations",
   ```

   `uv sync` installs `django-import-export` itself; if you pin packages by hand, add
   `django-import-export>=4.4.1`.

2. **Add the middleware to `MIDDLEWARE`**, directly after `CurrentSiteMiddleware`. It reads the
   current site from the thread-local that middleware populates, on both the request and the
   response phase:

   ```diff
     "freedom_ls.site_aware_models.middleware.CurrentSiteMiddleware",
   + "freedom_ls.referral_tracking.middleware.AttributionCaptureMiddleware",
     "allauth.account.middleware.AccountMiddleware",
   ```

   Leave it out and the project still boots, but no cookie is ever minted, the tally stays
   empty, and every signup records `utm_source="direct"` / `utm_medium="none"`.

3. **Run the migration.** `freedom_ls_referral_tracking.0001_initial` creates the
   `freedom_ls_referral_tracking_signupattribution` and
   `freedom_ls_referral_tracking_firsttouchcount` tables:

   ```
   python manage.py migrate
   ```

4. **Run `collectstatic`** on any deployment that serves static files from a collected root, so
   the new admin stylesheet and `django-import-export`'s own static files are served. Without
   it every admin page requests a 404 stylesheet; nothing breaks, but long values on a phone
   widen the page again.

   ```
   python manage.py collectstatic
   ```

5. **Grant view permissions.** Neither admin overrides `has_view_permission`, so `is_staff`
   alone shows nothing. Staff who should see the tables need
   `freedom_ls_referral_tracking.view_signupattribution` and
   `freedom_ls_referral_tracking.view_firsttouchcount`. The export action and the Export button
   are gated on that same view permission; there is no separate export permission. Superusers
   see both as usual.

6. **Optionally override the three new settings.** All have defaults and none is required:

   | Setting | Default | Meaning |
   | --- | --- | --- |
   | `REFERRAL_TRACKING_COOKIE_NAME` | `"fls_attribution"` | Name of the signed first-party cookie |
   | `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS` | `90` | How long a first touch stays frozen; enforced server-side from the signature |
   | `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` | `1000` | Distinct attribution keys tallied per site per day before further new keys fold into one overflow row |

   The cookie's `Secure` flag mirrors your existing `SESSION_COOKIE_SECURE`; there is no
   separate setting for it.

7. **Check `TRUSTED_PROXY_IP_HEADER` if you run behind a proxy or CDN.** The row's `client_ip`
   comes from the same `get_client_ip` the consent records use. With the header unset behind a
   proxy, every row stores the proxy's own address, and nothing warns you.

8. **If a CDN or shared cache fronts the site**, confirm it honours `Cache-Control: private,
   no-store` and `Vary: Cookie`. A response that mints the cookie carries both, so a cache that
   ignores them would serve one visitor's signed cookie to everyone after them and attribute
   their signups to the first visitor's campaign. Ordinary responses are untouched.

9. **Settle the privacy position before enabling capture in the EU or UK.** The operator of a
   downstream project is the data controller. The attribution cookie is unlikely to count as
   strictly necessary, so treat it like an analytics cookie under your consent banner. Reading
   `_ga`, `_fbp` and `_fbc` into a permanent record against a named account is a separate use
   of those identifiers, and the combination of click ids, cookies, IP and user agent against
   an identity usually calls for a data protection impact assessment. There is no retention
   period and no scheduled deletion: a row lives until its `User` is deleted, which
   `docs/product/security-and-data-handling.md` now states under retention. The full field
   list is in `freedom_ls/referral_tracking/models.py`.

No `npm install` and no Tailwind rebuild. The one Python package change is `django-import-export`.
