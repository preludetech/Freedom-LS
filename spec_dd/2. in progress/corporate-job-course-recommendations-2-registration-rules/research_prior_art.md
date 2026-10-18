# Research: prior art for rule-based automatic registration

Topic `prior_art`. Question: what has already been tried for rule-based automatic course registration, in FreedomLS and elsewhere, and what happened? Vendor terms (enrolment, assignment, audience) are kept for other systems; FLS says "registration". Searches used Grep/Glob over `spec_dd/` (including `3. done` and `0. noop`), `docs/` and `freedom_ls/`. No Bash, so no `git log` was read.

## 1. In FreedomLS

### 1.1 Headline: nothing automatic has shipped, and nothing was tried and dropped

- No earlier attempt at rule-based, bulk-by-attribute or cohort-auto-fill registration exists in the code, in `3. done` or in `0. noop`. The grep for auto-register, auto-enrol, bulk registration, registration rule and dynamic group found hits only in the current effort (roadmap "Registration rules", ideas 2 to 5, the `corporate-job-course-recommendations` parent) and in unrelated research files.
- `docs/product/roadmap.md` lines 61 to 68 list "auto-enrolment on launch" and notify-on-launch as not built. The coming-soon-courses spec (`spec_dd/3. done/2026-07-03_07:52_courses_coming_soon/1. spec.md` line 54, `idea.md` line 185) put "auto-enrolling interested students on launch" explicitly out of scope; its `research_waitlist_ux.md` (lines 114 to 123) rejected auto-enrol as a default, because it "may create unwanted enrolments; user didn't explicitly enrol". It was deferred, not tried.
- Item 12 of `spec_dd/corporate-readiness/README.md` (lines 248 to 259) is the origin. It suggests the output be ordinary `CohortCourseRegistration` or `LearnerCourseRegistration` rows and floats "rule-maintained (dynamic) cohorts" as "the cheapest way in". The current effort then took the opposite side on cohorts (roadmap decision 3: rules write one `LearnerCourseRegistration` per learner, no rule-filled cohorts, because they change what cohort reports, cohort deadlines and cohort-scoped roles see). So the dynamic-cohort idea was considered and rejected on paper, never built.
- Applications are deliberately not auto-enrolment: `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/0. idea.md` line 78 ("Approval is not enrolment"), with `research_reference_implementations.md` lines 165 to 173 noting that selective or high-stakes flows decouple approval from enrolment, and Moodle `enrol_apply` / `enrol_gapply` auto-enrol as the lightweight path. The same decision recurs in `application-review-ui` (research_review_workflow.md line 7, idea.md line 316).
- Bulk registration by humans is the nearest shipped thing: `educator-interface-3-panel-framework-dialogs` `research_domain_events.md` (lines 24, 156) records "bulk register/unregister course" as an event shape for spec 8 (`educator-interface-8-bulk-operations`, still in `1. next`). Bulk registration is therefore specified but not built.

### 1.2 What exists today that rules must fit

