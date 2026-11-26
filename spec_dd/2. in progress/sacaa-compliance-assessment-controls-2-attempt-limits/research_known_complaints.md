# Known complaints: quiz attempt limits and waits between attempts

Evidence caveat: search turned up docs, university help pages and a few Moodle tracker items, not many first-hand forum threads. Frequency and severity below are judgement from that thin base, marked (inferred) where no source says it. No tracker item was found for double-click double-start, and none for timezone-wrong countdowns.

## Complaints, ranked

| # | Complaint | Common / severe | Mitigation seen |
|---|-----------|-----------------|-----------------|
| 1 | Attempt burned by accidental start, crash or network drop; cap now used up | Most common, high severity when the cap is small (inferred; the instructor-side fixes below exist because it recurs) | Staff-side relief: Moodle lets teachers delete an attempt from the Results report, and a college guide calls this the fix for a "rogue" attempt that used the limit. Moodle also has per-user and per-group overrides of the attempt count. Canvas instructors check the quiz log, then grant extra attempts or time. Deletion is irreversible. |
| 2 | Cap reached with no path forward | Severe, and common in practice. Every system answers it with a staff action, so learners must ask someone. | Moodle overrides, Canvas extra attempts. This spec has no staff grant (out of scope) and relies on spec 7 course restart. Say so on the locked page. |
| 3 | Instructors cannot see why a learner is locked or what was recorded | Moderate (inferred) | Canvas quiz log lets staff verify a connection problem. Open edX Staff Debug Info shows the attempt count per learner. |
| 4 | Count goes wrong after deletion or edits, so the learner sees "all attempts used" early | Rare but severe; Moodle tracker item reports this after deletions | Derive the count from completed attempt rows each time. This spec already does, and stores no counter. |
| 5 | Confusing "when does it reopen" rule | Moderate. Moodle's delay is measured from whichever is earlier: completion time plus delay, or start time plus time limit plus delay. Docs need worked examples. A 120 s delay in the docs example rejects a late submission. | Use one rule, measured from the failed attempt's `completed_time` (already settled). Show the exact time on the page. |
| 6 | Timezone and clock-skew countdowns | No sourced complaint. (inferred) A countdown driven by the browser clock drifts or is wrong where the device clock is wrong. | Send the server's remaining seconds or an absolute server time. Take the countdown from that, and re-check on click on the server (already settled). Show the time in the learner's timezone. |
| 7 | Stale or cached pages: back button or refresh shows an old state | Moderate. Moodle MDL-68970 asked for attempt pages to be uncached for this reason. | The server re-checks at click. The button turning active in place must not trust a cached page. |
| 8 | Double-click or double-submit creates two attempts | No sourced report. (inferred) Possible wherever start is not serialised. | The `CourseProgress` row lock plus reuse of an open attempt (already settled). Disable the button on submit. |
| 9 | Open or abandoned attempt blocks or counts | Canvas and Brightspace point out that a timed attempt keeps running while the learner is disconnected. Reopening or extending an auto-submitted attempt is not possible in Canvas. | Open attempts do not count, and continue is never blocked (settled). Spec 3 and spec 5 own expiry. |
| 10 | Delays applying after a pass, or retaking a passed quiz | No sourced complaint. (inferred) | Waits apply after a failure only (settled). The answers also refuse a new attempt after a pass. |
| 11 | No explanation of why Start is gone | No sourced complaint. (inferred, a standard usability issue) | Show the reason, attempts used and left, and the open time on both pages (settled). |

## Implications for the spec

- Item 1 plus item 2 are the main risk. With no staff grant, a learner who loses an attempt to a crash waits for the spec 7 restart. The spec should state this in the UI copy and in what staff can see.
- Item 3: consider showing staff the attempts used, attempts left and next-open time for a learner on the educator side. This is a gap to flag, not a decision.
- For the live countdown, use the server's remaining time as the source and make the click re-check authoritative. The server re-check on click is already settled.
- Avoid Moodle's two-rule delay formula. Item 5 shows it is a documented source of confusion.

## Sources

- https://docs.moodle.org/503/en/Quiz_configuration (delay rule, overrides, worked examples)
- https://docs.moodle.org/en/Capabilities/mod/quiz:deleteattempts (teachers can delete attempts)
- https://support.sou.edu/kb/articles/pdf/faculty-clear-student-quiz-attempt (delete is irreversible)
- https://tracker-old.moodle.org/browse/MDL-68970 (uncached attempt pages, back button)
- https://teaching.usask.ca/articles/2025-03-04-digital-exam-disruptions.php (Canvas quiz log, extra time or attempts after a disruption)
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Giving-a-student-a-second-chance-on-their-original-quiz/m-p/450491 (extra attempt vs reopen, auto-submit cannot be extended)
- https://www.vanderbilt.edu/brightspace/quiz-faqs/ (timed attempt keeps running when disconnected)
- https://docs.openedx.org/en/ulmo/educators/references/course_development/learner_problem_view.html (attempt counts, Staff Debug Info)

status: ok
