# Research: prior art for the `recommend` outcome

Topic `prior_art`. Question: what has already been tried for this, here or elsewhere, and what happened?

Evidence quality: the "here" half is read from the repo directly. The "elsewhere" half is thin. Public material on rule-driven recommendations is mostly vendor documentation, not bug reports. Two searches for stale-after-enrolment and cross-tenant leak reports found no defect reports, only documented intended behaviour. That absence is stated as a gap, not a finding.

## Here

### 1. Nothing has tried rule-made recommendations

- `git log` could not be run (no shell tool in this unit). The repo search found `RecommendedCourse` only in: the model, factory, admin, `queries.py`, the learner dashboard (`freedom_ls/learner_interface/views.py`), QA helper commands, and spec research files. No earlier spec built or attempted recommendations from rules.
- `freedom_ls/course_recommendations/` and `freedom_ls/registration_rules/` hold no `TODO` or `@claude` comments (grep returned nothing). The only open pointer is the commented-out `form_progress` FK and the module docstring "Keep this model standalone and additive" in `freedom_ls/course_recommendations/models.py`, both of which the idea says stay.
- `freedom_ls/role_based_permissions/registry.py:98-101` has four commented-out `recommendedcourse` permission lines. They are not a TODO, but they show recommendations have no role-based permission today. The idea does not need them (no educator screen until spec 4).

### 2. What `RecommendedCourse` is today

- Fields: `user` FK (CASCADE, `related_name="recommended_courses"`), `course` FK (CASCADE, `related_name="recommendations"`), `created_at`, plus `site` from `SiteAwareModel`. No uniqueness constraint, no creator, no organisation. `Meta.ordering = ["-created_at"]`.
- Created by: Django admin, `RecommendedCourseFactory`, QA helpers. No production code (`spec_dd/1. next/corporate-job-course-recommendations/research_fls_user_attributes_and_registrations.md` §3).
- Cleared by: self-registration only, `RecommendedCourse.objects.filter(user=request.user, course=course).delete()` at `freedom_ls/learner_interface/views.py:912-913`. Spec 2's `research_codebase.md` (line 324) recorded that rule-made registrations do not clear it, and left that to this spec.
- Read by: `get_recommended_courses(user)` in `queries.py` filters `RecommendedCourse.objects.filter(user=user)`, with `.objects` being the site-filtered manager. It is not scoped by organisation or by registration state. `_visible_recommendations` (views.py:183-207) then drops courses the visibility gate hides, sorts by newest then course slug, and the dashboard excludes recommended courses from "Available" (views.py:286, 502).
- Consequence for this spec: the dashboard does not itself hide a recommendation for a course the learner is registered on. Today only the self-registration `delete()` keeps the section honest. A rule-made or admin-made registration leaves a stale card. The idea's "every registration path clears the recommendation" closes that gap.
- Dashboard history (`spec_dd/3. done/2026-09-09_21:01_better-learner-dashboard-course-display/1. spec.md`, ~lines 125-130, 524-530): "RecommendedCourse rows are curated per learner and usually few, but nothing caps them", so the section is paginated. A form submission that writes several recommendations in one transaction produces tied `created_at` values, hence the slug tiebreak. A rule that recommends many courses at once to one learner would hit the same tie case, and a big rule run produces many rows per learner, which the pagination already copes with.
- `spec_dd/3. done/2026-08-30_08:06_final_pre_deploy_db_structure_cleanup/research_deletion_semantics.md` (lines 86-87, 227) confirmed `RecommendedCourse` is keyed on `User` and left its CASCADE deletes as they are.

### 3. What the registration-rules effort decided that lands here

From spec 2 (`spec_dd/3. done/2026-10-23_20:02_corporate-job-course-recommendations-2-registration-rules/1. spec.md`), items this spec reuses or must not contradict:

