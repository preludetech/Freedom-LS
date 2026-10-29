# Research: known complaints about in-app LMS messaging

Question: what do users commonly complain about with this kind of work?

Caveat: web searches found mostly forum posts and vendor blogs. No r/Professors or r/Teachers threads and no app-store reviews surfaced. Several Canvas threads date from about 2023. Each claim below is tied to its source, and prevalence is not measured.

## 1. Web findings

### 1.1 Messages that go unnoticed or never arrive (Canvas Inbox)
- Email notifications for Inbox messages skip some senders or stop without any settings change. Notification settings show three "Conversations" lines and the labels confuse people.
  - https://community.canvaslms.com/t5/Question-Forum/Not-all-Inbox-notifications-not-being-sent-to-email/m-p/200792
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Two-Inbox-questions-re-notifications-and-formatting/m-p/558127
- Students report replies that "don't go through". Staff answer "check Sent". The sender gets no delivery or read feedback.
  - https://community.canvaslms.com/t5/Question-Forum/Inbox-messages-not-going-through/td-p/393046
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Conersation-not-appearing-in-Canvas-inbox/m-p/524513
- Sending to yourself shows no copy in the Inbox, which surprises people (same threads).
- The Inbox is another channel competing with university email. Instructors want to hide it. Some want basic text formatting.
- Lesson: show delivery and sent state clearly. Keep notification categories few and plainly labelled. A message must be findable in one place.

### 1.2 Educators overwhelmed by learner DMs
- Instructors with 1,000 to 2,000 students per term cannot switch the Inbox off per course. They ask for auto-reply or out-of-office, partly for wellbeing and to avoid false response-time expectations.
  - https://community.canvaslms.com/t5/Idea-Conversations/Auto-reply-for-Canvas-messages/idi-p/334329
- Students skip the syllabus and forget each teacher's contact rules.
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Student-messages/m-p/71752
- Workarounds seen in the wild:
  - Handle messages only while logged into the course (York eClass blog): https://www.yorku.ca/professor/drsmith/2020/08/27/eclass-messaging/
  - Push information through Announcements instead of DMs (Columbia): https://support.ctl.columbia.edu/1813810
- A Canvas idea asks for a course inbox with a shared archive, so questions are not buried in one person's inbox. https://community.canvaslms.com/t5/Canvas-Ideas/Inbox-Enable-a-Course-Inbox-with-Shared-Archive/idi-p/618495
- Lesson: learner-to-educator messaging needs routing (the shared help-desk) and educator controls. These could be an availability notice, an off switch per educator or course, and a nudge to check the content first.

### 1.3 Finding the right recipient (Moodle, Canvas)
- Moodle visibility depends on settings: contacts only, contacts plus classmates, or site-wide messaging. Search returns grouped sections (Contacts, Non-contacts, Messages).
  - https://docs.moodle.org/38/en/Messaging
  - Privacy bug MDL-65023: course contacts were findable by users who shared no course and were not contacts. https://tracker-old.moodle.org/browse/MDL-65023
- Moodle messages have users build a contact list before they can talk to people. Recipient search is a known friction. The two failures to avoid are an unusable search and a search that leaks people the viewer should not see.
- Lesson: this matches the idea ("see all the users we can message, quick filter"). Scope the candidate list by the messaging policy. Never list people the viewer may not message.

### 1.4 Harassment and spam between learners
- One university turned off students' ability to message the whole class at once because staff feared inappropriate spam (found via the Canvas/WWU search: https://atus.wwu.edu/kb/changes-canvas-inbox-messaging).
- Moodle gives teachers delete-any-message capability in group conversations (`moodle/site:deleteanymessage`), so moderation exists but is capability-gated. https://docs.moodle.org/38/en/Messaging
- Lesson: learner-to-learner messaging needs a block or report path, per-organisation off switches, and no mass-send. The repo already has a messaging policy (user-communication-3) and block/report designs (section 2).

### 1.5 Privacy of messages and admin oversight
- Canvas staff answer: Inbox messages are visible to sender and listed recipients only. An admin can see all messages but rarely does. Instructors and TAs see only messages sent to them. Admins with masquerade rights can see messages, and a subpoena can compel disclosure.
  - https://community.canvaslms.com/t5/Question-Forum/Private-conversation-between-all-students-in-the-class/td-p/460080
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Canvas-private-massages/m-p/605253
- Research shows students are often unclear about what the LMS collects and who can see it. Instructors are largely unaware too.
  - https://scholars.uky.edu/en/publications/information-flow-solipsism-in-canvas-an-exploration-of-student-pr/
  - https://conpro23.ieee-security.org/papers/schmidt-conpro23.pdf
