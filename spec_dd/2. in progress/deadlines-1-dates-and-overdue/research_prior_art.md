# Research: prior art for due dates, course time limit and overdue

Scope: what was tried before, here and elsewhere, and what bears on spec 1. Constraints from done
specs are in `spec_dd/1. next/deadlines/research_current_deadlines.md` section 3 (per-organisation
deadlines, inactive cohort question, `DEADLINES_ACTIVE`); not repeated. Section 5 there also holds
corporate-readiness item 13.

## 1. Here

### 1.1 `2026-02-19_19:25_deadlines` (the old implementation)

Decided (`1. spec.md`):
- Three models: `CohortDeadline`, `StudentDeadline`, `StudentCohortDeadlineOverride`. Each pointed at
  its target by `ContentType` + `object_id` (generic FK, null = whole course) and carried a
  `deadline` datetime plus `is_hard_deadline`. All fixed datetimes; no offsets.
- Resolution: item beats course within a registration; an override beats the cohort deadline for
  that learner; individual registration deadlines coexist with cohort ones; where several compete,
  show all and the most permissive (latest) governs. Inactive registrations ignored.
- Consequence: hard = lock incomplete items after expiry (completed stay viewable); soft = display only.
  A `CoursePart` deadline was treated as applying to the last item in the part.
- Admin only, inlines on the registrations, "a dedicated UI can be built later".

QA (`qa_report.md`, 2026-02-19): 13 of 15 passed, "no bugs found", but the pass was thin:
- 4a and 4b only "partial": the override and item-beats-course rules could not be shown on an
  incomplete item, because every candidate item was either completed or had its own item deadline.
  Test data, not logic, limited the check. Lesson: seed a case per layer with an incomplete item and no
  competing layer.
- 2d (CoursePart deadline) never run; the test course had no parts.
- **The TOC showed the original cohort date, not the overridden one**, so an extended learner saw the
  wrong date. Recommended then, still true now: always display the effective date and say which layer
  supplied it. The old TOC tooltip did name the source ("Cohort X", "Individual registration"), which
  learners found helpful; keep that.
- Admin `content_type` dropdown listed every content type in the system. The new design avoids a
  generic FK, so this goes away; if any choice field remains, restrict it.

### 1.2 `2026-02-21_16:30_deadlines_deactivate`

`DEADLINES_ACTIVE` was added within two days of the feature because deadline queries on every course
page cost too much for deployments that do not use deadlines. Regret signal: the first design had no
cheap "off" and queried four tables per page (`get_course_deadlines`). Lessons for spec 1:
- The resolver should batch per course (one set of queries for the whole TOC), not per item.
- The new design removes the flag (idea.md). Without it, a course with no authored deadlines and no
  override rows must cost near nothing: prefer reading the placement's frontmatter-derived field first
  and only touching override tables when a row can exist.
- The old spec said "do not set the default in settings; mock in tests". Tests that need the flag go
  with it.

### 1.3 `better-course-progress-tracking` (done 2026-08-28)

- Moved deadlines to the `Learner` grain (plan Task 20): seven `learner__user=` filters in
  `deadline_utils.py` switched; success criterion 9 (organisations are separate) verified in 3b QA.
  Seam QA S10.5 showed the adversarial case works: deactivating the cohort registration made the
  learner resolve to the individual grant and the cohort's deadlines vanished.
- **Grain mismatch (S10.3), recorded not fixed**: `CohortDeadline` stored the form's pk while progress is
  keyed to the `ContentCollectionItem`. One deadline badge appeared on both placements of one form, each
  with independent progress. Plan line ~1065 also warned that `_fetch_deadline_data` filtered
  `object_id__in` on *content* ids and handing it collection-item ids would have dropped every badge.
  This is the direct reason the new idea attaches to the placement. New risk it creates: content
  re-import that moves a child creates a new `ContentCollectionItem` (open question in idea.md), so
  authored frontmatter deadlines must be re-derived on sync and stored override rows keyed to a
  placement can be orphaned. Decide whether overrides key to placement or to (course, child + position)
  and what happens to them on a move.
- **QA left a hard deadline behind (todo.md line 76)**: a `LearnerDeadline` set in S10.6 locked a fixture
  learner out of a quiz whenever she resolved to that registration, and had to be deleted by hand.
  Deadline data persists across QA runs and silently changes unrelated tests. Spec 1 should have its seed
  and QA commands create, label and clean their rows (the old `qa_create_*deadline*` commands are being
  removed; whatever replaces them should be idempotent and show what they created).
- S10.6 also noted: a learner locked on one organisation's record but not the other's gets no on-screen
  reason beyond the deadline badge. Overdue display should say which registration it comes from when
  more than one exists for the course.
- Upgrade note: a hard-deadline-locked item reads "blocked" rather than "in progress" in progress
  states. Removing locking changes this; the TOC state mapping needs checking (see
  `research_deadline_integration_points.md`).

### 1.4 `user-communication-3-messaging-policy` (layered resolver)

Closest in-repo template for the "one resolver over layers" in idea.md.
- `research_layered_rule_shape.md` and `1. spec.md` (line ~193): an ordered module-level list of layer
  functions, most specific first; first non-`inherit` value wins; returns `ResolvedFlag(value, source)`
  so the winning layer is named; "unset needs no label"; adding a layer is one line, no migration.
  Layers that depend only on one row are resolved in Python and passed in; SQL uses `Coalesce(NullIf(...))`.
