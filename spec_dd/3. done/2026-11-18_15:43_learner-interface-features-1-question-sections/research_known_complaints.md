# Research: known complaints about tagging questions to sections or outcomes

Question: what do course authors and educators commonly complain about when tying questions to sections or outcomes in LMSes and question banks?

Evidence is thin and mostly from Canvas and Moodle community or tracker threads. Treat each as a pattern, not a measurement. Web search found nothing specific on tag drift or competency loss on restore, so the drift point below is design inference, flagged as such.

## Findings that would change the spec

1. **One-at-a-time tagging of a large bank is the top complaint.** Canvas Classic let an instructor align an outcome to a whole question bank. New Quizzes only aligns to a whole quiz or a single question, and instructors call aligning a large bank question by question "very labor intensive". Spec implication: the form-level default plus per-question override (already settled) is the right answer to this. Make sure the default applies to every question that names no sections, so an author tags a 40-question form once. Do not require the per-question key.
   - https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Allow-outcomes-to-be-aligned-with-item-banks/m-p/543896
   - https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Allow-outcomes-to-be-aligned-with-item-banks/idi-p/543460/page/2

2. **A link at the wrong level silently gives wrong results.** In one Canvas thread, question-level tags only counted when outcomes were also placed on the whole quiz, and every outcome then reported the same whole-quiz score. Another thread reports alignments that never show in reporting, with no error. Spec implication: define precisely and document the override rule (a question that names sections replaces the form default; it does not add to it), and state it once in the docs and the validator. The ambiguity "does a per-question list add to or replace the default?" is the likely source of author surprise. Decide it explicitly, and consider having the validator or loader report the resolved sections per question.
   - https://community.canvaslms.com/t5/Canvas-Question-Forum/Outcome-Alignments-Not-Showing/m-p/597737
   - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Outcome-aligned-question-banks-but-no-indication-in/td-p/525859

3. **Targets that exist in the system but cannot be chosen.** Canvas users report course-level outcomes not appearing for linking, because only account-level ones are offered. The analogue here: the settled design allows a `CoursePart` or a `Topic` only. Authors will want to name things that are neither (a whole course, a group of topics). Spec implication: say plainly in the docs and the load error that only a part or a topic is a valid target, and make the error name what was found (for example "path resolves to a Course, not a part or topic"). Do not widen the target set in this spec.
   - https://community.canvaslms.com:443/t5/Canvas-Question-Forum/Trouble-with-course-created-outcomes-not-appearing-for-linking/m-p/570858
   - https://community.canvaslms.com:443/t5/Canvas-Ideas/New-Quizzes-Allow-any-outcome-available-to-the-course-to-be/idc-p/546570

4. **Reuse across contexts is why vendors restrict bank-level links.** A Canvas staff reply says bank questions may measure different outcomes in different courses, which is the stated reason New Quizzes does not align banks. This supports linking to content (part or topic), not to a placement, which is the settled choice. It also warns that an unplaced bank form carries links that mean "this content" regardless of course; the spec must not imply a course context for them.
   - https://community.canvaslms.com/t5/Archived-Questions/Unable-to-Add-Outcomes-to-Item-Bank-Questions/m-p/474508

5. **Copy, restore and reorganise break references.** Moodle's tracker and docs show repeated restore and category-move bugs where question categories or set references point at the wrong context or are pushed into a different level, and the documented workaround is to trim or exclude the question bank on restore. Moodle also has duplicate-stamp problems after category moves. Spec implication: FLS references by path in the source file, so a rename or move of the target breaks the link at the next load. That load error (settled) is the safeguard. The error message should name the question and the old path. The docs should say that renaming or moving a part or topic means updating the question files, and that the validator finds every affected one. A rename-following mechanism (uuid reference) was not chosen; the research found no evidence authors expect one when the fix is a visible load error.
   - https://docs.moodle.org/503/en/How_to_minimize_the_question_bank_when_doing_backup/restore
   - https://tracker-old.moodle.org/browse/MDL-85166
   - https://tracker-old.moodle.org/browse/MDL-85556
   - https://tracker-old.moodle.org/browse/MDL-54864

6. **Orphans and coverage gaps are what authors check after revising.** Alignment studies map many objectives to many assessment tasks and explicitly look for tasks that assess nothing and objectives with no assessment. Spec implication (inference, not a new feature): with default-only tagging, a question may name no section at all. Settle whether that is allowed (it must be, since the idea says forms without links still work) and whether the validator may report it. The spec should not build a coverage report (out of scope), but should not make it impossible later: the stored link should be queryable from the section side.
   - https://pmc.ncbi.nlm.nih.gov/articles/PMC4346822
   - https://www.stonybrook.edu/celt/assess/course-assessment-planning.html

7. **Multi-outcome questions** appear in the complaint sources only as a given (many-to-many mapping is standard in alignment work). The Canvas complaints are not that a question has several targets, but that the tooling makes each extra target another manual step. Several-per-question is settled; the authoring key should accept a list and also a single string if the schema allows, so the common one-section case stays one line.

## Not found

- No source on tag drift between question text and the tagged content (a question edited until it no longer tests its section). This is a human-process risk no tooling in the sources solves. Nothing here changes the spec.
- No source on competency or tag loss on course copy beyond the Moodle category issues above.

status: ok
