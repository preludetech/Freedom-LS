# Research: known complaints about educator reporting in LMSs

Scope: dashboards, at-risk flags, cohort reports (screen and PDF), learner drill-downs, roster CSV exports. Evidence came from a handful of web searches (snippets, not full thread reads), so treat it as indicative. Where a category had no direct evidence, that is stated.

## Findings

### 1. Slow or timing-out reports at scale
- Moodle completion report CSV/Excel export times out for courses with a few thousand users. The reporter traced it to over 250k SQL queries in one request, growing with users times completion criteria (an N+1 shape). Unresolved. https://tracker-old.moodle.org/browse/MDL-77116
- Moodle log reports time out on large courses; raising proxy timeouts and earlier patches did not help. https://tracker-old.moodle.org/browse/MDL-69276
- Moodle gradebook hitting PHP max execution time with 3,000+ students (forum, Moodle 2.8.5). https://moodle.org/mod/forum/discuss.php?d=357534 (listed in search results; thread title not confirmed)
- Open edX grade reports are asynchronous and can take seconds to hours depending on course size and grading config. Users are told not to click the button repeatedly because that slows things further. https://docs.openedx.org/en/ulmo/educators/how-tos/data/view_learner_grades.html

### 2. Stale numbers and unclear freshness
- Canvas New Analytics refreshes about every 24 hours; Course Activity data may lag longer. Community answers reported delays of 40 to 48 hours. https://community.canvaslms.com/t5/Canvas-Question-Forum/New-Analytics-is-different-than-gradebook/td-p/490860
- University of Wisconsin-Madison KB (updated Aug 2025) documents severe data lag and incomplete data in Canvas Course Analytics and tells instructors not to rely on it. https://kb.wisc.edu/luwmad/page.php?id=144516
- Open edX grade reports are a snapshot at generation time. Users must regenerate to see later changes. https://docs.openedx.org/en/ulmo/educators/how-tos/data/view_learner_grades.html
- Open edX download links expire within about 5 minutes, which looks like a failed download. Same source and https://public.docs.edunext.co/en/latest/external/course_instructors/running_courses/data-download.html

### 3. Numbers that disagree between screens
- Canvas: Analytics versus Gradebook mismatches are a recurring forum question. Causes: refresh lag, ungraded or unposted work, "Current Score" (only work the student took part in) versus "Final Score" (all work). https://community.canvaslms.com/t5/Canvas-Question-Forum/New-Analytics-course-average-is-wrong/m-p/514558 , https://community.canvaslms.com/t5/Question-Forum/Analytics-mismatch-with-Gradebook/td-p/435610 , https://boisestate.atlassian.net/wiki/spaces/LTS/pages/1880031251/Understanding+and+Avoiding+Canvas+Score+Discrepancies , https://blogs.chapman.edu/academics/?p=4465
- Lesson: institutions have to write guides explaining the gap. The gap is a definition problem as much as a freshness problem.

### 4. At-risk flags: confusing, false positives
- Direct complaint evidence was not found. Searches returned vendor marketing and research papers with no false-positive data or instructor feedback. https://openeducat.org/de/ai/features/learning-analytics/ , https://www.mdpi.com/2504-2289/5/4/71
- One tangential signal: a vendor sheet shows "percent at-risk students" as an instructor KPI, which suggests flags can be turned against instructors. https://community.canvaslms.com:443/xjnht99997/attachments/xjnht99997/briefs/11/7/Instructor%20Insight%20-%20Overview.pdf
- Treat the false-positive risk as an inference from the flag rules (inactive for a week misfires on holidays, self-paced learners, or content done offline), not a sourced complaint. Needs a follow-up search of early-alert literature if the spec wants evidence.

### 5. Too many metrics
- No supporting evidence found. G2-style reviews complain of too little depth, not too many metrics. This idea's small fixed set of flags is consistent with that.

