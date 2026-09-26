# Messaging policy

Spec 3 of 8 in the User communication effort. Read the "User communication" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A single answer to "may this user message that user?" that every messaging surface asks. It is a
swappable `MessagingPolicy` class, fed by messaging configuration that can be set at site,
organisation, cohort or course registration, and learner level, with the most specific level
winning. Nothing is open until a level opens it. The relationship queries the policy needs sit
beside it: the educators of a learner, and the peers who share a cohort or a course with a learner.
Site admins edit the configuration in the Django admin.

This spec ships no learner- or educator-facing screen. Direct messaging and the educator inbox build
on it.

## Why

FLS installs communicate in very different ways. A free self-paced course must not let a learner
who has just signed up message staff or other learners. A paid arrangement may let a learner message
their TA directly. A cohort-based programme may want peers in the same cohort to talk to each other.
A single site-wide switch cannot express this, and hard-coded rules would force every install into
one shape. If the answer lives in one policy, the composer, the inbox and the educator quick view
all agree on who can reach whom, and an install that needs different rules replaces one class.

## What is settled

- **The policy is a swappable class**, selected by a dotted-path setting and loaded the way
  `COURSE_ACCESS_BACKEND` is: a base class declaring the contract, an `AppSettings`-declared
  setting, and a cached loader. FLS ships one default implementation.
- **The contract covers three questions for a pair of users on one site:** may the sender start a
  conversation with the recipient, may the sender reply in an existing conversation with the
  recipient, and which users may the sender start a conversation with. The third exists because
  the composer offers only permitted recipients, so it has to be a queryset, not a check run per
  user.
- **Conversations are one-to-one.** The policy judges pairs and never groups.
- **The out-of-the-box rules, with no configuration anywhere:** an educator may start a
  conversation with any learner they can already see (`learners_visible_to`), and that learner may
  reply. A learner may not start a conversation with an educator or with another learner.
- **"Educators of a learner" is the inverse of `learners_visible_to`.** An educator counts as one of
  a learner's educators exactly when that learner is visible to them, so the two directions never
  disagree. The query is new. It is built from the same role assignment rows (`instructor` and `ta`
  on the learner's cohorts, the organisation-scoped roles on the learner's organisation) and in the
  same organisation-first, cohort-second shape as the existing visibility helpers in
  `learner_management/queries.py`. It is written once and reused by every surface.
- **"Peers" means learners who share a cohort (`CohortMembership`) or a course.** Sharing a course
  covers both registration paths, `LearnerCourseRegistration` and `CohortCourseRegistration`
  reached through `CohortMembership`. Only active rows count: a removed `Learner`
  (`is_active=False`) or an inactive registration takes no part.
- **Cohorts are optional.** On an install with no cohorts, every rule resolves through the
  organisation and individual registrations, with no special case.
- **Configuration is layered and closed by default.** The levels, from least to most specific:
  Django settings defaults, then site, organisation, cohort or course registration, and learner.
  The most specific level that sets a value wins, and a level that leaves a value unset falls
  through to the next. A level can open messaging (for example, learner to educator, or peer to
  peer within a cohort) or close it again.
- **The site level is one row per site**, shaped like `SiteSignupPolicy`: the row beats the
  settings default, and a site with no row uses the settings default.
- **The learner level is how a paid or premium arrangement is expressed today.** Opening
  learner-to-TA messaging for one learner is a learner-level setting. The design must leave room
  for a later platform-wide per-user level of service (for example, a paid subscription) without
  a rework.
- **Messaging configuration is its own set of rows**, separate from notification configuration.
- **Everything is site-aware.** Configuration rows are `SiteAwareModel`s, the policy only ever
  relates users on the same site, and the relationship queries take the site explicitly so they
  work outside a request.
- **Configuration is edited in the Django admin** through `SiteAwareModelAdmin`.
- **The policy and the relationship queries live in the new `comms` app.** The `comms` base app
  imports no cohort model directly. Cohort- and registration-aware logic sits in the policy
  implementation and the relationship queries.

## Open until the spec

- **How a layered rule is expressed.** Each level could carry flags (learner may start with an
  educator, peers in a cohort may message, and so on), or each level could name one of a small set
  of named policies. The choice decides what a site admin sees in the Django admin and how the
  learner level stays open to a later platform-wide per-user level.
- **How a learner's cohort registration and individual registration combine** when both, for the
  same course, carry messaging configuration.
- **Whose context decides a pair.** When a learner messages a peer, both learners have their own
  configuration. When a learner is registered for several courses, or has `Learner` rows in more
  than one organisation, several registrations and organisations apply. The spec has to say which
  configuration governs a given sender and recipient, and whether one side being closed is enough
  to refuse.
- **What happens to an existing conversation when the rules change** (configuration closed, a
  registration made inactive, a learner removed from the organisation). Can either side still
  reply? Does the conversation stay readable?
- **Which of the three roles on an organisation or site** (`organisation_staff`, `site_admin`,
  cohort `instructor`/`ta`) a learner is offered as an educator when learner-to-educator messaging
  is open. The inverse-visibility rule settles who counts. What the composer offers may be
  narrower.

## Out of scope

- The inbox, thread, composer and polling (spec 4), the educator inbox and quick-view message tab
  (spec 5), report and block (spec 6). Block will narrow what this policy allows. This spec leaves
  room for that and does not build it.
- Notification configuration and preferences (specs 1 and 2).
- An educator-interface screen for editing messaging configuration.
- The platform-wide per-user level of service, and any subscriptions feature.
- Stricter safeguarding modes for sites serving minors.
- Group conversations, announcements, discussion forums, inline feedback on content.

## Resources

- `research_flexible_configurable_comms.md` (this directory): settings versus per-site database
  configuration, the dotted-path backend pattern, and how Canvas and Moodle restrict who can
  message whom.
- `user-communication/research_messaging_relationships_and_surfaces.md`: the models and role
  assignments that decide who is an educator of a learner, what a policy can key off, the
  `COURSE_ACCESS_BACKEND` and `SiteSignupPolicy` precedents, and the site-scoping rules outside a
  request.
- `user-communication/research_lms_comms_landscape.md`: which LMSs allow peer messaging and why many
  block it.
- `user-communication/research_comms_ux_pitfalls.md`: safeguarding reasons to keep peer messaging
  off by default.
- `user-communication/research_comms_patterns.md`: the "who can message whom" section.
- `user-communication/idea.md`, the source idea.
- Code to build on: `freedom_ls/course_access` (the swappable backend and its loader),
  `SiteSignupPolicy` in `freedom_ls/accounts/models.py`, `freedom_ls/base/app_settings.py`,
  `learners_visible_to` and the other helpers in `freedom_ls/learner_management/queries.py`,
  `freedom_ls/role_based_permissions`.
- Specs: done `organisations`, `learners-associated-with-organisations` and
  `role_based_permission_system_foundations`. `educator-interface-5-permissions`, which may change
  how organisation-scoped roles reach permissions but keeps the visibility helpers.
- Skills: `domain-glossary`, `fls-dev:multi-tenant`, `ds:app-settings`, `fls-dev:app-settings`,
  `ds:admin-interface`, `fls-dev:admin-interface`, `ds:testing`, `fls-dev:testing`.
