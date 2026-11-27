# Research: known complaints when an LMS restricts question and answer access and logs views

Topic: `known_complaints`. Method: web searches only (search result summaries; pages were not opened in full). Evidence is thin on some points. Each finding is marked **Sourced** (a search result supports it) or **Inference** (my reasoning from the sources and general practice). The Moodle tracker and Canvas forums gave no thread that matches "audit log flooded by view entries" or "admin bypasses question confidentiality" directly.

## 1. Educators locked out of questions they teach

**Sourced.**
- Moodle: a teacher's question rights stop at their own course. A question category outside the course where they hold the teacher role gives them nothing by default. Capabilities split into "view all" and "view mine", and the "all" capability wins. Teachers who cannot see questions are usually missing one of these, or sit behind a role override. (https://docs.moodle.org/405/en/Question_permissions)
- Moodle forum: an admin found the preview capability missing from the editing teacher role and added it by hand. The first suggestion in the thread was to check enrolment. (https://moodle.org/mod/forum/discuss.php?d=310412)
- Moodle: `mod/quiz:preview` and `mod/quiz:attempt` conflict. A user cannot be allowed to both preview and attempt. Teachers who were given the attempt capability lose preview. (https://docs.moodle.org/503/en/Capabilities/mod/quiz:preview)
- Canvas New Quizzes: item banks belong to the creating user, not the course. Colleagues must be given access, and TAs and instructors need edit access, not view access, to see question feedback and grading notes. (https://community.instructure.com/en/discussion/593001/how-can-a-ta-see-the-feedback-of-a-banked-question-in-new-quizzes)
- Canvas: sharing set at edit level can fall to view-only after a course copy. Designers complained they could not edit institution-shared banks. (https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Increased-Visibility-of-Item-Banks-Across/idi-p/578356)
- Canvas: a question was asked about restricting who can view quiz questions. Staff said no role setting does this and pointed the user to the Ideas board. (https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Added-levels-of-quiz-security-at-question-level/m-p/470708)
- Canvas: threads on "Quizzes and item banks inaccessible in newly created course" and "How can I get permission to edit a new quiz & question bank in a class I teach". (https://community.canvaslms.com/t5/Archived-Questions/Quizzes-and-item-banks-inaccessible-in-newly-created-course/m-p/484776/highlight/true, https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-How-can-I-get-permission-to-edit-a-new-quiz-question/m-p/236824)

**Relevance to the spec (Inference).** The recurring complaint is "I teach this course and I cannot see its quiz", with the cause hidden in a permission the educator cannot see. Here a cohort admin or organisation admin who today previews content will lose it. The spec should:
- Say plainly on screen that the permission is missing, and name it.
- Keep every non-question part of the course preview and cohort report working.
- Make the new role easy to find and assign.
- Not let any existing role pick up the permission silently, so the loss is deliberate and documented.
- Tell existing admins in the release notes or docs that the preview and quiz detail go away until they are given the role.

## 2. Confusing hidden sections

**Sourced (weakly).** The Canvas and Moodle threads above show the same pattern: the feature simply is not there for the user, and they ask forum strangers why. The Moodle docs advise checking role overrides and "Not set" inheritance because the cause is rarely visible in the page the user is looking at (https://docs.moodle.org/503/en/Roles_FAQ).

**Inference.** Omitting a panel silently looks like a bug or a missing feature. This supports the idea's recommendation of a visible one-line note in place of the panel ("Question detail is hidden: you do not have permission to view questions"). For the PDF, the same note, so a printed report is not mistaken for a broken one. The scores and counts must stay, or the report looks half empty. The note should not name which role to ask for if the site renames roles, but should name the permission.

## 3. Audit logs flooded by view entries

**Sourced.**
- Moodle: the standard log table has no built-in cleanup, grows without bound and can reach over 100 GB on busy sites. (https://moodle.org/plugins/tool_s3logs)
- Moodle forum: a 18 GB log made a SELECT slow on every module view. Clearing 30 days helped. (https://moodle.org/mod/forum/discuss.php?d=394716)
- Moodle forum: too many writes to the standard log, with users asking to filter some records. (https://moodle.org/mod/forum/discuss.php?d=311248)
- Moodle tracker: reads against a large log table blocking inserts, closed "Won't Fix". (https://tracker-old.moodle.org/browse/MDL-11901)
- Moodle docs: a write buffer setting exists to batch log inserts. (https://docs.moodle.org/500/en/admin/setting/logsettingstandard)
- Zendesk: an admin buried in routine sign-in entries cannot find configuration changes. (https://support.zendesk.com/hc/en-us/community/posts/4408868407834-Overwhelmed-by-noise-in-audit-log/comments/4411294294170)
- Microsoft: reads outnumber writes by roughly 100 to 1, so auditing reads is very noisy. Advice is to audit only the objects that matter. (https://learn.microsoft.com/en-us/archive/blogs/ericfitz/minimizing-directory-service-audit-event-noise)
- NXLog: filter noise at the source. (https://nxlog.co/news-and-blog/posts/reduce-log-noise-and-fight-soc-alert-fatigue/)

**Relevance (Inference).**
- The idea logs one entry per rendering request with no dedupe. The risk is not volume from page loads, since only holders of a narrow role view questions, but a multi-page form or a report that re-renders on each HTMX swap. Define exactly which requests count as a "view" (the idea already excludes paging continuation, prefetch and plain GET).
- Because the audit log is also the organisation's change history (`conversation.viewed` is already there), view entries can bury change entries. Filters by verb or noun in the Audit log page and the History tab should let an auditor show only `viewed question`, or hide it.
- No dedupe means a holder who refreshes ten times writes ten entries. That is defensible for a compliance trail but expect complaints. Document it.
- Write cost: one row per view is small for this role. Do not add retention or archiving here (out of scope), but note growth in the docs.

## 4. Cached reports leaking or going stale after permission changes

**Sourced.**
- Moodle tracker: a teacher-role change not showing up; workaround was purging all caches (GUI or `admin/cli/purge_caches.php`). (https://tracker-old.moodle.org/browse/MDL-44493, https://tracker-old.moodle.org/browse/MDL-52370)
- Moodle tracker MDL-81991: `has_capability()` returns wrong results for some tasks when user data is marked dirty, in 4.3 and 4.4. (https://tracker-old.moodle.org/browse/MDL-81991)
- Moodle Roles FAQ: old releases applied role changes only at next login. A "Not set" permission keeps whatever was in force on entry. (https://docs.moodle.org/503/en/Roles_FAQ)
- UCLA: a teacher kept seeing all grades after a group capability change until it was switched from Allow to Not set. (https://bookstack.kb.ucla.edu/books/ccle-and-moodle/page/modifying-roles-in-moodle)
- Moodle forum on role switching and session storage: stale data stored in the session. (https://bitbucket.org/dw8/moodle-format_tiles/issues/69/session-storage-and-switching-roles)

**Relevance (Inference).** The pattern is a cache or session holding an answer to "may this user see it?" past the moment it changes, and the fix is a manual purge. For FLS:
- Do not cache the permission decision. Either the cache key includes the has-permission flag (so the two versions are separate entries), or the permission is checked on every request and the cached payload is stripped of detail. Keying on the flag means revoking a role takes effect on the next request with no purge.
- A holder's cached panel must never be served to a non-holder; a test should assert it in both directions (holder then non-holder, non-holder then holder).
- A cached version with detail still sitting in the cache after revocation is acceptable only if no non-holder can be served it. Consider whether the cache key should also be tied to the viewing request rather than shared across users.
- A cache hit must still write the audit entry for a holder, or the trail has gaps. Moodle-style "viewed but not logged" is the failure to avoid.
- Stored PDFs are the same problem in file form: a file carrying the detail outlives a role revocation. The idea's recommendation (refuse download of a detail-carrying file to a non-holder) matches this.

## 5. Superusers and admins bypassing controls

**Sourced.**
- Moodle: `moodle/site:doanything` (legacy) and the admin override pass every capability check; docs say overrides on it should not be set. The searches found no doc on hiding question content from site admins. (https://docs.moodle.org/test/Capabilities/moodle/site:doanything)
- Moodle Roles FAQ: admins should not be given a second role, because a second assignment can explain lingering access. (https://docs.moodle.org/503/en/Roles_FAQ)

**Inference.** Admin bypass is the usual hole in "confidential question bank" claims: the Django admin and superuser `can()` both pass. The idea already addresses this by removing the admin pages and logging superuser views. Residual complaints to expect:
- A superuser can still read the bank through a shell, the API and database access (all out of scope). Docs should say the trail covers the application UI only.
- Auditors may ask why superusers pass the check at all. The answer is that their views are logged like everyone else's.
- Superusers can grant themselves the role. Role assignment is already an audited action; the docs should point to it.

## 6. Removing admin pages breaks support workflows

**Sourced.** Nothing found directly. No tracker thread on removing admin question pages.

**Inference (general experience, flagged).**
- Support staff use admin pages to answer "why did this learner get this wrong", to fix a typo in a question, to look up a question id from a ticket, and to check which option is marked correct. Removing the pages removes the tool, and the replacement (the gated preview and the cohort report) answers only part of those.
- Workflows to check before removal: fixing question text (content is loaded from files, so editing is probably in content files rather than the admin; verify), looking up answers on a survey or application (kept, per the idea), support reading a learner's answer on a quiz (removed; the attempt review in spec 5 is the replacement), and data export.
- Dead links: the idea says links degrade to plain text. Add a test that visits each remaining admin page that referenced the removed models (list filters, autocomplete fields, `raw_id_fields`, inlines) to catch broken changelist filters and reverse errors.
- Say in the docs where each removed workflow now lives, and that a user without the role cannot do it at all, including support.
- The QUIZ vs survey split in `FormProgressAdmin` is a likely source of confusion: the same admin shows an answers document for one form and not another. A short note in place of the document ("Answers to quizzes are hidden; see the attempt review") avoids a silent gap, in line with section 2.

## Summary of design pressures for the spec

1. Show a visible note and name the permission wherever detail is hidden (screen, PDF, preview action refusal page).
2. Keep scores and counts everywhere so reports stay useful.
3. Key the report cache on the permission, and test both directions; audit even on a cache hit.
4. Define "one view" precisely; give auditors a way to filter `viewed question` entries in and out.
5. Gate stored PDFs at download as well as generation.
6. Check every admin link, filter and inline that touched the removed models; map each removed support task to its new home in the docs.
7. Document the limits: shell, API and database access are outside the trail; role assignment is audited; no dedupe.

status: ok