- The EFF documents LMS data being misread by administrators and used against students. https://www.eff.org/deeplinks/2022/04/canvas-and-other-online-learning-platforms-arent-perfect-just-ask-students
- Lesson: admin oversight (idea: org admin sees educator-learner comms) will be a trust issue. Disclose it in the UI where people write. Limit scope to educator-learner threads, not learner-learner. Consider an audit trail of who read what. The repo already has an educator-interface audit-log design.

### 1.6 Shared inbox: who is handling this?
- Standard help-desk complaints: two agents answer the same person, and nobody owns a message because each assumes someone else replied. Fixes are one owner per conversation, visible history, collision detection (flags a teammate viewing or replying), and claiming before drafting. The 23% duplicate-reply figure from one guide is unverified.
  - https://help.devcloudsoftware.com/blog/what-is-a-shared-inbox
  - https://www.getmailbird.com/shared-inbox-accountability-system-design/
  - https://www.helpspot.com/shared-inbox
  - https://www.getmailbird.com/distributed-teams-gmail-shared-inbox-ownership/
- Lesson: help requests from the course player need a visible assignee and status. The learner should see who picked up the request and who answered.

### 1.7 Duplicate or inconsistent badges
- No source discusses a messages icon badge plus a bell badge for the same event as a design complaint. Found instead: badge counts that disagree with the in-app unread count.
  - Telegram: https://bugs.telegram.org/c/203/87
  - Microsoft Teams iOS: https://support.microsoft.com/en-gb/topic/incorrect-notification-count-in-teams-for-ios-ade8a6d6-4aad-4ea3-9617-11850ebc30a3
  - FirstUp: https://support.firstup.io/hc/en-us/articles/41510231432343-Known-Issue-Inconsistency-on-Notification-Badge-Count-FE-29638
- Lesson: the idea's rule (a new message appears only on the messages icon, not the bell) removes the duplicate. The risk then is the two counts drifting. Compute the messages count and the bell count from one source, and make it clear what each one counts.

### 1.8 Losing context of which lesson a question is about
- No direct source found. By inference from Canvas Inbox threads, which are not tied to content, learners paste links by hand and educators ask "which page?". The idea's contextual help request therefore needs to carry the content item and its link automatically. Treat this as an inference, not a sourced finding.

## 2. This repo's own QA reports

- user-communication-1-notifications-core, qa_report.md: no bugs. Observations that apply here:
  - Focus drops to `<body>` after an in-place pagination swap.
  - Session expiry redirects to `next=/notifications/` instead of the page the user was on.
  - The unread state is not in the link's accessible name.
  - Mobile row buttons are 46x35, under the 44px touch guideline.
  - The failure panel once closed itself during an outage.
- user-communication-3-messaging-policy, qa_report.md: one bug, fixed. Mobile and tablet "Offered educator roles" checkboxes were unstyled 17px rows, and mobile changelist cards clipped long names.
- user-communication-4-direct-messaging, qa_report.md: 0 bugs. Observations that are UX complaints for this work:
  - Day separators are repeated by the sender line ("You · 19 Oct").
  - Mobile educator section cards show an empty "Status" label for read conversations.
  - Mobile educator thread page stacks two back controls ("← Messages" and "Back to messages"). This fits the idea's removal of the index page.
  - Rollup rule: a bell row "New message from X" is created per unread episode, so Eve's bell held three read rows. This is the duplicate-notification source the idea wants removed.
  - A quick view refetches only on a client `learnerChanged` event, so another person's changes show up late.
  - A learner with no recipients gets no New message button (3. frontend_qa), which is the learner complaint in the idea ("can't start new threads").
  - Stale picks are refused with a 422 and the draft is kept. A double-send duplicate risk was in the QA plan.
- better-looking-notifications (design docs): has report/block designs (uc-10) and a queue (uc-11). These are prior art for harassment handling.

## 3. Complaint checklist for the spec

1. Delivery and sent state visible. A failed send keeps the draft (done in user-communication-4; keep it).
2. One count per event. No bell row for messages. Messages count and bell count come from separate, documented sources.
3. Recipient picker lists only allowed people, with a filter. No leaks beyond policy.
4. Educator load controls. Routing to the help-desk, ownership and status, an availability notice. Consider throttling.
5. Help requests carry the content context automatically.
6. Help-desk shows assignee, status and replier. Avoid collisions.
7. Admin oversight is disclosed to participants, scoped to educator-learner threads and audited.
8. Learner-learner messaging has block/report and no mass send.
9. Accessibility, mobile touch targets (44px) and focus handling.

status: ok · reason: web and repo QA research done; no Reddit, app-store or Moodle forum complaint threads were reachable, so section 1 relies on Canvas forums, vendor docs and research papers
