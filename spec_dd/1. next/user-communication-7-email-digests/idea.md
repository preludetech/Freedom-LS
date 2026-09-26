# Notification email digests and quiet hours

Spec 7 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Two new ways to receive notification email, on top of the immediate-or-off choice spec 2 ships:

- **Daily and weekly digests.** A user can choose daily or weekly for a notification category.
  Instead of one email per notification, they get one email per period that gathers everything
  in the categories they set to digest.
- **Quiet hours.** A user can set a window in their own timezone, such as 22:00 to 07:00, during
  which no notification email is sent to them. Mail held back by quiet hours goes out when the
  window ends.

A new sweep in `fls_run_housekeeping` sends due digests and releases mail held by quiet hours. The
deployment documentation states the cadence a deployment has to schedule that command at for
digests and quiet hours to work as promised.

## Why

Per-event email is the biggest cause of notification fatigue and mass unsubscribes in LMS
platforms. Moodle, Canvas and Blackboard all offer immediate, daily and weekly, and learners and
educators prefer one grouped email to a stream of single ones. Mail that arrives at 03:00 local
time because the server sends in UTC is a common complaint too. Spec 2 stops the worst of this
(immediate or off, with messages rolled up per conversation). This spec gives users the quieter
options.

## What is settled

- **Frequencies per category are immediate, daily, weekly or off.** This spec adds daily and
  weekly to the choices spec 2 offers on the user preferences page, and to the per-site defaults
  row. A setting in Django settings gives the default, the per-site row overrides it, and the
  user's own preference overrides both. There is no course or registration level.
- **Digests are email only.** The in-app bell and notification centre are unchanged: every
  notification still appears there straight away, whatever the email frequency.
- **Quiet hours apply only to notification email.** They do not hide anything in-app, and they do
  not touch allauth's transactional mail (verification, password reset, login codes).
- **Quiet hours use the recipient's timezone**, never the server's (`TIME_ZONE` is UTC).
- **The sweep lives in `fls_run_housekeeping`.** FLS has no built-in scheduler; the deployment
  runs that command on a schedule of its own. This spec names the cadence it needs rather than
  assuming one, the same way `retry-sent-emails` states its "at least hourly".
- **The sweep passes `site_id` explicitly** for every user and notification it handles, because
  `SiteAwareManager` does not filter outside a request. A digest only ever gathers notifications
  from the site it is sent for.
- **Digest mail uses the same path as spec 2's notification email**: queued through the
  `retry-sent-emails` transport, rendered on the themed `base_email.html`, carrying spec 2's
  one-click unsubscribe. A notification is never emailed twice, once immediately and once in a
  digest.
- **Conversations stay rolled up.** A digest never lists individual messages from an active
  conversation; it summarises them, the same way spec 2's immediate email does.

## Open until the spec

- **What a digest contains when a user has both unread notifications and unread
  conversations.** For example, one email with a notifications section and a "5 unread messages
  across 3 conversations" line, or conversations left to their own immediate or off setting.
  The effort assigns this unknown to this spec.
- **Where a user's timezone comes from.** The user model has no timezone field today. The spec
  decides whether users set it on the preferences page, whether it is detected from the browser
  and confirmed, and what applies before a user has one (the site's default, or UTC).
- **Which categories may be put on a digest or held by quiet hours.** Some mail may be too
  time-sensitive to wait. The spec decides whether categories carry a flag that forbids digest or
  bypasses quiet hours, and which of the categories that exist by then need it.
- **Whether the shipped default for non-message categories moves from immediate to daily.**
  Research favours daily digests out of the box. The spec decides the Django settings default,
  knowing a site can override it.
- **When the daily and weekly digests go out**: a fixed local hour for every user, a user-chosen
  hour, which weekday for weekly, and how quiet hours interact with the digest's send time.
- **What the sweep does when the deployment's schedule is late or missed**: send the overdue
  digest once on the next run, and never send two for the same period.
- **Whether quiet hours are one window per user or can differ by day** (weekends, for instance).

## Out of scope

- Hourly digests or any frequency finer than daily.
- Digests or quiet hours for the in-app notification centre.
- An educator or site-admin screen for editing site defaults; the per-site row is edited in the
  Django admin.
- Deadline-approaching reminders or any other new event produced by a periodic scan. Events come
  from features that raise them through spec 1's API.
- Any scheduler inside FLS (Celery beat, `django-q`, APScheduler).

## Resources

- `spec_dd/1. next/user-communication-2-notification-email/`: the preferences page, per-site
  defaults row, unsubscribe and notification email templates this spec extends.
- `spec_dd/1. next/user-communication-1-notifications-core/`: the notification model and
  category registry the digest reads.
- `spec_dd/1. next/retry-sent-emails/1. spec.md`: the mail transport, and the housekeeping
  sweeps and cadence wording to follow.
- `spec_dd/1. next/user-communication/idea.md`: the source idea.
- `research_notification_sources_and_delivery.md` (parent): the delivery stack, the tasks
  backend and worker in production, and why `fls_run_housekeeping` is the place for a digest
  sweep.
- `research_comms_ux_pitfalls.md` (parent): quiet-leaning defaults, per-category frequencies,
  quiet hours and timezone-aware delivery.
- `research_lms_comms_landscape.md` (parent): how Moodle, Canvas and others offer immediate,
  daily and weekly email.
- `research_comms_patterns.md` (parent): the common digest batching pattern and a
  `digest_frequency` preference shape.
- `docs/product/deployment.md`: where the housekeeping cadence is documented.
- Skills: `domain-glossary`, `brand-guidelines` (digest copy and email), `fls-dev:multi-tenant`,
  `ds:app-settings`, `fls-dev:app-settings`, `fls-dev:template`, `fls-dev:testing`.
