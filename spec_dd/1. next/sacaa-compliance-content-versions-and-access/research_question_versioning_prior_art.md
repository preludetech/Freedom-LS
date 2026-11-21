# Research: question versioning, retirement, content-as-code sync and bank access, prior art

Date: 2026-11-21. Input: `idea.md` in this folder. Complements `spec_dd/1. next/sacaa-compliance/research_sacaa_requirements.md` (not repeated; its 5-year retention and "attempt must be reproducible" findings are taken as given).

Method: time-boxed web pass using search snippets plus a few page fetches. Several primary sources were unreadable (PDF streams, truncated pages). Labels: (a) stated in a source read, (b) forum/vendor/secondary claim, (c) my inference, (?) not found. Moodle schema detail (table/column names) is from my own background knowledge, NOT confirmed by a fetched source; the dev docs URL I tried returned 404.

FLS terms: `Form`, `FormPage`, `FormQuestion` (and its options), `FormProgress`, `content_save`.

## 1. Question revisions: what triggers a version, how attempts stay pinned

### Moodle 4.x
- (a) Question bank UI has a Version column showing "the various edits of that question", with a History action; Status column holds ready/draft; a question can be set draft or ready at creation or in the column. Source: https://docs.moodle.org/405/en/Question_bank
- (b) A Moodle developer (Tim Hunt, via forum summary) says once a student starts a quiz, Moodle records which version of which question is in use and sticks with it; only students who started after the edit see the new version. Source: https://moodle.org/mod/forum/discuss.php?d=453360 (and https://moodle.org/mod/forum/discuss.php?d=438090).
- (b) A quiz slot can be set to a specific version or "Always latest". Changing to "Always latest" then running a full regrade can retroactively change what past answers are marked against (MDL-75823, https://tracker-old.moodle.org/browse/MDL-75823). Lesson: a "float to latest" pointer and regrade is the main way history gets rewritten.
- (b) Feature request MDL-80006: let a minor edit update in-progress attempts instead of making a new version, i.e. Moodle makes every save a new version and has no "minor edit" concept. https://tracker-old.moodle.org/browse/MDL-80006
- (c, background knowledge) Model: `question_bank_entries` (stable identity) 1-to-many `question_versions` (version number, status ready/draft/hidden) 1-to-1 `question` (the actual content row, immutable per version). Attempts store the `question` row id, so they point at the exact version. Quiz slots point at the entry plus a version choice (specific or null = latest). Version created on every save of the edit form.
- (b) The "Import question as new version" plugin exists because stock import creates a new entry rather than a new version of an existing one. https://moodle.org/plugins/qbank_importasversion
- Takeaway for FLS: the identity/version split plus "attempt pins the version row" is the established pattern, and it is the same as what the idea asks for.

### Canvas New Quizzes / Item Banks
- (b) Once students have submitted, an item can only be edited by creating a copy via "Edit in Bank"; the copy gets separate statistics, the original stays visible only in quizzes already taken, and the new version goes to students who have not taken the quiz or have attempts remaining. Sources: https://kb.wisc.edu/luwmad/page.php?id=153005 , https://blogs.flinders.edu.au/fit/2023/08/22/canvas-faqs-quiz-edits-after-submission/ , https://community.instructure.com/t5/Instructor-Guide/How-do-I-edit-an-item-bank-item-in-New-Quizzes/ta-p/703 (page itself could not be read; summarised from search).
- (b) Institutional advice: regrade in SpeedGrader first, then edit the bank item. Sources conflict on whether plain bank edits propagate to every quiz using the item (community idea https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-allow-changes-to-item-banks/idi-p/573615).
- Pattern: copy-on-edit only once answered ("fork if used"), unchanged otherwise.

### Open edX
- (a) Editing a released problem does NOT touch learner state: learners who answered under the old key keep their scores; learners after the change are scored against the new one. Staff must rescore or replace the component. Source: https://docs.openedx.org/en/ulmo/educators/references/course_development/modifying_released_problem.html
- (b) Learner state lives in `StudentModule` keyed by the problem's usage key (not by a content version); each save also writes a history row (https://discuss.openedx.org/t/extra-history-record-stored-on-each-problem-submission/8081). Resetting attempts is done by code that keeps data for analytics (Confluence page https://openedx.atlassian.net/wiki/x/IIBLAw).
- (c) So Open edX stores the answer and the score but not a pointer to the question text as it was; the question definition is overwritten in place. It is weaker than Moodle for audit. This is the failure mode the idea wants to avoid.
- (b) Content Libraries v2 (library import) is additive: "creating new versions of that content in the library as necessary. No content is deleted from the library as a result of an import." Source: https://openedx.atlassian.net/wiki/spaces/COMM/pages/3966795804 (search snippet).

### QTI 3 (1EdTech)
- (b) The assessment item root has an `identifier`; I found nothing in snippets on a mandatory version/revision scheme or deprecation. Identifier stability and any version scheme are left to the packaging/metadata layer. Spec: https://www.imsglobal.org/sites/default/files/spec/qti/v3/info/index.html ; guide https://www.imsglobal.org/node/196951. (?) Not verified beyond that.
- (c) Takeaway: QTI gives a stable item id but does not solve version history; do not look to it for the version model.

### Commercial assessment platforms
- Questionmark (vendor marketing, (b)): item versioning "to track exactly what's been changed, when, and by who"; version history with rollback; side-by-side revision comparison; audit trail of edits; role locking; "retiring keeps the question in the bank, unused, and it can still be referenced to defend past tests or run statistics on". Sources: https://www.questionmark.com/platform/flexible-authoring/ , https://www.questionmark.com/app/uploads/2023/01/Intro-to-Questionmark.pdf
- Inspera (b): editing a bank question alerts users opening a question set that contains it (https://elearning.uq.edu.au/node/13145). Item bank access is bank + access groups + permissions, and a bank manager can govern structure without seeing content (https://inspera.com/why-inspera/item-banks/). Retired-item mechanics not found.
- Mastery Connect (Instructure) has an item versioning FAQ: https://community.canvaslms.com:443/t5/Mastery-Connect-Assessments/What-is-item-versioning-in-Mastery-Connect/ta-p/386883 (not read).
- Aviation-specific CBT systems: (?) not found. Notably SACAA itself reportedly runs Questionmark Perception for its question database, built from the SA-CATS 61 syllabus, four options per question (parliamentary reply, https://pa.org.za/speech/51185221, via search snippet). That sets the auditor's mental model: a Questionmark-style bank with versioned, retired items.

## 2. Retiring, hiding and how staff see it

- Moodle: deleting a question still used by a quiz only hides it (kept in DB). "Also show old questions" reveals hidden ones. Status draft/ready gates whether a question can be drawn. Source: https://docs.moodle.org/405/en/Question_bank. MDL-84433 notes the main view shows the latest version per entry (https://tracker-old.moodle.org/browse/MDL-84433).
- Canvas: old version remains only inside quizzes already taken; the replacement is a separate item with separate statistics.
- Questionmark: retired status, stays referenceable for defending past tests (above).
- Open edX: no retirement concept for problems found; unit/problem removal means removal from the course structure (?).
- Blackboard/UTEP (b): random blocks link to the pool question, "so if you change the original question, the revised version appears", and the way to exclude is remove it from the pool: i.e. the lax, non-compliant baseline. https://www.utep.edu/extendeduniversity/cid/faculty-training/tutorials/assessments-and-assignments/creating-random-blocks.html , https://help.blackboard.com/Learn/Instructor/Original/Tests_Pools_Surveys/Reuse_Questions/Random_Block
- (c) Common staff display: a status badge (hidden/retired/superseded), version number plus date, and "show old/hidden" toggle in the bank list; in attempt review, the question as answered with a flag if it is no longer current.

## 3. Git/file-based content pipelines: deletions, identifiers, provenance

- Moodle GIFT/XML import: additive only; no deletion detection; re-importing creates duplicates (R/Exams example), and there is no stable id on import beyond an optional `idnumber`. The qbank_importasversion plugin is a workaround. Sources: https://docs.moodle.org/403/en/Question_import , https://moodle.org/plugins/qbank_importasversion , https://tracker-old.moodle.org/browse/MDL-63752. (b)
- Open edX OLX: blocks are identified by `url_name` within a course key, so identity is author-controlled and stable. Whether course re-import removes missing blocks and what happens to StudentModule rows: not found in sources (?). Library import is explicitly additive (no deletion). Courses are "periodically re-exported and re-imported" as the normal flow (https://edx-partner-course-staff.readthedocs.io/en/latest/releasing_course/export_import_course.html).
- Docs-as-code assessment tools with commit-hash provenance and clean-repo gates: none found in this pass. (?) The clean-repo check is a standard release-engineering practice (e.g. `git status --porcelain`, `git rev-parse HEAD`, `git remote get-url origin`) rather than an LMS convention.
- (c) Implications for `content_save`:
  - Full-sync-per-Site (the idea's "assume single source") is stricter than anything surveyed; every surveyed LMS is additive. The retire-not-delete step is therefore novel and must be designed by us. Must define: match key (the UUID), what "absent from all paths" means with several repos, and un-retire when a UUID reappears.
  - Stable identifier must be author-owned and in the file (as `url_name` and QTI `identifier` are), which is exactly what the `--generate-uuids` split enforces.
  - Provenance: store repo origin URL plus commit SHA on the version row; refuse to save from a dirty tree so the SHA actually describes the content. Moodle/Canvas/Open edX have no equivalent (they store who/when, not source commit).

## 4. Restricting bank/answer-key visibility and logging views

- Moodle: bank access is capability-based; by default only users with at least a teacher role in a course reach its bank; a site-wide "Question bank Manager" can be custom-defined (https://docs.moodle.org/405/en/Question_bank). Logging of views is via the generic event log, not a dedicated bank-view audit (c).
- Inspera: separate admin permission (manage bank structure) from content permission (see questions) via access groups (https://inspera.com/why-inspera/item-banks/).
- Questionmark: role locking and audit of changes (marketing); view logging not claimed.
- FAA: active question specifics are confidential; no public full list; FAA Order 8080.6 covers testing centre and test/data security (not retrieved). https://www.faa.gov/training_testing/testing/Frequently_Asked_Questions.pdf , https://www.faa.gov/documentLibrary/media/Order/FAA_Order_8080.6H.pdf
- EASA Part-147 (secondary): the bank "must be secured against unauthorised access to maintain examination integrity", reviewed and refreshed regularly, and large enough that sittings are not predictable (Sofema summary, https://sofemafaq.netlify.app/knowledge/part-147-a-105-examination-standard/). EASA FAQ: the authority must sample-check and review the organisation's question data bank and exam process (https://www.easa.europa.eu/en/faq/19074). Proposed new 147.A.25 (UK CAA RMT 0201 consultation, Jan 2026) targets exam cheating, fraud and conflict of interest and refers to controlled storage including the question database; I could not read the text (PDF unreadable): https://consultations.caa.co.uk/policy-development/update-to-uk-regulation-eu-no-1321-2014-continuing/user_uploads/rmt_0201_consultation_continuing_airworthiness_part-147.pdf
- None of the above explicitly mandates logging each view of the bank. The idea's view-log is stricter than the surveyed norm but is consistent with SACAA's e-learning matrix (next section).

## 5. SACAA / comparable wording and the source quote

- Most relevant find: a 2024 SACAA tender annex "e-learning platform risk matrix" reproduces SA-CATS 141.07.1 requirements for e-learning systems. Per search/fetch summary (b, PDF text not extractable, so wording is NOT verified): assessment by category uses an online test drawn from a master question list, sometimes with randomised answer order; security row requires a secure question database and an annual audit of access to it in higher categories, plus an internal audit trail of results; records kept five years. https://documents.easytenders.co.za/public/tenders/2024/03/145827/blobname659d9792-a493-473c-8c36-91e3f2c4f023pdfdownloadedfilenameannexure-a-e-learning-platform-risk-matrix.pdf
  - (c) This is very likely the family of requirement the idea comes from: "random questions from a master list" plus "audit of database access" matches the sibling items in the idea (version control + view logging). The "revised question blocked from random selection but retained for audit" sentence is plausibly a row in that same matrix or in SA-CATS 141.07.1 itself.
  - Action: download the PDF locally and read it, and obtain SA-CATS 141 (Subpart 7, e-learning) from caa.co.za; confirm whether the revision sentence is there and which risk category (1 to 3 or similar) the client's e-learning falls under, since controls are tiered.
- The exact phrase "whenever a question is revised it shall be blocked from the random questions available to the student but, should remain in the system for audit purposes": searches returned no hit. Origin not confirmed. (?)
- Part 141 manual: manual and amendments are Director-approved, format per SA-CATS 141 (https://api.acts.co.za/civil-aviation-act-2009/nr425_141_05_6_training_and_pr.php). (c) So a client may also have this sentence in its own approved manual, which is the document the auditor will actually test against.
- SACAA investigated exam question suitability via its Internal Forensic Unit with an independent expert (pa.org.za link above): evidence that questions themselves, not just results, get audited, which supports reproducing the exact text answered.
- EASA/CAA UK: no wording found on revision of questions or retaining superseded questions. The Part-147 "regularly reviewed and refreshed" duty implies revision happens and is expected, but retention of superseded items is not stated in what I read.

## Translation into FLS terms

- Identity vs version: `FormQuestion` keeps its UUID as stable identity (the content_save UUID). Add an immutable per-version snapshot of question text, option texts and correct-option marker (and score/type), created when `content_save` sees any field differ (exact text/value comparison, matching the idea's "any change counts").
- Pinning: the learner's stored answer (under `FormProgress`) must reference the version row, not the live question. This is Moodle's model; Open edX's overwrite-in-place model is what to avoid.
- Serving: random draw and display select only the current (non-superseded, non-retired) version. In-progress attempts: Moodle pins to the version started; Canvas lets attempts already begun keep the old one. Recommended: an in-progress `FormProgress` finishes on the versions it was served (c), which also needs the served set recorded at start; decide and state this explicitly in the spec because the idea is silent.
- Retire: UUID absent from the full source set marks the question (and Form/FormPage as applicable) retired, not deleted; old versions kept. Same status for "superseded by newer version" vs "retired" is worth distinguishing for staff display.
- Provenance: version row stores source repo origin, commit SHA, and saved-at.
- Staff display: in the educator view of a learner's attempt, show the version text answered, the version number and date, and a "no longer served" badge when it is superseded or retired. Bank list gets a "show superseded/retired" toggle (Moodle precedent).
- Access: a distinct permission to view question text/answers (Inspera: bank-manage separate from content-view); every view (and perhaps export) writes an audit log entry; remove the Django admin question views so there is no unlogged path. Note the learner-facing attempt review of answers is a separate path and should be reviewed for the same leak.
- content_snapshots (paused idea): the surveyed systems get compliance from per-question version rows only, not whole-course snapshots, which supports the idea's lightweight intent. Caveat: if the Form's structure (which questions, draw rules) can change, "reproduce the paper" also needs the served question list stored per attempt (see sacaa research note).

## Patterns worth adopting

1. Stable identity plus immutable version rows; attempts reference the version row (Moodle).
2. New version on any change at the content_save boundary, exact comparison; no "minor edit" carve-out (Moodle forum shows demand for one, but a carve-out defeats audit).
3. Retire (status), never delete; keep retired/superseded items referenceable by past attempts (Questionmark, Moodle hide).
4. Separate "manage structure" from "view content" permissions (Inspera); log views.
5. Store source provenance (origin plus commit SHA) per version, and gate content_save on clean tree (no surveyed LMS does this; ours is stronger).
6. In-progress attempts keep the versions they were served (Moodle, Canvas).
7. Treat the author-written UUID as the sync key (url_name/QTI identifier precedent), generated only in an explicit authoring mode.

## Patterns worth rejecting

1. Overwrite-in-place with scores kept but question text lost (Open edX): fails audit.
2. "Always latest" pointers combined with regrade (Moodle MDL-75823): rewrites history. If regrade exists in FLS, it must say which version it marks against.
3. Linked-not-copied random blocks where an edit silently changes what is served (Blackboard/UTEP).
4. Additive-only import with no deletion handling (Moodle GIFT/XML, OpenEdX library import): leaves removed content still being served; the idea already rejects this. But do not hard-delete either.
5. Whole-course snapshots (the paused content_snapshots): no surveyed system needs them for question-level audit.
6. Relying on the Django admin for question viewing: unlogged path.

## Gaps to close before the spec

- Read the SA-CATS 141.07.1 risk matrix text (and SA-CATS 141) to confirm the source quote, the tier that applies, the exact "audit of access to database" frequency (annual per summary) and any per-attempt record fields.
- Confirm whether the client's manual repeats the sentence.
- Decide: in-progress attempt behaviour on mid-attempt edit; whether version-change detection includes non-text fields (marks, order, tags); whether Form-level changes (question added/removed from a Form) are versioned.

status: ok
reason: prior art covered for Moodle, Canvas, Open edX, QTI, Questionmark/Inspera and EASA/FAA; SACAA quote origin not confirmed (likely SA-CATS 141.07.1 e-learning matrix, PDF unreadable); Moodle schema names and Open edX re-import deletion behaviour unverified
