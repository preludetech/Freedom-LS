# Notification email, digests and quiet hours

Spec 2 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes. This
spec absorbed spec 7 (email digests and quiet hours).

## What

Email becomes a second way a notification reaches its recipient, next to the in-app notification
centre. Each user picks, per notification category, how that category arrives by email:

- **Immediately**: one email per notification.
- **Daily or weekly digest**: one email per period that gathers everything in the categories set
  to that digest.
- **Off**: no email.

Users can also set **quiet hours**: a window in their own timezone, such as 22:00 to 07:00, during
which no notification email is sent to them. Mail held back by quiet hours goes out when the
window ends.

Users make these choices on a notification preferences page. Each site sets its own defaults, and
every notification email carries a one-click unsubscribe. A new sweep in `fls_run_housekeeping`
sends due digests and releases mail held by quiet hours.

## Why

A notification that lives only in the bell reaches people who are already logged in. The learner
who registered for a course and has not been back, or the one who finished and left, is who email
is for. Email is also where LMSs go wrong most often: "too many emails" is the top complaint in
the landscape research, and an unsubscribe that switches everything off also silences the messages
that matter. Per-event email is the biggest cause of that fatigue. Moodle, Canvas and Blackboard
all offer immediate, daily and weekly, and learners and educators prefer one grouped email to a
stream of single ones. Mail that arrives at 03:00 local time because the server sends in UTC is a
common complaint too.

This spec adds email with all of those controls in place from the first message sent, so no site
starts out sending one email per event and has its defaults changed under it later.

## What is settled

- **Email is a delivery backend on spec 1's notification layer.** Raising a notification stays one
  call. The email leg decides what to do from the recipient's preference for that category. The
  categories are the ones spec 1's registry defines, so a feature that adds a notification
  category gets email preferences for it with no further work.
- **Frequencies per category are immediate, daily, weekly or off.**
- **Preferences, digests and quiet hours apply to email only.** The in-app bell and notification
  centre keep every notification and show it straight away, whatever the user picks for email.
- **Defaults resolve in three layers**: Django settings give the package defaults, a per-site row
  overrides them, and the user's own preference overrides both. The per-site row follows the
  `SiteSignupPolicy` pattern: one site-aware row per site, edited in the Django admin. There is no
  course, cohort or registration level for notification email.
- **The preferences page belongs to the user**, whatever their role. Learners and educators use the
  same page, and it shows each category with its current setting, whether that setting is the
  user's own or the site default, and the user's quiet hours.
- **A notification is never emailed twice**, once immediately and once in a digest.
- **Conversations stay rolled up.** An active conversation never sends one email per message,
  immediately or in a digest; a digest summarises unread conversations rather than listing
  individual messages.
- **Every notification email has a one-click unsubscribe**: a `List-Unsubscribe` header with the
  one-click POST form mail providers require, and a readable link in the footer. Both work without
  logging in and take effect at once. Digest emails carry it too.
- **Account mail is untouched.** allauth's verification, password reset and login code mail is not
  a notification category, is never digested and ignores quiet hours.
- **Quiet hours use the recipient's timezone**, never the server's (`TIME_ZONE` is UTC).
- **Templates extend the themed `base_email.html`** and reuse the branding context the
  email-styling spec built, so notification mail looks like the site's other mail. Each email says
  what happened and links to the page in FLS where the user acts on it. The platform is the record,
  and the email is the pointer to it. There is no reply-by-email, so the email says where to reply.
- **Sending goes through the mail transport `retry-sent-emails` builds.** This spec adds no retry,
  persistence or failure handling of its own. Notification email runs on a worker, so a deployment
  must set `EMAIL_BACKEND` to the queued backend. The spec states that as a deployment requirement,
  in the same terms `retry-sent-emails` uses.
- **The digest and quiet-hours sweep lives in `fls_run_housekeeping`.** FLS has no built-in
  scheduler; the deployment runs that command on a schedule of its own. The spec names the cadence
  it needs in `docs/product/deployment.md` rather than assuming one, the same way
  `retry-sent-emails` states its "at least hourly".
- **Background sends and the sweep pass `site_id` explicitly.** No request is in play and
  `SiteAwareManager` does not filter outside one, so the site's defaults, theme and absolute links
  resolve from the site the notification was raised on. A digest only ever gathers notifications
  from the site it is sent for.
- **The design comes from Claude Design**, registered in `user-communication/design.md`. This
  spec builds the preferences page (the version with four email options and quiet hours), the
  unsubscribe confirmation, the notification email and the digest email to it.

## Open until the spec

- **Time-sensitive categories.** Whether a category can carry a flag, set by the package or a
  site, that keeps it from being turned off, put on a digest or held by quiet hours. Decide it as
  one attribute of the category, not three, and say which of the categories that exist today need
  it.
