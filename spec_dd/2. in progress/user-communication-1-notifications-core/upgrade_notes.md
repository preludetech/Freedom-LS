---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/header_bar.html
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/cotton/button.html
  - freedom_ls/base/templates/cotton/pagination.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: add "freedom_ls.comms"; not enforced by a check, but every page with the header fails to render without it
  - NOTIFICATIONS_ENABLED  # optional: default False; True shows the bell
  - NOTIFICATION_CATEGORIES  # optional: default FLS_NOTIFICATION_CATEGORIES
  - NOTIFICATION_DELIVERY_BACKENDS  # optional: default []
  - NOTIFICATION_BADGE_POLL_SECONDS  # optional: default 45
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: user-communication-1-notifications-core

FLS now has in-app notifications in a new `freedom_ls.comms` app. It adds a bell in the header, a notification centre at `/notifications/`, and one event: `course.registered`, raised when someone else registers a learner for a course.

## Breaking changes

- **New required app.** `freedom_ls/base/templates/partials/header_bar.html` now runs `{% load comms_tags %}`, and registering a learner now writes a `Notification` row. A project whose `INSTALLED_APPS` doesn't include `"freedom_ls.comms"` fails on every page that renders the header, and on every new course registration. Projects that take `INSTALLED_APPS` from `config/settings_base.py` get the app automatically. No system check enforces this.
- **Registrations now notify the learner unless `self_registered` is set.** `LearnerCourseRegistration` has a new `self_registered` boolean (default `False`). When a new registration is created with `self_registered=False`, the learner gets a `course.registered` notification. FLS's own self-registration view (`learner_interface.views.initiate_course_access`) sets it to `True`. If your project has its own code where learners register themselves, set `self_registered=True` on create. Otherwise those learners get notified about a registration they made themselves. Registrations that existed before the migration stay `False` and raise nothing, because only new registrations are announced.

## Manual steps

1. Add `"freedom_ls.comms"` to `INSTALLED_APPS` if your settings don't take it from `config/settings_base.py`.
2. Include the URLs if your root URLconf doesn't take them from `config/urls.py`: `path("notifications/", include("freedom_ls.comms.urls"))`. The app namespace is `comms`.
3. Run `uv run manage.py migrate`. This applies `freedom_ls_comms.0001_initial` (the `Notification` table) and `freedom_ls_learner_management.0002_learnercourseregistration_self_registered`.
4. Set `NOTIFICATIONS_ENABLED = True` to show the bell. It is off by default, so the bell renders nothing. Notifications are still recorded and the `/notifications/` URLs still answer, so the history is already there when a site turns the bell on.
5. Optional settings, all read through `freedom_ls.comms.config`:
   - `NOTIFICATION_CATEGORIES`: defaults to `FLS_NOTIFICATION_CATEGORIES` from `freedom_ls.base.notification_categories`. To add your own categories, append `NotificationCategory(...)` entries from the same module. To stop FLS raising a category, leave it out of the list.
   - `NOTIFICATION_DELIVERY_BACKENDS`: a list of dotted paths to `freedom_ls.comms.delivery.NotificationDeliveryBackend` subclasses. Each one is run as a `django.tasks` task for every stored notification. Defaults to `[]`.
   - `NOTIFICATION_BADGE_POLL_SECONDS`: how often the badge polls. Defaults to `45`.
6. Run `uv run manage.py check`. Two new checks can fire: `freedom_ls_comms.E001` (two categories in `NOTIFICATION_CATEGORIES` share a key) and `freedom_ls_comms.E002` (a `NOTIFICATION_DELIVERY_BACKENDS` path doesn't import).
7. Run `npm run tailwind_build`. The bell, panel and centre templates under `freedom_ls/comms/templates/` use utility classes your bundle doesn't have yet.
8. If your theme shadows any template in `changed_template_paths`, merge the changes into your copy:
   - `partials/header_bar.html`: `{% load comms_tags %}` at the top, and `{% notification_bell %}` next to the user-menu include inside a `flex items-center gap-2` wrapper. Without the tag, the bell never appears.
   - `_base.html`: a new `<script defer src="{% static 'comms/js/alpine-components.js' %}">` after the base Alpine components. The bell needs it.
   - `cotton/button.html`: a new optional `autofocus` attribute.
   - `cotton/pagination.html`: a new optional `push_url` attribute that adds `hx-push-url="true"` to the page links.

No Python or npm package changes.
