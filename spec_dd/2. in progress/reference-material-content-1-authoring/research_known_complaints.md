# Research: known complaints about reference, resource and optional material in LMSs

Scope: what course authors and learners complain about, and what the Reference material authoring spec (`reference:` key, `CourseReferencePart`, `content_save` reconcile and cleanup, validation) should guard against. Facts only. Evidence comes from search result summaries and snippets. Pages were not opened in full, so wording is paraphrased and treated as indicative. Gaps are listed at the end.

## 1. Optional content counted toward completion or progress

Facts:
- Moodle's Completion Progress block includes every activity or resource that has completion tracking on. Items set to "Do not indicate activity completion" are left out. JAMK guidance describes that setting as suited to non-compulsory items. Instructors who pick "selected activities" must add each new item to the bar by hand.
  - https://docs.moodle.org/34/en/Completion_Progress_block
  - https://help.jamk.fi/moodle/?p=789
- RWTH Aachen's Moodle help gives the percentage as completed activities divided by total activities in the bar. Any included optional item that is unfinished lowers the percentage.
  - https://help.itc.rwth-aachen.de/en/service/8d9eb2f36eea4fcaa9abd0e1ca008b22/article/be17b9aa49964a4cb131dd741d709961/
- Articulate Rise authors report that the progress meter counts every lesson, optional ones included. The workaround of lowering the course-completion percentage lets a learner finish through unimportant lessons and skip the content that matters. Authors cannot choose which lessons make up that percentage.
  - https://community.articulate.com/discussions/rise-360/exclude-lesson-from-progress-bar
  - https://community.articulate.com/discussions/discuss/optional-course-in-lms/658653
  - https://community.articulate.com/discussions/rise-360/setting-lessons-as-mandatory-and-optional-within-a-course
- A Docebo admin reported learners who finished the SCORM package but not an optional survey. Reports showed them as completed while course progress stayed at 50%.
  - https://community.docebo.com/product-q-a-7/course-progress-doesn-t-reflect-100-completion-7387

Guard against: a reference part must never contribute to `progress_percentage`, completion or gating. The model keeps it out of `Course.items`. The cleanup of the old collection item is the point where this can silently fail. A part moved from `children:` to `reference:` that keeps its row in `Course.items` is the same complaint.

## 2. Progress bars confusing for learners and authors

Facts:
- Canvas has no native percentage-complete. Items without module requirements do not count toward progress. Students see status icons only.
  - https://community.instructure.com/en/discussion/658717/progress-indicator-for-work-completed
  - https://community.canvaslms.com/t5/Canvas-Ideas/Modules-Progress-bar-Improvements-Detailed-information-per/idi-p/618385
- Canvas modules with no requirements were labelled "Completed" for every user. This was a misleading label, documented as a bug and reported resolved on 7/26/25.
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/progress-indicator-for-work-completed/m-p/659329
- Canvas module progress is not recalculated after a module is re-locked (Known Issue). One Chico State guide says saving a module clears stored progress for all students in it.
  - https://community.canvaslms.com/t5/Known-Issues/Re-locking-module-progress-doesn-t-re-calculate-progress/ta-p/639329
  - https://support.csuchico.edu/TDClient/1984/Portal/KB/ArticleDet?ID=113557
- RWTH Aachen notes that instructors may be unable to choose what the bar contains. JAMK notes that students mark resources completed without opening them, or forget to mark them.

Guard against: a reference part should have no completion state of its own. This spec only stores the data, but it should state that reference viewing writes nothing, as the idea does, so the sibling learner spec has no state to mislead with. An "optional" flag on an item in the path is the pattern behind most of these complaints. The separate-list design avoids it.

## 3. Resources hard to find

Facts:
- Canvas's Student Modules early-adopter findings and community threads show students struggling with module navigation and with what is locked or complete. This is the closest direct evidence found.
  - https://community.canvaslms.com/t5/The-Product-Blog/Improving-the-Student-Experience-Key-Findings-from-the-Student/bc-p/661895
- Moodle docs describe activities in sections that no longer exist as "orphaned activities". They sit in a separate area and are easy to lose.
  - https://docs.moodle.org/en/Course_restore
  - https://help.mlc-wels.edu/books/moodle-for-faculty/page/fixing-orphaned-content/export/markdown

Guard against: reference material that is stored but not listed by any `reference:` entry is unreachable. That is the "orphaned" case. The idea settles that there is no auto-discovery and that `reference/` is ignored as learning-path content. So a part dropped into `reference/` but not listed will not appear anywhere. Validation or save output should say which parts were not picked up. This is a candidate rule, not a settled one. No direct forum evidence was found on "can't find the reference section" for the other named LMSs, so the learner-visibility part belongs to spec 2.

## 4. Duplicated content when shared between courses

