# Research: prior art for user-communication-ux-improve

Question: what has already been tried for this, here or elsewhere, and what happened?
Research was done by reading the repo files (no git log available, only Read/Glob/Grep/Web).

## 1. Here: what already exists and what it decided

### Shipped (all in `spec_dd/3. done/`)

- `2026-09-27_00:24_user-communication-1-notifications-core`: the bell, `raise_notification`, `Notification` with read/seen state. `better-looking-notifications` restyled it.
- `2026-10-10_08:57_user-communication-3-messaging-policy`: `MessagingPolicy` (swappable class, default `LayeredMessagingPolicy`). Layered flags `learner_to_educator`, `learner_to_cohort_peer`, `learner_to_course_peer`; **all default `closed`** (`MESSAGING_DEFAULT_FLAGS`). Offered educators default to `["cohort_admin"]` only. Config is per site, organisation, cohort/registration and learner, most specific wins.
- `2026-10-22_20:02_user-communication-4-direct-messaging` (absorbed planned spec 5, educator messaging): `Conversation`, `ConversationParticipant`, `Message`; shared inbox, thread, new-conversation picker; header Messages button with polled count; educator-interface Messages section with polled sidebar count; message box in the learner quick view; rollup notification `message.received`. `MESSAGING_ENABLED` is off by default. QA: 0 bugs, 89 screenshots, all sections passed (`qa_report.md`).

### Decisions in spec 4 that this idea reverses or reshapes