From `research_fls_user_attributes_and_registrations.md` (parent effort) and `freedom_ls/learner_management/models.py` line 153:
- `LearnerCourseRegistration` has only the boolean `self_registered` as provenance. `self_registered=False` means "registered by staff"; a rule-made row would be indistinguishable (research lines 21, 216 to 233). `CohortCourseRegistration` has no source field at all.
- `self_registered` was added in migration `0002_learnercourseregistration_self_registered`, shipped with `user-communication-1-notifications-core` (its upgrade notes line 36), to drive the `course.registered` notification. The code comment deliberately sets it only on create so reactivation does not change who made the row (research line 176). That is the existing precedent for "do not change who made a row when reactivating" and matches the idea's "never take over, reactivate only your own".
- Registrations are minted by a signal path: `learner_progress.signals` creates progress records on `post_save` of `LearnerCourseRegistration`, `CohortCourseRegistration`, `CohortMembership`. The better-course-progress-tracking upgrade notes (`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/upgrade_notes.md` lines 77 to 85) state the lesson that matters for a rule engine: `bulk_create` does not fire `post_save`, so any bulk writer "must call `ensure_course_progress_record()`" itself, and percentage recalculation is likewise needed after `update()` / `bulk_create()` / `bulk_update()`. A rule evaluator that uses `bulk_create` for speed will silently skip progress-record creation and anything else hung on the signal.
- `learners-associated-with-organisations` research (`research_migration_and_autocreation.md` lines 225 to 255) is a repo-internal warning about signal-based "when X is created, make Y" automation: it needed two wiring points for Site creation alone, is blind to `bulk_create`, fires in every factory call (about 366 call sites), and is invisible at the call site. It also names a future bulk-enrolment feature reaching for `bulk_create` as the exact way such sync gets silently broken.
- `fire_webhook_event` / `course.registered`: `UserCourseRegistration.save()` precedent fires a webhook from `save()` when `_state.adding`; the spec's open question (webhook outside a request) comes from this. See parent `research_fls_backends_and_toggles.md` §4.

### 1.3 Progress-tracking design assumption that rules break

`research_enrolment_bound_progress_lifecycle.md` (better-course-progress-tracking, §3, lines 191 to 229) records that FLS's safety rests on "registrations are only ever created and deactivated by a human act". A rule engine is the first feature to deactivate rows without a human act, so this assumption is knowingly void. That document's evidence (below, section 2.3) is the reason the idea says "progress is never deleted" and retracts only by `is_active=False`.

### 1.4 What was dropped or decided against, and why (the current effort's own history)

From the parent `research_enrolment_rule_engines.md` §4 options and roadmap "Decisions already taken":
- Option A (rule fills a Cohort, existing `CohortCourseRegistration` does the rest): rejected, decision 3.
- Option C alone (recommend only): rejected as insufficient for mandatory compliance; kept as the second outcome (spec 3).
- Option D (pluggable outcome/backends): outcome kept as a one-valued choice, with the rule-kind seam, but the research warned "do not build the interface until a second backend exists"; spec 2 resolves that by shipping the seam with one kind (decision 14).
- Option B (direct rows with provenance) was chosen.
- Docebo-style non-retroactivity was rejected in favour of Moodle Workplace's run-on-enable (decision 5).
- Org-defined custom attributes, SCIM/SSO sync and rule-filled cohorts are out of scope for all five specs.

## 2. Elsewhere: what happened

Sources marked (excerpt) were search-result excerpts in the earlier parent research because the vendor pages returned 403 to the fetcher; they are carried forward, not re-verified.

### 2.1 Vendor engines (from parent `research_enrolment_rule_engines.md`, condensed)

- Docebo Enrollment Rules: group- or branch-triggered, not retroactive (admins use a "drop everyone out of the group and back in" workaround), no automatic unenrol, group-OR-branch limit, admins asking for rule/group visibility and unenrol reasons; Docebo is building an engine "independent from" groups. https://community.docebo.com/product-q-a-7/enrollment-rules-6746 , https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576 , https://help.docebo.com/hc/en-us/articles/360020128579-Activating-and-managing-the-Enrollment-rules-app
- Cornerstone: daily batch of dynamic groups; Dynamic Removal off by default and in-progress training kept unless a separate switch is on; removal only after leaving all overlapping assignments; reassignment only of what dynamic removal itself removed. https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Removal.htm (excerpt), https://help.csod.com/help/csod_0/Content/Learning_Assignment_Tool/Dynamic_Reassignment/Dynamic_Reassignment_Overview.htm (excerpt)
- Absorb: rules re-run on course or profile edit; auto-unenrol is support-enabled only and not-started only; the count preview is disputed and customers fear one edit unenrolling thousands. https://support.absorblms.com/hc/en-us/articles/22708205949587-Creating-Enrollment-Rules (excerpt), https://ideas.absorblms.com/ideas/LMS-I-49 (summary only; login-gated)
- Moodle Workplace dynamic rules: preview shows a count and a user list; enabling runs once as an ad-hoc task; actions do not reapply while a user keeps matching but may reapply after unmatch then rematch, capped by "rule action limits"; a rule with an invalid condition or action is auto-disabled and flagged. https://docs.moodle.org/501/en/Dynamic_rules , https://docs.moodle.org/501/en/Dynamic_rules_Configuration
- Totara dynamic audiences: see 2.2.
- SmarterU lists failed automated enrolments with per-row reasons: https://support.smarteru.com/docs/troubleshooting-made-easy-with-recommended-enrollments

