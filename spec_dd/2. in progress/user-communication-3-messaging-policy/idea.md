# Messaging policy

Spec 3 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first. It holds the build order, what this spec depends on and may
run beside, the decisions already taken, and the assumptions every idea in the effort makes.

## What

Every messaging surface asks one question: may this user message that user? This spec gives a
single answer to it. The answer comes from a swappable `MessagingPolicy` class, which reads
messaging configuration that can be set at site, organisation, cohort or course registration, and
learner level. The most specific level wins, and nothing is open until a level opens it. The
relationship queries the policy needs sit beside it: the educators of a learner, the peers who share
a cohort or a course with a learner, and the colleagues of an educator. Site admins edit the
configuration in the Django admin.

This spec ships no learner- or educator-facing screen. Direct messaging and the educator inbox are
built on top of it.

## Why

FLS installs communicate in very different ways. On a free self-paced course, a learner who has
just signed up must not be able to message staff or other learners. A paid arrangement may let a
learner message their cohort admin directly. A cohort-based programme may want peers in the same
cohort to talk to each other. A single site-wide switch cannot express this, and hard-coded rules
would force every install into one shape. With the answer in one policy, the composer, the inbox
and the educator quick view all agree on who can reach whom. An install that needs different rules
replaces one class.

## Terms

| Term | Status | Meaning |
| --- | --- | --- |
| educator of a learner | coined | a user for whom `learners_visible_to` includes that `Learner` |
| peer | coined | a learner who shares an active `CohortMembership` or an active course registration with another learner in the same organisation |
| colleague | coined | an educator who holds a role in the same organisation as another educator, either on the organisation itself or on one of its cohorts |

## What is settled

### The policy

- **The policy is a swappable class.** A dotted-path setting selects it, and it loads the way
  `COURSE_ACCESS_BACKEND` does: a base class declares the contract, an `AppSettings`-declared
  setting names the class, and a cached loader returns it. FLS ships one default implementation.
- **The contract asks three questions about two users on one site.** May the sender start a
  conversation with the recipient? May the sender reply in an existing conversation? Which users
  may the sender start a conversation with? The third has to return a queryset rather than run a
  check per user, because the composer offers only permitted recipients.
- **The reply question receives the conversation as well as the pair.** The default policy does
  not use it. A replacement policy can use it, for example to let a learner keep answering an
  educator who wrote first, without a contract change.
- **Answers carry a reason.** A refusal returns a reason code rather than a bare `False`, so
  direct messaging can show why replying is closed instead of failing silently. This spec defines
  the codes and spec 4 words them.
- **The policy never caches an answer across requests.**
- **Conversations are one-to-one.** The policy judges pairs, never groups.
- **Block narrows the policy.** Spec 6 checks a block after the policy for both starting and
  replying. A refusal that carries a reason composes with that check. This spec builds no veto.

### Out-of-the-box rules, with no configuration anywhere

- An educator may start a conversation with any learner in their `learners_visible_to`, and that
  learner may reply.
- A learner may not start a conversation with an educator or with another learner.
- Colleagues may always message each other. This needs no configuration and is not part of the
  layered flags.

### Who counts

- **"Educators of a learner" is the inverse of `learners_visible_to`.** An educator counts as one
  of a learner's educators exactly when that learner is visible to them, so the two directions
  never disagree. The new query reads the same rows the forward query reads: `SiteRoleAssignment`
  and `ObjectRoleAssignment` rows, filtered to the roles that `roles_granting(VIEW_LEARNER, site)`
  returns and gated on an active `OrganisationMember`. It follows the same order:
  organisation first, then cohort. It never reads guardian rows and never hard-codes role names,
  so custom roles count on both sides. A scenario-matrix test checks that the two queries agree.
  Write the query once and reuse it on every surface.
