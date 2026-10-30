---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/comms/templates/comms/inbox.html  # deleted
  - freedom_ls/comms/templates/comms/start.html
  - freedom_ls/comms/templates/comms/thread.html
  - freedom_ls/comms/templates/comms/partials/closed_note.html
  - freedom_ls/comms/templates/comms/partials/composer.html
  - freedom_ls/comms/templates/comms/partials/conversation_row.html
  - freedom_ls/comms/templates/comms/partials/message_box.html
  - freedom_ls/comms/templates/comms/partials/messages_button.html
  - freedom_ls/comms/templates/comms/partials/notification_bell.html
  - freedom_ls/comms/templates/comms/partials/recipient_picker.html
  - freedom_ls/comms/templates/comms/partials/thread.html
  - freedom_ls/comms/templates/comms/partials/thread_older.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/conversation_last_message.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/conversation_state.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/conversation_with.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/modal/new_message.html  # deleted
  - freedom_ls/educator_interface/templates/educator_interface/panels/conversation_thread.html  # deleted
requires_settings_change: true
changed_settings:
  - MESSAGING_DEFAULT_FLAGS  # optional: the shipped default for learner_to_educator is now "open"
  - NOTIFICATION_CATEGORIES  # optional: only if your override lists message.received
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: user-communication-ux-improve

## Breaking changes

- **Learners can message their cohort admins by default.** The shipped default of
  `MESSAGING_DEFAULT_FLAGS["learner_to_educator"]` changed from `"closed"` to `"open"`. A project
  that never set `MESSAGING_DEFAULT_FLAGS` now lets learners start conversations with their
  educators. To keep the old behaviour, set `MESSAGING_DEFAULT_FLAGS` with
  `"learner_to_educator": "closed"`, or close it per organisation with an
  `OrganisationMessagingConfig` row.
- **Organisation and site admins can read learner-educator conversations.** The
  `organisation_admin` and `site_admin` roles gain `freedom_ls_comms.view_conversation`, scoped to
  the learner. Roles are read live, so this takes effect on deploy with no migration. Each open
  writes a `conversation.viewed` audit entry that shows on the learner's History tab. A project
  that defines its own role config should decide whether its admin roles get this permission.
- **Messages no longer raise notifications.** The `message.received` notification category is gone
  from `FLS_NOTIFICATION_CATEGORIES`, and so is its URL builder module
  `freedom_ls.comms.notification_urls`. A project whose `NOTIFICATION_CATEGORIES` setting lists a
  `message.received` category pointing at `freedom_ls.comms.notification_urls.conversation_url`
  must remove that entry, or rendering such a notification fails on the missing import. Existing
  `message.received` rows stay in the database; the notification queryset already hides rows whose
  category is not configured.
- **The educator interface's Messages section is gone.** `MessagesConfig` is removed from
  `freedom_ls.educator_interface.views` and from `interface_config`, so
  `/educator/organisations/<slug>/messages` no longer resolves, and nor does the URL name
  `educator_interface:messages_unread_count`. A project that imports `MessagesConfig` or builds its
  own `interface_config` around it must drop it. Educators now reach a learner's conversation from
  the learner page's new Messages tab.
- **`PICKER_LIST_ALL_LIMIT` is removed** from `freedom_ls.comms.messaging`. Code that imported it
  must stop.

## Manual steps

- Rebuild Tailwind: the messages panel, the messages page's thread pane, the oversight modal and
  the learner Messages tab add new templates with new utility classes.
- If you override any template in `changed_template_paths`, re-apply your changes against the new
  version. The deleted ones are no longer rendered; remove your overrides of them.
- Decide whether learners on your site should be able to message their educators (see the first
  breaking change) and set `MESSAGING_DEFAULT_FLAGS` if not.
