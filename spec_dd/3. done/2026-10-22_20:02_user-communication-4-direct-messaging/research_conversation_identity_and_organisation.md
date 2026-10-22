# Research: conversation identity and organisation context

Question owned by `idea.md` ("Organisation context"): does a conversation record the organisation
it was started in, so a pair holds one conversation per organisation, or is there one per pair per
site? Builds on `research_prior_django_messaging.md` and
`spec_dd/1. next/user-communication/research_comms_patterns.md`, which are not repeated.

## Recommendation (short)

**One conversation per pair of users per site, with no organisation recorded.** Spec 5's
organisation-scoped inbox filters by a *derived* organisation (the other participant's active
`Learner` row in that organisation, which the educator can see), not a stored one. Model it as a
`Conversation` plus two participant rows carrying `last_read_at`, with the pair made unique by an
ordered pair key. Reasons below.

## 1. Evidence from the codebase

### The policy is already organisation-blind per pair

- Spec 3 decision 5: resolution "pools the sender's active `Learner` rows on the site"; each
  candidate resolves through the chain of its own organisation; `can_reply` "ignores the
  conversation passed to it". `can_start`/`can_reply` take `sender`, `recipient`, `site` only.
  So the policy's answer is a property of the pair on the site, never of a conversation's
  organisation. A stored organisation would be data the policy never reads and could contradict
  (see "organisation recorded but the policy says yes via another organisation" below).
- `can_reply` is symmetric: allowed when either direction's start is allowed now. Reply rights
  therefore already follow the live relationship, not a snapshot taken at conversation start.
- `colleagues_of(user, site)` in `freedom_ls/learner_management/queries.py` (line 519) and the
  colleague branch of `can_start` involve no `Learner` row at all. A colleague pair has no
  organisation on the learner side; "the organisation" is only derivable as a shared
  organisation-or-cohort-scoped role, and a pair may share several. A recorded organisation would
  have to be chosen arbitrarily or be nullable, which makes the column a partial fact.

### A user can be in several organisations

- `Learner` is unique on `(site, user, organisation)` (`unique_learner_per_organisation`,
  `freedom_ls/learner_management/models.py` line 76) and its docstring says "A user may hold a
  Learner row in more than one organisation". An educator can hold roles in several organisations
  (the spec 3 "multi-organisation educator" worked example). So the same two people can be related
  in organisation A *and* organisation B at once. With per-organisation conversations, a
  multi-organisation pair gets two threads with the same human, and the policy (which pools) could
  allow a reply in one that it refuses in the other for no reason the user can see.
- `peers_through` restricts course peers to the organisation because "a course is not owned by
  one"; peers are an organisation-internal relation, so a peer pair almost always lives in one
  organisation, but a learner in two organisations can be a peer of the same person in both.

### Spec 5 can filter without a stored organisation

- `learners_visible_to(user, organisation)` returns the `Learner` rows an educator may see in one
  organisation (active learners only). An organisation-scoped educator inbox for organisation X is
  then: conversations where the educator is a participant and the other participant has an active
  `Learner` row in X that is in `learners_visible_to(educator, X)`. That is one `Exists`/`pk__in`
  filter on `Learner(site, user_id, organisation=X)`; no `Conversation.organisation` is needed.
- The same filter also encodes the privacy rule spec 5 needs: an educator sees a conversation in
  organisation X's inbox only if they could see that learner in X. See privacy below.
- Colleague conversations (no `Learner` row) have no derived organisation through learners. Spec 5
  decides where they appear: either a separate "colleagues" group outside the organisation filter,
  or in organisation X when `colleagues_of` links the pair through a role in X. Either works with
  derivation; a stored organisation would force the choice at creation time.
- Caveat: the derived filter can place one conversation in two organisations' inboxes when the
  other person is a learner in both and the educator can see them in both. That is correct
  behaviour (the educator genuinely sees the learner in both), and it is the same conversation, so
  no duplicated thread.

### What happens when a learner leaves the organisation

- A removed learner has `Learner.is_active=False`. `educators_of` returns nothing for an inactive
  learner and `learners_visible_to` filters `is_active=True` "so a removed learner must not
  reappear". Self-service registration can reactivate the row (`Learner` docstring).
- Per pair: the conversation survives. The policy refuses new messages (`NO_RELATIONSHIP`) if no
  other link remains, or keeps allowing them if another organisation still links the pair. The
  thread shows history read-only with a reason (the "open until the spec" item). If the learner
  rejoins, the same thread resumes with its history, which matches how a person experiences
  "the same chat with my tutor".
