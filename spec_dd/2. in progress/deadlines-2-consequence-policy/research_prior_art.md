# Research: prior art for the deadline consequence policy

Scope: what has been tried for a layered policy of mark overdue, close, end access, notify, with a
grace window, here and elsewhere, and what happened. Sentiment and landscape detail already live in
`spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md` (sections d, f) and
`research_deadlines_user_sentiment.md` (section a); only what bears on this spec is repeated.

Method note: I had no shell, so I could not run `git log`. Everything "here" comes from `spec_dd/`
(all folders) and the code at HEAD. No commit was found by name for a consequence-policy attempt;
the files show none was ever built.

## 1. Here

### 1.1 Nothing has built a consequence policy yet

No earlier spec, plan or code carries "grace window", a consequence switch or a policy class for
deadlines. The grep of `freedom_ls/` (non-test) finds no "grace" or "consequence" for deadlines. The
only prior consequence is the old hard/soft flag below, now deleted. This spec is the first attempt.

### 1.2 The old hard/soft lock (`3. done/2026-02-19_19:25_deadlines`)

- Decided: consequence baked into each date row as `is_hard_deadline`. Hard locks incomplete items
  after expiry; completed items stay viewable; soft is display only. A course-level hard deadline
  locks every incomplete item. A `CoursePart` deadline meant "the last item in the part".
- Inactive registrations ignored; several competing deadlines: show all, most permissive governs
  access.
- QA (13 of 15 passed, "no bugs") was thin: 4a/4b (override and item-beats-course) were only partial
  because no incomplete item isolated each layer; 2d (CoursePart) never ran; the TOC showed the
  cohort's original date, not the learner's override.
- What was dropped on purpose by deadlines-1 (`research_prior_art.md` there, 1.5): the per-row flag.
  "Moving consequence to a policy (spec 2) removes it. Dropping it is a deliberate narrowing; do not
  carry `is_hard_deadline`." Also: no part-level deadline; do not reintroduce it.
- Its enforcement had two sources of truth (`research_deadline_integration_points.md` section 4):
  `get_course_index` -> `_apply_deadline_locking` (forces `BLOCKED`, `url=None`) and a second check
  in `view_course_item` using `is_item_locked_by_deadline`. `form_start` and `form_fill_page` were
  covered only through the index status. This is why the idea demands one decision read by both.
