# Research: known complaints about due dates on shared content and layered overrides

Scope: Canvas (Blueprint, assign-to overrides), Open edX (reruns, shifts). Moodle and Reddit were not searched; the gap is noted at the end. Findings are from search summaries and I did not open every page. Treat anecdotes as indicative.

## Complaints and what the idea should do

| # | Complaint (source system) | Do / avoid in this idea |
|---|---|---|
| 1 | A sync from the shared source overwrites dates set locally (Canvas Blueprint: locked items are overwritten on sync). | Keep the placement value as content, below staff overrides. A load must never touch staff override rows. |
| 2 | A sync wipes locally set dates to blank because the source has none (Canvas Ideas "syncs should not override set dates with nulls"). | The idea's "removing a key removes the value" rule is right for content defaults, but it must only clear the placement value, never a staff override. State it in the spec and test it. |
| 3 | A local edit freezes the item against later source changes, so later source updates silently stop arriving (Wharton; Canvas Ideas on locked assignments). | Staff overrides already sit above content. The admin must show "Default has changed" so a moved placement value is visible rather than silently ignored. The idea covers this; keep it. |
| 4 | Sync errors when a local date change collides with a source change (Canvas "due dates changes exception"). | Precedence is layered, not merged, so there is no conflict state. Avoid any design that needs a merge. |
| 5 | The user cannot tell which date applies. Canvas shows only one date for a student in several sections. The API reports the last override. Individual beats "Everyone" with little explanation (Canvas threads). | The admin "Content default" column must name the layer the value came from: placement or child file. Consider showing the effective value and its source in one place. |
| 6 | Reruns and copies reset or keep dates unpredictably. Open edX reruns reset the start date to 2030 and leave other dates for hand editing. Contributors ask for better date handling than "remove". | The sync is deterministic. Every load rewrites the placement values from `course.md`. A removed key means no value. Say this in the author plugin wording. |
| 7 | Re-entering overrides per cohort or per section for every item of a reused part (the product owner's problem, and the Canvas multi-section chores). | This is the idea's core. Per-item values on the course-to-part placement avoid per-cohort repetition. The shorthand for "every item" removes per-item repetition for the common case. Recommend allowing it. |
| 8 | Dates set at the shared source leak into every reuse (Sinclair: blueprint course dates overwrite the teaching shells). | Keep the child file as a default for single placement. Warn authors in the plugin docs that a date in a shared part's item file applies in every course that places it unless the placement overrides it. |
| 9 | Inherited dates display wrongly (Canvas known issue: items inheriting module assign-to dates show the wrong date). | One resolver is the only reader, used by the learner view, the admin and the overdue logic. No second place computes a date. |
| 10 | Silent failures when a path names nothing. | Fail the load on an unknown item path, as the idea says. Name the course, part and path in the error. |

## Implications for the open questions

- Storage: the resolver must fetch the placement values in a fixed number of queries. A JSON column on the course-to-part `ContentCollectionItem` is the cheapest read. A row per (course, item) is easier to query and show in the admin. Either way the complaints above only require that it is rewritten on every load and shown with its source.
- `overrides`: retire it or reuse it. Whichever is chosen, the due fields must not be a key inside a free-form dict, because a free-form dict is where unseen precedence confusion starts (complaint 5).
- Stale placement values after a part is edited: a named path that no longer exists should fail the load (complaint 10), not be kept silently. Pruning old placements is out of scope, so the spec should say how a removed placement's values are dealt with.

## Gaps

No Moodle tracker or Reddit r/Professors threads were searched. Canvas evidence is mostly institutional guides and forum posts, with no official Instructure statement found.

## References

- Montana State Blueprint guide: https://www.montana.edu/ecat/help/instructors/blueprint/blueprint-management-guide/
- Wharton, section edits stop receiving blueprint date changes: https://support.wharton.upenn.edu/help/pdfexport/id/64e62b575c8d3376c91db450
- Canvas Community, Blueprint sync issue with Quizzes: https://community.canvaslms.com/t5/Canvas-Question-Forum/Blueprint-sync-issue-with-Quizzes/td-p/486504
- Canvas Ideas, locked assignments: https://community.canvaslms.com/t5/Canvas-Ideas/Blueprint-Allow-Locked-Assignments-to-be-Deleted-in-Associate/idi-p/300101
- Canvas Ideas, syncs overriding dates with nulls: https://community.canvaslms.com/t5/Idea-Conversations/Blueprint-syncs-should-not-override-set-dates-with-nulls/m-p/509078
- Sinclair, blueprint course dates overwrite shells: https://www.sinclair.edu/academics/divisions/elearning-division/elearn-canvas-migration/lms-migration-communications/may-13-2026-attention-course-coordinators-do-not-add-course-start-or-end-dates-in-canvas-blueprints/
- Canvas, multiple section due dates: https://community.canvaslms.com/t5/Question-Forum/Multiple-due-dates-for-a-single-assignment-via-Student-in/m-p/408739
- Canvas, assigning different due dates to multiple sections: https://community.canvaslms.com/t5/Canvas-Question-Forum/Assigning-different-due-dates-to-multiple-sections/m-p/612985
- Canvas Known Issue, inherited module dates: https://community.canvaslms.com/t5/Known-Issues/Items-inheriting-module-assign-to-dates-do-not-display-the/ta-p/614426
- Miami University, individual overrides beat Everyone: https://miamioh.teamdynamix.com/TDClient/1813/Portal/KB/PrintArticle?ID=45561
- Open edX rerun docs: https://docs.openedx.org/en/ulmo/educators/how-tos/rerun_course.html
- Open edX discuss, relative due dates: https://discuss.openedx.org/t/course-start-and-end-relative-due-dates/16718
- Open edX course shifts proposal: https://openedx.atlassian.net/wiki/spaces/AC/pages/415662305/Course+shifts+feature+proposal+and+discussion

status: ok