- Prior art it cites (Moodle capability overrides) says every layered system needs a way to explain
  the result. Matches the sentiment ask for "follows the default, or visibly flags that it does not".
- Differences to respect: messaging layers are "most specific wins"; deadlines also have "most
  permissive wins" within one layer and a fixed/relative split. Resolve within-layer first, then
  across layers. Pause and shifts (specs 3, 4) must be added as one more step, not a second resolver, so
  keep the return type extensible (value + source + anything the explanation needs).
- QA: only one bug, an admin widget styling one (B1, fixed). Admin override UIs on mobile needed
  explicit widget work; budget for it.

### 1.5 Things neither the old spec nor QA covered (the "what it missed")

- **Time zones and midnight**: the old spec never mentions them. `DateTimeField` only, no stated zone,
  no end-of-day rule. This is why idea.md decides "end of day in the site's zone, always name the zone".
- **Overrides were separate rows, not annotated copies**: no actor, no reason, no timestamp. A learner
  override is a deadline row that ignores later cohort edits, with nothing marking that it has drifted.
  Open question in idea.md; the old model offers nothing to reuse except the "most specific beats
  general" ordering.
- **Hard/soft was a per-row flag**, so overdue meaning was baked into each date. Moving consequence to a
  policy (spec 2) removes it. Dropping it is a deliberate narrowing; do not carry `is_hard_deadline`.
- **Course-level date not in the "all items" resolution as a bound**: old rule "all incomplete items
  lock" at course expiry. The new time limit end is similar but offset-based; define whether an item due
  date later than the time limit end is allowed, shown, or flagged at load time.
- **`CoursePart` deadline = last item**: awkward and untested (2d). The new design has no part-level
  deadline in scope; do not reintroduce it implicitly via the course child list.
- **Uniqueness of course-level rows** enforced "at application level" because of nullable columns
  (spec 1.1). With a dedicated course-level field or row type, a real constraint is possible.
- Corporate-readiness item 13 asks that relative dates "agree with rules (12) and recertification
  (11)". A new `CourseProgress` per cycle (item 11) gives a new `created_at` and so a new start
  automatically; that is a point in favour of anchoring on `CourseProgress.created_at`. See
  research_current_deadlines.md section 5 for the rest.

## 2. Elsewhere

- **Open edX, self-paced courses**: fixed dates do not suit rolling enrolment, so Personalized Learner
  Schedules (PLS) give each learner suggested due dates relative to their enrolment (or course start if
  later), spread evenly over graded sections by default, with author overrides per subsection; learners
  can shift their dates later. It is behind waffle flags and requires graded subsections and a
  self-paced course; adoption is partial and docs are inconsistent about defaults. A community "course
  shifts" proposal exists to move all dates for a group; it was described as raw and not confirmed
  merged. Takeaways: relative dates started as suggestions, not enforced; the anchor is "later of start
  and enrolment" (FLS picks registration only, with `created_at` that is the same thing for late
  joiners); shifts are a separate concern added later (specs 3 and 4). Even-spread defaults were useful
  but are not in scope here.
- **Moodle, Course relative dates**: experimental, site setting under Development/Experimental
  settings. Mode is chosen at course creation and cannot be changed afterwards, or enabled on existing
  courses. Covers only assignment dates and weekly section dates; not Restrict access or Quiz. Takeaway:
  a mode flag per course, applied late, covering only some activity types, left it half-useful and
  experimental for years. Hence idea.md's choice of per-item fixed or relative with no course mode,
  and the need for the resolver to work for every viewable item type (topic and form) from day one.
- Landscape detail (Moodle, TalentLMS, LearnDash, Open edX attach and override dates) is in
  `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`; not repeated.

## 3. Lessons that bear on the design

1. Attach to the placement; the old content-pk keying caused a documented mismatch.
2. Show the effective date and its source, never the base date when an override exists.
3. One batched resolver per course; the old per-page cost produced a feature flag within two days.
4. Overrides need actor, reason and a drift marker; the old model had none.
5. Make seed and QA data explicit and cleanable; stale deadlines poisoned later QA.
6. Seed QA so every layer is tested on an incomplete item with no competing layer.
7. Put time zone and end-of-day in the first spec; the old one never decided them.
8. Mirror the messaging-policy resolver shape (ordered layers, value plus source) so specs 3 and 4 add
   layers rather than a second resolver.
9. No per-course mode switch (Moodle) and no consequence baked into the date (old hard/soft flag).

## References

- Open edX docs, Course pacing: https://docs.openedx.org/en/open-release-sumac.master/educators/references/setting_course_pacing.html
- Open edX docs, Schedule and Details (PLS): https://docs.openedx.org/en/ulmo/educators/references/course_development/about_page.html
- Open edX forum, Personalized Course Content Schedules: https://discuss.openedx.org/t/request-for-feedback-personalized-course-content-schedules/1304
- Open edX forum, Course start and end relative due dates: https://discuss.openedx.org/t/course-start-and-end-relative-due-dates/16718
- Open edX wiki, Course shifts proposal: https://openedx.atlassian.net/wiki/spaces/AC/pages/415662305/Course+shifts+feature+proposal+and+discussion
- Moodle docs, Course relative dates: https://docs.moodle.org/501/en/Course_relative_dates

status: ok
