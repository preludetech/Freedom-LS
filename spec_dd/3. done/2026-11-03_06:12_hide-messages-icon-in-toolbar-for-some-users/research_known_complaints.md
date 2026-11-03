# Research: known complaints about LMS messaging availability

Scope note: two web searches only (Moodle, Canvas). Search snippets were summarised, not full thread reads. Items marked "not researched" were not covered and are not claimed.

## Findings (sourced)

1. **No per-course off switch (Moodle).** Private messaging is a site-wide admin setting ("Enable messaging system"). Users ask for per-course control and are pointed at workarounds: removing `moodle/course:viewparticipants` from the Student role (reported not to hide participants in the mobile app), core-code hacks to block student-to-student messages (break between versions), or hiding the "Message My Teacher" block per course.
   - https://moodle.org/mod/forum/discuss.php?d=343495
   - https://moodle.org/mod/forum/discuss.php?d=326347
   - https://docs.moodle.org/502/en/Messaging
   - https://wnpspt.waseda.jp/teacher_en/wsdmoodle/?p=5818

2. **Turning it off leaves orphan links (Moodle).** After disabling the messaging system site-wide, some menu links remain and must be removed by hand in theme settings. This is the "icon that appears but leads nowhere" complaint.
   - https://elearning.3rdwavemedia.com/?p=3797

3. **No course-level control (Canvas).** A Canvas moderator said disabling cannot be done at the instructor/course level. An admin can disable student-to-student messaging, but it applies to the whole account and affects all instructors.
   - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-ARCHIVED-Restrict-Email-inbox/m-p/187992
   - https://community.canvaslms.com/t5/Canvas-Question-Forum/Disable-Canvas-messaging/m-p/632625
   - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Disabling-Canvas-Inbox/m-p/580756

4. **Instructor overload.** Instructors ask for inbox disabling or auto-reply. One said they now simply ignore Canvas Inbox messages. Another wanted the inbox blocked during exams.
   - https://community.canvaslms.com/t5/Canvas-Question-Forum/Can-you-Please-Allow-Inbox-Disabling-or-Auto-reply/m-p/529722
   - https://community.canvaslms.com/t5/Idea-Conversations/Disconnect-Student-Ability-to-Send-Email-Through-Canvas/idi-p/488677

5. **Partial restrictions are confusing.** At WWU, student-to-all-students messaging was turned off, but students can still message instructors and their group members. Users must be told what still works, and discussions are suggested as the alternative.
   - https://atus.wwu.edu/kb/decision-science-classes-have-canvas-messaging-tools-disabled
   - https://atus.wwu.edu/kb/changes-canvas-inbox-messaging

6. **Role/user-level setting requested.** The Canvas Ideas thread "Make inbox rights a user level setting" shows demand for finer granularity than the account level.
   - https://community.canvaslms.com/t5/Canvas-Ideas/Notifications-Make-inbox-rights-a-user-level-setting/idc-p/348341

## Not researched (no sourced evidence; treat as hypotheses)
- Spam or abuse via learner messaging in free/MOOC courses.
- Messages lost when a feature is turned off.
- Unread badges for hidden features.
- Confusing empty inboxes.

## Implications for FLS (inference, not sourced)
- Decide visibility from the learner's context (organisation or site messaging setting, plus whether any permitted recipient exists). A global-only toggle is the most common complaint.
- Hide every entry point together (icon, menu links, badge, notification links), so none is left leading nowhere.
- Hiding the icon should not delete existing messages. Keep the data and the direct URL behaviour defined.
- Make the rule explicit and discoverable to admins (one clearly labelled setting). Tell users what still works under a partial restriction.

status: ok