| Idea item | What spec 4 decided | Source |
|---|---|---|
| No bell notification for new messages | Spec 4 raises one **rollup** bell notification per unread conversation (`message.received`, "New message from X", no excerpt), updated in place, cleared when the thread opens. It is built, QA-tested (§8) and the roadmap treats it as a delivery contract for spec 2 (email reads `Notification.message` at send time). Removing it touches `FLS_NOTIFICATION_CATEGORIES`, `rollup_key`, `mark_notifications_read`, and the planned email spec 2 which assumes the rollup. | spec 4 "Notifications" section; roadmap "Delivery contract for spec 2" |
| Icon-only header button | Spec 4 originally asked for icon plus aria-label. QA found the design showed a label, so the team **decided** to show a visible "Messages" label from `lg` up and icon-only below, corner badge kept, and updated the spec. This idea reverses the desktop half of that decision. | spec 4 `todo.md` line 58; QA 2.1, 12.1 |
| Header button opens the inbox | Decision 3: the button **always opens the shared inbox**, for educators as well. A dropdown of recent messages is new work (no dropdown of recents exists; note `<c-dropdown-menu>` is a menu button and the bell panel is the nearest pattern). | spec 4 Decisions 3 |
| Remove messages index page, keep list-left/thread-right | The shared page already is list-left, thread-right on desktop (QA 3.1). On mobile the inbox is a separate screen with a back arrow (QA 12.1). So "remove the index" really means: make `/messages/` land in the two-pane thread view with the newest conversation (or an empty thread state) selected. Empty-state copy today: "Your educators can message you, and you can reply." | QA 2.2, 2.4, 3.1, 12.1 |
| New conversation from the thread view with a filterable list of everyone | Already built as a "New message" modal (To field focused, grouped list, search narrows, name+email for educators, 'No one you can message matches ...' for zero results). The `New message` button appears only when the policy yields recipients (hidden for a learner with policy closed, QA 2.2/2.4). The research recommendation was search-first, server-filtered, capped (~20), grouped as presentation, with a threshold: up to ~15 recipients show all, above that require 2+ chars. No combobox with arrow keys exists in FLS; the simpler search box plus button list was recommended. | `research_recipient_picker_at_scale.md`; QA §6 |
| Learners start threads with educators and each other | **Already supported when the policy is open**: QA 6.2 (site `learner_to_educator=open`: Lena's inbox gains New message, picker shows a "Cohort admin" group with no emails, no word "instructors") and 7.5 (peer messaging via `learner_to_cohort_peer`). The idea's complaint ("learners can only see threads with messages") is the **default-closed policy**, not missing UI. Peers default closed deliberately because the picker would newly disclose classmates' names. | spec 3 settings; QA 6.2, 7.5; `research_recipient_picker_at_scale.md` §3 privacy |
| Educator sees learner comms on the learner page and can send | Partly built: the **quick view** has a Messages box (last 3 messages, composer, Open conversation link; QA §10) and the Messages section has per-learner threads. Not built: a tab on the full learner page (`/educator/organisations/<org>/learners/<uuid>`). Spec 4 decision 2 lists only learner conversations of the selected organisation in the section; colleague conversations stay in the shared inbox only. Educator Messages section also hides threads the educator is no longer allowed to see (404 by pk, QA 9.6 to 9.9). | spec 4 Decisions 1, 2; QA §5, §9, §10 |
| Remove educator Messages page, use top header | Spec 4 built the sidebar Messages section (own polled count, per-organisation, 404s for other orgs) and, **separately**, the header button to the shared inbox, which also lists educator threads (QA 5.7: includes Eli Educator, Gus Gone, deleted user). Two surfaces with different scopes exist on purpose (organisation-scoped vs site-wide). Collapsing them loses organisation scoping unless the shared inbox gains an organisation filter. The sidebar count and header badge are documented as allowed to disagree (QA 11.2). | spec 4 Decisions 2, 3; QA 5.7, 11.2 |
| Org admin sees comms between educators and learners | **Deliberately not built.** Decision 5: models not registered in Django admin so "private message bodies stay out of staff view"; spec 6 (moderation) was to build the report queue where site admins hide messages. Org admin reading other people's conversations is a privacy reversal, not an extension, and the educator section's visibility rule is "conversations you are a participant in" (`QA 5.2`: Eli Educator, Gus Gone etc. absent for Eve). Thread pages 404 for non-participants (QA 9.4). The idea would need an explicit disclosure to participants and likely an audit log (see 2. Overlaps). | spec 4 Decision 5; QA 9.4, 5.2 |
| Course-player help request to a shared help desk with tickets | **Not planned anywhere.** Grep for help desk / help ticket / support ticket across `spec_dd/` found nothing outside this idea. Spec 4 scope explicitly excludes group conversations and broadcasts; a conversation is exactly two users (`pair_key`). A help desk (many educators, one queue, claim/assign, status) is a different model from the two-person `Conversation`. Roadmap decision 1: "Two channels: notifications and direct messaging. Announcements, discussion forums and inline feedback on content are not in this effort." | spec 4 Scope "Out"; roadmap Decisions 1 |

### Deferred or decided against (relevant)

- Group conversations, broadcasts, attachments, editing, deleting, typing indicators, presence: out of spec 4.
- Real-time push: spec 8 (optional Django Channels), polling is the transport (roadmap Decision 2). Any dropdown of recent messages must also work on polling alone (the header badge polls `/messages/badge/`; thread polls every 8s, inbox every 45s).
- Report and block: `user-communication-6-moderation`, still `next`. It adds controls to the thread views and a report queue; a new thread layout and any org-admin oversight must coordinate with it (shared files, threat of rework).
- Email: `user-communication-2-notification-email`, still `next`, depends on the rollup notification.
- Spec 3 research noted "moderated messaging" (messages go to an instructor queue before delivery) as a possible install need but kept the queue itself out of scope (`research_flexible_configurable_comms.md`, lines ~269 and 594).
- Messaging model decision that matters for learner-initiated help: one conversation per pair of users per site, no organisation stored (Decision 1). A "help request" to "the educators" has no single recipient; a learner would need a recipient resolved by the policy (offered educators default to `cohort_admin` only).

### Overlap with other planned or in-progress work

- `in-app-feedback` (in progress, spec/plan/QA plan exist): configurable feedback prompts at pause points with rating and free text, registry of trigger points, modal with thank-you message. It touches the course player/trigger-points area, not messaging. A "ask for help here" control in the course player would sit in the same page regions and could reuse its trigger/modal mechanics. No ticket or reply loop in it. Risk: UI collision on the player chrome, not data model collision.
- `educator-interface-11-audit-log` (done 2026-10-29): relevant precedent for org-admin oversight. It scopes entries per organisation and tests that an org admin sees only their own organisation. If oversight of comms is built, it likely should write audit entries on access.
- `multi-step-course-applications` idea (line ~206) states anonymous applicants cannot use `comms` direct messaging; separate request channel needed. Same constraint: `comms` is for users with accounts.
- `deadlines-5-reminders`, `user-communication-2`, `-6`, `-8`: touch notifications and thread views; sequencing/conflict with notification removal and thread layout changes.
- Nothing named "ticket" or "help desk" exists in the repo as planned work. This is greenfield.

### Observations from spec 4 QA that this idea overlaps

- Two back controls stack on the mobile educator thread (observation, no action). A single two-pane thread view is a chance to fix it.
- On mobile educator cards show a 'Status' label with an empty value for read conversations.
- Sender lines on older days show a date rather than a clock time, repeating the day separator.
- Sidebar count and header badge can disagree by design (organisation-scoped vs all).
- The New message modal originally lost drafts when the recipient stopped being messageable; fixed (422 with draft kept). Any new "start from the thread view" flow must keep that behaviour.

## 2. Elsewhere (web)

Prior in-repo research (`research_prior_lms_messaging_ux.md`, dated 2026-02-21) already covers Canvas, Moodle, Google Classroom, Blackboard and Schoology. Key points that bear on this idea are repeated here with the sources; the new web searches add the items marked "new".

### Learner-to-learner messaging: spam, harassment, controls

- Canvas has no built-in per-student block. Community requests ask for it: https://community.canvaslms.com/t5/Canvas-Ideas/Inbox-Allow-students-to-block-messages-from-other-students/idc-p/536738 and https://community.canvaslms.com/t5/Canvas-Ideas/Account-Settings-Inbox-Give-Canvas-Admins-control-to-block/idi-p/656924. The closest control is turning off the "Conversations - send messages to individual course members" permission for the student role, which is all-or-nothing for the course (new; from the first link's thread). Course-level control request: https://community.canvaslms.com/t5/Canvas-Ideas/Course-Settings-Control-Conversations-at-a-Course-Level/idc-p/418055.
- One university turned off its "all in" student messaging in 2018 after faculty reported spam, pointing instructors to Discussions for group communication while keeping one-to-one student messages (new): https://atus.wwu.edu/kb/changes-canvas-inbox-messaging.
- Harassment in LMS messaging is typically handled outside the tool (instructor, institution, Title IX), with screenshots as evidence (new): https://community.canvaslms.com/t5/Canvas-Question-Forum/Is-there-a-way-to-block-someone-in-my-inbox/m-p/521493.
- Moodle: some admins disable messaging entirely because unsupervised student-to-student messaging enables bullying (https://moodle.org/mod/forum/discuss.php?d=410788). Moodle's privacy options are per user (contacts only, or contacts plus course members); admin can enable site-wide messaging (https://docs.moodle.org/502/en/Messaging). Pitfall (new): choosing "contacts only" also blocks tutors from messaging the student (University of Edinburgh guide, https://www.moodle.is.ed.ac.uk/pluginfile.php/10119/mod_resource/content/13/messages_student_2023.pdf). Lesson for FLS: any learner-side block must not silently cut off educators; spec 6's block design should be checked for this.
- Schoology: students cannot message each other unless an admin enables it, which limits peer collaboration (https://uc.powerschool-docs.com/en/schoology/latest/send-messages). Schoology mass messages create individual threads (privacy-safe).
- Takeaway: platforms ship learner-to-learner messaging closed or admin-gated; where it is open the control levers requested afterwards are block and report, which is FLS spec 6 (not yet built). Opening learner-initiated threads before spec 6 means no report or block exists.

### Contextual help from the course player

- Google Classroom ties communication to the work: private comments on an assignment keep the recipient implied and the context attached; there is no general DM (https://support.google.com/edu/classroom/answer/9093530?hl=en). Praised for simplicity (per the in-repo summary).
- Moodle institutions typically separate technical help (a help tab or button routed to an IT queue, e.g. https://www.okanagancollege.ca/node/10323, https://helpdesk.earlham.edu/TDClient/57/Portal/Requests/ServiceDet?ID=1565) from course-content questions (to the instructor, after self-help). Brandeis splits tech issues from registrar issues (https://guides.library.brandeis.edu/moodlefaculty/facultyquickstartguide). The pattern is routing by question type, not one undifferentiated help channel. My search found no documented "ask for help on this lesson" button with measured outcomes; this is an evidence gap, not evidence of failure.
- Instructor workload: fielding learner questions around the clock is one of the main reasons online teaching feels heavier; faculty want students to know questions get answered without being "in my class 24x7" (https://www.facultyfocus.com/articles/online-education/online-course-design-and-preparation/time-management-tips-for-online-instructors/, https://www.facultyfocus.com/articles/online-education/three-ways-to-efficiently-and-effectively-support-online-learners/). Clear course structure reduces repeated logistical questions (same sources).
- In-repo evidence (PMC8287087, https://pmc.ncbi.nlm.nih.gov/articles/PMC8287087/): learners ignore LMS messaging, yet educators resent a new inbox. "Yet another inbox" is the top complaint, which argues for the help-desk queue living inside the surfaces educators already use (educator interface) rather than a new one.

### Shared help-desk queues

- Generic help-desk guidance (vendor material, so treat as practitioner opinion, not research): separate roles for inbox owner, triage lead and responders; rotate triage in small teams; track first-response time, resolution time, backlog; example SLAs 1h critical, 8h standard; canned replies, internal notes, auto-reply confirming receipt (https://www.supportbench.com/?p=25710, https://www.bitrix24.com/articles/help-desk-triage-scales-rules.php, https://www.dragapp.com/blog/shared-inbox-for-customer-support-without-helpdesk/). One higher-ed helpdesk vendor warns that when everything shares one queue at one priority, urgent items sit behind minor ones (https://openeducat.org/feature-helpdesk).
- Education-specific TA/instructor queue studies were not found. Evidence gap.
- Failure modes inferred from the above (labelled as inference): unowned queue (nobody claims), course-content questions routed to educators with no scope, duplicate answers from several educators, learners re-asking because they cannot see status, and escalation of what should be a public Q&A into private one-to-one work.

### Canvas/Blackboard messaging UX complaints relevant to the thread/dropdown work

- Duplicate sends when an error appears and the user clicks send repeatedly (Canvas): FLS already handles with `client_key` idempotency and a disabled Send (QA 9.1, 9.2).
- Moodle's drawer (messaging icon in the top bar, available on any page, starred/group/personal sections, badge on icon) is the closest precedent for the header dropdown of recent messages: https://docs.moodle.org/501/en/Messaging. Blackboard shows the Messages count in base navigation and, on visiting the page, changes the red number to a pill to reduce distraction (https://services.gvsu.edu/TDClient/60/Portal/KB/ArticleDet?ID=6081). Both put a badge on the messages icon rather than, additionally, notifying in the bell, supporting the idea's "no bell entry for messages".
- Canvas, Moodle and Schoology all use a numbered badge on the messages entry, not a bell entry, for new messages.

## 3. Implications for the spec (for the spec author to weigh)

1. Several idea items are already built or are policy settings: learner-initiated threads (set `learner_to_educator` open), picker with search and grouping, educator message box in quick view. The spec should state the gap precisely (empty-state/entry point for learners; a learner-page tab) rather than re-specify.
2. Removing the bell notification for messages is contrary to the shipped rollup design and the email spec 2 assumptions; decide whether to remove it entirely, keep it only for email, or make it a per-category default. Dependency on `user-communication-2` needs a decision.
3. Org-admin oversight reverses Decision 5. If kept, it needs an explicit privacy statement, probably participant-visible disclosure, an access audit entry (precedent: `educator-interface-11-audit-log`), and coordination with `user-communication-6-moderation`.
4. A shared help desk is a new model (many-to-one, status, claim, ticket link) and has no existing "ticket" feature to link to; it likely needs its own spec. Inline help in the player overlaps `in-app-feedback` UI placement.
5. Learner-to-learner opening before block and report exist (spec 6) repeats the Canvas/Moodle experience: spam and harassment handled out of band. Default stays closed per spec 3.
6. Collapsing educator section and shared inbox loses organisation scoping; the badge/count disagreement is documented as intended.

## Sources (web)

- https://community.canvaslms.com/t5/Canvas-Ideas/Inbox-Allow-students-to-block-messages-from-other-students/idc-p/536738
- https://community.canvaslms.com/t5/Canvas-Ideas/Course-Settings-Control-Conversations-at-a-Course-Level/idc-p/418055
- https://community.canvaslms.com/t5/Canvas-Ideas/Account-Settings-Inbox-Give-Canvas-Admins-control-to-block/idi-p/656924
- https://community.canvaslms.com/t5/Canvas-Question-Forum/Is-there-a-way-to-block-someone-in-my-inbox/m-p/521493
- https://atus.wwu.edu/kb/changes-canvas-inbox-messaging
- https://moodle.org/mod/forum/discuss.php?d=410788
- https://docs.moodle.org/502/en/Messaging
- https://docs.moodle.org/501/en/Messaging
- https://www.moodle.is.ed.ac.uk/pluginfile.php/10119/mod_resource/content/13/messages_student_2023.pdf
- https://uc.powerschool-docs.com/en/schoology/latest/send-messages
- https://services.gvsu.edu/TDClient/60/Portal/KB/ArticleDet?ID=6081
- https://support.google.com/edu/classroom/answer/9093530?hl=en
- https://www.okanagancollege.ca/node/10323
- https://helpdesk.earlham.edu/TDClient/57/Portal/Requests/ServiceDet?ID=1565
- https://guides.library.brandeis.edu/moodlefaculty/facultyquickstartguide
- https://www.facultyfocus.com/articles/online-education/online-course-design-and-preparation/time-management-tips-for-online-instructors/
- https://www.facultyfocus.com/articles/online-education/three-ways-to-efficiently-and-effectively-support-online-learners/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8287087/
- https://www.supportbench.com/?p=25710
- https://www.bitrix24.com/articles/help-desk-triage-scales-rules.php
- https://www.dragapp.com/blog/shared-inbox-for-customer-support-without-helpdesk/
- https://openeducat.org/feature-helpdesk

Repo sources: `spec_dd/3. done/2026-10-22_20:02_user-communication-4-direct-messaging/{1. spec.md,qa_report.md,todo.md,research_prior_lms_messaging_ux.md,research_recipient_picker_at_scale.md}`, `spec_dd/3. done/2026-10-10_08:57_user-communication-3-messaging-policy/{1. spec.md,research_flexible_configurable_comms.md}`, `spec_dd/1. next/roadmap.md` (User communication section, lines 136 to 214), `spec_dd/1. next/multi-step-course-applications/idea.md`, `spec_dd/2. in progress/in-app-feedback/1. spec.md`.

Not verified: git log (no shell); the actual current state of code beyond the QA report; vendor-sourced help-desk numbers are not education-specific.

status: ok · reason: complete; evidence gaps noted for course-player help requests and education TA queues
