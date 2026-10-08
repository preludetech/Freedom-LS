# Research: what happens to an existing conversation when the rules change

Context: spec 3 (`MessagingPolicy`) answers three questions for a pair of users on a site: may the sender start, may the sender reply, and which users may the sender start with. This note covers the open question of what "may reply" means once an established one-to-one conversation exists and the rules, registrations or relationships underneath it change.

Evidence strength: Canvas and Teams findings are from community threads and forum posts (partly behind login walls); Moodle, Slack and Discord findings are thin and partly inferred from documentation; the safeguarding material is guidance text, not a study. Treat prior art as illustrative, not definitive.

## 1. Prior art

**Canvas (closest analogue, and a cautionary tale).** When a course concludes, Canvas stops instructors replying to or messaging students in that course through the inbox, but a student can still reply to an existing conversation, and the instructor sees it. The reverse is the painful case: replies the instructor writes after the end date appear in the instructor's thread but the student never receives them. Both sides believe the conversation is live. A community idea ("Fully Obey Course Participation Settings and Dates") asks for replies to be refused after the end date, including replies by email, with a message saying the course has ended. A separate forum thread reports "Inbox won't allow reply through Section end date". Lessons: (a) the rule is evaluated per reply against current course state, not against how the conversation began; (b) it was applied asymmetrically and silently, which is the worst outcome; (c) the community's ask is a visible refusal, not a silent drop. This matches the rule already in spec 4: no reply is accepted and then left undelivered. (The existing `research_comms_ux_pitfalls.md` already records the silent-failure complaint.)

**Moodle.** Moodle messaging is built on conversations that persist independently of enrolment. A user can choose to accept messages only from contacts, or from contacts and people sharing a course; an admin can enable site-wide messaging (`messagingallusers`). Deleting a message only removes it for the deleting user. Moodle docs do not describe unenrolment behaviour for an existing conversation (I could not find a source); from the model, the history stays and whether a reply is allowed is decided at send time from the recipient's privacy preference, contact status and block status, not from the original conversation. Treat this as inference. Block in Moodle is a per-user preference that overrides course sharing.

**Microsoft Teams.** A participant removed from a chat keeps read access to history up to the removal and cannot send afterwards. That is read-only archive plus refusal to send, triggered by a membership event. Guest removal is the same pattern, with the guest's history retained.

**Slack.** Deactivating a member keeps their messages and DM history for history and search, with a "deactivated" label on the profile. The source does not state how replying is handled, but a deactivated account cannot receive a reply in any meaningful way. Pattern: history preserved, the counterpart is labelled, not erased.

**Discord.** Existing DM channels persist after two people stop sharing a server. Whether a new message is deliverable depends on the recipient's privacy setting ("allow DMs from server members") evaluated at send time, so leaving or being banned from the shared server can make a DM fail even though the channel exists. Blocking hides the blocker's view of the history behind a "Blocked Message" bar and stops new messages; the blocked party's history view does not change. Pattern: re-check at send, blocking is asymmetric in what each side sees.

**LinkedIn and marketplaces (general knowledge, not sourced here).** Removing a connection typically leaves the message thread readable but restricts new messages to what the current relationship and settings allow; blocking removes the thread from the blocker's view and prevents contact. Not verified against current documentation; weight low.

**Safeguarding guidance (UK).** DfE "Guidance for safer working practice for those working with children and young people in education settings" (Feb 2022) and school policies derived from it say staff should communicate with pupils only through approved school systems, should not accept communications from learners or their families past or present on personal channels, and that any pre-existing relationship is to be raised with the Designated Safeguarding Lead and recorded. Reading: when the formal relationship ends, contact should not continue informally, and the institutional channel is the only sanctioned one. That argues against an educator-side grace period that lets an educator keep initiating or replying after the learner is no longer theirs, and for keeping a record on the institution's system. It does not say a learner must be prevented from replying, so it supports the asymmetry in section 2. This is guidance for schools; FLS sites serving adults are not bound by it, and spec 3 already puts stricter safeguarding modes out of scope.

## 2. Patterns

| Pattern | Reply rule | History | Examples |
|---|---|---|---|
| A. Re-check on every reply | Current policy decides each reply | Stays readable; composer replaced by a reason when refused | Teams, Discord (settings), Moodle (inferred), Canvas (course-state part) |
| B. Grant persists | A legitimately started conversation may always be replied to | Readable | Canvas learner side in practice (student can still reply), email-style threads |
| C. Hybrid: educator side re-checked, learner side persists | Educator reply needs current visibility; learner reply to an educator who messaged them is allowed unless blocked or removed from the site | Readable | Not seen as a named product pattern; a plausible design |
| D. Hide on loss of relationship | Conversation disappears from the inbox | Hidden | Discord block on blocker's side only; rarely used for ordinary rule changes |

