# UX patterns: recommend outcome for registration rules

Scope: the idea adds no learner-facing surface. The UX bearing on it is in the Django admin
(rule form, preview, `RecommendedCourse` list) and in how the existing dashboard behaves.

## 1. What exists today (read from the code)

- Dashboard: `freedom_ls/learner_interface/views.py` `_recommended_section` builds a section headed
  "Recommended courses" (`wrapper_id="recommended-courses"`) from `get_recommended_courses(user)`
  (`course_recommendations/queries.py`, filtered on `user` only, no organisation).
- `_visible_recommendations` drops courses the visibility gate hides from a learner not registered
  for them, and sorts newest first, ties by course slug. A recommended course that is not
  published therefore just does not show; it is not an error.
- Recommended courses are removed from the Available and category sections (`excluded_ids`), so a
  course appears in one place. Empty sections are not rendered (`section.is_empty` filter), so when
  the last recommendation goes the heading disappears.
- Cards are the shared `course_card.html`, a plain detail link, no "Recommended because" text, no
  dismiss control.
- On self-registration the view deletes the `RecommendedCourse` and redirects into the player. The
  card therefore moves from Recommended to In progress on next load. No other path clears it today.
- `RecommendedCourseAdmin` (`course_recommendations/admin.py`): `list_display = user, course,
  created_at`; no creator column; `exclude = ["site"]`.
- `RegistrationRuleAdmin` (spec 2): rule add page takes name, organisation, course; the change page
  holds `is_enabled` and conditions inline. Saving renders a confirmation preview
  (`admin/registration_rules/preview.html`) with lists "will register", "will retract", "stays
  registered" (with a reason string such as "Started the course" or "Still matched by <rule>").
  Learner names are hidden behind `view_learner` permission, counts only otherwise. List columns
  carry warnings ("Change not yet applied", "Uses inactive entries"). The registration admin shows
  the creating rule as a read-only, linked "Registration rule" field, "(deleted)" when gone, blank
  for staff- or learner-made.

## 2. Admin: choosing assign versus recommend on a rule

Patterns seen in rule-based enrolment tools:

- Totara splits the two intents into separate settings of an audience: "Enrolled learning" (enrol
  or unenrol all members) and "Visible learning" (limit what members see in the catalogue). The
  outcome is a property of the link between audience and course, not a separate rule type. Sources:
  <https://totara.help/docs/what-is-an-audience>, <https://totara.help/docs/dynamic-audience-settings>.
  (Web search did not confirm a Totara "recommended" outcome by name; the idea's own research file
  `research_enrolment_rule_engines.md` is the better source for Totara/SAP/Arcoro.)
- Common pattern: a single required choice field on the rule (radio or select, two values), with
  help text stating the consequence in learner terms: "Register: matching learners are registered
  and see the course under In progress. Recommend: matching learners see the course under
  Recommended courses and choose for themselves." Radios beat a dropdown for two options because
  both consequences stay visible.
- Default to the less impactful outcome? Registering is the consequential one (it creates
  obligation, progress and possibly notifications), so a new rule showing "recommend" preselected
  would be safer, but spec 2 rules already default to register; do not silently change that.
  Decision for the spec: whether the field is required with an explicit default.
- Changing the outcome on an existing rule is the sharp edge. Switching register -> recommend would
  have to decide what happens to registrations the rule made (they stay; spec 2 retracts only on
  unmatch). Switching recommend -> register would register people the learner never chose.
  Spec 2 already made `organisation` and `course` read-only after creation with the comment "staff
  disable the rule and make a new one instead"; the same treatment (outcome fixed after creation,
  set on the add page) is the most consistent pattern and removes the need to preview an outcome
  swap. If the outcome stays editable, the preview must show both lists (new recommendations, and
  what happens to existing registrations) and say plainly that registrations are not undone.
- Show the outcome in the rule changelist as a column and filter (`list_filter`), next to
  `course` and `is_enabled`, since "this rule registers people" versus "this rule suggests" is the
  first thing a person scanning rules needs to know.
