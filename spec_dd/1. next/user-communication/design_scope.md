# Design scope: user communication

"The visual-only rule" is the note in `design.md`: the design shows look and feel, and nothing it
draws adds functionality. Rows it settles were not asked one by one.

| Drawn element | Design section | Question asked | Answer | Decided at | Date | Why |
|---|---|---|---|---|---|---|
| Preferences gear (panel header) | 1 Bell and unread badge | not recorded (settled before design_scope.md existed) | later: user-communication-2-notification-email | user-communication-1-notifications-core | 2026-09-27 | No preferences page yet |
| Preferences button (centre header) | 2 Notification centre | not recorded (settled before design_scope.md existed) | leave out | user-communication-1-notifications-core | 2026-09-27 | Same as the gear |
| "about" line on centre rows | 2 Notification centre | not recorded (settled before design_scope.md existed) | leave out | user-communication-1-notifications-core | 2026-09-27 | Left out by the done spec's plan |
| "Show older notifications" | 2 Notification centre | not recorded (settled before design_scope.md existed) | leave out | user-communication-1-notifications-core | 2026-09-27 | The centre keeps its pagination |
| `role="dialog"` / `aria-haspopup="dialog"` on the panel | 1 Bell and unread badge | not recorded (settled before design_scope.md existed) | leave out | user-communication-1-notifications-core | 2026-09-27 | The panel is a disclosure and does not trap focus |
| Message notification (panel and centre) | 1 Bell and unread badge, 2 Notification centre | not recorded (settled before design_scope.md existed) | leave out | user-communication-1-notifications-core | 2026-09-27 | No message category until `user-communication-4-direct-messaging` |
| Course completion: notification item, preference row and email | 1, 2, 3, 4 | Build a course completion notification, preference row and email? | leave out | user-communication | 2026-09-29 | Keeps notifications-core's Decision 12 |
| In-app On/Off switch per category | 3 Notification preferences | Build an in-app switch per category? | leave out | user-communication | 2026-09-29 | Preferences apply to email only, as idea 2 settles |
| Course or cohort context on conversations (inbox rows, thread header, educator rows) | 5, 6, 8 | Should conversations carry a course or cohort context? | leave out | user-communication | 2026-09-29 | The design is visual only; no new functionality from it |
| Site admin group in the educator sidebar (Reports with count, Site settings) | 8 Educator inbox, 11 Report queue | Build the Site admin sidebar group? | leave out | user-communication | 2026-09-29 | The design is visual only; spec 6 decides where the queue lives |
| Application and Deadline category rows | 2 Notification centre | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Only `course.registered` exists; categories come from specs, not the design |
| Per-category description line | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | `NotificationCategory` has no description; not in idea 2 |
| Site-disabled category row (Turned off tag, lock, reason) | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Idea 2 has per-site defaults, not a site switch-off |
| "Application updates" preference row | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | No such category |
| Autosave ("Changes save as you make them") | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | How preferences save is spec 2's decision |
| Breadcrumb "Profile > Notification preferences" | 3 Notification preferences | none | open: ask when user-communication-2-notification-email starts | user-communication | 2026-09-29 | Idea 2 lists where the page sits as open |
| Signed-in header on the unsubscribe landing | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Unsubscribe works without logging in (idea 2) |
| "New messages" on Daily digest | 3 Notification preferences | none | open: ask when user-communication-7-email-digests starts | user-communication | 2026-09-29 | Idea 7 lists what a digest holds for conversations as open |
| Quiet hours on/off switch | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Idea 7 describes a window, not a switch |
| "Change timezone" link | 3 Notification preferences | none: the visual-only rule | leave out | user-communication | 2026-09-29 | No user timezone setting; idea 7 lists its source as open |
| Email as a select at 375px | 3 Notification preferences | none | open: ask when user-communication-7-email-digests starts | user-communication | 2026-09-29 | Layout only; spec 7 owns the four-option control |
| Email footer "You're getting this email because…" line | 4 Notification email | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Not in the brief or idea 2 |
| Postal address in the email footer | 4 Notification email | none: the visual-only rule | leave out | user-communication | 2026-09-29 | No address in the email branding context |
| "N new" count on a conversation row | 5 Learner inbox | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Idea 4 has a per-conversation marker, not a count |
| Conversation options menu in the thread header | 5 Learner inbox | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Only a per-message menu is asked for |
| Closed-thread and empty-picker copy naming per-course messaging settings | 6, 7 | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Copy must name the policy's real levels (spec 3), not a course switch |
| "You already have a conversation" in the picker | 7 Starting a conversation | none | open: ask when user-communication-4-direct-messaging starts | user-communication | 2026-09-29 | Depends on one conversation per pair, open in idea 4 |
| Cohort filter in the educator inbox | 8 Educator inbox | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Not in idea 5; a conversation has no cohort |
| Educator "New message" button | 8 Educator inbox | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Idea 5 starts conversations from the quick view |
| Per-organisation unread counts (switcher menu, mobile note) | 8 Educator inbox | none: the visual-only rule | leave out | user-communication | 2026-09-29 | The inbox shows the open organisation only |
| Quick view Messages tab in the denied state, with reason | 9 Quick view Messages tab | none: the visual-only rule | leave out | user-communication | 2026-09-29 | Idea 5 hides the tab when messaging is not allowed |
| "Showing the latest messages" line with "Open in Messages" | 9 Quick view Messages tab | none | open: ask when user-communication-5-educator-messaging starts | user-communication | 2026-09-29 | Idea 5 lists how much thread the tab shows as open |
| "Block <name>" on the Report sent step | 10 Report and block | none | open: ask when user-communication-6-moderation starts | user-communication | 2026-09-29 | Idea 6 lists whether reporting also blocks as open |
| "<Name> isn't told who reported it" line | 10 Report and block | none: the visual-only rule | leave out | user-communication | 2026-09-29 | A privacy promise no spec makes |
| Extra block consequences (earlier messages stay, unblock any time) | 10 Report and block | none | open: ask when user-communication-6-moderation starts | user-communication | 2026-09-29 | Copy depends on idea 6's open unblock question |
| Message menu on instructor and TA messages | 10 Report and block | none | open: ask when user-communication-6-moderation starts | user-communication | 2026-09-29 | Idea 6 lists whether a learner may block an educator as open |
| Report queue inside the educator interface | 11 Report queue | none | open: ask when user-communication-6-moderation starts | user-communication | 2026-09-29 | Idea 6 lists the queue's location as open |
| Stored text of a hidden message shown in the queue | 11 Report queue | none: the visual-only rule | leave out | user-communication | 2026-09-29 | The brief says the message is kept, not shown |
