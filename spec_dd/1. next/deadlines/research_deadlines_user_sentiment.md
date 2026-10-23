# Research: what users say about LMS deadlines (likes, dislikes, wishes)

Scope: input to cutting the FLS "deadlines" idea into specs. Complements `research_lms_deadlines_landscape.md` (what systems do); this file is about what users say. Terms in quotes belong to the named system, not to FLS.

## Method and evidence limits (read first)

- Source: web search (standard mode); each result was a summary of pages, not a full read of every thread. Claims below are limited to what those summaries stated, each with its URL.
- Reddit: searches for r/Teachers, r/instructionaldesign, r/coursera and others returned no Reddit threads at all. No Reddit evidence is included. Treat this as a gap, not as "Reddit has no opinion".
- Not found: G2 reviews on deadlines/overdue handling; Thinkific and Teachable community-forum threads; learner-side Open edX forum complaints; Udemy; moodle.org forum threads on bulk extensions. Capterra/GetApp/SoftwareFinder TalentLMS reviews had nothing deadline-specific.
- Strongest evidence is the Canvas Community (Ideas and Question Forum), Docebo community, the Coursera/DeepLearning.AI community, and Moodle tracker/forum. Vendor-sold surveys (Recurly, Ruzuku, TextBolt) are marked as having a commercial interest.
- Audience tags: [L] learner, [E] educator/instructor, [A] admin/L&D staff. Many sources are educators or admins speaking about learners; the tag is the speaker.

## (a) Hard vs soft deadlines and consequences

### Likes
- [L/E] Advisory deadlines with no penalty are accepted: DeepLearning.AI learners on Coursera say deadlines are advisory and auto-reset with no grading penalty. https://community.deeplearning.ai/t/how-can-i-reset-the-course-deadline-i-am-not-trying-to-pursue-a-grade/270822
- [E] Grace and leniency are valued: a Canvas instructor using a grace period reports students still appreciated the flexibility once it was explained. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197
- [E] Late-work-accepted-for-a-window policies (no deduction up to one week, folder closes a week later) are used by instructors as a deliberate design. https://www.pcc.edu/online/2022/06/late-work-that-actually-works/ (Portland CC teaching blog; search summary)
- [L] Flexible self-paced format is preferred by students (80% in one university study), though some want more structure against procrastination. https://sigcse2024.sigcse.org/details/sigcse-ts-2024-Papers-1/157/Effect-of-Deadlines-on-Student-Submission-Timelines-and-Success-in-a-Fully-Online-Sel and a flexible-format study cited in the same search (https://teach.ufl.edu/wp-content/uploads/2025/05/RiTL-2025-Ahn.pdf)
- [A/E] Evidence that structure helps completion, but mostly vendor-reported: Ruzuku 64.2% cohort vs 48.2% self-paced (vendor with a commercial interest); a MOOC study 45% fixed-schedule vs 13% self-paced, authors attribute much to different starting populations. https://www.ruzuku.com/learn/articles/cohort-vs-self-paced
- [A] Open edX's own decision record says learners finish better with multiple incremental deadlines, which is why relative dates exist. https://docs.openedx.org/en/ulmo/educators/how-tos/course_development/set_course_pacing.html (see also the decision-record summary at https://discuss.openedx.org/t/course-start-and-end-relative-due-dates/16718)
- [E] SIGCSE 2024: carefully chosen deadline policies improved timeliness and pass rates in a self-paced course. https://sigcse2024.sigcse.org/details/sigcse-ts-2024-Papers-1/157/Effect-of-Deadlines-on-Student-Submission-Timelines-and-Success-in-a-Fully-Online-Sel

