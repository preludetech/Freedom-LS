# Research: reference implementations of deadline consequences

Scope: how Moodle, Canvas, Open edX, Blackboard, TalentLMS, LearnDash and others turn a passed date into a consequence (late mark, close, access end, notify), how a grace period is modelled, what happens to in-progress work, how access is restored, and how settings are layered. Goes deeper than `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md` (sections d and f) and does not repeat it. System terms in quotes belong to that system, not to FLS.

Sources are vendor docs, university help pages and forum posts (standard-mode search). Caveats are marked per item. Not verified: Thinkific and Docebo expiry/restore docs (searches returned neither), Moodle gradebook "Grant extension" against override cut-off, Open edX default courseware access after a self-paced course end (not confirmed), and two TalentLMS help pages (HTTP 403).

## 1. Moodle

**Assignment: due date vs cut-off are separate consequences.** "Due date": submissions still allowed, marked late. "Cut-off date": "the submit button will be hidden", students cannot submit. "Allow submissions from" blocks early work. "Remind me to grade by" is a teacher-facing date that feeds the teacher's timeline, appearing once at least one student has submitted (so the educator notification is a date on its own, not a consequence of lateness). The assignment page documents no grace period; "Grant attempts" is unrelated. https://docs.moodle.org/en/Assignment_settings

**In-progress work at assignment cut-off: undefined in docs.** With "Require students click submit button" = Yes, students keep drafts but cannot submit after cut-off; docs do not say a draft is auto-submitted. Teachers can "Prevent submission changes" or "Revert the submission to draft" per submission. Practical reading: the draft is left as a draft, unsubmitted, and the teacher decides. https://docs.moodle.org/en/Assignment_settings

**Assignment time limit** (per attempt) is a different axis: it does not stop submission; a late-by-time-limit submission is recorded as such. https://docs.moodle.org/en/Assignment_settings

**Quiz: three explicit answers to "what about an open attempt when time ends".** The "When time expires" setting offers (1) "Open attempts are submitted automatically" (default), (2) "Grace period": open attempts can still be submitted but no more questions answered, with a configurable "Submission grace period", (3) "Strict cutoff": attempts must be submitted before time expires "or they are not counted". If the student is actively working when the countdown reaches zero, the attempt is submitted at that moment regardless; the setting applies only to a student who left and returned. The quiz "Close date": no new attempts can start; answers submitted after closing are saved but not marked; students may still view the description and review. https://docs.moodle.org/en/Quiz_settings

So Moodle already models a **grace window as an explicit named mode, per item, only for timed attempts** (not for due dates), and it treats "close" as "stop starting things" with finish-or-auto-submit as a separate choice.

**Overrides (layered per item).** User override beats group override; with several group overrides the most generous value wins (earliest open, latest close, longest time limit, most attempts). Only enabled fields are overridden. Overrides do not follow later changes to the base due date and do not survive backup/restore. Moodle 5.2 adds a "Reason for override". https://docs.moodle.org/en/Assignment_overrides , https://www.monash.edu/learning-teaching/teachhq/moodle/assignment/how-to/extensions-and-resubmissions , https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211 , quiz precedence at https://docs.moodle.org/en/Quiz_settings

**Course access end = enrolment end, a different mechanism from item dates.** Self enrolment has "Enrolment duration", an "Enrolment expiry action" (suspend or unenrol; unenrol purges grades, groups and preferences, so the docs warn against it), "Notify before enrolment expires" to teacher and optionally student with a threshold in days, and an "Expiry notification hour". Defaults are site-wide (Site administration > Plugins > Enrolments > Self enrolment) and a course teacher may override per course. A suspended enrolment is restored by reactivating it with a new "Enrolment ends" date. https://docs.moodle.org/en/Self_enrolment , https://telsupport.brookes.ac.uk/articles/how-do-i-reactivate-suspended-enrolments-in-moodle/

