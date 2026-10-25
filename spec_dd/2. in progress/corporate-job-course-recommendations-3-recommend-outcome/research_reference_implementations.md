# Research: reference implementations of a rule outcome that recommends a course

Scope: how other products let a rule (driven by user attributes) put a course in front of a learner as a suggestion, without assigning it, and how they treat provenance, overlapping rules, registration, unmatching, preview and multi-organisation users. This goes deeper than `spec_dd/1. next/corporate-job-course-recommendations/research_enrolment_rule_engines.md` (which covers rule engines for assignment) and does not repeat its per-product tables. Vendor terms ("enrol", "assignment", "audience", "campaign") are kept and attributed. FLS terms ("registration", `RecommendedCourse`, "organisation") are used only in section 4.

Evidence quality: the honest headline is that **public documentation for rule-driven recommendation is thin**. Most products' "recommended" feature is either machine-learned (Totara, Workday, Cornerstone, Canvas Catalog, Moodle blocks) or a catalog-ordering feature, not a per-learner row with a lifecycle. Several vendor pages returned 403/404 to the fetcher (Arcoro, SAP KB 2336483, SAP Learning Academy page). Claims from search-result summaries are marked "(excerpt)". Where nothing was found it says "Not found" rather than filling from memory. Anything from model knowledge is labelled "(model knowledge, unverified)".

## 1. Per-product findings