### Dislikes
- [E] Canvas marks "Late" automatically even inside a grace period, and the label cannot be turned off per course; students worry they were late. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197 ; staff must manually reset status to None (UTS): https://educationexpress.uts.edu.au/blog/2025/02/18/how-to-manage-consistent-due-times-and-late-penalties-in-canvas/
- [E] Late penalties are inflexible: a student a minute late is penalised; weekends and holidays count as days late. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Gradual-automatic-late-penalties/idc-p/543028 ; https://community.canvaslms.com/t5/Canvas-Ideas/Override-Late-Policy-in-Speedgrader/idc-p/418979
- [E] Flat late penalty not available automatically; the 10% deduction must be applied by hand. https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Late-policy-that-is-not-dependent-on-how-late-the/m-p/511135
- [A] Docebo "soft deadline" silently suppresses the expired-course notification (Docebo support, Aug 2025), breaking admins' overdue reminders. https://community.docebo.com/product-q-a-7/notifications-for-courses-coming-due-soon-or-past-due-soft-deadline-on-and-learning-plan-course-validity-periods-14525
- [L] Coursera "Reset deadlines" has destroyed work: learners report quizzes/assignments removed or locked after reset. https://community.deeplearning.ai/t/my-compleated-assignments-disappeared-with-no-warning-after-deadline-reset/5861 ; https://community.deeplearning.ai/t/resetting-deadline-removed-quiz-and-home-submissions/7643 ; https://community.deeplearning.ai/t/assignment-progress-lost/3609
- [L] Reset only appears after missing two assessment deadlines in a row or by about two weeks, so learners cannot reset early. https://community.deeplearning.ai/t/how-do-i-reset-my-deadlines-to-get-the-new-content-without-waiting-for-two-weeks-to-get-the-new-content/516413

### Wishes
- [E] Grace period before automatic late status/penalty (e.g. 5 minutes to 12 hours) without moving the due time off 11:59 pm. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197 ; https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Allow-grace-period-before-automatically/idi-p/652712
- [E] Control over when automatic "missing" grades start. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Allow-grace-period-before-automatically/idi-p/652712
- [A] Learners notice that advisory vs graded deadlines differ by course; no explicit ask found, but Coursera staff replies show hard deadlines are product-line specific (degree/MasterTrack). Landscape file covers this; no new sentiment source.

## (b) Extensions and per-learner overrides

### Likes
- [E] Moodle's "Grant extension" from the grading screen, with multi-select, avoids creating overrides one by one. https://ucldata.atlassian.net/wiki/x/SABBDg (UCL help, via search summary)
- [E] Moodle user/group overrides are seen as the easy answer to technical-problem extensions. https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211
- [E] Canvas "Assign To" is the established way to give a student their own due/available/until dates. https://help.harmonizelearning.com/hc/en-us/articles/32768471875469

### Dislikes
- [E] Canvas: multiple extensions for one student are "tedious and difficult"; each assignment is edited separately. https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Change-multiple-assignment-due-dates-per-student/idi-p/600900 ; accommodation extensions must be entered one assignment at a time. https://community.canvaslms.com/t5/Canvas-Question-Forum/Modifying-due-dates-for-accommodations/m-p/615568
- [E] Canvas bulk date tool changes dates, not times. https://community.canvaslms.com/t5/Idea-Conversations/Bulk-edit-assignments-with-multiple-dates/idi-p/432428 (and the later "add time option" idea, marked delivered: https://community.canvaslms.com/t5/Canvas-Ideas/Add-time-option-to-bulk-assignment-due-date-changer/m-p/444580)
- [E] Canvas "Assign To": if "Available Until" is in use you must also extend it for the student; removing "Everyone" by accident wipes access/grades for everyone else. https://help.harmonizelearning.com/hc/en-us/articles/32768471875469 ; https://support.csuchico.edu/TDClient/1984/Portal/KB/PrintArticle?ID=113756
- [E] Canvas: the Assign To panel hid due/availability dates after a redesign, risking forgotten dates. https://community.canvaslms.com/t5/Canvas-Question-Forum/Assign-to-panel-in-Assignments-now-hides-due-dates-and/m-p/609501
- [E] Canvas known issue: module-created assignments with an "Everyone else" override do not populate the due date. https://community.canvaslms.com/t5/Known-Issues/OPEN-Assign-To-module-setting-causing-some-assignments-due-at/ta-p/618814
- [E] Moodle overrides do not survive backup/restore. https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211
- [A] LearnDash extend-access replaces the existing end date (does not add); group end dates cap the course extension. https://learndash.com/support/kb/add-ons/users/extend-access/ ; https://learndash.com/support/wp-json/wp/v2/docs/5491