- **Provenance is a side table in the rules app**, not a column on the core model (decision 2). `RuleRegistration` is one-to-one to the registration, `rule` is `SET_NULL`, with a `rule_name` snapshot (decision 5). A core-model FK into an optional app would make core migrations depend on it. The idea says to use "the approach spec 2 chose": a recommendation-side table in the rules app, not a column on `RecommendedCourse`. Note the roadmap row for spec 3 still says "`RecommendedCourse` gains provenance". Reconcile the two: either a side table beside `RuleRegistration` (consistent with spec 2) or a column (which makes `course_recommendations` depend on the optional rules app). Spec 2's optional-app rule (decision 1, 1a; "no core app imports `freedom_ls.registration_rules`") settles it towards the side table.
- **The optional-app constraint also governs clearing.** Spec 2's `research_codebase.md` (lines 385-389) said spec 3's "clear on every registration path" must not import the rules app from core and should use a signal or a core-owned mechanism. Spec 2 already has one `post_save` receiver on `LearnerCourseRegistration` (`freedom_ls/learner_progress/signals.py`, `_ensure_and_announce`) that mints progress and raises `course.registered` for every path. That receiver is the natural single place to clear a recommendation. Does `course_recommendations` get imported by `learner_progress`? Check `test_organisation/import_contracts.toml` before choosing; the earlier `lint-imports` contract failed builds in spec 2 (plan.md line 168 raised the same question for `learner_interface`).
- **`RuleState`, the kind seam and `matching_learners`** are built so "preview and evaluation run the same query" (spec 2 Requirements, rule-kind seam). A recommend outcome reuses `matching_learners` and `classify_rule_changes`/`apply_rule_changes`. Spec 2's `RegistrationRule.outcome` has one choice, `REGISTER`, "designed as a choice with one value so spec 3 adds `recommend` without reshaping rules" (spec 2 `idea.md` line 14).
- **`started_course_exists`** in `learner_progress` was added for retraction and the spec says "Spec 3 reuses it". It is about retracting a registration. For a recommendation, "started" is irrelevant (a recommendation is removed outright). The reuse is probably limited to the "already registered" skip (which is a registration-exists check, not a started check). Do not copy the started-gate onto recommendations.
- **Hand-over and ownership** (decision 10) work by re-pointing a row at another enabled rule. The idea's "if another enabled rule still matches, the recommendation stays" is the same mechanism; the open question is whether the row is re-pointed (as spec 2 does) or deleted and re-created.
- **`evaluate_learner` scope** already covers "every registration of the learner that any rule owns", so a learner who moved organisation is retracted from the old organisation's rules. Recommendations owned by a rule need the same coverage, and this is the concrete shape of the idea's open organisation-scoping question: a user in two organisations has one `User` but two `Learner` rows, and `RecommendedCourse` has no `Learner`.
- **Entry protection, deletion order and `danger_content_delete`.** Spec 2 added `RegistrationRule.course` as `PROTECT` and appended the rule delete to `deletion_order`. If recommendation provenance rows have a `PROTECT`/`SET_NULL` on the rule or the course, `danger_content_delete` and its order need the same check.
- **Webhooks / notifications.** Spec 2 made `course.registered` fire from a task. Recommendations raise none (idea), so nothing in `fire_webhook_event_for_site` is reused.
- **Upgrade notes** (spec 2): new optional app, migrations, the task worker (`manage.py fls_run_worker`) must run in production or rules never apply, `for_picker` signature change, registration webhooks fire outside requests. For spec 3 the upgrade-note items likely are: a new migration on the rules app (and maybe `course_recommendations` if a uniqueness constraint is added), a uniqueness constraint on `(user, course)` that fails to apply if production already holds duplicates (the model has no constraint today, and admin-made duplicates are possible), and the `Outcome` choice gaining `recommend`. The duplicate-data migration risk is the one to plan for.

### 4. QA findings from spec 2 that bear on this spec

From `qa_report.md` in the spec 2 folder (0 bugs, 35 test rows, all pass):