- Wording of existing warnings ("The rule still registers learners, who will not see it until it
  is [published]") needs an outcome-aware variant for recommend: a recommendation for an
  unpublished course is hidden by the dashboard gate, so say "will not see the recommendation".

## 3. Previews: who would be recommended to or have a recommendation removed

- Match the structure spec 2 already uses (grouped lists, counts, permission-gated names) rather
  than invent a second layout. Confirmation-dialog guidance says to name the outcome and
  consequences concretely ("Recommend to 24 learners", "Remove recommendation from 3"), scale
  friction to risk, and avoid generic "Are you sure?". Sources:
  <https://appmaster.io/blog/bulk-actions-done-safely-preview-permissions-undo-patterns>,
  <https://uxplanet.org/confirmation-dialogs-how-to-design-dialogues-without-irritation-7b4cf2599956>.
  Nielsen Norman Group's articles "Confirmation Dialogs Can Prevent User Errors - If Not
  Overused" and "Preventing User Errors" are the usual references; not fetched here.
- Recommend preview groups to show: will be recommended; will have recommendation removed; stays
  recommended (reason: "Still matched by <rule>" mirrors spec 2's hand-over wording); skipped
  (already registered; or an admin-made recommendation already exists and the rule will not
  claim it). Skipped groups are optional but they answer the admin's likely question "why is X not
  on the list?". Keep them as counts if lists get long.
- Recommend removal is low risk and reversible (the learner loses a suggestion, no progress is
  lost), unlike retracting a registration. Retract preview carries "kept because started" cases;
  recommend has none, so its confirmation can be lighter. Do not reuse the "will retract" label for
  recommendations: use "recommendation removed" so admins cannot confuse the two.
- The preview must be per outcome: a recommend rule's page should not show "will register".
- The switch-off banner (`switch_is_off`) should apply unchanged, with wording "no recommendations
  will be made or removed until it is switched on".

## 4. Labelling admin-made versus rule-made recommendations in the admin list

- Add a "Source" or "Made by" column to `RecommendedCourseAdmin.list_display`: the rule name as a
  link to the rule change page, or blank/"Admin" for rows without a rule. Mirror spec 2's
  `registration_rule` field exactly: linked name, "(deleted)" when the rule is gone, blank for
  admin-made. A visible "Admin" word is slightly clearer than blank in a list, since blank can look
  like missing data; pick one and be consistent with the registration admin.
- Add a `list_filter` with "Made by a rule / Made by an admin" (the custom filter checks the rule
  being null), plus filtering by rule. Staff retracting or auditing need this filter more than a
  column.
- Make the rule field read-only on the change form so staff cannot reassign provenance, and
  keep the add form creating admin-made rows (no rule). This matches "rules never take over rows".
- Admin deleting a rule-made row: it may be recreated by the next evaluation if the learner still
  matches. Worth a help text or warning on the row's delete page; otherwise staff will think
  delete is broken. (Proper dismissal is out of scope; see section 7.)
- Admin-made rows with a rule match too: the row stays admin-made, so it does not disappear when
  the rule unmatches. Staff reading the list should see "Admin" for it, which makes the behaviour
  discoverable.
- If organisation is stored on the row (open question in the idea) show it as a column and
  filter too. Choice between provenance alone and an organisation field is for the spec.

## 5. Learner-facing recommended sections: what disappears when

Established behaviour in FLS and typical elsewhere:

| Event | Recommended card |
| --- | --- |
| Learner self-registers | Removed (today) and the course moves to In progress |
| Registered by admin, cohort, rule | Must also be removed (idea, settled) so it never shows both in Recommended and In progress |
| Learner stops matching the rule | Removed on next evaluation; page shows it until reload |
| Rule disabled | Removed (counts as everyone unmatching) |
| Another enabled rule still matches | Stays |
| Course becomes hidden / unpublished | Not shown (visibility gate) but row stays |
| Last recommendation gone | Section heading disappears (empty sections not rendered) |

- A card vanishing without explanation is a known UX irritant, but with no notification and no
  reasons in scope, silence is the accepted trade: recommendations are soft suggestions, not
  commitments. Keep it noted that learners get no explanation.
- After "register" from a recommendation FLS redirects into the player, giving clear feedback; no
  change needed.
- Recommended courses leave Available and category sections, so rule-recommended courses do not
  appear twice. No change needed; the dedupe already uses `excluded_ids`.
- Ordering is newest first. Rule runs may create many rows in one transaction, tie broken by
  slug. A bulk run therefore pushes a new rule's courses to the top ahead of an older admin pick;
  acceptable, but the spec should state it.

## 6. Multi-organisation users

- The dashboard reads recommendations by user and site only. A user in two organisations with two
  recommend rules would see both rules' courses in one list, which is the expected, simple pattern
  (a person has one dashboard). Totara and similar tools also show the union of a user's audiences'
  learning on one catalogue.
- The UX risk is retraction: the dashboard cannot attribute a card to an organisation, so it can't
  explain it, and admins in organisation A must not see or remove organisation B's rows. In admin
  terms: list filter by rule/organisation; a rule's preview names only learners in its own
  organisation; the removal step touches only rows made by that rule (provenance) and for the
  organisation's rules. If a user is in A and B, and both rules recommend the same course, a
  single row cannot satisfy "unique per user and course" and "each rule retracts its own"; that
  is the idea's open question, and the UX consequence is: unmatching in A must not remove the
  card while B still matches, and the admin list should show one row with both reasons or one row
  per rule. One row with the course shown once on the dashboard is the right learner experience;
  how the admin sees two sources is a design choice (for example a through-style link of rule to
  recommendation, as spec 2 did for registrations).
- Admin-side visibility across organisations: site-wide admins see everything; educator screens
  are spec 4 and out of scope here.

## 7. Patterns the idea puts out of scope (brief)

- Dismiss: commonly a small "Not interested" control on the card that hides the suggestion and
  must be remembered so the rule does not re-create it. Without it, an evaluation that recreates
  a row after staff delete it is the visible symptom noted in section 4.
- Reasons: "Recommended because you are in Finance" text on the card, usually fed by rule name or a
  label. Would need provenance to be learner-readable.
- Expiry: auto-removal after a period or when the course is full. Not designed here.

## References

- Totara, What is an audience? <https://totara.help/docs/what-is-an-audience>
- Totara, Dynamic audience settings <https://totara.help/docs/dynamic-audience-settings>
- Bulk actions with preview, permissions and undo <https://appmaster.io/blog/bulk-actions-done-safely-preview-permissions-undo-patterns>
- Confirmation dialogs without irritation <https://uxplanet.org/confirmation-dialogs-how-to-design-dialogues-without-irritation-7b4cf2599956>
- Local: `freedom_ls/learner_interface/views.py`, `freedom_ls/course_recommendations/{admin,queries}.py`,
  `freedom_ls/registration_rules/admin.py`

status: ok