### Totara
- Two tiers on an audience: "Enrolled learning" (assignment) and "Visible learning" (catalogue visibility only; options No users / All users / Enrolled users only / Enrolled users and members of selected audience; needs "audience-based visibility" enabled). Visible learning is **not** a recommendation: it gates what a learner may see, it does not push anything onto the learner. https://totara.help/docs/dynamic-audience-settings (fetched this session).
- The same page documents add-enrolled-learning is processed in the background for existing users and removal "may take minutes ... depending on audience size". It does **not** say what happens to enrolments when a member leaves the audience (fetched; the earlier research file's claim comes from a forum reply, https://totara.community/mod/forum/discuss.php?d=16374).
- Totara "Recommended for you" is a separate machine-learning feature (Totara 15+ via Machine Learning Service; legacy recommender deprecated in 17). It suggests Engage and Learn content, ranks already-enrolled courses lower and excludes joined workspaces. It is a dashboard/profile block. No link from audience rules to this block was found. https://totara.help/17/docs/what-are-recommendations, https://totara.help/18/docs/what-are-recommendations, https://totara.help/15/docs/what-are-recommendations (excerpts).
- Takeaway: the idea.md claim that Totara "visible learning" offers a rule-driven recommend outcome is a loose fit. Visible learning is the nearest rule-driven non-assignment tier, but it is audience-based gating, not a per-learner recommendation row. Do not cite it as precedent for a row model.

### SAP SuccessFactors Learning
- Assignment profiles can also **recommend** specific items, programs or collections based on user attributes, described as promoting content rather than mandatory assignment. Source: SAP Learning Academy "Assigning Learning Automatically" (search excerpt): https://learning.sap.com/courses/sap-successfactors-learning-academy/assigning-learning-needs-to-users-automatically . The page itself returned 404 to direct fetch under a slightly different URL, so the storage of recommended items and the conversion on enrolment are **not documented** in what was reachable.
- Propagation is explicit: "Propagate Assignment profile" applies changes after you edit the profile's items. Deactivating a profile stops future assignments but keeps existing ones; "Deactivate and Unassign" removes them. Removing an item from a user's Assigned Items does not withdraw the class registration (known issue, enhancement request 209531); SAP advises withdrawing the registration instead, which clears both the registration and the plan item. https://userapps.support.sap.com/sap/support/knowledge/en/2678347, https://userapps.support.sap.com/sap/support/knowledge/en/2335740 (excerpts).
- Takeaway: SAP has a two-step disable (deactivate keeps; deactivate-and-unassign removes). Two linked records (plan item vs registration) drift apart when one is removed without the other. Both are cautionary for FLS where the recommendation and the registration are separate rows.

### Arcoro
- Courses can be made required or recommended when users meet criteria such as department; required appear under assigned, recommended in the catalog; a course assigned through a rule can only be removed through that rule. https://support.arcoro.com/hc/en-us/articles/360051795874 (the earlier file's excerpt; this session the page returned 403 and a follow-up search found no further Arcoro text on recommended-vs-required, so lifecycle on enrolment/unmatch is **not found**).
- Takeaway: the "removable only through the rule" pattern is the product-level analogue of FLS "rule-made rows are only retracted by rules; admin-made rows are never retracted by rules".

### Workday Learning
- "Required for You" is campaign-driven; "Recommended for You" is a separate ML-driven worklet (needs ML enabled; draws on completions, profile and similar-role patterns; hidden when empty). No evidence a campaign can be marked "recommended". https://doc.workday.com/admin-guide/en-us/human-capital-management/learning/learning-content/chr1460991670411.html (excerpt).
- Campaign audiences support dynamic updates: learners are removed when they no longer meet audience criteria; learners who already completed the content are skipped even if they completed it outside the campaign. Same source (excerpt). Useful as the "skip if already done" precedent, for the assignment outcome.
- Takeaway: Workday shows the split rule-driven-required vs model-driven-recommended is the industry norm. Rule-driven recommendation rows are the less common design.

### MangoApps (small vendor, but the only found admin-rule recommender with docs)
- Admin sets a default recommendation category plus rules; each rule has criteria (Admin Role, Availability, Department, Language, Level, Team), ANDed, and picks a **course category** to show. Users matching no rule see the default. Multiple rules for different segments. https://guides.mangoapps.com/lms-guide/learn-admin/recommendations (fetched).
- The page says nothing on enrolment, unmatch or preview. Notably there are **no stored per-learner rows**: it is evaluated at display time against the learner's attributes. That is the "computed, not materialised" design.
- Takeaway: this is the natural counter-design to a materialised `RecommendedCourse` row: no retraction, no provenance, no staleness, but also no admin-made rows, no "why", and no query "who has been recommended X" without re-evaluating.

### Moodle
- Cohort sync: add/remove from a cohort enrols/unenrols automatically ("enrolment is synchronised"). https://docs.moodle.org/501/en/Cohort_sync (fetched). The external unenrol action (unenrol vs suspend) is per tracker MDL-37616 (excerpt, see earlier research). That the enrolment row records which enrolment instance created it (so removing one method keeps another) is model knowledge, unverified here, but is the same "per-source ownership, remove only when no source remains" idea as Cornerstone's overlap behaviour.
- Recommendation plugins on moodle.org are not rule-driven by HR attribute: `block_recommend_course` (peer recommendation; learners recommend to each other; dashboard cards; admin history of who recommended what to whom and a stats page), `block_datacurso_recomendate` (AI), `block_course_recommender` (learner-chosen interest tags), `block_recommender` (OU, popularity; Moodle 2.4 era). None targets by cohort or profile field. https://moodle.org/plugins/block_recommend_course, https://moodle.org/plugins/block_datacurso_recomendate, https://moodle.org/plugins/block_course_recommender (search excerpts).
- Interesting detail: `block_recommend_course` stores a **recommender -> recipient -> course** history that admins can read. That is a provenance record (who made this suggestion) for a human actor, analogous to FLS storing which rule made a row.
- Workplace dynamic rules (earlier research) remain the closest Moodle analogue for preview (count + user list before enabling) and for "actions do not reapply while a user keeps matching".

### Open edX and Canvas
- Open edX: learner dashboard lists enrolled courses; no recommendation section found; the closest rule-ish plugin is Course Access Groups, which assigns learners to a group at registration to control visibility/enrolment, not to recommend. https://docs.openedx.org/en/ulmo/learners/concepts/open_edx_platform/what_is_course_dashboard.html, https://pypi.org/project/course-access-groups/ (excerpts).
- Canvas Catalog: recommendations come from enrolment co-occurrence ("Frequently Bought Together") and fall back to popular/trending courses; no attribute rule. https://community.canvaslms.com/t5/The-Product-Blog/New-in-Canvas-Catalog-Course-Recommendations-Based-on-Real/ba-p/638062 (excerpt).
- Takeaway: neither is a reference for this outcome. Report as "no precedent".

### Cornerstone, Docebo
- Rule-based outputs are assignments only. Cornerstone recommendations are AI/profile-driven (https://help.csod.com/skills-studio/ss-help-get-started/topics/ss-help-about-learning-recommendations.html, excerpt). No rule-driven "recommended" found for Docebo. See the earlier research for unmatch/overlap detail; the relevant carry-over for this spec is Cornerstone's "remove only after leaving all overlapping assignments" and "dynamic reassignment only re-adds what dynamic removal itself removed".

### Open-source rule-engine patterns (generic, no product)
- Not found: a documented open-source LMS with rule-driven recommendation rows. What does exist is the generic **reconciliation** pattern used by Kubernetes-style controllers and by Django permission/group sync code: compute the desired set from the rule, diff against existing owned rows, create the missing, delete the surplus, touch nothing not owned. (model knowledge, unverified here; it is how the settled behaviours in idea.md can be stated as a single idempotent function.)

## 2. Comparison for the recommend outcome

| Product | Rule-driven recommend? | Stored per-learner row? | Provenance | On registration | On unmatch / disable | Overlap | Preview |
|---|---|---|---|---|---|---|---|
| SAP SF Learning | yes, via assignment profile (excerpt) | not documented | profile | not documented | deactivate keeps; deactivate-and-unassign removes; propagate is explicit | not documented | not found |
| Arcoro | yes, required or recommended per criteria (excerpt) | not documented | the rule (removable only through it) | not found | not found | not found | not found |
| Totara | no; "visible learning" gates visibility only; recommendations are ML | n/a | n/a | ML ranks enrolled courses lower | n/a | n/a | n/a |
| Workday | no; campaigns are required, recommended is ML | n/a | campaign | completed content skipped | dynamic audience removes on unmatch | n/a | not found |
| MangoApps | yes, rule maps criteria to a category | no, computed at display | none needed | not documented | automatic (re-evaluated) | default category when none match; multiple rules supported | not documented |
| Moodle plugins | peer/AI/tag only | yes for peer plugin (recommender -> recipient -> course) | recommender user | not documented | n/a | n/a | admin history page |
| Open edX, Canvas | no | n/a | n/a | n/a | n/a | n/a | n/a |

## 3. What the references tell us, topic by topic

1. **Data model for recommendation rows.** Only two designs are visible: computed at display time (MangoApps, Workday/Totara ML) or a stored row keyed learner + course with an actor (Moodle `block_recommend_course`). No source documents a unique constraint; MangoApps avoids the need by not storing. A stored row needs a uniqueness constraint to make evaluation idempotent; this is not in any reference and must be a FLS decision (already settled in idea.md).
2. **Provenance.** Arcoro's "only removable through its rule" and Moodle's recommender-on-row are the two precedents. Both mean the row carries its source. SAP's drift between plan item and registration shows what happens without a single owner.
3. **Overlapping rules.** The only documented behaviour is Cornerstone's "remove only after all matching assignments are gone" (from the earlier file) and MangoApps's AND-within-rule, multiple rules per segment. Nothing documents what a recommend rule and an assign rule for the same course should do together; the natural reading (registration wins, recommendation cleared) agrees with Workday skipping learners who already completed content and Totara ranking enrolled courses lower.
4. **When the learner registers.** No reference documents clearing a stored recommendation on registration from every path. The nearest are Workday (completed content skipped) and Totara (enrolled ranks lower), both computed. In a stored-row design, clearing on every path is therefore FLS's own responsibility and cannot be borrowed.
5. **Unmatching and disable.** Disable has two models in SAP: stop-future-only vs also-unassign. For recommendations, which carry no progress, removal is the low-risk choice (no data loss, unlike Totara's unenrol warning in https://totara.help/docs/what-is-an-audience). MangoApps removes automatically because it is computed.
6. **Preview.** No reference previews a recommend outcome. Moodle Workplace (count plus user list before enabling) and SmarterU (per-row failure reasons) remain the models for the list; no source distinguishes "will recommend" from "will remove a recommendation".
7. **Multi-organisation users.** Not found in any source for recommendations. Moodle Workplace scopes rules to a tenant (earlier research). Totara and others treat audiences as site-wide. Therefore the FLS organisation question is unaddressed by prior art.

## 4. Implications for FLS (not decisions)

FLS words: `RecommendedCourse` (keyed on `User` and `Site`), registration rule, organisation, `Learner`.

- The stored-row design in idea.md has little direct precedent; the nearest are Arcoro (rule-owned, removable only via the rule) and `block_recommend_course` (row with actor, admin history). Reasonable to justify it on those two and on the need to keep admin-made rows (which a computed design like MangoApps cannot support).
- The "computed at display" design (MangoApps) is a genuine alternative that dissolves retraction, staleness and uniqueness, and handles multi-organisation users naturally (evaluate per organisation per request). Its cost is that admin-made rows, preview "who is recommended" and clearing semantics have no stored home. Worth stating in the spec as a considered and rejected option, since idea.md already settled on rows.
- Organisation scoping: no prior art, so the spec decides it. Two sound shapes follow from the provenance precedent: (a) the row's rule reference implies the organisation (rule belongs to one organisation), so a rule retracts only rows where `rule = this rule`; admin-made rows have no rule and no organisation; the dashboard shows the union of the user's rows. (b) Add an organisation to the row. Reference products give no evidence either way; (a) matches "removable only through the rule" with fewer fields, and the multi-organisation dashboard question is then whether a user in organisations A and B should see A's rule-made recommendation while acting in B (Moodle Workplace tenancy suggests rules and their effects stay inside their tenant).
- Overlap: model the retraction as "delete rows owned by this rule where learner no longer matches, then keep the row if another enabled rule still matches". Cornerstone's overlap behaviour and the "reconcile" pattern both support computing the desired set across all enabled rules for the course rather than per rule in isolation. Beware the one-row-per-course uniqueness: with several rules matching, only one rule can own the row, so a retraction by the owner must hand over or recreate for another matching rule. No reference documents this; it is a spec decision and a likely source of bugs.
- Registration clearing: since no reference provides it, enumerate paths from `research_fls_user_attributes_and_registrations.md` section 4 and decide on a central hook versus per-path calls.
- Disable: removing rows on disable is safe for recommendations (no progress at risk). SAP's two-step disable is not needed; disable counts as every learner unmatching, as idea.md states.
- Preview: reuse the spec 2 list; add the "remove a recommendation" action to the same rows. Moodle Workplace and SmarterU back showing the reason per row.
- Correct the Totara claim in idea.md: "Totara (visible learning)" is gating, not recommending; SAP and Arcoro are the real precedents, both only via excerpts.

## 5. Gaps and what to verify before relying on this

- SAP: how a recommended item is stored and what registering does to it. Needs SAP Learning admin guide access.
- Arcoro: required-vs-recommended lifecycle. Needs the Arcoro help article (403 to fetcher).
- Workday: whether a campaign can be recommended-type; Engagement Builder docs.
- No source on multi-organisation recommendation dashboards.
- Model-knowledge items flagged above are unverified.

## Sources
- https://totara.help/docs/dynamic-audience-settings
- https://totara.help/docs/what-is-an-audience
- https://totara.help/17/docs/what-are-recommendations
- https://totara.help/18/docs/what-are-recommendations
- https://totara.help/15/docs/what-are-recommendations
- https://totara.community/mod/forum/discuss.php?d=16374
- https://learning.sap.com/courses/sap-successfactors-learning-academy/assigning-learning-needs-to-users-automatically
- https://userapps.support.sap.com/sap/support/knowledge/en/2678347
- https://userapps.support.sap.com/sap/support/knowledge/en/2335740
- https://support.arcoro.com/hc/en-us/articles/360051795874
- https://doc.workday.com/admin-guide/en-us/human-capital-management/learning/learning-content/chr1460991670411.html
- https://guides.mangoapps.com/lms-guide/learn-admin/recommendations
- https://docs.moodle.org/501/en/Cohort_sync
- https://moodle.org/plugins/block_recommend_course
- https://moodle.org/plugins/block_datacurso_recomendate
- https://moodle.org/plugins/block_course_recommender
- https://docs.openedx.org/en/ulmo/learners/concepts/open_edx_platform/what_is_course_dashboard.html
- https://pypi.org/project/course-access-groups/
- https://community.canvaslms.com/t5/The-Product-Blog/New-in-Canvas-Catalog-Course-Recommendations-Based-on-Real/ba-p/638062
- https://help.csod.com/skills-studio/ss-help-get-started/topics/ss-help-about-learning-recommendations.html

status: ok