- The preview page, hand-over, flapping and switch-off/on cases all behaved as specified. The plan disagreed with the spec in five places (empty `last_evaluated_at` after create, hand-over before the started check, switch-off warning timing, owned rows after hand-over, Chrome ERR_CACHE_MISS on the POST preview). The code followed the spec each time. Lesson for the spec 3 QA plan: write expected results from the spec's evaluation rules, not from intuition.
- An observation worth carrying: "After 4.5, an active registration owned by a disabled rule stayed with it until a later evaluation handed it to the enabled matching rule." Ownership can lag until the next evaluation. A recommendation hand-over needs the same lag tolerance, and the preview should be described as a forecast (spec 2 decision 8).
- The preview lists names under "Will be registered", "Will be retracted" and "Stops matching but stays registered". The recommend outcome needs analogous headings ("Will be recommended", "Recommendation will be removed"), and a "stays recommended: another rule matches" reason. The third list's "started" reason does not apply.
- Reusable QA seed: `qa_create_registration_rules_scenario` (added by the spec 2 QA data helper), plus `qa_create_rich_dashboard_learner` and `qa_create_dashboard_paging_fixtures` for recommended-section fixtures. The `.claude/agent-memory/fls-dev-qa-data-helper/` notes (`reference_dashboard_paging_fixture_teardown.md`, `reference_demodev_s1_fixture_collisions.md`) record that seed E writes four recommendations for `demodev_s1` and collides with other fixtures. A rule-made recommendation fixture should avoid that learner.
- Spec 2's `research_known_complaints.md` listed complaints about registration; two apply to recommendations too: provenance detail ("why am I seeing this"), and preview-versus-run drift. The learner-facing "why am I in this course" complaint is inferred there, not sourced.

### 5. Open items on the roadmap that land on this spec

From `spec_dd/1. next/roadmap.md` (lines 359-484):

- Unknowns table row: "How organisation-owned rules scope `RecommendedCourse`, which is keyed on `User`, not `Learner`." Owner: 3. Affects: 4.
- Roadmap caution: "Spec 3 edits the self-registration view in `learner_interface`" (clearing is already there, so the edit is probably to keep or move it).
- Decisions 6, 7, 11, 12 and the "No recommendation for a learner already registered" and "A recommendation raises no notification" assumptions are already settled and match the idea.
- `educator-interface-11-audit-log` should record rule actions (spec 2 added a line to its idea). Recommendation create and remove by rules are the same class of action.

## Elsewhere

### 6. Vendors that offer both outcomes from one rule

