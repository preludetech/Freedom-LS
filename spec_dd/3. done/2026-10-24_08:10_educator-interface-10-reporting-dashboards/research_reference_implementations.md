# Research: reference implementations of educator reporting

Topic `reference_implementations`. Question: how do other LMSs solve organisation/class/learner reporting, async downloads, at-risk flags and roster exports?

Method: a handful of web searches (standard mode) on 2026-10-22. Findings are limited to what the search summaries and docs snippets stated. Gaps are flagged as such rather than filled from memory. Terms below are the other systems' own (Moodle "course", Open edX "learner", etc.), not FLS vocabulary.

## Per system

### Moodle
- Levels: course-centred. Separate course reports for Course completion, Activity completion, Course participation, Activity report (view count and last access per activity) and Logs. No organisation-level dashboard in core.
  - https://docs.moodle.org/503/en/Course_completion_report
  - https://warwick.ac.uk/services/its/servicessupport/academictechnology/support/guides/moodle-guides/course-participation
  - https://www.simpson.edu/app/uploads/2024/11/Moodle-Reports.docx
- Live vs precomputed: the course reports are on-request views over completion and log tables. Logs are retained for a limited time (one institution says 120 days), and logs show page views, not reading.
  - https://royalroads.atlassian.net/wiki/x/xBFZ
- At-risk: the core Analytics model "Students at risk of dropping out" (since 3.4). Target: enrolled students with no activity in the final quarter of the course. Indicators follow the Community of Inquiry model (cognitive, social, teacher presence). It needs accurate course start and end dates, and it works best for online or blended courses. It is a predictive model run by scheduled tasks, not a live rule.
  - https://docs.moodle.org/en/Students_at_risk_of_dropping_out
  - https://docs.moodle.org/401/en/Using_analytics
- Exports: the Course completion report only exists when completion is enabled. Recent versions (5.3 per the docs page, marked work in progress) add the standard download widget (CSV, Excel, PDF), and the export reflects the current filtered view. The Participation report can message the users who have not engaged.
  - https://docs.moodle.org/503/en/Course_completion_report
- Not found: the activity completion report's refresh behaviour.

### Canvas (New Analytics)
- Levels: course analytics (course activity, grades) and an individual student view for grade and participation. Instructors can message students by grade or participation criteria. I did not find confirmation of the "student context card" in these results.
  - https://itsupport.ou.edu/TDClient/34/OKC/KB/Article/2928/Canvas-New-Analytics?SIDs=2625
  - https://nus.atlassian.net/wiki/spaces/canvasinstructor/pages/34865801
- Live vs precomputed: precomputed. Several institutions state a roughly 24 hour refresh. Report data may be delayed by 24 hours and Course Activity Report data by 40 hours. Recent submissions may not show, so users are told to check when the data was last updated. Only active and completed enrolments are included. Nothing shows for unpublished courses.
  - https://help.ohio.edu/TDClient/30/Portal/KB/ArticleDet?ID=1068
  - https://blogs.ubc.ca/sauderteachingplaybook/?p=290
- At-risk: no single flag. The educator filters on grade or participation criteria and messages that group.

### Open edX
- Levels: the per-course Instructor Dashboard, with a Data Download tab. Organisation-wide analytics are separate (Insights, not covered by these searches).
- Async downloads: "Generate Grade Report" starts a background job. The educator can navigate away. A Pending Tasks section lists the active tasks. When done, a linked CSV appears, newest first. Run time depends on grading complexity and learner count (seconds to hours). Community advice is not to click the button repeatedly. The report includes learners who are no longer enrolled, which makes it sensitive personal data. Access is restricted to a Course Data Researcher role (since Juniper).
  - https://docs.openedx.org/en/ulmo/educators/how-tos/data/view_learner_grades.html
  - https://public.docs.edunext.co/en/latest/external/course_instructors/running_courses/data-download.html
  - https://docs.openedx.org/en/open-release-sumac.master/educators/how-tos/data/manage_course_grades.html
