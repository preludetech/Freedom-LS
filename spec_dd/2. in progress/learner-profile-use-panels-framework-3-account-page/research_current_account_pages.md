# Research: the personal / self-service account pages today

Read-only inventory for the idea "Update the personal profile settings pages to use the panel framework". The profile model side is in `spec_dd/1. next/learner-public-profile/research_existing_profile_code.md`; not repeated here.

## Summary

- Only ONE FLS-owned settings page exists: `accounts:account_profile` (name and picture-to-come). Everything else the user can reach is stock allauth, wrapped by one FLS layout override.
- Enabled allauth apps are `allauth` and `allauth.account` only (`config/settings_base.py:154-155`). There is no `allauth.mfa`, `allauth.socialaccount`, `allauth.usersessions` or `allauth.headless` in `INSTALLED_APPS` (headless URLs are commented out, `config/urls.py:84`). So there are NO MFA / TOTP / recovery code / passkey / session / social-connection / reauthentication-specific pages today. The `manage.html` nav links for them are guarded with `{% url ... as x %}`, so they silently do not render.
- There is no notification/email preference page, no messaging preference page, no time-zone or language picker for users, and no legal-consent "settings" page.
- Where "panel" shows up: `freedom_ls/panel_framework` is a separate app (educator-oriented). The account pages do not use it. The existing public-profile ideas explicitly say account editing stays on plain views in `accounts`, NOT the panel framework (see the last section) — the idea being cut reverses that decision, so those four specs' constraint lines will need updating.

## Page inventory

### 1. `accounts:account_profile` (path `/accounts/profile/`)

| Item | Detail |
|---|---|
| URL | `freedom_ls/accounts/urls.py:8-12`, name `account_profile`, namespace `accounts` (`app_name`, line 5); mounted at `accounts/` in `config/urls.py:71` (allauth is mounted at the same prefix on line 70) |
| View | `edit_profile`, `freedom_ls/accounts/views.py:29-40`. Function view, `@login_required`. On valid POST saves and adds a flash message "Profile saved" (no redirect, re-renders; no 422 on invalid) |
| Form | `UserForm`, `freedom_ls/accounts/forms.py:30-35`, ModelForm on `User`, fields `first_name`, `last_name`. Carries `# TODO: allow the user to upload a profile picture` (line 33; `learner-public-profile-1-profile-picture` completes it) |
| Template | `freedom_ls/accounts/templates/accounts/profile.html` (24 lines): `{{form}}` dumped raw, a `<c-button type="submit">`, plain `<h1>`. No panel components |
| Base layout | extends `allauth/layouts/manage.html`, i.e. the FLS override `freedom_ls/base/templates/allauth/layouts/manage.html`, which extends `allauth/layouts/base.html` (FLS override, one line: `{% extends "_base.html" %}`) |
| Edits | The signed-in user's own `first_name` / `last_name` |
| Who | Any authenticated user (learner or staff). Not exempt from registration completion: a user with incomplete registration forms is redirected away to `complete_registration` (not in `EXEMPT_URL_NAMES`, `freedom_ls/accounts/middleware.py:29-46`; asserted in `accounts/tests/test_middleware.py:43,254-259`) |
| Linked from | (a) Header user menu "Profile": `freedom_ls/base/templates/partials/header_bar_user_menu.html:18` (included from `partials/header_bar.html:24`, from `_base.html:118`; so every learner-facing page and any page on `_base.html`); (b) Educator interface sidebar, a settings (cog) icon, aria-label "Account settings", in the `#sidebar-user` block of `freedom_ls/educator_interface/templates/educator_interface/_shell.html:61-65`; (c) the `manage.html` nav does NOT link to it (it links only to the allauth pages below) |
| Tests | No direct test of the view's GET/POST or `UserForm`. Indirect only: `freedom_ls/accounts/tests/test_middleware.py` (uses the URL as the non-exempt probe, ~20 lines), `freedom_ls/educator_interface/tests/test_sidebar.py:173-187` (cog link href), `freedom_ls/contrib/conformance/test_urls.py:79` (login-required conformance probe), `freedom_ls/referral_tracking/tests/test_middleware.py:263`. A cut should add tests for the form save |

