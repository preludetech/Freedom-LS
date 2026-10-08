# Research: attribute-driven automatic enrolment rules in other LMSs

Scope: how other products implement "attribute -> automatically enrol" rules, and what goes wrong. Vendor terms ("enrolment", "enrollment", "assignment", "audience") are kept and attributed. FLS's own word is "registration" and is used only in the "Implications for FLS" section. Background already covered in `spec_dd/corporate-readiness/research_corporate_features.md` section 2 is not repeated.

Evidence quality: vendor docs where reachable; otherwise vendor community forums. Several vendor help pages returned 403 to the fetcher (Docebo help centre, Absorb help centre), so some claims come from search-result excerpts of those pages and are marked "(excerpt)". Gaps are stated explicitly rather than filled from memory.

## 1. Per-product findings

### Docebo (Enrollment Rules app + automatic Groups)

- Rule shape: an enrollment rule says "when a user joins group X or branch Y, enrol them in course/learning plan Z". Attributes are not in the rule itself; they work indirectly via automatic groups whose membership is driven by conditions on enrollment status, branches and user additional fields. A rule can use a Group or a Branch but not both. https://community.docebo.com/product-q-a-7/auto-enroll-new-users-6020 (search excerpt), https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576
- Chaining: Group B = "in Ops AND completed course 1" -> enrol in course 2. Same sources as above (first link).
- Trigger: fires when a user becomes new to a group, including existing users who join or leave-and-rejoin a group. https://community.docebo.com/product-q-a-7/enrollment-rules-6746
- Retroactivity: not retroactive. Creating a rule does not touch current group members; only "NEW accounts coming in" once the rule is enabled. A community workaround is to temporarily change group conditions so everyone drops out then restore them so members re-enter as "new". A one-time duplicate enrolment is otherwise needed. https://community.docebo.com/product-q-a-7/enrollment-rules-6746, https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576
- Stops matching: no automatic unenrolment. Users removed from a group stay enrolled and get no unenrolment notification. https://community.docebo.com/product-q-a-7/enrollment-rules-6746 and https://community.docebo.com/product-q-a-7/unenroll-rules-11833 (search excerpt, a 2024 community proposal for automatic unenrol).
- Assignment vs recommendation: results show only auto-enrolment; no "recommended" state for rules found. (Gap.)
- Audit/explainability: admins want to see when members were added to a group and which enrollment rules are attached to a group, and want recorded unenrolment reasons; Docebo has an Audit Trail app used to find which admin changed what. https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576, https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492
- Direction of travel: Docebo's own design group (2026) is building a new enrollment engine that operates "independently from" groups, with improved operators and new conditions; community asks for decoupled unenrolment logic. https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576

### Cornerstone (dynamic groups + Learning Assignment Tool)

- Rule shape: dynamic groups with criteria such as Original Hire Date between two dates; the group then drives ongoing training assignments via the Learning Assignment Tool (LAT). https://help.csod.com/help/csod_0/Content/System_Configuration/Organizational_Units/Use_Case_-_Create_a_Dynamic_New_Hire_Group.htm
- Trigger: dynamic group re-evaluated once daily at an admin-defined time (back-end setting); first run can take about ten minutes. Same URL.
- Stops matching: "Dynamic Removal" is a per-assignment opt-in, off by default. Started training is kept unless a separate "Remove in progress training" switch is on. With several overlapping assignments, training is removed only after the user leaves all of them. https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Removal.htm, https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Learning_Assignment_Use_Cases/Use_Cases_-_Common_Uses_for_Dynamic_Removal.htm (search excerpts)
- Re-matching: "Dynamic reassignment" only re-assigns training that dynamic removal itself removed, not training removed manually or by the Training Removal Tool. https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Reassignment/Dynamic_Reassignment_Overview.htm (excerpt)
- Org changes: effective-dated OU/division changes only affect dynamic assignments if the change falls inside the assignment period. https://help.csod.com/help/csod_0/Content/Link/Effective_Dating/Effective_Dating.htm (excerpt)
- Override: the manual Remove button is greyed out while a dynamic assignment is active; the assignment must be deactivated first. Dynamic Removal URL above.
- Assignment vs recommendation: assignment is the rule-based mechanism; Cornerstone's "recommendations" are separately AI/profile-driven, not rule-driven (no rule-based recommended flag found). https://help.csod.com/skills-studio/ss-help-get-started/topics/ss-help-about-learning-recommendations.html (excerpt)
- Not found: full list of LAT criteria attributes; explicit preview feature.