Already summarised in `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (lines 16, 28, 44, 66-69, 118-119); not repeated beyond what bears on this spec:

- Totara "visible learning" is a visibility tier separate from enrolment. https://totara.help/docs/dynamic-audience-settings . In audience-based visibility, removing a learning item from the Visible learning list also removes the audience-based visibility settings (search result excerpt of https://totara.help/19/docs/dynamic-audience-settings). Dynamic audiences are "always live": a user who stops matching all rules is dropped from the audience (a 2015 staff forum reply; old, check against the version). Forum answers (2019) say that once a user leaves an audience, the program is no longer visible, but progress still appears in their Record of Learning. Lesson: a recommendation vanishing when the match ends is accepted vendor behaviour; the learner keeps any history.
- SAP SuccessFactors Learning: recommendations are attached to an assignment profile and shown on a Recommended tile; items already in the learner's plan or already completed do not appear. https://userapps.support.sap.com/sap/support/knowledge/en/2336483 . Lesson: SAP filters out registered items at read time as well as, presumably, at write time. The FLS dashboard does not filter registered courses out of the recommended section at read time (§2). A read-time guard in addition to clearing on every path is a possible belt and braces choice, not required by the idea.
- Arcoro: courses can be required or recommended by criteria; required show as assigned, recommended in the catalog; a rule-assigned course can be removed only through its rule. https://support.arcoro.com/hc/en-us/articles/360051795874 . The "only through the rule" lock is the counterpart of the idea's "rules never take over rows" (admin-made recommendations stay admin-made).
- OasisLMS: recommendation logic drops courses a user has already started; visibility rules apply to recommendations, so hidden courses do not surface. https://university.oasis-lms.com/AssetListing/How-recommendation-works-in-OasisLMS-11833/User-Experience-in-Evergreen-Recommendation-23071 . FLS already routes recommendations through `filter_visible` (views.py:183-207), so this matches.
- No public report was found of a duplicate or stale recommendation after enrolment from a rule engine. Searches returned vendor docs describing the intended filtering (SAP, Oasis), not defects. Treat "stale after enrolment" as a design-time risk (FLS's own §2 gap), not a documented field failure.

### 7. Retraction surprises

- Moodle: unenrolled users lose course data and leave the gradebook, while suspended ones keep it; cohort sync's unenrol action is site-wide. https://moodle.org/mod/forum/discuss.php?d=419477 . Docebo's design group notes a single "stopped matching" signal is too blunt. https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576 . These concern registrations. A recommendation has no learner data to lose, so retracting is the low-risk case, which supports the idea's "unmatching removes it" with no started-gate. Spec 2's `research_known_complaints.md` §1-2 covers the registration side.
- Moodle Workplace: actions do not reapply while a user keeps matching; "rule action limits" cap repeats. https://docs.moodle.org/501/en/Dynamic_rules . It also auto-disables a rule whose condition or action becomes invalid. A recommend rule on a course later deleted or hidden has the same problem. FLS: `RegistrationRule.course` is `PROTECT`, and `_visible_recommendations` hides courses the gate hides, so no extra work is needed.
- Flapping: a learner whose attribute flaps gets a recommendation created and removed repeatedly (Totara-style live audiences). Spec 2 handled this for registrations by never deleting. For recommendations the equivalent cost is only churn in `created_at` (new rows sort to the top of the section each time they come back). Consider whether re-creation after unmatching should reset `created_at`; the idea does not say.

### 8. Multi-tenant scoping

- Moodle Workplace: a dynamic rule's `IF <conditions> THEN <actions>` runs only against active users in the tenant that owns the rule; cross-tenant ("Shared space") rules may use only shared items, and are editable only in the shared space. https://docs.moodle.org/en/Dynamic_rules_Tenants , https://docs.moodle.org/503/en/Dynamic_rules_Tenants (the 5.03 page is marked work in progress). Lesson: Moodle scopes by the rule's owner (its tenant), the same shape as FLS's organisation-owned rules. No public tenant-leak bug was found; the search returned documentation only.
- FLS's own scoping split: sites are enforced by `SiteAwareModel` managers; organisations are enforced by explicit filters in the rules app (spec 2's `matching_learners` filters `site_id` and `organisation_id` explicitly). `RecommendedCourse` has `site` but no organisation, and the dashboard reads by `user` and site only. So a rule from one organisation can create a row that a user who also belongs to a second organisation (on the same site) sees. That is the idea's open question. Moodle's answer (a rule only acts on its own tenant's users and the user sees one tenant at a time) does not map directly: FLS dashboards are per user, not per organisation.

## Summary of what this means for the spec

1. No prior attempt exists; the closest precedent is spec 2's own mechanism (side-table provenance in the optional rules app, reconcile-from-current-state, preview from the same query).
2. Provenance: the roadmap row says `RecommendedCourse` gains it; spec 2's optional-app rule points to a side table in the rules app. Reconcile the wording.
3. Clearing on every registration path should use the existing core `post_save` on `LearnerCourseRegistration` (the same receiver that mints progress), not an import of the rules app. Check the import contracts.
4. Adding a `(user, course)` uniqueness constraint needs a migration that copes with existing duplicates; flag this in upgrade notes.
5. The dashboard has no read-time guard for registered courses. Only clearing keeps it honest.
6. Organisation scoping stays open: the evidence elsewhere (Moodle Workplace) scopes by the rule's owning tenant, with no public leak reports found.
7. Spec 2's "started" gate and "stays registered" list do not apply to recommendations; reuse only the "already registered" check.

## References

- https://totara.help/docs/dynamic-audience-settings
- https://totara.help/19/docs/dynamic-audience-settings
- https://userapps.support.sap.com/sap/support/knowledge/en/2336483
- https://support.arcoro.com/hc/en-us/articles/360051795874
- https://university.oasis-lms.com/AssetListing/How-recommendation-works-in-OasisLMS-11833/User-Experience-in-Evergreen-Recommendation-23071
- https://moodle.org/mod/forum/discuss.php?d=419477
- https://community.docebo.com/pdg-enrollment-unenrollment-automation-142/welcome-to-the-pdg-for-the-enrollment-rules-engine-ere-15576
- https://docs.moodle.org/501/en/Dynamic_rules
- https://docs.moodle.org/en/Dynamic_rules_Tenants
- https://docs.moodle.org/503/en/Dynamic_rules_Tenants

status: ok
