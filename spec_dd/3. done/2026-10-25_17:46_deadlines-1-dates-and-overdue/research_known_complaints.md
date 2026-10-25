# Research: known complaints about due dates and course time limits

Topic: `known_complaints`. Narrow to spec 1 (dates, time limit, overdue display; no consequences, extensions or reminders). Broad sentiment is in `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md` ("sentiment file"); it is cited by section, not repeated.

## Evidence limits

- Web search (standard mode), three rounds, summaries not full thread reads. Claims are limited to what the summaries stated.
- No Reddit (r/Professors, r/instructionaldesign) threads were reachable, same gap as the sentiment file (its "Method and evidence limits"). Not evidence of silence.
- No source found for: DST shifting a stored deadline in a core LMS (only WeBWorK-on-Moodle, sentiment file (g)); overdue badges on already-completed LMS items beyond one Canvas idea; late enrolment into a cohort with fixed dates already past (only Canvas "Until date" workarounds). Those rows below are labelled design judgement.
- "How common" is an estimate from how many independent threads/trackers were seen: High (several systems), Medium (one or two systems, repeated), Low (single report or none found).

## Complaints

### 1. Overrides do not follow a later edit of the default
- What: an educator sets a user/group override, later changes the base due date, and the overridden date stays put. Monash tells staff to review and hand-edit every override after changing the base date. Moodle overrides are also lost on backup/restore.
- How common: Medium (Moodle docs from two universities; sentiment file (b) and implication 4).
- Implication: the open question "does an override follow later edits" must be answered explicitly. Store an override as either an absolute value or an offset-from-default and show which; the admin must display "differs from default" and the current default beside the override. Adopt the sentiment file's rule: follow, or visibly flag that it no longer does.
- https://www.monash.edu/learning-teaching/teachhq/moodle/assignment/how-to/extensions-and-resubmissions ; https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211

### 2. Different screens show different dates for the same learner
- What: Moodle trackers report group/user override or extension dates missing from the dashboard timeline (only the default deadline shows), calendar and timeline disagreeing after a user override replaces an extension, and a group override date not shown when switching groups. A Canvas known issue: an "Everyone else" override left the due date unpopulated.
- How common: Medium (three Moodle tickets plus one Canvas known issue).
- Implication: one resolver feeding table of contents, course detail and dashboard card, never a per-view date calculation. Test that all three surfaces agree for each layer combination. Matches the idea's "one resolver" decision.
- https://tracker-old.moodle.org/browse/MDL-77441 ; https://tracker-old.moodle.org/browse/MDL-65116 ; https://tracker-old.moodle.org/browse/MDL-85113 ; https://community.canvaslms.com/t5/Known-Issues/OPEN-Assign-To-module-setting-causing-some-assignments-due-at/ta-p/618814

### 3. Relative dates computed from an unclear or wrong anchor
- What: Moodle enrolment-offset requests (MDL-72483, MDL-46922) ask which enrolment counts when there are several methods and whether re-enrolment restarts the clock; one request was closed "Won't Do" (MDL-61209) and the core feature is experimental. Open edX measures from the later of course start and enrolment, only for self-paced courses and graded subsections, and admins report the option not appearing (config confusion).
- How common: Medium-High (many asks, repeated across Moodle and Open edX; sentiment file (d)).
- Implication: the settled anchor (`CourseProgress.created_at`) is right but must be shown to the learner and admin ("starts from your registration on <date>"). Document what re-registration does (new `CourseProgress` row or not) since users ask exactly this. Do not make it conditional on obscure flags: always available in frontmatter.
- https://tracker-old.moodle.org/browse/MDL-72483 ; https://tracker-old.moodle.org/browse/MDL-46922 ; https://tracker-old.moodle.org/browse/MDL-61209 ; https://discuss.openedx.org/t/issue-with-the-self-paced-configration/14574 ; https://discuss.openedx.org/t/setting-relative-due-weeks-in-authoring-mfe/19158

### 4. Displayed dates differ from the authored values
- What: in Open edX, due dates shown come from a separate data model (edx-when), not the raw course content, so authors see a mismatch between what they typed and what learners see; the Dates page only showed dates under certain flags. Authors cannot tell why.
- How common: Low-Medium (a few Open edX threads).
- Implication: the admin should show the effective date and which layer produced it (see item 11). Keep resolver output reproducible from stored inputs.
- https://discuss.openedx.org/t/due-dates-in-dates-page/10659 ; https://discuss.openedx.org/t/course-relative-due-dates-and-the-direction-for-scheduling/682

### 5. Dates change or detach when content is re-published, copied or re-ordered
- What: Moodle overrides do not survive backup/restore; Canvas "Assign To" accidents wipe entries; Canvas bulk date tools changed dates but not times (sentiment file (b)). No thread found specifically on re-ordering or moving an item between collections.
- How common: Medium for copy/restore loss; Low for re-order (design judgement).
- Implication: the open question on re-import is real. The sync creates a new `ContentCollectionItem` when a child moves collection, so a placement-attached override would silently vanish. Decide: carry overrides to the new placement, or flag them as orphaned in admin. Never silently drop. Validate frontmatter on load and report changes to dates.

