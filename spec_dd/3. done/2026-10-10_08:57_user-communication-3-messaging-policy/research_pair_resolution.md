# Research: whose context decides a pair

Topic for `idea.md` "Open until the spec": *Whose context decides a pair*, and the linked question of how a `CohortCourseRegistration` and a `LearnerCourseRegistration` for the same course combine. Vocabulary follows the domain glossary (`Learner` is a user's row per organisation; `CohortMembership`, `LearnerCourseRegistration`, `CohortCourseRegistration`). Moodle, Canvas and Discord keep their own terms.

## 1. What the codebase gives a pair to resolve over

### 1.1 The rows

| Row | Org-scoped? | Active flag | Notes |
|---|---|---|---|
| `Learner` (user, organisation) | yes, one per user per organisation | `is_active` | Unique per `(site, user, organisation)`. A user may hold several. All enrolment hangs off `Learner`, not `User`. |
| `CohortMembership` (cohort, learner) | via cohort | **none** | No `is_active`, so membership counts only through `Learner.is_active`. `clean()` forbids cross-organisation membership, but factories skip `clean()`. |
| `Cohort` | one organisation | **none** | |
| `LearnerCourseRegistration` (learner, course) | via learner | `is_active` | Unique per `(site, learner, course)`, so one per organisation per course for one user. |
| `CohortCourseRegistration` (cohort, course) | via cohort | `is_active` | Reaches learners through `CohortMembership`. |
| `OrganisationMember` (user, organisation) | yes | `is_active` | Gates organisation- and cohort-level role grants in `can()`. Independent of `Learner`. |
| `ObjectRoleAssignment` / `SiteRoleAssignment` | cohort, organisation or site scope | `is_active` | The educator side. |

The new configuration rows can therefore attach to exactly these anchors: site (one row), `Organisation`, `Cohort`, the two registration models, and `Learner`. Two facts matter for pair resolution.

- **A `Learner` row is organisation-scoped.** A learner-level setting is a setting on one (user, organisation), not on the user. A user in two organisations has two learner-level rows, and the organisation a setting applies to is decided by which `Learner` row the link runs through.
- **A cohort is single-organisation, so any cohort link fixes the organisation.** Both sides' `Learner` rows are in `cohort.organisation`. Only a *course* link (two `LearnerCourseRegistration` rows, or one of each kind) can join two `Learner` rows from different organisations.

### 1.2 Which configuration rows can apply to each pair

Notation: S = settings default, Site = the site row, Org = organisation row, Coh = cohort row, Reg = a registration row (individual or cohort kind), L = learner row.

**Learner to educator.** The educator is not a `Learner` in the relevant sense. They link to the learner through role assignments, i.e. the inverse of `learners_visible_to`. This is the same "educators of a learner" helper the idea settles.
- Link by a cohort role (`cohort_admin`, `cohort_viewer`): the link context is that `Cohort`. Applicable rows are S, Site, the cohort's Org, Coh and the sender's L in that organisation. A learner in two cohorts of the same educator gives two candidate cohorts.
- Link by an organisation role (`organisation_admin`, `organisation_staff`), or by `site_admin` (site scope): there is no cohort. Applicable rows are S, Site, Org (site-level admins link through every organisation of the site) and the sender's L. A cohort row never applies, because the educator's visibility did not come through it.
- Course registrations do not link an educator, because no role is scoped to a course. A `Reg` row can still be meaningful ("learners on this paid course may message their educators"). Since it is not part of how the educator is linked, it can only enter as an additional opener on the sender's own `Learner` row in that organisation (see 4.3).

**Learner to learner, peers in a cohort.** The link context is the shared `Cohort`, so both `Learner` rows are in one organisation. Applicable rows are S, Site, Org, Coh, and L on the sender (and, as a possible veto, L on the recipient). Cohort-level registrations are not part of the link.

**Learner to learner, peers in a course.** Two link shapes exist, and both can hold at once for one pair and one course.
- Sender via `LearnerCourseRegistration`, recipient via `LearnerCourseRegistration`: link context = the course, with two individual `Reg` rows, one per side.
- Either side via `CohortCourseRegistration` through `CohortMembership`: the `Reg` row is the cohort-kind row, and its `Cohort` is also a config anchor (Coh).
- Sender and recipient may sit in different organisations here, since nothing forces the two `Learner` rows to share one. Org is then ambiguous: sender's, recipient's, or both.
- Rows can apply on the sender's side and the recipient's side, and the two sides may use different registration kinds.

**Educator to learner.** The idea's default is open: any learner in `learners_visible_to` can be started by the educator. Applicable rows are S, Site, Org and Coh (the link cohorts), and the learner's L. A closed setting must be able to override the "educator may start" default for it to be configurable at all. Whether it should be (versus educator-initiated always open as a safety/duty-of-care channel) is a spec question; see 4.5.

**Cross-cutting flags and scoping.**
- Both `Learner.is_active` and registration `is_active` must hold, tested in the *same* `.filter()` call as the membership join. Existing code documents why a split leaks access (`is_registered_for_course_expression` comment on removed vs active `Learner` in one cohort).
- Educator links need `OrganisationMember.is_active` for organisation- and cohort-level roles. The existing `_granted_organisations`/`_granted_cohorts` helpers in `capabilities.py` are the place that gate lives; the inverse query must reuse them rather than re-deriving it.
- Site scoping: `SiteAwareManager` filters only inside a request. The relationship queries take `site` explicitly and filter every table on it (`site=site` on `Learner`, memberships, registrations, config rows).
- A cohort has no active flag and no "concluded" state. Nothing in the codebase models an ended cohort or course, so "concluded course" has no FLS equivalent.

### 1.3 How the existing code already resolves the same ambiguity

`learner_for_course(user, course)` (`freedom_ls/learner_management/queries.py:121-165`) is the nearest precedent. For one user and one course it picks one registration deterministically: cohort registration beats individual, and between two cohort registrations it orders by `-is_active, -registered_at`. This is a *single-winner* rule for deciding which row work lands under. It is not necessarily the right rule for configuration, because for *work* exactly one record must win, whereas for *permission to message* nothing requires a single winner. Do not copy "cohort wins" into messaging config without noticing that it reverses "most specific wins": an individual registration is more specific than a cohort one, yet `learner_for_course` ranks the cohort one first.

`is_registered_for_course_expression` is the precedent for the other style: two `Exists()` combined with `|`, a permissive union as one queryset expression.

## 2. Resolution strategies

Terms. A **candidate context** is one concrete link between the pair (a shared cohort; a shared course via a given registration pair; an educator's cohort role; an organisation role). **Layered value** = the nullable flag after most-specific-wins within one candidate: `Coalesce(L, Reg-or-Coh, Org, Site, S)`.

| Strategy | Meaning | Closed-by-default fit | Weakness |
|---|---|---|---|
| A. Per-relationship context, any candidate opens | Resolve layered value per candidate. Pair allowed if at least one candidate is open. | Good: nothing is open until some candidate says so. | A close on one candidate cannot shut the pair while another candidate is open. |
| B. Per-relationship, deny overrides | Allowed if at least one candidate open and none explicitly closed. | Good, plus the close is effective. | "Explicit closed" must be distinguished from "unset"; a stale closed row on a stray cohort blocks a paid, open arrangement. |
| C. All-must-allow | Every candidate and every side's config must be open. | Strictest. | One unrelated cohort or an old registration can silence a pair that has a valid open link. Surprising for admins. |
| D. Sender-only | Only the sender's configuration is consulted. | Simple, one lookup chain. | The recipient cannot refuse; for peer messaging this weakens safeguarding. |
| E. Both-sides consent | Sender's layered value is open and the recipient's layered value for the same context allows receiving. | Strongest consent model. | Doubles the config surface (send flags and receive flags), and recipient resolution needs its own layering. |
| F. Most specific wins across *all* applicable rows | Flatten every row of every candidate into one chain by specificity. | Looks uniform. | "Most specific" is not a total order across candidates (two cohorts are equal-specific siblings), so it needs a tiebreak that is arbitrary. |

Within one candidate, most-specific-wins is the settled rule, and all of A to E reuse it. The difference is only how candidates and sides combine.

### How other systems chose

- **Moodle.** Two gates. Site level: personal messaging on or off, plus an optional site-wide messaging mode that lets users see and message anyone. Within that, the **recipient** chooses a privacy preference, "My contacts only" or "My contacts and anyone in my courses" (the default). Link = a shared course or an accepted contact. Moodle chose recipient-consent (strategy E-like) because messaging is a personal channel and the recipient bears the cost of unwanted contact; course membership is the "stranger-free" link. The course-membership link is a union of any shared course (strategy A across courses). Sources: [Messaging settings](https://docs.moodle.org/502/en/Messaging_settings); preference wording per [Moodle help summaries](https://docs.moodle.org/38/en/Messaging) and the search results listed below.
- **Canvas.** Recipients in Inbox are scoped by course (and section or group) membership. Whether students can write to the whole class or to individuals is controlled by role permissions ("Conversations: send messages to entire class", "...to individual course members"), which a Canvas admin sets by role. Per the community threads in the references, instructors cannot set this per course; it is an account-level permission per role. (Correction to the premise in the brief: Canvas does not have a per-course "Allow students to message each other" switch that the teacher controls; it is a permission, and a long-standing feature request is to make it course-level.) Canvas chose permission-by-role plus link-by-shared-course (strategy D: sender capability, no recipient preference), because an LMS institution wants one consistent rule enforced centrally, not individual consent. Behaviour for concluded courses is not something I could verify from a source in this session; treat it as unverified.
- **Discord.** The link is a shared server. The recipient's privacy setting "Allow direct messages from server members" is a per-server toggle (the account-level default applies only to servers joined afterwards), so consent is recipient-side and per-link. I did not find an authoritative statement about what happens when the pair shares two servers with conflicting toggles; commonly reported behaviour is that any permissive shared server lets the DM through, but that is unverified here. Discord's design is recipient-consent with the link as the context: strategy E with A across links.
- **Slack.** Not researched from a source this session. General knowledge only: DMs are workspace-scoped, organisation-wide admin policies sit above them, and Connect channels add cross-organisation links. Treat as unverified and do not rely on it.

Take-away pattern in all three systems: the link (shared course or server) is the unit of context; the sender's right comes from an admin-level capability (Canvas) or the recipient's preference scoped to the link (Moodle, Discord); and multiple links are a union, not an intersection.

## 3. Interaction with the composer's recipient queryset

The composer needs "which users may this sender start a conversation with" as one queryset (the idea's third contract question). What stays expressible:

- **A, B, D: yes, cheaply.** Candidate contexts belong to the *sender*, and there are few (a handful of cohorts, registrations, organisations). Two sound shapes:
  1. Resolve the layered value for each of the sender's candidates, either in Python (a few queries total, not one per recipient) or in SQL with `Coalesce` annotations over the joined config rows. Keep only the open candidates' ids.
  2. Build the recipient queryset as a union of per-link filters over those ids: `Learner.objects.filter(is_active=True, site=site, cohortmembership__cohort_id__in=open_cohort_ids)` OR `... learnercourseregistration__course_id__in=open_courses_individual` OR cohort-registered learners (join `cohortmembership__cohort__course_registrations`, with the registration `is_active` and learner `is_active` conditions all in one `filter()`), then `.exclude(pk=sender)` and map to `User` with `.distinct()`.
  This is a loop over the sender's contexts, not over recipients, and the final result is one ORM queryset. Per-candidate resolution is the same function the single-pair check uses, so the check and the queryset cannot drift (the same "queryset mirrors per-row check" discipline `is_registered_for_course_expression` documents).
- **B (deny overrides): yes.** Add `.exclude(...)` of any link whose layered value is explicitly closed, or fold it into step 1 by dropping a pair when any candidate for that recipient is closed. The second form needs a per-recipient join of candidates, which is an `Exists`/`NOT Exists` pair against the same membership tables, still one queryset but harder to read.
- **C (all-must-allow): expressible but costly.** "Every shared context is open" is a `NOT EXISTS` on shared contexts whose layered value is not open, joined per recipient. It works but the per-recipient candidate set means a correlated subquery with the config `Coalesce`.
- **E (recipient consent): partly.** A recipient *veto* flag at learner level is a cheap `.exclude(Exists(config row with value False for this recipient learner))`. A full recipient-side layered resolution (recipient's cohort row, organisation row, and so on, for that link) is a correlated `Coalesce` over the recipient's rows. It is possible in SQL but it is the most complex, and it pushes recipients' configuration into every composer query.
- **F: not cleanly.** The tiebreak rule cannot be written as a total order in SQL without an arbitrary key.
- **Anything that calls Python per user** (an arbitrary swapped-in policy that cannot produce a queryset) cannot serve the composer. The contract should require the queryset method, and a swapped policy then owes one.

Cross-cutting cost notes: educators-of-a-learner is a union of three role sources (cohort role, organisation role, site role); the existing sample in the relationships research builds this with `.union()`. Mixing `.union()` with the further filters above fails in Django, so build the recipient set from `Q`/`Exists` on `pk__in` subqueries rather than `.union()` where more filtering follows. `ObjectRoleAssignment.object_id` is a `CharField`, so cohort and organisation UUIDs need casting for the join.

## 4. Edge cases

### 4.1 Peer pair sharing two cohorts with conflicting configuration

A and B are both in cohort X (peer messaging open) and cohort Y (peer messaging closed, an explicit row). Both cohorts are in one organisation.
- A: allowed (X is open). Y's explicit close is local to Y. This matches Moodle and Discord's union-of-links behaviour and avoids a stale row on one cohort silencing a pair that has a good reason to talk.
- B: refused, because the close is explicit. Admins who want "close it for the learner" get that through the learner level.
- The practical difference only exists when the closed row is explicit. If Y leaves the value unset it falls through to Org/Site/S, where the closed-by-default answer is also "closed", and the pair is still allowed through X.

### 4.2 Learner-level setting on the sender versus on the recipient

- Learner level is most specific, so on the **sender** it overrides every candidate context's value (the sender's own `Learner` row in the link's organisation). A learner-level close on the sender is a hard stop; a learner-level open (the "paid" arrangement) opens every educator link, and peer links only if the flag is about that relationship (the flags are relationship-specific: "may start with educator", "may start with peer").
- On the **recipient**, the layering has no natural slot: the layered value is about what the sender may do. A recipient-side learner row can only act as a **veto** ("does not accept messages from peers") or as an additional opt-in. Letting a recipient's open setting *open* a pair would let a learner expose themselves to messages the organisation never opened, which is a safeguarding hole in a closed-by-default design. Recommend: recipient-side learner level can only close (veto), never open, and only if the spec decides to ship a recipient veto at all. It is not requested in the idea ("Don't build functionality that is not explicitly requested"), so the safe default is sender-side only, with the contract leaving room for a veto, which is also what the idea says about block (spec 6 will narrow what the policy allows).
- Per-`Learner`-row scope: a learner-level row in organisation X says nothing about the same user's `Learner` row in Y.

### 4.3 Organisation-level conflict when users span organisations

- **Cohort links** never span organisations; the organisation is the cohort's.
- **Educator links**: the learner's `Learner` row in the organisation where the educator holds a role is the context; the other organisation's configuration is irrelevant. An educator with roles in two organisations where the learner is also present in both gives two candidates (strategy A: any open).
- **Course peer links across organisations** are the only real conflict. Options: (i) require both `Learner` rows to share an organisation for the course link to count (smallest, keeps "organisation" an unambiguous context); (ii) allow it only if *both* organisations resolve open (all-must-allow at the organisation boundary: neither organisation can unilaterally expose its learners to another's); (iii) sender's organisation decides (an organisation can opt its learners into talking to strangers from other organisations). (iii) is the weakest for safeguarding. (i) is simplest and queryset-friendly (`organisation_id` equality in the join); (ii) is the principled expansion.
- A `Reg` row opening educator messaging: the registration belongs to the sender's `Learner` row, which fixes its organisation; it is an additional opener only for educators linked within that same organisation.

### 4.4 Cohort registration and individual registration for the same course

Both exist for one learner and one course, each with a (possibly different) value. Options: individual wins (most specific), cohort wins (matches `learner_for_course`), both separate candidates (any-open), both separate with deny overrides.
- Recommend treating them as **two separate candidates**, not ranking them. They are alternative reasons the learner is on the course, often different commercial arrangements (an employer cohort and a personal purchase). Ranking them reintroduces a "which wins" rule that `learner_for_course` already shows to be hard to get right and that has no queryset-friendly total order across the sender's several cohorts. For the config meaning "individual wins" on a per-course basis, the learner level already exists.

### 4.5 Educator to learner and "closed" semantics

The idea's default makes educator-initiated contact open with no configuration. Under strategy A (any-open) with a default of open, a close on one candidate does not close the pair because other candidates fall through to the open default. If admins must be able to close educator-initiated contact, either make the default for that flag an explicit "open" that only the learner level can override, or do not make educator-initiated contact configurable in this spec. Flag as an open decision for the spec.

### 4.6 Reply after change

Not in scope here. The reply check can use the same per-pair resolution with a different flag; "reply allowed when any shared context or an existing conversation exists" is for the separate open question.

## 5. Recommendation

**Strategy A+, sender-side, per-link candidates, hard stop at learner level.**

1. **One candidate per concrete link.** For a pair the candidates are: each shared active cohort; each shared course via each registration path (individual and cohort-kind are separate candidates, not ranked); each educator role link (cohort, organisation, site). Each candidate is resolved separately by the layered chain `Coalesce(Learner, Registration-or-Cohort, Organisation, Site, Settings)`, most specific wins, unset falls through, closed by default.
2. **The pair is allowed if any candidate resolves open**, for the relationship in question (learner to educator, peer, educator to learner).
3. **Sender-side only.** The sender's `Learner` row (in the organisation the candidate runs through) supplies the learner level. The recipient's configuration is not consulted, except that a recipient-side `Learner` explicit close is reserved as a veto the contract may later use (block, spec 6). It never opens a pair.
4. **The learner level is a stop that is not specific to a candidate**, because the sender's `Learner` row is the same in every context of one organisation. A learner-level `False` closes every link of that organisation; a learner-level `True` opens every link of the relevant relationship. This also matches "the learner level is how a paid arrangement is expressed", and a later platform-wide per-user level is one more term at the top of the same `Coalesce`.
5. **Cross-organisation course peer links**: require the two `Learner` rows to share an organisation for the course link to count (4.3 (i)), and note (ii) as the expansion. Cohort links are single-organisation by construction.
6. **Requirements on the implementation**: implement per-candidate resolution once and use it for the pair check, the reply check, and the recipient queryset; take `site` explicitly; every join condition on `is_active` in one `filter()`; reuse `capabilities.py` helpers for the educator side (including the `OrganisationMember` gate) rather than reassembling role queries.

Trade-offs of the recommendation.
- **For:** matches how Moodle and Discord treat multiple links (union); easy to explain to site admins ("any shared place that has it switched on"); keeps one efficient queryset built from the sender's few contexts; avoids a ranking rule between cohort and individual registrations; a stale cohort row cannot silence a valid open arrangement.
- **Against:** an explicit close at cohort or registration level is local, so it does not shut a pair that is also linked through an open context. Admins who need a person shut off use the learner level (or, later, block). If the spec prefers admin-intuitive closes, strategy B (deny overrides) is the alternative: same queryset shape plus an exclude of explicitly closed candidates, at the cost of stale rows blocking valid pairs.
- Sender-only skips recipient consent. For a safeguarding-sensitive install, the veto hook plus block (spec 6) is the planned mitigation; full recipient consent (Moodle style) doubles the configuration surface and is not requested.

## 6. Worked examples under the recommended rule

Assume settings default closed everywhere, site row absent unless stated. "Open" means the relationship's flag is true.

1. **Peer, one shared cohort.** Learner A and B are in cohort X (`Coh` X: peers open), same organisation O (`Org` unset). Both `Learner.is_active`. Sender A's `Learner` row unset. Resolution for candidate X: `Coalesce(None, True, ...)` = open. Outcome: allowed. B is offered in A's composer.
2. **Two cohorts, conflicting.** As 1, plus A and B also share cohort Y with explicit peers closed. Candidates X open, Y closed. Any-open: allowed. A's composer includes B once (`distinct()`).
3. **Learner-level stop.** As 2, but A's `Learner` row in O has explicit "may start with peer: false". Layered value is false for every candidate. Outcome: refused, and the composer offers none of the peers in O.
4. **Paid learner to educator.** Site and `Org` unset; cohort Z has no row. Learner C's `Learner` row has "may start with educator: true". D holds `cohort_admin` on Z (C in Z). Candidate Z resolves open at the learner level. Outcome: C may start with D. C may not start with E, who holds no role linking to C.
5. **Same course, two registrations.** F and G are both registered for course K. F by `LearnerCourseRegistration` (config: peers open), G through cohort W which holds a `CohortCourseRegistration` for K (config unset), same organisation O, `Org` closed. Sender F: the candidate is F's individual registration open (F's own side). Outcome: F may start with G. Sender G: G's candidate is the cohort registration, unset, falls to `Org` closed. Outcome: G may not start with F. (Asymmetric, as sender-side-only implies; surfaced to admins by documentation.)
6. **Individual and cohort registrations, same learner and course.** H is on course K through an individual registration (open) and cohort W's registration (explicitly closed), peer relationship with J who shares only the course. Two separate candidates: one open, one closed. Outcome: allowed (any-open). Not "cohort wins" as in `learner_for_course`.
7. **Cross-organisation course peers.** K1 (org P) and K2 (org Q) both have active individual registrations for course M, both organisations open for peers. No shared organisation, no shared cohort. Outcome under 4.3 (i): refused. Under 4.3 (ii): allowed only because both organisations resolve open.
8. **Removed learner and inactive registration.** B's `Learner.is_active=False`, or the registration on the shared course is inactive. That candidate does not exist. If it was the only link, the pair has no candidate and is refused.
9. **Multi-organisation educator.** Educator R holds `organisation_staff` in O1 and `cohort_viewer` on a cohort of O2. Learner S has a `Learner` row in both. S's learner-level in O1 is open for educator, in O2 unset. Candidates: O1 role link (open via learner level), O2 cohort link (unset, closed). Outcome: allowed, through O1.
10. **Educator to learner under default.** No configuration. Educator R sees learner T through `learners_visible_to`. Outcome: allowed (the shipped default). If an install adds an explicit closed `Org` row for educator-initiated contact, per 4.5 the pair is refused only if the spec makes this flag closable by a more specific level and no candidate re-opens it.

## References

Web
- Moodle messaging settings (site-wide messaging, user preferences): https://docs.moodle.org/502/en/Messaging_settings
- Moodle messaging overview (contacts and course privacy wording, older version): https://docs.moodle.org/38/en/Messaging
- Moodle privacy preference wording "My contacts only" / "My contacts and anyone in my courses": https://help.itc.rwth-aachen.de/en/service/8d9eb2f36eea4fcaa9abd0e1ca008b22/article/9aee3d3cb49648d59d25f35023bbb60b and https://tracker-old.moodle.org/browse/MDL-63214
- Canvas feature request about course-level control of conversations (messaging is an account-level role permission): https://community.canvaslms.com/t5/Canvas-Ideas/Course-Settings-Control-Conversations-at-a-Course-Level/idc-p/418055
- Canvas Inbox recipients scoped by course and role permissions: https://asklits.mtholyoke.edu/TDClient/50/Portal/KB/Article/19850/The-Canvas-Inbox and https://www.it.northwestern.edu/departments/it-services-support/teaching/teach-tech/2022/time-saving-tip-ways-to-message-students-in-canvas.html
- Discord direct messages from server members, per-server toggle: https://support.discord.com/hc/articles/217916488 and https://support.discord.com/hc/fr/community/posts/6672500847767-Limit-who-can-message-you
- Not verified from a source: Canvas concluded-course behaviour, Discord multi-server conflict behaviour, Slack rules.

Codebase
- `freedom_ls/learner_management/models.py` (`Learner`, `OrganisationMember`, `CohortMembership`, `LearnerCourseRegistration`, `CohortCourseRegistration`, `Cohort`)
- `freedom_ls/learner_management/queries.py` (`is_registered_for_course_expression`, `learner_for_course`, `latest_registration`, `cohorts_visible_to`, `learners_visible_to`, `organisations_accessible_to`)
- `freedom_ls/learner_management/capabilities.py` (`_granted_organisations`, `_granted_cohorts`, `_site_grants`, `_member_organisations`, `can`)
- `freedom_ls/role_based_permissions/models.py` (`ObjectRoleAssignment`, `SiteRoleAssignment`)
- `spec_dd/2. in progress/user-communication-3-messaging-policy/idea.md`
- `spec_dd/2. in progress/user-communication-3-messaging-policy/research_flexible_configurable_comms.md`
- `spec_dd/1. next/user-communication/research_messaging_relationships_and_surfaces.md`

status: ok
