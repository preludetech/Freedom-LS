# Notifications core

Spec 1 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

FLS gets a notification layer: a way to tell a user about their own activity and a place in the
product where they see it.

- A new `comms` app. One call raises a notification for one user. The notification is stored for
  that user and shows up in the product.
- A bell with an unread badge in the shared header bar. It opens a panel of recent notifications
  and keeps its count current by HTMX polling.
- A notification centre page that lists all of a user's notifications, with mark-as-read.
- The first two events: a learner's course registration and a learner's course completion.

## Why

FLS has no way to tell a user something about their own activity after the moment has passed.
Django's `messages` toasts disappear with the response that queued them. The only outward event
mechanism, `fire_webhook_event`, sends events to external systems and never to the user.
Application review, deadlines and direct messaging all need somewhere to say "this happened to
you". This spec builds that place once, with two events that already have hooks, so that later
features only add events.

## What is settled

**Raising a notification**

- Any feature raises a notification with one call that names the recipient user, a category and
  the target the notification is about. The caller does not know how delivery happens.
- A notification belongs to one `User` on one site, not to a `Learner`. Educators receive
  notifications too, and a notification is not scoped to an organisation.
- The caller supplies the site. It reads `site_id` off the row the event is about, which a
  `LearnerCourseRegistration` and a `CourseProgress` already carry, or background work passes it
  explicitly. The site never depends on a current request, so raising works in management commands and tasks. Unlike
  `fire_webhook_event`, which silently does nothing outside a request, raising a notification
  never silently drops one.
- FLS raises a notification only after the change it announces has committed, and a failure to
  notify never breaks the registration or completion that raised it. `course.registered` already
  works this way, through `transaction.on_commit` in `freedom_ls/learner_progress/signals.py`.

**Categories**

- `comms` owns the category registry. Raising a notification with an unknown category is an
  error.
- Categories are declared the way `WEBHOOK_EVENT_TYPES` declares event types: an app setting whose
  default is an FLS constant, which a downstream project extends in its own settings. Each
  category carries a stable key (`course.registered`, `course.completed`), a human label and an
  icon resolved through `c-icon`. Spec 2 adds a default email on/off and later specs may add an
  audience. The key survives relabelling because preferences, per-site defaults and digests key
  off it.
- `comms` does not import `webhooks`. If `webhooks` ever reads the categories, it does so one way,
  without a dependency on `comms`. `research_category_registry.md` compares the options.

**What a notification stores and how it links**

- A notification stores its category, a target and a small snapshot of the facts it displays,
  such as the course title, taken at the moment it is raised. The target is a generic foreign key with
  the same shape as `ObjectRoleAssignment.target`, so later categories can point at conversations
  or deadlines without a new column.
- Its text comes from a translatable template for each category, filled from the snapshot.
  Renaming a course does not rewrite past notifications.
- Its link is built from the live target each time it is shown. No URL is stored, because a
  course's slug is re-derived from its title on every content reload. If the target no longer
  exists, the notification still shows its text, without a link.
- `research_notification_content_and_targets.md` has the reference implementations and the
  course rename and delete behaviour.

**Delivery**

- Every notification is written to the in-app store first. It is always on, needs no
  configuration and is not swappable.
- Additional delivery backends sit on top: an app setting lists zero or more import paths
  resolved with `import_string`, each implementing a declared contract in the manner of
  `COURSE_ACCESS_BACKEND`. The list is empty in this spec. Spec 2 adds email to it without
  touching any caller, and decides per category and per user inside its backend.
- A backend acts only on a stored notification. It runs as its own queued task with `site_id`
  passed explicitly, so one backend failing affects neither the stored notification nor another
  backend. `research_delivery_backend_seam.md` compares this with Laravel, Noticed and Moodle.

**The first events**

- **Course registration.** A learner with a new, active `LearnerCourseRegistration` gets a
  notification. The `post_save` receiver that announces `course.registered`,
  `ensure_course_progress_on_learner_registration`, raises it, so it covers every creation path:
  learner self-registration, the Django admin, QA commands, and future educator and bulk
  registration.
  Staff-created registrations get the same notification as self-registrations. Reactivating an
  existing registration does not notify again.
- **Course completion.** A learner who completes a course gets a notification, raised from the
  branch in `course_finish` that stamps `completed_time` and fires `course.completed`. That branch
  runs once per learner and course. The learner is already looking at the completion page, so
  this notification serves as the durable record and as what spec 2 emails.
- Cohort registration and cohort membership changes raise no notification. They fire no event
  today, and naming those events belongs to the educator interface's spec 7.
- `research_first_events_edge_cases.md` has every creation path and the idempotency analysis.
- No notifications are backfilled. Every bell starts empty on the day this ships, and an
  educator's bell stays empty until a later spec adds an event that reaches them.

**Seen and read**

- A notification is **seen** or **read**, and the two are separate. Opening the bell panel or
  the notification centre marks everything so far as seen, which clears the badge. A
  notification becomes read only when the user follows its link or marks it read. The badge
  counts unread notifications the user has not yet seen; the panel and centre mark every unread
  notification until it is read.
