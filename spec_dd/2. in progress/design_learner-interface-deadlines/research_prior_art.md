# Research: prior art for learner-facing deadline display

Topic `prior_art`. Source idea: `idea.md` here (dashboard card band, player next-deadline card, inline outline row dates, body header deadline card; upcoming-deadlines grouped list is a separate later spec). `design.md` is a visual reference only.

## Part 1: Here (spec_dd history)

### 1.1 `3. done/2026-02-19_19:25_deadlines` and `2026-02-21_16:30_deadlines_deactivate` (old implementation)
- Built: `CohortDeadline`, `LearnerDeadline`, `LearnerCohortDeadlineOverride`, hard-lock deadlines, TOC badges in `course_minimal_toc.html` (`deadline-badges` partialdef), `DEADLINES_ACTIVE` switch. Old QA screenshots (`test2-toc-deadline-display.png`, `test3*`) cover TOC deadline display and expired-item lock.
- Outcome: removed wholesale by deadlines-1 (no rows migrated). The old badge used `text-warning` (Sand) as text, which fails contrast, and `title` for explanation, which is unreliable on touch/keyboard (deadlines-1 `research_ux_patterns.md` section 2). Do not reintroduce either.
- Not binding on this work except as the thing it replaces.

### 1.2 `3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue` (the display baseline this work upgrades)
Decisions on learner-facing display (spec `1. spec.md`, "Learner interface"):
- Wording is "Deadline" and "Missed deadline", never "Due" or "Overdue". Missed mark is `<c-panel-status-badge tone="error" label="Missed deadline">` (brand-guidelines). Added a `learner_interface -> panel_framework` edge.
- Every learner date goes through the `local_time` template tag (`<time datetime=UTC>`, server text in site zone) and the `localTime` Alpine component (rewrites in the browser zone, no zone label unless `show_time_zone_to_learners`). Decision 9.
- TOC (`course_minimal_toc.html`, shared by player sidebar and course detail): "Deadline <date>" on its own line under the row title, indented to start under the row icon; on overdue rows the chip replaces the word "Deadline"; completed rows show neither; part rows show no date. `get_course_index` adds `collection_item_id`, `due_at`, `is_overdue` to each child dict.
- Course detail resolves no deadlines and shows none, to any viewer (registered or not); it shows only a "Time limit N days" stat cell. Only the player passes `CourseDeadlines`.
- Dashboard card: ONE line in the card body above the progress bar, never in the eyebrow slot (the eyebrow is "the single place status is ever shown"). Priority: (1) any missed deadline: chip plus earliest missed title and date; (2) earliest future: muted "Next deadline: <title> <date>"; (3) nothing. The time limit counts as one more deadline titled "Course". Query count constant in cards/items (`course_deadlines_for`).
- Date rule: no `due_time` means end of day 23:59:59 in the site zone; `datetime` attr is whole-second (commit fc7a38ad4).
- Inherited research (`research_ux_patterns.md`): no competitor puts per-item dates on a course card; they show next date, an overdue count or one chip. Absolute date is source of truth, relative text only a supplement; overdue is a text label first, colour reinforces (WCAG 1.4.1); no ticking countdown; a truncated row must not truncate the date or label (title `truncate`, date `shrink-0`).
- QA (`qa_report.md`, FULL, desktop/mobile/tablet): all pass, 0 bugs. Confirmed: deadline line starts under the icon (116px desktop, 76px mobile); chip and date fit on one line on mobile and tablet, wrap under the chip on desktop; card line sits above the progress bar; no horizontal overflow or console errors; outline uses a sheet at mobile and tablet. Known gaps: top-level dated rows alignment untested (no demo course has a dated top-level item); the 5.1 player check was weak; unfold inline rows show "CohortDeadlineOverride object" (admin only, no `__str__`). Two plan errors (US DST on 8 Mar 2026; whole-second `datetime`) were plan faults, not bugs.
- Demo data for QA: `functionality_demo_course_parts` (time limit 90 days, relative dues, one fixed past date), seed command `qa_create_deadlines_seed`.