- Deliberate exemptions that survive: `course_form_complete` ("a learner is always entitled to the
  score they earned, including after a deadline has closed the quiz itself") and `form_submit_and_exit`
  ("refusing it would strand that attempt incomplete"). The second is directly the open question on
  whether "close" leaves an in-progress attempt finishable: the old code chose "yes, submit is never
  gated", though a started attempt could not be re-entered via `form_fill_page`.

### 1.3 `2026-02-21_16:30_deadlines_deactivate`

`DEADLINES_ACTIVE` was added within two days because per-page deadline queries (four tables) cost too
much for installs not using deadlines. Lesson for enforcement on read: the closed/ended decision runs
on the hot path of every player and TOC request, so it must be a batched, near-free check when no
policy row or date exists. The flag is removed in deadlines-1; the default policy (mark overdue only)
must keep "no rows" cheap.

### 1.4 `better-course-progress-tracking`

- Deadlines moved to the `Learner` grain; separate organisations get separate deadlines.
- S10.5: deactivating the cohort registration made the learner resolve to the individual grant and
  the cohort's deadlines vanished. Adversarial case for "which registration governs": the answer
  moved when a registration flipped.
- S10.6: a hard `LearnerDeadline` left behind in QA locked a fixture learner out of a quiz, and
  nothing on screen said why beyond the badge. Lesson: whatever closes an item must say that it is
  closed and why, next to the date (the idea already asks for this); QA data that closes things must
  be cleaned up.
- Grain mismatch S10.3: deadline keyed to content pk, progress keyed to the placement. Fixed in
  deadlines-1 by keying to `ContentCollectionItem`; the closed decision must key the same way.

### 1.5 `deadlines-1-dates-and-overdue` (done 2026-10-25)

What spec 2 inherits (`freedom_ls/deadlines/resolver.py`, `upgrade_notes.md`, `qa_report.md`):
- **Nothing locks now.** Upgrade note: "Deadlines no longer lock content ... learners see a due date
  and an overdue mark, and that is all." The old lock was removed outright, so spec 2 reintroduces
  closing from scratch rather than reviving it. Note the TOC `BLOCKED` mapping from the old lock is
  gone; "closed" needs its own status or flag.
- The resolver gives `ResolvedDeadline(due_at, source)` per item and for the time limit
  (`CourseDeadlines.items`, `.time_limit`), with `is_overdue(resolved, completed, now)` =
  `due_at is not None and not completed and now > due_at`. Overdue is shown unconditionally. A grace
  window plugs in as `now > due_at + grace`; there is no `grace` in the resolver today. Pause and
  extension (spec 3) are meant to be one more step in this same resolver, not a second one.
- The same layered idea already applies to dates: first layer with a value wins, source named
  (content, cohort registration, learner). The policy resolver should likewise return value plus
  the layer that supplied it, so the learner can be told which rule applies.
- QA: 0 bugs, but notes that an override's "default changed" drift note exists (§6) and that cohort
  override changes were visible in player and dashboard. Overrides move the date, so a grace window
  computed as `due_at + grace` follows the override automatically unless the policy stores a
  fixed close date (see open question on override interaction).
- The old QA lesson stands: seed one incomplete item per layer (for policy: one per layer holding a
  different consequence) so each layer is tested in isolation.

### 1.6 `user-communication-3-messaging-policy` (done 2026-10-10)

The template named by the idea. Reusable and not reusable parts:
- Reusable: swappable class behind a setting (`MESSAGING_POLICY`, `comms/messaging_loader.py` with
  `@functools.cache`, autouse cache-clear fixture, checks E003/E004, string default creates no import
  edge); contract in a core app and default implementation in a separate app; frozen dataclass
  decision whose `__bool__` raises; one table per level; admin-only editing; missing row behaves as
  all-inherit; `LAYER_ORDER` tuple with the settings layer always present and a new layer being one
  tuple entry; `resolve_flag(layers)` plus a SQL twin (`Coalesce(NullIf(...))`); resolved value carries
  its source layer.
- Not reusable as is: `MessagingFlags` is three flags of `inherit/open/closed` with CheckConstraints.
  Deadline settings are a grace duration, a number-like value, and booleans, so each needs its own unset
  marker (the idea says this). The messaging layer order puts learner and registration above cohort
  and organisation, and never includes a course. Messaging sidesteps the "two registrations" problem by
  using "any path that resolves open"; deadlines cannot, since one registration must govern (idea).
  Messaging's per-registration config carries only the one flag a registration can affect; the same
  discipline suggests listing which settings each layer may hold (an open question here).
- What it deferred and why: no educator screen ("admin only"), no "why" screen; reason codes and
  wording were left to the later consumer spec. Same split applies here: spec 6 owns the educator UI
  and spec 5 owns raising notifications.
- Its QA found one bug, an admin widget styling issue; admin work on override UIs needed explicit
  widget budget.
- Deployment lesson: the app is optional only by a system check (E004) telling downstream projects to
  add it to `INSTALLED_APPS`. Deadlines-1 recorded the opposite risk (no check; failure at import).
  A swappable deadline policy with the default in `freedom_ls.deadlines` would need the same E003/E004
  style checks.

### 1.7 `COURSE_ACCESS_BACKEND` (done) as the enforcement seam

From `research_deadline_integration_points.md` section 4: `VisibilityEnforcingBackend` is applied by
the loader so no backend can bypass coming-soon/hidden; it exempts registered users using
`is_registered_for_course_expression`. A deadline wrapper would be a second wrapper of the same
kind. The record states the trade directly: wrapping covers every route that calls `get_access`;
changing `is_registered_for_course` also changes who sees hidden courses. `CourseAccessDecision` has
no "why not" field today, so the learner could not be told access ended unless a field is added
(additive; callers read only four fields).
Also from the same file: flipping `is_active` was rejected by the idea (it would drop the course from
the dashboard, stop `learner_for_course` resolving and fire `course.unregistered`).

### 1.8 Corporate-readiness

`spec_dd/corporate-readiness/` mentions recertification and relative dates (item 13 asks that
relative dates agree with rules and recertification). Not a policy attempt, but it supports ending
access without deactivating the registration, and "new window, progress kept" on restore.

## 2. Elsewhere

### 2.1 Moodle: due date, cut-off date, no grace setting

- Due date flags late; cut-off date closes submission; no cut-off means late work is accepted
  indefinitely; cut-off equal to due date means no late work. There is no separate grace period; the
  common workaround is a cut-off some hours after the due date (often 24h). Source: Kenyon and RWTH
  guides and a search summary of Moodle docs.
- An extension sets both the due date and the cut-off for that learner (HUJI guide). Closer to what
  spec 2 must do: when an override moves the date, a derived close date moves with it.
- MDL-44098: lateness in the grading table was calculated from the assignment due date rather than
  the student's extended date. A direct analogue of the risk that a consequence or its label computes
  from the base date instead of the effective date. The tracker says only the grading table was wrong.
  Note: tracker-old.moodle.org; check the affected branches before citing as current.
- Consequence is per activity (cut-off is a field on each assignment), not a site, organisation or
  cohort policy. Matches the landscape file's conclusion that per-cohort or per-organisation
  consequence policy is not a first-class concept anywhere.

### 2.2 Canvas: Late label inside a grace period

- Idea thread "Enable a grace period for automatic late": Canvas marks Late automatically even
  inside a grace window, the label cannot be turned off per course, staff reset status to None by
  hand. Wishes: a 5 minute to 12 hour grace before late status or penalty, due time left at 11:59 pm,
  and control over when "missing" starts. Not shown as implemented in what I found.
  https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197
  and https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Allow-grace-period-before-automatically/idi-p/652712
- Extending only the close date ("Until") still leaves the submission flagged late unless the due
  date or an assign-to override also changes (La Salle KB, in the landscape file).
- Takeaway for spec 2: the idea's choice that the overdue mark can appear at the due date while closing
  waits for the window is the Canvas complaint in reverse. Canvas users wanted the mark itself to wait.
  This is a real design fork: Canvas sentiment says users want "late" to wait for the grace window; the
  idea shows overdue at the due date and delays only closing. The idea's version is defensible only
  if the learner sees the consequence next to the date ("overdue now, closes on X"), and a policy
  switch for mark overdue exists (it does).

### 2.3 Docebo: soft deadline silently suppresses a notification

Docebo support (Aug 2025) confirmed a soft deadline suppresses the "course expired" notification, so
admins' overdue reminders did not fire. The policy equivalent: a "notify educators" switch that is off
by default is fine, but one consequence switched off must not quietly disable another. Spec 2 only
records the notify switch, so the hazard moves to spec 5; the policy needs the switch to be an
independent setting and visible in the admin.
https://community.docebo.com/product-q-a-7/notifications-for-courses-coming-due-soon-or-past-due-soft-deadline-on-and-learning-plan-course-validity-periods-14525

### 2.4 Open edX: course-wide grace period; end date as hard cutoff

- Grace period is set per course, in HH:MM, uniform across the course, and cannot be set per
  assignment (Studio assessment guide). Graded content cannot be submitted after the course end
  date. Archived courses (past end) allow viewing but not graded submission.
  https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3945365643/Course-Level+Assessment+Configuration
  and https://edx.readthedocs.io/projects/open-edx-learner-guide/en/open-release-juniper.master/SFD_content_availability.html
- Access expiry by track: audit learners lose access after a course-specific number of weeks
  (from enrolment or course start, whichever later); verified keep access longer.
  https://support.edx.org/hc/en-us/articles/360021149373-How-can-I-get-access-after-a-course-expires
- Takeaways: (a) a single grace length is normal and a per-item grace was not offered; (b) "ended"
  is split into "cannot submit graded work" and "can still view", which is the FLS "past results
  stay visible; completed items never close" idea; (c) access expiry differs by learner class in
  edX, supporting a per-registration layer. Relative-date prior art is in deadlines-1's prior art file.

### 2.5 TalentLMS and LearnDash: access ends, staff set a new date

TalentLMS: course expires and access is revoked; staff can set a new expiration for specific users
(then the "Expired" label in the instructor panel is the basic at-risk view). LearnDash: access ends
and the learner is notified; the extension add-on reportedly resets or ignores existing access
(vendor claim). Sources in the landscape file (d, f). Takeaway: restoring opens a new window and keeps
progress matches staff-set new expiration; the stacking of extensions is a spec 3 concern.

### 2.6 Coursera: reset deadline lost work

Coursera "reset deadlines" has reportedly destroyed work when it moved learners to a new version;
reset only appears after two missed deadlines. Source in sentiment (a). Takeaway: restore must keep
all progress and not move a learner to new content; the idea already says so.

### 2.7 SuccessFactors: layered settings and propagation

Item-level email settings override process-level defaults; process changes apply only to new items
unless "Propagate settings to all active items". A reminder that a layered policy needs a rule for
what a change does to existing rows. Here enforcement is computed on read from the current policy, so
a policy edit changes existing learners immediately. That is a decision the spec should state
(it differs from SuccessFactors, where it did not propagate).
https://userapps.support.sap.com/sap/support/knowledge/en/2477571

## 3. What this means for the open questions

(Observations from prior art, not decisions.)

1. **Layer order, course vs organisation.** Moodle and Open edX hold consequence at course or activity;
   nobody layers course against organisation. The messaging chain ends learner, registration, cohort,
   organisation, site, settings and has no course. A likely order from the roadmap's "most specific
   first" is registration, cohort, course, organisation, site, settings, but prior art does not settle
   cohort vs course; the cohort registration row ties cohort to course, so a cohort-course setting may
   be the same row as the registration layer.
2. **Where access ended is enforced.** The deadline wrapper mirrors `VisibilityEnforcingBackend` and
   covers every `get_access` route (`_course_access_redirect`, `course_home`, `course_detail`). The
   predicate route would also change who sees hidden courses and the dashboard "In progress" list.
   Docebo/Canvas sentiment says the learner must be told why: that needs a "reason" on the decision.
3. **Does close leave an in-progress attempt finishable.** The old code left `form_submit_and_exit`
   ungated and `course_form_complete` ungated, but gated `form_start` and `form_fill_page`. So the
   precedent is: submit what is already in flight, do not start or re-enter. Coursera and Open edX
   archived-course behaviour (view, no new graded work) fit.
4. **Registration layer key.** `learner_for_course` resolves one `ResolvedRegistration`; cohort beats
   individual. S10.5 shows it flips when a registration deactivates. Messaging's answer (any path) does
   not apply.
5. **Grace and overrides.** Moodle extensions move due and cut-off together; MDL-44098 shows the failure
   when a derived label uses the base date. Compute grace from the effective `due_at`.
6. **Overdue mark vs grace.** Canvas users complain the Late label appears inside the grace window.
   The idea marks overdue at the due date. Say so explicitly in the spec and show it next to the
   consequence.

## 4. Lessons

- Do not rebuild the old lock: two sources of truth and an unexplained badge were its flaws.
- One decision object read by the player, the TOC and the dashboard, carrying the reason and the
  layer that set it.
- Reuse the messaging resolver's shape; do not reuse its flag field or its "any path" rule.
- Per-learner overrides should move derived close dates with them.
- Keep the exemptions (completed items, results page, `form_submit_and_exit`) as named tests.
- Cheap on read when no policy row exists (the `DEADLINES_ACTIVE` regret).
- QA data that closes things must be seeded and cleaned explicitly.
- Add the E003/E004-style checks for the swappable class; deadlines-1's missing check was a gap.

## References

- Old spec and QA: `spec_dd/3. done/2026-02-19_19:25_deadlines/`
- `spec_dd/3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue/` (upgrade_notes, qa_report, research_prior_art)
- `spec_dd/3. done/2026-10-10_08:57_user-communication-3-messaging-policy/1. spec.md`
- `spec_dd/1. next/roadmap.md` Deadlines section; `spec_dd/1. next/deadlines/research_*.md`
- Moodle MDL-44098: https://tracker-old.moodle.org/browse/MDL-44098
- Kenyon on due and cut-off dates: https://www.kenyon.edu/offices-and-services/center-for-innovative-pedagogy/instructional-technology/moodle/moodle-assignments-due-dates-and-cutoff-dates/
- Canvas ideas: https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197
- Docebo: https://community.docebo.com/product-q-a-7/notifications-for-courses-coming-due-soon-or-past-due-soft-deadline-on-and-learning-plan-course-validity-periods-14525
- Open edX course-level assessment configuration: https://openedx.atlassian.net/wiki/spaces/OEPM/pages/3945365643/Course-Level+Assessment+Configuration
- Open edX learner guide: https://edx.readthedocs.io/projects/open-edx-learner-guide/en/open-release-juniper.master/SFD_content_availability.html
- edX access after expiry: https://support.edx.org/hc/en-us/articles/360021149373-How-can-I-get-access-after-a-course-expires
- SuccessFactors propagation: https://userapps.support.sap.com/sap/support/knowledge/en/2477571
- TalentLMS expiry: https://help.talentlms.com/hc/en-us/articles/360014572494-How-to-work-with-time-limits-and-expired-courses

status: ok
