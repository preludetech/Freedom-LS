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
- The first two events: a learner's own individual course registration, and a learner's course
  completion.

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
  what the notification links to. The caller does not know how delivery happens.
- A notification belongs to one user on one site. It is site-aware, like every other FLS row.
- Raising a notification works outside a request. Background work passes `site_id` explicitly,
  the way `fire_webhook_event` hands it to its dispatch task, because `SiteAwareManager` does not
  filter and `save()` does not set a site when no request is present.
- Every notification has a category ("Course registration", "Course completion"). Later specs key
  per-category preferences and email off it, so a category is a stable, named thing and not free
  text.
- Delivery goes through a backend seam. The in-app store is the first and only backend in this
  spec. A second backend (email) can be added without touching any caller. The seam follows the
  shape of `COURSE_ACCESS_BACKEND`: a declared contract and a setting resolved with
  `import_string`.
- The in-app notification centre is always on and needs no configuration.
- Each notification links back to what it is about, such as the course. A user never has to go
  looking for the thing a notification mentions.

**The first events**

- **Course registration.** A learner registered individually for a course
  (`LearnerCourseRegistration`) gets a notification. This is the point where `course.registered`
  fires today.
- **Course completion.** A learner who completes a course gets a notification. This is the branch
  in `course_finish` that stamps `completed_time` and fires `course.completed`.
- Cohort registration and cohort membership changes raise no notification. They fire no event
  today, and naming those events belongs to the educator interface's spec 7.

**Surfaces**

- The bell and unread badge live in `partials/header_bar.html`, immediately left of the avatar
  menu. That template is shared by the learner dashboard, the course player and the educator
  interface, so every signed-in user sees the bell, learners and educators alike.
- The badge shows the unread count and caps at "99+". The bell's accessible name reads the count
  ("Notifications, 3 unread"), and the count sits in a `role="status"` live region so a polled
  change is announced politely.
- The bell opens a panel of the most recent notifications (about eight), each with a category
  icon, one line of text, a relative time and an unread marker. The panel footer has "Mark all as
  read" and "See all". At 375px the panel is a full-width sheet.
- The notification centre is a full page reached from "See all". It has All and Unread filters,
  groups notifications by day (Today, Yesterday, then dates), and lets the user mark one or all
  read.
- HTMX polling is the only transport. The badge polls only while the tab is visible. Nothing
  depends on Django Channels, ASGI or a channel layer.
- Unread state is shown by icon, text and weight together, never by colour alone. Every control
  is keyboard-reachable with a visible focus ring. Every screen meets WCAG 2.2 AA and works at
  375px.
- The screens follow the Claude Design mockups for the bell, panel and notification centre,
  including the empty, all-read, unread and error states. Colours come from FLS role tokens and
  icons from `c-icon`, so re-themed sites follow.

**Words**

- A notification is not a toast. "Messages" in FLS already means `django.contrib.messages` toasts
  and, from spec 4 of this effort, direct messages. This spec's noun is **notification**.

## Open until the spec

- **Category registry.** Does raising a notification go through `fire_webhook_event`'s event-type
  registry, or does `comms` keep its own category registry that webhooks may also read? Either
  way the answer must hold for the email, messaging and digest specs, which key off the same
  categories. `fire_webhook_event` silently does nothing outside a request, and raising a
  notification must not.
- **What is stored.** Is a notification's text rendered and stored when it is raised, or rendered
  from its category and target each time it is shown? This decides what a notification says
  after a course is renamed or removed.
- **When a notification counts as read.** On opening the panel, on following its link, or only
  on an explicit mark-as-read.
- **Retention.** Whether old notifications are kept indefinitely, or capped or aged out, and how
  the centre pages a long list.
- **Polling interval** for the badge, within the 30 to 60 seconds the research recommends.

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

## Resources

- `research_prior_notification_ux.md` (this directory): badge and dot patterns, HTMX polling
  intervals and visibility-gated polling, ARIA live regions and keyboard rules for unread
  indicators.
- `spec_dd/1. next/user-communication/research_notification_sources_and_delivery.md`: every
  event hook in FLS today, where `course.registered` and `course.completed` fire, why cohort
  registration never announces, and the delivery and task stack.
- `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md`: the
  shared header bar as the bell's home, the `COURSE_ACCESS_BACKEND` pattern for a swappable
  backend, and the multi-tenant rules for writing rows from background work.
- `spec_dd/1. next/user-communication/research_comms_ux_pitfalls.md`: notification fatigue, the
  "one place to check" principle, and accessibility failures in badges.
- `spec_dd/1. next/user-communication/research_comms_patterns.md` and
  `research_lms_comms_landscape.md`: notification data-model patterns and how other LMSs do it.
- `spec_dd/1. next/user-communication/design_brief.md` (sections 1 and 2) and the Claude Design
  mockups that will land beside it.
- Code this builds on: `partials/header_bar.html`, `freedom_ls/webhooks/events.py`,
  `freedom_ls/learner_progress/signals.py`, `course_finish` in `freedom_ls/learner_interface/views.py`,
  `freedom_ls/course_access/loader.py`.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `ds:app-settings`,
  `fls-dev:app-settings`, `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`,
  `fls-dev:icon-usage`, `fls-dev:testing`, `fls-dev:playwright-tests`.