- Per organisation: the conversation is orphaned with an organisation the learner no longer
  belongs to; the old organisation's educators would keep a stored link to it. Whether they may
  still read it is a policy question the stored column invites and the derived filter answers
  automatically (the learner is no longer visible there, so the conversation drops out of their
  organisation inbox).

### Privacy leak risks

Participants are the only readers; the leak risk is spec 5 surfacing conversations to someone who
is not a participant, or to a participant in the wrong context. Messages are only ever visible to
the two participants (idea.md), so an organisation-B educator cannot read a thread between a
learner and an organisation-A educator under either design, because they are not a participant.
The real risk is the *educator's own inbox*: an educator in both A and B has one conversation list.

- **Per pair, derived**: an educator who is an educator in A and B and talks to a learner who is in
  both sees one thread with that learner in both organisations' inboxes. A learner's message
  written for an A-matter is visible in B's inbox view only to the same person (the educator), so no
  third party reads it. The residual risk is a *shared-device or screen-share* context in B, and it
  is the educator's, not a data leak. Mitigation if wanted: show an organisation label on the thread.
- **Per pair, derived, learner side**: the learner sees one thread with that educator; they cannot
  tell which organisation the educator's message refers to. The composer's "who will see this" line
  states the two participants, which stays true.
- **Per organisation, stored**: the opposite risk appears when the *same educator* wearing an
  organisation-B hat replies to an organisation-A thread by mistake (they are in the wrong
  inbox). That is a UI error that per-organisation conversations prevent. It is the one genuine
  benefit of storing the organisation, and it is cosmetic compared with cost.
- **Hidden leak with a stored organisation**: if policy allows a pair via organisation B but the
  stored organisation is A, then an A-scoped inbox filter shows a conversation the A administrator
  may not intend, or hides a reachable one. Storing a fact the policy ignores creates a place for the
  two to disagree. Derivation cannot disagree with the live data.
- Spec 6 (reports) will let site admins read a reported message. Organisation context is useful
  there but is a *site admin's* concern (site-wide), so it needs no stored column either.

## 2. How other products scope DMs

- **Slack**: a direct message belongs to a workspace; the same two people in two workspaces have two
  separate DMs, because a workspace is the identity boundary. The analogue of FLS's workspace is the
  **site**, not the organisation. Organisations here are inside one site, sharing one user table, one
  login and one notification bell. So Slack's rule supports "one per pair per site". (From general
  product knowledge; not fetched.)
- **Canvas**: conversations are global to the user's inbox, not per course. A conversation carries
  an optional course or group *context* (`context_name`, `context_code`), used to label and filter
  the inbox (`filter[]=course_<id>`). An existing private conversation with the same recipients is
  reused unless `force_new` is set. The docs do not say how reuse behaves across two course
  contexts. This is the closest analogue to a *derived or soft* organisation: a label, not an
  identity. Source: https://canvas.instructure.com/doc/api/conversations.html
- **Moodle**: private messaging is a site-wide conversation between two users, not per course;
  course context appears only in the "contact" list and in course-participant shortcuts. (From
  general knowledge; the developer docs page I tried returned 404, so this is unverified.) The
  pattern is again one thread per pair, courses as discovery, not identity.
- **Research already in this directory** (`research_prior_django_messaging.md`, shared
  `research_comms_patterns.md`) found the common pair-identity patterns are an ordered-pair unique
  key or a participant table; none key a one-to-one thread on a sub-site grouping.

Takeaway: products that scope DMs do it at the identity boundary (workspace, site). Sub-groupings
(course, group) are filter labels. FLS's organisation is a sub-grouping, so it is a filter label.

## 3. Data-model shape options (idea level)

All options are `SiteAwareModel` + `TimestampedModel` per project conventions. Site is on every row,
so the `site` filter is automatic and a pair is unique *within a site* (users already belong to one
site, so the site column in the key is for convention and for the explicit-`site_id` background
rule).

### A. Conversation + two participant rows (`last_read_at` per row)

- `Conversation` (site, timestamps, maybe `last_message_at` for inbox ordering).
- `ConversationParticipant` (conversation, user, `last_read_at`), unique on
  `(conversation, user)`.
- Pros: read state is naturally per participant and private to the reader; unread =
  "latest message from other, created after my `last_read_at`" (no per-message read flag, which the
  prior research already favoured); extends to group conversations later (explicitly out of scope
  now but this is the evolution path); a user's inbox is a join on their own participant rows, one
  indexed lookup; spec 6 block and spec 5 labels can hang off the participant row.
- Cons: one-to-one uniqueness is not expressible as a simple constraint across rows. Need a
  separate guarantee that two users share at most one conversation: a pair key (below), or a
  transactional get-or-create. Two extra rows per conversation, and writes touch two tables.

