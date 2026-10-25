# Research: known complaints about recommendations and rule-based assignment

Scope: what users and admins complain about with LMS course recommendations and dynamic/rule-based
assignment, mapped to the `recommend` outcome idea (`idea.md`).

## Evidence base and its limits

Public, citable evidence is thin. Two web searches per vendor surfaced a few forum threads and vendor docs.
No Reddit, G2 or Capterra thread specifically about rule-made recommendations went into this file. Most
evidence is about Totara dynamic audiences (rule-driven enrolment) and Docebo's algorithmic suggestions.
Items marked "inferred" are plausible failure modes drawn from the idea's own design, not sourced complaints.

## Sourced complaints

1. **Rule unmatching silently removes things and destroys data (Totara).** Dynamic audience rules are
   always live. A learner who stops matching is dropped from the audience, and the courses granted through it are
   lost, including Record of Learning entries and grades. A partner called it a "huge problem". Totara later added an
   "External unenrol action" setting to suspend rather than delete, and an exception-audience workaround.
   Sources: https://totara.community/mod/forum/discuss.php?d=16374 ,
   https://totara.help/19/docs/dynamic-audience-settings , https://totara.help/docs/what-is-an-audience
2. **Recommendations not relevant, and logic is opaque (Docebo).** A community user says Docebo never explained how
   "suggested" content is chosen, and that infrequent users get poor suggestions.
   Source: https://community.docebo.com/product-q-a-7/a-suggested-for-you-channel-10210
3. **Opaque algorithmic feeds (LinkedIn Learning, Degreed).** Feeds mix profile, network, popularity and recency
   signals, so learners cannot tell why an item appears. The vendors document inputs but offer no per-item "why".
   Sources: https://www.linkedin.com/help/linkedin/answer/a702844 ,
   https://integrations.degreed.com/listings/linkedin-learning
4. **Admin-pushed recommendations are a separate, weaker tier (SAP SuccessFactors).** A recommended item is "a learning
   item you want to show to a group but not necessarily assign", shown on a Recommendations tile. This is the same
   model as the idea. Source: https://userapps.support.sap.com/sap/support/knowledge/en/2336483
5. **Design burden and flexibility cost (Docebo, Cornerstone reviews).** Reviewers say you must be deliberate when
   designing paths, and that Cornerstone's dynamic groups and assignment timing are flexible but heavy.
   Sources: https://trustradius.com/compare-products/cornerstone-ondemand-vs-docebo-learning-platform ,
   https://www.selecthub.com/lms-software/docebo-vs-cornerstone-lms/

## Complaint map

| Complaint | Source status | Idea's position |
|---|---|---|
| Learner loses data when a rule unmatches (Totara) | Sourced | Mostly moot: a recommendation holds no learner data. Unmatching removes the row, and spec 2's decisions govern registrations. Addressed. |
| Recommendation persists after enrolment or completion | Inferred, common failure mode | Addressed: every registration path clears it, and registered learners are skipped. Completion without registration cannot occur. |
| Recommendation vanishes unexpectedly | Sourced by analogy (Totara) | Partly addressed: it is removed on unmatch or disable, with no dismissal and no reason shown. The learner gets no signal that it was withdrawn. Gap worth a stated decision in the spec. |
| Too many recommendations | Inferred | Missed. No cap, no ranking, and ranking is out of scope. A broad rule can flood the dashboard section. Consider noting a dashboard ordering or limit as accepted risk. |
| No explanation of why | Sourced (Docebo, LinkedIn, Degreed) | Out of scope ("reasons"). Provenance records the rule for admins only. |
| Cannot dismiss | Inferred (common) | Out of scope (dismissal). A dismissed-then-re-created row is also a risk later: any future dismissal needs a tombstone or it will reappear on re-evaluation. |
| Admin cannot tell who made a recommendation | Inferred | Addressed: provenance records the rule, and rows without a rule are admin-made. |
| Rule overrides or retracts a manual choice | Totara exception-audience workaround implies it | Addressed: rules never take over admin-made rows. |
| Duplicate recommendations | Inferred | Addressed: uniqueness per learner and course. Check the existing data for duplicates before adding the constraint (research file notes none exists today). |
| Two rules overlap, one is disabled and the recommendation disappears | Inferred | Addressed: the row stays while another enabled rule matches. The spec must define the provenance shape (single rule FK versus a many-to-many) that makes this possible. |
| Cross-organisation leaks | Inferred | Open in the idea: `RecommendedCourse` is keyed on `User` and `Site`, with no organisation. The spec must settle this. A rule must never retract another organisation's row. |
| Preview does not match what happens | Inferred | Addressed: preview shows recommend and remove lists in spec 2's list. The spec should require preview and evaluation to share one code path. |
| Rules silently stop applying | Inferred | Partly addressed: the organisation switch off means nothing is evaluated and rows stay. Nothing tells admins the switch is off. A UI matter for spec 4. |
| Notification noise | Inferred | Addressed: no notification and no webhook. |
| Stale recommendations after the switch is turned off | Inferred | Out of scope by decision: rows stay. Document it. |

## Suggestions for the spec

- Keep the "no data held, so unmatching is safe" argument explicit, contrasting with Totara's unenrol-on-unmatch.
- State the behaviour when the learner sees a recommendation vanish, and accept it explicitly.
- Record the flood risk as accepted, since there is no ranking or cap.
- Require preview and evaluation to share logic.
- Resolve organisation scoping and overlap-provenance together.

status: ok
