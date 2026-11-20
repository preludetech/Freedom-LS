---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/header_bar_user_menu.html
  - freedom_ls/base/templates/cotton/dropdown-menu.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form.html
  - freedom_ls/base/templates/allauth/layouts/manage.html  # deleted; replaced by freedom_ls/accounts/templates/allauth/layouts/manage.html
  - freedom_ls/accounts/templates/accounts/profile.html  # deleted
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
- The template `accounts/profile.html` is deleted. An override of it in a downstream project is no
  longer rendered; move its customisations into the new templates under
  `freedom_ls/accounts/templates/accounts/` (`account_page.html`, `_account_shell.html`,
  `panels/name.html`, `panels/profile_picture.html`, `partials/`).
- `allauth/layouts/manage.html` moved from `freedom_ls/base/templates/` to
  `freedom_ls/accounts/templates/`, and now renders the allauth pages (email, password and so on)
  inside the account area's sidebar layout. A downstream override at the same template path still
  wins, but it now replaces the sidebar layout.

## Manual steps

- Rebuild Tailwind: the new account templates use utility classes the bundle may not hold yet.
- If you override `partials/header_bar_user_menu.html`, re-apply your changes: the avatar markup moved
  to the new `partials/header_avatar.html`, the menu's accessible name now comes from that partial's
  `sr-only` text, and the menu item reads "Account" instead of "Profile".
- If you override `cotton/dropdown-menu.html`, note it now omits `aria-label` when `aria_label` is
  empty.
- If you override `panel_framework/partials/inline_record_form.html`, its `<form>` class changed from
  `space-y-3` to `flex flex-col gap-3 space-y-0`.
- Search your project for `account_profile_picture`, `edit_profile` and `accounts/profile.html` and
  update each reference as described above.