**Layering in Moodle.** Site admin default, then course teacher setting, then per-item dates, then group/user override per item. The course-end consequence (expiry action) and the item consequence (cut-off) live in different tables and are set at different scopes. There is no organisation or cohort policy layer in core (cohorts only drive enrolment). Moodle also has no single "policy object": consequences are spread over settings that each have their own default.

## 2. Canvas

**Dates and consequence are separate.** Three dates (Due, Available From, "Until"). Due flags late. "Until" locks submission. Late and missing-submission policy is a gradebook setting per course, applied automatically (fixed percentage for missing work, a deduction per interval for late work), separate from dates. Policies are course-scoped and do not carry over to other courses. https://canvas.ou.edu/doc/api/late_policy.html , https://teaching.resources.osu.edu/toolsets/carmencanvas/guides/carmen-gradebook/gradebook-missing-late-policies

**No grace period.** Canvas has no built-in grace setting; the "late" label cannot be turned off; the community workaround is to set Until equal to Due. Grace periods are an institutional convention. (Community answers; unverified against current Instructure docs.) https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Disable-Canvas-late-submission/td-p/141412

**In-progress at Until for quizzes: auto-submit.** Only attempts already started are auto-submitted at Until. With a time limit, the quiz submits at the timer unless Until comes first. Changing Until does not affect attempts already in progress; a student auto-submitted on the old date needs a re-attempt through Moderate. Secondary sources, described differently across institutions. https://miamioh.teamdynamix.com/TDClient/1813/Portal/KB/Article/41800/Quiz-auto-submitted-despite-extended-due-date-Canvas , https://community.canvaslms.com/docs/DOC-9959-415250754

**Course end: concluded vs hidden.** Course participation dates come from the term or are overridden at the course (or section). With "Restrict students from viewing course after course end date" off, a concluded course stays visible but all content is read-only. With it on, the course disappears from the student's Courses list. Staff extend access by overriding the course/section end date. These restrictions also apply to override start and end dates. https://kb.wisc.edu/helpdesk/76452 , https://servicedesk.uwgb.edu/TDClient/33/Portal/KB/ArticleDet?ID=1915 , https://rollins.teamdynamix.com/TDClient/1835/Portal/KB/PrintArticle?ID=137870

This is the closest reference to the open question "who still sees a hidden course": Canvas models **ended = read-only** as the default and **hidden** as a separate switch.

**Layering in Canvas.** Account/term dates, then course participation override, then section override, then per-assignment "Assign To" (everyone, section, student). Late policy sits at course only.

## 3. Open edX

**Course end is about credit, not necessarily access.** The end date is when learners "can no longer earn credit for graded problems or toward certificates"; they "can continue to complete available coursework". In self-paced courses course teams can make individual components unavailable by the end date (for example a final exam) via hide-by-date. No end date means no certificate access. Default courseware access after end for self-paced was not confirmed. https://docs.openedx.org/en/latest/educators/references/course_dates.html , https://docs.openedx.org/en/ulmo/educators/references/course_development/about_page.html

**Access expiry (Course Duration Limits).** A separate feature gives audit enrollments a personal expiration date computed from the enrolment date, bounded by a minimum and maximum duration (code defaults: 4 and 12 weeks, from a source mirror; check per release). It is controlled by `CourseDurationLimitConfig`, a stacked configuration model: the same row can be set globally, per site, per org or per course, and the most specific enabled row wins. It also records an "enabled as of" date, so a limit applies only to enrolments created after it was switched on. An expired audit learner gets an "audit expired" error. https://docs.openedx.org/projects/edx-platform/en/ulmo/references/docstrings/openedx/openedx.features.course_duration_limits.html

**How access is restored.** Mostly by upgrading to verified (a commercial route). Upgrading gives access through the course end date and does not change the end date. After the end date verified learners keep archived access while the content exists. The Open edX forum has no documented operator route to set per-learner expiry outside edX.org; the suggested path is an external tool calling the enrolment APIs. (edX support page returned 403; summary from search results.) https://support.edx.org/hc/en-us/articles/360021149373-How-can-I-get-access-after-a-course-expires , https://discuss.openedx.org/t/access-expired-for-a-course-on-the-dashboard/363

