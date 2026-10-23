# Deadline reminders

Spec 5 of 7 in the Deadlines effort. Read the "Deadlines" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A sweep in `deployment/housekeeping.py` that watches effective deadlines and tells people about
them. It raises in-app notifications to learners as a deadline approaches, falls due today and
passes. It raises one rolled-up notification to educators when learners go overdue, if the
deadline policy's "notify educators" consequence is on. It fires a `deadline.missed` webhook for
each missed deadline, and fires the webhook for a pause that ends on its planned resume date.

This spec builds on spec 3, which gives it the effective-date resolver (spec 1), the policy
(spec 2) and the pause and extension records.

## Why

A deadline nobody is reminded of is a trap. The research found reminders are the norm in
comparable systems, and also where they fail: one notification per offset, reminders that
silently stop for soft or extended deadlines (Docebo), no reminder at all (Canvas), and learners
who mute a bell that fires too often. FLS has no scheduler of its own, and
`user-communication-7-email-digests` explicitly leaves deadline reminders to the deadlines
effort, so this spec owns the scan, the categories and the answers to the `notifications` skill.
The sweep is also the only place a time-driven webhook can come from, since nothing fires at the
instant a date passes.

## What is settled

- **The sweep lives in `deployment/housekeeping.py`.** It is a function called from
  `run_housekeeping_sweeps()` with its own failure handling beside the other sweeps. The
  deployment supplies the cadence. It is idempotent and safe to run late, twice or not at all.
- **It iterates all sites.** There is no request, so it passes `site_id` explicitly into every
  `raise_notification` call and task argument, uses `_base_manager` or explicit filters, and
  passes `site=` to `fire_webhook_event`. The work is split into small tasks, because a task over
  `WORKER_MAX_TASK_SECONDS` gets the worker killed.
- **Reminders anchor on the effective deadline** that spec 1's resolver returns, so an extension
  or a pause moves them. Nothing about a soft deadline, an extension or a grace window silently
  switches reminders off.
- **Learner categories: approaching, due today, overdue.** Each is sent once per learner and
  effective deadline. A reminder is raised only for an incomplete collection item, or for a course
  whose course progress record is not complete. A completed item never reminds.
- **A paused learner gets no reminder.** Pause is evaluated when read, so the sweep skips any
  registration paused at the moment it runs.
- **Educator overdue notification.** When the resolved policy's "notify educators" consequence is
  on, educators are told that learners are overdue. The category is a rollup, so a busy week of
  many learners going overdue does not fill the bell.
- **Webhooks.** `deadline.missed` is added to `FLS_WEBHOOK_EVENT_TYPES` with a sample payload,
  using the payload convention (`user_id`, `user_email`, `organisation_id`, `learner_id`,
  `course_id`, `course_title`). It fires once per missed deadline. The sweep also fires spec 3's
  resume webhook when a pause ends on its planned resume date, because nothing else notices the
  moment.
- **In-app until email exists.** Delivery is the bell. When `user-communication-2-notification-email`
  lands the same categories can be emailed; this spec builds no channel and no digest.
- **The five questions for the new categories** (the `notifications` skill's checklist):
  1. Actor: the system, through the sweep. The recipient is never the actor.
  2. Without it the learner learns of the date only by opening the course or the dashboard, and
     an educator only by opening the cohort.
  3. The learner opens the course (the existing `course_home_url` builder). The educator opens the
     cohort's Needs attention list, which spec 7 builds.
  4. At most once per learner, category and effective deadline. The educator category rolls up.
  5. In-app is enough now. Learner reminders are time-sensitive and are the candidates for
     always-emailed categories that `user-communication-2` and `-7` leave open; this spec settles
     nothing there.
- **A notification and a webhook are separate.** A learner pausing themselves is not notified, but
  the webhook still fires, as spec 3 and 4 settle.
- **The default policy sends no educator notification.** It is mark overdue only, so nothing reaches
  educators until an organisation turns the consequence on.

## Open until the spec

- **Reminder offsets.** Fixed defaults in the policy, or an editable rule list. The research
  favours one rule with several offsets over one notification per offset, with offsets that are
  configurable and not a hard-coded ladder.
- **The sent record** that keeps each reminder and each webhook to once, and what re-arms it when an
  extension moves the effective date.
- **The educator rollup.** Per cohort and course, per day or while unread, and which educators
  receive it (the `educators_of` resolution or something narrower).
- **How several deadlines falling due together read** to a learner: one notification or one each.
- **How the sweep stays cheap** at a realistic number of learners, and whether the layering check
  allows `deployment` to import `learner_management` and `comms`. Only code reading answers these.

## Out of scope

- Digests, quiet hours and email delivery (`user-communication-2-notification-email`,
  `user-communication-7-email-digests`).
- Line-manager escalation, scheduled or emailed reports, SMS and push channels.
- Educator-interface lists of overdue learners (spec 7).
- Webhooks for pause, resume and extension themselves, which fire from spec 3's actions.
- Dates, policy, extensions and pause (specs 1, 2 and 3), and the learner's own pause (spec 4).
- Any scheduler inside FLS.

## Resources

- `spec_dd/1. next/deadlines/research_deadline_integration_points.md`: sections 1 (sweeps, `site_id`, lateness),
  2 (notifications) and 7 (webhooks).
- `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`: section (e), how SuccessFactors, Docebo and
  Moodle remind.
- `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`: section (e) and implications 9 to 11.
- `spec_dd/1. next/user-communication-7-email-digests/idea.md`: the exclusion that leaves this scan to the
  deadlines effort.
- Skills: `notifications`, `domain-glossary`, `fls-dev:multi-tenant`, `fls-dev:testing`.