Further observations:
- **Read-only archive versus hidden.** Products overwhelmingly keep history visible to the person who lost the ability to send (Teams, Slack, Discord). Hiding is reserved for the blocker's own view. Hiding a thread because a registration lapsed would also hide something the user may need (for example an instruction or a complaint trail).
- **Educator versus learner.** Safeguarding and power asymmetry argue for treating the educator side more strictly: an educator no longer responsible for a learner has no business initiating or continuing contact. The learner side needs more care because refusing a learner's reply produces the Canvas "shouting into a void" experience, and a learner replying to an educator is low risk. But a learner who is removed from the site (`Learner.is_active=False`) has no access to FLS at all, so the question is moot for them.
- **Blocking overrides everything.** In every system found, block wins over any persisted grant: no new messages in either direction from the blocked party to the blocker, history kept. Spec 6 already settles that "a block only ever removes permission".

## 3. What the "may reply" question needs as input

The decision here is about the shape of the contract, even if the default rule is chosen later.

- **Pattern A (re-check) needs only the pair** `(sender, recipient, site)`. This is what the draft contract already supplies. The reply check can be the same predicate as the start check, or a looser one.
- **Pattern B (grant persists) needs the conversation**, not just the pair: at minimum "a conversation between these two exists on this site". Since conversations are one-to-one and a pair holds at most one per organisation (spec 4 open question), the pair plus the site may be enough to answer "has a conversation been legitimately started", but only if spec 4 guarantees the existence row. To be robust, pass the conversation (or its initiator, creation time and organisation) in.
- **Pattern C (hybrid) needs to know who started it and the roles of each side**: who initiated (educator or learner), and which side the sender is. Role-per-side comes from the policy's own relationship queries; initiator needs the conversation.
- **When it started** matters only if the rule is time-bound ("grant lasts N days after the last permitted state") or if a site wants "conversations started before the change stay open". Cheap to pass; expensive to retrofit.
- **Organisation context.** `Learner` is per organisation. If a pair has one conversation per organisation, the organisation is part of the question; if one overall, the policy must say which organisation's configuration governs, which links to the "whose context decides a pair" open question in the idea.

Therefore a reply check that takes `(sender, recipient, site, conversation)` supports A, B and C. A pair-only signature forces A. Passing the conversation costs nothing today and lets a swapped policy implement B or C without a contract change.

**Which spec owns what**
- Spec 3 (policy contract): the signature of the reply question, the default rule, and the shape of the answer. Recommend the answer carries a refusal reason (a small reason code or label) rather than a bare boolean, so spec 4 can render "why not" instead of guessing. Spec 3 also owns the relationship queries, whose inactive-row rules (`Learner.is_active`, inactive registrations) already determine most rule changes. Spec 3 owns not caching the answer across requests.
- Spec 4 (thread UI and send path): history stays readable when reply is refused; the composer is replaced by a short reason from the policy; the server re-checks on send and rejects with a visible error (the rule already settled in spec 4); the inbox keeps listing the conversation; unread state and the notification behave sensibly for a conversation nobody can answer (notification still raised for a message sent while permitted; no new notification once refused).
- Spec 6 (report and block): block is checked on top of the policy for both start and reply, in both directions; a blocked sender gets a refusal wording decided there; reporting must stay possible on a conversation in which replying is refused, since moderation does not depend on messaging permission. The policy contract just needs to be composable with a block check (policy first, block narrows), which it is.

## 4. Common complaints per pattern