### Moodle Workplace dynamic rules

- Rule shape: header + body of conditions and actions, "IF conditions = TRUE THEN actions". Multiple conditions are ANDed only; the same condition can be reused. Applies to every active user in the tenant; rules belong to one tenant and cannot be shared across tenants (stated for 3.11 docs). Conditions/actions are contributed by each Workplace plugin. https://docs.moodle.org/501/en/Dynamic_rules, https://docs.moodle.org/311/en/Dynamic_rules
- Triggers: most conditions are event-based; some (e.g. "course not completed") are scanned on cron. Enabling a rule runs it once as an ad-hoc task in the next cron, so users who already match are processed (i.e. retroactive on enable). https://docs.moodle.org/en/Dynamic_rules_Configuration (search excerpt, version-dependent)
- Repeat behaviour: actions do not reapply while a user keeps matching; they may reapply if the user stops then matches again. Header option "rule action limits" caps repeats. Same sources.
- Preview/audit: before enabling, Moodle shows the count of affected users and a full list of matching users; each rule has a report; a rule whose condition/action becomes invalid (e.g. deleted course) is auto-disabled and flagged. Same Configuration page (excerpt).
- Stops matching: a rule is "if this then that" - actions are forward-only; the search found no unenrol-on-unmatch semantics. (Gap; program assignment/allocation actions were not documented in the pages reachable.)

### Totara (dynamic audiences)

- Rule shape: audiences are cohorts of users, either set or dynamic (rule-based on user fields/position/organisation). Audiences can grant "Enrolled learning" (courses, programs, certifications, learning plan templates) and separately "Visible learning" (visibility only). https://totara.help/docs/what-is-an-audience, https://totara.help/docs/dynamic-audience-settings
- Triggers: membership and audience-based enrolments for new users are processed before first login; adding enrolled learning for existing users is processed in the background. https://totara.help/docs/dynamic-audience-settings
- Stops matching: dynamic membership is live, so a user who stops matching leaves the audience and loses the audience-based enrolment. https://totara.community/mod/forum/discuss.php?d=16374 (forum, Totara staff reply per search excerpt). Docs warn that removal can unenrol from many courses and deletes user settings, grades and group membership in those courses. https://totara.help/docs/what-is-an-audience
- Assignment vs recommendation: Totara separates "Enrolled learning" (assignment) from "Visible learning" (visibility without enrolment) - a built-in two-tier model. https://totara.help/docs/dynamic-audience-settings
- Notifications: per-audience choice of no alerts, alerts to affected members, or alerts to all members. https://totara.help/docs/dynamic-audience-settings (search excerpt)
- Complaint: a community thread reports users removed from audience-based certification assignment still being enrolled in underlying courses. https://totara.community/mod/forum/discuss.php?d=28017
- Not verified: AND/OR grouping detail (the "Audience rules" page was not fetched): https://totara.help/19/docs/audience-rules

### TalentLMS

- No attribute-rule engine found. Closest native: a per-group checkbox "Auto-enroll users to training" (off by default); users get enrolled in the group's courses/learning paths when added to the group. Adding a course to the group later does not enrol existing members; members added manually by an admin/instructor are not auto-enrolled. https://help.talentlms.com/hc/en-us/articles/9651522442396-How-to-work-with-groups-in-TalentLMS (search excerpt)
- New users: a "default group" auto-enrols new registrants into its courses. https://help.talentlms.com/hc/en-us/articles/9651391053212-How-to-assign-courses-to-users-upon-registration-in-TalentLMS
- Automations (event -> action, e.g. on course completion enrol in another course) exist but a "user attribute/group-add" trigger was not confirmed. https://help.talentlms.com/hc/en-us/articles/9651457002908-How-to-trigger-a-custom-action-when-users-complete-a-specific-course-in-TalentLMS