**Relative dates and extensions.** `edx-when` is the central date store (absolute or relative; start, end, due). A relative date is an offset added to content availability, the later of enrolment date and course start. Individual due date extensions (instructor dashboard "Extensions" tab) are per-user rows in the same store, so an extension is a data row, not a code branch. https://pypi.python.org/pypi/edx-when/ , https://discuss.openedx.org/t/course-relative-due-dates-and-the-direction-for-scheduling/682

**Layering in Open edX.** The stacked config pattern (global, site, org, course) for the duration-limit feature is the nearest match to the FLS site, organisation, course resolver. It has no cohort layer in that feature, and a learner-level date is a separate record.

## 4. Blackboard Learn Ultra

Late submissions are accepted and marked late by default. Two instructor switches harden it: "Prohibit new attempts after due date" (can be enabled alone) and "Prohibit late submissions" (a hard deadline; it turns on the first). With a hard deadline, **in-progress and saved attempts auto-submit at the due date** and the student gets an emailed receipt. Per-student accommodations are still honoured under a hard deadline (assignment of accommodations is not detailed in results). Note the separation: late mark (default), no new attempts, no late submission are three independent steps. https://help.blackboard.com/node/42436 , https://help.blackboard.com/node/42966

Course availability duration was not covered by results.

## 5. Course-time-limit systems (TalentLMS, LearnDash, others)

- **TalentLMS.** Course expires, access is revoked, user shows "Expired", the instructor changes the expiration date per user. Branch or course level defaults not confirmed (page 403). https://help.talentlms.com/hc/en-us/articles/360014657413-How-to-change-the-expiration-date-of-a-course-for-specific-users
- **LearnDash.** Per-user or per-group "extend access"; new date replaces the existing end date. https://learndash.com/support/kb/add-ons/users/extend-access/
- **Restore is often not a simple extension.** Oasis LMS: extension per learner is not possible once the course has expired universally; the course expiration date must be changed and the course republished. LearnWorlds: an expired learner cannot be extended and must buy again. Teachery: extending the course expiration date does not restore access for those already lapsed. These are the failure modes the "only staff restore, new window, keep progress" decision avoids. https://university.oasis-lms.com/AssetListing/Questions-from-Zendesk-10737/How-to-extend-an-expiration-date-for-a-learner-23874 , https://support.learnworlds.com/support/solutions/articles/12000041927 , https://help.teachery.co/en/articles/122-set-a-course-end-date-or-course-expiration-date-for-your-courses

## 6. Findings that bear on the open questions