### 6. Exports: encoding and missing columns
- Excel garbles non-Latin text in UTF-8 CSVs with no BOM. Canvas users have a feature request for UTF-8 with BOM, status "New", and Canvas advises the Excel Data > From Text import. https://community.canvaslms.com/t5/Canvas-Ideas/Files-UTF-8-with-BOM-as-default-encoding-when-downloading-CSV/idi-p/584159
- Same problem in other products, with the BOM as the standard fix. https://meta.discourse.org/t/exported-csv-files-have-garbled-characters/277293 , https://support.atlassian.com/jira/kb/csv-files-exported-from-search-results-are-garbled-when-open-by-excel/ , https://learningbox.online/en/2021/06/18/blog_csv-bom-utf8
- Missing-column complaints: not found directly. G2 reviews cite limited customization of reports (below).

### 7. Reports limited to admins, locked behind tiers
- Absorb LMS G2 reviews: admin and manager reporting is restricted and not very customizable; extended reporting needed a paid package that was not made clear up front. https://www.g2.com/survey_responses/absorb-lms-review-8769511 , https://www.g2.com/survey_responses/absorb-lms-review-9098139
- Litmos (limited reporting) https://ai.g2.com/product/litmos ; TalentLMS and Tovuti (shallow for power users, manual work) https://www.rfp.wiki/vendors/tovuti-lms/talentlms
- Open edX restricts Data Download to staff who also hold the Course Data Researcher role. This can leave instructors unable to get their own data. https://appsembler.com/docs/student-information-open-edx/ (search result; claim from the summary, not verified on the page)

### 8. Lack of drill-down
- Not directly evidenced beyond the G2 "basic metrics, wish for clearer insights" comments on Absorb. The Moodle and Canvas mismatches in 3 are made worse by having no path from a number to the rows behind it.

### 9. Permission leaks across classes or groups
- Moodle: teachers in "separate groups" still saw other groups' grades and posts because they held "Access all groups". Removing the capability did not close every report; the Grades admin page still showed other groups. https://moodle.org/mod/forum/discuss.php?d=75421 , https://moodle.org/mod/forum/discuss.php?d=126018 , https://docs.moodle.org/402/en/Groups_overview
- Lesson: scoping applied per view leaks; each report, export and aggregate must be tested as the restricted role.

## What this idea should guard against

1. Per-learner query explosions. Moodle's 250k-query export is the cautionary case. Measure the gather's query count and time at 30/100/300 learners (already in Discovery) and keep the dashboard on cheap aggregates.
2. Silent truncation. `REPORTS_MAX_LEARNERS` must be visibly stated on screen, in the PDF and in any export, not just applied.
3. No "as of" time. Every on-screen report, tile and cached figure should show when it was gathered, and PDF generation should show its state ("a report is being generated"). Avoid the Canvas 24 to 48 hour lag with no indicator.
4. Two definitions of the same number. Keep one status definition in `reports` and one source for dashboard tiles, lists, badges and the PDF. If the dashboard uses aggregates while the report uses the gather, test that they agree on the same seeded data, and define "average progress" and "needing attention" in the UI (the Canvas Current/Final score confusion).
5. Opaque at-risk flags. Show why a learner is flagged (no activity, failed latest quiz, inactive N days) and the data behind it, link to the learner drill-down, and keep the flag set small. Consider the false-positive risk of "inactive for a week" for self-paced learners; no sourced evidence, so decide deliberately.
6. Excel-hostile CSV. Roster export should be UTF-8 with BOM (or documented), with stable named columns, and tested with non-ASCII names. Guard against CSV formula injection in names, a standard risk not covered by the sources.
7. Admin-only reporting. Cohort admins and viewers must reach dashboards, report generation and roster export for their cohorts without admin access.
8. Permission leaks. The organisation dashboard aggregates, needs-attention lists, tile counts, PDF downloads and CSV exports must each be scoped to the viewer's cohorts. Test each surface as a cohort viewer assigned to one of two cohorts, including counts and the quick view. Moodle's partial fix shows that checking one view is not enough.
9. Expiring or confusing downloads. A generated report should stay downloadable from the cohort page, and failures should be explained. Open edX's 5-minute links are the anti-pattern.
10. Repeated-click pile-ups. The one-in-flight-per-cohort rule should disable the generate button, not only reject the request.
11. No path from number to rows. Every tile and list item should link to a filtered list or the learner drill-down.

status: ok
