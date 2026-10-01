---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/comms/templates/comms/notification_list.html
  - freedom_ls/comms/templates/comms/partials/notification_badge.html
  - freedom_ls/comms/templates/comms/partials/notification_panel.html
  - freedom_ls/comms/templates/comms/partials/notification_row.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: better-looking notifications

## Breaking changes

None. Behaviour of the bell, panel and notification centre is unchanged; only their markup and
classes changed.

`NotificationCategory` (`freedom_ls/base/notification_categories.py`) gains an optional `colour`
field that defaults to `None`, so existing `NOTIFICATION_CATEGORIES` entries keep working. A
category with no colour gets a neutral icon tile.

## Manual steps

1. **Rebuild Tailwind** (`npm run tailwind_build`). The notification templates use utility classes
   that may be missing from an existing bundle, such as `bg-primary/5`, `ring-header`,
   `line-clamp-2` and the coloured icon-tile classes.
2. **Review template overrides.** If your project shadows any of these templates, compare your copy
   with the new FLS version and carry the changes across:
   - `comms/notification_list.html`
   - `comms/partials/notification_badge.html`
   - `comms/partials/notification_panel.html`
   - `comms/partials/notification_row.html`: the whole row is now the click target (the link
     stretches with `after:absolute after:inset-0`, and the action column sits above it with
     `relative z-10`), unread rows are tinted, and the icon sits in a tile coloured by
     `notification.colour`.
3. **Optional: colour your notification categories.** Set `colour=NotificationColour.<MEMBER>` on a
   `NotificationCategory` in your `NOTIFICATION_CATEGORIES` setting to give its tile a colour. The
   members are `PRIMARY`, `SUCCESS`, `WARNING`, `INFO` and `ERROR`, imported from
   `freedom_ls.base.notification_categories`.
4. **Optional: icon overrides.** A new semantic icon, `check_all`, is used on the "Mark all as read"
   buttons. All four built-in icon sets map it. To use a different glyph, add a `check_all` entry to
   `FREEDOM_LS_ICON_OVERRIDES`.
5. **Optional, for projects using the `sdd` and `fls-dev` Claude Code plugins:** re-run `/sdd:init`
   and then `/fls-dev:init`. They add the `## Design Hooks` section and its `Design check` key to
   `.claude/sdd/config.md`, which `/sdd:implement_plan` uses to check built screens against a
   registered design. If you leave the key blank, the check is skipped.
