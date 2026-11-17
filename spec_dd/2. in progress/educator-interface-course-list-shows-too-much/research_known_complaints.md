# Research: known complaints in cross-tenant course sharing and permissions

Scope note: I did not read answers.md or the other research files. I only read idea.md. Searches were limited (3 web searches), so evidence is thin. I found few first-person forum complaints. Most items below are vendor docs, feature requests and maintainer comments. Where evidence is weak I say so. Nothing was found for TalentLMS, LearnUpon, G2 or Capterra.

## Complaints and implications

### 1. Hiding a course also hides learner progress (Absorb)
- Complaint: an Absorb customer idea says that hiding a course from non-system admins also hides progress for it. The only alternatives are leaving other admins able to see the course, or impersonating learners. They ask for a separate "show data in reporting" setting per course.
- Source: https://ideas.absorblms.com/ideas/LMS-I-3878
- Implication: this directly matches our "see" flag. A `see=false` grant must not hide a course's progress for an org whose learners are registered. Our rule "existing registrations keep the course visible without content" covers this. The spec should state that educators still see their own learners' progress, and only their own learners'. It should also say which course-list and report surfaces show it.

### 2. Un-sharing makes the course and its data vanish (Second Nature)
- Behaviour: when the parent removes a shared course, it is removed from the sub-account. Sessions and progress data are hidden for that account. Restoring the share brings the history back.
- Source: https://support.secondnature.ai/articles/6805419329-sharing-courses-across-accounts-parent-sub-accounts
- Implication: hiding is the less surprising choice, because the data is not deleted and is recoverable. Our "existing registrations keep the course visible" rule is better than this. The spec should say that revoking a grant never deletes registrations or progress, and never removes the learner's own access. It should say what an educator sees for a course that is kept visible only because of registrations (a name and progress, no content). It should also say that re-granting restores full access.

### 3. Orphaned or ambiguous enrolment on un-share (Docebo)
- Complaint: a Docebo community user asked for a way to unassign a course from a branch so that everyone in it is unenrolled. This suggests that removing branch access does not unenrol by default, and that admins want an explicit choice. Branch and course enrolment are separate actions. The thread shows no confirmed answer.
- Sources: https://community.docebo.com/integrations-apis-45/course-unassignment-unenroll-from-branches-6102 and https://community.docebo.com/product-q-a-7/adding-courses-for-specific-branch-visibility-only-15040
- Implication: the spec should say explicitly that revoking a grant does not unregister anyone. It should also say that new registrations are blocked once `register` is revoked, and who may remove existing ones.

### 4. Edge cases and unclear scoping when courses are shared (IOMAD, Moodle Workplace)
- Observation: an IOMAD maintainer says users should only see courses in their active company, but edge cases exist. One example is a user enrolled in a course their editing company has not added. A related open question is which company's course group a user lands in.
- Observation: Moodle Workplace docs say shared-course participants can see other tenants' users in participant lists, forums and the gradebook. The docs recommend separate group mode.
- Sources: https://github.com/iomad/iomad/pull/1339 and https://docs.moodle.org/502/en/Multi-tenancy_Tenants
- Implication: a course-level `see` flag can leak other orgs' learners through other surfaces (participant lists, reports, cohort pickers). The spec should require that every educator query for registrations, progress and learners is scoped to the educator's own org, not just the course list. Also test the edge case of a registration existing without a grant.

### 5. Cross-tenant admin leakage (Canvas, reverse case)
- Canvas known issue: a sub-account admin could view New Analytics in courses where they were only enrolled as a student in another sub-account.
- Source: https://community.canvaslms.com:443/t5/Known-Issues/New-Analytics-displays-for-users-enrolled-as-Students-in-a/ta-p/647368
- Implication: the same class of bug as our idea.md, where secondary surfaces (analytics, detail URLs, APIs) ignore list-level filtering. Add tests that direct URL access to a hidden course's educator pages returns 404 (or 403), and not only that the list omits it.

### 6. Course admins seeing too much learner detail (Zensai Learn365)
- Vendor added a global toggle that limits course admins' access to learner progress details.
- Source: https://helpcenter.zensai.com/hc/en-us/articles/360011420397-Limit-access-to-Learn365-learners-learning-progress-details-for-course-admins-and-line-managers
- Implication: weak evidence. Keep `see`/`register`/`preview` independent but resist adding more flags. Do not add a progress-detail flag unless it is requested.

### 7. Not covered by evidence (my inference, not found in sources)
These are common themes I expect but did not find sourced complaints for:
- Too many knobs and permission-matrix confusion. Three independent flags allow odd combinations such as `register` without `see`. The spec should define each combination, or normalise it (for example `register` implies `see`).
- No way to tell why a course is missing. Consider a short explanation on the educator side, or at least a documented debug path.
- Edits propagating unexpectedly. Shared content is edited once by the owner, so grantees see changes. Say so in docs.
- Seat or licence accounting. A `register` grant bypasses price and application gates, so state who is billed or counted, or that FLS does not account for it.
- A `register` grant bypassing application gates is high-trust. Document that it is deliberate.

## Summary of spec implications
1. Revoking a grant never deletes or hides registrations or progress for the grantee's own learners (items 1, 2, 3).
2. Scope every educator surface to the educator's org, not just the list (items 4, 5).
3. Test direct URL access to hidden courses (item 5).
4. Define flag combinations, or normalise them (item 7).
5. Keep the flag set minimal (item 6).

status: ok · reason: completed with thin first-hand evidence. Items 7 and part of 6 are inference. No G2, Capterra, TalentLMS or LearnUpon sources were found.