- **The composer offers a learner only a configured subset of their educators.** When
  learner-to-educator messaging is open, configuration chooses which role keys are offered. By
  default the offer is the cohort-scoped `cohort_admin` holders who reach the learner. An install
  without cohorts adds `organisation_admin`. `site_admin` is never offered by default. A person
  is offered if any of their roles toward the learner is on the list. The offered set must always
  be a subset of the learner's educators. Every educator of a learner can still start a
  conversation with them and reply to them, so the asymmetry only affects who the learner can
  write to first.
- **Peers share an active cohort or an active course.** A shared course counts through either
  registration path: `LearnerCourseRegistration`, or `CohortCourseRegistration` reached through
  `CohortMembership`. Only active rows count, so a removed `Learner` (`is_active=False`) or an
  inactive registration takes no part. Two learners who share a course count as peers only when
  their `Learner` rows share an organisation. Cohorts never span organisations.
- **Cohorts are optional.** On an install with no cohorts, every rule resolves through the
  organisation and individual registrations, with no special case.

### Configuration

- **Each level carries four flags, and each flag is `inherit`, `open` or `closed`.** The flags are:
  - a learner may start a conversation with an educator
  - a learner may start a conversation with a peer in a shared cohort
  - a learner may start a conversation with a peer in a shared course
  - an educator may start a conversation with a learner

  Each flag falls through on its own, so a level can open one thing and inherit the rest. Named
  presets such as "educator-led" or "cohort community" may come later as a shortcut that fills in the
  flags. They are never stored as the rule.
- **The levels, from least to most specific:** the Django settings default, then site,
  organisation, cohort or course registration, and learner. The most specific level that sets a
  flag wins. The settings defaults are closed, except the educator-to-learner flag, which is open.
- **The resolver walks an ordered list of layers and returns the value along with the layer that
  supplied it.** Tests and any later "why" screen use the source. A later platform-wide per-user
  level of service, such as a paid subscription, becomes one more layer in that list, with no
  migration of existing rows.
- **The site level is one row per site**, shaped like `SiteSignupPolicy`. The row beats the
  settings default, and a site with no row uses the settings default.
- **The learner level is how a paid or premium arrangement is expressed today.** It sits on the
  `Learner` row, so it applies within that organisation only. Opening learner-to-educator
  messaging for one learner is a learner-level setting.
- **Messaging configuration is its own set of rows**, separate from notification configuration.
- **Configuration is edited in the Django admin** through `SiteAwareModelAdmin`.

### Whose context decides a pair

- **Each concrete link between the two users is a candidate**, and the layered chain resolves
  each candidate separately. A candidate is a shared active cohort, a shared course through each
  registration path, or an educator role link on a cohort, an organisation or the site. A cohort-kind and an
  individual registration for the same course are two separate candidates. Neither ranks above
  the other.
- **The pair is allowed if any candidate resolves open.** An explicit close applies only to its
  own context, so a stale closed row on one cohort cannot silence a pair that another context
  opened. To shut one learner off entirely, close the flag at the learner level.
- **Only the sender's configuration counts.** The sender's `Learner` row in the candidate's
  organisation supplies the learner level, and the recipient's configuration is never consulted.
  A setting on the recipient's side can never open a pair. Peer messaging is therefore asymmetric
  when two peers' registrations carry different configuration.
- **One resolution serves the start check, the reply check and the recipient queryset**, so the
  three can never disagree, and the recipient queryset stays a single ORM query over the sender's
  contexts.

### When the rules change

- **Every reply is checked against the rules as they stand now.** Closing configuration, making
  a registration inactive, removing a learner, or an educator losing the role that made the
  learner visible all stop replies in the affected direction. A closed configuration and an ended
  relationship are treated the same way.
- **History stays readable.** A conversation nobody may reply to is not hidden, and the refusal
  reason tells each side why.

### Site scoping and app boundaries

- **Everything is site-aware.** Configuration rows are `SiteAwareModel`s, and the policy only
  relates users on the same site. The relationship queries take the site explicitly and filter
  every site-aware table by it, so they work outside a request. They are not built on
  `organisations_accessible_to` or `all_cohorts_visible_to`, which return nothing without a
  request.
