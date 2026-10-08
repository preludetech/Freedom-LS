# Registration rules in the educator interface

Spec 4 of 5 in the Registration rules effort. Read the "Registration rules" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Educator-interface screens for four things:

- The organisation's lists of job titles, departments and locations.
- A learner's HR attributes (job title, department, location, start date), viewed and edited on the learner detail page that `educator-interface-7-learner-administration` builds.
- Registration rules, with both outcomes (`register` and `recommend`): list, create, edit, enable, disable, and delete once disabled.
- The preview list an admin sees before a rule is enabled, edited or disabled.

## Why

Specs 1 to 3 give an organisation lists, attributes and rules, but only in the Django admin. The people who own these decisions are organisation admins, and the educator interface exists so they don't need a superuser. Rules are also the one feature here where a mistake reaches many people at once: enabling a rule can register and notify hundreds of learners in a single step. The screen has to show who is affected, and by how many notifications, before the admin commits. `../corporate-job-course-recommendations/research_enrolment_rule_engines.md` records that Absorb's count-only preview can disagree with the result, that admins fear one edit unenrolling thousands, and that Moodle Workplace and SmarterU, which list the affected users, are the better model.

## What is settled

**Who manages what.** Only `organisation_admin` and `site_admin` manage the attribute lists and registration rules. Everything is organisation-scoped and site-aware. Controls a user cannot use are hidden, not disabled. An action the user can see but may no longer perform returns 403 with a message saying what happened and who to ask. Another organisation's slugs and ids return 404.

**The switch gates rules, not attributes.** The rules screens appear only when the organisation's switch is on. A learner's attributes are always viewable and editable, because attributes are stored regardless of the switch. The attribute lists are needed to fill those attributes, so they are reachable whether or not the switch is on.

**Attribute lists.** One screen per list or one screen with three sections; the spec chooses. Add, rename and remove an entry. What happens to an entry learners or rules still use follows spec 1's decision, and the screen shows how many learners and rules use an entry before the admin removes or deactivates it.

**Learner attributes.** The learner detail page gains a section for job title, department, location and start date. Pickers offer only the organisation's list entries. Saving an edit triggers re-evaluation through the path spec 2 owns. When the switch is on and an edit will change what rules do for that learner, the page says so.

**Rules.** The list shows each rule's course, outcome, conditions in words, enabled or disabled, and how many learners it has acted on. Create and edit take a course, an outcome, and conditions chosen from the organisation's lists (and a start-date "on or after" or "before" condition). Conditions combine with AND across attributes and OR within one. Enable and disable are explicit actions. A rule can be deleted only once disabled. A rule is never deleted from an enabled state, and the delete confirmation says what stays behind.

**The preview.** Before enable, edit or disable, the admin sees a list of the learners the rule would register, recommend to, or retract from, labelled by what will happen to each. It is a list, not a count. It states how many notifications will be sent. A disable is previewed as every learner unmatching the rule. Learners a retraction would leave alone (started courses, another enabled rule matching) are shown as left alone, with the reason. The admin confirms from the preview. The preview computes through spec 2's code, so it cannot disagree with what the evaluation then does.

**Built on the rebuilt panel framework.** Tables, dialogs, filters and the denied experience come from `educator-interface-2-panel-framework-tables`, `educator-interface-3-panel-framework-dialogs` and `educator-interface-5-permissions`. The mockups in the educator-interface design folder are the visual language, not the scope. Validation errors on HTMX forms return 422.

**Audit.** If `educator-interface-11-audit-log` has landed, rule creation, edit, enable, disable and delete, and attribute edits, are recorded in it. If it has not, nothing here blocks on it.

**Behaviour is not decided here.** Matching, triggers, retraction and recommendation behaviour belong to specs 2 and 3. These screens call them.

## Open until the spec

- Whether a `cohort_admin` or `cohort_viewer` sees a learner's attributes read-only on the learner detail page. Resolve it from the permission matrix `educator-interface-5-permissions` builds, and allow it only if the matrix makes it natural.
- Where the organisation switch is changed. It stays in the Django admin unless the spec finds it belongs on an organisation settings screen. Where it lives (spec 1) affects what the screens read.
- Whether the preview is computed on opening the dialog or as a page of its own, and how a preview of thousands of learners is paged, filtered and searched.
- What the screens show when the switch is on but the rules app is not installed, if spec 2 makes the app optional.
- Where rules and lists sit in the sidebar navigation.
- How a rule's provenance shows on the learner detail page's registrations list, if `educator-interface-7-learner-administration` has already landed its source column.

## Out of scope

- Matching, evaluation, retraction and recommendation behaviour (specs 2 and 3), the models and switch (spec 1), and CSV import of attributes (spec 5).
- Rule kinds other than attribute matching, organisation-defined attributes, rule-filled cohorts, rules that register cohorts.
- Editing a learner's name or email, which `educator-interface-7-learner-administration` owns.

## Resources

- `../corporate-job-course-recommendations/research_enrolment_rule_engines.md`: preview lists against counts, blast radius, how five LMSs show rules.
- `spec_dd/1. next/educator-interface-7-learner-administration/idea.md`: the learner detail page this spec adds attributes to.
- `spec_dd/1. next/educator-interface-11-audit-log/idea.md`: the audit log rule actions and attribute edits appear in.
- Mockups as visual language: `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/`.
- Skills: `domain-glossary`, `brand-guidelines`, `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:multi-tenant`, `fls-dev:testing`.
