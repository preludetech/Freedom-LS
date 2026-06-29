# Notify Interested Students on Course Launch

## Summary

When an educator flips a course's `visibility` from **coming soon** to **published**, the
students who **expressed interest** in that course (the lightweight waitlist) should be
**notified that it has launched** and is now available to enrol/apply for.

This is the deferred follow-up to the **Coming Soon & Hidden Courses** feature. That spec
(`spec_dd/2. in progress/courses_coming_soon/1. spec.md`) deliberately ships
**interest-recording only** in v1: it records `CourseInterest` rows but sends nothing on
launch, because FLS had no notification system at the time. The v1 model deliberately omits
any unused notification plumbing — so **this feature owns the `notified_at` stamp**: it adds a
nullable `CourseInterest.notified_at = models.DateTimeField(null=True, blank=True)` field via
its own migration, used for send-once idempotency (see Behaviour below).

## Origin / why this matters

- A waitlist that never tells anyone "it's ready" is a dead-end: students who raised their
  hand have to remember to come back and check. The demand signal is captured but never
  closed back to the learner.
- The courses_coming_soon spec currently has to tell educators "students will **not** be
  automatically notified" when they publish — this feature flips that into "X interested
  students will be notified".
- Most of the data model already exists: the interest records and the unique `(user, course)`
  constraint. This feature adds the one missing piece — the `notified_at` stamp (a new field +
  migration) — plus the delivery wiring.

## Dependency: a notification delivery mechanism

This feature **consumes** a notification system; it does not build one. It depends on:

- The general in-app notification system drafted in
  `spec_dd/0. drafts/simple_notifications/` (notification bell, types, statuses, per-type
  templates). A **"course launched"** (or "new course available") notification type is the
  natural fit — it would link to the course detail page.
- Optionally email delivery later (FLS email/template plumbing exists for other flows).

The notification infrastructure should be specced/built first (or alongside); this idea is
the first concrete *consumer* of it and a good driver for its requirements.

## Behaviour

- **Trigger:** a `Course` transitions `coming_soon → published` (detect on save / status
  change; the exact hook — model signal, service method on the educator "publish" action,
  or a management action — is a spec-level decision).
- **Audience:** every `CourseInterest` for that course **with `notified_at IS NULL`**.
  Students who left the waitlist (record deleted) are not in the set, so they aren't
  notified — correct by construction.
- **Action:** create a "course launched" notification per interested user (via the
  notifications app), linking to the course detail page, and **stamp `notified_at`** so a
  later re-publish (or a re-run) never double-notifies.
- **Idempotency:** only ever notify where `notified_at IS NULL`; set it atomically as part
  of sending. A course flipped coming_soon → published → coming_soon → published again
  should not re-notify students already notified (open question below).

## Educator UX

- On the publish action, replace the current v1 warning ("students will not be notified")
  with a confirmation: **"X interested students will be notified that this course has
  launched."**
- Optionally surface, in the educator course-management view, how many interested students
  have been notified vs. still pending.

## Edge cases / open questions

- **Re-publish:** if a course goes coming_soon → published → coming_soon → published, should
  newly-interested-during-the-second-coming-soon students be notified on the second launch
  while previously-notified ones are skipped? (`notified_at` per-row handles "notify once
  ever"; a "notify per launch" policy would need a different model — likely out of scope.)
- **Channel choice:** in-app only for v1, or in-app + email? In-app (via simple_notifications)
  is the lower-dependency baseline.
- **Delivery timing:** synchronous on publish vs. queued (a coming-soon course could have
  many interested students). FLS task-backend availability affects this.
- **Site isolation:** `CourseInterest` is site-aware; notifications must respect the same
  site scoping.
- **Unsubscribe/consent:** if email is used, respect any consent/unsubscribe rules (links
  to the registration/consent and any future communication-preference work).

## Out of scope

- Building the general notification system itself (see `simple_notifications` draft).
- **Auto-enrolling** interested students on launch (a separate deferred item from the
  courses_coming_soon spec — notification only here).
- Digests, batching policy, or per-user notification frequency controls.
- Notifications for any other lifecycle event (deadlines, etc.) — those are separate
  notification *types* owned by their own features.

## References

- Parent spec: `spec_dd/2. in progress/courses_coming_soon/1. spec.md` (§7 express interest,
  §10 launch transition, §2 out-of-scope notification dependency).
- Infrastructure dependency: `spec_dd/0. drafts/simple_notifications/0. idea.md`.
