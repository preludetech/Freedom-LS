---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/account/login.html
  - freedom_ls/base/templates/account/signup.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: more-prominent-signup-button

## Breaking changes

- **Acquisition calls to action now send anonymous visitors to signup, not login.** "Apply now" (`course_applications:apply`), "Enrol for free" (`learner_interface:initiate_course_access`) and express interest (`course_interest:express_interest`) redirect to `account_signup` with `next` set. When the site is closed for signups (`SiteSignupPolicy.allow_signups` is false, or no policy row and `ALLOW_SIGN_UPS` is false), they still go to `account_login`. Every other `@login_required` view, and removing interest, still goes to login. Downstream tests that assert these three redirects land on the login page need updating.
- **FLS now ships its own `account/login.html`** (in `freedom_ls/base/templates/account/`), replacing allauth's stock page. The heading and submit button read "Log in" instead of allauth's "Sign In". A failed login shows a "New here?" callout inside a `role="alert"` region, linking to signup with the typed email. A project that already overrides `account/login.html` keeps its own page and does not get any of this.
- **`account/signup.html` changed.** The heading and page title are now "Create an account" (previously "Sign Up" and "Signup"). The "Already have an account? Then please sign in." sentence is replaced by a "Log in" button. The submit button still reads "Sign Up".
- **`freedom_ls/tests/playwright_fixtures.py`**: `_login_via_ui` now clicks a button named "Log in". A downstream project that uses these fixtures and overrides `account/login.html` with a different submit label must rename its button to "Log in", or its Playwright logins will time out.

## Manual steps

- If you override `account/login.html` or `account/signup.html`, compare your copy with FLS's and re-apply your customisations on top of the new version, or copy across the switch button and the failed-login callout.
- If you have your own acquisition views that should send anonymous visitors to signup, you can decorate them with `freedom_ls.accounts.decorators.acquisition_login_required` in place of `login_required`. This is optional.

No migrations, settings, packages or Tailwind rebuild are needed.