### 2. allauth account management pages (all from `allauth.account`, unnamespaced URL names, path prefix `/accounts/`)

All render inside the FLS `manage.html` layout (allauth's own templates extend `allauth/layouts/manage.html`, resolved to the FLS override because `freedom_ls.base` templates win the search; the comment at `config/settings_base.py:148` says allauth is last in `INSTALLED_APPS` precisely to override its templates). Only the layouts and `elements/button.html` are overridden; the page bodies (`account/email.html`, `account/password_change.html`, etc.) are allauth's stock templates from `.venv/.../allauth/templates/account/`. Overridden under `freedom_ls/base/templates/`: `allauth/layouts/{base,entrance,manage}.html`, `allauth/elements/button.html`, `account/login.html`, `account/signup.html`. No `account/email.html` or `account/password_*.html` override exists.

| URL name | Path | View (library) | Edits | Notes |
|---|---|---|---|---|
| `account_email` | `/accounts/email/` | allauth `EmailView` | add / remove / make primary / re-send verification for `EmailAddress` | Linked "Change Email" at `manage.html:13-16`. Exempt from registration-completion redirect (`middleware.py:38`) |
| `account_change_password` | `/accounts/password/change/` | allauth `PasswordChangeView` | the user's password (requires old password) | Linked "Change Password" at `manage.html:18-21`. NOT exempt in the middleware. Only valid if the user has a usable password; otherwise allauth redirects to `account_set_password` |
| `account_set_password` | `/accounts/password/set/` | allauth `PasswordSetView` | first password for passwordless users | Not linked from the nav; reached by redirect from change-password |
| `account_inactive`, `account_logout` | `/accounts/inactive/`, `/accounts/logout/` | allauth | logout is a flow; logout button via `partials/logout_button.html` (included in `manage.html:39` and the header menu) | `account_logout` is exempt |
| Login, signup, password reset, email confirmation, `account_email_verification_sent`, `account_reauthenticate` | various | allauth | one-off flows, `entrance.html` layout | Entrance flows, not settings. Reauthentication exists as an allauth URL but is only hit when allauth demands it before a sensitive action |
| MFA (`mfa_index`, TOTP, recovery codes, passkeys/WebAuthn) | n/a | not installed | | `manage.html:28-31` guards the link; renders nothing today |
| Sessions (`usersessions_list`) | n/a | not installed | | `manage.html:33-36`; renders nothing today |
| Social connections (`socialaccount_connections`) | n/a | not installed | | `manage.html:23-26`; renders nothing today |

Relevant allauth settings (`config/settings_base.py`): `ACCOUNT_LOGIN_METHODS = {"email"}` (436), `ACCOUNT_EMAIL_VERIFICATION = "mandatory"` (437), `ACCOUNT_ADAPTER` (441, `freedom_ls/accounts/allauth_account_adapter.py`), `ACCOUNT_FORMS = {"signup": SiteAwareSignupForm}` (442; no form override for email or password change), `ACCOUNT_PREVENT_ENUMERATION` (444), `ACCOUNT_RATE_LIMITS` (463; includes `change_password`-type limits, off in dev: `settings_dev.py:81`), `ACCOUNT_EMAIL_NOTIFICATIONS = True` (509, sends "password changed" etc. emails; email templates in `freedom_ls/accounts/templates/account/email/`).

Tests: `freedom_ls/base/tests/invariants/test_error_pages.py:55-63` posts to `account_change_password` (rate-limit/error-page invariant). `account_email` is hit in `accounts/tests/test_middleware.py:172` (exempt-list check) and `accounts/tests/test_admin.py` covers the `EmailAddress` admin, not the page. No dedicated tests of `manage.html` or the nav.

### 3. Preferences, time zone, language, notifications

None exist as user-facing settings.
- `freedom_ls/comms/urls.py` has the notification inbox only: `notification_list`, `notification_badge`, `notification_panel`, `notification_open`, `notification_mark_read/unread`, `notification_mark_all_read`. No preference view.
- `messaging_policy` has no `urls.py` (policy is per-site config, edited by staff, not per user).
- Time zone is per Site (`SiteTimeZoneConfig`, `freedom_ls/site_aware_models/models.py:198`); learners are only shown the site's zone via `shows_time_zone_to_learners` (`learner_interface/views.py:104,704-708`). No per-user choice.
- `grep` found no per-user language or email-preference model or view. Unsubscribe footer links exist only in email templates (`accounts/templates/emails/includes/footer_links.html`).

### 4. `complete_registration` and legal consent

- `accounts:complete_registration` (`/accounts/complete-registration/`, `urls.py:18-22`), view `complete_registration_view` at `views.py:76-113`, `@login_required`, template `accounts/templates/accounts/complete_registration.html` extending `allauth/layouts/entrance.html`. It is a ONE-OFF FLOW, not a settings page: `RegistrationCompletionMiddleware` (`middleware.py`, registered `config/settings_base.py:185`) redirects any user (except superusers and exempt URL names / static / media) with unfilled `additional_registration_forms` here; the view redirects away (to `next` or `LOGIN_REDIRECT_URL`) once there is nothing incomplete. Forms come from `get_effective_additional_registration_forms(policy)` and `registration_forms.py`. Tests: `accounts/tests/test_views.py:56-199`, `test_middleware.py`, `test_registration_forms.py`. QA data: `qa_create_incomplete_registration_learner`.
- Legal docs: `accounts:legal_doc` (`/accounts/legal/<terms|privacy>/`, `views.py:43-57`, template `accounts/legal_doc.html`) is a read-only public page, exempt from the middleware. Consent is captured at signup (`SiteAwareSignupForm`, `forms.py:124-241`, writes `LegalConsent` rows) and there is no page to view or withdraw consent. Not a settings page. Test: `accounts/tests/test_legal_doc_view.py`.

## The layout that ties them together

`freedom_ls/base/templates/allauth/layouts/manage.html`: a centred `max-w-2xl` column with `{% block content %}` on top and a plain vertical `<nav>` below it (a border-top, link list of Change Email, Change Password, Account Connections, Two-Factor Authentication, Sessions, then a logout button). It is a bottom link list, not a sidebar, and it does not include the "Profile" page in the list, so Profile and the allauth pages are not cross-linked in a consistent way: Profile is reachable from the header menu and the educator cog, and from Profile the user only sees the other pages through that bottom list. Note `profile.html` has no `<c-page-header>`-style heading; an `<h1>` is hand-written.

The educator sidebar (`_shell.html`) and the learner header (`header_bar_user_menu.html`) both link only to `accounts:account_profile`; neither links to email or password pages directly.

## Theme shadowing in concrete projects

`docs/how tos/theme-fls.md:80,287-324` documents that the active theme's `templates/` directory is prepended to the template search path (Tier 3), so a downstream theme can shadow any template by path, including `allauth/layouts/manage.html`, `accounts/profile.html`, `account/email.html`. Nothing in `docs/` or `claude_plugins/fls-dev` names these account templates or records a downstream project overriding them (greps for `allauth`, `account_profile` in docs and fls-dev only hit email templates, the Playwright login fixture and deployment checks). So I could not confirm any downstream project shadows them; moving `accounts/profile.html` to panel templates or renaming template paths is a compatibility risk for any theme that shadowed `accounts/profile.html` or `allauth/layouts/manage.html`, and should be called out in the spec's migration notes.

## What the learner-public-profile effort plans to add to the account area

- `learner-public-profile-1-profile-picture` (in progress, `spec_dd/2. in progress/`): upload / replace / remove one picture on `accounts:account_profile`; finishes the `UserForm` TODO; edits every avatar template (header menu, messaging, panel avatar chips). Line 47 of its idea: "Account editing stays on plain views in `accounts`, not the panel framework."
- `learner-public-profile-2-profile-and-page` (`spec_dd/1. next/`): a SEPARATE public-profile edit page (not `account_profile`), on plain views in `accounts`, in the style of `edit_profile`: blurb, work experience list, "open to work" switch, profile on/off switch, plus the anonymous public profile page at its own shareable link. Line 54: not the panel framework.
- `learner-public-profile-3-completed-courses`: adds a section to the profile edit page and the profile page to hide / re-show a completed course. Line 37: plain views in `accounts`.
- `learner-public-profile-4-certificates`: learner uploads self-reported certificates on the profile edit page (plain views); staff upload issued ones on a Certificates panel on the educator learner page (this one DOES use the panel framework).
- `learner-public-profile-5-index`, `-6-index-access`, `-7-contact`: index and contact; learner-facing styling, not panels. `-7` adds contact options chosen by the learner (account email is never shown without their choice), which will probably be a further settings section.
- Parent `spec_dd/1. next/learner-public-profile/idea.md:8` poses the open question that this cut answers: "should we use the panels framework for the user-profile and these settings?"

Roadmap hooks (`spec_dd/1. next/roadmap.md`): `educator-interface-refactor-1-scaffolding-and-common` is blocked by `learner-public-profile-1-profile-picture`; `extract_panels_framework-1..6` move the framework into its own package, so a learner-facing consumer should depend on the extracted package's template contract (`extract_panels_framework-4-template-contract`), and the framework is educator-styled (the educator `_shell.html`, `sidebar_nav`, `panel-avatar-chip`).

## Implications for a cut

Natural groupings:
1. **Profile and public-profile editing (FLS-owned)**: `accounts:account_profile` (`edit_profile`, `UserForm`, `accounts/profile.html`) plus the new public-profile edit page, picture, work experience, certificates and hidden-course sections from `learner-public-profile-1..4`. This is the real target; it is all plain Django views, so converting means a new panel-framework shell/page for the learner or staff user and moving the form into panels (needs the 422-on-invalid HTMX convention, which `edit_profile` lacks today).
2. **Sign-in security pages (allauth-owned)**: `account_email`, `account_change_password`, `account_set_password` (plus reauthentication and any future MFA / sessions / social pages if those apps are enabled). Converting means either (a) keeping allauth's views and wrapping them with an FLS layout that shares the panel shell and nav (cheapest: edit `manage.html` only), or (b) writing FLS views that use allauth's forms (`allauth.account.forms.AddEmailForm`, `ChangePasswordForm`, `SetPasswordForm`) and flows, which risks losing allauth's rate limits, reauthentication, notification emails and `AccountAdapter` hooks. Recommend (a) for the cut.
3. **Navigation**: `manage.html` bottom link list, header-menu "Profile" link (`header_bar_user_menu.html:18`), educator cog (`_shell.html:61`). One shared account-area nav (profile, email, password, public profile, later MFA) is the natural framework "sidebar/menu group" and fixes the inconsistent cross-linking.
4. **One-off flows (leave alone)**: `complete_registration`, `legal_doc`, login, signup, password reset, email confirmation. They use `entrance.html` and must work before the user is fully set up; the registration-completion middleware depends on them.

Constraints to carry into the spec:
- Layout-only decisions: the learner-facing pages must work for learners, who do not use the educator `_shell.html`; the panel framework currently has an educator shell, so a learner shell or generic shell variant is needed.
- `EXEMPT_URL_NAMES` (`middleware.py:29`) must stay in step with any renamed or new URL names.
- Four public-profile ideas state "not the panel framework" for account editing (`-1` line 47, `-2` line 54, `-3` line 37, `-4` line 53); they need amending, and `-1` is already in progress.
- No tests today cover `edit_profile`; add them before converting.
- Theme shadowing risk for `accounts/profile.html` and `allauth/layouts/manage.html` (see above).

status: ok