Facts:
- Open edX library-linked blocks: re-importing a course changed the library_content source version and child blocks disappeared. Reloading at the library version restored defaults and wiped the course's local edits. Duplication and export/import of such blocks have a documented list of bugs.
  - https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804
  - https://openedx.atlassian.net/wiki/spaces/COMM/pages/3858661405/Bugs+from+Content+Libraries+V1
- Moodle's restore into an existing course can be a merge or a delete-and-restore. The defaults are admin-configurable and can be locked, so behaviour differs per site.
  - https://docs.moodle.org/en/Course_restore
  - https://docs.moodle.org/501/en/Restore
- Not found: a forum thread that directly complains about copies drifting apart when the same resource is copied into several courses. This is commonly known, but it was not confirmed by a source here.

Guard against: sharing by `../` path means one `CoursePart` row referenced by several courses, so there is a single source. The idea's note that cleanup applies only to the listing course and that another course keeps its own placement matches the cross-course interference risk. Tests should cover two courses sharing one part, with only one moving it to `reference:`.

## 5. Imports leaving stale or orphaned items

Facts:
- Open edX: a 2U spec memo for API-based course management proposes that updates either be rejected with a list of the blocks that would be orphaned, or delete them automatically. It is a design proposal, not confirmed behaviour.
  - https://openedx.atlassian.net/wiki/spaces/COMM/pages/3696066564/Spec+Memo+API-Based+Management+of+edX+Course+Blocks+Outlines+and+Settings+MVP
- Open edX `cms import` over an existing course updates the existing course in place.
  - https://discuss.openedx.org/t/how-to-overwrite-existing-course-content-using-manage-py-cms-import/743
- Moodle: when the target has fewer sections than the source, extra activities become "orphaned activities".
  - https://docs.moodle.org/en/Course_restore

Guard against: the idea records that the loader never deletes collection items. That is the stale-row case in this system. The spec covers it for parts listed under `reference:`, and for `CourseReferencePart` rows via replace semantics. Both must be exercised by a repeat load in tests: load, edit the files, load again, and assert the database matches the files.

## 6. Silent deletion of instructor data on re-import

Facts:
- Open edX: reloading a library-linked block wiped out the course's content edits (see section 4).
  - https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804
- Open edX OLX import in Tutor 19 completed without error but created only the course root and about blocks, so chapters were missing with no clear error.
  - https://discuss.openedx.org/t/olx-import-only-imports-course-root-about-blocks-never-chapters-tutor-19-teak/18925
- Canvas module save clears stored progress records for all students in that module (Chico State guide, see section 2).
- Not found: a source confirming that Open edX or Moodle re-import deletes learner progress or grades. None of the searches addressed it.

Guard against: the cleanup deletes the collection item "together with the deadline overrides on it and its part-placement due dates". Deadline overrides are educator-set data, and `learner_progress` has foreign keys to collection items (the idea says reference viewing writes nothing, so no change there). The spec should check what the deletion cascades to, such as learner progress rows for that item. It should make sure the save output names what was removed, which the idea already commits to. A candidate safeguard: a dry-run or a clear message before removing a placement that has overrides. This is a suggestion, not a settled item.

## 7. Confusing validation errors

Facts:
- The Tutor 19 OLX report above is the failure mode where import silently does less than expected, rather than an error.
- Moodle restore docs rely on admin-locked defaults that change behaviour per site, which the user cannot see from the import screen.
- Not found: a forum thread on confusing validation messages for optional or reference content in particular.

Guard against: each rule in the idea (due key on a reference entry, non-`Topic` child in a reference part, part in both lists) should produce an error that names the course, the part path and the rule. An entry that points at a non-part file should fail clearly (still open in the idea). The offline validator and `save_content_to_db` run the same rules, so wording should match in both.

## Mapping to the spec

| Complaint | Where the spec already guards | Gap to confirm |
|---|---|---|
| Optional items inflate or deflate progress | Separate model; cleanup of old placement | Test that a moved part leaves no `Course.items` row |
| Progress labels misleading | Reference viewing writes nothing | Sibling spec 2 must not show progress on reference |
| Resource not discoverable | `reference:` list and order | Unlisted files in `reference/` give no signal |
| Shared content duplicates | `../` path sharing, real FK | Two-course test; cleanup scoped to one course |
| Stale or orphaned rows | Replace semantics, cleanup | Repeat-load test |
| Silent deletion | Save output names removals | What the placement delete cascades to |
| Confusing errors | Rules in both check lists | Error wording naming course and path |

## Gaps in this research
- No usable results for Thinkific, Teachable or TalentLMS. The search returned only Articulate Rise and Docebo threads.
- Nothing found on Docebo or TalentLMS imports.
- The Moodle forum or tracker threads on optional resources were not found directly. Moodle evidence comes from documentation and university help pages.
- Pages were not fetched in full.

status: ok
