---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/partials/header_bar_user_menu.html
  - freedom_ls/accounts/templates/accounts/profile.html
  - freedom_ls/comms/templates/comms/partials/participant_avatar.html
  - freedom_ls/comms/templates/comms/partials/recipient_picker.html
  - freedom_ls/educator_interface/templates/educator_interface/_shell.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/staff_member.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_settings.html
  - freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html
  - freedom_ls/panel_framework/templates/cotton/panel-person-link.html
requires_settings_change: true
changed_settings:
  - STORAGES  # hard: a hand-built dict must declare 'profile_pictures' or the process fails at model import
  - AWS_S3_PROFILE_PICTURES_BUCKET_NAME  # hard: check --deploy reports freedom_ls_deployment.E003 (or E002) without it
  - SECURE_CSP_REPORT_ONLY  # optional: only a project that defines its own CSP dict
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: learner-public-profile-1-profile-picture

Users can upload, replace and remove a profile picture on the account page. It shows in the header
user menu, messaging and the educator interface, with initials as the fallback. Pictures are stored
through a new fixed storage alias, `profile_pictures`, as 400×400 WebP files under
`profile_pictures/<user pk>/`.

## Breaking changes

- **`STORAGES` needs a `profile_pictures` entry.** `User.profile_picture` resolves its storage
  through `freedom_ls.accounts.models.get_profile_picture_storage` when models are imported. A
  project that writes its `STORAGES` dict by hand and leaves the alias out fails to start with
  `ImproperlyConfigured: settings.STORAGES has no 'profile_pictures' entry`. A project whose
  `STORAGES` comes from `freedom_ls.deployment.storage.build_storages()` gets the alias
  automatically, and `config/settings_base.py` declares it as `FileSystemStorage` for development.
- **Production needs `AWS_S3_PROFILE_PICTURES_BUCKET_NAME`.** The alias holds personal data and
  serves signed URLs only. Point it at the private user-data bucket, the same one `USER_UPLOADS`
  and `GENERATED` use. When the alias falls back to the shared `AWS_STORAGE_BUCKET_NAME`,
  `manage.py check --deploy` reports `freedom_ls_deployment.E003`. When no bucket is set at all and
  `DEBUG` is off, it reports `freedom_ls_deployment.E002`. The same per-purpose variables as the
  other aliases apply (`AWS_S3_PROFILE_PICTURES_ENDPOINT_URL`, `..._CUSTOM_DOMAIN` and so on), each
  falling back to its shared `AWS_S3_*` value.

## Manual steps

- Run `uv run manage.py migrate`. This applies `freedom_ls_accounts.0005_user_profile_picture`.
- If you build `STORAGES` by hand, add a `profile_pictures` entry. In production, set
  `AWS_S3_PROFILE_PICTURES_BUCKET_NAME`, then run `manage.py check --deploy`.
- If you define your own `SECURE_CSP_REPORT_ONLY` (or an enforced CSP), add
  `*media_csp_sources(PROFILE_PICTURES_PURPOSE)` to `img-src`. Both names are imported from
  `freedom_ls.deployment.storage`. Avatars load straight from the bucket. This adds nothing while
  pictures are on local disk.
- Allow a 10 MB request body on the account page (`/accounts/profile/`) in any reverse proxy in
  front of the app. Uploads up to 10 MB are accepted.
- Review overrides of the templates listed in `changed_template_paths`:
  - `_base.html` now loads `base/js/profile-picture-fallback.js` as a plain (not deferred) script
    outside any block. It removes an avatar `<img data-profile-picture>` that fails to load, so the
    initials show. An override that drops it shows broken images for missing pictures.
  - `accounts/profile.html` posts with `enctype="multipart/form-data"` and shows the avatar chip.
    An override without the enctype silently drops the upload.
  - `cotton/panel-avatar-chip.html` and `cotton/panel-person-link.html` take a new `picture_url`
    attribute. Pass it bound (`:picture_url="user.profile_picture_url"`). An empty value shows
    initials.
  - The other templates pass `picture_url` to the avatar chip, or render the picture in the header
    user menu.
- Rebuild Tailwind (`npm run tailwind_build`). The avatar markup uses utility classes your bundle
  may not include yet.
