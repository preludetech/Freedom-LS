---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: hide-messages-icon-in-toolbar-for-some-users

## Breaking changes

Every `MESSAGING_POLICY` must now implement `recipients_for`. With `MESSAGING_ENABLED` on, the
header calls it on every page render for each signed-in user with no conversation. A policy that
defines only `can_start` and `can_reply` and inherits the base `recipients_for`, which raises
`NotImplementedError`, now fails with a 500 on every page for those users, not only on
`/messages/`. The default `LayeredMessagingPolicy` already implements it.

With `MESSAGING_ENABLED` on, the header Messages button (the `messages_button` template tag in
`freedom_ls/comms/templatetags/comms_tags.py`) now shows only to a user who has an existing
conversation on the site, or to whom the configured `MESSAGING_POLICY` offers at least one
recipient. Other users no longer see it. The `/messages/` views behave as before.

The tag now takes the template context and reads `context["request"]`, like `notification_bell`.
The `{% messages_button %}` call in `freedom_ls/base/templates/partials/header_bar.html` is
unchanged, so a header override that calls the tag the same way keeps working, as long as the
`request` context processor is enabled.

## Manual steps

No action needed for projects using the default `LayeredMessagingPolicy`.

A project with its own `MESSAGING_POLICY`: make sure it implements `recipients_for`. The header now calls that policy's `recipients_for`
(followed by `.exists()`) on every page render for each signed-in user with no conversation. If
your `recipients_for` is expensive, every page pays that cost. A user with a conversation skips
the call.