- **A. Re-check on every reply.** Learners lose the ability to answer a question the educator asked, for example "can you reply with your result?" after a cohort ends. Educators feel cut off from a learner who needed follow-up. The conversation looks live but is not (Canvas) when the composer shows no reason. Surprise that a config change mid-conversation silently changes behaviour. Mitigated by a visible reason and by keeping history readable.
- **B. Grant persists.** An educator or learner whose relationship ended can keep contacting the other indefinitely; this is the safeguarding concern in the UK guidance and is hard to turn off, because closing configuration appears to do nothing for existing conversations. Admins who "closed messaging" find messages still flowing. Removed or lapsed participants can still message people, which is the worst surprise for a site admin.
- **C. Hybrid.** Hard to explain and to document; two rule sets to test; sites ask "why can the learner reply but I cannot?". Canvas shows how this feels (the learner can reply, the instructor cannot, and the instructor's reply goes nowhere). A hybrid is only tolerable if the refusal is visible on the restricted side and the unrestricted side is told nothing misleading.
- **D. Hide.** Users report lost threads and cannot find an earlier instruction or answer; no evidence trail for complaints; support burden.
- **Silent failure in any pattern** is the dominant complaint in the sources (Canvas): "message sent" displayed, nothing delivered.

## 5. Recommendation

**Recommended default for the shipped `DefaultMessagingPolicy`: pattern A with a learner-side exception limited to replying, and always keep history readable.**

Concretely:
1. **Contract.** `may_reply(sender, recipient, site, conversation)` returns a decision carrying an allow flag and, when refused, a reason code. Pass the conversation (or the initiator, creation time and organisation) so a replacement policy can implement B or C. The policy itself must not cache. The queryset question for starting is unchanged.
2. **Default rule.** Evaluated against the current rules each time, using the same relationship queries as start. Out of the box: an educator may reply to a learner while `learners_visible_to` still includes that learner; a learner may reply to an educator while that educator still counts as one of the learner's educators (the inverse query), and both sides are active on the site. No special grant. Reasons: this keeps the policy a single honest answer to "who can reach whom now", matches the way closing configuration is expected to work, and matches the safeguarding reading that an ended relationship should not continue on the institution's channel.
3. **When a rule closes, the conversation stays readable to both sides** (Teams, Slack, Discord pattern). It is not hidden. Hiding is spec 6's concern for block only, and even there nothing is deleted.
4. **Configuration closed versus relationship ended.** Treat them the same in the default, since the policy cannot tell which the site admin intended. If a site wants "existing conversations survive a closed configuration", it replaces the policy class or a later spec adds a level flag; do not build it now ("Don't build functionality that is not explicitly requested").
5. **Removed learner (`is_active=False`).** Both directions refuse, and the counterpart's thread shows a neutral reason. The removed learner cannot log into this learner's FLS access anyway.
6. **Educator losing the role.** The educator can no longer reply; the learner's reply is refused with a visible reason ("this person can no longer be messaged"), not silently. This is a symmetric consequence of the inverse-visibility rule already settled in the idea, which is also the reason the "educators of a learner" query and `learners_visible_to` must agree.
7. **Block.** Spec 6 layers it on top: a block refuses start and reply in both directions with the policy first and the block narrowing. Nothing in spec 3 needs to change, provided the reply decision is a composable value with a reason.

**Trade-offs**
- Pattern A is simplest and safest for safeguarding, and consistent across start and reply, but it can strand a learner mid-conversation. The mitigation is the visible reason and readable history; the cost is a possibly frustrating moment at the end of a cohort.
- Pattern B protects conversation continuity and avoids stranded learners, but defeats "closed by default" as the site admin understands it, and conflicts with the safeguarding guidance for any site with minors.
- Pattern C, the learner-reply-persists variant, is attractive for learner experience and low safeguarding risk (a learner replying to an educator who has already contacted them), but it adds a second rule set and is harder to explain. If a first user complaint arrives, it is a small addition because the contract already receives the conversation and the initiator.
- Passing the conversation into the contract costs one extra argument now and avoids a contract change later; a pair-only signature is smaller but forces pattern A for ever.

**Open items to resolve in the spec (not decided here)**
- Whether a pair holds one conversation overall or one per organisation (spec 4), because it decides which organisation's configuration governs a reply.
- The exact refusal reason codes and their user-facing wording (spec 4 renders them; spec 3 defines the codes).
- Whether a missing or inactive `Learner` row for the sender counts as "removed" or as a plain refusal.

## References

- Canvas Community idea, Fully Obey Course Participation Settings and Dates: https://community.canvaslms.com/ideas/14115-canvas-inbox-messages-fully-obey-course-participation-settings-and-dates
- Canvas Community thread, Inbox won't allow reply through Section end date: https://community.canvaslms.com/t5/Canvas-Question-Forum/Inbox-won-t-allow-reply-through-Section-end-date/m-p/544950
- Canvas Community, Instructors should be notified if replies are not being sent: https://community.canvaslms.com/t5/Canvas-Ideas/Inbox-Instructors-should-be-notified-if-their-reply-to-student-messages-are-not-being-sent/idi-p/459542
- Moodle docs, About messaging: https://docs.moodle.org/en/message
- Moodle docs 4.2, Messaging: https://docs.moodle.org/402/en/Messaging
- Microsoft Tech Community, Guest users removed from Teams group chat: https://techcommunity.microsoft.com/discussions/microsoftteams/guest-users-removed-from-teams-group-chat/4394012/replies/4395107
- Torii, Slack user removal (deactivated users keep messages): https://www.toriihq.com/articles/slack-user-removal
- Discord support community, DM still possible when you are banned: https://support.discord.com/hc/ja/community/posts/360051947594-DM-still-possible-when-you-are-banned
- Redact community, What happens to old Discord messages when you block someone: https://community.redact.dev/t/when-you-block-someone-on-discord-does-it-delete-the-old-messages/125
- DfE, Guidance for safer working practice for those working with children and young people in education settings (Feb 2022): https://www.wigan-leigh.ac.uk/wp-content/uploads/2025/07/Guidance-for-safer-working-practice-for-those-working-with-children-and-young-people-in-education-settings-Feb-2022.pdf
- Three Counties Academy Trust, Professional Boundaries with Pupils Policy: https://files.schudio.com/three-counties-academy-trust/files/documents/SG12_Professional_Boundaries_with_Pupils_Policy.pdf

status: ok
