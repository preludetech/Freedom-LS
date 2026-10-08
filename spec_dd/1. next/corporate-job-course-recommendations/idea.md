> This idea has been cut into 5 specs. Their order, dependencies, the decisions already taken and
> the assumptions are in the "Registration rules" section of `spec_dd/1. next/roadmap.md`. Start there.
> The text below is the original brief and is kept as written.

# Rule-based course registration and recommendation from HR attributes

Corporate admins don't register people by hand. They write rules: "everyone with job title Driver
gets Road Safety", "everyone in Finance should see Budgeting Basics". This is item 12 in
`spec_dd/corporate-readiness/README.md`, and `spec_dd/corporate-readiness/research_corporate_features.md`
section 2 shows it is table stakes for corporate buyers. Academic systems don't offer it.

FLS can't do this today. No user record holds a job title, department or anything like it, and
registrations are only made by self-registration or by an admin. This idea adds HR attributes to
`Learner`, and adds registration rules that match learners on those attributes and then register
them for a course or recommend it.

Not every client needs this. It is switched on per organisation and is off by default.

## Decisions

### HR attributes live on `Learner`, as fixed fields

`Learner` is per organisation, so each employer holds its own view of a person. Use a small fixed
set: job title, department, location and start date. Fixed fields are simple to match, edit and
import by CSV. A new attribute costs a migration, which is acceptable. Organisation-defined custom
fields are out of scope.

Don't name an attribute "role". In FLS, roles are `role_based_permissions` roles, which grant
permissions.

`user-profile-upgrades` adds phone number and date of birth to the user's own profile. That is a
different need. Those fields describe the person to themselves, and these describe the person to
an employer. Check with that spec so the same data doesn't end up stored in two places.

### Registration rules

A **registration rule** (coined term; there is no existing one) belongs to an organisation. It
names a course, the attribute conditions a `Learner` must match, and an outcome:

- `register` creates a `LearnerCourseRegistration` for each matching learner.
- `recommend` creates a `RecommendedCourse` for each matching learner. The learner
  sees it in the dashboard's "Recommended courses" section and chooses whether to register.

Rules write one row per learner. They don't keep a cohort filled. Writing per learner gives each
row its own provenance, keeps retraction safe, and lets both outcomes use the same mechanism.
We rejected rule-filled ("dynamic") cohorts because they change what cohort reports,
cohort-level deadlines and cohort-scoped educator roles see.
`research_fls_user_attributes_and_registrations.md` §5 has the trade-off.

Every row a rule creates records which rule made it. A rule never takes over a registration that
already existed, made by hand or by self-registration. Today a rule-made registration can't
be told apart from an admin-made one, and `RecommendedCourse` has no source and no uniqueness. Both
models need provenance.

The attribute-matching rule is the first kind of rule. More kinds may follow, such as
recommendations driven by form answers (the commented-out `FormProgress` link on
`RecommendedCourse` points that way). Leave a seam for them in the pattern `COURSE_ACCESS_BACKEND`
already uses. Ship only one kind. `research_fls_backends_and_toggles.md` §1 describes that pattern.

### When rules run

FLS evaluates a rule when someone enables or edits it, and when a learner's attributes change or a
`Learner` is created. Enabling a rule applies it to everyone who already matches. Docebo doesn't
do this, and it is that product's top complaint.

Before an admin enables or edits a rule, they see a preview listing the learners it would
register, recommend to, or retract from. A list, not a count: Absorb shows only a count, and that
count can disagree with what actually happens.

Evaluation runs as a background task on `django.tasks`. `fire_webhook_event` silently does nothing
outside a request, so the spec has to decide how rule-made registrations still produce their
`course.registered` webhook.

### When a learner stops matching

- The rule removes any recommendation it made.
- The rule deactivates a registration it made (`is_active=False`) if the learner hasn't started
  the course, and leaves it alone if they have. Progress is never deleted. Totara's removal wiping grades is
  the documented worst case.
- If another enabled rule still matches the learner for the same course, nothing is retracted.

### Notifications

A rule-made registration sends the learner the usual `course.registered` notification, exactly as
an admin registration does. Rule-made rows are not `self_registered`. When a rule is first enabled
this can notify many people at once, and the preview makes that visible before it happens.

### Switched on per organisation

The feature is off unless an organisation turns it on. While it is off, no rules are evaluated,
and registrations and recommendations already made stay in place. `Organisation` has no settings
field and FLS has no organisation-level toggle yet, so this sets a new precedent. Every Site has a
default organisation, so a single-organisation Site switches it on there.
`research_fls_backends_and_toggles.md` §3 compares the switch levels.

### Where admins manage it

Both the Django admin and the educator interface. The Django admin comes first. The
educator-interface screens come in a later spec, after `educator-interface-7-learner-administration`
(learner screens). CSV import of attributes depends on `educator-interface-8-bulk-operations`. If
`educator-interface-11-audit-log` lands first, rule actions should appear in the audit log.

## Cutting this up

This is too big for one spec. Run `/sdd:roadmap` on it to cut it into ordered specs, roughly:

1. HR attributes on `Learner` and the organisation-level switch, in the Django admin.
2. Registration rules: both outcomes, provenance, evaluation triggers, preview and retraction,
   in the Django admin.
3. Educator-interface screens for attributes, rules and preview, plus CSV import of attributes.
   Depends on educator-interface 7 and 8.

## Out of scope

- SCIM and SSO attribute sync. Their own README items; when they land, they trigger re-evaluation
  through the same attribute-change path.
- Due dates relative to registration or start date (README item 13) and recertification
  (item 11). Both have to agree with these rules later.
- Line managers (item 14).
- Organisation-defined custom attributes.

## Research

- `research_enrolment_rule_engines.md`: how Docebo, Cornerstone, Totara, Moodle Workplace and
  Absorb do rules, retroactivity, unmatching and preview, and what admins complain about.
- `research_fls_user_attributes_and_registrations.md`: where user data, registrations and
  `RecommendedCourse` live today, and every code path that creates registrations.
- `research_fls_backends_and_toggles.md`: FLS's backend, settings and per-Site switch patterns,
  and the background-task, signal, notification and webhook machinery.
