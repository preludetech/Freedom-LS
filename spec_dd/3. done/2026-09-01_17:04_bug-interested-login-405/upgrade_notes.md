---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: bug-interested-login-405

An anonymous visitor who clicked **"I'm interested"** on a coming-soon course and
then signed in landed on the POST-only express-interest URL with HTTP 405. The
click now survives sign-in: the visitor returns to the course detail page with
the interest recorded.

## Breaking changes

**`course_interest` partial views no longer carry `@login_required`.**
`partial_express_interest` and `partial_remove_interest`
(`freedom_ls/course_interest/views.py`) handle the anonymous case themselves.
The response an anonymous POST gets has changed shape:

- htmx request (`HX-Request` header): **204** with an `HX-Redirect` header
  pointing at the login page. It used to be a 302 that htmx followed inside its
  XHR, swapping the whole login page into the CTA element.
- non-htmx request: still a **302** to the login page, but `next` is now a
  GET-safe URL instead of the POST-only endpoint.

If you have code or tests asserting a 302-to-login on
`course_interest:express_interest` / `course_interest:remove_interest` for an
htmx request, they need updating to the 204 + `HX-Redirect` shape.

**`RegistrationCompletionMiddleware` redirect shape changed.**
`freedom_ls/accounts/middleware.py` now routes through `redirect_to_auth`
instead of a bare `redirect()`. A full-page GET/HEAD gets a 302 to
`accounts:complete_registration` **with a `?next=` back to the requested page**
(it previously dropped the intent). A POST or an htmx request still goes to the
completion page, and an htmx request gets 204 + `HX-Redirect` rather than a 302.
Downstream code that subclasses this middleware or asserts on its plain 302
should be reviewed.

**New URL name** (additive, nothing to change unless you reverse it):
`course_interest:deferred_express_interest`, served at
`interest/courses/<slug:course_slug>/deferred-express-interest/`. It is the
GET-safe landing view that records the interest after sign-in, and it only
writes for the slug the POST view stashed in the session — a bare GET of the URL
records nothing.

**New shared helper**: `freedom_ls.accounts.utils.redirect_to_auth`. Use it
wherever you send a visitor to an auth page from a view htmx may call. Its
`next_url` must be GET-safe and built server-side (e.g. with `reverse()`); never
pass through a user-supplied `next` without
`url_has_allowed_host_and_scheme()`.

## Manual steps

1. Review and re-apply your customisations to the two changed templates:
   - `freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html`
     — both forms gained `hx-disabled-elt="find button"`, which blocks a second
     click landing before the swap from escaping htmx and submitting the form
     natively (a full page reload).
   - `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`
     — the two-column wrapper gained an explicit `grid-cols-1`, so a long locked
     topic title no longer makes the page scroll sideways on a phone.
2. Nothing else. No migrations, no new packages, no settings keys, no new system
   checks. `grid-cols-1` is already used elsewhere in FLS templates, so an
   existing Tailwind bundle already contains it and does not need rebuilding.

`config/settings_dev.py` also flipped `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE` and
`OVERRIDE_COURSE_ACCESS_TO_FREE` to `False` so the FLS dev site exercises real
visibility and access rules. Those are FLS's own demo-project dev settings and
both keys already default to `False` in `freedom_ls/course_access/config.py` —
downstream projects keep their own settings and need do nothing.