### 6. Group or cohort override conflicts and "most permissive" surprises
- What: Moodle users report confusion when group and user overrides coexist (user override replaces extension; which wins is learned by trial). Canvas: multiple "Assign To" entries mean the student sees the most favourable, and educators are surprised when removing "Everyone" strips the others.
- How common: Medium (Moodle tickets, Canvas guides; sentiment file (b)).
- Implication: "most permissive wins within a layer" is defensible but must be explained in the admin and visible per learner. Show the contributing deadlines and the winner. Layer precedence (learner > cohort registration > content) must appear as help text on the override models.
- https://tracker-old.moodle.org/browse/MDL-85113 ; https://support.csuchico.edu/TDClient/1984/Portal/KB/PrintArticle?ID=113756

### 7. "23:59" versus "00:00" and the missing-second problem
- What: Canvas default 11:59 pm: instructors say a submission one second after is late, prefer midnight but use 11:59 because students read 12:00 am as the next day. Parents of school students complained about midnight due times; Murray State moved its default to 5 pm.
- How common: High (many Canvas threads; sentiment file (g)).
- Implication: store a due moment, and display the end-of-day default as a date plus "end of day, <zone>", not as "23:59". The comparison for overdue must be "past the instant", exclusive, defined once and tested at the boundary. Consider letting authors set a time of day; at minimum do not hardcode the 23:59 string in templates.
- https://community.canvaslms.com/t5/Canvas-Question-Forum/Assignment-submitted-on-due-date-time-marked-as-late/m-p/511838 ; https://community.canvaslms.com/t5/Canvas-Ideas/Set-Assignment-Default-Due-Time/idc-p/365289 ; https://community.canvaslms.com/t5/Question-Forum/Assignment-due-times/m-p/459441 ; https://murraystatenews.org/?p=201706

### 8. Time zones: unlabelled times and "off by a day" for remote learners
- What: a Canvas user set 11:59 pm in their zone; East Coast students saw 12:59 am the next day and thought it a mistake. Moodle shows times in the user's zone without naming it; global users read them as UTC. DST shifted deadlines by an hour in WeBWorK on Moodle.
- How common: High (sentiment file (g) plus the Canvas thread).
- Implication: confirms the settled rule: site time zone, name the zone on every shown date. Add: a date-only display of an end-of-day deadline can be a different calendar day in the learner's own zone, so show the weekday and zone. Compute offsets (days after start) in the site zone, not UTC, and test across a DST change (a "30 days" offset must still land on end of a local day, not 23:00 or 01:00).
- https://community.canvaslms.com/t5/Question-Forum/Setting-Due-date-and-time-12-00-AM-in-Canvas-Calendar/m-p/192879 ; https://moodle.org/mod/forum/discuss.php?d=407277 ; https://webwork.maa.org/moodle/mod/forum/discuss.php?d=3421

### 9. Overdue marks on items that are already done or not required
- What: Canvas idea: a paper-submitted assignment stays marked overdue after it is scored, and Modules show "No submission". Educators ask that overdue clear once complete, like "missing".
- How common: Low-Medium (one idea thread; the pattern is a known bug class). Not-required case: none found, design judgement.
- Implication: the settled rule "a completed item is never overdue" needs a precise definition of complete (placement-level progress completed) and a test that completing an item removes the mark on all three surfaces. If a placement's course content has optional items, a due date on an optional item still shows overdue; decide whether optional items can carry a due date or are exempt.
- https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Student-Submitting-on-Paper-to-an-Online-Assignment/m-p/544984

### 10. Overdue noise on dashboards and the hidden-date problem
- What: Canvas hid due dates in the Assign To panel after a redesign; students and staff ask that the date always be visible. Educators and learners complain of notification fatigue (reminders are a later spec, but the same fatigue arises from many red marks). Moodle's timeline block listing only default deadlines is the opposite problem.
- How common: Medium (Canvas ideas; Edinburgh and Sussex fatigue posts in sentiment file (e)).
- Implication: dashboard card: one summary ("3 items overdue", nearest due date), not a mark per item. A course with many overdue items must not flood the card. Always show the date (and its zone) next to the mark, never "overdue" alone.
- https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Date-should-always-be-visible-on-assignments-to/idc-p/498972 ; https://community.canvaslms.com/t5/Canvas-Question-Forum/Assign-to-panel-in-Assignments-now-hides-due-dates-and/m-p/609501

### 11. Admins cannot tell which layer set a date, or who and why
- What: Moodle overrides carry no reason or actor; staff only see a date. Canvas known issues involve dates appearing or vanishing from override interplay. UTS needs manual status resets because the cause is invisible. Sentiment file (b) and implication 4.
- How common: Medium (inferred from multiple tracker and help-doc workarounds; no single thread titled this).
- Implication: the resolver should return the winning layer with the date, and the Django admin should surface it (a read-only "effective due date and source" on the learner and cohort registration pages). The open question on actor and reason: record who and why on every override now, since specs 3 and 6 depend on it.