1. **Layer order between course and organisation.** Open edX's stacked config orders global, site, org, course (course most specific). Moodle orders site, course, item, group/user. Canvas orders term/account, course, section, student. All put the course more specific than the organisation/site. Nobody has a cohort-level policy; the nearest are Moodle groups and Canvas sections, and both apply only to dates, not consequences. Consequences (late policy, expiry action, duration limit) stay at site/course scope; per-learner exceptions are made by changing dates, not consequences. This supports resolving course over organisation, and suggests the registration layer should hold date-like or "allow this one" exceptions rather than a full consequence set.
2. **Where "access ended" is enforced.** Canvas separates "concluded: read-only" from "hidden from the course list" with a switch; Moodle suspends the enrolment (the enrolment itself changes state); Open edX raises an access error from the access check with a distinct reason ("audit expired") and the dashboard says so. The dashboard-visible "access ended" state FLS wants matches Canvas's read-only/visible mode and Open edX's explicit error. None uses a time-driven change of `is_active`-like state silently, except Moodle's suspend action, which is run by a cron.
3. **In-progress attempt at close.** Four documented answers: auto-submit (Canvas quiz, Blackboard hard deadline, Moodle quiz default), finish-only-with-grace (Moodle "Grace period" mode), count-nothing (Moodle "Strict cutoff"), leave as draft for teacher action (Moodle assignment). Even in the auto-submit cases the system makes a decision at the moment of the deadline, which needs a sweep or on-read finalisation. A "close but leave an in-progress attempt finishable" rule is equivalent to Moodle's grace-period mode and Blackboard's separation of "no new attempts" from "no late submission".
4. **Grace window.** Moodle models it only for timed quiz attempts, as a named mode with its own length. Canvas has none (and users ask for it). Blackboard has none. A policy-level window in front of closing and ending is therefore new design, not a copy; Canvas users' complaint is the evidence it is wanted. Open question none of the systems answers: whether an override that moves a date moves the grace window with it. Moodle overrides replace the date value outright and carry no grace, and overrides do not track base-date edits (documented pain).
5. **Educator notification is its own date or setting.** Moodle's "Remind me to grade by" and "Notify before enrolment expires" (teacher, optionally student) are separate settings, not consequences of the late flag; Moodle sends them via a configured hour. Consistent with FLS keeping "notify educators" as a switch that spec 5 acts on.
6. **Restore.** Systems that restore well (Moodle reactivate with new end date, Canvas course/section end-date override, TalentLMS new expiration date) keep the enrolment row and progress and give a new end date; systems that restore badly end the record (unenrol purges data in Moodle; re-purchase in LearnWorlds). Moodle explicitly warns that unenrol purges grades. This supports "ending access does not unregister; restore opens a new window and keeps progress".
7. **Time-of-effect.** Open edX applies its limit only to enrolments created after the feature's "enabled as of" date. A policy change should say whether it affects existing registrations; Moodle and Open edX diverge here (Moodle edits apply to the live course; edX records a start date), and SuccessFactors needs an explicit "propagate" action (landscape file section d).

## Reference URLs (consolidated)

- https://docs.moodle.org/en/Assignment_settings
- https://docs.moodle.org/en/Quiz_settings
- https://docs.moodle.org/en/Assignment_overrides
- https://docs.moodle.org/en/Self_enrolment
- https://www.monash.edu/learning-teaching/teachhq/moodle/assignment/how-to/extensions-and-resubmissions
- https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211
- https://telsupport.brookes.ac.uk/articles/how-do-i-reactivate-suspended-enrolments-in-moodle/
- https://canvas.ou.edu/doc/api/late_policy.html
- https://teaching.resources.osu.edu/toolsets/carmencanvas/guides/carmen-gradebook/gradebook-missing-late-policies
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Disable-Canvas-late-submission/td-p/141412
- https://miamioh.teamdynamix.com/TDClient/1813/Portal/KB/Article/41800/Quiz-auto-submitted-despite-extended-due-date-Canvas
- https://kb.wisc.edu/helpdesk/76452
- https://servicedesk.uwgb.edu/TDClient/33/Portal/KB/ArticleDet?ID=1915
- https://docs.openedx.org/en/latest/educators/references/course_dates.html
- https://docs.openedx.org/projects/edx-platform/en/ulmo/references/docstrings/openedx/openedx.features.course_duration_limits.html
- https://support.edx.org/hc/en-us/articles/360021149373-How-can-I-get-access-after-a-course-expires
- https://pypi.python.org/pypi/edx-when/
- https://help.blackboard.com/node/42436
- https://help.blackboard.com/node/42966
- https://learndash.com/support/kb/add-ons/users/extend-access/
- https://university.oasis-lms.com/AssetListing/Questions-from-Zendesk-10737/How-to-extend-an-expiration-date-for-a-learner-23874
- https://support.learnworlds.com/support/solutions/articles/12000041927
- https://help.teachery.co/en/articles/122-set-a-course-end-date-or-course-expiration-date-for-your-courses

status: ok · reason: web research complete; gaps listed at top (Thinkific, Docebo restore, Moodle grant-extension vs cut-off, Open edX default post-end access)
