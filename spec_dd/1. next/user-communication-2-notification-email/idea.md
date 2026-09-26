# Notification email

Spec 2 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Email becomes a second way a notification reaches its recipient, next to the in-app notification
centre. Each user picks, per notification category, whether that category also arrives by email
straight away or not at all. They make that choice on a notification preferences page. Each site
sets its own defaults, and every notification email carries a one-click unsubscribe.

## Why

A notification that lives only in the bell reaches people who are already logged in. The learner
who registered for a course and has not been back, or the one who finished and left, is who email
is for. Email is also where LMSs go wrong most often: "too many emails" is the top complaint in
the landscape research, and an unsubscribe that switches everything off also silences the messages
that matter. This spec adds email with the controls in place from the first message sent.

## What is settled

- **Email is a delivery backend on spec 1's notification layer.** Raising a notification stays one
  call. The email leg decides whether to send from the recipient's preference for that category, and
  it sends one email per notification, never one per underlying event. The categories are the ones
  spec 1's registry defines, so a feature that adds a notification category gets email preferences
  for it with no further work.
- **Two choices per category: immediate or off.** Daily and weekly digests and quiet hours belong
  to spec 7, and the preference model must be able to take them later without a rewrite.
- **Preferences apply to email only.** The in-app centre keeps every notification, whatever the
  user picks for email.
- **Defaults resolve in three layers**: Django settings give the package defaults, a per-site row
  overrides them, and the user's own preference overrides both. The per-site row follows the
  `SiteSignupPolicy` pattern: one site-aware row per site, edited in the Django admin. There is no
  course, cohort or registration level for notification email.
- **The preferences page belongs to the user**, whatever their role. Learners and educators use the
  same page, and it shows each category with its current setting, whether that setting is the
  user's own or the site default.
- **Every notification email has a one-click unsubscribe**: a `List-Unsubscribe` header with the
  one-click POST form mail providers require, and a readable link in the footer. Both work without
  logging in and take effect at once. Account mail from allauth (verification, password reset,
  login code) is not a notification category and is untouched.
- **Templates extend the themed `base_email.html`** and reuse the branding context the
  email-styling spec built, so notification mail looks like the site's other mail. Each email says
  what happened and links to the page in FLS where the user acts on it. The platform is the record,
  and the email is the pointer to it. There is no reply-by-email, so the email says where to reply.
- **Sending goes through the mail transport `retry-sent-emails` builds.** This spec adds no retry,
  persistence or failure handling of its own. Notification email runs on a worker, so a deployment
  must set `EMAIL_BACKEND` to the queued backend. The spec states that as a deployment requirement,
  in the same terms `retry-sent-emails` uses.
- **Background sends pass `site_id` explicitly.** No request is in play, so the site's defaults,
  theme and absolute links resolve from the site the notification was raised on.
- **Mockups come from Claude Design** via `design_brief.md`. This spec builds the preferences
  page and the unsubscribe confirmation to them.

## Open until the spec

- Whether the footer link and the one-click header turn off only the category the email was about,
  or all notification email. The pitfalls research counts all-or-nothing opt-out as the main
  failure. If both routes are offered, the spec says which one the header takes.
- Whether a site or the package can mark a category as always emailed, so users cannot turn it off,
  and if so which of today's categories qualify.
- What an unsubscribe token carries (user, site, category), how it is signed, and whether it
  expires.
- Where the preferences page sits and how users reach it: from the notification centre, from the
  profile, or from both.
- What happens when the recipient has no verified email address: skip silently, record the skip
  against the notification, or show it on the preferences page.
- What happens when a notification that has already been emailed is updated, for example the
  rolled-up notification spec 4 raises per unread conversation: send nothing more until the user
  reads it, or send again.

## Out of scope

- Digests, digest frequencies and quiet hours (spec 7).
- Retry, persistence and failure classification for outgoing mail (`retry-sent-emails`).
- Bounce and complaint feedback from the mail provider, and suppression lists.
- New notification events or categories. Spec 1 and later features add those.
- Notification settings at course, cohort or registration level.
- A screen outside the Django admin for editing site defaults.
- Reply-by-email, SMS and mobile push.

## Resources

- `spec_dd/1. next/user-communication/idea.md`: the source idea.
- `spec_dd/1. next/user-communication/design_brief.md` and the Claude Design mockups that will land
  beside it: the preferences page and its empty and error states.
- `spec_dd/1. next/user-communication-1-notifications-core/`: the notification layer, the category
  registry and the notification centre this spec plugs into.
- `spec_dd/1. next/retry-sent-emails/1. spec.md`: the `OutboundEmail` transport under every email
  this spec sends, and the wording for the queued-backend deployment requirement.
- `spec_dd/3. done/2026-06-15_00:19_email-styling/`: themed `base_email.html` and the branding
  context in `AccountAdapter`.
- `SiteSignupPolicy` in `freedom_ls/accounts/models.py`: the pattern for the per-site defaults row.
- Shared research in `spec_dd/1. next/user-communication/`:
  - `research_notification_sources_and_delivery.md`: the mail pipeline, the tasks backend in
    production and what the email-styling work already provides.
  - `research_comms_ux_pitfalls.md`: notification fatigue, one-click unsubscribe requirements and
    email as a pointer, not the record.
  - `research_lms_comms_landscape.md`: how Canvas, Moodle and Open edX shape per-user email
    preferences and where they fail.
  - `research_comms_patterns.md`: notification and preference data-model patterns.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:multi-tenant`, `ds:app-settings`,
  `fls-dev:app-settings`, `fls-dev:template`, `ds:htmx`, `fls-dev:admin-interface`,
  `fls-dev:testing`.