### 1.3 `3. done/2026-11-01_23:53_deadlines-2-consequence-policy` (copy states the redesign must keep)
Spec copy table (`1. spec.md` ~lines 288-298), applied to the TOC, the section header and the card line from one set of index keys:
| State | Copy |
|---|---|
| Due, closing on | "Deadline <date>. Closes <close date>." |
| Overdue, open, `mark_overdue` on | "Missed deadline" chip, then "Closes <close date>." when closing is on |
| Overdue, `mark_overdue` off | "Deadline <date>." (+ "Closes ..." when closing on); no chip |
| Closed | "Closed <close date>" chip with icon, never colour alone; screen reader text "Closed" |
| Time limit, ending on | "Access ends <date>." |
| Access ended | "Access ended <date>." (dashboard eyebrow; course detail message, no CTA) |
- The player ALREADY has a header deadline line: QA 3.1 notes "header repeats Missed deadline + Closes", 3.7 notes a completed item has no header deadline line. The idea's "body header deadline card" upgrades an existing element, it is not new surface.
- `mark_overdue` off (setting hierarchy: course/cohort/site) must suppress the chip everywhere: outline, header, dashboard card item and time limit.
- Closed sequential lock rule 11: items after a closed incomplete item are unlinked with sr "Locked" and no Closed chip.
- QA: 34 records, 33 pass, 1 fail. Open bugs (both UNRESOLVED in report): B1 the dashboard card's "Closed" line drops the item title (`partials/deadline_labels.html` only renders the title in overdue/due branches; spec copy table says "Closed <close date>" for TOC, header, card alike); B2 results page under `after_access_ended=nothing` still draws an empty "COURSE OUTLINE" panel (not deadline display). Observations: an ended course's player outline still prints "Missed deadline" chips on locked rows; mobile 375px dashboard renders stacked cards; mobile closed-topic header chip wraps cleanly at 375 with no overflow; mobile outline drawer lists Closed/Locked rows with chips; tablet uses the drawer outline ("Open course outline").
- Implication: the shared `partials/deadline_labels.html` is the single copy source; the redesign should consume it rather than fork copy, and B1 is a live defect in the card path the band touches.

### 1.4 `1. next/` and `2. in progress/` (pending work that touches learner-facing deadlines)
- `deadlines-3-extensions-and-pause`: course detail and dashboard show the paused state and planned resume date (line 55). The band and next-deadline card need a paused state or must leave room for one.
- `deadlines-4-learner-self-pause`: pause control/banner on course detail; paused state on the dashboard card within `CourseListingEntry` (line 60).
- `deadlines-5-reminders`: learner notifications; notes learners otherwise learn of a date only by opening the course or dashboard (line 58), the argument for better in-page display.
- `deadlines-6/7`: educator-side only (Needs attention, reports); no learner display overlap, but 7 reuses `reports` status/badge vocabulary, so learner chip tones should not be reinvented.
- `1. next/deadlines/` parent idea plus four shared research files (`research_current_deadlines.md`, `research_deadline_integration_points.md`, `research_lms_deadlines_landscape.md`, `research_deadlines_user_sentiment.md`).
- `roadmap.md` line 911: `design_learner-interface-deadlines` is listed "Redesign how deadlines and windows look to learners", dependencies "none", status in progress. Roadmap Deadlines section (lines 501-519, 554-626): seven specs, 1 and 2 done; 3-7 "next".
- The "upcoming deadlines page" (grouped list) is deferred to a new spec by `idea.md`; nothing in `1. next/` covers it yet. `design.md` marks panel A grouped list, hero, alert, banner, drawer/popover, mobile dashboard/sheet as out of scope.

