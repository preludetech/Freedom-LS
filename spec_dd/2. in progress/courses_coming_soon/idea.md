# Coming Soon & Hidden Courses

## Summary

Give every course a **visibility status** so the platform can show courses that
aren't yet open for enrolment ("coming soon") and keep some courses out of student
discovery entirely ("hidden"). Today every course is always discoverable and
enrollable — there is no status field at all.

For "coming soon" courses, students can't register but can **express interest**
(a lightweight waitlist), giving educators a demand signal for what to launch next.

## Course visibility states

A single `status` field on `Course` (one `TextChoices` enum, mirroring the existing
`DifficultyLevel` pattern). Three states for now:

- **Published** — current behaviour: discoverable everywhere, enrollable. This is the
  **default**, so existing courses stay visible after migration.
- **Coming soon** — appears everywhere a course normally appears (listings, dashboard,
  detail page), clearly badged. Students can't register; they can express interest.
- **Hidden** — not discoverable by students: excluded from all browse/discovery
  surfaces, and the detail page returns 404 for students who aren't registered.

A single enum (rather than separate boolean flags) keeps states mutually exclusive,
makes student filtering a one-line change, and is trivially extensible. A future
`draft` state (educator-only, invisible even by direct link) can be added as a
one-line enum addition if needed — out of scope for now.

### Visibility rules

- **Students** see Published + Coming soon in browse/discovery surfaces. Hidden courses
  are filtered out at the single choke-point (`get_all_courses()` and the dashboard
  querysets in `student_interface`).
- **Educators / admins** always see all courses regardless of status, with the status
  shown as a badge in the course management list. (Educator queries are unchanged.)
- **Hidden + already-registered students keep their access.** Hidden only removes the
  course from discovery — students mid-course aren't disrupted; their dashboard and
  direct URL still work. (Unregistered students hitting a hidden detail URL get 404.)

## Express interest (waitlist) for coming-soon courses

- On a coming-soon course, the usual "Enrol & start" CTA is replaced by an
  **"I'm interested"** action (avoids implying a capacity-limited queue). Clicking it
  records the student's interest.
- A new **`CourseInterest`** record captures `user`, `course`, `created_at`, and a
  nullable `notified_at` (unused in v1, but present so launch-notification can be wired
  up later without a migration). Unique on `(user, course)`; created via `get_or_create`
  so repeated clicks are idempotent.
- After expressing interest the CTA visibly changes state (e.g. "Interested" + a quiet
  "remove interest" link) and the user gets inline confirmation. **Students can leave the
  waitlist** — a low-prominence secondary action, not a prominent toggle.
- Coming-soon course cards/rows get distinct status variants (e.g. interested vs.
  not-interested), fitting the existing template-dispatch pattern for card states.

## Launch transition (coming soon → published)

**v1 records interest only.** When an educator flips a course to Published, it simply
becomes enrollable; interested students see it as available on their next visit. There
is **no notification** — FLS has no email/notification system yet, so the UI must not
promise one. The `CourseInterest.notified_at` field is included now so that notify-on-
launch (or auto-enrol) can be added later without model changes. This dependency should
be flagged in the spec.

## Educator visibility of demand

Surface the waitlist as a demand signal: show an **interest count** per coming-soon
course in the educator course-management list, with a drill-down to the list of
interested students. This is what makes the waitlist data actionable (which course to
prioritise launching) rather than data that goes nowhere.

## Things to design against (from UX research)

- No feedback after clicking interest → must visibly change CTA state + confirm.
- Coming-soon cards indistinguishable from enrollable ones → clear "Coming soon" badge,
  no enrol button.
- Courses stuck in "coming soon" forever with a waitlist nobody looks at → educator
  count/drill-down addresses this.
- No way to leave the waitlist → quiet "remove interest" action included.

## Open questions / dependencies

- **Notification system** is a deferred dependency. The data model is built ready for it;
  the spec should note that "notify interested students on launch" is future work
  pending an email/in-app notification system.
- How (if at all) should course content metadata in the content directory set status on
  import? Default to `published` on import to preserve backward compatibility; an explicit
  override mechanism is a spec-level detail.

## Out of scope (for now)

- Email / in-app notifications on launch.
- Auto-enrolling interested students on launch.
- A separate `draft` state (educator-only).
- Capacity-limited waitlists / queue positions / scarcity mechanics.

## Research

See `research_visibility_states.md` (how to model course visibility states; reference
implementations) and `research_waitlist_ux.md` (coming-soon + waitlist UX patterns,
pitfalls, educator view) in this directory.