### 12. Late enrolment into a cohort with fixed dates already past
- What: Canvas late-enrolment guidance (Seattle Central) is workarounds by hand: a start module, per-section Until dates; auto "missing" scoring hits late joiners (USU). No thread complained of an overdue badge itself; design judgement, since this is the natural result of fixed dates plus late registration.
- How common: Low as a stated complaint; High as a real situation in cohort programmes.
- Implication: a learner registered after a fixed item date sees it overdue from day one. Spec must state this is accepted for display, and that the learner override (admin) is the cure. Consider whether the display for a fixed date earlier than the learner's registration should read as "was due <date>" rather than a failure state. Offsets (relative dates) avoid the problem; steer authors to them in the `fls-content` plugin guidance.
- https://seattlecentral.edu/employees/elearning/continuity-planning/strategies-late-enrollment-students ; https://www.usu.edu/teach/help-topics/canvas/automatically-score-missing-assignments

### 13. Course time limit versus item due dates disagree
- What: LearnDash group end dates cap individual course extensions; Open edX shifts suggested dates but not past course end (sentiment file (b)). Users are surprised when an item date falls after the course limit or the reverse.
- How common: Low-Medium.
- Implication: validate on load and at override: an item due date later than the course time limit end (for the same learner) is shown as such, or flagged at content load when both are offsets. Say in the UI which is the binding date.
- https://learndash.com/support/kb/add-ons/users/extend-access/

### 14. Partial or experimental implementations of relative dates
- What: Moodle relative dates are assignment-only, weekly format only, experimental; Open edX works only for graded subsections of self-paced courses.
- How common: Medium-High (sentiment file (d)).
- Implication: relative offsets must work for every item type and every course shape FLS has, else the feature is judged by its gaps. Include test coverage across the content types in `content_base`.

## Priority for the spec

1. Boundary and zone rules (7, 8): decide once, label everywhere.
2. Override semantics and visibility (1, 6, 11): follow-or-flag, show winning layer, record actor and reason.
3. One resolver for every surface (2).
4. Re-import behaviour for moved placements (5).
5. Complete means never overdue; dashboard shows a summary (9, 10).
6. State late-registration and limit-versus-item behaviour (12, 13).

## References

- Sentiment file (parent): `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md`
- https://www.monash.edu/learning-teaching/teachhq/moodle/assignment/how-to/extensions-and-resubmissions
- https://royalroads.atlassian.net/wiki/spaces/ITKNOW/pages/5839211
- https://tracker-old.moodle.org/browse/MDL-77441 , MDL-65116 , MDL-85113 , MDL-72483 , MDL-46922 , MDL-61209 (all under https://tracker-old.moodle.org/browse/)
- https://discuss.openedx.org/t/issue-with-the-self-paced-configration/14574
- https://discuss.openedx.org/t/setting-relative-due-weeks-in-authoring-mfe/19158
- https://discuss.openedx.org/t/due-dates-in-dates-page/10659
- https://discuss.openedx.org/t/course-relative-due-dates-and-the-direction-for-scheduling/682
- https://community.canvaslms.com/t5/Canvas-Question-Forum/Assignment-submitted-on-due-date-time-marked-as-late/m-p/511838
- https://community.canvaslms.com/t5/Canvas-Ideas/Set-Assignment-Default-Due-Time/idc-p/365289
- https://community.canvaslms.com/t5/Question-Forum/Assignment-due-times/m-p/459441
- https://community.canvaslms.com/t5/Question-Forum/Setting-Due-date-and-time-12-00-AM-in-Canvas-Calendar/m-p/192879
- https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Date-should-always-be-visible-on-assignments-to/idc-p/498972
- https://community.canvaslms.com/t5/Canvas-Question-Forum/Assign-to-panel-in-Assignments-now-hides-due-dates-and/m-p/609501
- https://community.canvaslms.com/t5/Canvas-Ideas/Assignments-Student-Submitting-on-Paper-to-an-Online-Assignment/m-p/544984
- https://community.canvaslms.com/t5/Known-Issues/OPEN-Assign-To-module-setting-causing-some-assignments-due-at/ta-p/618814
- https://support.csuchico.edu/TDClient/1984/Portal/KB/PrintArticle?ID=113756
- https://murraystatenews.org/?p=201706
- https://moodle.org/mod/forum/discuss.php?d=407277
- https://webwork.maa.org/moodle/mod/forum/discuss.php?d=3421
- https://seattlecentral.edu/employees/elearning/continuity-planning/strategies-late-enrollment-students
- https://www.usu.edu/teach/help-topics/canvas/automatically-score-missing-assignments
- https://learndash.com/support/kb/add-ons/users/extend-access/

status: ok · reason: complaints gathered from Moodle, Canvas, Open edX, LearnDash sources; no Reddit reachable; DST, completed-item and late-enrolment rows rest partly on design judgement