### 1.5 Decisions this work must not reopen
1. Terms: "Deadline", "Missed deadline", "Closed", "Access ends", "Access ended"; never "Due"/"Overdue" in learner copy.
2. Missed mark = `c-panel-status-badge tone="error"`; colour never carries meaning alone; icons paired with text.
3. Dates only via `local_time` / `localTime` (`<time datetime>` UTC, browser zone, zone label only when `show_time_zone_to_learners`). No relative-only text, no live countdown.
4. Resolution is `course_deadlines` / `course_deadlines_for` plus the `get_course_index` keys (`collection_item_id`, `due_at`, `is_overdue`, deadline-2 keys); no new resolver, no per-item or per-card queries.
5. Course detail shows no deadlines and only the authored "Time limit N days" cell (spec 1 Decision; QA verified identical for all viewers). The redesign cards live in the player and dashboard only.
6. The dashboard card has one status eyebrow; deadline info goes in the body, not a second status chip. The "band under the thumbnail" decision (idea) must be reconciled with this rule explicitly, since the band is a new slot.
7. Completed rows show no deadline or chip; part rows show no date; time limit counts as the "Course" deadline.
8. `mark_overdue`, `close_items`, grace window and `after_access_ended` policy semantics (spec 2) are fixed; display only reads them.
9. Visual scope: design.md picks only card C band, sidebar B next-deadline card, outline A dates, header B block, tablet and mobile outline sheet; use project theme/components, not design colours.
10. Query-budget tests, site isolation and one-registration-governs tests from spec 1 remain valid regression guards.

## Part 2: Elsewhere

Evidence limits: no official post-mortem on any of these redesigns; user reaction comes from forum threads and institutional notes. Searches of the open web returned little learner feedback on the edX Dates tab.