### Wishes
- [E] Change multiple assignment due dates for one student from the Gradebook/Grades page. https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Change-multiple-assignment-due-dates-per-student/idi-p/600900
- [E] Update all due dates in a module at once. https://community.canvaslms.com/t5/Canvas-Ideas/Modules-Update-due-dates-for-all-items/m-p/614833
- [A] Stackable extensions: a third-party plugin exists precisely because purchased days should add onto existing expiry. https://ko.wordpress.org/plugins/course-access-extender-for-learndash/
- [L] Learner-initiated shift: Open edX lets learners shift suggested due dates into the future themselves once a date has passed (not before; not after the course ends). https://support.edx.org/hc/en-us/articles/206501098-I-can-t-make-a-deadline-can-I-get-an-extension
- [A] Moodle has a plugin for students to request manual enrolment extensions, indicating demand for a request flow. https://moodle.org/plugins/local_extendmanualenrol/1.0.5/36265
- Institutional extension policies show what staff expect to administer: fees, limits (one 8-week extension, a second for severe illness, 16-week cap), request deadlines, documented medical reason. https://www.tesu.edu/academics/catalog/course-extensions ; https://anaheim.edu/wp-content/uploads/2025/01/aumedicalabsence_ff.pdf

## (c) Pausing / freezing an enrolment

Evidence is thin for LMSs; most is from institutional policy and subscription products.

### Likes
- [L, subscription] Pausing is the most wanted subscription feature: 55% named it top (Recurly/Hanover survey, vendor with commercial interest); where offered, 25% paused instead of cancelling. https://recurly.com/blog/the-pause-button-your-best-retention-tool ; https://recurly.com/blog/what-consumers-want-pausing-options/
- [L, subscription] A common cancel reason is "too much of the product", and skip-one-order is not enough for a longer break; Recharge case study. https://getperspective.ai/blog/pause-vs-cancel-2026-what-subscription-pause-requests-tell-you (secondary)
- [A] Capturing a reason at pause time is more honest than cancel-time exit surveys (opinion). https://changelog.skio.com/changelog/skip-and-pause-surveys
- [L, institutions] Medical leave is accepted when documented, and time away may or may not count against maximum completion time: Royal Roads counts it toward the maximum program deadline. https://royalroads.ca/sites/default/files/2021-07/Medical%20Leave%20of%20Absence.pdf

### Dislikes
- [L, gyms] Billing continued during closures and freezes were refused or hard to get (phone cancel impossible; fees and onerous conditions); regulators got involved. https://billypenn.com/2020/04/10/some-philly-gyms-delayed-membership-freeze-causing-customer-outrage/ ; https://ag.ny.gov/press-release/2020/attorney-general-james-delivers-financial-relief-new-york-sports-clubs-and ; https://www.pressreader.com/canada/calgary-herald/20201228/281586653211061
- [A] Uptake caveat: many with the option never use it. https://recurly.com/blog/the-pause-button-your-best-retention-tool
- [L, course platforms] Refund/extension requests being declined citing terms is a repeated competitor-blog claim for Thinkific/Teachable (Ruzuku sells a competing platform; anecdotal). https://www.ruzuku.com/learn/articles/how-to-cancel-thinkific
- [A] Extensions often require request before the term ends and carry fees even for illness. https://www.tesu.edu/academics/catalog/course-extensions

### Wishes
- [L] Pause offered at the point of cancelling (Recharge design). https://getperspective.ai/blog/pause-vs-cancel-2026-what-subscription-pause-requests-tell-you
- [A] Teachable shows demand-side pattern: fixed unenrol date vs rolling duration, manual re-enrol; no pause found. https://intercom.help/teachableknowledgebase/en/articles/11682480-product-access-duration
- [A] LearnDash: no built-in pause/freeze found in search; users rely on extend-access. https://learndash.com/support/kb/add-ons/users/extend-access/
- No community thread found asking specifically for "pause course clock" in Moodle, Canvas, TalentLMS or Docebo.

## (d) Relative vs fixed dates

### Likes
- [A] Relative dates (offset from enrolment or course start, whichever is later) exist in Open edX because of completion data from edx.org. https://discuss.openedx.org/t/course-start-and-end-relative-due-dates/16718
- [L] Learners can see and shift personal relative dates (Open edX "Personalized Learning Schedule"). https://support.edx.org/hc/en-us/articles/206501098-I-can-t-make-a-deadline-can-I-get-an-extension
- [A] Moodle "Course relative dates" feature shows dates relative to each user's start. https://docs.moodle.org/405/en/Course_relative_dates