- **The policy lives in the new `comms` app, and the `comms` base app imports no cohort model
  directly.** Cohort-aware and registration-aware logic sits in the policy implementation and the
  relationship queries.

## Open until the spec

- **Whether the educator-to-learner flag can be closed.** Under the any-open rule, closing it at
  one level does not close a pair that another candidate leaves at the open default. The spec
  either lets only the learner level close it or drops the flag from this spec.
- **Where the offered-roles setting lives.** The spec decides which levels carry it, and how it
  catches a role key missing from the site's role config. A typo would silently offer nobody.
- **Where "educators of a learner" lives.** It needs the private helpers beside
  `learners_visible_to` in `learner_management/queries.py`, which suggests it belongs there rather
  than in `comms`.
- **The edges of "colleague".** Is a `site_admin` a colleague of every educator on the site? Do
  superusers count as educators or colleagues at all?
- **Which organisation governs a reply** when a pair shares more than one. This depends on whether
  spec 4 keeps one conversation per pair or one per organisation.
- **Whether a missing or inactive sender `Learner` row** counts as "removed" or as a plain refusal,
  and the full list of reason codes.
- **How a future `Cohort.is_active`**, planned in `educator-interface-6-cohort-administration`,
  affects visibility, the inverse query and peers. The agreement test catches any change made to
  one side only.

## Out of scope

- Spec 4 builds the inbox, thread, composer and polling. Spec 5 builds the educator inbox and the
  quick-view message tab. Spec 6 builds report and block.
- A recipient-side veto or opt-out, beyond leaving room for block.
- Notification configuration and preferences, which belong to specs 1 and 2.
- An educator-interface screen for editing messaging configuration, and an admin "why" screen.
- Named presets.
- The platform-wide per-user level of service, and any subscriptions feature.
- Stricter safeguarding modes for sites serving minors.
- Group conversations, announcements, discussion forums, inline feedback on content.

## Resources

- `research_layered_rule_shape.md`: why each level uses tri-state flags rather than named
  policies, with prior art from Moodle, Canvas, Discourse and Teams.
- `research_pair_resolution.md`: candidate-per-link resolution, plus worked examples of pairs and
  configuration rows with the outcome for each.
- `research_rule_changes_and_existing_conversations.md`: reply-after-change patterns, the
  complaints each one draws, and how the work splits across specs 3, 4 and 6.
- `research_educator_and_peer_queries.md`: how `learners_visible_to` works today after the
  `educator-interface-5-permissions` role rename and the `OrganisationMember` gate, how to build
  and test the inverse query, the peers queryset, and which educators to offer.
- `research_flexible_configurable_comms.md`: settings versus per-site database configuration,
  the dotted-path backend pattern, and how Canvas and Moodle restrict who can message whom.
- `user-communication/research_messaging_relationships_and_surfaces.md`: the models and
  precedents. Its role names `instructor`, `ta` and `organisation_staff`, and its guardian advice,
  are out of date. `research_educator_and_peer_queries.md` corrects them.
- `user-communication/research_lms_comms_landscape.md`, `user-communication/research_comms_ux_pitfalls.md`
  and `user-communication/research_comms_patterns.md`: which LMSs allow peer messaging, the safeguarding reasons to keep
  it off by default, and who-can-message-whom patterns.
- `user-communication/idea.md`, the source idea.
- Code to build on: `freedom_ls/course_access` (the swappable backend and its loader),
  `SiteSignupPolicy` in `freedom_ls/accounts/models.py`, `freedom_ls/base/app_settings.py`,
  `freedom_ls/learner_management/queries.py`, `roles_granting` in
  `freedom_ls/role_based_permissions`, `OrganisationMember`.
- Done specs: `organisations`, `learners-associated-with-organisations`,
  `role_based_permission_system_foundations`, `educator-interface-5-permissions`.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `ds:app-settings`, `fls-dev:app-settings`,
  `ds:admin-interface`, `fls-dev:admin-interface`, `ds:testing`, `fls-dev:testing`.