### Absorb LMS

- Rule shape: rules are defined per course. Fields include Department and Group (preferred over free-text custom fields because they are system-controlled); operators include Is Only, "and sub-departments of", Contains / Starts With / Ends With; conditions combine with AND. https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt)
- Exclusion was historically hard (Departments "Is Only" or "And sub-departments of" only); later handled by building a Group and using it in the rule (2024 idea post). https://ideas.absorblms.com/ideas/LMS-I-1144 (excerpt)
- Triggers: rules apply to existing and new users, and re-run when the course is edited (all enrollees) or a user profile is edited (that user). Manual admin enrolment bypasses rules, visibility rules and prerequisites. https://support.absorblms.com/hc/en-us/articles/360053094693-Automatic-Enrollment-Rules (excerpt)
- Stops matching: optional "Automatic Unenrollment", a client setting enabled only by Absorb support (CSM); once on, a per-course toggle appears, and only users who have not yet started the course are unenrolled. https://support.absorblms.com/hc/en-us/articles/22708205949587-Creating-Enrollment-Rules (excerpt)
- Notifications: must be enabled at both course level and portal level (message templates). Same article.
- Preview: a count preview exists but customers report it can disagree with the post-save result, and ask for a list of affected users; also fear one admin editing a rule and unenrolling thousands; one customer had Absorb write a script run every two hours to unenrol learners who no longer match and have not completed. https://ideas.absorblms.com/ideas/LMS-I-49, https://ideas.absorblms.com/ideas/LMS-I-676 (search-result summaries; the ideas pages themselves required login and were not read).

### Other products worth noting