### Dislikes
- [A] Moodle relative dates are experimental, assignment-only, weekly format only, no Restrict access or Quiz. https://docs.moodle.org/405/en/Course_relative_dates
- [A] Moodle request for relative dates on all activities was closed "Won't Do" (MDL-61209); a duplicate (MDL-46922) was closed. https://tracker-old.moodle.org/browse/MDL-61209 ; https://tracker-old.moodle.org/browse/MDL-46922
- [A] Open edX: admins enabled the relative-date setting site-wide but the option does not appear; unclear defaults in Tutor. https://discuss.openedx.org/t/issue-with-the-self-paced-configration/14574
- [A] Moodle forum: new-hire onboarding thread concluded core Moodle cannot set due dates from enrolment; workarounds were cohorts, custom reports, or Totara. https://moodle.org/mod/forum/discuss.php?d=395169

### Wishes
- [A] Teacher-set offset (hours/days/weeks after enrolment) for due dates, with open questions: first enrolment only when several enrolment methods exist, and whether re-enrolment restarts the clock (MDL-72483). https://tracker-old.moodle.org/browse/MDL-72483
- [A] X days after enrolment, especially for quizzes (MDL-46922). https://tracker-old.moodle.org/browse/MDL-46922
- [A] Recurring compliance: next due date computed from last completion, reassignment N days after completion; admins ask whether an early or late completion should move the cycle. https://learnupon.com/?p=10708 ; https://help.fldata.com/kb/lms-troubleshooting-due-dates
- [A] Totara admins run manual daily tasks to catch learners who retook a course outside the recertification window. https://totara.community/mod/forum/discuss.php?d=26245

## (e) Reminders

### Likes
- [L, A] Reminder ladders are the vendor/consultant norm: 7, 3, 1 days before, manager escalation on first overdue day. https://www.absorblms.com/resources/articles/how-to-boost-training-completion-rates-with-automated-training-reminders (vendor)
- [A] TalentLMS reviewers praise automated notifications and reminders for required training (several Capterra/SoftwareFinder reviewers; not deadline-specific). https://capterra.com/p/132935/TalentLMS/reviews/ ; https://softwarefinder.com/lms/talentlms/reviews?page=5
- [A] Logging each notice creates an audit trail of follow-up. https://orrs.msu.edu/train/compliance-officer/compliance-strategies.html
- [L] Students prefer deadline notices on smartphones; they rank deadlines the most important syllabus item but look for them in several LMS places (UNH study). https://findscholars.unh.edu/display/publication598404

### Dislikes
- [L] Students feel overwhelmed by notifications and ignore important ones; many never learn to change settings (Edinburgh); "announcement fatigue" and muting (Sussex). https://blogs.ed.ac.uk/learning-design/2021/06/25/notification-fatigue/ ; https://blogs.sussex.ac.uk/tel/wp-json/wp/v2/posts/9461
- [A] MSU: timing is a judgment call, too close leaves no time to act, too early loses urgency; managers split between "notify me earlier" and "too many emails". https://orrs.msu.edu/train/compliance-officer/compliance-strategies.html
- [A] Docebo: one notification has one schedule and one primary recipient role, so 30/20/7-day reminders with a manager copy need several separate notifications. https://community.docebo.com/product-q-a-7/setting-up-course-completion-reminders-16422
- [A] Docebo: no learning-plan-level reminder; workaround digest depends on course "Active Until"; notifications cannot go directly to managers from a learning plan. https://community.docebo.com/product-q-a-7/learning-plans-past-due-notifications-4656 ; https://community.docebo.com/product-q-a-7/how-to-create-learning-plan-notifications-for-managers-13837
- [A] TalentLMS reviewers: limited notification customisation, "unreliable notifications", ~2 hour delay on enrolment alert. https://capterra.com/p/132935/TalentLMS/reviews/?page=5 ; https://www.getapp.com.au/software/90660/talentlms
- [L] Canvas has no automatic due-date reminder; the idea is open for years. https://community.canvaslms.com/t5/Canvas-Ideas/Notifications-Automatic-due-date-reminder-notifications/idc-p/400618