### 2.1 Canvas
- New student dashboard with a centralized To-Do List widget (Rutgers announcement, release 25 May 2026): opt-in, student-only roles, classic view retained; one list across all courses, sortable by course or status (Missing, Upcoming), counts of due/missing/submitted. Items appear only if instructors set due dates and include them; text headers in modules do not appear. https://canvas.rutgers.edu/2026/05/25/canvas-student-dashboard-changes/
- Earlier (2018) List View from the dashboard menu showing upcoming work across classes. https://scholarblogs.emory.edu/digitalmatters/?p=929
- Reported afterwards: a Canvas Student iOS update reverted the To-Do list to its original model after complaints that it showed too many items (https://community.canvaslms.com/t5/Canvas-Mobile-Forum/New-update-regarding-the-to-do-feature-on-Canvas/m-p/656022); students who fall behind on six or seven assignments see old backlog crowd out future work (https://community.canvaslms.com/t5/Canvas-Mobile-Forum/To-do-List/m-p/551220); a change.org petition "Undo the New Canvas Update" exists (https://www.change.org/p/undo-the-new-canvas-update; content unverified). Note: the Canvas dashboard course card itself shows no per-item dates (deadlines-1 UX research).
- Lesson: aggregated lists need caps and backlog handling (relevant to the deferred grouped-list spec, not this one); undated items vanish, so the display depends on authors setting dates. Relevant here: Canvas Assign To panel hid due dates after a redesign, risking forgotten dates (https://community.canvaslms.com/t5/Canvas-Question-Forum/Assign-to-panel-in-Assignments-now-hides-due-dates-and/m-p/609501). Canvas "Late" label shown even inside a grace period, not switchable per course, worries students (https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197); FLS's `mark_overdue` toggle already addresses this.

### 2.2 Open edX
- Dates tab: vertical date-ordered timeline with badges ("Due", "Completed", "Past due", "Today"); made the default for all courses (https://discuss.openedx.org/t/dates-tab-added-as-default-for-all-courses/7849). Dates in the learner's account zone, else browser zone (https://support.edx.org/hc/en-us/sections/115004169647-About-Dates-and-Schedules). Self-paced dates are suggestions. Legacy Dates tab later removed for the MFE version (commit noted in the search).
- Missed-deadlines banner above the list with "Shift due dates" button, driven by the Dates API `missed_deadlines` flag (https://code.vt.edu/hsinyu/edx-platform-release/-/blame/514d10599df8dbbe16c032cd8347c1a1e8c5eb82/lms/templates/dates_banner.html). Outline shows "Due <date>" under each subsection with zone abbreviation.
- Reported afterwards: no learner feedback found; operators asked how to remove "Course starts in X months" pre-release reminders (https://discuss.openedx.org/t/how-to-remove-course-starts-in-x-months-reminder-from-pre-release-courses/8027), a sign banners need off switches. Open edX rationale: incremental deadlines improve completion (https://docs.openedx.org/en/ulmo/educators/how-tos/course_development/set_course_pacing.html).
- Lesson: per-row date under the title plus a page-level summary is the proven pairing; it matches the idea (inline row dates plus next-deadline card).

### 2.3 Moodle
- 4.0 dashboard redesign: Timeline block as the deadline-focused view with prominent "overdue" badges, grouped by date or course, filters including Overdue (https://catalyst-au.net/blog/moodle-dashboard-redesign-moodle-40). Course Overview block split into Timeline and Courses blocks (https://tracker-old.moodle.org/browse/MDL-63044).
- Reported afterwards (tracker): MDL-72594, overdue badge ignored items that expired earlier "today" (https://tracker-old.moodle.org/browse/MDL-72594); MDL-73613, overdue filter loaded a single course and fixing "today" overdue made all courses always display (https://tracker-old.moodle.org/browse/MDL-73613). Moodle shows times in the user's zone without naming it; global users read them as UTC (https://moodle.org/mod/forum/discuss.php?d=407277).
- Lesson: the overdue boundary (same-day items) and time-zone labelling are where bugs and confusion concentrate. FLS already ties overdue to `now > due_at` and an end-of-day default (spec 1 Decision 3); a band or card must use `is_overdue` from the index, not recompute.

### 2.4 Coursera
- Suggested (flexible) deadlines: no penalty for missing; learners can adjust or turn them off; "Reset deadlines" offered after missing two assessment deadlines in a row or one by two weeks, usable repeatedly; reset shifts dates forward so they no longer appear behind (https://blog.coursera.org/coursera-update-striking-a-balance-with-start/ ; forum quote https://community.deeplearning.ai/t/reset-deadlines-question/125989).
- Reported afterwards: learners report the reset option missing or failing, needing support to fix (https://community.deeplearning.ai/t/unable-to-reset-deadline-for-gans-specialization-courses/736274 ; https://community.deeplearning.ai/t/cannot-reset-deadlines-for-course-3-dls/155009); some report work removed or locked after reset (https://community.deeplearning.ai/t/my-compleated-assignments-disappeared-with-no-warning-after-deadline-reset/5861); advisory deadlines accepted when clearly advisory (https://community.deeplearning.ai/t/how-can-i-reset-the-course-deadline-i-am-not-trying-to-pursue-a-grade/270822).
- Lesson: soft vs hard must be visibly different in the display; "Missed" must not read as punitive when `mark_overdue` is on but nothing closes. Resets/shifts are specs 3-4, not this one.

### 2.5 Cross-cutting takeaways for this spec
- Card-level: show one next/missed signal, not a list; FLS card line already follows that and the band restyles it.
- Row-level: date under title, text label plus icon plus colour, never colour alone; keep date from truncating.
- Page-level summary above the outline (edX banner, Coursera course home) is the precedent for the next-deadline card.
- Boundary and zone consistency (Moodle trackers, Canvas zone threads): one source of truth for "overdue" and for time rendering.
- Redesigns that hid or crowded dates drew reversions (Canvas iOS To-Do revert, Assign To panel); keep information density in rows modest ("keep text to a minimum" per idea).

## References
- Repo: `spec_dd/3. done/2026-10-25_17:46_deadlines-1-dates-and-overdue/{1. spec.md,qa_report.md,research_ux_patterns.md}`; `spec_dd/3. done/2026-11-01_23:53_deadlines-2-consequence-policy/{1. spec.md,qa_report.md}`; `spec_dd/3. done/2026-02-19_19:25_deadlines/qa_report.md`; `spec_dd/1. next/roadmap.md`; `spec_dd/1. next/deadlines*/idea.md`; `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`.
- Web URLs inline above.

status: ok