- A user can mark one notification read, mark all read, and mark a read notification unread
  again.
- `research_read_state_and_retention.md` surveys how GitHub, Slack, Linear, Discourse, Moodle and
  Canvas handle this.

**Surfaces**

- The bell and badge live in `partials/header_bar.html`, immediately left of the avatar menu.
  That template is shared by the learner dashboard, the course player and the educator
  interface, so every signed-in user sees the bell, learners and educators alike.
- The badge caps at "99+". The bell's accessible name reads the count ("Notifications, 3 new"),
  and the count sits in a `role="status"` live region so a polled change is announced politely.
- The bell opens a panel of the most recent notifications (about eight), each with a category
  icon, one line of text, a relative time and an unread marker. The panel footer has "Mark all
  as read" and "See all". At 375px the panel is a full-width sheet.
- The notification centre is a full page reached from "See all". It has All and Unread filters,
  groups notifications by day (Today, Yesterday, then dates), and lets the user mark one or all
  read. It pages with the numbered pagination FLS already uses (`c-pagination`), and a day may
  split across a page boundary.
- Every notification is kept. Nothing ages out in this spec. If retention is wanted later, it is
  one more sweep in the existing `fls_run_housekeeping`.
- Unread state is shown by icon, text and weight together, never by colour alone. Every control
  is keyboard-reachable with a visible focus ring. Every screen meets WCAG 2.2 AA and works at
  375px.
- The screens follow the Claude Design design (`user-communication/design.md`) for the bell, panel and notification centre,
  including the empty, all-read, unread and error states. Colours come from FLS role tokens and
  icons from `c-icon`, so re-themed sites follow.

**Polling**

- HTMX polling is the only transport. Nothing depends on Django Channels, ASGI or a channel
  layer. This is the first poller in FLS.
- The badge polls every 45 seconds while the tab is visible, and refreshes as soon as a hidden
  tab becomes visible again. The interval is a `comms` app setting defaulting to 45.
- Marking notifications seen or read updates the badge in the same response, without waiting for
  the next poll.
- A poll from an expired session sends the browser to sign in. It never swaps a login page into
  the header; `redirect_to_auth` already does this for HTMX requests.
- The unread count is not cached. `research_badge_polling_in_fls.md` has the per-request cost and
  the HTMX pitfalls.

**Words**

- A notification is not a toast. "Messages" in FLS already means `django.contrib.messages` toasts
  and, from spec 4 of this effort, direct messages. This spec's noun is **notification**.
- **Seen** and **read** are the two states above, and only those.

## Out of scope

- Email delivery, notification preferences and unsubscribe (spec 2), and digests and quiet
  hours (spec 7).
- Direct messages and the message item in the bell (spec 4).
- Real-time push over Django Channels (spec 8).
- Cohort registration, membership and deadline events, application approved and rejected, and
  course-launch notifications for interested learners. Each lands with the feature that owns the
  event, through this spec's call.
- A welcome notification on signup (`user.registered`), and allauth's account mail.
- Showing a new notification as a toast.
- Retention and age-out.
- Changing `fire_webhook_event` or the webhook event registry.

## Resources

- Research in this directory: `research_prior_notification_ux.md` (badge patterns, polling
  intervals, ARIA and keyboard rules for unread indicators) and the six `research_*.md` files
  cited above.
- `spec_dd/1. next/user-communication/research_notification_sources_and_delivery.md`: every
  event hook in FLS today and the delivery and task stack.
- `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md`: the
  shared header bar as the bell's home, the `COURSE_ACCESS_BACKEND` pattern, and the multi-tenant
  rules for writing rows from background work.
- `spec_dd/1. next/user-communication/research_comms_ux_pitfalls.md`: notification fatigue, the
  "one place to check" principle, and accessibility failures in badges.
- `spec_dd/1. next/user-communication/research_comms_patterns.md` and
  `research_lms_comms_landscape.md`: notification data-model patterns and how other LMSs do it.
- `spec_dd/1. next/user-communication/design.md`: the Claude Design design for the bell, the panel and the notification centre
  (brief sections 1 and 2). Read it through the Claude Design integration, as that file says.
- `spec_dd/1. next/user-communication/design_brief.md` (sections 1 and 2): the brief it was drawn from.
- Code this builds on: `partials/header_bar.html`, `freedom_ls/webhooks/config.py`,
  `freedom_ls/learner_progress/signals.py`, `course_finish` in
  `freedom_ls/learner_interface/views.py`, `freedom_ls/course_access/loader.py`,
  `freedom_ls/role_based_permissions/models.py` (`ObjectRoleAssignment`),
  `freedom_ls/accounts/utils.py` (`redirect_to_auth`), `freedom_ls/deployment/housekeeping.py`.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `ds:app-settings`,
  `fls-dev:app-settings`, `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`,
  `fls-dev:icon-usage`, `fls-dev:testing`, `fls-dev:playwright-tests`.
