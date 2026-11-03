# Research: reference implementations (messaging visibility)

Question: how do other platforms decide whether learners see messaging, where does the toggle live, is the icon hidden or disabled, and what happens to existing threads?

Evidence level: Moodle and Canvas were checked against web search results this session (URLs below). The other platforms are from general knowledge and were not re-verified; treat them as lower confidence.

## Moodle (verified via docs)
- Two levels of site switch:
  - Personal messaging is on by default. An admin turns it off under Site administration > Advanced features ("Enable messaging"). Off means the messaging UI (drawer/icon) disappears for everyone.
  - Separately, "Allow site-wide messaging" (Messaging settings, called `messagingallusers` in code) is off by default. It controls whether users can message people they share no course with. The default is contacts and course peers only.
- Per-user opt-out: each user can restrict incoming messages to their contacts and course members, so the privacy choice sits with the recipient.
- Role capability: `moodle/site:sendmessage` lets a role send messages. The FAQ recipe is to remove it from the authenticated-user role, then grant it to a specific role at system context. A "Cannot send messages" role with the capability set to Prohibit handles misuse.
- There is no course-level switch in core. The nearest equivalents are capabilities overridden in a course context, or the participants list.
- Icon: the whole feature is hidden when the global switch is off. Capability gaps only remove the ability to send, so the icon can still show.
- Existing threads: stored data is kept, but not reachable while messaging is disabled.
- Sources:
  - https://docs.moodle.org/404/en/Messaging_settings
  - https://docs.moodle.org/404/en/Messaging_permissions
  - https://docs.moodle.org/28/en/Messaging_FAQ

## Canvas (verified via community threads)
- Control is by role permission at account level (Account > Permissions > Student role). The relevant permissions are "Conversations - send messages to individual course members" and "Conversations - send messages to entire class". Admins disable them per role.
- There is no course-level toggle. Instructure staff said it cannot be done at instructor level, and several open Idea threads ask for a course-level control. The whole-account scope is a known pain point.
- Side effect reported: disabling the permissions can remove the option to message teachers or "All in Teachers".
- Existing threads: the Inbox still exists, and the restriction is on sending and recipient choice.
- Sources:
  - https://community.canvaslms.com/t5/Canvas-Ideas/Course-Settings-Control-Conversations-at-a-Course-Level/idc-p/418055
  - https://community.canvaslms.com/t5/Canvas-Ideas/Course-Settings-Restrict-Inbox-Conversation-messages-for-a/idi-p/620633
  - https://community.canvaslms.com/t5/Canvas-Ideas/Notifications-Make-inbox-rights-a-user-level-setting/idc-p/348341
  - https://atus.wwu.edu/kb/decision-science-classes-have-canvas-messaging-tools-disabled

## Others (from general knowledge, not re-verified)
- Open edX: there is no learner direct messaging in core. Discussions are a per-course tool that course staff enable or disable under Pages and Resources. When it is off, the Discussion tab vanishes (hidden, not disabled), and the posts stay stored.
- Thinkific, Teachable, Kajabi: community or discussion features are product or space level. Teachers enable them per course or product, and free products often skip them. Navigation entries only appear when the feature is enabled for the school and the learner has access to a community.
- Google Classroom: the teacher sets per-class stream permissions (students can post and comment, can only comment, or only teachers post). Private comments go to the teacher only. Workspace admins control domain-wide who can communicate with whom. Controls are restrictions, not icon hiding.
- Discourse and Slack: admins use site and workspace settings. Discourse has `enable_personal_messages` and a minimum trust level for sending PMs (`personal_message_enabled_groups`), so access is gated by group membership. Slack uses workspace permissions for who can DM or create channels. Both hide the "new message" action from non-permitted users while existing conversations stay readable.

## Patterns that apply to FLS
1. Hide the entry point entirely when the feature is off at the broadest scope (Moodle global switch, Open edX discussions tab). Disabled-but-visible icons are rare.
2. Fine-grained "may send" is a permission or role, which is separate from the visibility switch (Moodle, Canvas, Discourse).
3. The main scopes are site or organisation (Moodle, Canvas, Discourse) and course or product (Open edX, Thinkific). Canvas shows that account-only scope frustrates users who want course-level control. That is directly the FLS case, where some courses are free and others sit inside organisations with messaging on.
4. Existing data is kept when a feature is turned off. Access to old threads is either lost with the UI (Moodle global) or kept read-only (Discourse, Slack). It is rarely deleted.
5. A sensible rule for FLS, which is a design suggestion and not something the platforms prescribe: show the icon if messaging is enabled for the site and the learner has a reason to use it (an organisation or cohort with messaging on, or existing threads). Hide it when the learner is only on free courses with no messaging-enabled organisation and has no existing threads. Keeping the icon when old threads exist avoids stranding them.

status: ok