### Wishes
- [L, E] Canvas idea: default reminder 24 hours before, only to students who have not submitted. One student calls 24 hours useless and wants 30/10/5 minutes; others want adjustable, opt-out, per-course control, reminders after the due date when late work is still accepted, and repeats for long assignments. https://community.canvaslms.com/t5/Canvas-Ideas/Notifications-Automatic-due-date-reminder-notifications/idc-p/535467
- [L] Reminder for lock dates (last day late work is accepted). https://community.canvaslms.com/t5/Canvas-Ideas/Calendar-Reminder-for-lock-dates/idi-p/610137
- [A] Docebo: manager notification before the due date, not only a digest after (no replies). https://community.docebo.com/product-q-a-7/notification-to-manager-that-learning-plan-enrollment-is-due-soon-12887
- [A] Overdue-only recurring manager digests, which Docebo added as "Include only expired enrollments". https://community.docebo.com/product-q-a-7/recurring-digest-notifications-for-overdue-courses-only-12151
- [A] SuccessFactors: notify managers only after the due date. https://groups.community.sap.com:443/t5/human-capital-management-q-a/escalate-notify-manager-when-learning-item-compliance-training-is-over-due/qaq-p/12480740
- Evidence gap: no controlled study of reminder frequency vs completion was found; TextBolt claims are marketing. https://textbolt.com/blog/reduce-missed-academic-deadlines/

## (f) At-risk / overdue reporting

### Likes
- [E] Canvas "Students in Need of Attention" report (late/missing thresholds). https://help.canvas.yale.edu/a/2029620-students-in-need-of-attention-report
- [E] Third-party Dropout Detective: nightly risk level with late, missing, zeros, last access. https://www.usm.edu/online-learning/dropout-detective.php
- [A] Docebo "My Team" page lets managers find overdue requirements. https://community.docebo.com/product-q-a-7/learning-plans-past-due-notifications-4656
- [A] LearnUpon-style compliance reports show who has not finished or is not compliant. https://learnupon.com/?p=10708

### Dislikes
- [E] Canvas report data is not live (refreshed every 8 hours at Yale). https://help.canvas.yale.edu/a/2029620-students-in-need-of-attention-report
- [E] A per-student missing-assignment report was not possible in Canvas; an idea was open. https://community.canvaslms.com/t5/Archived-Questions/Missing-assignment-report/td-p/165174
- [A] TalentLMS reviewers: reports hard to shape; poor reporting of courses. https://capterra.com/p/132935/TalentLMS/reviews/?page=6
- [A] Totara admins need manual daily tasks to detect recertification edge cases. https://totara.community/mod/forum/discuss.php?d=26245

### Wishes
- [A] Flag overdue courses to managers on Docebo My Team (posted to the idea portal). https://community.docebo.com/product-q-a-7/due-dates-and-alerting-supervisors-4703
- [A] Compliance admins want clock-per-person renewal handled automatically, since cycles do not align across employees. https://coggno.com/blog/automated-recertification-tracking-compliance-lms-lapsed-training/ (vendor)

## (g) Timezone and end-of-day

### Likes
- [E] Setting a morning deadline (Monday 8 a.m.) for working adults who only have Sunday evening; with the explicit warning to tell students about time zones. https://community.canvaslms.com:443/t5/Idea-Conversations/Ability-to-Set-Default-Due-Time-at-Course-Level/idc-p/426173
- [E] A course-level default due time was requested as a way to keep times consistent. same thread.

### Dislikes
- [L] Canvas default 11:59 pm is criticised as stress-inducing; "11:59" means a submission 1 second past is late. https://saratogafalcon.org/11019/opinion/teachers-should-not-set-deadlines-1159/ (student opinion piece); https://community.canvaslms.com/t5/Canvas-Question-Forum/Assignment-submitted-on-due-date-time-marked-as-late/m-p/511838
- [L] Moodle shows times in the user's zone without naming it; global users read unlabelled time as UTC. https://moodle.org/mod/forum/discuss.php?d=407277
- [L] Where site timezone is forced, students forget times differ from their local time. https://moodle.org/mod/forum/discuss.php?d=262477
- [E] DST shifts deadlines by an hour. https://webwork.maa.org/moodle/mod/forum/discuss.php?d=3421 (WeBWorK on Moodle, not core Moodle)