- **The shipped default for each category.** Research favours daily digests out of the box for
  non-message categories. The spec decides the Django settings default, knowing a site can
  override it.
- **What the footer link and one-click header turn off**: only the category the email was about,
  or all notification email. The pitfalls research counts all-or-nothing opt-out as the main
  failure. If both routes are offered, the spec says which one the header takes, and what a
  digest's unsubscribe turns off when it covers several categories.
- **What an unsubscribe token carries** (user, site, category), how it is signed, and whether it
  expires.
- **What is recorded per notification about email**, so that a notification is never emailed
  twice, and what happens when an emailed notification is updated, for example the rolled-up
  notification spec 4 raises per unread conversation: send nothing more until the user reads it,
  send again, or include it in the next digest.
- **What a digest contains when a user has both unread notifications and unread conversations.**
  For example, one email with a notifications section and a "5 unread messages across 3
  conversations" line, or conversations left to their own immediate or off setting.
- **Where a user's timezone comes from.** The user model has no timezone field today. The spec
  decides whether users set it on the preferences page, whether it is detected from the browser
  and confirmed, and what applies before a user has one (the site's default, or UTC).
- **When the daily and weekly digests go out**: a fixed local hour for every user, a user-chosen
  hour, which weekday for weekly, and how quiet hours interact with the digest's send time.
- **What the sweep does when the deployment's schedule is late or missed**: send the overdue
  digest once on the next run, and never send two for the same period.
- **Whether quiet hours are one window per user or can differ by day** (weekends, for instance).
- **Where the preferences page sits and how users reach it**: from the notification centre, from
  the profile, or from both.
- **What happens when the recipient has no verified email address**: skip silently, record the
  skip against the notification, or show it on the preferences page.

## Out of scope

- Hourly digests or any frequency finer than daily.
- Digests or quiet hours for the in-app notification centre.
- Retry, persistence and failure classification for outgoing mail (`retry-sent-emails`).
- Bounce and complaint feedback from the mail provider, and suppression lists.
- New notification events or categories, including deadline-approaching reminders or any other
  event produced by a periodic scan. Spec 1 and later features add those through spec 1's API.
- Any scheduler inside FLS (Celery beat, `django-q`, APScheduler).
- Notification settings at course, cohort or registration level.
- A screen outside the Django admin for editing site defaults.
- Reply-by-email, SMS and mobile push.

## Resources

- `spec_dd/1. next/user-communication/idea.md`: the source idea.
- `spec_dd/1. next/user-communication/design.md`: the Claude Design design for the preferences page
  (both the Immediately / Off version and the version with four email options and quiet hours), the
  unsubscribe landing page and the notification email. Read it through the Claude Design
  integration, as that file says.
- `spec_dd/1. next/user-communication/design_brief.md` (sections 3 and 4): the brief it was drawn from.
- `spec_dd/1. next/user-communication-1-notifications-core/`: the notification layer, the category
  registry and the notification centre this spec plugs into.
- `spec_dd/1. next/retry-sent-emails/1. spec.md`: the `OutboundEmail` transport under every email
  this spec sends, the wording for the queued-backend deployment requirement, and the housekeeping
  sweeps and cadence wording to follow.
- `spec_dd/3. done/2026-06-15_00:19_email-styling/`: themed `base_email.html` and the branding
  context in `AccountAdapter`.
- `SiteSignupPolicy` in `freedom_ls/accounts/models.py`: the pattern for the per-site defaults row.
- `docs/product/deployment.md`: where the housekeeping cadence is documented.
- Shared research in `spec_dd/1. next/user-communication/`:
  - `research_notification_sources_and_delivery.md`: the mail pipeline, the tasks backend and
    worker in production, what the email-styling work already provides, and why
    `fls_run_housekeeping` is the place for a digest sweep.
  - `research_comms_ux_pitfalls.md`: notification fatigue, one-click unsubscribe requirements,
    email as a pointer and not the record, quiet-leaning defaults, per-category frequencies, quiet
    hours and timezone-aware delivery.
  - `research_lms_comms_landscape.md`: how Canvas, Moodle and Open edX shape per-user email
    preferences, immediate, daily and weekly email, and where they fail.
  - `research_comms_patterns.md`: notification and preference data-model patterns, the common
    digest batching pattern and a `digest_frequency` preference shape.
- Skills: `domain-glossary`, `notifications`, `brand-guidelines`, `fls-dev:multi-tenant`,
  `ds:app-settings`, `fls-dev:app-settings`, `fls-dev:template`, `ds:htmx`,
  `fls-dev:admin-interface`, `fls-dev:testing`.