- SmarterU: a "Recommended Enrollments" screen previews the automated enrollments the system will process and lists those that failed, with per-row failure reasons (e.g. course not in the user's group; no sessions available). https://support.smarteru.com/docs/troubleshooting-made-easy-with-recommended-enrollments (note: "recommended" here means pending auto-enrolment, not learner opt-in).
- Soffront: rules apply only to users added to the selected groups after the rule is created; an "apply rule" button enrols existing users. https://support.soffront.com/knowledge-base/enrolment-rules-in-lms/ (search excerpt)
- SAP SuccessFactors Learning: recommendations are a distinct concept from assignment, attached to an assignment profile, and show on a Recommended tile without being assigned. https://userapps.support.sap.com/sap/support/knowledge/en/2336483 (search excerpt)
- Arcoro: courses can be made required or recommended when users meet criteria such as department; required appear under assigned, recommended in the catalog; courses assigned through a rule can only be removed through that rule. https://support.arcoro.com/hc/en-us/articles/360051795874 (search excerpt)
- Penn Medicine (Cornerstone-based) guidance: match on org ID / job code; a job change auto-unassigns old-job courses and assigns new-job courses; do not use personal IDs as rule attributes or it stops being dynamic. https://www.uphs.upenn.edu/EMPLOYEESELFSERVICE/STRATEGICLEARNING/KL/docs_new/Assignment%20Profile%20Attribute%20Formats.pdf (search excerpt)

### Open-source references

- Moodle cohort sync: cohort membership drives course enrolment; later add/remove of cohort members enrols/unenrols them. https://docs.moodle.org/501/en/Cohort_sync. The "External unenrol action" (unenrol vs disable/suspend enrolment) exists per tracker MDL-37616: https://tracker-old.moodle.org/browse/MDL-37616 (excerpt; confirm on current version). Moodle core does not populate cohorts from attributes itself; that comes from uploads or plugins (not verified in fetched docs).
- Moodle plugin "Enrol by user profile fields" (enrol_attributes): enrols by any profile value (works with LDAP/Shibboleth-fed hidden fields). A user comment says enrolments it creates cannot be suspended or removed, and it would re-enrol anyway. https://moodle.org/plugins/enrol_attributes (excerpt)
- Moodle "Autoenrol" plugin uses core availability rules (date, profile). https://moodle.org/plugins/enrol_autoenrol (excerpt)
- Open edX: no attribute-rule engine found. Enrolment is manual/self/batch-by-email with an "auto enroll" checkbox; auto cohorts are random assignment within a course, not attribute-based. https://open-edx-building-and-running-a-course.readthedocs.io/en/latest/manage_live_course/course_enrollment.html (search excerpt). Pre-registration by email is described only from model knowledge (CourseEnrollmentAllowed) and is unverified here.

## 2. Cross-product comparison

| Product | Conditions | Target | Trigger | Retroactive | Unmatch behaviour | Assignment vs recommend | Preview / audit |
|---|---|---|---|---|---|---|---|
| Docebo | via auto-group (fields, branch, status) | course / learning plan | on group join | No (workarounds) | keeps enrolment | assignment only found | Audit Trail app; wished-for rule/group visibility |
| Cornerstone | dynamic group criteria (e.g. hire date) | training via LAT | daily batch | yes on next run | opt-in Dynamic Removal; in-progress kept unless extra switch | assignment | not found |
| Moodle Workplace | AND-only conditions | actions from plugins | events + cron; once on enable | yes on enable | forward-only | action-defined | count + user list before enable; report; auto-disable on invalid |
| Totara | dynamic audience rules | enrolled vs visible learning | background/cron | yes | removal can unenrol, wipes course data | both (enrolled vs visible) | notify options |
| TalentLMS | none (group membership) | group's courses | on group add | No | keeps | assignment | not found |
| Absorb | Department/Group/fields, AND, contains etc | per course | create/edit course, edit profile | Yes | opt-in, support-enabled, not-started only | assignment | count preview only, disputed |
| Moodle cohort sync | cohort membership | course | cron sync | yes | unenrol or suspend (setting) | assignment | n/a |

## 3. Common complaints / failure modes (with sources)

- Not retroactive, then confusing: Docebo admins must use workarounds or duplicate one-time enrolments. https://community.docebo.com/product-q-a-7/enrollment-rules-6746
- No unenrol on unmatch, so stale mandatory training remains and audit groups include people who should not be there. https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576
- Unenrol on unmatch destroying data: Totara warns of deleted settings, grades and group membership. https://totara.help/docs/what-is-an-audience
- A single unmatch signal is too blunt: a user going on leave should not be unenrolled from courses in progress; removal should depend on which condition stopped being true. Docebo PDG URL above. Cornerstone and Absorb both address this by only removing not-started (or opt-in in-progress) training.
- Surprise mass enrolment / blast radius: a Docebo thread where a change enrolled users in every course and another admin once enrolled 100,000+ users, slowing the system; resolution was the Audit Trail to find the admin. https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492 (search excerpt). Absorb customers fear one admin edit unenrolling thousands. https://ideas.absorblms.com/ideas/LMS-I-49 (summary)
- Preview that is only a count, and can disagree with the result. Absorb ideas above. Moodle Workplace and SmarterU are the better models (user list; failure reasons).
- Rule conflicts / overlap: Cornerstone removes only after leaving all overlapping assignments; Docebo group-OR-branch limitation prevents "branch except group" rules; Absorb lacked exclusion. URLs above.
- Manual override interplay: Cornerstone blocks manual removal while dynamic; Absorb manual enrolment bypasses rules; Arcoro rule-assigned courses removable only through the rule; TalentLMS manually-added members not auto-enrolled. URLs above.
- Performance at scale: rules that run continuously add processing load (Docebo PDG); Totara processes audience changes in the background and large removals take minutes; Cornerstone uses a daily batch. URLs above.
- Notification floods: Totara offers per-audience alert modes; Absorb requires course- and portal-level email switches; Docebo reports no unenrol notifications. Part of why mass runs are risky. URLs above.
- Dirty source attributes: free-text fields cause mismatches; Absorb recommends system-controlled fields and looser operators; Penn guidance warns against personal-ID matching. URLs above.
- Hidden vendor-side toggles: Absorb automatic unenrol is enabled only by support; Cornerstone Dynamic Removal is off by default. URLs above.

## 4. Implications for FLS

FLS words: a rule would produce `LearnerCourseRegistration` rows (individual) rather than `CohortCourseRegistration` (cohort-level), or sit above `Cohort` membership. Nothing below is a decision.

Observations that hold across products:
1. Almost everyone has two layers: a membership layer (group / audience / dynamic group / cohort) and an enrolment layer on top. Vendors that fused them (Docebo) are now splitting them (their 2026 new engine "independent from" groups).
2. Unmatch handling is the contentious part; the safe pattern seen is opt-in, not-started-only, and distinguishing rule-created from manually-created enrolments.
3. Trustworthy preview (list, not count) and an audit trail of "why" are consistently requested and rarely delivered.

Options:
- A. Rule -> cohort membership -> existing cohort registration. Rules (job title, role, hire date) keep a `Cohort` populated; existing `CohortCourseRegistration` does the rest. Precedent: Moodle cohort sync, Docebo groups, Totara audiences. Pro: reuses existing registration model and educator UI; cohort is itself the explanation of "why". Cons: inherits the membership-layer unmatch problem (Totara data-loss, Docebo no-unenrol); one person in many role cohorts means many cohorts; cohort membership then needs a "rule-managed vs manual" distinction (cf. Arcoro, Cornerstone).
- B. Rule -> direct `LearnerCourseRegistration` rows, tagged with source (rule id, evaluated-at, matched attribute values). Precedent: Absorb, Cornerstone LAT. Pro: per-person provenance gives explainability and safe unmatch (only remove rows tagged by that rule, only if not started). Cons: more rows; needs reconciliation logic when rules are edited; manual vs rule-created overlap must be defined (Absorb: manual bypasses rules).
- C. Rule -> recommendation (suggested, learner opts in), no registration until accepted. Precedent: Totara "Visible learning", SAP recommended items, Arcoro recommended. Pro: lowest blast radius; unmatch simply hides the suggestion; matches the "recommendations" name of this idea. Cons: not enough for mandatory compliance; needs its own learner-facing surface.
- D. Support both outcomes through one rule "outcome" type (register vs recommend), as Totara, SAP and Arcoro do, implemented as pluggable backends. Fits the "other rule backends later" note in `idea.md`. Cost: a backend interface to design early; do not build the interface until a second backend exists (project convention: do not build unrequested functionality).

Cross-cutting design choices to settle regardless of option (each is a trade-off seen above):
- Retroactivity: apply on create/attribute-change and/or a "run now" for existing users; Docebo's non-retroactivity is a top complaint, Moodle Workplace's run-on-enable is the milder model.
- Unmatch default: keep (safe, stale) vs remove not-started only (Absorb, Cornerstone) vs suspend (Moodle cohort sync option). Removal that deletes progress is the documented worst case (Totara).
- Dry-run preview listing users and failure reasons before enabling (Moodle Workplace, SmarterU) and a registration provenance record (the gap Docebo admins report).
- Notifications on bulk runs: suppress or batch by default (Totara has modes; Absorb needs two switches).
- Per-client on/off: Moodle Workplace scopes rules per tenant; Absorb/Cornerstone gate removal behind admin/support settings. A per-site feature flag plus per-rule enabled flag is the pattern; Absorb's "support-enabled only" shows a second, higher guard for destructive behaviour.
- Attribute hygiene: prefer controlled fields (department, job title choices) over free text, or normalise before matching (Absorb guidance).

status: ok