### Wishes
- [E] Show the timezone next to every clock time. https://moodle.org/mod/forum/discuss.php?d=407277
- [E] Grace after the due time instead of moving the due time. https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Settings-Enable-a-grace-period-for-automatic-late/idi-p/658197

## Implications for FLS

Strength key: STRONG = several independent sources across systems; MODERATE = a few sources; WEAK = one source or vendor claim.

1. Separate "late" from "closed" from "penalty", and make a grace window a first-class setting. STRONG (Canvas ideas on grace periods and the unconditional "Late" label, UTS manual resets, Moodle due/cut-off split). Do not make the label undeletable once a grace period applies.
2. Make per-learner extension cheap in bulk: multi-select learners and multi-select items in one action, from the learner's progress view as well as from the item. STRONG (Canvas bulk ideas, accommodation threads, Moodle "Grant extension" praise). The pain is repetition, not the concept.
3. Extending must not leave a half-extended state: one extension action should move due and close dates together, and be impossible to apply in a way that still shows late. STRONG (Canvas Until/due mismatch, Harmonize and LaSalle guides, plus Chico accidental removal of "Everyone").
4. Overrides must follow or visibly flag base-date edits and survive course copy. MODERATE (Moodle backup/restore loss, Monash base-date non-tracking in the landscape file; Canvas known issues).
5. Never destroy learner work on reset, extend or pause. STRONG for Coursera (multiple independent learner posts), single-system but severe.
6. Support relative-to-enrolment deadlines at item and course level and define re-enrolment semantics up front (first enrolment? restart the clock?). MODERATE (Open edX rationale, Moodle trackers and forum asking for it repeatedly and one "Won't Do", MDL-72483 open questions). Users clearly want it, and the partial implementations are a complaint.
7. Pause is a gap in LMSs, not a solved problem: model it as a first-class record with a reason and an approval option, resume date, and a rule for shifting dates. MODERATE (subscription surveys, medical-leave policies, gym grievances; no LMS thread was found, so this rests on adjacent domains). Hard rule from the gym complaints: stopping the clock and any charge must happen together and be easy to request.
8. Cap and document extension and pause: count/length limits, request-before-end rules, documented reason. MODERATE (university extension policies; gym policies in the landscape file). Make limits configurable per course/organisation.
9. Reminders need a single rule object with several offsets and several recipient roles, not one notification per offset. STRONG (Docebo threads, SuccessFactors in the landscape file). Include before-due, due-today, and after-due-while-late-work-is-accepted offsets (Canvas ideas).
10. Anchor reminders on the effective deadline and ensure that soft or extended deadlines never silently disable them. MODERATE (Docebo soft-deadline suppression, enrolment-anchored mismatch).
11. Respect notification fatigue: per-learner channel and opt-out settings, only notify those who have not completed, one digest when several items fall due together. MODERATE (Edinburgh, Sussex, Canvas idea comments). Optimal timing is contested (24 hours called useless by one student; MSU says unknown); make offsets configurable and do not hard-code a ladder. Evidence on any best schedule is WEAK.
12. Educator at-risk view must be live, filterable, and list late/missing counts with a threshold; managers need overdue-only digests and an "overdue/due soon" team page. MODERATE (Canvas, Docebo, Totara). Stale data (8 hour refresh) was a complaint, so show the as-of time at least.
13. Escalation to a manager or educator should be configurable as before-due and after-due separately. MODERATE (SuccessFactors and Docebo requests, both unresolved).
14. Time handling: show timezone beside every time shown, avoid midnight defaults, default to end-of-local-day or a configurable course time, test DST. STRONG (Moodle forum, Canvas 11:59 discussion, WeBWorK DST, landscape file).
15. Consequence policy per course/cohort/organisation is new ground: no user in the search asked for it in those terms, but learners and educators complain when consequences are invisible or inconsistent (Coursera hard vs soft by programme, Docebo soft-deadline surprises). Show learners the consequence in the UI next to each deadline. WEAK as demand evidence; design judgement.
16. Do not rely on Reddit or G2 findings: they were not reached. If the owner needs those voices, run a targeted follow-up.

status: ok · reason: web research complete for Canvas, Moodle, Docebo, Coursera, Open edX, TalentLMS and subscription pause; no Reddit, G2, Thinkific/Teachable forum threads were retrievable (see limits at top)
