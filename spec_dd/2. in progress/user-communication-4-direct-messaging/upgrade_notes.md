---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/header_bar.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/quick_view_host.html
  - freedom_ls/panel_framework/templates/cotton/panel-search-field.html
requires_settings_change: true
changed_settings:
  - MESSAGING_ENABLED            # optional: default False; True turns direct messaging on
  - MESSAGE_MAX_LENGTH           # optional: default 2000
  - MESSAGE_PAGE_SIZE            # optional: default 30
  - MESSAGE_INBOX_POLL_SECONDS   # optional: default 45
  - MESSAGE_THREAD_POLL_SECONDS  # optional: default 8
  - NOTIFICATION_CATEGORIES      # optional: an explicit list must add message.received to opt in
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: user-communication-4-direct-messaging

FLS now has one-to-one direct messaging in `freedom_ls.comms`. Learners get an inbox at
`/messages/` and a Messages button in the header. Educators get a Messages section in the educator
interface and a message box in the learner quick view. Who may message whom is decided by the
`MessagingPolicy` from user-communication-3-messaging-policy.

Messaging is off by default. With `MESSAGING_ENABLED = False`, no messaging control renders, the
educator Messages section has no menu entry, and every messaging URL returns 404.

## Breaking changes

None. No new system check runs, and nothing changes until a project sets `MESSAGING_ENABLED = True`.

Two things to know if your project extends the messaging or notification code:

- **`MessagingPolicy` has two new methods, both with defaults.** `can_reply_many` answers
  `can_reply` for many conversations at once; the base version loops over `can_reply`.
  `group_recipients` arranges the recipient picker under headings; the base version returns one
  group with no heading. A custom policy that subclasses `freedom_ls.comms.messaging_policy.MessagingPolicy`
  keeps working without changes. Override `can_reply_many` if your `can_reply` costs queries, since
  the inbox calls it for every listed conversation. `can_reply`'s `conversation` argument is now
  typed `freedom_ls.comms.models.Conversation` instead of `Model`; the value passed is the same.
- **`NotificationCategory` has a new `rollup` field** (default `False`). A rollup category keeps one
  unread notification per user and target, and later events update that row. Your own categories
  are unaffected.

## Manual steps

1. Run `uv run manage.py migrate`. This applies `freedom_ls_comms.0002_conversation_message`
   (the `Conversation`, `ConversationParticipant` and `Message` tables) and
   `freedom_ls_comms.0003_notification_rollup_key` (a nullable `Notification.rollup_key` column and a
   partial unique constraint). No data migration runs.
2. Include the URLs if your root URLconf doesn't take them from `config/urls.py`:
   `path("messages/", include("freedom_ls.comms.messaging_urls"))`. The app namespace is
   `conversations`. The educator unread-count URL comes in with `freedom_ls.educator_interface.urls`.
3. Set `MESSAGING_ENABLED = True` to turn messaging on.
4. If you set `NOTIFICATION_CATEGORIES` to your own list rather than extending
   `FLS_NOTIFICATION_CATEGORIES`, add the `message.received` category from
   `freedom_ls.base.notification_categories` to get "New message from …" notifications. Left out, a
   new message raises no notification; messaging still works.
5. Optional settings, all read through `freedom_ls.comms.config`:
   - `MESSAGE_MAX_LENGTH`: the longest message body, in characters. Defaults to `2000`.
   - `MESSAGE_PAGE_SIZE`: messages per page of thread history. Defaults to `30`.
   - `MESSAGE_INBOX_POLL_SECONDS`: how often the header badge, the inbox list and the educator
     sidebar count poll. Defaults to `45`.
   - `MESSAGE_THREAD_POLL_SECONDS`: how often an open thread polls for new messages. Defaults to `8`.
6. Run `npm run tailwind_build`. The new templates under `freedom_ls/comms/templates/comms/` and
   `freedom_ls/educator_interface/templates/` use utility classes your bundle doesn't have yet.
7. If your theme shadows any template in `changed_template_paths`, merge the changes into your copy:
   - `partials/header_bar.html`: `{% messages_button %}` before `{% notification_bell %}`. Without
     it, the header has no Messages button.
   - `panel_framework/partials/sidebar_nav.html`: a new branch that renders a self-polling count
     element when a section sets `count_url`. Without it, the educator Messages section shows no
     unread count.
   - `panel_framework/partials/quick_view_host.html`: a new `data-quick-view-discard-prompt` block
     ("Discard your message?"). Without it, closing the quick view with an unsent message discards
     the draft without asking.
   - `cotton/panel-search-field.html`: a new optional `autofocus` attribute.
8. If you defined your own panel sections, `freedom_ls.panel_framework.views.SectionConfigBase` has three new
   classmethods, all with defaults: `is_available` (hide the section and 404 its paths),
   `get_menu_count_url` and `get_menu_count_poll_seconds` (a polled menu count). Nothing to change
   unless you want to use them.

No Python or npm package changes.