### 2.2 Documented failures

1. Mass unenrolment with data loss (Totara). Audience sync is the most common cause of unexpected unenrolment because membership changes for unrelated reasons. The default "Unenrol the user from course" external-unenrol setting deletes course progress and grades while keeping the completion record; "Disable course enrolment" keeps them. One admin reported losing about 1,700 records after a default setting removed data, and recommended disable-over-unenrol. Totara's fix: "Disable course enrolment and remove roles", after which re-enrolment restores grades. https://totara.community/mod/forum/discuss.php?d=23613 , https://totara.help/docs/unenrolling-users , https://totara.help/docs/what-is-an-audience
   Lesson for FLS: retract by `is_active=False` only, never delete; reactivation must be able to restore progress (the idea already does this).
2. Dynamic membership dropping people who should keep access (Totara). Dynamic audience rules are continuously re-evaluated, and a learner who stops matching loses everything granted through the audience. Recurring certification windows broke "course completion" rules because completions move to history; the workaround (OR "is assigned to the program") also keeps people who should leave. https://totara.community/mod/forum/discuss.php?d=16374 , https://totara.community/mod/forum/discuss.php?d=16454 , https://totara.community/mod/forum/discuss.php?d=28202
   Lesson: a single "stopped matching" signal is too blunt; the idea's "started means leave alone" and "another enabled rule blocks retraction" address this.
3. Sync as failure amplifier (Moodle cohort sync, Canvas SIS). Because cohort membership comes from external feeds, every add/remove cycle in the source becomes an unenrol/re-enrol cycle and a tracking-data-loss event; admins built a double-enrolment workaround so cohort sync could not touch grades. Canvas SIS "full batch" imports delete enrolments absent from a truncated or malformed file; Instructure titles posts "Admins beware: An SIS import error has plagued Canvas since 2017". No single dated postmortem was verified; the evidence is a recurring pattern. https://moodle.org/mod/forum/discuss.php?d=365898 , https://community.instructure.com/t5/Canvas-LMS-Blog/Admins-beware-An-SIS-import-error-has-plagued-Canvas-since-2017/ba-p/613180 , https://community.instructure.com/en/discussion/415514/sis-import-batch-mode-deletes-courses-enrollments-we-include-in-csv-files
   Lesson: rules must never delete, and a bad attribute import (spec 5) is the likeliest trigger for a mass retraction. The preview-before-change plus not-started-only rule limits the blast radius.
