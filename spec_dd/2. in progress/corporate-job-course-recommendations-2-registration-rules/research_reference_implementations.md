# Research: reference implementations of attribute-based automatic enrolment rules

Topic: `reference_implementations`. Builds on `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (Docebo, Cornerstone, Moodle Workplace, Totara, TalentLMS, Absorb, Moodle cohort sync, SmarterU and others). That ground is not repeated. This file adds systems and depth the earlier file lacks: Microsoft Entra ID dynamic groups, Okta group rules, Moodle `tool_dynamic_cohorts`, Moodle `local_profilecohort`, Moodle `enrol_attributes`, Canvas and Open edX. Vendor terms are kept and attributed. FLS words (registration, rule, outcome) appear only in section 3.

Evidence quality: Entra docs fetched in full. Okta is from search-result excerpts; the Okta help pages and developer API page returned 404 or outline only. The Moodle plugin pages give little (no repo, no README), and `tool_dynamic_cohorts` came from a fetched GitHub README summary. No source code was read for any product, so data-model claims are inferred from docs and marked as such. Gaps are listed, not filled from memory.

## 1. Per-system findings

### Microsoft Entra ID dynamic membership groups (closest analogue for add/remove)

- Rule data model: a group with membership type "Dynamic" and a single rule string `<Property> <Operator> <Value>` combined with `-and`, `-or`, `-not` and parentheses; max 3,072 characters; max 15,000 dynamic groups per tenant. A rule-builder UI covers up to five expressions, a text box covers the rest. https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-membership
- Condition combination: free boolean algebra. Precedence: comparison, then `-not`, `-and`, `-or`. An `-in ["a","b"]` operator gives "any of these values" within one attribute, which is the same shape as FLS's "AND across attributes, OR within one". `-ge`/`-le` exist for the date attribute `employeeHireDate` (preview), the same on-or-after / before idea as the FLS start dates. Same URL.
- Provenance: membership is not "enrolled by" anyone. A dynamic group is purely derived; you cannot manually add or remove a member. This sidesteps the manual-versus-rule overlap problem by forbidding the overlap. Same URL.
- Unmatch: members are removed as soon as they stop satisfying the rule. No grace, no keep option. Same URL.
- Trigger: when any attribute of a user or device changes, all dynamic rules in the directory are re-evaluated for that change. Creating or editing a rule triggers evaluation of that group. Processing is asynchronous. https://learn.microsoft.com/en-us/entra/identity/users/groups-create-rule
- Observability: a per-group "Dynamic rule processing status" (Evaluating, Processing, Update complete, Processing error, Update paused, Not started) and "Last membership change" timestamp; an alert if no pending update could be processed for 24 hours; an admin "Pause processing" switch per group. Same URL (groups-create-rule).
- Side effects: users newly added to a Microsoft 365 dynamic group receive the welcome email, and this can be turned off in Exchange PowerShell. So notification-on-rule-add is a known default that admins want to control. Same URL.
- Preview: the docs describe a "Validate rules" feature for sampling users against a rule (page 404'd at the URL tried: https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-rule-validate-users). Treat as unverified here. The portal does explain why an invalid rule cannot be processed.
- Security warning worth copying: the group is only as trustworthy as the write permissions on the attributes in the rule (for example attributes users can edit themselves). Same URL (groups-dynamic-membership).
- Performance advice: avoid `-contains`/`-match`; prefer simple equality; clean up stale users because every user is evaluated. https://learn.microsoft.com/en-us/entra/identity/users/groups-create-rule

### Okta group rules

- Rule data model (from docs excerpt): a rule has conditions on one or more profile attributes, groups, or both; basic condition rules support string attributes only; the rule assigns users to target group(s). Org limit 2,000 rules; rules cannot target admin groups; only super/org admins edit rules. https://help.okta.com/en-us/content/topics/users-groups-profiles/usgp-about-group-rules.htm
- Unmatch: membership follows the attribute; when department changes the user leaves the Sales group. Same URL.
- Manual override as an explicit record: if an admin manually removes a rule-added user from the group, Okta puts the user on the rule's exclusion ("exception") list, and re-activating the rule does not re-add them. Clearing it requires deactivating the rule, editing the exception list (API for big lists) and reactivating. https://support.okta.com/help/s/article/How-to-add-and-remove-users-from-groups-using-group-rules-and-exceptions, https://support.okta.com/help/s/question/0D54z00009WkjHJCAZ/reactivating-of-a-group-rule-doesnt-add-user-to-the-group-if-user-was-manually-removed-from-it (search excerpts). This is the same intent as the FLS decision "a rule never reactivates a registration staff deactivated", implemented as a per-rule per-user exception row.
- Deactivate versus delete: deactivating a rule keeps members it added and stops applying to new users; deleting a rule makes the admin choose to keep or remove rule-added members, and the choice is permanent. https://support.okta.com/help/s/article/what-happens-if-group-rules-are-deactivated-and-deleted (excerpt). This is the opposite of the FLS decision that disabling counts as everyone unmatching.
- Not found: when rules are evaluated, rule preview, conflict resolution. The Okta developer API page only returned an outline (fields, status ACTIVE/INACTIVE, evaluation, deactivation with `removeUsers`, membership types). https://developer.okta.com/docs/reference/api/groups/

### Moodle tool_dynamic_cohorts (Catalyst IT)

- Rule data model: each rule has one target cohort, a set of conditions, and one logical operator (AND or OR) for the whole rule. One cohort can be managed by only one rule, so two rules never fight over a cohort. https://github.com/catalyst/moodle-tool_dynamic_cohorts (README summary)
- Triggers: a scheduled task finds all enabled rules and queues one ad-hoc task per rule; conditions can also listen to events (profile condition listens to user created/updated) for near-real-time adds; per-rule and global switches turn real-time off; bulk mode inserts directly in batches and fires no events unless asked. Same URL.
- Safe-edit workflow: rules are created disabled; admin reviews the affected-user count in the rules table, then enables; any edit disables the rule again until reviewed and re-enabled. Same URL. Preview is a count only; no list.
- Not found: how removal on unmatch works and what happens to manually added members (README summary was silent).

### Moodle local_profilecohort

- Maintains cohort membership from a custom profile field. The Moodle plugin page states the plugin is feature-complete, will not get major features, and recommends `tool_dynamic_cohorts` as the more versatile option. No README or repo was reachable. https://marketplace.moodle.com/plugins/local_profilecohort
- Not found: rule shape, trigger, removal.

### Moodle enrol_attributes

- "Enrol by user profile fields": enrols users from any profile value, typically hidden fields fed by LDAP or Shibboleth. The marketplace page gives no rule syntax, AND/OR, sync timing, unmatch behaviour or repo. https://marketplace.moodle.com/plugins/enrol_attributes. The earlier research file records a user comment that its enrolments cannot be suspended or removed.
- Why it matters: it is an enrolment method instance in the course (provenance = the enrol instance), the standard Moodle way to record how an enrolment arose.

### Moodle core cohort sync (extra detail)

- Removing a user from a cohort suspends the cohort-sync enrolment instead of deleting it, and leaves role assignment in place; one tracker issue notes group membership is not removed and was closed Won't Fix. https://tracker-old.moodle.org/browse/MDL-67445. External unenrol action unenrol vs suspend: https://tracker-old.moodle.org/browse/MDL-37616 (excerpt).
- Enrolment source is first-class: each Moodle enrolment sits on an enrol instance (manual, self, cohort...), so "who made this" is always known, and a user enrolled by two methods has two rows and is only truly removed when both go. This is the Moodle equivalent of the FLS rule that another enabled rule matching blocks retraction.

### Canvas and Open edX

- Canvas: no attribute-rule engine found. Enrolment comes from SIS imports (rows carry the SIS source) and manual or self-enrolment. The only relevant result is a community post that SIS-created courses are not "manually created". https://community.canvaslms.com/t5/Admin-Group/Only-courses-with-blank-SIS-ID-are-considered-quot-Manually/m-p/159786. Treat Canvas as: provenance by SIS batch, not by rule.
- Open edX: no attribute engine. Batch enrolment by email with an "Auto Enroll" option: matching registered accounts are enrolled immediately, and unmatched emails are enrolled when the account is registered. https://open-edx-building-and-running-a-course.readthedocs.io/en/latest/manage_live_course/course_enrollment.html. Useful only as precedent for "evaluate on user created".

## 2. Comparison on the questions asked

| System | Rule data model | Combination | Records source of the membership/enrolment | On unmatch | Trigger | Preview |
|---|---|---|---|---|---|---|
| Entra dynamic groups | one rule string per group | free `-and/-or/-not`, `-in` lists, date `-ge/-le` | none; membership is derived, manual edits forbidden | removed at once | any attribute change; rule save | processing status and last-change time; validate feature unverified |
| Okta group rules | conditions on attributes/groups, target groups; exception list | not fully documented (AND/OR of conditions) | rule-added versus manual known; exception list for manual removals | follows attribute; deactivate keeps members; delete asks keep/remove | not found | not found |
| tool_dynamic_cohorts | rule: cohort, conditions, one AND/OR operator | one operator per rule | one rule per cohort (ownership by exclusivity) | removal exists, details not found | cron to per-rule ad-hoc tasks plus events; global/per-rule real-time switch | created disabled, count in table, edit disables again |
| Moodle cohort sync | cohort to course enrol instance | n/a | enrol instance per method | suspend or unenrol (setting) | cron plus events | n/a |
| enrol_attributes | profile value rules (details not found) | not found | enrol instance | not found, user reports no removal | not found | not found |
| Canvas / Open edX | no rule engine | n/a | SIS batch / batch email | n/a | on account registration (edX) | n/a |

## 3. What this idea should borrow or avoid

The idea's settled design already matches the best practice in the earlier file (direct per-learner rows, tag with the rule, retract only not-started, list preview). Points where these systems add something:

Borrow:
1. Evaluate everything affected on a single attribute change, asynchronously, and expose a status. Entra re-evaluates on attribute change and exposes "processing / update complete / error / last membership change" per rule. The FLS rule should store a last-evaluated time and a last-run outcome (ok or error) on the rule so admins can see a background task failed. This fits `django.tasks`, where failure is otherwise invisible.
2. Edit makes the rule safe again. `tool_dynamic_cohorts` disables a rule after any edit until re-reviewed. The idea instead previews and confirms an edit, which is equivalent; keep confirm-before-apply and do not let an edit apply in the admin before the preview has been shown.
3. A per-rule, per-learner exception record for staff deactivations. Okta stores a manual removal as an exception so reactivating the rule does not undo it. The idea's rule "never reactivates a registration staff deactivated; reactivates only rows it deactivated itself" needs the same fact recorded: either store which actor deactivated the row, or keep a flag or field on the registration for "deactivated by rule". Decide this in the spec under the provenance shape; a plain boolean `is_active` is not enough.
4. Provenance as a first-class pointer, as Moodle does with the enrol instance. The nullable FK to the rule fits the "open until the spec" question: a FK answers "which rule", and a null means a person made it. Because Moodle shows a learner can hold two enrolment methods for one course, FLS has a one-row-per-learner-per-course uniqueness question: a learner already registered by staff keeps the staff row (idea: never take over). So multi-rule overlap must be answered by "any other enabled matching rule blocks retraction" (the idea's rule), not by multiple rows.
5. Option to pause a rule without retracting. Entra has "Pause processing" and Okta deactivation keeps members. The idea defines disabling as retracting everyone, which is stricter and closer to Cornerstone. Consider whether the spec needs a third state only if staff ask; the research evidence says admins like it, but the idea says do not build unrequested. Flag it as an open question, do not build it.
6. Warn about who can edit the attributes. Entra's security note matters here: if learners can edit their own job title or department (spec 1), a rule becomes a self-registration path. The spec should state whether HR attributes are staff-only.
7. One rule owns one target. `tool_dynamic_cohorts` allows one rule per cohort to avoid conflicts. FLS cannot do that, since the idea allows several rules for one course and uses "another enabled rule blocks retraction". Keep the idea's approach and test the two-rule case explicitly.

Avoid:
1. Free-form rule strings (Entra rule text, Okta expressions). They need a parser, a validator and an editor, and the idea's conditions are a fixed small set (four lists, four dates). Use structured condition rows.
2. Preview that is only a count (tool_dynamic_cohorts, Absorb). The idea already requires a list; keep it.
3. Disabling or deleting a rule that silently drops everyone, or the opposite (Okta delete asks keep or remove, a permanent choice). The idea's "disable counts as everyone unmatching, with the same preview, and delete only once disabled" avoids both; keep it.
4. Welcome email floods. Entra and Totara send notifications to everyone newly matched. The idea sends `course.registered` for each rule-made registration; a bulk enable of a large rule will send many. Note this as a risk for the spec (batching or a rule-level notify switch is the mitigation in Totara), not a change to the settled decision.
5. Evaluating the whole tenant for every attribute change (Entra does this; its docs push people to simplify rules for speed). FLS should evaluate only the changed learner against rules for their organisation when a single learner changes, and all learners of the organisation only when a rule changes.
6. Unmatch that deletes progress (Totara) or leaves role/group residue (Moodle MDL-67445). The idea only sets `is_active=False` for not-started courses and leaves started ones alone, which avoids both.

## 4. Gaps

- No source code was read for any system; data-model rows are inferred from docs.
- Entra "Validate rules" behaviour, Okta evaluation timing and preview, `tool_dynamic_cohorts` removal and manual-member behaviour, `enrol_attributes` and `local_profilecohort` internals were not reachable. Reading the `tool_dynamic_cohorts` repo source (`classes/rule.php`, `classes/cohort_manager.php`) would settle removal and manual-member handling.
- Canvas has no rule engine in the fetched material; Canvas SIS rules were not documented anywhere reachable.

## Sources

- https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-membership
- https://learn.microsoft.com/en-us/entra/identity/users/groups-create-rule
- https://help.okta.com/en-us/content/topics/users-groups-profiles/usgp-about-group-rules.htm
- https://support.okta.com/help/s/article/how-to-add-and-remove-users-from-groups-using-group-rules-and-exceptions
- https://support.okta.com/help/s/question/0D54z00009WkjHJCAZ/reactivating-of-a-group-rule-doesnt-add-user-to-the-group-if-user-was-manually-removed-from-it
- https://support.okta.com/help/s/article/what-happens-if-group-rules-are-deactivated-and-deleted
- https://developer.okta.com/docs/reference/api/groups/
- https://github.com/catalyst/moodle-tool_dynamic_cohorts
- https://marketplace.moodle.com/plugins/local_profilecohort
- https://marketplace.moodle.com/plugins/enrol_attributes
- https://tracker-old.moodle.org/browse/MDL-67445
- https://tracker-old.moodle.org/browse/MDL-37616
- https://community.canvaslms.com/t5/Admin-Group/Only-courses-with-blank-SIS-ID-are-considered-quot-Manually/m-p/159786
- https://open-edx-building-and-running-a-course.readthedocs.io/en/latest/manage_live_course/course_enrollment.html

status: ok · reason: Entra fully read; Okta, Moodle plugins and Canvas only partly reachable, gaps stated
