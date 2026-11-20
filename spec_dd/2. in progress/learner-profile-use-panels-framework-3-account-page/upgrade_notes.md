---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/header_bar_user_menu.html
  - freedom_ls/base/templates/cotton/dropdown-menu.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form.html
  - freedom_ls/base/templates/allauth/layouts/manage.html  # deleted; replaced by freedom_ls/accounts/templates/allauth/layouts/manage.html
  - freedom_ls/accounts/templates/accounts/profile.html  # deleted
  - freedom_ls/accounts/templates/allauth/elements/h1__manage.html  # new
  - freedom_ls/accounts/templates/allauth/elements/form__manage.html  # new
  - freedom_ls/accounts/templates/allauth/elements/button__manage.html  # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form_submit.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_name.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_name.html
  - freedom_ls/accounts/templates/accounts/partials/profile_picture_form.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-profile-use-panels-framework-3-account-page

## Breaking changes

- The account page is now a panel-framework page. `/accounts/profile/` redirects to
  `/accounts/profile/personal-details/`, which holds a Name panel and a Profile picture panel.
  `accounts:account_profile` still resolves with no arguments; it also takes a `path_string`.
- The URL name `accounts:account_profile_picture` (`profile/picture/`) is gone. Picture upload and
  removal are panel actions under `/accounts/profile/personal-details/__panels/...`. Replace any
  `{% url 'accounts:account_profile_picture' %}` or `reverse()` of it with
  `accounts:account_profile`.
- The views `freedom_ls.accounts.views.edit_profile` and `edit_profile_picture` are gone; the URL
  now routes to `freedom_ls.accounts.views.account_area`.
- `ProfilePictureForm` no longer has a `remove_profile_picture` checkbox field. Removal goes through
  `freedom_ls.accounts.forms.remove_profile_picture(user)`.
- `ProfilePictureForm` refuses a submit with no file ("Choose a picture first."). It used to
  validate and save nothing.
- The template `accounts/profile.html` is deleted. An override of it in a downstream project is no
  longer rendered; move its customisations into the new templates under
  `freedom_ls/accounts/templates/accounts/` (`account_page.html`, `_account_shell.html`,
  `panels/name.html`, `panels/profile_picture.html`, `partials/`).
- Email addresses and the password are panels on Personal details now. The account sidebar no
  longer lists Email or Password. allauth's `/accounts/email/` and `/accounts/password/change/`
  redirect to Personal details; their URL names (`account_email`, `account_change_password`)
  still reverse to the same paths. `/accounts/password/set/` keeps allauth's page (an application
  claim sends users there with a `next`), drawn by the manage layout. The redirect
  patterns live in `freedom_ls.accounts.urls`, so **include `freedom_ls.accounts.urls` before
  `allauth.urls`** under the same prefix in your root URLconf, or allauth's own pages keep
  answering.
- `allauth/layouts/manage.html` moved from `freedom_ls/base/templates/` to
  `freedom_ls/accounts/templates/`, and renders allauth's remaining management pages
  (connections, two-factor, sessions) in the account shell, shaped like a panel page: the heading
  as the header band with the navigation toggle beside it (`allauth/elements/h1__manage.html`),
  each form as a card with its buttons in the footer (`form__manage.html`, `button__manage.html`).
  A downstream override at the same template path still wins, but it now replaces that layout.
- A panel form's submit button sits in the card footer. `inline_record_form.html` no longer renders
  Save: render `panel_framework/partials/inline_record_form_submit.html` (`form_id`, optional
  `label`) in the panel template's `panel_actions` block after `{{ block.super }}`. The form's
  `hx-disabled-elt` and `hx-indicator` point at `#<form_id>-submit`. A panel template that
  includes the inline form and leaves `panel_actions` alone now has no Save button, and the
  invariant `panel_framework/tests/invariants/test_panel_form_buttons.py` fails on any panel body
  that renders a submit.

## Manual steps

- Rebuild Tailwind: the new account templates use utility classes the bundle may not hold yet.
- If you override `partials/header_bar_user_menu.html`, re-apply your changes: the avatar markup moved
  to the new `partials/header_avatar.html`, the menu's accessible name now comes from that partial's
  `sr-only` text, and the menu item reads "Account" instead of "Profile".
- If you override `cotton/dropdown-menu.html`, note it now omits `aria-label` when `aria_label` is
  empty.
- If you override `panel_framework/partials/inline_record_form.html`, its `<form>` class changed from
  `space-y-3` to `flex flex-col gap-3 space-y-0`, its field row lost `items-end`, and its Save
  button moved out (see Breaking changes).
- Move `path("accounts/", include("freedom_ls.accounts.urls"))` above
  `path("accounts/", include("allauth.urls"))` in your root URLconf.
- An inline form in a panel now also works with JavaScript off. `inline_record_form.html` gained
  `method="post"`, `action="{{ action_url }}"` and `{% csrf_token %}`; an override of it, or a
  template that renders its own inline form, needs the same three. A `FormPanelAction` with
  `renders_in_footer = False` answers a POST that has no `HX-Request` header with a 303 to the
  page, the outcome as a flash. A test that posts to such an action and reads the fragment must
  send `HX-Request: true`.
- Search your project for `account_profile_picture`, `edit_profile` and `accounts/profile.html` and
  update each reference as described above.