4. Blast radius from one admin edit (Docebo, Absorb). A Docebo thread describes a change enrolling users in every course and an admin enrolling 100,000+ users, slowing the system, resolved through the Audit Trail; Absorb customers fear one edit unenrolling thousands and one had a vendor-run script every two hours to unenrol non-matching learners. https://community.docebo.com/product-q-a-7/users-being-enrolled-into-category-they-should-not-be-7492 (excerpt), https://ideas.absorblms.com/ideas/LMS-I-49 , https://ideas.absorblms.com/ideas/LMS-I-676 (summaries)
   Lesson: list-not-count preview, audit trail of rule actions (the idea's audit-log hook), and background execution.
5. Preview that lies. Absorb's count preview can disagree with the post-save result. Lesson: preview and apply must share one evaluation function so they cannot diverge. Moodle Workplace and SmarterU (user list, failure reasons) are the better models.
6. Manual vs rule overlap. Moodle `enrol_attributes` users report its enrolments cannot be suspended or removed and re-enrol anyway (https://moodle.org/plugins/enrol_attributes , excerpt); Cornerstone greys out manual removal while an assignment is dynamic; Absorb manual enrolment bypasses rules; Arcoro rule-assigned courses are removable only through the rule; TalentLMS manually-added members are not auto-enrolled. Lesson: the idea's "never take over an existing row, never reactivate a staff-deactivated row" is the cleanest of these and avoids "re-enrols anyway".
7. Repeat firing. Moodle Workplace may reapply an action when a user stops matching and matches again, hence "rule action limits". FLS equivalent: a match, unmatch, rematch cycle must reactivate the rule's own row rather than create a second one or re-send `course.registered`. No reported infinite rule loop was found; rule-triggered-by-rule chaining exists only in Docebo (Group B = "in Ops AND completed course 1"), and FLS rules key on HR attributes only, so a registration cannot cause another rule to match.
8. Notification floods on mass runs: Totara offers per-audience alert modes, Absorb needs course-level and portal-level switches, Docebo sends no unenrol notifications. The idea's decision 10 (rule-made rows send `course.registered`) means enabling a rule on a large organisation sends one notification per learner; this is an open risk with no precedent resolution beyond opt-in alert modes.
9. Performance. Cornerstone chose a daily batch (first run about ten minutes); Totara runs audience changes in the background and large removals take minutes; Docebo PDG notes continuous rules add load. Moodle Workplace scans "course not completed"-type conditions on cron every run (inference, not documented as a defect). A targeted search found no reported performance defect or migration-away write-up for audience sync. Not found: published numbers.
10. Migrations away. Only Docebo's move towards an engine independent of groups was found (fusing membership and enrolment was the pain). No LMS migration-away story attributable to rule engines was found; stated as a gap.

### 2.3 What worked (patterns to copy)

- Not-started-only, opt-in unenrol (Cornerstone, Absorb).
- Reactivate only what the rule itself removed (Cornerstone Dynamic Reassignment).
- Retroactive on enable via one background task (Moodle Workplace).
- Per-person provenance (Cornerstone LAT, Absorb), which Docebo admins explicitly ask for.
- Auto-disable a rule whose course or condition target becomes invalid (Moodle Workplace). The idea does not state this; a deleted or archived course, or a deactivated list entry, is the FLS version.
- Controlled-vocabulary attributes (departments, titles) rather than free text; Penn Medicine guidance warns against matching on personal IDs. https://www.uphs.upenn.edu/EMPLOYEESELFSERVICE/STRATEGICLEARNING/KL/docs_new/Assignment%20Profile%20Attribute%20Formats.pdf (excerpt). FLS spec 1 already uses organisation lists.

## 3. Findings the spec should act on

1. There is no FLS prior attempt to inherit or avoid; the relevant FLS lessons are the `post_save` / `bulk_create` blind spot (upgrade notes lines 77 to 85) and the `self_registered` "set only on create" convention.
2. The better-course-progress-tracking assumption that registrations change only by human act no longer holds once rules exist; the spec should say which progress behaviours depend on it.
3. Preview and apply should share one evaluation function (Absorb discrepancy).
4. Define what a rematch does to a row the rule previously deactivated: reactivate, no second row, no second `course.registered` (Moodle repeat firing).
5. Decide notification volume on enable for a large organisation; no vendor solution to copy except opt-in alert modes.
6. Consider auto-disable or a flag when a rule's course is archived or deleted (Moodle Workplace).
7. A bad bulk attribute change (spec 5 CSV import, later SCIM) is the realistic trigger for mass retraction; the not-started-only rule and preview are the guard.

status: ok · reason: complete; no prior FLS attempt exists, web evidence from prior research plus Totara and Moodle searches; performance and migration-away evidence not found
