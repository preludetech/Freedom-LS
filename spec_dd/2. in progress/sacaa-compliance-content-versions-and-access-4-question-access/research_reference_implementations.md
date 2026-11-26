# Research: reference implementations of gated, audited access to questions and answer keys

Topic `reference_implementations`. Complements section 4 of `spec_dd/1. next/sacaa-compliance-content-versions-and-access/research_question_versioning_prior_art.md` (which covers Moodle default bank access, Inspera access groups, Questionmark, FAA and EASA). That is not repeated. Findings come from web search snippets and one page fetch; where a claim could not be confirmed it is marked.

## Moodle

- Capabilities (all per context; question categories are contexts): `moodle/question:viewall` / `viewmine`, `useall` / `usemine`, `editall` / `editmine`, `moveall` / `movemine`, `tagall` / `tagmine`, plus `add`, `config`, `managecategory`, `flag`. An `all` capability overrides its `mine` counterpart, which is then not tested. https://docs.moodle.org/en/Question_permissions
- `viewall` means seeing a question's content including every answer, and with it the user can also save a copy as new and export the category. Preview is a separate, weaker capability (`useall`). Defaults: manager and teacher; students have no bank access. https://docs.moodle.org/en/Capabilities/moodle/question:viewall , https://docs.moodle.org/500/en/Question_permissions
- Quiz reports: `mod/quiz:viewreports` (Grades and Responses reports; default manager, teacher, non-editing teacher) is separate from `mod/quiz:grade` (manual grading), and statistics has its own `quiz/statistics:view`. Reports are therefore gated by their own capability, not by the bank capability. A forum thread (MDL-38557) shows the two had overlapping checks that behaved inconsistently; the lesson is to gate each surface explicitly. https://docs.moodle.org/503/en/Capabilities/mod/quiz:viewreports , https://moodle.org/mod/forum/discuss.php?d=224916
- Logging: Moodle logs through its generic event system. Tracker MDL-36088 records that question-bank add/modify (and preview) were not logged at one point; whether this was later closed was not confirmed. I found no `question_viewed` event in core (a `question_created` event exists, linked to `question/preview.php`). MDL-44017 removed a generic `content_viewed` event as low value. Net: Moodle has a capability for who may see answers but no dedicated per-view audit of question content. https://tracker-old.moodle.org/browse/MDL-36088 , https://tracker-old.moodle.org/browse/MDL-44017 , https://docs.moodle.org/dev/Events
- Not confirmed: how the Responses report behaves for a user with `viewreports` but without bank `viewall` (whether question text is hidden).

## Canvas

- Classic question banks and New Quizzes item banks are shared with roles; sharing is limited to teacher, TA or admin roles. New Quizzes added a separate view permission so a bank can be used in quizzes without being editable. Account-wide visibility needs the account permission "Item Banks - manage account", included in the standard account admin role. https://community.canvaslms.com/t5/The-Product-Blog/New-Quizzes-Item-Banks-Management/m-p/470074 , https://kb.wisconsin.edu/dle/news.php?id=12763
- Community complaint "item bank for new quizzes is a huge security risk" (access is broad once shared). Treat as anecdotal. https://community.canvaslms.com/t5/Canvas-Question-Forum/Item-bank-for-new-quizzes-is-a-huge-security-risk/m-p/594984
- Not found: any log of item-bank question views; Canvas audit logs cover bank changes at most (unconfirmed). Canvas controls answer exposure to learners via a quiz setting, not a staff capability.

## Open edX

- Course team roles (Admin, Staff, Data Researcher; new authz system maps Course Admin / Course Staff) are course-wide. Staff see answers through the problem's Show Answer setting and the Staff Debug Info modal; "Never" hides the button even from staff but staff can still read the configured answer in the debug modal. Data Researcher reaches the Data Download tab (link to answer detail unconfirmed). There is no separate "may see answer key" role. https://docs.openedx.org/en/latest/educators/references/course_development/course_team_roles.html , https://discuss.openedx.org/t/problem-show-answer-never/11440 , https://docs.openedx.org/projects/openedx-authz/en/latest/concepts/core_roles_and_permissions/course_roles.html
- Tracking logs record learner events (problem_check etc.); I found no log of staff reading the answer key.

## TAO (Open Assessment Technologies)

- Functional roles are separated: Item Author, Test Author (needs Item Author to pick items), Test Center Administrator, Proctor (must be authorised), Reviewer (Results panel only), Test-taker. An ACL grants read/write per user or role on resources (e.g. folders of items: all authors read-only except the owner). So seeing items is a resource permission, and a Reviewer sees results without item authoring access. https://userguide.taotesting.com/user-documentation/latest/public/main-roles , https://userguide.taotesting.com/user-documentation/latest/public/access-control-and-permissions , https://userguide.taotesting.com/user-documentation/latest/public/permissions
- No TAO audit log of item views found.

## Blackboard

- Learner side: Ultra "Show correct answers" is off by default and release can be timed (after submission, due date, grades posted, date). Pool contents are hidden from students; instructors get a preview. Nothing found on a staff capability separating "see answers" from "teach the course", or on view logs. https://help.blackboard.com/node/30361 , https://lta.shu.ac.uk/support/guides/blackboard-ultra-guides/assessment-and-feedback/using-tests/question-pools-in-tests

## Commercial exam platforms

- Inspera (already in the prior-art file): access groups split bank structure management from content visibility. Questionmark: role locking and change audit, view logging not claimed. ExamSoft and others: my search found nothing on per-view question logging; not confirmed either way.

## Patterns across the set

1. Capability to view question content is separate from capability to use or preview it (Moodle `viewall` vs `useall`), and from capability to view results (Moodle `viewreports`). Reports are gated on their own.
2. Views are not logged anywhere surveyed. Logging covers creation, change, and learner activity. A per-view audit of the answer key is stricter than every reference (consistent with the prior-art conclusion).
3. Default grants are broad (teacher, instructor, any course staff), which is the weakness the FLS idea corrects by granting the permission to no existing role.
4. Capabilities are context-scoped (Moodle category context, TAO folder ACL, Canvas account vs course); FLS equivalent is the organisation scope.
5. Hiding is by omission on learner surfaces (settings), not by redaction for staff; no reference redacts question detail inside a report for staff lacking a capability. The FLS "omit detail, keep scores" report is original design, so the spec carries the cache and PDF decisions itself.
6. Moodle's `viewall` bundles view, copy and export: a reminder that answer-key access leaks through export paths (here: the PDF and the admin), which the idea already closes.

## Gaps

No source found for a reference platform that logs per-view access to question content, redacts report detail by capability, or stores export artefacts with a flag for whether they carry the key.

status: ok