- At-risk: nothing built in per these results.

### Google Classroom
- Levels: class, then student, with a Grades tab. Only partial findings: the official SIS export (Oct 2024) can include missing and excused grades, and it needs an admin-set-up SIS connection and a paid licence. A third-party guide says there is a "Download grades as CSV" option on the Grades tab (unverified against Google's help centre).
  - https://workspaceupdates.googleblog.com/2024/10/google-classroom-exporting-missing-and-excused-grades-to-sis.html
  - https://thebricks.com/resources/guide-how-to-export-google-classroom-grades-to-google-sheets
- At-risk: "missing" work is the signal, and it is shown per student. I found no official page confirming how it is shown.

### TalentLMS and Docebo
- TalentLMS: course reports export to Excel and can be scheduled to be sent by the arrow next to "Export in Excel". Release notes show recurring bugs with blank or missing-data CSV exports, which is a warning about silent failure.
  - https://help.talentlms.com/hc/en-us/articles/9652213844892-How-to-export-course-reports
  - https://help.talentlms.com/hc/en-us/articles/14391533370268-Release-Notes-June-2024
- Docebo: found nothing official on async export notification or an at-risk flag. Third-party connector pages describe at-risk rules built outside Docebo (time-window rules on enrolment and completion). Treat these as marketing.
  - https://tray.ai/connectors/docebo-integrations.md

## Cross-cutting patterns
1. Educator reports are course-centred. Organisation-wide views are rare and usually precomputed.
2. Precomputed analytics carry a visible freshness caveat (Canvas about 24 hours). Live views are used for the small operational lists.
3. Async downloads follow one pattern (Open edX): trigger, pending list, finished file link, with a warning against re-triggering. A pending list on the page itself is the norm, not email.
4. At-risk is either a predictive model (Moodle, heavy, needs course dates) or a simple educator-filtered criterion (Canvas grade/participation, Classroom missing work). No reference I found uses a fixed three-rule flag like the FLS report's.
5. Exports are a "what you see" download (Moodle respects the filters). Open edX warns that exports contain personal data of ex-learners.

## Borrow
- Open edX's trigger, pending state and a file link on the same page. This matches the idea's "a report is being generated" for the one-in-flight rule.
- Canvas's honesty about freshness: if the spec ends up using a cached or last-generated gather, show "as of <time>" on the cohort tab.
- Moodle's "message the people who haven't engaged" is the useful follow-up from an attention list. Messaging is out of scope here, but the attention list should link to the learner so a future link is cheap.
- Moodle's rule that the export reflects the current filtered view. For the roster, decide explicitly whether it is the whole roster or the filtered one, and label it.
- Role-gated downloads (Open edX's Data Researcher role). FLS's `can_view_cohort` gate plus the spec 5 matrix does this. Note that the roster is personal data and who may export it should be decided in spec 5 terms.
- Simple, transparent at-risk rules (the report's three flags) beat Moodle's model for a small system, and the definition is explainable to the educator.

## Avoid
- A predictive at-risk model, or anything that needs course dates FLS does not hold.
- A 24 hour stale organisation dashboard when FLS sizes may allow live aggregates. Decide after the measurement the idea requires.
- Silent blank exports (TalentLMS bugs). An empty or failed generation must say so, and the roster must never produce a header-only file without telling the user.
- Many separate course reports with overlapping content (Moodle). The idea's single cohort report with sections is the better shape.
- Exporting ex-members without saying so (Open edX). The roster should state what it includes (learners plus organisation members holding a role).
- Hammering the generate button. The one-in-flight rule needs a disabled state, not only an error.

## Caveats
- Search-summary sourced and shallow. Insights (Open edX), Docebo and Classroom detail were not confirmed from primary docs. Verify before quoting in the spec.

status: ok