### B. Two user FKs on `Conversation` (`user_a`, `user_b`, plus `a_last_read_at`, `b_last_read_at`)

- Pros: a pair is one row and uniqueness is a plain `UniqueConstraint(site, user_a, user_b)` with
  an ordering `CheckConstraint(user_a < user_b)`; get-or-create is one query; fewer joins.
- Cons: "my conversations" is `Q(user_a=me) | Q(user_b=me)` (an OR that defeats simple indexing;
  needs two indexes or a union); per-participant fields are duplicated columns and every read-state
  query must branch on which side the viewer is; never extends to groups; the ordering invariant
  must be enforced in application code on create (sort the two ids).

### C. Hybrid: option A plus a pair key on `Conversation`

- `Conversation.pair_key` (for example `"{low_user_id}:{high_user_id}"`, or two ordered FK columns)
  with `UniqueConstraint(site, pair_key)`. Participants stay a table for read state, the key
  guarantees at most one conversation per pair and makes get-or-create a single lookup.
- Pros: keeps A's read-state shape and gets B's hard uniqueness; the constraint is database-level,
  so the double-submit and race cases ("sending is safe to retry") cannot create two conversations.
- Cons: the key duplicates information in the participant rows; a redundancy that must be written
  once, in the one creation function. Locks the model to one-to-one unless the key is made nullable
  for later group conversations.

The ordered-pair constraint (low id first) is what makes (A,B) and (B,A) the same pair. It is
needed in B and C; option A alone relies on a transaction and `select_for_update` or a retry.

### Effect of the organisation question on shape

- Per-pair: the three options above stand as written.
- Per-organisation: every key above gains `organisation`, the pair-key uniqueness becomes
  `(site, organisation, pair_key)`, the colleague case needs a nullable or arbitrary organisation,
  and `can_reply` (which ignores the conversation) gets a conversation whose organisation it never
  uses. Colleague pairs would need a fake or nullable organisation, so uniqueness with a nullable
  column needs a partial constraint in PostgreSQL. This is the larger model for no gain the policy
  can use.

## 4. Option comparison on the organisation question

| Concern | One per pair per site (derived organisation) | One per pair per organisation (stored) |
| --- | --- | --- |
| User with `Learner` rows in two organisations | one thread with each educator | a thread per organisation per educator |
| Educator in two organisations | one thread per learner; appears in each inbox it qualifies for | split threads, risk of writing in the wrong one |
| Colleague messages (no `Learner` row) | natural | needs a nullable or arbitrary organisation |
| Spec 5 inbox filter | `Learner(user=other, organisation=X)` visible to educator; one `Exists` | simple `organisation=X` filter |
| Learner leaves organisation | thread survives; policy decides replies; resumes on rejoin | orphaned thread tied to an organisation they left |
| Policy agreement (spec 3 decision 5) | policy answer is per pair, same as the model | policy ignores the column; two truths |
| Wrong-context reply | possible, mitigated by an organisation label | prevented |
| Migration cost if wrong later | adding a nullable organisation column to a pair-unique model is a data-splitting job | merging threads is also a data job; roughly symmetric |

## 5. Reasoning and caveats

- The decisive point is that the policy resolves per pair on the site (spec 3 decision 5) and that
  colleagues have no `Learner` row. Both make a stored organisation either unused or partial.
- Spec 5 genuinely needs an organisation *view*, and `learners_visible_to(user, organisation)`
  already supplies exactly the filter, including the permission rule, so the organisation view
  comes free and cannot disagree with who the educator may see.
- Accepted costs: (a) a multi-organisation educator sees the same learner thread in two inboxes;
  (b) no stored answer to "which organisation was this started in", so it cannot be reported on
  afterwards; (c) colleague conversations need a spec 5 decision about where they appear. If (b)
  matters later, an optional nullable `started_in_organisation` is additive and does not change the
  uniqueness key, so the choice is reversible in the cheap direction, whereas per-organisation
  uniqueness is not.
- Spec 4 must still say what the thread shows when the policy stops permitting the pair: history
  readable, composer replaced by a reason keyed on `MessagingRefusal`. Per-pair identity makes this
  one state per thread rather than per (thread, organisation).
- Recommended model: option C (participant rows plus an ordered pair key unique per site), with
  `last_read_at` on the participant row, and the creation function the only writer of the pair key.
  If the spec author prefers fewer moving parts, option A with a transactional get-or-create is
  acceptable; option B is rejected because of the OR-on-two-columns inbox query and the dead end for
  later group conversations.

## Reference URLs

- Canvas Conversations API: https://canvas.instructure.com/doc/api/conversations.html
- Slack and Moodle behaviour above is stated from general product knowledge and was not fetched
  here; confirm before quoting.

status: ok
