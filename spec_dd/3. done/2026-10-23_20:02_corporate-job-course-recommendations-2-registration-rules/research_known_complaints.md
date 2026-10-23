# Research: known complaints about automatic, rule-based course enrolment

Topic: `known_complaints`. Question: what do admins and learners commonly complain about with automatic, rule-based enrolment, and does the idea (`idea.md`, spec 2 of Registration rules) already guard against each?

Vendor terms are kept and attributed ("enrolment", "assignment", "audience"). FLS's word, "registration", is used only for the idea's side.

Evidence quality: this builds on `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (cited below as "earlier research"). Several vendor pages (Docebo help, Absorb help and ideas) were not fetchable, so some claims come from search excerpts, and are marked "(excerpt)". One new search was run (Moodle unenrol versus suspend). Very little learner-side complaint material exists in public: almost all public complaint is from admins. Learner-side items below are inferred from admin descriptions and are marked "(inferred)". Okta, Azure AD dynamic groups, TalentLMS reviews, Workday Learning and Cornerstone forums were not searched afresh in this unit; the earlier research gives no complaint content for Workday or Okta/Azure AD, so that is a gap, not a finding.

## Complaint-by-complaint

### 1. Unexpected unenrolment and lost progress or grades

- Totara warns that removal from an audience can unenrol from many courses and delete settings, grades and group membership in those courses. https://totara.help/docs/what-is-an-audience
- Moodle: an unenrolled user normally keeps no course data and leaves the gradebook. A suspended user keeps their data. Cohort sync's "External unenrol action" chooses between unenrol and suspend, but it is site-wide and affects all cohorts in all courses. Recovery needs "Recover user's old grades if possible", and for non-manual methods depends on the `recovergradesdefault` setting. https://moodle.org/mod/forum/discuss.php?d=419477 ; https://docs.moodle.org/en/Unenrolment ; https://tracker-old.moodle.org/browse/MDL-37616 (excerpt)
- A single "stopped matching" signal is too blunt: someone going on leave should not lose in-progress courses (Docebo design group). https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576
- Mitigations vendors chose: Cornerstone Dynamic Removal is opt-in and keeps started training unless "Remove in progress training" is on (https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Removal.htm, excerpt). Absorb unenrols only not-started users, and only with a support-enabled setting (https://support.absorblms.com/hc/en-us/articles/22708205949587-Creating-Enrollment-Rules, excerpt).
- Learner view (inferred): a course disappears from the dashboard after a job or department change, with no explanation.

Idea status: guarded. A learner who started is left alone, progress is never deleted, retraction is `is_active=False` (reversible, nothing destroyed), another matching enabled rule blocks retraction, and staff only reactivate rows the rule itself deactivated.

Gaps:
- "Started" is still open in the idea. Too narrow a definition (progress record only) deactivates a registration for someone who opened content. Moodle's grade-recovery pain shows what a wrong call costs.
- The idea says a started learner is "left alone" but gives no signal that the rule no longer covers them. Cornerstone and Docebo admins want to find these stale rows (earlier research §3).
- Deactivated registration may still hide the course from the learner without explanation (inferred). The idea does not say what the learner sees.
- No guard on a data-entry mistake: one wrong department edit retracts a not-started registration, and the re-match reactivates it only if the rule made the deactivation. A flapping attribute (HR import fixed a day later) causes churn; see §8.

### 2. Stale mandatory training because nothing unenrols on unmatch

- Docebo: users removed from a group stay enrolled; no unenrolment notification; admins ask for decoupled unenrol logic. https://community.docebo.com/product-q-a-7/enrollment-rules-6746 ; https://community.docebo.com/product-q-a-7/unenroll-rules-11833 (excerpt)
- Totara: certification assignment removed but users still enrolled in underlying courses. https://totara.community/mod/forum/discuss.php?d=28017
- Moodle enrol_attributes plugin: a user comment says its enrolments cannot be suspended or removed and would be re-created. https://moodle.org/plugins/enrol_attributes (excerpt)

Idea status: guarded. Unmatching and disable both retract not-started learners, with preview.

Gap: started learners keep an active registration indefinitely with no flag. This is the same stale-row problem, narrowed to started learners. Acceptable, but name it.

### 3. Not retroactive, or rules that do not re-run

- Docebo: rules apply only to users who newly join a group; admins use temporary condition changes or duplicate one-time enrolments to catch existing users. https://community.docebo.com/product-q-a-7/enrollment-rules-6746
- Soffront: needs a manual "apply rule" button. https://support.soffront.com/knowledge-base/enrolment-rules-in-lms/ (excerpt)
- TalentLMS: adding a course to a group does not enrol existing members. https://help.talentlms.com/hc/en-us/articles/9651522442396-How-to-work-with-groups-in-TalentLMS (excerpt)
- Moodle Workplace: actions do not reapply while a user keeps matching; they may reapply after stop-then-match; "rule action limits" cap repeats. https://docs.moodle.org/501/en/Dynamic_rules
- Cornerstone: dynamic groups re-evaluate once daily, so changes lag up to a day. https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Use_Case_-_Create_a_Dynamic_New_Hire_Group.htm

Idea status: guarded. Enabling applies to everyone who already matches; runs on rule edit, attribute change and Learner creation.

Gaps:
- No "run again" or reconcile action for the case where a run failed, the organisation switch was off and then turned on, or a list entry changed. The idea says what triggers a run but not what repairs a missed one. Moodle Workplace runs enable as a cron ad-hoc task; Absorb re-runs on course edit.
- Org-level start-date conditions ("before a date") depend on time passing, not on an edit: a learner can start matching "on or after" a date with no attribute event firing. Cornerstone's daily batch and Moodle's cron scan exist for this reason. The idea lists only event triggers. This is the clearest unguarded "rule did not re-run" case.
- Turning the organisation switch off then on: the idea does not say whether this triggers a full re-evaluation.
- Whether a rule edit that changes nothing material still re-runs everything (cost, see §7).

### 4. Manual enrolments overwritten, or manual vs rule interplay

- Cornerstone: manual Remove is greyed out while a dynamic assignment is active. https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Removal.htm (excerpt)
- Absorb: manual enrolment bypasses rules. https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt)
- Arcoro: rule-assigned courses can be removed only through the rule. https://support.arcoro.com/hc/en-us/articles/360051795874 (excerpt)
- Moodle: removing a user from a cohort unenrols only the Cohort method; they stay enrolled by Manual, and admins then clean up by hand. https://moodle.org/mod/forum/discuss.php?d=419477
- Cornerstone dynamic reassignment re-assigns only what dynamic removal removed, not manual removals. https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Reassignment/Dynamic_Reassignment_Overview.htm (excerpt)

Idea status: well guarded. A rule never takes over an existing registration, never reactivates one staff deactivated, and reactivates only its own deactivations. This matches the Cornerstone model and avoids Cornerstone's "greyed-out remove".

Gaps:
- Staff cannot yet tell a staff-deactivated row from a rule-deactivated one in the UI; provenance is open in the idea. Without it the guard is invisible to admins.
- A rule skipped a learner because a registration already existed (manual). If staff later delete that manual registration, nothing re-runs the rule for that learner until an attribute changes. Same class as §3.
- The learner self-registered, then was matched: the rule does nothing, so the registration is not rule-protected and unmatching never touches it. Correct, but admins will ask "why is she still in it?" (inferred).

### 5. Unclear why someone was enrolled (no provenance or audit)

- Docebo admins ask when members joined a group, which enrollment rules are attached, and for recorded unenrolment reasons; the Audit Trail app is used to find which admin did it. https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576 ; https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492 (excerpt)
- Learner side (inferred): a learner who is auto-registered asks "why am I in this course?"; the notification is the only explanation.

Idea status: partly guarded. Every rule-made registration records the rule; rule actions go to the audit log if it has landed; educator-interface 7 shows the source.

Gaps:
- The record is only "which rule". It does not record when the rule registered the learner, nor which attribute values matched at that time. If a rule is later edited or the attribute changes, the "why" is lost. Earlier research option B proposed rule id, evaluated-at and matched values.
- Deactivation by a rule is not stated to record the rule or time. Admins asking "who removed this" is a Docebo complaint.
- The learner-facing explanation is unaddressed (idea scopes screens to spec 4 and educator-interface 7, which are staff views).
- If the rule is deleted (allowed once disabled), the provenance FK must not be lost or cascade-delete registrations; the idea does not say.

### 6. Notification floods

- Totara offers per-audience alert modes (none, affected, all) because enabling a rule on a big audience sends a large burst. https://totara.help/docs/dynamic-audience-settings (excerpt)
- Absorb needs notifications enabled at both course and portal level. https://support.absorblms.com/hc/en-us/articles/22708205949587-Creating-Enrollment-Rules (excerpt)
- Docebo sends nothing on rule unenrolment, which admins also complain about. See §2.
- Earlier research §4 lists "suppress or batch by default" as a cross-cutting choice.

Idea status: not guarded, and partly the opposite. The idea sends the usual `course.registered` for every rule-made registration. Enabling a rule for an existing 2,000-person department sends 2,000 notifications at once. Also, a flapping attribute (see §8) re-sends on every reactivation.

Gaps:
- No per-rule or per-run option to suppress or batch the notification on the initial application.
- No statement whether reactivation by the rule re-fires `course.registered`.
- No notification on retraction (matches Docebo's complaint, though silent deactivation is arguably the safer default; the idea should say so).
- The preview shows who would be registered but not that each will get a message.

### 7. Slow evaluation and blast radius

- Docebo: a change enrolled users in every course and one admin once enrolled 100,000+ users, slowing the system. https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492 (excerpt)
- Docebo design group: continuously running rules add processing load. See §2 URL.
- Cornerstone first dynamic group run can take about ten minutes; evaluation is a daily batch. See §3 URL.
- Totara processes large changes in the background and they take minutes. https://totara.help/docs/dynamic-audience-settings
- Absorb: customers fear one admin edit unenrolling thousands. https://ideas.absorblms.com/ideas/LMS-I-49 (summary)

Idea status: partly guarded. Evaluation is a background task, and preview lists affected learners before any enable, edit or disable. Retraction is reversible.

Gaps:
- Nothing says how big a run is bounded or chunked, or what happens when two edits to one rule queue concurrently (the second evaluation can run against the first one's half-applied state). Moodle Workplace cron tasks run as one ad-hoc task per enable.
- The preview is a point-in-time list; the run can differ if attributes change between preview and confirm. Absorb's complaint is exactly "preview disagrees with result" (https://ideas.absorblms.com/ideas/LMS-I-49, summary). The idea does not say the run will apply the list the staff saw, or re-compute.
- No progress or status indicator for a long run; the admin cannot tell if it finished (inferred from the Docebo and Totara background-processing complaints).
- An edit that touches a very large organisation has no confirm-friction beyond the preview.
- A preview of thousands of names as a list may itself be slow or unreadable; paging is not mentioned.

### 8. Rules matching on dirty or changing attributes, and flapping

- Free-text fields cause mismatches; Absorb recommends system-controlled fields. https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt)
- Penn guidance: do not use personal IDs as rule attributes. https://www.uphs.upenn.edu/EMPLOYEESELFSERVICE/STRATEGICLEARNING/KL/docs_new/Assignment%20Profile%20Attribute%20Formats.pdf (excerpt)
- Cornerstone effective-dating: org changes only affect dynamic assignments if inside the assignment period. https://help.csod.com/help/csod_0/Content/Link/Effective_Dating/Effective_Dating.htm (excerpt)

Idea status: mostly guarded. Conditions pick from the organisation's controlled lists; deactivated entries keep matching and the rule admin flags them; deactivating an entry retracts nothing.

Gaps:
- Transient wrong data (a bulk HR import, spec 5) can retract and re-register many learners in a row. There is no debounce, hold or "pause evaluation during import".
- Rules and a mid-year transfer: a learner moves out of Finance for a month and back. The idea covers the not-started case, but each leg may fire notifications (§6).
- A start-date condition that references a null date: the idea does not say whether a learner with no start date matches "before"/"on or after" (silent non-matching is a common surprise; inferred).

### 9. Rule conflicts, overlap and missing exclusions

- Cornerstone removes only after the user leaves all overlapping assignments. See §1 URLs.
- Docebo allows group or branch but not both, so "branch except group" cannot be written; Absorb historically lacked exclusion. https://ideas.absorblms.com/ideas/LMS-I-1144 (excerpt)
- Moodle Workplace auto-disables a rule whose condition or action becomes invalid and flags it. https://docs.moodle.org/501/en/Dynamic_rules

Idea status: guarded for overlap (another enabled rule blocks retraction). Exclusions are explicitly out ("no exclusions"), which is a known future complaint, not a bug.

Gaps:
- No rule-health state: if the course is deleted or archived, or the lists change, nothing is flagged or auto-disabled. Moodle Workplace does this.
- A course that is deactivated or unpublished while a rule targets it is not mentioned.

### 10. Hidden or destructive settings, and who can change a rule

- Absorb automatic unenrol is enabled only by support; Cornerstone Dynamic Removal is off by default. See earlier research §3, last bullet.
- Docebo and Absorb: who changed a rule is hard to find without a separate audit app.

Idea status: guarded by the organisation switch and per-rule enable. Audit is conditional on `educator-interface-11-audit-log` landing.

Gap: if the audit log has not landed, there is no record of who enabled, edited or disabled a rule, which is the Docebo "find which admin" complaint. The idea should say what is recorded by the rules app itself (at least created/changed by and when) rather than depend on another spec.

## Summary table

| Complaint | Where seen | Idea guards? | Main remaining gap |
|---|---|---|---|
| Unexpected unenrolment, lost progress | Totara, Moodle, Absorb, Cornerstone | Yes | "started" definition open; learner sees nothing explaining a deactivated course |
| Stale training, no unenrol on unmatch | Docebo, Totara, Moodle plugin | Yes | Started learners kept with no stale flag |
| Not retroactive / does not re-run | Docebo, Soffront, TalentLMS | Mostly | Date-based conditions fire no event; no re-run action; switch off-then-on |
| Manual enrolment overwritten | Cornerstone, Absorb, Arcoro, Moodle | Yes | Provenance not visible; no re-run after staff delete a manual row |
| Unclear why enrolled | Docebo | Partly | No when / matched values; deleted-rule handling; learner-facing reason |
| Notification floods | Totara, Absorb | No | No suppress or batch option; reactivation behaviour unstated |
| Slow evaluation / blast radius | Docebo, Cornerstone, Totara, Absorb | Partly | Preview vs run drift, concurrency, chunking, run status |
| Dirty or flapping attributes | Absorb, Penn | Mostly | Bulk-import churn, null dates |
| Overlap, exclusion, rule health | Cornerstone, Docebo, Moodle Workplace | Overlap yes | No rule-health / auto-disable; exclusions out of scope by design |
| Who changed a rule | Docebo, Absorb | Conditional | Depends on audit-log spec landing |

## Top items for the spec to settle

1. Notification volume on first application and on reactivation (no guard today).
2. Date-based conditions need a time-driven re-evaluation or the idea's promise ("stay true") fails for them.
3. Preview-to-run consistency and concurrent runs.
4. Provenance detail: time, matched values, deactivation by the rule, and deleted-rule behaviour.
5. "Started" definition, and a way to see started learners a rule no longer covers.
6. A repair path (re-evaluate on demand) and rule-health flags.

status: ok · reason: built on the earlier research plus one new Moodle search; learner-side and Workday/Okta/Azure AD complaint evidence is thin and is marked as gap or inferred
